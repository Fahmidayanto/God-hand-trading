"""
Walk-forward validation for ML Prediction v7.

Retrains fresh MFE/MAE regressors for each fold using ONLY data strictly
before the fold's test year, then predicts on that held-out year. Unlike
v5 (one fixed 2024/2025/2026 split) and v6 (no split at all, full-sample),
every prediction produced here is genuinely out-of-sample for the model
that made it.

    Fold 2022: train < 2022 (2020-2021) -> test 2022
    Fold 2023: train < 2023 (2020-2022) -> test 2023
    Fold 2024: train < 2024 (2020-2023) -> test 2024
    Fold 2025: train < 2025 (2020-2024) -> test 2025
    Fold 2026: train < 2026 (2020-2025) -> test 2026

Reuses the dataset already built by the v5 script (raw market data pipeline
is unchanged) instead of rebuilding features from the MarketData/LLHHBOS CSVs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
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
)

TEST_YEARS = [2022, 2023, 2024, 2025, 2026]


def main() -> int:
    output_dir = PYTHON_DIR / "valuecell" / "models" / "saved" / "filter_latest"
    dataset_path = output_dir / "dataset_v5_unconstrained.csv"

    logger.info("=== ML Prediction v7 Walk-Forward Validation ===")
    dataset = pd.read_csv(dataset_path)
    logger.info("Dataset loaded: {} samples ({} - {})", len(dataset), dataset["year"].min(), dataset["year"].max())

    model_df, _, _ = build_feature_matrix_v5(dataset)
    empty_mask = pd.Series(False, index=dataset.index)

    fold_summaries = []
    scored_folds = []

    for test_year in TEST_YEARS:
        train_mask = dataset["year"] < test_year
        test_mask = dataset["year"] == test_year
        n_train, n_test = int(train_mask.sum()), int(test_mask.sum())

        if n_train < 30 or n_test == 0:
            logger.warning("Skipping fold test_year={} (train={}, test={})", test_year, n_train, n_test)
            continue

        logger.info("--- Fold: train < {} ({} samples) -> test {} ({} samples) ---", test_year, n_train, test_year, n_test)

        y_mfe = dataset.loc[train_mask, "mfe_target"]
        mfe_model, mfe_scaler, mfe_features, mfe_winner = select_and_fit_regressor(
            model_df, y_mfe, train_mask, f"MFE_fold{test_year}"
        )
        mfe_metrics, mfe_preds = evaluate_regressor(
            mfe_model, mfe_scaler, mfe_features, dataset, model_df, "mfe", train_mask, empty_mask, test_mask
        )

        y_mae = dataset.loc[train_mask, "mae_target"]
        mae_model, mae_scaler, mae_features, mae_winner = select_and_fit_regressor(
            model_df, y_mae, train_mask, f"MAE_fold{test_year}"
        )
        mae_metrics, mae_preds = evaluate_regressor(
            mae_model, mae_scaler, mae_features, dataset, model_df, "mae", train_mask, empty_mask, test_mask
        )

        joblib.dump(mfe_model, output_dir / f"model_v7_fold{test_year}_mfe.pkl")
        joblib.dump(mfe_scaler, output_dir / f"scaler_v7_fold{test_year}_mfe.pkl")
        joblib.dump(mae_model, output_dir / f"model_v7_fold{test_year}_mae.pkl")
        joblib.dump(mae_scaler, output_dir / f"scaler_v7_fold{test_year}_mae.pkl")

        fold_scored = dataset.loc[test_mask].copy()
        fold_scored["predicted_mfe"] = mfe_preds[test_mask.values]
        fold_scored["predicted_mae"] = mae_preds[test_mask.values]
        fold_scored["fold_test_year"] = test_year
        fold_scored["fold_train_samples"] = n_train
        scored_folds.append(fold_scored)

        mfe_test = mfe_metrics.get("test", {})
        mae_test = mae_metrics.get("test", {})
        fold_summaries.append({
            "test_year": test_year,
            "train_samples": n_train,
            "test_samples": n_test,
            "mfe_winner": mfe_winner,
            "mfe_test_r2": mfe_test.get("r2"),
            "mfe_test_mae": mfe_test.get("mae"),
            "mae_winner": mae_winner,
            "mae_test_r2": mae_test.get("r2"),
            "mae_test_mae": mae_test.get("mae"),
        })

        logger.info(
            "Fold {} done. MFE test R2={} | MAE test R2={}",
            test_year, mfe_test.get("r2"), mae_test.get("r2"),
        )

    combined = pd.concat(scored_folds, ignore_index=True)
    combined_path = output_dir / "scored_v7_walk_forward.csv"
    combined.to_csv(combined_path, index=False)

    fold_report = pd.DataFrame(fold_summaries)
    fold_report_path = output_dir / "walk_forward_fold_report_v7.csv"
    fold_report.to_csv(fold_report_path, index=False)

    summary = {
        "model_type": "regression_v7_walk_forward",
        "training_script": "train_ml_prediction_v7_walk_forward.py",
        "test_years": TEST_YEARS,
        "note": "Each fold trained ONLY on data strictly before its test year. "
                "Predictions in scored_v7_walk_forward.csv are genuinely out-of-sample.",
        "folds": fold_summaries,
    }
    (output_dir / "summary_v7.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    logger.info("=== v7 WALK-FORWARD SUMMARY ===")
    print(fold_report.to_string(index=False))
    logger.info("Combined out-of-sample predictions saved to {}", combined_path)
    logger.info("Per-fold models saved as model_v7_fold<year>_mfe.pkl / _mae.pkl")

    return 0


if __name__ == "__main__":
    sys.exit(main())
