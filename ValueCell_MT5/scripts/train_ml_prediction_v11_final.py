"""
ML Prediction v11 FINAL: Full Training (2019-2026) Planned R:R & Reject Reason Aware.

Trains final production MFE and MAE models with:
- planned_rr
- reject_group dummies
- 884 LanceDB news/geopolitical events
- Price-Ratio Normalization (4500.0)

Outputs:
- model_v11_final_mfe.pkl
- scaler_v11_final_mfe.pkl
- model_v11_final_mae.pkl
- scaler_v11_final_mae.pkl
- summary_v11_final.json
- filter_model_meta.json (production active meta)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import pandas as pd
import numpy as np
from loguru import logger

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
PYTHON_DIR = PROJECT_ROOT / "python"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

from train_ml_prediction_v5_unconstrained import build_feature_matrix_v5  # noqa: E402
from train_ml_prediction_v11_walk_forward import select_and_fit_v11_regressor  # noqa: E402

BASE_REFERENCE_PRICE = 4500.0


def main() -> int:
    output_dir = PYTHON_DIR / "valuecell" / "models" / "saved" / "filter_latest"
    dataset_path = output_dir / "dataset_v11_unconstrained.csv"

    logger.info("=== ML Prediction v11 FINAL (Full Dataset 2019-2026, Planned R:R Aware) ===")
    dataset = pd.read_csv(dataset_path)
    logger.info("Dataset loaded: {} samples ({} - {})", len(dataset), dataset["year"].min(), dataset["year"].max())

    price_ratio_safe = (dataset["entry_price"] / BASE_REFERENCE_PRICE).clip(lower=1.0 / BASE_REFERENCE_PRICE)
    dataset["mfe_target_norm"] = dataset["mfe_target"] / price_ratio_safe
    dataset["mae_target_norm"] = dataset["mae_target"] / price_ratio_safe

    model_df, numeric_cols, cat_cols = build_feature_matrix_v5(dataset)
    model_df = model_df.drop(columns=["mfe_target_norm", "mae_target_norm"], errors="ignore")

    # Add v11 specific features into model_df
    v11_cols = [
        "planned_rr", "init_risk_points", "init_reward_points",
        "reject_group_NONE", "reject_group_TREND_FILTER_EMA",
        "reject_group_CYCLE_LIMIT", "reject_group_UNCONSTRAINED_SIM"
    ]
    for col in v11_cols:
        if col in dataset.columns:
            model_df[col] = dataset[col].astype(float)

    train_mask = pd.Series(True, index=dataset.index)
    n_train = int(train_mask.sum())
    logger.info("--- Final fit v11: train on all {} samples (2019-2026), no holdout ---", n_train)

    mfe_model, mfe_scaler, mfe_features, mfe_winner = select_and_fit_v11_regressor(
        model_df, dataset["mfe_target_norm"], train_mask, "MFEnorm_v11_final"
    )
    logger.info("Final MFE winner v11: {} ({} features)", mfe_winner, len(mfe_features))

    mae_model, mae_scaler, mae_features, mae_winner = select_and_fit_v11_regressor(
        model_df, dataset["mae_target_norm"], train_mask, "MAEnorm_v11_final"
    )
    logger.info("Final MAE winner v11: {} ({} features)", mae_winner, len(mae_features))

    # Check for v11 features in selected features
    mfe_v11_sel = [f for f in mfe_features if "planned" in f or "reject" in f or "news" in f or "fomc" in f]
    mae_v11_sel = [f for f in mae_features if "planned" in f or "reject" in f or "news" in f or "fomc" in f]
    logger.info("Selected v11/News Features in MFE: {}", mfe_v11_sel)
    logger.info("Selected v11/News Features in MAE: {}", mae_v11_sel)

    # Save artifacts
    joblib.dump(mfe_model, output_dir / "model_v11_final_mfe.pkl")
    joblib.dump(mfe_scaler, output_dir / "scaler_v11_final_mfe.pkl")
    joblib.dump(mae_model, output_dir / "model_v11_final_mae.pkl")
    joblib.dump(mae_scaler, output_dir / "scaler_v11_final_mae.pkl")

    summary = {
        "model_type": "regression_v11_planned_rr_and_reject_aware",
        "training_script": "train_ml_prediction_v11_final.py",
        "train_years": "2019-2026",
        "n_samples_total": n_train,
        "normalization": "price_ratio",
        "base_reference_price": BASE_REFERENCE_PRICE,
        "mfe_winner": mfe_winner,
        "mae_winner": mae_winner,
        "mfe_features": mfe_features,
        "mae_features": mae_features,
        "optimal_rr_threshold": 1.05,
    }
    (output_dir / "summary_v11_final.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (output_dir / "filter_model_meta.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    logger.info("✅ Model v11 Final saved to: {}", output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
