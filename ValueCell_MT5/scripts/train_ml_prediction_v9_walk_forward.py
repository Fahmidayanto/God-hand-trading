"""
ML Prediction v9: Walk-Forward Validation (News-Aware + Price-Ratio Normalized).

Uses:
- Dataset: dataset_v9_unconstrained.csv (with LanceDB news features: is_news_blackout,
  minutes_to_next_news, minutes_since_last_news, is_fomc_day, hours_to_next_fomc).
- Target Normalization: Price-Ratio Dynamic Scaling (BASE_REFERENCE_PRICE = 4500.0).
- Evaluation: Walk-Forward Expanding Window across 7 folds (2020-2026).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import pandas as pd
import numpy as np
from loguru import logger
from sklearn.metrics import mean_absolute_error, r2_score

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
PYTHON_DIR = PROJECT_ROOT / "python"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

from train_ml_prediction_v5_unconstrained import (  # noqa: E402
    build_feature_matrix_v5,
    select_and_fit_regressor,
)

TEST_YEARS = [2020, 2021, 2022, 2023, 2024, 2025, 2026]
BASE_REFERENCE_PRICE = 4500.0


def main() -> int:
    output_dir = PYTHON_DIR / "valuecell" / "models" / "saved" / "filter_latest"
    dataset_path = output_dir / "dataset_v9_unconstrained.csv"

    logger.info("=== ML Prediction v9 Walk-Forward (News-Aware & Price-Ratio Normalized) ===")
    dataset = pd.read_csv(dataset_path)
    logger.info("Dataset loaded: {} samples ({} - {})", len(dataset), dataset["year"].min(), dataset["year"].max())

    # Price-Ratio Dynamic Scaling for targets
    price_ratio_safe = (dataset["entry_price"] / BASE_REFERENCE_PRICE).clip(lower=1.0 / BASE_REFERENCE_PRICE)
    dataset["mfe_target_norm"] = dataset["mfe_target"] / price_ratio_safe
    dataset["mae_target_norm"] = dataset["mae_target"] / price_ratio_safe

    model_df, numeric_cols, cat_cols = build_feature_matrix_v5(dataset)
    model_df = model_df.drop(columns=["mfe_target_norm", "mae_target_norm"], errors="ignore")

    logger.info("Feature Matrix v9 Built: {} columns (Numeric: {}, Categorical: {})", len(model_df.columns), len(numeric_cols), len(cat_cols))
    # Check that news features are included in model_df
    news_cols = [c for c in model_df.columns if "news" in c or "fomc" in c]
    logger.info("Integrated News Features: {}", news_cols)

    fold_summaries = []
    scored_folds = []

    for test_year in TEST_YEARS:
        train_mask = dataset["year"] < test_year
        test_mask = dataset["year"] == test_year
        n_train, n_test = int(train_mask.sum()), int(test_mask.sum())

        if n_train < 30 or n_test == 0:
            logger.warning("Skipping fold test_year={} (train={}, test={})", test_year, n_train, n_test)
            continue

        logger.info("--- Fold v9: train < {} ({} samples) -> test {} ({} samples) ---", test_year, n_train, test_year, n_test)

        # 1. Fit MFE Regressor
        y_mfe_norm = dataset.loc[train_mask, "mfe_target_norm"]
        mfe_model, mfe_scaler, mfe_features, mfe_winner = select_and_fit_regressor(
            model_df, y_mfe_norm, train_mask, f"MFEnorm_v9_fold{test_year}"
        )
        pred_mfe_norm = mfe_model.predict(mfe_scaler.transform(model_df.loc[test_mask, mfe_features]))
        pred_mfe = pred_mfe_norm * price_ratio_safe.loc[test_mask].values

        # 2. Fit MAE Regressor
        y_mae_norm = dataset.loc[train_mask, "mae_target_norm"]
        mae_model, mae_scaler, mae_features, mae_winner = select_and_fit_regressor(
            model_df, y_mae_norm, train_mask, f"MAEnorm_v9_fold{test_year}"
        )
        pred_mae_norm = mae_model.predict(mae_scaler.transform(model_df.loc[test_mask, mae_features]))
        pred_mae = pred_mae_norm * price_ratio_safe.loc[test_mask].values

        # Out-of-sample metrics (scored in original points)
        act_mfe = dataset.loc[test_mask, "mfe_target"].values
        act_mae = dataset.loc[test_mask, "mae_target"].values

        mfe_test_r2 = float(r2_score(act_mfe, pred_mfe))
        mfe_test_mae = float(mean_absolute_error(act_mfe, pred_mfe))
        mae_test_r2 = float(r2_score(act_mae, pred_mae))
        mae_test_mae = float(mean_absolute_error(act_mae, pred_mae))

        # Bias ratio (mean predicted / mean actual)
        mfe_bias = float(pred_mfe.mean() / (act_mfe.mean() if act_mfe.mean() > 0 else 1.0))
        mae_bias = float(pred_mae.mean() / (act_mae.mean() if act_mae.mean() > 0 else 1.0))

        logger.info(
            "Fold v9 {} (test N={}) -> MFE winner: {} (R2={:.3f}, MAE={:.1f}, bias={:.2f}) | "
            "MAE winner: {} (R2={:.3f}, MAE={:.1f}, bias={:.2f})",
            test_year, n_test, mfe_winner, mfe_test_r2, mfe_test_mae, mfe_bias,
            mae_winner, mae_test_r2, mae_test_mae, mae_bias,
        )

        fold_summaries.append({
            "test_year": test_year,
            "train_samples": n_train,
            "test_samples": n_test,
            "mfe_winner": mfe_winner,
            "mfe_test_r2": mfe_test_r2,
            "mfe_test_mae": mfe_test_mae,
            "mfe_bias_ratio": mfe_bias,
            "mfe_features": mfe_features,
            "mae_winner": mae_winner,
            "mae_test_r2": mae_test_r2,
            "mae_test_mae": mae_test_mae,
            "mae_bias_ratio": mae_bias,
            "mae_features": mae_features,
        })

        fold_df = dataset.loc[test_mask].copy()
        fold_df["predicted_mfe"] = pred_mfe
        fold_df["predicted_mae"] = pred_mae
        fold_df["fold_test_year"] = test_year
        fold_df["fold_train_samples"] = n_train
        scored_folds.append(fold_df)

    # Save artifacts
    report_df = pd.DataFrame(fold_summaries).drop(columns=["mfe_features", "mae_features"])
    report_path = output_dir / "walk_forward_fold_report_v9.csv"
    report_df.to_csv(report_path, index=False)
    logger.info("Saved walk-forward fold report to: {}", report_path)

    scored_combined = pd.concat(scored_folds, axis=0).reset_index(drop=True)
    scored_path = output_dir / "scored_v9_walk_forward.csv"
    scored_combined.to_csv(scored_path, index=False)
    logger.info("Saved combined scored walk-forward dataset to: {}", scored_path)

    summary = {
        "model_type": "regression_v9_news_aware_price_ratio_normalized",
        "training_script": "train_ml_prediction_v9_walk_forward.py",
        "normalization": "price_ratio",
        "base_reference_price": BASE_REFERENCE_PRICE,
        "n_samples_total": len(dataset),
        "folds": fold_summaries,
    }
    summary_path = output_dir / "summary_v9.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    logger.info("Saved summary v9 to: {}", summary_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
