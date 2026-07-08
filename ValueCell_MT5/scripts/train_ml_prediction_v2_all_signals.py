"""
Train/evaluate ML Prediction v2 from all Backtest_result signal candidates.

This is an offline research script. It does not overwrite filter_latest.

Sources:
- Backtest_Results_XAUUSD_*.csv: EXECUTED and REJECTED EA signals
- LLHHBOSData_XAUUSD_*.csv: BoS/CHoCH structure candidates
- MarketData_XAUUSD_M15/H1/H4_*.csv: features and forward TP/SL labels
- SessionZone_XAUUSD_*.csv: session context features
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from loguru import logger
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.preprocessing import StandardScaler

try:
    from xgboost import XGBClassifier
except Exception as exc:  # pragma: no cover
    raise RuntimeError("xgboost is required for v2 training") from exc

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_ROOT.parent
PYTHON_DIR = PROJECT_ROOT / "python"

if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

from valuecell.models.feature_engineer import FeatureEngineer  # noqa: E402


FIXED_RISK = 30.0
FIXED_TARGET = 30.0
MAX_FORWARD_BARS = 1920  # 20 trading days on M15
THRESHOLDS = [round(x, 2) for x in np.arange(0.50, 0.86, 0.05)]


def parse_time(value: Any) -> pd.Timestamp:
    return pd.to_datetime(value, format="%Y.%m.%d %H:%M:%S", errors="coerce")


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def normalize_market_df(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    df["time"] = df["time"].map(parse_time)
    df = df.dropna(subset=["time"]).sort_values("time").reset_index(drop=True)
    return df


def load_structure_events(path: Path) -> pd.DataFrame:
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    header_idx = 0
    for idx, line in enumerate(lines):
        if line.startswith("Type,Direction/Action"):
            header_idx = idx
            break

    df = pd.read_csv(path, skiprows=header_idx)
    df.columns = [c.strip() for c in df.columns]
    df["time"] = df["Time"].map(parse_time)
    df = df.dropna(subset=["time"]).sort_values("time").reset_index(drop=True)
    return df


def load_session_zones(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()

    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]
    df["start_time"] = df["StartTime"].map(parse_time)
    df["end_time"] = df["EndTime"].map(parse_time)
    df = df.dropna(subset=["start_time", "end_time"]).sort_values("start_time")
    return df.reset_index(drop=True)


def direction_from_structure(row: pd.Series) -> str:
    raw_type = str(row.get("Type", "")).upper()
    raw_dir = str(row.get("Direction/Action", "")).upper()
    if "BULL" in raw_dir or "BULL" in raw_type:
        return "BULLISH"
    if "BEAR" in raw_dir or "BEAR" in raw_type:
        return "BEARISH"
    if raw_type == "HH":
        return "BULLISH"
    if raw_type == "LL":
        return "BEARISH"
    return "NEUTRAL"


def normalized_event_type(row: pd.Series) -> str:
    raw_type = str(row.get("Type", "")).upper()
    if "BOS" in raw_type:
        kind = "BOS"
    elif "CHOCH" in raw_type:
        kind = "CHOCH"
    else:
        kind = raw_type
    return f"{kind}_{direction_from_structure(row)}"


def row_to_event(row: pd.Series) -> dict[str, Any]:
    return {
        "type": normalized_event_type(row),
        "price": safe_float(row.get("Price")),
        "time": row["time"].to_pydatetime(),
    }


def last_rows_at_or_before(df: pd.DataFrame, when: pd.Timestamp, count: int) -> pd.DataFrame:
    idx = np.searchsorted(df["time"].values, np.datetime64(when), side="right")
    return df.iloc[max(0, idx - count) : idx].copy()


def current_bar_at_or_before(df: pd.DataFrame, when: pd.Timestamp) -> dict[str, Any] | None:
    rows = last_rows_at_or_before(df, when, 1)
    if rows.empty:
        return None

    row = rows.iloc[-1]
    return {
        "time": row["time"].to_pydatetime(),
        "open": safe_float(row["open"]),
        "high": safe_float(row["high"]),
        "low": safe_float(row["low"]),
        "close": safe_float(row["close"]),
        "volume": safe_float(row.get("volume")),
    }


def atr_value(df: pd.DataFrame, period: int = 14) -> float:
    if len(df) < period + 1:
        return 0.0
    high = df["high"].astype(float).to_numpy()
    low = df["low"].astype(float).to_numpy()
    close = df["close"].astype(float).to_numpy()
    tr = np.maximum.reduce(
        [
            high[1:] - low[1:],
            np.abs(high[1:] - close[:-1]),
            np.abs(low[1:] - close[:-1]),
        ]
    )
    return float(np.mean(tr[-period:])) if len(tr) >= period else 0.0


def trend_features(prefix: str, history: pd.DataFrame, entry_price: float, signal: str) -> dict[str, float]:
    if history.empty:
        return {
            f"{prefix}_above_ema200": 0.0,
            f"{prefix}_trend_aligned": 0.0,
            f"{prefix}_atr_14": 0.0,
            f"{prefix}_vol_ratio": 1.0,
            f"{prefix}_ema200_distance_atr": 0.0,
        }

    last = history.iloc[-1]
    ema = safe_float(last.get("ema200"), entry_price)
    close = safe_float(last.get("close"), entry_price)
    atr = atr_value(history)
    above = 1.0 if close > ema else 0.0
    aligned = 1.0 if (signal == "BUY" and close > ema) or (signal == "SELL" and close < ema) else 0.0
    avg_vol = history["volume"].tail(20).mean() if "volume" in history and len(history) >= 20 else 0.0
    vol_ratio = safe_float(last.get("volume"), 0.0) / avg_vol if avg_vol else 1.0
    distance_atr = (entry_price - ema) / atr if atr else 0.0
    return {
        f"{prefix}_above_ema200": above,
        f"{prefix}_trend_aligned": aligned,
        f"{prefix}_atr_14": atr,
        f"{prefix}_vol_ratio": float(vol_ratio),
        f"{prefix}_ema200_distance_atr": float(distance_atr),
    }


def momentum_features(m15_history: pd.DataFrame, entry_price: float) -> dict[str, float]:
    out = {}
    atr = atr_value(m15_history)
    for lookback in (3, 5, 10):
        if len(m15_history) > lookback and atr:
            prev = safe_float(m15_history.iloc[-lookback - 1].get("close"), entry_price)
            out[f"momentum_{lookback}_atr"] = (entry_price - prev) / atr
        else:
            out[f"momentum_{lookback}_atr"] = 0.0
    return out


def session_features(sessions: pd.DataFrame, when: pd.Timestamp, entry_price: float, atr: float) -> dict[str, Any]:
    default = {
        "session_zone_name": "UNKNOWN",
        "session_zone_is_dst": "UNKNOWN",
        "minutes_from_session_open": 0.0,
        "minutes_to_session_close": 0.0,
        "session_range_points": 0.0,
        "price_position_session_range": 0.5,
        "distance_to_session_high_atr": 0.0,
        "distance_to_session_low_atr": 0.0,
    }
    if sessions.empty:
        return default

    rows = sessions[(sessions["start_time"] <= when) & (when <= sessions["end_time"])]
    if rows.empty:
        rows = sessions[sessions["start_time"] <= when].tail(1)
    if rows.empty:
        return default

    row = rows.iloc[-1]
    high = safe_float(row.get("HighPrice"), entry_price)
    low = safe_float(row.get("LowPrice"), entry_price)
    rng = max(high - low, 0.0)
    pos = (entry_price - low) / rng if rng else 0.5
    return {
        "session_zone_name": str(row.get("Session", "UNKNOWN")),
        "session_zone_is_dst": str(row.get("IsDST", "UNKNOWN")),
        "minutes_from_session_open": float((when - row["start_time"]).total_seconds() / 60),
        "minutes_to_session_close": float((row["end_time"] - when).total_seconds() / 60),
        "session_range_points": safe_float(row.get("RangePoints"), 0.0),
        "price_position_session_range": float(pos),
        "distance_to_session_high_atr": (high - entry_price) / atr if atr else 0.0,
        "distance_to_session_low_atr": (entry_price - low) / atr if atr else 0.0,
    }


def make_trade_candidates(trades: pd.DataFrame, suffix: str) -> list[dict[str, Any]]:
    candidates = []
    for idx, row in trades.iterrows():
        signal = str(row.get("Type", "")).upper()
        if signal not in {"BUY", "SELL"}:
            continue
        entry_time = parse_time(row.get("EntryTime"))
        if pd.isna(entry_time):
            continue
        status = str(row.get("Status", "")).upper()
        candidates.append(
            {
                "source_year": suffix,
                "source": status if status in {"EXECUTED", "REJECTED"} else "BACKTEST_RESULT",
                "source_priority": 3 if status == "EXECUTED" else 2,
                "source_row": idx,
                "entry_time": entry_time,
                "signal": signal,
                "entry_price": safe_float(row.get("EntryPrice")),
                "timeframe": str(row.get("Timeframe", "M15")),
                "reject_reason": str(row.get("Reject_Reason", "N/A")),
                "session_name": str(row.get("Session", "UNKNOWN")),
                "session_is_dst": str(row.get("Session_IsDST", "UNKNOWN")),
                "actual_net_profit": safe_float(row.get("Net_Profit")),
                "actual_status": status,
                "actual_sl": safe_float(row.get("SL")),
                "actual_tp": safe_float(row.get("TP")),
                "structure_kind": "TRADE_ROW",
                "structure_direction": signal,
            }
        )
    return candidates


def make_structure_candidates(structures: pd.DataFrame, suffix: str, m15: pd.DataFrame) -> list[dict[str, Any]]:
    candidates = []
    for idx, row in structures.iterrows():
        raw_type = str(row.get("Type", "")).upper()
        if "BOS" not in raw_type and "CHOCH" not in raw_type:
            continue
        direction = direction_from_structure(row)
        signal = "BUY" if direction == "BULLISH" else "SELL" if direction == "BEARISH" else "UNKNOWN"
        if signal == "UNKNOWN":
            continue
        when = row["time"]
        current = current_bar_at_or_before(m15, when)
        if current is None:
            continue
        candidates.append(
            {
                "source_year": suffix,
                "source": raw_type,
                "source_priority": 1,
                "source_row": idx,
                "entry_time": when,
                "signal": signal,
                "entry_price": safe_float(current["close"], safe_float(row.get("Price"))),
                "timeframe": str(row.get("Timeframe", "M15")),
                "reject_reason": "N/A",
                "session_name": "UNKNOWN",
                "session_is_dst": "UNKNOWN",
                "actual_net_profit": 0.0,
                "actual_status": "STRUCTURE_ONLY",
                "actual_sl": 0.0,
                "actual_tp": 0.0,
                "structure_kind": raw_type,
                "structure_direction": direction,
            }
        )
    return candidates


def dedupe_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    df = pd.DataFrame(candidates)
    if df.empty:
        return []
    df["dedupe_time"] = df["entry_time"].dt.floor("15min")
    df["dedupe_price"] = df["entry_price"].round(1)
    df = df.sort_values(["source_priority"], ascending=False)
    df = df.drop_duplicates(["source_year", "dedupe_time", "signal", "dedupe_price"], keep="first")
    return df.drop(columns=["dedupe_time", "dedupe_price"]).to_dict("records")


def forward_outcome(
    m15: pd.DataFrame,
    when: pd.Timestamp,
    signal: str,
    entry: float,
    sl: float,
    tp: float,
    max_bars: int,
) -> dict[str, Any] | None:
    idx = np.searchsorted(m15["time"].values, np.datetime64(when), side="right")
    future = m15.iloc[idx : idx + max_bars]
    if future.empty:
        return None

    risk = abs(entry - sl)
    target = abs(tp - entry)
    if risk <= 0 or target <= 0:
        return None

    for bars_after, row in enumerate(future.itertuples(index=False), start=1):
        high = safe_float(getattr(row, "high"))
        low = safe_float(getattr(row, "low"))
        if signal == "BUY":
            hit_tp = high >= tp
            hit_sl = low <= sl
        else:
            hit_tp = low <= tp
            hit_sl = high >= sl
        if hit_tp and hit_sl:
            return None
        if hit_tp:
            return {
                "label_win": 1,
                "outcome": "TP",
                "outcome_r": target / risk,
                "bars_to_outcome": bars_after,
                "label_sl": sl,
                "label_tp": tp,
            }
        if hit_sl:
            return {
                "label_win": 0,
                "outcome": "SL",
                "outcome_r": -1.0,
                "bars_to_outcome": bars_after,
                "label_sl": sl,
                "label_tp": tp,
            }
    return None


def label_levels(candidate: dict[str, Any]) -> tuple[float, float]:
    entry = safe_float(candidate["entry_price"])
    sl = safe_float(candidate.get("actual_sl"))
    tp = safe_float(candidate.get("actual_tp"))
    if sl > 0 and tp > 0 and sl != tp:
        return sl, tp
    if candidate["signal"] == "BUY":
        return entry - FIXED_RISK, entry + FIXED_TARGET
    return entry + FIXED_RISK, entry - FIXED_TARGET


def build_dataset(backtest_dir: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    engineer = FeatureEngineer()
    samples = []
    skipped = {
        "missing_files": 0,
        "no_forward_outcome": 0,
        "missing_bar": 0,
        "candidates_total": 0,
        "candidates_after_dedupe": 0,
    }

    for results_path in sorted(backtest_dir.glob("Backtest_Results_XAUUSD_*.csv")):
        suffix = results_path.stem.replace("Backtest_Results_XAUUSD_", "")
        paths = {
            "structures": backtest_dir / f"LLHHBOSData_XAUUSD_{suffix}.csv",
            "m15": backtest_dir / f"MarketData_XAUUSD_M15_{suffix}.csv",
            "h1": backtest_dir / f"MarketData_XAUUSD_H1_{suffix}.csv",
            "h4": backtest_dir / f"MarketData_XAUUSD_H4_{suffix}.csv",
            "sessions": backtest_dir / f"SessionZone_XAUUSD_{suffix}.csv",
        }
        if not all(paths[k].exists() for k in ("structures", "m15", "h1", "h4")):
            skipped["missing_files"] += 1
            logger.warning("Skipping {} because required CSV missing", suffix)
            continue

        trades = pd.read_csv(results_path)
        trades.columns = [c.strip() for c in trades.columns]
        structures = load_structure_events(paths["structures"])
        m15 = normalize_market_df(paths["m15"])
        h1 = normalize_market_df(paths["h1"])
        h4 = normalize_market_df(paths["h4"])
        sessions = load_session_zones(paths["sessions"])

        candidates = make_trade_candidates(trades, suffix)
        candidates.extend(make_structure_candidates(structures, suffix, m15))
        skipped["candidates_total"] += len(candidates)
        candidates = dedupe_candidates(candidates)
        skipped["candidates_after_dedupe"] += len(candidates)

        year_count = 0
        for candidate in candidates:
            when = candidate["entry_time"]
            current_bar = current_bar_at_or_before(m15, when)
            if current_bar is None:
                skipped["missing_bar"] += 1
                continue

            sl, tp = label_levels(candidate)
            outcome = forward_outcome(
                m15=m15,
                when=when,
                signal=candidate["signal"],
                entry=safe_float(candidate["entry_price"]),
                sl=sl,
                tp=tp,
                max_bars=MAX_FORWARD_BARS,
            )
            if outcome is None:
                skipped["no_forward_outcome"] += 1
                continue

            recent_structures = structures[structures["time"] <= when].tail(50)
            structure_events = [row_to_event(r) for _, r in recent_structures.iterrows()]
            m15_history = last_rows_at_or_before(m15, when, 220)
            h1_history = last_rows_at_or_before(h1, when, 220)
            h4_history = last_rows_at_or_before(h4, when, 220)

            base_features = engineer.extract_features(
                current_bar=current_bar,
                structure_events=structure_events,
                h1_data=h1_history,
                m15_history=m15_history,
            )
            atr = safe_float(base_features.get("atr_14"))
            row = {
                "source_year": candidate["source_year"],
                "year": int(candidate["source_year"][:4]),
                "entry_time": when,
                "source": candidate["source"],
                "actual_status": candidate["actual_status"],
                "signal": candidate["signal"],
                "entry_price": safe_float(candidate["entry_price"]),
                "timeframe": candidate["timeframe"],
                "reject_reason": candidate["reject_reason"],
                "session_name": candidate["session_name"],
                "session_is_dst": candidate["session_is_dst"],
                "structure_kind": candidate["structure_kind"],
                "structure_direction": candidate["structure_direction"],
                "spread": safe_float(m15_history.iloc[-1].get("spread")) if not m15_history.empty else 0.0,
                "actual_net_profit": candidate["actual_net_profit"],
                **outcome,
                **base_features,
                **trend_features("h4", h4_history, safe_float(candidate["entry_price"]), candidate["signal"]),
                **trend_features("h1_ext", h1_history, safe_float(candidate["entry_price"]), candidate["signal"]),
                **momentum_features(m15_history, safe_float(candidate["entry_price"])),
                **session_features(sessions, when, safe_float(candidate["entry_price"]), atr),
            }
            samples.append(row)
            year_count += 1
        logger.info("Built {} v2 samples from {}", year_count, suffix)

    dataset = pd.DataFrame(samples)
    info = {"skipped": skipped}
    return dataset, info


def max_drawdown(values: pd.Series) -> float:
    if values.empty:
        return 0.0
    equity = values.cumsum()
    peak = equity.cummax()
    return float((equity - peak).min())


def profit_factor(values: pd.Series) -> float:
    gross_profit = float(values[values > 0].sum())
    gross_loss = abs(float(values[values < 0].sum()))
    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else 0.0
    return gross_profit / gross_loss


def classification_metrics(y_true: pd.Series, prob: np.ndarray) -> dict[str, float]:
    pred = (prob >= 0.5).astype(int)
    metrics = {
        "accuracy": accuracy_score(y_true, pred),
        "precision": precision_score(y_true, pred, zero_division=0),
        "recall": recall_score(y_true, pred, zero_division=0),
        "f1": f1_score(y_true, pred, zero_division=0),
    }
    if y_true.nunique() > 1:
        metrics["auc"] = roc_auc_score(y_true, prob)
    else:
        metrics["auc"] = 0.0
    return {k: float(v) for k, v in metrics.items()}


def threshold_report(df: pd.DataFrame, split_name: str) -> pd.DataFrame:
    rows = []
    baseline_r = df["outcome_r"]
    rows.append(
        {
            "split": split_name,
            "threshold": 0.0,
            "candidates": len(df),
            "accepted": len(df),
            "winrate": float(df["label_win"].mean()) if len(df) else 0.0,
            "total_r": float(baseline_r.sum()),
            "avg_r": float(baseline_r.mean()) if len(df) else 0.0,
            "max_drawdown_r": max_drawdown(baseline_r),
            "profit_factor": profit_factor(baseline_r),
        }
    )
    for threshold in THRESHOLDS:
        accepted = df[df["probability"] >= threshold]
        values = accepted["outcome_r"]
        rows.append(
            {
                "split": split_name,
                "threshold": threshold,
                "candidates": len(df),
                "accepted": len(accepted),
                "winrate": float(accepted["label_win"].mean()) if len(accepted) else 0.0,
                "total_r": float(values.sum()) if len(accepted) else 0.0,
                "avg_r": float(values.mean()) if len(accepted) else 0.0,
                "max_drawdown_r": max_drawdown(values),
                "profit_factor": profit_factor(values),
            }
        )
    return pd.DataFrame(rows)


def train_and_evaluate(dataset: pd.DataFrame) -> tuple[Any, StandardScaler, pd.DataFrame, dict[str, Any]]:
    categorical = [
        "source",
        "actual_status",
        "signal",
        "reject_reason",
        "session_name",
        "session_is_dst",
        "structure_kind",
        "structure_direction",
        "session_zone_name",
        "session_zone_is_dst",
    ]
    excluded = {
        "source_year",
        "entry_time",
        "label_win",
        "outcome",
        "outcome_r",
        "bars_to_outcome",
        "label_sl",
        "label_tp",
        "actual_net_profit",
        "year",
    }
    numeric = [
        c
        for c in dataset.columns
        if c not in excluded and c not in categorical and pd.api.types.is_numeric_dtype(dataset[c])
    ]
    model_df = pd.get_dummies(dataset[numeric + categorical], columns=categorical, dummy_na=True)
    model_df = model_df.replace([np.inf, -np.inf], 0.0).fillna(0.0)
    model_df = model_df.loc[:, ~model_df.columns.duplicated()]

    train_mask = dataset["year"] <= 2024
    val_mask = dataset["year"] == 2025
    test_mask = dataset["year"] >= 2026

    scaler = StandardScaler()
    x_train = scaler.fit_transform(model_df.loc[train_mask])
    y_train = dataset.loc[train_mask, "label_win"].astype(int)

    counts = y_train.value_counts()
    scale_pos_weight = float(counts.get(0, 1) / counts.get(1, 1))
    model = XGBClassifier(
        n_estimators=500,
        max_depth=4,
        learning_rate=0.035,
        subsample=0.85,
        colsample_bytree=0.85,
        objective="binary:logistic",
        eval_metric="logloss",
        scale_pos_weight=scale_pos_weight,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(x_train, y_train)

    scored = dataset.copy()
    scored["probability"] = model.predict_proba(scaler.transform(model_df))[:, 1]

    metrics = {
        "feature_columns": list(model_df.columns),
        "train": classification_metrics(
            dataset.loc[train_mask, "label_win"].astype(int),
            scored.loc[train_mask, "probability"].to_numpy(),
        ),
        "validation": classification_metrics(
            dataset.loc[val_mask, "label_win"].astype(int),
            scored.loc[val_mask, "probability"].to_numpy(),
        )
        if val_mask.any()
        else {},
        "test": classification_metrics(
            dataset.loc[test_mask, "label_win"].astype(int),
            scored.loc[test_mask, "probability"].to_numpy(),
        )
        if test_mask.any()
        else {},
        "rows": {
            "train": int(train_mask.sum()),
            "validation": int(val_mask.sum()),
            "test": int(test_mask.sum()),
            "total": int(len(dataset)),
        },
    }
    return model, scaler, scored, metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backtest-dir", type=Path, default=REPO_ROOT / "Backtest_result")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PYTHON_DIR / "valuecell" / "models" / "experiments" / "ml_prediction_v2_all_signals",
    )
    args = parser.parse_args()

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = args.output_dir / stamp
    run_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Building v2 dataset from {}", args.backtest_dir)
    dataset, info = build_dataset(args.backtest_dir)
    if dataset.empty:
        raise RuntimeError("No v2 samples built.")

    dataset_path = run_dir / "dataset_v2_all_signals.csv"
    dataset.to_csv(dataset_path, index=False)

    model, scaler, scored, metrics = train_and_evaluate(dataset)
    scored_path = run_dir / "scored_v2_all_signals.csv"
    scored.to_csv(scored_path, index=False)

    reports = []
    for split_name, mask in {
        "train_2020_2024": scored["year"] <= 2024,
        "validation_2025": scored["year"] == 2025,
        "test_2026": scored["year"] >= 2026,
        "all": scored["year"] >= 2020,
    }.items():
        if mask.any():
            reports.append(threshold_report(scored.loc[mask], split_name))
    report = pd.concat(reports, ignore_index=True)
    report_path = run_dir / "threshold_report.csv"
    report.to_csv(report_path, index=False)

    joblib.dump(model, run_dir / "model_xgb.pkl")
    joblib.dump(scaler, run_dir / "scaler.pkl")

    best_validation = report[report["split"] == "validation_2025"].sort_values(
        ["total_r", "profit_factor", "accepted"], ascending=[False, False, False]
    )
    best = best_validation.iloc[0].to_dict() if not best_validation.empty else {}
    summary = {
        "created_at": datetime.now().isoformat(),
        "source_backtest_dir": str(args.backtest_dir.resolve()),
        "run_dir": str(run_dir.resolve()),
        "dataset_path": str(dataset_path.resolve()),
        "scored_path": str(scored_path.resolve()),
        "threshold_report_path": str(report_path.resolve()),
        "skipped": info["skipped"],
        "metrics": metrics,
        "best_validation_threshold": best,
        "label_counts": {str(k): int(v) for k, v in dataset["label_win"].value_counts().items()},
        "source_counts": {str(k): int(v) for k, v in dataset["source"].value_counts().items()},
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    logger.info("V2 samples: {} | labels={}", len(dataset), summary["label_counts"])
    logger.info("Metrics: {}", metrics)
    logger.info("Best validation threshold: {}", best)
    logger.info("Report saved to {}", report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
