"""
Final (no-holdout) v8 model: same ATR-normalized methodology validated by the
walk-forward folds (train_ml_prediction_v8_walk_forward_normalized.py), but
trained on the entire 2017-2026 dataset with no year held out.

This model cannot be scored against a held-out test year (there isn't one
left) -- it borrows its credibility from the walk-forward validation, which
already proved the ATR-normalized approach generalizes across 9 different
fold windows. The only way to genuinely validate THIS specific model is with
data from a year it never trained on (e.g. 2016, once available).

    Final: train on 2017-2026 (2384 samples) -> no test split
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
)

# Price-Ratio Dynamic Scaling (EA Dev_Bot_v11_Gold: BaseReferencePrice=4500).
# Target dinormalisasi ke basis harga acuan 4500, konsisten dengan scaling SL/TP EA.
BASE_REFERENCE_PRICE = 4500.0


def main() -> int:
    output_dir = PYTHON_DIR / "valuecell" / "models" / "saved" / "filter_latest"
    dataset_path = output_dir / "dataset_v5_unconstrained.csv"

    logger.info("=== ML Prediction v8 FINAL (no held-out year) ===")
    dataset = pd.read_csv(dataset_path)
    logger.info("Dataset loaded: {} samples ({} - {})", len(dataset), dataset["year"].min(), dataset["year"].max())

    atr_safe = dataset["entry_price"].clip(lower=1.0) / BASE_REFERENCE_PRICE
    dataset["mfe_target_norm"] = dataset["mfe_target"] / atr_safe
    dataset["mae_target_norm"] = dataset["mae_target"] / atr_safe

    model_df, _, _ = build_feature_matrix_v5(dataset)
    model_df = model_df.drop(columns=["mfe_target_norm", "mae_target_norm"], errors="ignore")

    # No held-out split: every row is training data.
    train_mask = pd.Series(True, index=dataset.index)
    n_train = int(train_mask.sum())
    logger.info("--- Final fit: train on all {} samples (2017-2026), no test split ---", n_train)

    y_mfe_norm = dataset.loc[train_mask, "mfe_target_norm"]
    mfe_model, mfe_scaler, mfe_features, mfe_winner = select_and_fit_regressor(
        model_df, y_mfe_norm, train_mask, "MFEnorm_final"
    )

    y_mae_norm = dataset.loc[train_mask, "mae_target_norm"]
    mae_model, mae_scaler, mae_features, mae_winner = select_and_fit_regressor(
        model_df, y_mae_norm, train_mask, "MAEnorm_final"
    )

    joblib.dump(mfe_model, output_dir / "model_v8_final_mfe.pkl")
    joblib.dump(mfe_scaler, output_dir / "scaler_v8_final_mfe.pkl")
    joblib.dump(mae_model, output_dir / "model_v8_final_mae.pkl")
    joblib.dump(mae_scaler, output_dir / "scaler_v8_final_mae.pkl")

    # ponytail: inference agent memuat foldfinal (production_fold="final"), bukan
    # model_v8_final_* — tanpa copy ini agent diam-diam memakai model stale.
    import shutil
    for src, dst in [
        ("model_v8_final_mfe.pkl", "model_v8_foldfinal_mfe.pkl"),
        ("scaler_v8_final_mfe.pkl", "scaler_v8_foldfinal_mfe.pkl"),
        ("model_v8_final_mae.pkl", "model_v8_foldfinal_mae.pkl"),
        ("scaler_v8_final_mae.pkl", "scaler_v8_foldfinal_mae.pkl"),
    ]:
        shutil.copyfile(output_dir / src, output_dir / dst)
    logger.info("Synced model_v8_final_* -> model_v8_foldfinal_* (inference path)")

    summary = {
        "model_type": "regression_v8_final_price_ratio_normalized",
        "training_script": "train_ml_prediction_v8_final.py",
        "train_years": f"{int(dataset['year'].min())}-{int(dataset['year'].max())}",
        "n_samples_total": n_train,
        "note": (
            "No held-out test year -- every sample (2017-2026) was used for training. "
            "This model's validity rests on the walk-forward folds (summary_v8.json) "
            "proving the price-ratio-normalized approach generalizes; it has not itself been "
            "scored against unseen data. Blind-test with a year outside 2017-2026 "
            "(e.g. 2016) once available."
        ),
        "normalization": "price_ratio",
        "base_reference_price": BASE_REFERENCE_PRICE,
        "mfe_winner": mfe_winner,
        "mfe_features": mfe_features,
        "mae_winner": mae_winner,
        "mae_features": mae_features,
    }
    (output_dir / "summary_v8_final.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    logger.info("=== v8 FINAL SUMMARY ===")
    logger.info("MFE winner: {} ({} features)", mfe_winner, len(mfe_features))
    logger.info("MAE winner: {} ({} features)", mae_winner, len(mae_features))
    logger.info("Models saved as model_v8_final_mfe.pkl / model_v8_final_mae.pkl")

    return 0


if __name__ == "__main__":
    sys.exit(main())
