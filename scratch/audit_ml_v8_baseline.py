"""Audit existing ML v8 artifacts without modifying production model files."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = REPO_ROOT / "ValueCell_MT5" / "python" / "valuecell" / "models" / "saved" / "filter_latest"
BACKTEST_DIR = REPO_ROOT / "Backtest_result"

DATASET_PATH = MODEL_DIR / "dataset_v5_unconstrained.csv"
SCORED_PATHS = {
    "v8_walk_forward_existing": MODEL_DIR / "scored_v8_walk_forward.csv",
    "v8_final_existing": MODEL_DIR / "scored_v8_final.csv",
}

RAW_PATTERNS = (
    "Backtest_Results_XAUUSD_*.csv",
    "Backtest_Summary_XAUUSD_*.csv",
    "MarketData_XAUUSD_M15_*.csv",
    "MarketData_XAUUSD_H1_*.csv",
    "MarketData_XAUUSD_H4_*.csv",
    "LLHHBOSData_XAUUSD_*.csv",
    "SessionZone_XAUUSD_*.csv",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dynamic_lot(expected_rr: pd.Series) -> pd.Series:
    conditions = [
        expected_rr >= 2.0,
        expected_rr >= 1.5,
        expected_rr >= 1.2,
        expected_rr >= 1.05,
    ]
    return pd.Series(np.select(conditions, [0.07, 0.04, 0.02, 0.01], default=0.0), index=expected_rr.index)


def profit_factor(values: pd.Series) -> float:
    gross_profit = float(values[values > 0].sum())
    gross_loss = abs(float(values[values < 0].sum()))
    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else 0.0
    return gross_profit / gross_loss


def max_drawdown(values: pd.Series) -> float:
    if values.empty:
        return 0.0
    equity = values.cumsum()
    return float((equity - equity.cummax()).min())


def json_safe(value):
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, float) and not np.isfinite(value):
        return "Infinity" if value > 0 else "-Infinity"
    return value


def summarize(frame: pd.DataFrame) -> dict[str, float | int]:
    flat_pnl = frame["actual_net_profit"].astype(float)
    dynamic_pnl = frame["dynamic_net_pnl"].astype(float)
    return {
        "trades": int(len(frame)),
        "wins": int((flat_pnl > 0).sum()),
        "losses": int((flat_pnl <= 0).sum()),
        "win_rate_pct": float((flat_pnl > 0).mean() * 100.0) if len(frame) else 0.0,
        "flat_net_pnl": float(flat_pnl.sum()),
        "dynamic_net_pnl": float(dynamic_pnl.sum()),
        "profit_factor_dynamic": profit_factor(dynamic_pnl),
        "maximum_drawdown_dynamic": max_drawdown(dynamic_pnl),
        "expectancy_flat": float(flat_pnl.mean()) if len(frame) else 0.0,
        "expectancy_dynamic": float(dynamic_pnl.mean()) if len(frame) else 0.0,
    }


def evaluate_scored(path: Path, years: set[int] | None = None) -> tuple[dict, pd.DataFrame]:
    path = path.resolve()
    frame = pd.read_csv(path)
    required = {"entry_time", "predicted_mfe", "predicted_mae", "actual_net_profit"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{path.name} missing required columns: {missing}")

    if "ea_status" in frame.columns:
        frame = frame[frame["ea_status"].astype(str).str.upper() == "EXECUTED"].copy()
    elif "source" in frame.columns:
        frame = frame[frame["source"].astype(str).str.upper() == "EXECUTED"].copy()

    frame["entry_time"] = pd.to_datetime(frame["entry_time"], utc=True, errors="raise")
    frame["year"] = frame["entry_time"].dt.year
    if years is not None:
        frame = frame[frame["year"].isin(years)].copy()

    frame = frame.sort_values(["entry_time", "signal"], kind="stable").reset_index(drop=True)
    frame["expected_rr"] = frame["predicted_mfe"] / frame["predicted_mae"].clip(lower=1.0)
    frame["dynamic_lot"] = dynamic_lot(frame["expected_rr"])
    frame = frame[frame["dynamic_lot"] > 0].copy().reset_index(drop=True)
    frame["dynamic_net_pnl"] = frame["actual_net_profit"] * (frame["dynamic_lot"] / 0.01)

    by_year = {
        str(int(year)): summarize(group.reset_index(drop=True))
        for year, group in frame.groupby("year", sort=True)
    }
    by_signal = {
        str(signal): summarize(group.reset_index(drop=True))
        for signal, group in frame.groupby("signal", sort=True)
    }
    by_session = {
        str(session): summarize(group.reset_index(drop=True))
        for session, group in frame.groupby("session_name", sort=True)
    }
    price_bins = pd.cut(
        frame["entry_price"],
        bins=[0, 1500, 2000, 2500, 3000, 4000, float("inf")],
        labels=["<1500", "1500-1999", "2000-2499", "2500-2999", "3000-3999", ">=4000"],
        right=False,
    )
    by_price_regime = {
        str(regime): summarize(frame.loc[index].reset_index(drop=True))
        for regime, index in frame.groupby(price_bins, observed=True).groups.items()
    }

    report = {
        "artifact": str(path.relative_to(REPO_ROOT)),
        "sha256": sha256(path),
        "metric_contract": {
            "win": "actual_net_profit > 0",
            "loss": "actual_net_profit <= 0",
            "flat_net_pnl": "sum(actual_net_profit) at 0.01 lot",
            "dynamic_net_pnl": "actual_net_profit * dynamic_lot / 0.01",
            "rr_threshold": 1.05,
            "dynamic_lot_tiers": {"1.05": 0.01, "1.20": 0.02, "1.50": 0.04, "2.00": 0.07},
        },
        "scope_years": sorted(int(year) for year in frame["year"].unique()),
        "total": summarize(frame),
        "by_year": by_year,
        "by_signal": by_signal,
        "by_session": by_session,
        "by_price_regime": by_price_regime,
    }
    return report, frame


def raw_manifest() -> list[dict[str, str | int]]:
    manifest = []
    for pattern in RAW_PATTERNS:
        for path in sorted(BACKTEST_DIR.glob(pattern)):
            manifest.append({
                "path": str(path.relative_to(REPO_ROOT)),
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
            })
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--walk-forward-path", type=Path, default=SCORED_PATHS["v8_walk_forward_existing"])
    parser.add_argument("--canonical", action="store_true")
    args = parser.parse_args()

    run_id = datetime.now(timezone.utc).strftime("v8_baseline_audit_%Y%m%dT%H%M%SZ")
    output_dir = args.output_dir or (REPO_ROOT / "scratch" / "ml_experiments" / run_id)
    output_dir.mkdir(parents=True, exist_ok=False)

    scored_paths = {
        "v8_walk_forward": args.walk_forward_path,
        "v8_final_existing": SCORED_PATHS["v8_final_existing"],
    }
    reports = {}
    scored_frames = {}
    for name, path in scored_paths.items():
        reports[name], scored_frames[name] = evaluate_scored(path)

    common_years = set(reports["v8_walk_forward"]["scope_years"]) & set(
        reports["v8_final_existing"]["scope_years"]
    )
    reports["v8_final_existing_common_years"], _ = evaluate_scored(
        SCORED_PATHS["v8_final_existing"], common_years
    )

    manifest = raw_manifest()
    dataset_manifest = {
        "path": str(DATASET_PATH.relative_to(REPO_ROOT)),
        "size_bytes": DATASET_PATH.stat().st_size,
        "sha256": sha256(DATASET_PATH),
        "rows": int(len(pd.read_csv(DATASET_PATH, usecols=["entry_time"]))),
    }
    audit = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "CANONICAL_V8_OOS" if args.canonical else "AUDIT_ONLY_NOT_CANONICAL",
        "dataset": dataset_manifest,
        "raw_files": manifest,
        "raw_manifest_sha256": hashlib.sha256(
            json.dumps(manifest, sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "reports": reports,
    }

    (output_dir / "audit.json").write_text(
        json.dumps(json_safe(audit), indent=2, allow_nan=False),
        encoding="utf-8",
    )
    for name, frame in scored_frames.items():
        frame.to_csv(output_dir / f"accepted_trades_{name}.csv", index=False)

    print(json.dumps({
        "output_dir": str(output_dir),
        "dataset": dataset_manifest,
        "raw_file_count": len(manifest),
        "reports": {name: report["total"] for name, report in reports.items()},
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())