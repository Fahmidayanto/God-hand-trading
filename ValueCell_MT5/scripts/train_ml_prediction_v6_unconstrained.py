"""
Train ML Prediction v6 (Regression Model) on the FULL unconstrained dataset (2020 - Jul 2026).

Unlike v5 (train=2020-2024, validation=2025, test=2026), v6 fits, tunes the R:R
threshold, and evaluates on the same full dataset -- no held-out split. Metrics
reported here are therefore in-sample and should not be read as a forecast of
future performance; see explore_optimization_scenarios_v6.py for Scenario 4/5
backtests on top of these predictions.

Reuses the dataset already built by the v5 script (raw market data pipeline is
unchanged) instead of rebuilding features from the MarketData/LLHHBOS CSVs again.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from loguru import logger

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from train_ml_prediction_v5_unconstrained import (  # noqa: E402
    PYTHON_DIR,
    build_feature_matrix_v5,
    select_and_fit_regressor,
    evaluate_regressor,
    accepted_trading_metrics_v5,
    choose_threshold_v5,
)


def main() -> int:
    output_dir = PYTHON_DIR / "valuecell" / "models" / "saved" / "filter_latest"
    dataset_path = output_dir / "dataset_v5_unconstrained.csv"

    logger.info("=== ML Prediction v6 (Full-Sample) Training ===")
    if not dataset_path.exists():
        raise RuntimeError(f"Dataset not found at {dataset_path}. Run the v5 training script first to build it.")

    dataset = pd.read_csv(dataset_path)
    logger.info("Dataset loaded: {} samples ({} - {})", len(dataset), dataset["year"].min(), dataset["year"].max())

    model_df, _, _ = build_feature_matrix_v5(dataset)

    # v6 fits, tunes, and evaluates on the FULL dataset -- no held-out split.
    full_mask = pd.Series(True, index=dataset.index)
    empty_mask = pd.Series(False, index=dataset.index)

    logger.info("--- Fitting MFE Regressor (full-sample) ---")
    y_mfe = dataset.loc[full_mask, "mfe_target"]
    mfe_model, mfe_scaler, mfe_features, mfe_winner_name = select_and_fit_regressor(model_df, y_mfe, full_mask, "MFE")
    mfe_metrics, mfe_preds = evaluate_regressor(
        mfe_model, mfe_scaler, mfe_features, dataset, model_df, "mfe", full_mask, empty_mask, empty_mask
    )

    logger.info("--- Fitting MAE Regressor (full-sample) ---")
    y_mae = dataset.loc[full_mask, "mae_target"]
    mae_model, mae_scaler, mae_features, mae_winner_name = select_and_fit_regressor(model_df, y_mae, full_mask, "MAE")
    mae_metrics, mae_preds = evaluate_regressor(
        mae_model, mae_scaler, mae_features, dataset, model_df, "mae", full_mask, empty_mask, empty_mask
    )

    scored = dataset.copy()
    scored["predicted_mfe"] = mfe_preds
    scored["predicted_mae"] = mae_preds
    scored_path = output_dir / "scored_v6_unconstrained.csv"
    scored.to_csv(scored_path, index=False)

    joblib.dump(mfe_model, output_dir / "model_v6_mfe.pkl")
    joblib.dump(mfe_scaler, output_dir / "scaler_v6_mfe.pkl")
    joblib.dump(mae_model, output_dir / "model_v6_mae.pkl")
    joblib.dump(mae_scaler, output_dir / "scaler_v6_mae.pkl")

    # Grid search R:R threshold on the full dataset (in-sample, no separate validation split)
    rr_thresholds = [round(x, 2) for x in np.arange(0.8, 2.01, 0.05)]
    rr_reports = [accepted_trading_metrics_v5(scored, 0.0, "full_2020_2026")]
    for th in rr_thresholds:
        rr_reports.append(accepted_trading_metrics_v5(scored, th, "full_2020_2026"))
    rr_report_df = pd.DataFrame(rr_reports)
    rr_report_df.to_csv(output_dir / "rr_threshold_report_v6.csv", index=False)

    min_accepted = max(5, int(np.ceil(len(scored) * 0.10)))
    best_threshold = choose_threshold_v5(rr_report_df, min_accepted)
    opt_th = best_threshold.get("rr_threshold", 1.0)

    summary = {
        "model_type": "regression_v6_full_sample",
        "version": f"v6_full_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}",
        "training_script": "train_ml_prediction_v6_unconstrained.py",
        "n_samples_total": len(dataset),
        "note": "Trained, threshold-tuned, and evaluated on the FULL 2020-2026(Jul) dataset -- no held-out split. Metrics are in-sample.",
        "mfe_winner_name": mfe_winner_name,
        "mfe_features": mfe_features,
        "mfe_metrics": mfe_metrics,
        "mae_winner_name": mae_winner_name,
        "mae_features": mae_features,
        "mae_metrics": mae_metrics,
        "optimal_rr_threshold": opt_th,
        "best_threshold_metrics": best_threshold,
    }
    summary_path = output_dir / "summary_v6.json"
    summary_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    logger.info("=== v6 FULL-SAMPLE RESULTS ===")
    logger.info("MFE Winner: {}", mfe_winner_name)
    logger.info("MAE Winner: {}", mae_winner_name)
    logger.info("Optimal RR Threshold: {}", opt_th)
    logger.info(
        "Net Profit @ threshold: ${:,.2f} | PF: {:.2f} | WR: {:.1%} ({} accepted)",
        best_threshold.get("net_profit", 0.0),
        best_threshold.get("profit_factor", 0.0),
        best_threshold.get("winrate", 0.0),
        best_threshold.get("accepted", 0),
    )
    logger.info("Saved model_v6_mfe.pkl, model_v6_mae.pkl, scored_v6_unconstrained.csv, summary_v6.json")

    return 0


if __name__ == "__main__":
    sys.exit(main())
