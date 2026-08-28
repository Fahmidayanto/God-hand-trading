"""
ML Prediction v9 FINAL: Full Training (2019-2026) News-Aware + Price-Ratio Normalized.

Trains on all 1,942 samples with LanceDB news features (is_news_blackout,
minutes_to_next_news, minutes_since_last_news, is_fomc_day, hours_to_next_fomc)
and Price-Ratio Dynamic Scaling (BASE_REFERENCE_PRICE = 4500.0).

Outputs:
- model_v9_final_mfe.pkl, scaler_v9_final_mfe.pkl
- model_v9_final_mae.pkl, scaler_v9_final_mae.pkl
- summary_v9_final.json
- filter_model_meta.json (production active meta)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
import shutil

import joblib
import pandas as pd
from loguru import logger

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

BASE_REFERENCE_PRICE = 4500.0


def main() -> int:
    output_dir = PYTHON_DIR / "valuecell" / "models" / "saved" / "filter_latest"
    dataset_path = output_dir / "dataset_v9_unconstrained.csv"

    logger.info("=== ML Prediction v9 FINAL (Full Dataset 2019-2026, News-Aware) ===")
    dataset = pd.read_csv(dataset_path)
    logger.info("Dataset loaded: {} samples ({} - {})", len(dataset), dataset["year"].min(), dataset["year"].max())

    # Dynamic Scaling
    price_ratio_safe = (dataset["entry_price"] / BASE_REFERENCE_PRICE).clip(lower=1.0 / BASE_REFERENCE_PRICE)
    dataset["mfe_target_norm"] = dataset["mfe_target"] / price_ratio_safe
    dataset["mae_target_norm"] = dataset["mae_target"] / price_ratio_safe

    model_df, numeric_cols, cat_cols = build_feature_matrix_v5(dataset)
    model_df = model_df.drop(columns=["mfe_target_norm", "mae_target_norm"], errors="ignore")

    train_mask = pd.Series(True, index=dataset.index)
    n_train = int(train_mask.sum())
    logger.info("--- Final fit v9: train on all {} samples (2019-2026), no holdout ---", n_train)

    # 1. Fit MFE Regressor
    y_mfe_norm = dataset.loc[train_mask, "mfe_target_norm"]
    mfe_model, mfe_scaler, mfe_features, mfe_winner = select_and_fit_regressor(
        model_df, y_mfe_norm, train_mask, "MFEnorm_v9_final"
    )
    logger.info("Final MFE winner v9: {} ({} features)", mfe_winner, len(mfe_features))

    # 2. Fit MAE Regressor
    y_mae_norm = dataset.loc[train_mask, "mae_target_norm"]
    mae_model, mae_scaler, mae_features, mae_winner = select_and_fit_regressor(
        model_df, y_mae_norm, train_mask, "MAEnorm_v9_final"
    )
    logger.info("Final MAE winner v9: {} ({} features)", mae_winner, len(mae_features))

    # Check for news features in selected features
    mfe_news = [f for f in mfe_features if "news" in f or "fomc" in f]
    mae_news = [f for f in mae_features if "news" in f or "fomc" in f]
    logger.info("Selected News Features in MFE: {}", mfe_news)
    logger.info("Selected News Features in MAE: {}", mae_news)

    # Save artifacts
    joblib.dump(mfe_model, output_dir / "model_v9_final_mfe.pkl")
    joblib.dump(mfe_scaler, output_dir / "scaler_v9_final_mfe.pkl")
    joblib.dump(mae_model, output_dir / "model_v9_final_mae.pkl")
    joblib.dump(mae_scaler, output_dir / "scaler_v9_final_mae.pkl")

    # Also update the foldfinal names for agent inference
    joblib.dump(mfe_model, output_dir / "model_v9_foldfinal_mfe.pkl")
    joblib.dump(mfe_scaler, output_dir / "scaler_v9_foldfinal_mfe.pkl")
    joblib.dump(mae_model, output_dir / "model_v9_foldfinal_mae.pkl")
    joblib.dump(mae_scaler, output_dir / "scaler_v9_foldfinal_mae.pkl")

    summary = {
        "model_type": "regression_v9_final_news_aware_price_ratio_normalized",
        "training_script": "train_ml_prediction_v9_final.py",
        "train_years": "2019-2026",
        "n_samples_total": n_train,
        "normalization": "price_ratio",
        "base_reference_price": BASE_REFERENCE_PRICE,
        "mfe_winner": mfe_winner,
        "mfe_features": mfe_features,
        "mae_winner": mae_winner,
        "mae_features": mae_features,
        "optimal_rr_threshold": 1.05,
    }
    (output_dir / "summary_v9_final.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (output_dir / "filter_model_meta.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    logger.info("✅ Model v9 Final saved to: {}", output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
