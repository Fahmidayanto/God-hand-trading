"""
Train/evaluate ML Prediction v5 (Regression Model) using unconstrained raw market data.
Looks forward 24 hours to find true MFE and MAE targets after any structure event.
Uses M15, H1, H4, EMA 200, and Session Zones.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import joblib
import numpy as np
import pandas as pd
from loguru import logger
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import KFold, cross_val_score
from sklearn.preprocessing import StandardScaler

try:
    from xgboost import XGBRegressor
except Exception as exc:
    raise RuntimeError("xgboost is required for v5 training") from exc

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from train_ml_prediction_v3 import (  # noqa: E402
    PYTHON_DIR,
    REPO_ROOT,
    normalize_market_df,
    load_structure_events,
    load_session_zones,
    parse_time,
    safe_float,
    current_bar_at_or_before,
    last_rows_at_or_before,
    row_to_event,
    trend_features,
    momentum_features,
    session_features,
    price_normalized_features,
    FeatureEngineer,
    atr_value,
)


def completed_rows_at_or_before(
    frame: pd.DataFrame,
    when: pd.Timestamp,
    timeframe: str,
    count: int,
) -> pd.DataFrame:
    """Return only candles whose close time is available at prediction time."""
    close_cutoff = pd.Timestamp(when) - pd.Timedelta(timeframe)
    return last_rows_at_or_before(frame, close_cutoff, count)


def point_in_time_session_features(
    sessions: pd.DataFrame,
    m15: pd.DataFrame,
    when: pd.Timestamp,
    entry_price: float,
    atr: float,
) -> Dict[str, Any]:
    """Build session features from M15 candles completed by prediction time."""
    base = session_features(sessions, when, entry_price, atr)
    if sessions.empty:
        return base

    matching = sessions[(sessions["start_time"] <= when) & (when <= sessions["end_time"])]
    if matching.empty:
        matching = sessions[sessions["end_time"] <= when].tail(1)
    if matching.empty:
        return base

    session = matching.iloc[-1]
    observed = completed_rows_at_or_before(m15, when, "15min", len(m15))
    observed = observed[
        (observed["time"] >= session["start_time"])
        & (observed["time"] < session["end_time"])
    ]
    if observed.empty:
        base.update({
            "session_range_points": 0.0,
            "price_position_session_range": 0.5,
            "distance_to_session_high_atr": 0.0,
            "distance_to_session_low_atr": 0.0,
        })
        return base

    high = float(observed["high"].max())
    low = float(observed["low"].min())
    price_range = max(high - low, 0.0)
    base.update({
        "session_range_points": price_range * 100.0,
        "price_position_session_range": (entry_price - low) / price_range if price_range else 0.5,
        "distance_to_session_high_atr": (high - entry_price) / atr if atr else 0.0,
        "distance_to_session_low_atr": (entry_price - low) / atr if atr else 0.0,
    })
    return base


def build_dataset_v5_unconstrained(backtest_dir: Path) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Build unconstrained dataset directly from structure events and raw market data."""
    engineer = FeatureEngineer()
    samples = []
    skipped = {
        "missing_files": 0,
        "no_m15_bar": 0,
        "insufficient_forward_data": 0,
        "total_structures": 0,
    }

    # Gather all structure files
    structure_files = sorted(backtest_dir.glob("LLHHBOSData_XAUUSD_*.csv"))

    for struct_path in structure_files:
        suffix = struct_path.stem.replace("LLHHBOSData_XAUUSD_", "")
        paths = {
            "m15": backtest_dir / f"MarketData_XAUUSD_M15_{suffix}.csv",
            "h1": backtest_dir / f"MarketData_XAUUSD_H1_{suffix}.csv",
            "h4": backtest_dir / f"MarketData_XAUUSD_H4_{suffix}.csv",
            "sessions": backtest_dir / f"SessionZone_XAUUSD_{suffix}.csv",
            "results": backtest_dir / f"Backtest_Results_XAUUSD_{suffix}.csv",
        }

        if not all(paths[k].exists() for k in ("m15", "h1", "h4")):
            skipped["missing_files"] += 1
            logger.warning("Skipping {} – required MarketData CSV missing", suffix)
            continue

        # Load dataframes
        structures_df = load_structure_events(struct_path)
        m15 = normalize_market_df(paths["m15"])
        h1 = normalize_market_df(paths["h1"])
        h4 = normalize_market_df(paths["h4"])
        sessions = load_session_zones(paths["sessions"])

        # Load backtest results for real trade profit mapping
        real_trades = {}
        entry_structures = {}
        ea_status = {}
        ea_reject_reason = {}
        if paths["results"].exists():
            try:
                results_df = pd.read_csv(paths["results"])
                results_df.columns = [c.strip() for c in results_df.columns]
                for _, r in results_df.iterrows():
                    t_time = parse_time(r.get("EntryTime"))
                    t_type = str(r.get("Type", "")).strip().upper()
                    if not pd.isna(t_time) and t_type in ("BUY", "SELL"):
                        # EA EntryTime = bar M15 SETELAH event struktur (offset +15 menit).
                        # Kunci mapping = waktu event struktur = EntryTime - 15 menit.
                        event_key = (t_time - pd.Timedelta(minutes=15), t_type)
                        real_trades[event_key] = safe_float(r.get("Net_Profit"))
                        # EntryStructure (CHoCH/BoS_1/BoS_2): fitur kategorikal sinyal
                        entry_structures[event_key] = str(r.get("EntryStructure", "")).strip()
                        # Status + Reject_Reason: keputusan filter asli EA (EXECUTED / REJECTED)
                        ea_status[event_key] = str(r.get("Status", "")).strip().upper()
                        ea_reject_reason[event_key] = str(r.get("Reject_Reason", "N/A")).strip()
            except Exception as e:
                logger.warning(f"Failed to load backtest results for mapping: {e}")

        # Compute EMA200 on timeframes
        m15["ema200"] = m15["close"].ewm(span=200, adjust=False).mean()
        h1["ema200"] = h1["close"].ewm(span=200, adjust=False).mean()
        h4["ema200"] = h4["close"].ewm(span=200, adjust=False).mean()

        year_count = 0
        
        # Filter for BoS or CHoCH events (setup triggers)
        events_df = structures_df[structures_df["Type"].isin(["BoS", "CHoCH", "BOS"])]
        skipped["total_structures"] += len(events_df)

        for _, row in events_df.iterrows():
            entry_time = row["time"]
            prediction_time = entry_time + pd.Timedelta(minutes=15)
            dir_action = str(row.get("Direction/Action", "")).upper()
            
            if "BULL" in dir_action:
                signal = "BUY"
            elif "BEAR" in dir_action:
                signal = "SELL"
            else:
                continue

            # Find M15 bar at entry
            m15_history = completed_rows_at_or_before(m15, prediction_time, "15min", 220)
            if m15_history.empty:
                skipped["no_m15_bar"] += 1
                continue
            current_bar = current_bar_at_or_before(m15_history, entry_time)
            if current_bar is None:
                skipped["no_m15_bar"] += 1
                continue

            entry_price = safe_float(current_bar.get("close"))
            if entry_price <= 0:
                continue

            # Find 24 hours (96 M15 bars) forward window strictly after entry_time
            start_idx = np.searchsorted(m15["time"].values, np.datetime64(entry_time), side="right")
            forward_bars = m15.iloc[start_idx : start_idx + 96]
            if len(forward_bars) < 12:  # require at least 3 hours of forward data
                skipped["insufficient_forward_data"] += 1
                continue

            # Calculate MFE and MAE unconstrained targets (in gold points: 1 USD = 100 points)
            max_high = float(forward_bars["high"].max())
            min_low = float(forward_bars["low"].min())

            if signal == "BUY":
                mfe_target = max(0.0, (max_high - entry_price) * 100.0)
                mae_target = max(0.0, (entry_price - min_low) * 100.0)
            else:
                mfe_target = max(0.0, (entry_price - min_low) * 100.0)
                mae_target = max(0.0, (max_high - entry_price) * 100.0)

            # Get historical windows (220 bars)
            h1_history = completed_rows_at_or_before(h1, prediction_time, "1h", 220)
            h4_history = completed_rows_at_or_before(h4, prediction_time, "4h", 220)

            # Extract base structure features
            recent_structures = structures_df[structures_df["time"] <= entry_time].tail(50)
            structure_events = [row_to_event(r) for _, r in recent_structures.iterrows()]

            base_features = engineer.extract_features(
                current_bar=current_bar,
                structure_events=structure_events,
                h1_data=h1_history,
                m15_history=m15_history,
            )

            # Compute custom metrics
            m15_atr = atr_value(m15_history)
            m15_atr_pct = (m15_atr / entry_price) * 100.0 if entry_price > 0 else 0.0
            
            spread = safe_float(m15_history.iloc[-1].get("spread"), 0.15) if not m15_history.empty else 0.15
            spread_pct = (spread / entry_price) * 100.0 if entry_price > 0 else 0.0
            spread_to_atr_ratio = spread / m15_atr if m15_atr > 0 else 0.0
            
            body_ratio_ea = base_features.get("body_ratio", 0.5)

            h1_atr = atr_value(h1_history)
            h1_atr_pct = (h1_atr / entry_price) * 100.0 if entry_price > 0 else 0.0
            
            h4_atr = atr_value(h4_history)
            h4_atr_pct = (h4_atr / entry_price) * 100.0 if entry_price > 0 else 0.0

            # Calculate H1 & H4 EMA distances
            h4_ema200_distance_atr = 0.0
            h4_ema200_distance_pct = 0.0
            if not h4_history.empty:
                h4_ema = float(h4_history.iloc[-1].get("ema200", entry_price))
                h4_ema200_distance_atr = (entry_price - h4_ema) / h4_atr if h4_atr > 0 else 0.0
                h4_ema200_distance_pct = (h4_ema200_distance_atr * h4_atr / entry_price) * 100.0 if entry_price > 0 else 0.0

            h1_ext_ema200_distance_atr = 0.0
            h1_ext_ema200_distance_pct = 0.0
            if not h1_history.empty:
                h1_ema = float(h1_history.iloc[-1].get("ema200", entry_price))
                h1_ext_ema200_distance_atr = (entry_price - h1_ema) / h1_atr if h1_atr > 0 else 0.0
                h1_ext_ema200_distance_pct = (h1_ext_ema200_distance_atr * h1_atr / entry_price) * 100.0 if entry_price > 0 else 0.0

            # Calculate M15 EMA 200
            m15_ema200_distance_atr = 0.0
            m15_ema200_distance_pct = 0.0
            if not m15_history.empty:
                m15_ema = float(m15_history.iloc[-1].get("ema200", entry_price))
                m15_ema200_distance_atr = (entry_price - m15_ema) / m15_atr if m15_atr > 0 else 0.0
                m15_ema200_distance_pct = (m15_ema200_distance_atr * m15_atr / entry_price) * 100.0 if entry_price > 0 else 0.0

            h4_vol_ratio = 1.0
            if not h4_history.empty:
                avg_h4_vol = h4_history["volume"].tail(20).mean()
                h4_vol_ratio = float(h4_history.iloc[-1].get("volume", 0.0)) / avg_h4_vol if avg_h4_vol > 0 else 1.0

            # Dummy EA features for training consistency
            csv_features = {
                "body_ratio_ea": body_ratio_ea,
                "body_ratio_min": 0.5,
                "body_ratio_passed": 1.0,
                "body_ratio_mode_enc": 1.0,
                "init_risk_points": 300.0,
                "init_reward_points": 300.0,
                "initial_rr": 1.0,
            }

            all_raw = {
                **base_features,
                "h4_ema200_distance_pct": h4_ema200_distance_pct,
                "spread_to_atr_ratio": spread_to_atr_ratio,
                "body_ratio_ea": body_ratio_ea,
                "h4_atr_14": h4_atr,
                "h1_atr_14_pct": h1_atr_pct,
                "h1_ext_ema200_distance_atr": h1_ext_ema200_distance_atr,
                "h4_ema200_distance_atr": h4_ema200_distance_atr,
                "h1_ext_ema200_distance_pct": h1_ext_ema200_distance_pct,
                "h4_vol_ratio": h4_vol_ratio,
                "spread_pct": spread_pct,
                "init_risk_points": 300.0,
                "atr_14_pct": m15_atr_pct,
                "m15_ema200_distance_atr": m15_ema200_distance_atr,
                "m15_ema200_distance_pct": m15_ema200_distance_pct,
                "spread": spread,
                **csv_features,
            }

            norm_features = price_normalized_features(all_raw, entry_price)

            # Map actual net profit or simulate trade outcome
            actual_net_profit = real_trades.get((entry_time, signal))
            if actual_net_profit is None:
                # Simulasi meniru logika SL/TP EA Dev_Bot_v11_Gold (hybrid zone + price-ratio):
                #   SL anchor = swing referensi (LL utk BUY / HH utk SELL) + buffer 2000 poin x ratio
                #   Hybrid zone: jarak < MinSL(3000) dilebarkan ke 3000; > MaxSL(6000 x ratio) dipotong
                #   TP = 6000 poin x ratio; lot basis 0.05 (konsisten dgn PnL riil EA)
                # Simulasi bar-per-bar: sentuh SL/TP mana yang kena lebih dulu dalam window 24 jam.
                BASE_REF = 4500.0
                ratio = max(entry_price, 1.0) / BASE_REF
                point = 0.01  # 1 broker point = 0.01 USD price move

                swing_ref = None
                if signal == "BUY":
                    # LL referensi = low terendah window sebelum entry (pullback leg bullish)
                    hist_lows = m15_history["low"].tail(96) if not m15_history.empty else None
                    if hist_lows is not None and len(hist_lows) > 0:
                        swing_ref = float(hist_lows.min())
                else:
                    hist_highs = m15_history["high"].tail(96) if not m15_history.empty else None
                    if hist_highs is not None and len(hist_highs) > 0:
                        swing_ref = float(hist_highs.max())

                min_sl_dist = 3000 * point          # MinSL_Points_M15
                max_sl_dist = 6000 * ratio * point  # DefaultSL_Buy/Sell_M15 x ratio
                buffer = 2000 * ratio * point       # SL_Buffer_Points_M15 x ratio
                tp_dist = 6000 * ratio * point      # DefaultTP_Buy/Sell_M15 x ratio

                if signal == "BUY":
                    sl_price = (swing_ref - buffer) if swing_ref else (entry_price - min_sl_dist)
                    sl_dist = entry_price - sl_price
                    if sl_dist > max_sl_dist:
                        sl_price = entry_price - max_sl_dist
                    elif sl_dist < min_sl_dist:
                        sl_price = entry_price - min_sl_dist
                    tp_price = entry_price + tp_dist
                else:
                    sl_price = (swing_ref + buffer) if swing_ref else (entry_price + min_sl_dist)
                    sl_dist = sl_price - entry_price
                    if sl_dist > max_sl_dist:
                        sl_price = entry_price + max_sl_dist
                    elif sl_dist < min_sl_dist:
                        sl_price = entry_price + min_sl_dist
                    tp_price = entry_price - tp_dist

                # Bar-per-bar: first touch wins (konsisten eksekusi MT5: SL diprioritaskan saat keduanya kena di bar sama)
                sim_profit_usd = None
                for _, fb in forward_bars.iterrows():
                    hit_sl = (fb["low"] <= sl_price) if signal == "BUY" else (fb["high"] >= sl_price)
                    hit_tp = (fb["high"] >= tp_price) if signal == "BUY" else (fb["low"] <= tp_price)
                    if hit_sl:
                        sim_profit_usd = -(abs(entry_price - sl_price)) * 10.0 * 0.1  # 0.1 lot basis sim
                        break
                    if hit_tp:
                        sim_profit_usd = abs(tp_price - entry_price) * 10.0 * 0.1
                        break
                if sim_profit_usd is None:
                    final_close = float(forward_bars.iloc[-1]["close"])
                    profit_points = (final_close - entry_price) * 100.0 if signal == "BUY" else (entry_price - final_close) * 100.0
                    sim_profit_usd = (profit_points / 10.0) * 1.0  # approximate USD profit
                actual_net_profit = sim_profit_usd

            # Compute session features
            sess_feats = point_in_time_session_features(
                sessions,
                m15,
                prediction_time,
                entry_price,
                m15_atr,
            )
            session_name = sess_feats.get("session_zone_name", "UNKNOWN")
            session_is_dst = sess_feats.get("session_zone_is_dst", "UNKNOWN")

            # EntryStructure dari CSV real trade (kosong = sinyal tanpa eksekusi)
            entry_structure = entry_structures.get((entry_time, signal), "")
            # Status + Reject_Reason asli EA (EXECUTED / REJECTED + alasan filter)
            ea_event_status = ea_status.get((entry_time, signal), "")
            ea_event_reject_reason = ea_reject_reason.get((entry_time, signal), "N/A")

            sample = {
                "source_year": suffix,
                "year": int(suffix[:4]),
                "entry_time": entry_time,
                "source": "EXECUTED",
                "signal": signal,
                "entry_price": entry_price,
                "timeframe": "M15",
                "mfe_target": mfe_target,
                "mae_target": mae_target,
                "actual_net_profit": actual_net_profit,
                "session_name": session_name,
                "session_is_dst": session_is_dst,
                "entry_structure": entry_structure if entry_structure else "NONE",
                "ea_status": ea_event_status if ea_event_status else "NO_MATCH",
                "ea_reject_reason": ea_event_reject_reason if ea_event_reject_reason else "N/A",
                **all_raw,
                **momentum_features(m15_history, entry_price),
                **sess_feats,
                **norm_features,
            }
            samples.append(sample)
            year_count += 1

        logger.info("Built {} unconstrained v5 samples from {}", year_count, suffix)

    dataset = pd.DataFrame(samples)
    return dataset, {"skipped": skipped}


def build_feature_matrix_v5(dataset: pd.DataFrame) -> Tuple[pd.DataFrame, List[str], List[str]]:
    categorical = [
        "signal",
        "session_name",
        "session_is_dst",
        "session_zone_name",
        "session_zone_is_dst",
        "entry_structure",
    ]
    excluded = {
        "source_year", "entry_time", "year", "timeframe", "entry_price", "source", "reject_reason",
        "mfe_target", "mae_target", "mfe_target_norm", "mae_target_norm",
        "ea_status", "ea_reject_reason",
        "close_reason", "mfe_points", "mae_points", "mfe_to_rr", "mae_to_rr",
        "final_rr", "final_risk_points", "final_reward_points",
        "trailing_modified", "trailing_count", "tp_expanded", "tp_expand_count", "actual_net_profit",
        "reject_reason_enc", "is_rejected_body", "is_rejected_h1_ema", "is_rejected_h4_ema",
    }
    numeric = [
        c for c in dataset.columns
        if c not in excluded and c not in categorical and pd.api.types.is_numeric_dtype(dataset[c])
    ]
    model_df = pd.get_dummies(dataset[numeric + categorical], columns=categorical, dummy_na=True)
    model_df = model_df.replace([np.inf, -np.inf], 0.0).fillna(0.0)
    model_df = model_df.loc[:, ~model_df.columns.duplicated()]
    return model_df, numeric, categorical


def select_and_fit_regressor(
    model_df: pd.DataFrame,
    y_train: pd.Series,
    train_mask: pd.Series,
    target_name: str,
) -> Tuple[Any, StandardScaler, List[str], str]:
    x_train_raw = model_df.loc[train_mask]

    pre_xgb = XGBRegressor(n_estimators=150, max_depth=3, learning_rate=0.03, random_state=42, n_jobs=-1)
    pre_xgb.fit(StandardScaler().fit_transform(x_train_raw), y_train)
    importance = dict(zip(model_df.columns, pre_xgb.feature_importances_))
    ranked_features = [k for k, _ in sorted(importance.items(), key=lambda x: x[1], reverse=True)]

    kf = KFold(n_splits=5, shuffle=True, random_state=42)

    best_cv_r2 = -999.0
    best_model_name = ""
    best_model_obj = None
    best_features = []
    best_scaler = None

    feature_counts = [10, 15, 20, 25, 30]
    candidates = [
        ("Ridge_alpha10.0", Ridge(alpha=10.0)),
        ("RandomForest_d4_n150_leaf12", RandomForestRegressor(max_depth=4, n_estimators=150, min_samples_leaf=12, random_state=42, n_jobs=-1)),
        ("RandomForest_d5_n200_leaf15", RandomForestRegressor(max_depth=5, n_estimators=200, min_samples_leaf=15, random_state=42, n_jobs=-1)),
        ("XGBoost_d3_n120_lr002", XGBRegressor(max_depth=3, n_estimators=120, learning_rate=0.02, random_state=42, n_jobs=-1)),
    ]

    for feat_count in feature_counts:
        top_features = ranked_features[: min(feat_count, len(ranked_features))]
        x_train_selected = x_train_raw[top_features]
        scaler = StandardScaler()
        x_train = scaler.fit_transform(x_train_selected)

        for name, model in candidates:
            r2_scores = cross_val_score(model, x_train, y_train, cv=kf, scoring="r2")
            mean_r2 = r2_scores.mean()
            if mean_r2 > best_cv_r2:
                best_cv_r2 = mean_r2
                best_model_name = f"{name}_f{feat_count}"
                best_model_obj = model
                best_features = top_features
                best_scaler = scaler

    logger.info("🏆 [{}] Winner: {} (CV R2={:.4f})", target_name, best_model_name, best_cv_r2)

    x_train_final = best_scaler.fit_transform(x_train_raw[best_features])
    x_train_final_df = pd.DataFrame(x_train_final, columns=best_features)
    
    from sklearn.base import clone
    candidate_dict = dict(candidates)
    base_name = best_model_name.split("_f")[0]
    final_model = clone(candidate_dict[base_name])
    final_model.fit(x_train_final_df, y_train.values if hasattr(y_train, "values") else y_train)

    return final_model, best_scaler, best_features, best_model_name


def evaluate_regressor(
    model: Any,
    scaler: StandardScaler,
    features: List[str],
    dataset: pd.DataFrame,
    model_df: pd.DataFrame,
    target_name: str,
    train_mask: pd.Series,
    val_mask: pd.Series,
    test_mask: pd.Series,
) -> Tuple[Dict[str, Any], np.ndarray]:
    x_scaled = scaler.transform(model_df[features])
    predictions = model.predict(x_scaled)

    metrics = {}
    for split_name, mask in {
        "train": train_mask,
        "validation": val_mask,
        "test": test_mask,
    }.items():
        if not mask.any():
            continue
        y_true = dataset.loc[mask, f"{target_name}_target"]
        y_pred = predictions[mask]
        metrics[split_name] = {
            "r2": float(r2_score(y_true, y_pred)),
            "mae": float(mean_absolute_error(y_true, y_pred)),
            "y_mean": float(y_true.mean()),
            "y_pred_mean": float(y_pred.mean()),
            "y_std": float(y_true.std()),
        }

    return metrics, predictions


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


def accepted_trading_metrics_v5(df: pd.DataFrame, threshold: float, split_name: str) -> Dict[str, Any]:
    df = df.copy()
    df["expected_rr"] = df["predicted_mfe"] / df["predicted_mae"].clip(lower=1.0)
    accepted = df if threshold <= 0 else df[df["expected_rr"] >= threshold]
    returns = accepted["actual_net_profit"].astype(float) if not accepted.empty else pd.Series(dtype=float)
    win_flags = (accepted["actual_net_profit"] > 0).astype(int) if not accepted.empty else pd.Series(dtype=int)
    candidates = len(df)
    return {
        "split": split_name,
        "rr_threshold": float(threshold),
        "candidates": int(candidates),
        "accepted": int(len(accepted)),
        "accepted_rate": float(len(accepted) / candidates) if candidates else 0.0,
        "winrate": float(win_flags.mean()) if len(win_flags) else 0.0,
        "net_profit": float(returns.sum()) if len(returns) else 0.0,
        "avg_net_profit": float(returns.mean()) if len(returns) else 0.0,
        "profit_factor": profit_factor(returns) if len(returns) else 0.0,
        "max_drawdown": max_drawdown(returns) if len(returns) else 0.0,
        "expectancy": float(returns.mean()) if len(returns) else 0.0,
    }


def choose_threshold_v5(report: pd.DataFrame, min_accepted: int) -> Dict[str, Any]:
    candidates = report[(report["rr_threshold"] > 0) & (report["accepted"] >= min_accepted)].copy()
    if candidates.empty:
        candidates = report[(report["rr_threshold"] > 0) & (report["accepted"] > 0)].copy()
    if candidates.empty:
        return report.iloc[0].to_dict() if not report.empty else {}
    candidates["profit_factor_rank"] = candidates["profit_factor"].replace(np.inf, 1e9)
    candidates = candidates.sort_values(
        ["net_profit", "profit_factor_rank", "winrate", "accepted"],
        ascending=[False, False, False, False],
    )
    return candidates.iloc[0].drop(labels=["profit_factor_rank"], errors="ignore").to_dict()


def run_filter_combination_grid_search(df: pd.DataFrame, output_dir: Path) -> None:
    """Evaluate and print performance metrics under various filter combinations."""
    logger.info("--- Running Filter Combination Grid Search ---")
    
    # 1. Baseline: MS Only (All trades)
    ms_only = df["actual_net_profit"]
    
    # 2. ML Filter Only (R:R >= 1.0)
    df["expected_rr"] = df["predicted_mfe"] / df["predicted_mae"].clip(lower=1.0)
    ml_only = df[df["expected_rr"] >= 1.0]["actual_net_profit"]
    
    # 3. EA Body Ratio Filter Only (dummy proxy of EA body ratio passing)
    ea_body = df[df["body_ratio"] >= 0.5]["actual_net_profit"]
    
    # 4. ML + EA Body Ratio
    ml_ea = df[(df["expected_rr"] >= 1.0) & (df["body_ratio"] >= 0.5)]["actual_net_profit"]
    
    # Compile report
    scenarios = [
        ("MS Baseline (No Filters)", ms_only),
        ("ML Filter Only (R:R >= 1.0)", ml_only),
        ("EA Body Filter Only", ea_body),
        ("ML + EA Combined Filter", ml_ea),
    ]
    
    records = []
    print(f"\n{'Filter Scenario':30} | {'Trades':6} | {'Win Rate':8} | {'Net Profit':10} | {'Profit Factor':13} | {'Max DD'}")
    print("-" * 90)
    for name, returns in scenarios:
        win_rate = (returns > 0).mean() if len(returns) else 0.0
        pf = profit_factor(returns)
        dd = max_drawdown(returns)
        print(f"{name:30} | {len(returns):6} | {win_rate:8.1%} | ${returns.sum():9.2f} | {pf:13.2f} | ${dd:.2f}")
        records.append({
            "scenario": name,
            "trades": len(returns),
            "win_rate": win_rate,
            "net_profit": returns.sum(),
            "profit_factor": pf,
            "max_drawdown": dd,
        })
        
    report_df = pd.DataFrame(records)
    report_df.to_csv(output_dir / "filter_combination_report.csv", index=False)
    logger.info("Filter combination matrix saved to filter_combination_report.csv")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backtest-dir", type=Path, default=REPO_ROOT / "Backtest_result")
    parser.add_argument(
        "--output-dir", type=Path,
        default=PYTHON_DIR / "valuecell" / "models" / "saved" / "filter_latest",
    )
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    logger.info("=== ML Prediction v5 Unconstrained Regression Training ===")
    logger.info("Backtest dir: {}", args.backtest_dir)
    logger.info("Output dir:   {}", args.output_dir)

    dataset, info = build_dataset_v5_unconstrained(args.backtest_dir)
    if dataset.empty:
        raise RuntimeError("No v5 unconstrained samples built.")

    logger.info("Dataset built: {} samples", len(dataset))
    logger.info("Skipped: {}", info["skipped"])

    dataset_path = args.output_dir / "dataset_v5_unconstrained.csv"
    dataset.to_csv(dataset_path, index=False)

    model_df, _, _ = build_feature_matrix_v5(dataset)

    # Price-Ratio Dynamic Scaling (EA Dev_Bot_v11_Gold: BaseReferencePrice=4500).
    # Target dinormalisasi ke basis harga acuan 4500: target_norm = target_points x 4500 / entry_price.
    # Konsisten dengan cara EA menskalakan SL/TP (ratio = currentPrice / 4500).
    BASE_REFERENCE_PRICE = 4500.0
    price_ratio = dataset["entry_price"].clip(lower=1.0) / BASE_REFERENCE_PRICE
    dataset["mfe_target_norm"] = dataset["mfe_target"] / price_ratio
    dataset["mae_target_norm"] = dataset["mae_target"] / price_ratio
    logger.info("Targets normalized to base reference price {} (price-ratio scaling)", BASE_REFERENCE_PRICE)

    train_mask = dataset["year"] <= 2024
    val_mask = dataset["year"] == 2025
    test_mask = dataset["year"] >= 2026

    # --- Target 1: MFE ---
    logger.info("--- Fitting MFE Regressor ---")
    y_train_mfe = dataset.loc[train_mask, "mfe_target_norm"]
    mfe_model, mfe_scaler, mfe_features, mfe_winner_name = select_and_fit_regressor(model_df, y_train_mfe, train_mask, "MFE")
    mfe_metrics, mfe_preds = evaluate_regressor(
        mfe_model, mfe_scaler, mfe_features, dataset, model_df, "mfe", train_mask, val_mask, test_mask
    )

    # --- Target 2: MAE ---
    logger.info("--- Fitting MAE Regressor ---")
    y_train_mae = dataset.loc[train_mask, "mae_target_norm"]
    mae_model, mae_scaler, mae_features, mae_winner_name = select_and_fit_regressor(model_df, y_train_mae, train_mask, "MAE")
    mae_metrics, mae_preds = evaluate_regressor(
        mae_model, mae_scaler, mae_features, dataset, model_df, "mae", train_mask, val_mask, test_mask
    )

    # Save Scored Dataset
    scored = dataset.copy()
    scored["predicted_mfe"] = mfe_preds
    scored["predicted_mae"] = mae_preds
    scored_path = args.output_dir / "scored_v5_unconstrained.csv"
    scored.to_csv(scored_path, index=False)

    # Save artifacts directly to filter_latest
    joblib.dump(mfe_model, args.output_dir / "model_v5_mfe.pkl")
    joblib.dump(mfe_scaler, args.output_dir / "scaler_v5_mfe.pkl")
    joblib.dump(mae_model, args.output_dir / "model_v5_mae.pkl")
    joblib.dump(mae_scaler, args.output_dir / "scaler_v5_mae.pkl")

    # Grid search Expected R:R threshold from 0.8 to 2.0
    rr_thresholds = [round(x, 2) for x in np.arange(0.8, 2.01, 0.05)]
    rr_reports = []

    scored_train = scored.loc[train_mask]
    scored_val = scored.loc[val_mask]
    scored_test = scored.loc[test_mask]

    for split_name, split_df in {
        "train_2020_2024": scored_train,
        "validation_2025": scored_val,
        "test_2026": scored_test,
        "all": scored,
    }.items():
        if split_df.empty:
            continue
        rr_reports.append(accepted_trading_metrics_v5(split_df, 0.0, split_name))
        for th in rr_thresholds:
            rr_reports.append(accepted_trading_metrics_v5(split_df, th, split_name))

    rr_report_df = pd.DataFrame(rr_reports)
    rr_report_path = args.output_dir / "rr_threshold_report.csv"
    rr_report_df.to_csv(rr_report_path, index=False)

    # Choose best threshold based on validation 2025
    val_report = rr_report_df[rr_report_df["split"] == "validation_2025"]
    min_val_accepted = max(5, int(np.ceil(int(val_mask.sum()) * 0.10)))
    best_threshold = choose_threshold_v5(val_report, min_val_accepted)

    opt_th = best_threshold.get("rr_threshold", 1.0)
    test_metrics_at_th = accepted_trading_metrics_v5(scored_test, opt_th, "test_2026") if not scored_test.empty else {}

    # Run filter combinations analysis
    run_filter_combination_grid_search(scored, args.output_dir)

    # Generate Summary JSON
    summary = {
        "model_type": "regression_v5",
        "version": f"v5_unconstrained_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "created_at": datetime.now().isoformat(),
        "training_script": "train_ml_prediction_v5_unconstrained.py",
        "n_samples_total": len(dataset),
        "mfe_winner_name": mfe_winner_name,
        "mfe_features": mfe_features,
        "mfe_metrics": mfe_metrics,
        "mae_winner_name": mae_winner_name,
        "mae_features": mae_features,
        "mae_metrics": mae_metrics,
        "optimal_rr_threshold": opt_th,
        "best_validation_threshold": best_threshold,
        "test_metrics_at_optimal_threshold": test_metrics_at_th,
    }
    
    # Save both filter_model_meta.json (active load file) and summary_v5.json (experiment logs)
    summary_path = args.output_dir / "summary_v5.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    
    meta_path = args.output_dir / "filter_model_meta.json"
    meta_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    logger.info("=== v5 UNCONSTRAINED RESULTS ===")
    logger.info("MFE Winner     : {}", mfe_winner_name)
    logger.info("MAE Winner     : {}", mae_winner_name)
    logger.info("Optimal RR Th  : {}", opt_th)
    logger.info("Val Net Profit : ${:,.2f} | PF: {:.2f} | WR: {:.1%} ({} accepted)", 
                best_threshold.get("net_profit", 0.0), 
                best_threshold.get("profit_factor", 0.0), 
                best_threshold.get("winrate", 0.0), 
                best_threshold.get("accepted", 0))
    logger.info("Test Net Profit: ${:,.2f} | PF: {:.2f} | WR: {:.1%} ({} accepted)", 
                test_metrics_at_th.get("net_profit", 0.0), 
                test_metrics_at_th.get("profit_factor", 0.0), 
                test_metrics_at_th.get("winrate", 0.0), 
                test_metrics_at_th.get("accepted", 0))
    logger.info("Summary metadata saved as filter_model_meta.json and summary_v5.json")

    return 0


if __name__ == "__main__":
    sys.exit(main())
