"""
ML Prediction v10 FINAL: Full Training (2019-2026) Multi-Output Joint Regressor.

Trains 1 single joint model to predict Y = [mfe_norm, mae_norm] simultaneously,
capturing the negative correlation trade-off and trade dynamics.

Outputs:
- model_v10_final_joint.pkl
- scaler_v10_final_joint.pkl
- summary_v10_final.json
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
from train_ml_prediction_v10_walk_forward import select_and_fit_joint_regressor  # noqa: E402

BASE_REFERENCE_PRICE = 4500.0


def main() -> int:
    output_dir = PYTHON_DIR / "valuecell" / "models" / "saved" / "filter_latest"
    dataset_path = output_dir / "dataset_v9_unconstrained.csv"

    logger.info("=== ML Prediction v10 FINAL (Multi-Output Joint MFE-MAE, 2019-2026) ===")
    dataset = pd.read_csv(dataset_path)
    logger.info("Dataset loaded: {} samples ({} - {})", len(dataset), dataset["year"].min(), dataset["year"].max())

    # Dynamic Scaling
    price_ratio_safe = (dataset["entry_price"] / BASE_REFERENCE_PRICE).clip(lower=1.0 / BASE_REFERENCE_PRICE)
    dataset["mfe_target_norm"] = dataset["mfe_target"] / price_ratio_safe
    dataset["mae_target_norm"] = dataset["mae_target"] / price_ratio_safe

    model_df, numeric_cols, cat_cols = build_feature_matrix_v5(dataset)
    model_df = model_df.drop(columns=["mfe_target_norm", "mae_target_norm"], errors="ignore")

    Y_df = dataset[["mfe_target_norm", "mae_target_norm"]].copy()

    train_mask = pd.Series(True, index=dataset.index)
    n_train = int(train_mask.sum())
    logger.info("--- Final fit v10: train on all {} samples (2019-2026), no holdout ---", n_train)

    joint_model, joint_scaler, joint_features, joint_winner = select_and_fit_joint_regressor(
        model_df, Y_df, train_mask, "Joint_v10_final"
    )

    logger.info("Final Joint Winner v10: {} ({} features)", joint_winner, len(joint_features))

    # Check for news features in selected features
    news_selected = [f for f in joint_features if "news" in f or "fomc" in f]
    logger.info("Selected News Features in Joint Model: {}", news_selected)

    # Save artifacts
    joblib.dump(joint_model, output_dir / "model_v10_final_joint.pkl")
    joblib.dump(joint_scaler, output_dir / "scaler_v10_final_joint.pkl")

    summary = {
        "model_type": "regression_v10_multi_output_joint",
        "training_script": "train_ml_prediction_v10_final.py",
        "train_years": "2019-2026",
        "n_samples_total": n_train,
        "normalization": "price_ratio",
        "base_reference_price": BASE_REFERENCE_PRICE,
        "joint_winner": joint_winner,
        "joint_features": joint_features,
        "target_names": ["mfe_norm", "mae_norm"],
        "optimal_rr_threshold": 1.05,
    }
    (output_dir / "summary_v10_final.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (output_dir / "filter_model_meta.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    logger.info("✅ Model v10 Final saved to: {}", output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
