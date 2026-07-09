"""
Train/evaluate ML Prediction v5 (Regression Model) from Backtest_result signal candidates.

v5 focuses on predicting MFE (Max Favorable Excursion) and MAE (Max Adverse Excursion):
- Target 1: MFE (TP Dinamis) -> MaxFavorablePoints
- Target 2: MAE (SL Dinamis) -> MaxAdversePoints
- Models: XGBRegressor, RandomForestRegressor, Ridge Regression
- Features: Pre-trade price-normalized features, spread_to_atr_ratio, double_trend_aligned.
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
    label_from_csv,
    label_levels,
    forward_outcome_label,
    current_bar_at_or_before,
    last_rows_at_or_before,
    row_to_event,
    trend_features,
    momentum_features,
    session_features,
    csv_trade_features,
    price_normalized_features,
    FeatureEngineer,
)


# ============================================================
# DATASET BUILDING
# ============================================================
def build_dataset_v5(backtest_dir: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Build EXECUTED-only dataset for Regression v5 (MFE and MAE targets)."""
    engineer = FeatureEngineer()
    samples = []
    skipped = {
        "missing_files": 0,
        "rejected_skipped": 0,
        "no_label": 0,
        "missing_bar": 0,
        "candidates_total": 0,
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

            # Skip REJECTED signals entirely
            if status == "REJECTED":
                skipped["rejected_skipped"] += 1
                continue

            # --- Target Continuous Variables for Regressor ---
            mfe_target = safe_float(trade_row.get("MaxFavorablePoints"), 0.0)
            mae_target = safe_float(trade_row.get("MaxAdversePoints"), 0.0)

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
                "session_name": str(trade_row.get("Session", "UNKNOWN")),
                "session_is_dst": str(trade_row.get("Session_IsDST", "UNKNOWN")),
                "session_zone_name": str(trade_row.get("Session_Zone", "UNKNOWN")),
                "session_zone_is_dst": str(trade_row.get("Session_Zone_IsDST", "UNKNOWN")),
                "mfe_target": mfe_target,
                "mae_target": mae_target,
                "actual_net_profit": safe_float(trade_row.get("Net_Profit")),
                "spread": all_raw["spread"],
                **all_raw,
                **momentum_features(m15_history, entry_price),
                **session_features(sessions, entry_time, entry_price, atr),
                **norm_features,
            }
            samples.append(sample)
            year_count += 1

        logger.info("Built {} v5 samples from {}", year_count, suffix)

    dataset = pd.DataFrame(samples)
    return dataset, {"skipped": skipped}


# ============================================================
# FEATURE MATRIX
# ============================================================
def build_feature_matrix_v5(dataset: pd.DataFrame) -> tuple[pd.DataFrame, list[str], list[str]]:
    categorical = [
        "signal",
        "session_name",
        "session_is_dst",
        "session_zone_name",
        "session_zone_is_dst",
    ]
    excluded = {
        # Meta columns
        "source_year", "entry_time", "year", "timeframe", "entry_price", "source", "reject_reason",
        # Target variables (continuous)
        "mfe_target", "mae_target",
        # Leakage metrics
        "close_reason", "mfe_points", "mae_points", "mfe_to_rr", "mae_to_rr",
        "final_rr", "final_risk_points", "final_reward_points",
        "trailing_modified", "trailing_count", "tp_expanded", "tp_expand_count", "actual_net_profit",
        # Reject flags (meaningless for executed only)
        "reject_reason_enc", "is_rejected_body", "is_rejected_h1_ema", "is_rejected_h4_ema",
    }
    numeric = [
        c for c in dataset.columns
        if c not in excluded and c not in categorical and pd.api.types.is_numeric_dtype(dataset[c])
    ]
    model_df = pd.get_dummies(dataset[numeric + categorical], columns=categorical, dummy_na=True)
    model_df = model_df.replace([np.inf, -np.inf], 0.0).fillna(0.0)
    model_df = model_df.loc[:, ~model_df.columns.duplicated()]
    logger.info("Feature matrix: {} numeric + {} categorical = {} columns",
                len(numeric), len(categorical), len(model_df.columns))
    return model_df, numeric, categorical


# ============================================================
# MODEL SELECTION & TRAINING
# ============================================================
def select_and_fit_regressor(
    model_df: pd.DataFrame,
    y_train: pd.Series,
    train_mask: pd.Series,
    target_name: str,
) -> tuple[Any, StandardScaler, list[str], str]:
    """Select the best regression model and top features for the given target by CV R2."""
    x_train_raw = model_df.loc[train_mask]

    # Preliminary selection of top features using XGBoost importance
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

    feature_counts = [10, 15, 20, 25, 30, 40, 50]
    candidates = [
        ("Ridge_alpha1.0", Ridge(alpha=1.0)),
        ("Ridge_alpha10.0", Ridge(alpha=10.0)),
        ("Ridge_alpha100.0", Ridge(alpha=100.0)),
        ("RandomForest_d3_n100_leaf8", RandomForestRegressor(max_depth=3, n_estimators=100, min_samples_leaf=8, random_state=42, n_jobs=-1)),
        ("RandomForest_d4_n150_leaf12", RandomForestRegressor(max_depth=4, n_estimators=150, min_samples_leaf=12, random_state=42, n_jobs=-1)),
        ("RandomForest_d5_n200_leaf15", RandomForestRegressor(max_depth=5, n_estimators=200, min_samples_leaf=15, random_state=42, n_jobs=-1)),
        ("XGBoost_d2_n100_lr003", XGBRegressor(max_depth=2, n_estimators=100, learning_rate=0.03, random_state=42, n_jobs=-1)),
        ("XGBoost_d3_n120_lr002", XGBRegressor(max_depth=3, n_estimators=120, learning_rate=0.02, random_state=42, n_jobs=-1)),
        ("XGBoost_d4_n150_lr001", XGBRegressor(max_depth=4, n_estimators=150, learning_rate=0.01, random_state=42, n_jobs=-1)),
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

    # Fit final model with best features and best scaler
    x_train_final = best_scaler.fit_transform(x_train_raw[best_features])
    
    # Clone the clean estimator to avoid refitting warning
    from sklearn.base import clone
    candidate_dict = dict(candidates)
    base_name = best_model_name.split("_f")[0]
    final_model = clone(candidate_dict[base_name])
    final_model.fit(x_train_final, y_train)
    final_model.feature_names_in_ = np.array(best_features, dtype=object)

    return final_model, best_scaler, best_features, best_model_name


def evaluate_regressor(
    model: Any,
    scaler: StandardScaler,
    features: list[str],
    dataset: pd.DataFrame,
    model_df: pd.DataFrame,
    target_name: str,
    train_mask: pd.Series,
    val_mask: pd.Series,
    test_mask: pd.Series,
) -> dict[str, Any]:
    """Score full dataset and compute performance metrics for regression."""
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


# ============================================================
# TRADING SIMULATION & OPTIMIZATION
# ============================================================
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


def accepted_trading_metrics_v5(df: pd.DataFrame, threshold: float, split_name: str) -> dict[str, Any]:
    # Calculate expected RR (predicted_mfe / predicted_mae)
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


def choose_threshold_v5(report: pd.DataFrame, min_accepted: int) -> dict[str, Any]:
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


# ============================================================
# MAIN
# ============================================================
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backtest-dir", type=Path, default=REPO_ROOT / "Backtest_result")
    parser.add_argument(
        "--output-dir", type=Path,
        default=PYTHON_DIR / "valuecell" / "models" / "experiments" / "ml_prediction_v5",
    )
    args = parser.parse_args()

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = args.output_dir / stamp
    run_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=== ML Prediction v5 Regression Training ===")
    logger.info("Backtest dir: {}", args.backtest_dir)
    logger.info("Output dir:   {}", run_dir)

    dataset, info = build_dataset_v5(args.backtest_dir)
    if dataset.empty:
        raise RuntimeError("No v5 samples built.")

    logger.info("Dataset built: {} samples", len(dataset))
    logger.info("Skipped: {}", info["skipped"])

    dataset_path = run_dir / "dataset_v5.csv"
    dataset.to_csv(dataset_path, index=False)

    model_df, _, _ = build_feature_matrix_v5(dataset)

    train_mask = dataset["year"] <= 2024
    val_mask = dataset["year"] == 2025
    test_mask = dataset["year"] >= 2026

    # --- Target 1: MFE (TP Target) ---
    logger.info("--- Fitting MFE Regressor ---")
    y_train_mfe = dataset.loc[train_mask, "mfe_target"]
    mfe_model, mfe_scaler, mfe_features, mfe_winner_name = select_and_fit_regressor(model_df, y_train_mfe, train_mask, "MFE")
    mfe_metrics, mfe_preds = evaluate_regressor(
        mfe_model, mfe_scaler, mfe_features, dataset, model_df, "mfe", train_mask, val_mask, test_mask
    )

    # --- Target 2: MAE (SL Target) ---
    logger.info("--- Fitting MAE Regressor ---")
    y_train_mae = dataset.loc[train_mask, "mae_target"]
    mae_model, mae_scaler, mae_features, mae_winner_name = select_and_fit_regressor(model_df, y_train_mae, train_mask, "MAE")
    mae_metrics, mae_preds = evaluate_regressor(
        mae_model, mae_scaler, mae_features, dataset, model_df, "mae", train_mask, val_mask, test_mask
    )

    # Save Scored Dataset
    scored = dataset.copy()
    scored["predicted_mfe"] = mfe_preds
    scored["predicted_mae"] = mae_preds
    scored_path = run_dir / "scored_v5.csv"
    scored.to_csv(scored_path, index=False)

    # Save artifacts
    joblib.dump(mfe_model, run_dir / "model_v5_mfe.pkl")
    joblib.dump(mfe_scaler, run_dir / "scaler_v5_mfe.pkl")
    joblib.dump(mae_model, run_dir / "model_v5_mae.pkl")
    joblib.dump(mae_scaler, run_dir / "scaler_v5_mae.pkl")

    # Grid search Expected R:R threshold from 1.0 to 2.5
    rr_thresholds = [round(x, 2) for x in np.arange(1.0, 2.51, 0.02)]
    rr_reports = []

    # Partition scored datasets for threshold calculation
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
    rr_report_path = run_dir / "rr_threshold_report.csv"
    rr_report_df.to_csv(rr_report_path, index=False)

    # Choose best threshold based on validation 2025
    val_report = rr_report_df[rr_report_df["split"] == "validation_2025"]
    min_val_accepted = max(5, int(np.ceil(int(val_mask.sum()) * 0.10)))
    best_threshold = choose_threshold_v5(val_report, min_val_accepted)

    # Fetch corresponding test metrics at that optimal validation threshold
    opt_th = best_threshold.get("rr_threshold", 1.3)
    test_metrics_at_th = accepted_trading_metrics_v5(scored_test, opt_th, "test_2026") if not scored_test.empty else {}

    # Generate Summary
    summary = {
        "version": f"v5_{stamp}",
        "created_at": datetime.now().isoformat(),
        "training_script": "train_ml_prediction_v5.py",
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
    summary_path = run_dir / "summary_v5.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    logger.info("=== v5 RESULTS ===")
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
    logger.info("Summary saved to {}", summary_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
