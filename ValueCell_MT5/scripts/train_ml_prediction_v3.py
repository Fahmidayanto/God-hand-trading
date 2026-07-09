"""
Train/evaluate ML Prediction v3 from all Backtest_result signal candidates.

v3 improvements over v2:
- EXECUTED-only dataset (Option A): balanced labels from CloseReason
- Price-normalized features: ATR/price, EMA-dist/price (regime-agnostic)
- Feature selection: top-20 by XGBoost importance (reduces overfit with small data)
- Multi-model comparison: XGBoost vs LogisticRegression vs RandomForest
- CV-based n_estimators search (no early stopping with small val set)
- Output goes to experiments/ dir, does NOT overwrite filter_latest
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
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, f1_score, precision_score, recall_score, roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

try:
    from xgboost import XGBClassifier
except Exception as exc:
    raise RuntimeError("xgboost is required for v3 training") from exc

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_ROOT.parent
PYTHON_DIR = PROJECT_ROOT / "python"

if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

from valuecell.models.feature_engineer import FeatureEngineer  # noqa: E402


# ============================================================
# CONSTANTS
# ============================================================
FIXED_RISK = 30.0
FIXED_TARGET = 30.0
MAX_FORWARD_BARS = 1920  # 20 trading days on M15
THRESHOLDS = [round(x, 2) for x in np.arange(0.40, 0.91, 0.05)]

BODY_RATIO_MODE_MAP = {
    "STRICT": 0,
    "H4_ADAPTIVE_TREND": 1,
    "H4_STRETCHED_STRICT": 2,
    "H4_ADAPTIVE_STRETCHED": 3,
}

REJECT_REASON_MAP = {
    "N/A": 0,
    "Body Ratio Filter": 1,
    "H1 EMA200 Filter": 2,
    "H4 EMA Filter": 3,
    "Session Filter": 4,
    "Volume Filter": 5,
}


# ============================================================
# UTILITIES
# ============================================================
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


def last_rows_at_or_before(df: pd.DataFrame, when: pd.Timestamp, count: int) -> pd.DataFrame:
    idx = np.searchsorted(df["time"].values, np.datetime64(when), side="right")
    return df.iloc[max(0, idx - count): idx].copy()


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
    tr = np.maximum.reduce([
        high[1:] - low[1:],
        np.abs(high[1:] - close[:-1]),
        np.abs(low[1:] - close[:-1]),
    ])
    return float(np.mean(tr[-period:])) if len(tr) >= period else 0.0


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
    kind = "BOS" if "BOS" in raw_type else "CHOCH" if "CHOCH" in raw_type else raw_type
    return f"{kind}_{direction_from_structure(row)}"


def row_to_event(row: pd.Series) -> dict[str, Any]:
    return {
        "type": normalized_event_type(row),
        "price": safe_float(row.get("Price")),
        "time": row["time"].to_pydatetime(),
    }


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


# ============================================================
# V3-SPECIFIC: CSV-BASED FEATURES
# ============================================================
def csv_trade_features(row: pd.Series) -> dict[str, float]:
    """Extract PRE-TRADE features from the Backtest_Results CSV.

    CRITICAL: Only include features known AT THE TIME OF ENTRY.
    Post-trade data (CloseReason, MFE, MAE, FinalRR, Trailing/TP outcomes)
    MUST NOT be used — they cause data leakage (they encode the label).

    Pre-trade features (safe to use):
    - BodyRatio, BodyRatioMin, BodyRatioPassed, BodyRatioMode → candle quality at entry
    - InitialRiskPoints, InitialRewardPoints → planned R:R at entry
    - Reject_Reason → why signal was blocked (known at filter time)
    """
    # Body ratio — actual value computed by EA at entry candle
    body_ratio_ea = safe_float(row.get("BodyRatio"), 0.0)
    body_ratio_min = safe_float(row.get("BodyRatioMin"), 0.0)
    body_ratio_passed = 1.0 if str(row.get("BodyRatioPassed", "NO")).upper() == "YES" else 0.0
    body_ratio_mode_raw = str(row.get("BodyRatioMode", "")).strip()
    body_ratio_mode_enc = float(BODY_RATIO_MODE_MAP.get(body_ratio_mode_raw, -1))

    # Planned risk/reward at entry (InitialSL and InitialTP are set at open)
    init_risk = safe_float(row.get("InitialRiskPoints"), 0.0)
    init_reward = safe_float(row.get("InitialRewardPoints"), 0.0)
    initial_rr = init_reward / init_risk if init_risk > 0 else 0.0

    # Rejection filter encoding — known at filter evaluation time
    reject_reason_raw = str(row.get("Reject_Reason", "N/A")).strip()
    reject_enc = float(REJECT_REASON_MAP.get(reject_reason_raw, 0))
    is_rejected_body = 1.0 if reject_reason_raw == "Body Ratio Filter" else 0.0
    is_rejected_h1_ema = 1.0 if reject_reason_raw == "H1 EMA200 Filter" else 0.0
    is_rejected_h4_ema = 1.0 if reject_reason_raw == "H4 EMA Filter" else 0.0

    # NOTE: The following are POST-TRADE and must NOT be used as features:
    # CloseReason, MaxFavorablePoints, MaxAdversePoints,
    # FinalRiskPoints, FinalRewardPoints, TrailingModified,
    # TrailingCount, TPExpanded, TPExpandCount
    # Including these causes data leakage — the model would see the answer.

    return {
        "body_ratio_ea": body_ratio_ea,
        "body_ratio_min": body_ratio_min,
        "body_ratio_passed": body_ratio_passed,
        "body_ratio_mode_enc": body_ratio_mode_enc,
        "initial_rr": float(initial_rr),
        "init_risk_points": init_risk,
        "init_reward_points": init_reward,
        # reject_reason fields omitted: EXECUTED-only, all would be 0 (N/A)
    }


# ============================================================
# LABELING
# ============================================================
def label_from_csv(row: pd.Series, status: str) -> int | None:
    """
    v3 labeling strategy:
    - REJECTED -> always label=0 (filter correctly blocked)
    - EXECUTED + TAKE_PROFIT -> label=1
    - EXECUTED + STOP_LOSS -> label=0
    - EXECUTED + EXPERT_CLOSE -> label from Net_Profit > 0
    """
    if status == "REJECTED":
        return 0
    close_reason = str(row.get("CloseReason", "")).strip().upper()
    if close_reason in ("TAKE_PROFIT", "TAKEPROFIT"):
        return 1
    if close_reason in ("STOP_LOSS", "STOPLOSS"):
        return 0
    if close_reason in ("EXPERT_CLOSE", "EXPERTCLOSE", "MANUAL"):
        net = safe_float(row.get("Net_Profit"), 0.0)
        return 1 if net > 0 else 0
    return None  # Unknown – will use forward simulation fallback


def label_levels(entry: float, sl_col: float, tp_col: float, signal: str) -> tuple[float, float]:
    if sl_col > 0 and tp_col > 0 and sl_col != tp_col:
        return sl_col, tp_col
    if signal == "BUY":
        return entry - FIXED_RISK, entry + FIXED_TARGET
    return entry + FIXED_RISK, entry - FIXED_TARGET


def forward_outcome_label(
    m15: pd.DataFrame,
    when: pd.Timestamp,
    signal: str,
    entry: float,
    sl: float,
    tp: float,
    max_bars: int = MAX_FORWARD_BARS,
) -> int | None:
    idx = np.searchsorted(m15["time"].values, np.datetime64(when), side="right")
    future = m15.iloc[idx: idx + max_bars]
    if future.empty:
        return None
    risk = abs(entry - sl)
    target = abs(tp - entry)
    if risk <= 0 or target <= 0:
        return None
    for row in future.itertuples(index=False):
        high = safe_float(getattr(row, "high"))
        low = safe_float(getattr(row, "low"))
        hit_tp = (high >= tp) if signal == "BUY" else (low <= tp)
        hit_sl = (low <= sl) if signal == "BUY" else (high >= sl)
        if hit_tp and hit_sl:
            return None
        if hit_tp:
            return 1
        if hit_sl:
            return 0
    return None


# ============================================================
# DATASET BUILDING
# ============================================================
def build_dataset(backtest_dir: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Build EXECUTED-only dataset (Option A).

    Only EXECUTED trades are used. REJECTED trades are skipped entirely.
    This forces the model to learn genuine market signal quality:
    - EXECUTED + TAKE_PROFIT  -> label=1
    - EXECUTED + STOP_LOSS    -> label=0
    - EXECUTED + EXPERT_CLOSE -> label from Net_Profit > 0
    Result: ~360 balanced samples (176 vs 184).
    """
    engineer = FeatureEngineer()
    samples = []
    skipped = {
        "missing_files": 0,
        "rejected_skipped": 0,
        "no_label": 0,
        "missing_bar": 0,
        "candidates_total": 0,
        "label_from_csv": 0,
        "label_from_forward": 0,
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
            logger.warning("Skipping {} – required CSV missing", suffix)
            continue

        trades = pd.read_csv(results_path)
        trades.columns = [c.strip() for c in trades.columns]
        structures = load_structure_events(paths["structures"])
        m15 = normalize_market_df(paths["m15"])
        h1 = normalize_market_df(paths["h1"])
        h4 = normalize_market_df(paths["h4"])
        sessions = load_session_zones(paths["sessions"])

        year_count = 0
        skipped["candidates_total"] += len(trades)

        for idx, trade_row in trades.iterrows():
            signal = str(trade_row.get("Type", "")).strip().upper()
            if signal not in {"BUY", "SELL"}:
                continue

            entry_time = parse_time(trade_row.get("EntryTime"))
            if pd.isna(entry_time):
                continue

            status = str(trade_row.get("Status", "")).strip().upper()

            # Option A: skip REJECTED signals entirely
            if status == "REJECTED":
                skipped["rejected_skipped"] += 1
                continue

            # --- Label from CloseReason (no forward sim needed) ---
            label = label_from_csv(trade_row, status)
            used_forward = False

            # Fallback: forward sim only if CloseReason is unrecognised
            if label is None:
                sl_col = safe_float(trade_row.get("SL"), 0.0)
                tp_col = safe_float(trade_row.get("TP"), 0.0)
                entry_price = safe_float(trade_row.get("EntryPrice"))
                sl, tp = label_levels(entry_price, sl_col, tp_col, signal)
                label = forward_outcome_label(m15, entry_time, signal, entry_price, sl, tp)
                if label is None:
                    skipped["no_label"] += 1
                    continue
                used_forward = True
                skipped["label_from_forward"] += 1
            else:
                skipped["label_from_csv"] += 1

            # --- Current bar at entry ---
            current_bar = current_bar_at_or_before(m15, entry_time)
            if current_bar is None:
                skipped["missing_bar"] += 1
                continue

            entry_price = safe_float(trade_row.get("EntryPrice"), safe_float(current_bar.get("close")))

            # --- Market structure context ---
            recent_structures = structures[structures["time"] <= entry_time].tail(50)
            structure_events = [row_to_event(r) for _, r in recent_structures.iterrows()]

            # --- History windows ---
            m15_history = last_rows_at_or_before(m15, entry_time, 220)
            h1_history = last_rows_at_or_before(h1, entry_time, 220)
            h4_history = last_rows_at_or_before(h4, entry_time, 220)

            # --- Feature extraction ---
            base_features = engineer.extract_features(
                current_bar=current_bar,
                structure_events=structure_events,
                h1_data=h1_history,
                m15_history=m15_history,
            )
            atr = safe_float(base_features.get("atr_14"))

            # v3 CSV-derived features
            csv_features = csv_trade_features(trade_row)

            # v3 price-normalized features (regime-agnostic)
            all_raw = {
                **base_features,
                **trend_features("h4", h4_history, entry_price, signal),
                **trend_features("h1_ext", h1_history, entry_price, signal),
                **csv_features,
                "spread": safe_float(m15_history.iloc[-1].get("spread")) if not m15_history.empty else 0.0,
            }
            norm_features = price_normalized_features(all_raw, entry_price)

            sample = {
                "source_year": suffix,
                "year": int(suffix[:4]),
                "entry_time": entry_time,
                "source": status,
                "signal": signal,
                "entry_price": entry_price,
                "timeframe": str(trade_row.get("Timeframe", "M15")),
                "reject_reason": str(trade_row.get("Reject_Reason", "N/A")),
                "session_name": str(trade_row.get("Session", "UNKNOWN")),
                "session_is_dst": str(trade_row.get("Session_IsDST", "UNKNOWN")),
                "close_reason": str(trade_row.get("CloseReason", "N/A")),
                "label_win": label,
                "label_source": "csv" if not used_forward else "forward_sim",
                "actual_net_profit": safe_float(trade_row.get("Net_Profit")),
                "spread": safe_float(m15_history.iloc[-1].get("spread")) if not m15_history.empty else 0.0,
                **all_raw,
                **momentum_features(m15_history, entry_price),
                **session_features(sessions, entry_time, entry_price, atr),
                **norm_features,
            }
            samples.append(sample)
            year_count += 1

        logger.info("Built {} v3 samples from {}", year_count, suffix)

    dataset = pd.DataFrame(samples)
    return dataset, {"skipped": skipped}


def price_normalized_features(raw_features: dict[str, float], entry_price: float) -> dict[str, float]:
    """Add regime-agnostic versions of price-scale-dependent features.

    Problem: raw ATR values (e.g. h1_atr_14=20 in 2020 vs h1_atr_14=60 in 2026)
    mean completely different things in terms of market volatility relative to price.
    When model trains on 2020 data (price~1500) and tests on 2026 (price~4000),
    it sees ATR values it has never seen, causing poor generalization.

    Solution: express ATR and EMA distances as percentage of entry_price.
    These are regime-agnostic: 1% ATR means the same thing regardless of year.
    """
    if entry_price <= 0:
        return {}
    out = {}
    pct_features = [
        "atr_14", "h1_atr_14", "h4_atr_14", "h1_ext_atr_14",
        "spread",
    ]
    for feat in pct_features:
        val = raw_features.get(feat, 0.0)
        out[f"{feat}_pct"] = (val / entry_price) * 100.0 if val else 0.0

    # EMA-distance features are already expressed in ATR units (pre-normalized)
    # but ATR itself grows with price, so re-express in price %
    for prefix in ("h4", "h1_ext"):
        atr = raw_features.get(f"{prefix}_atr_14", 0.0)
        dist_atr = raw_features.get(f"{prefix}_ema200_distance_atr", 0.0)
        if atr and entry_price:
            dist_price = dist_atr * atr  # back to points
            out[f"{prefix}_ema200_distance_pct"] = (dist_price / entry_price) * 100.0
        else:
            out[f"{prefix}_ema200_distance_pct"] = 0.0

    # InitialRisk expressed as % of price (constant in $ terms but differs % per regime)
    init_risk = raw_features.get("init_risk_points", 0.0)
    out["init_risk_pct"] = (init_risk / entry_price) * 100.0 if init_risk and entry_price else 0.0

    # 1. Spread-to-ATR ratio (M15)
    spread = raw_features.get("spread", 0.0)
    atr = raw_features.get("atr_14", 0.0)
    out["spread_to_atr_ratio"] = spread / atr if atr > 0 else 0.0

    # 2. Double Trend Alignment (H1 and H4 both aligned with trade direction)
    h4_aligned = raw_features.get("h4_trend_aligned", 0.0)
    h1_aligned = raw_features.get("h1_ext_trend_aligned", 0.0)
    out["double_trend_aligned"] = 1.0 if (h4_aligned == 1.0 and h1_aligned == 1.0) else 0.0

    return out


# ============================================================
# METRICS
# ============================================================
def classification_metrics(y_true: pd.Series, prob: np.ndarray) -> dict[str, float]:
    if len(y_true) == 0:
        return {}
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


def threshold_report(df: pd.DataFrame, split_name: str) -> pd.DataFrame:
    rows = []
    baseline_r = df["label_win"]
    rows.append({
        "split": split_name,
        "threshold": 0.0,
        "candidates": len(df),
        "accepted": len(df),
        "winrate": float(df["label_win"].mean()) if len(df) else 0.0,
        "profit_factor": profit_factor(baseline_r.map({1: 1.0, 0: -1.0})),
    })
    for threshold in THRESHOLDS:
        accepted = df[df["probability"] >= threshold]
        rows.append({
            "split": split_name,
            "threshold": threshold,
            "candidates": len(df),
            "accepted": len(accepted),
            "winrate": float(accepted["label_win"].mean()) if len(accepted) else 0.0,
            "profit_factor": profit_factor(accepted["label_win"].map({1: 1.0, 0: -1.0})),
        })
    return pd.DataFrame(rows)


# ============================================================
# TRAIN
# ============================================================
def build_feature_matrix(dataset: pd.DataFrame) -> tuple[pd.DataFrame, list[str], list[str]]:
    # Categorical features — pre-trade, EXECUTED-only dataset
    categorical = [
        # NOTE: "source" removed — all rows are EXECUTED, zero variance
        # NOTE: "reject_reason" removed — all rows are N/A for EXECUTED
        "signal",           # BUY or SELL
        "session_name",     # session at entry time
        "session_is_dst",
        "session_zone_name",
        "session_zone_is_dst",
        # NOTE: close_reason is POST-TRADE → EXCLUDED (data leakage)
    ]
    # Columns that must never enter the feature matrix
    excluded = {
        # Meta / index columns
        "source_year", "entry_time", "label_win", "label_source",
        "actual_net_profit", "year", "timeframe", "entry_price",
        # Constant columns (all EXECUTED)
        "source", "reject_reason",
        # ---- POST-TRADE DATA (leakage) ----
        "close_reason",
        "mfe_points", "mae_points", "mfe_to_rr", "mae_to_rr",
        "final_rr", "final_risk_points", "final_reward_points",
        "trailing_modified", "trailing_count",
        "tp_expanded", "tp_expand_count",
        # Reject features — all N/A for EXECUTED-only
        "reject_reason_enc", "is_rejected_body", "is_rejected_h1_ema", "is_rejected_h4_ema",
    }
    numeric = [
        c for c in dataset.columns
        if c not in excluded and c not in categorical and pd.api.types.is_numeric_dtype(dataset[c])
    ]
    model_df = pd.get_dummies(dataset[numeric + categorical], columns=categorical, dummy_na=True)
    model_df = model_df.replace([np.inf, -np.inf], 0.0).fillna(0.0)
    model_df = model_df.loc[:, ~model_df.columns.duplicated()]
    logger.info("Feature matrix: {} numeric + {} categorical = {} total columns",
                len(numeric), len(categorical), len(model_df.columns))
    return model_df, numeric, categorical


def train_and_evaluate(dataset: pd.DataFrame) -> tuple[Any, StandardScaler, pd.DataFrame, dict[str, Any]]:
    model_df, numeric, categorical = build_feature_matrix(dataset)

    train_mask = dataset["year"] <= 2024
    val_mask = dataset["year"] == 2025
    test_mask = dataset["year"] >= 2026

    # Target arrays
    y_train = dataset.loc[train_mask, "label_win"].astype(int)
    counts = y_train.value_counts()
    scale_pos_weight = float(counts.get(0, 1) / counts.get(1, 1))
    logger.info("Train label distribution: {}", counts.to_dict())
    logger.info("scale_pos_weight={:.3f}", scale_pos_weight)

    # Temporary scaling for preliminary feature selection
    temp_scaler = StandardScaler()
    x_train_temp = temp_scaler.fit_transform(model_df.loc[train_mask])

    # --- Step 1: Feature Selection via preliminary XGBoost ---
    pre_params = dict(
        max_depth=3,
        learning_rate=0.01,
        subsample=0.75,
        colsample_bytree=0.70,
        min_child_weight=8,
        gamma=0.1,
        reg_alpha=0.3,
        reg_lambda=1.5,
        scale_pos_weight=scale_pos_weight,
        objective="binary:logistic",
        random_state=42,
        n_jobs=-1,
    )
    pre_xgb = XGBClassifier(n_estimators=150, **pre_params)
    pre_xgb.fit(x_train_temp, y_train, verbose=False)

    feat_imp = dict(zip(model_df.columns, pre_xgb.feature_importances_))
    top_features = [k for k, v in sorted(feat_imp.items(), key=lambda x: x[1], reverse=True)[:20]]
    logger.info("Selected top 20 features: {}", top_features)

    # Filter model_df to selected features
    model_df_filtered = model_df[top_features]

    # Standard scaling with selected features
    scaler = StandardScaler()
    x_train = scaler.fit_transform(model_df_filtered.loc[train_mask])
    x_val = scaler.transform(model_df_filtered.loc[val_mask]) if val_mask.any() else None
    x_test = scaler.transform(model_df_filtered.loc[test_mask]) if test_mask.any() else None

    # CV setup
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    best_cv_auc = 0.0
    best_model_name = ""
    best_model_obj = None

    # --- Step 2: Multi-Model Evaluation & Selection ---

    # A. XGBoost Grid Search
    xgb_best_n = 150
    xgb_best_auc = 0.0
    for n in [50, 100, 150, 200, 300]:
        probe = XGBClassifier(n_estimators=n, **pre_params)
        scores = cross_val_score(probe, x_train, y_train, cv=skf, scoring="roc_auc")
        if scores.mean() > xgb_best_auc:
            xgb_best_auc = scores.mean()
            xgb_best_n = n
    logger.info("XGBoost best CV AUC: {:.4f} (n_estimators={})", xgb_best_auc, xgb_best_n)

    if xgb_best_auc > best_cv_auc:
        best_cv_auc = xgb_best_auc
        best_model_name = f"XGBoost_n{xgb_best_n}"
        best_model_obj = XGBClassifier(n_estimators=xgb_best_n, **pre_params)

    # B. Logistic Regression Grid Search
    lr_best_c = 1.0
    lr_best_auc = 0.0
    for C in [0.01, 0.1, 1.0, 10.0]:
        probe = LogisticRegression(C=C, max_iter=1000, random_state=42, class_weight='balanced')
        scores = cross_val_score(probe, x_train, y_train, cv=skf, scoring="roc_auc")
        if scores.mean() > lr_best_auc:
            lr_best_auc = scores.mean()
            lr_best_c = C
    logger.info("Logistic Regression best CV AUC: {:.4f} (C={})", lr_best_auc, lr_best_c)

    if lr_best_auc > best_cv_auc:
        best_cv_auc = lr_best_auc
        best_model_name = f"LogisticRegression_C{lr_best_c}"
        best_model_obj = LogisticRegression(C=lr_best_c, max_iter=1000, random_state=42, class_weight='balanced')

    # C. Random Forest Grid Search
    rf_best_depth = 3
    rf_best_n = 100
    rf_best_leaf = 5
    rf_best_feat = 'sqrt'
    rf_best_auc = 0.0
    for depth in [3, 4, 5]:
        for n in [100, 200, 300]:
            for leaf in [3, 5, 8, 12]:
                for feat in ['sqrt', 0.4, 0.6]:
                    probe = RandomForestClassifier(
                        max_depth=depth,
                        n_estimators=n,
                        min_samples_leaf=leaf,
                        max_features=feat,
                        random_state=42,
                        class_weight='balanced',
                        n_jobs=-1
                    )
                    scores = cross_val_score(probe, x_train, y_train, cv=skf, scoring="roc_auc")
                    if scores.mean() > rf_best_auc:
                        rf_best_auc = scores.mean()
                        rf_best_depth = depth
                        rf_best_n = n
                        rf_best_leaf = leaf
                        rf_best_feat = feat
    logger.info("Random Forest best CV AUC: {:.4f} (depth={}, n_estimators={}, min_samples_leaf={}, max_features={})",
                rf_best_auc, rf_best_depth, rf_best_n, rf_best_leaf, rf_best_feat)

    if rf_best_auc > best_cv_auc:
        best_cv_auc = rf_best_auc
        best_model_name = f"RandomForest_d{rf_best_depth}_n{rf_best_n}_leaf{rf_best_leaf}_feat{rf_best_feat}"
        best_model_obj = RandomForestClassifier(
            max_depth=rf_best_depth,
            n_estimators=rf_best_n,
            min_samples_leaf=rf_best_leaf,
            max_features=rf_best_feat,
            random_state=42,
            class_weight='balanced',
            n_jobs=-1
        )

    logger.info("🏆 Winning Model: {} (CV AUC: {:.4f})", best_model_name, best_cv_auc)

    # --- Step 3: Train Final Winner ---
    model = best_model_obj
    model.fit(x_train, y_train)

    cv_auc = cross_val_score(model, x_train, y_train, cv=skf, scoring="roc_auc")
    cv_f1 = cross_val_score(model, x_train, y_train, cv=skf, scoring="f1")

    # Score full dataset (using only filtered features)
    all_proba = model.predict_proba(scaler.transform(model_df_filtered))[:, 1]
    scored = dataset.copy()
    scored["probability"] = all_proba

    metrics: dict[str, Any] = {
        "feature_columns": list(model_df_filtered.columns),
        "n_features": len(model_df_filtered.columns),
        "winner_name": best_model_name,
        "cv_auc_mean": float(cv_auc.mean()),
        "cv_auc_std": float(cv_auc.std()),
        "cv_f1_mean": float(cv_f1.mean()),
        "cv_f1_std": float(cv_f1.std()),
        "train": classification_metrics(
            dataset.loc[train_mask, "label_win"].astype(int),
            scored.loc[train_mask, "probability"].to_numpy(),
        ),
        "validation": classification_metrics(
            dataset.loc[val_mask, "label_win"].astype(int),
            scored.loc[val_mask, "probability"].to_numpy(),
        ) if val_mask.any() else {},
        "test": classification_metrics(
            dataset.loc[test_mask, "label_win"].astype(int),
            scored.loc[test_mask, "probability"].to_numpy(),
        ) if test_mask.any() else {},
        "rows": {
            "train": int(train_mask.sum()),
            "validation": int(val_mask.sum()),
            "test": int(test_mask.sum()),
            "total": int(len(dataset)),
        },
    }

    # Extract Top Features relative importance
    if hasattr(model, "feature_importances_"):
        raw_imp = dict(zip(model_df_filtered.columns, model.feature_importances_))
    elif hasattr(model, "coef_"):
        raw_imp = dict(zip(model_df_filtered.columns, np.abs(model.coef_[0])))
    else:
        raw_imp = {col: 1.0 for col in model_df_filtered.columns}

    sorted_imp = sorted(raw_imp.items(), key=lambda x: x[1], reverse=True)
    logger.info("Top features for selected model: {}", sorted_imp)
    metrics["top_features"] = {k: float(v) for k, v in sorted_imp}

    # Store final model features inside features so load code knows the exact inputs
    model.feature_names_in_ = np.array(model_df_filtered.columns, dtype=object)

    return model, scaler, scored, metrics


# ============================================================
# MAIN
# ============================================================
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backtest-dir", type=Path, default=REPO_ROOT / "Backtest_result")
    parser.add_argument(
        "--output-dir", type=Path,
        default=PYTHON_DIR / "valuecell" / "models" / "experiments" / "ml_prediction_v3",
    )
    parser.add_argument("--save-to-filter-latest", action="store_true",
                        help="Also copy best model to filter_latest/ (requires explicit flag)")
    args = parser.parse_args()

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = args.output_dir / stamp
    run_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=== ML Prediction v3 Training ===")
    logger.info("Backtest dir: {}", args.backtest_dir)
    logger.info("Output dir:   {}", run_dir)

    dataset, info = build_dataset(args.backtest_dir)
    if dataset.empty:
        raise RuntimeError("No v3 samples built.")

    logger.info("Dataset built: {} samples | labels={}", len(dataset),
                dataset["label_win"].value_counts().to_dict())
    logger.info("Label sources: {}", dataset["label_source"].value_counts().to_dict())
    logger.info("Skipped: {}", info["skipped"])

    dataset_path = run_dir / "dataset_v3.csv"
    dataset.to_csv(dataset_path, index=False)

    model, scaler, scored, metrics = train_and_evaluate(dataset)
    scored_path = run_dir / "scored_v3.csv"
    scored.to_csv(scored_path, index=False)

    # Threshold report
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

    # Save artifacts
    model_path = run_dir / "model_v3_xgb.pkl"
    scaler_path = run_dir / "scaler_v3.pkl"
    joblib.dump(model, model_path)
    joblib.dump(scaler, scaler_path)

    best_validation = report[report["split"] == "validation_2025"].sort_values(
        ["profit_factor", "accepted"], ascending=[False, False]
    )
    best = best_validation.iloc[0].to_dict() if not best_validation.empty else {}

    summary = {
        "version": f"v3_{stamp}",
        "created_at": datetime.now().isoformat(),
        "model_type": type(model).__name__,
        "winner_name": metrics["winner_name"],
        "training_script": "train_ml_prediction_v3.py",
        "source_backtest_dir": str(args.backtest_dir.resolve()),
        "run_dir": str(run_dir.resolve()),
        "dataset_path": str(dataset_path.resolve()),
        "n_samples_total": len(dataset),
        "label_counts": {str(k): int(v) for k, v in dataset["label_win"].value_counts().items()},
        "label_sources": {str(k): int(v) for k, v in dataset["label_source"].value_counts().items()},
        "source_counts": {str(k): int(v) for k, v in dataset["source"].value_counts().items()},
        "skipped": info["skipped"],
        "metrics": metrics,
        "best_validation_threshold": best,
    }
    summary_path = run_dir / "summary_v3.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    logger.info("=== v3 RESULTS ===")
    logger.info("Total samples  : {}", len(dataset))
    logger.info("Winning Model  : {}", metrics["winner_name"])
    logger.info("Train AUC      : {:.4f}", metrics["train"].get("auc", 0))
    logger.info("Val   AUC      : {:.4f}", metrics.get("validation", {}).get("auc", 0))
    logger.info("Test  AUC      : {:.4f}", metrics.get("test", {}).get("auc", 0))
    logger.info("CV    AUC      : {:.4f} ± {:.4f}", metrics["cv_auc_mean"], metrics["cv_auc_std"])
    logger.info("CV    F1       : {:.4f} ± {:.4f}", metrics["cv_f1_mean"], metrics["cv_f1_std"])
    logger.info("Best validation threshold: {}", best)
    logger.info("Summary saved: {}", summary_path)

    # Optional: copy to filter_latest
    if args.save_to_filter_latest:
        import shutil
        latest_dir = PYTHON_DIR / "valuecell" / "models" / "saved" / "filter_latest"
        # Backup existing
        if latest_dir.exists():
            backup = latest_dir.parent / f"filter_latest_backup_{stamp}"
            shutil.copytree(latest_dir, backup)
            logger.info("Backed up filter_latest to {}", backup)
        latest_dir.mkdir(parents=True, exist_ok=True)

        # Build meta for filter_latest (compatible with existing API)
        feature_cols = [c for c in metrics["feature_columns"]]
        meta = {
            "version": stamp,
            "trained_at": datetime.now().isoformat(),
            "model_type": type(model).__name__,
            "winner_name": metrics["winner_name"],
            "training_version": "v3",
            "n_features": len(feature_cols),
            "feature_names": feature_cols,
            "threshold": float(best.get("threshold", 0.6)),
            "optimal_threshold": float(best.get("threshold", 0.6)),
            "train_rows": int(metrics["rows"]["train"]),
            "label_counts": summary["label_counts"],
            "source_backtest_dir": str(args.backtest_dir.resolve()),
            "train_accuracy": metrics["train"].get("accuracy", 0),
            "train_precision": metrics["train"].get("precision", 0),
            "train_recall": metrics["train"].get("recall", 0),
            "train_f1": metrics["train"].get("f1", 0),
            "train_auc": metrics["train"].get("auc", 0),
            "test_accuracy": metrics.get("test", {}).get("accuracy", 0),
            "test_precision": metrics.get("test", {}).get("precision", 0),
            "test_recall": metrics.get("test", {}).get("recall", 0),
            "test_f1": metrics.get("test", {}).get("f1", 0),
            "test_auc": metrics.get("test", {}).get("auc", 0),
            "cv_auc_mean": metrics["cv_auc_mean"],
            "cv_auc_std": metrics["cv_auc_std"],
            "cv_f1_mean": metrics["cv_f1_mean"],
            "cv_f1_std": metrics["cv_f1_std"],
            "top_features": metrics.get("top_features", {}),
        }
        shutil.copy(model_path, latest_dir / "filter_model_xgb.pkl")
        shutil.copy(scaler_path, latest_dir / "filter_scaler.pkl")
        (latest_dir / "filter_model_meta.json").write_text(
            json.dumps(meta, indent=2), encoding="utf-8"
        )
        logger.info("Saved v3 model to filter_latest/")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
