"""
Walk-forward validation for ML Prediction v8 -- same expanding-window folds as
v7, but regression targets are normalized by ATR at entry time instead of raw
points:

    mfe_target_norm = mfe_target / atr_14
    mae_target_norm = mae_target / atr_14

Root cause this fixes: gold's price level moved from ~$1,800 (2020) to
~$4,600+ (2026), so raw-point MFE/MAE targets grew ~5x over the same window.
A model trained on 2020-2025 raw points cannot extrapolate to 2026's scale
(v7 fold2026 underestimated MFE by 2.06x and accepted zero trades). Predicting
the ATR-relative ratio instead lets the model learn "how big a move is
relative to current volatility", which stays roughly stable across price
regimes; predictions are converted back to points (* ATR) after inference.

IMPORTANT: mfe_target_norm/mae_target_norm must be dropped from the feature
matrix before fitting -- otherwise the target leaks into its own features
(this bug was caught during manual validation: CV R2 was a suspicious 0.9999
until the columns were excluded).

    Fold 2022: train < 2022 (2020-2021) -> test 2022
    Fold 2023: train < 2023 (2020-2022) -> test 2023
    Fold 2024: train < 2024 (2020-2023) -> test 2024
    Fold 2025: train < 2025 (2020-2024) -> test 2025
    Fold 2026: train < 2026 (2020-2025) -> test 2026
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import pandas as pd
from loguru import logger
from sklearn.metrics import mean_absolute_error, r2_score

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from train_ml_prediction_v5_unconstrained import (  # noqa: E402
    PYTHON_DIR,
    build_feature_matrix_v5,
    select_and_fit_regressor,
)

TEST_YEARS = [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026]
ATR_FLOOR = 0.5


def main() -> int:
    output_dir = PYTHON_DIR / "valuecell" / "models" / "saved" / "filter_latest"
    dataset_path = output_dir / "dataset_v5_unconstrained.csv"

    logger.info("=== ML Prediction v8 Walk-Forward (ATR-Normalized Targets) ===")
    dataset = pd.read_csv(dataset_path)
    logger.info("Dataset loaded: {} samples ({} - {})", len(dataset), dataset["year"].min(), dataset["year"].max())

    atr_safe = dataset["atr_14"].clip(lower=ATR_FLOOR)
    dataset["mfe_target_norm"] = dataset["mfe_target"] / atr_safe
    dataset["mae_target_norm"] = dataset["mae_target"] / atr_safe

    model_df, _, _ = build_feature_matrix_v5(dataset)
    # Critical: drop the normalized targets from the feature matrix so they
    # cannot leak into their own prediction.
    model_df = model_df.drop(columns=["mfe_target_norm", "mae_target_norm"], errors="ignore")

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

        y_mfe_norm = dataset.loc[train_mask, "mfe_target_norm"]
        mfe_model, mfe_scaler, mfe_features, mfe_winner = select_and_fit_regressor(
            model_df, y_mfe_norm, train_mask, f"MFEnorm_fold{test_year}"
        )
        pred_mfe_norm = mfe_model.predict(mfe_scaler.transform(model_df.loc[test_mask, mfe_features]))

        y_mae_norm = dataset.loc[train_mask, "mae_target_norm"]
        mae_model, mae_scaler, mae_features, mae_winner = select_and_fit_regressor(
            model_df, y_mae_norm, train_mask, f"MAEnorm_fold{test_year}"
        )
        pred_mae_norm = mae_model.predict(mae_scaler.transform(model_df.loc[test_mask, mae_features]))

        atr_test = atr_safe.loc[test_mask].values
        pred_mfe_points = pred_mfe_norm * atr_test
        pred_mae_points = pred_mae_norm * atr_test

        actual_mfe = dataset.loc[test_mask, "mfe_target"].values
        actual_mae = dataset.loc[test_mask, "mae_target"].values

        mfe_r2 = r2_score(actual_mfe, pred_mfe_points)
        mae_r2 = r2_score(actual_mae, pred_mae_points)
        mfe_mae_err = mean_absolute_error(actual_mfe, pred_mfe_points)
        mae_mae_err = mean_absolute_error(actual_mae, pred_mae_points)
        mfe_bias = actual_mfe.mean() / pred_mfe_points.mean() if pred_mfe_points.mean() else float("nan")
        mae_bias = actual_mae.mean() / pred_mae_points.mean() if pred_mae_points.mean() else float("nan")

        joblib.dump(mfe_model, output_dir / f"model_v8_fold{test_year}_mfe.pkl")
        joblib.dump(mfe_scaler, output_dir / f"scaler_v8_fold{test_year}_mfe.pkl")
        joblib.dump(mae_model, output_dir / f"model_v8_fold{test_year}_mae.pkl")
        joblib.dump(mae_scaler, output_dir / f"scaler_v8_fold{test_year}_mae.pkl")

        fold_scored = dataset.loc[test_mask].copy()
        fold_scored["predicted_mfe"] = pred_mfe_points
        fold_scored["predicted_mae"] = pred_mae_points
        fold_scored["fold_test_year"] = test_year
        fold_scored["fold_train_samples"] = n_train
        scored_folds.append(fold_scored)

        fold_summaries.append({
            "test_year": test_year,
            "train_samples": n_train,
            "test_samples": n_test,
            "mfe_winner": mfe_winner,
            "mfe_test_r2": mfe_r2,
            "mfe_test_mae": mfe_mae_err,
            "mfe_bias_ratio": mfe_bias,
            "mae_winner": mae_winner,
            "mae_test_r2": mae_r2,
            "mae_test_mae": mae_mae_err,
            "mae_bias_ratio": mae_bias,
        })

        logger.info(
            "Fold {} done. MFE R2={:.3f} (bias={:.3f}) | MAE R2={:.3f} (bias={:.3f})",
            test_year, mfe_r2, mfe_bias, mae_r2, mae_bias,
        )

    combined = pd.concat(scored_folds, ignore_index=True)
    combined_path = output_dir / "scored_v8_walk_forward.csv"
    combined.to_csv(combined_path, index=False)

    fold_report = pd.DataFrame(fold_summaries)
    fold_report_path = output_dir / "walk_forward_fold_report_v8.csv"
    fold_report.to_csv(fold_report_path, index=False)

    summary = {
        "model_type": "regression_v8_walk_forward_atr_normalized",
        "training_script": "train_ml_prediction_v8_walk_forward_normalized.py",
        "test_years": TEST_YEARS,
        "note": "Same walk-forward folds as v7, but targets are ATR-normalized "
                "(mfe_target/atr_14, mae_target/atr_14) to fix extrapolation failure "
                "across gold's 2020->2026 price regime shift (~2.6x). Predictions "
                "converted back to points via * atr_14 before scoring.",
        "atr_floor": ATR_FLOOR,
        "folds": fold_summaries,
    }
    (output_dir / "summary_v8.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    logger.info("=== v8 WALK-FORWARD (NORMALIZED) SUMMARY ===")
    print(fold_report.to_string(index=False))
    logger.info("Combined out-of-sample predictions saved to {}", combined_path)
    logger.info("Per-fold models saved as model_v8_fold<year>_mfe.pkl / _mae.pkl")

    return 0


if __name__ == "__main__":
    sys.exit(main())
