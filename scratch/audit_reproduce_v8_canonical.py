"""
Audit and Reproduce Baseline v8 Canonical vs v8 Final (In-Sample) and v9/v10/v11 Baselines.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
SAVED_MODELS_DIR = REPO_ROOT / "ValueCell_MT5" / "python" / "valuecell" / "models" / "saved" / "filter_latest"
DATASET_V5_PATH = SAVED_MODELS_DIR / "dataset_v5_unconstrained.csv"
DATASET_V9_PATH = SAVED_MODELS_DIR / "dataset_v9_unconstrained.csv"
DATASET_V11_PATH = SAVED_MODELS_DIR / "dataset_v11_unconstrained.csv"

SCORED_V8_WF_PATH = SAVED_MODELS_DIR / "scored_v8_walk_forward.csv"
SCORED_V8_FINAL_PATH = SAVED_MODELS_DIR / "scored_v8_final.csv"
SCORED_V9_WF_PATH = SAVED_MODELS_DIR / "scored_v9_walk_forward.csv"
SCORED_V10_WF_PATH = SAVED_MODELS_DIR / "scored_v10_walk_forward.csv"
SCORED_V11_WF_PATH = SAVED_MODELS_DIR / "scored_v11_walk_forward.csv"


def file_sha256(path: Path) -> str:
    if not path.exists():
        return "MISSING"
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()[:16]


def get_dynamic_lot(rr: float) -> float:
    if rr >= 2.0:
        return 0.07
    elif rr >= 1.5:
        return 0.04
    elif rr >= 1.2:
        return 0.02
    elif rr >= 1.05:
        return 0.01
    return 0.0


def max_drawdown(pnl_series: pd.Series) -> float:
    if len(pnl_series) == 0:
        return 0.0
    equity = pnl_series.cumsum()
    peak = equity.cummax()
    dd = (equity - peak).min()
    return float(dd)


def profit_factor(pnl_series: pd.Series) -> float:
    wins = pnl_series[pnl_series > 0].sum()
    losses = abs(pnl_series[pnl_series < 0].sum())
    if losses == 0:
        return float("inf") if wins > 0 else 0.0
    return float(wins / losses)


def evaluate_scored_df(df: pd.DataFrame, model_name: str, has_news_filter: bool = False, has_weekend_filter: bool = False) -> dict:
    if "ea_status" in df.columns:
        ea = df[df["ea_status"] == "EXECUTED"].copy().reset_index(drop=True)
    elif "source" in df.columns:
        ea = df[df["source"] == "EXECUTED"].copy().reset_index(drop=True)
    else:
        ea = df.copy().reset_index(drop=True)

    if "actual_net_profit" not in ea.columns and "net_profit" in ea.columns:
        ea["actual_net_profit"] = ea["net_profit"]
    
    ea["expected_rr"] = ea["predicted_mfe"] / np.maximum(1.0, ea["predicted_mae"])
    
    t_dt = pd.to_datetime(ea["entry_time"], utc=True)
    is_friday_late = (t_dt.dt.weekday == 4) & (t_dt.dt.hour >= 18)
    is_monday_open = ((t_dt.dt.weekday == 6) & (t_dt.dt.hour >= 22)) | ((t_dt.dt.weekday == 0) & (t_dt.dt.hour < 1))
    is_weekend = is_friday_late | is_monday_open

    pass_mask = ea["expected_rr"] >= 1.05
    if has_news_filter and "is_news_blackout" in ea.columns:
        pass_mask = pass_mask & (ea["is_news_blackout"] == 0)
    if has_weekend_filter:
        pass_mask = pass_mask & (~is_weekend)

    passed = ea[pass_mask].copy().reset_index(drop=True)
    
    passed["dyn_lot"] = [get_dynamic_lot(r) for r in passed["expected_rr"]]
    passed["dyn_net_pnl"] = passed["actual_net_profit"] * (passed["dyn_lot"] / 0.01)
    
    n_trades = len(passed)
    n_wins = int((passed["actual_net_profit"] > 0).sum())
    win_rate = (n_wins / n_trades * 100.0) if n_trades > 0 else 0.0
    flat_pnl = float(passed["actual_net_profit"].sum())
    dyn_pnl = float(passed["dyn_net_pnl"].sum())
    pf = profit_factor(passed["dyn_net_pnl"])
    dd = max_drawdown(passed["dyn_net_pnl"])

    # Per year breakdown
    by_year = {}
    for yr in sorted(ea["year"].unique()):
        yr_sub = passed[passed["year"] == yr]
        yr_trd = len(yr_sub)
        yr_wins = int((yr_sub["actual_net_profit"] > 0).sum())
        yr_wr = (yr_wins / yr_trd * 100.0) if yr_trd > 0 else 0.0
        yr_flat = float(yr_sub["actual_net_profit"].sum())
        yr_dyn = float(yr_sub["dyn_net_pnl"].sum())
        by_year[int(yr)] = {
            "trades": yr_trd,
            "wins": yr_wins,
            "win_rate": yr_wr,
            "flat_pnl": yr_flat,
            "dyn_pnl": yr_dyn,
        }

    return {
        "model": model_name,
        "trades": n_trades,
        "wins": n_wins,
        "win_rate": win_rate,
        "flat_net_pnl": flat_pnl,
        "dynamic_net_pnl": dyn_pnl,
        "profit_factor": pf,
        "max_drawdown": dd,
        "by_year": by_year,
    }


def main():
    print("=" * 80)
    print("AUDIT BASELINE REPRODUCIBILITY & DATASET FINGERPRINT")
    print("=" * 80)

    for p in [DATASET_V5_PATH, DATASET_V9_PATH, DATASET_V11_PATH]:
        if p.exists():
            df = pd.read_csv(p)
            print(f"Dataset: {p.name:30} | Rows: {len(df):5} | Cols: {len(df.columns):3} | SHA256: {file_sha256(p)}")

    print("\n" + "=" * 80)
    print("REKONSILIASI HASIL MODEL DARI RAW SCORED CSV")
    print("=" * 80)

    # 1. v8 Walk-Forward (Canonical)
    df_v8_wf = pd.read_csv(SCORED_V8_WF_PATH)
    res_v8_wf = evaluate_scored_df(df_v8_wf, "v8 Walk-Forward (Canonical OOS)")

    # 2. v8 Final (In-Sample)
    df_v8_fn = pd.read_csv(SCORED_V8_FINAL_PATH) if SCORED_V8_FINAL_PATH.exists() else df_v8_wf
    res_v8_fn = evaluate_scored_df(df_v8_fn, "v8 Final (In-Sample Fit)")

    # 3. v9 Walk-Forward (News + Weekend Aware)
    df_v9_wf = pd.read_csv(SCORED_V9_WF_PATH)
    res_v9_wf = evaluate_scored_df(df_v9_wf, "v9 Walk-Forward (News+Weekend)", has_news_filter=True, has_weekend_filter=True)

    # 4. v10 Walk-Forward (Multi-Output Joint)
    df_v10_wf = pd.read_csv(SCORED_V10_WF_PATH)
    res_v10_wf = evaluate_scored_df(df_v10_wf, "v10 Walk-Forward (Joint)", has_news_filter=True, has_weekend_filter=True)

    # 5. v11 Walk-Forward (Planned R:R + Reject Reason)
    df_v11_wf = pd.read_csv(SCORED_V11_WF_PATH)
    res_v11_wf = evaluate_scored_df(df_v11_wf, "v11 Walk-Forward (Planned R:R)", has_news_filter=True, has_weekend_filter=True)

    all_models = [res_v8_wf, res_v8_fn, res_v9_wf, res_v10_wf, res_v11_wf]

    print(f"\n{'Model Name':35} | {'Trades':6} | {'WinRate':8} | {'Flat Net PnL':14} | {'Dynamic Net PnL':16} | {'PF':6} | {'Max DD':10}")
    print("-" * 105)
    for r in all_models:
        print(f"{r['model']:35} | {r['trades']:6} | {r['win_rate']:7.1f}% | {r['flat_net_pnl']:12.2f} USD | {r['dynamic_net_pnl']:14.2f} USD | {r['profit_factor']:5.2f} | {r['max_drawdown']:9.2f}")

    print("\n" + "=" * 80)
    print("BREAKDOWN TAHUNAN DYNAMIC NET PNL (USD) SETIAP MODEL:")
    print("=" * 80)
    years = sorted(res_v8_wf["by_year"].keys())
    header = f"{'Year':6} | " + " | ".join([f"{r['model'][:12]:12}" for r in all_models])
    print(header)
    print("-" * len(header))
    for yr in years:
        row = f"{yr:6} | "
        for r in all_models:
            pnl = r["by_year"].get(yr, {}).get("dyn_pnl", 0.0)
            row += f"{pnl:12.2f} | "
        print(row)

    print("\n" + "=" * 80)
    print("BREAKDOWN TAHUNAN FLAT NET PNL 0.01 LOT (USD):")
    print("=" * 80)
    header = f"{'Year':6} | " + " | ".join([f"{r['model'][:12]:12}" for r in all_models])
    print(header)
    print("-" * len(header))
    for yr in years:
        row = f"{yr:6} | "
        for r in all_models:
            pnl = r["by_year"].get(yr, {}).get("flat_pnl", 0.0)
            row += f"{pnl:12.2f} | "
        print(row)

    # Save baseline canonical specification to JSON
    baseline_spec = {
        "canonical_baseline_name": "v8_walk_forward_normalized",
        "dataset_v5_sha256": file_sha256(DATASET_V5_PATH),
        "total_trades": res_v8_wf["trades"],
        "win_rate": res_v8_wf["win_rate"],
        "flat_net_pnl": res_v8_wf["flat_net_pnl"],
        "dynamic_net_pnl": res_v8_wf["dynamic_net_pnl"],
        "profit_factor": res_v8_wf["profit_factor"],
        "max_drawdown": res_v8_wf["max_drawdown"],
        "by_year": res_v8_wf["by_year"],
    }
    spec_path = REPO_ROOT / "scratch" / "baseline_v8_canonical_spec.json"
    with open(spec_path, "w") as f:
        json.dump(baseline_spec, f, indent=2)
    print(f"\n✅ Baseline canonical v8 specification saved to: {spec_path}")


if __name__ == "__main__":
    main()
