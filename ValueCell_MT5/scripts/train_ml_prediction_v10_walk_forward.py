"""
ML Prediction v10: Walk-Forward Validation (Multi-Output Joint Regressor).

Predicts joint targets Y = [mfe_norm, mae_norm] simultaneously to capture
the negative correlation and trade-off dynamics between MFE and MAE.

Uses:
- Dataset: dataset_v9_unconstrained.csv (76 features + 884 LanceDB news/geopolitical events)
- Dynamic Scaling: BaseReferencePrice = 4500.0
- Estimators: MultiOutput(Ridge), MultiOutput(RandomForest), MultiOutput(ExtraTrees), MultiOutput(XGBoost)
- Walk-Forward Folds: 2020 to 2026
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
from sklearn.preprocessing import RobustScaler
from sklearn.feature_selection import SelectKBest, f_regression
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor
from sklearn.multioutput import MultiOutputRegressor
from xgboost import XGBRegressor

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
PYTHON_DIR = PROJECT_ROOT / "python"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

from train_ml_prediction_v5_unconstrained import build_feature_matrix_v5  # noqa: E402

TEST_YEARS = [2020, 2021, 2022, 2023, 2024, 2025, 2026]
BASE_REFERENCE_PRICE = 4500.0


def select_and_fit_joint_regressor(
    X: pd.DataFrame,
    Y: pd.DataFrame,
    train_mask: pd.Series,
    target_name: str = "Joint_MFE_MAE",
) -> tuple[any, RobustScaler, list[str], str]:
    """Fit candidate multi-output regressors and select the winner via joint CV score."""
    X_train = X.loc[train_mask].copy()
    Y_train = Y.loc[train_mask].copy()

    # Pre-select top K features using combined variance / f_regression
    scaler = RobustScaler()
    X_scaled = scaler.fit_transform(X_train)

    # Feature selection candidates
    k_candidates = [15, 20, 25, 30]
    best_score = -999.0
    best_model = None
    best_features = list(X.columns)
    best_scaler = scaler
    best_name = "None"

    # Candidate multi-output models
    models = {
        "Multi_RF_d5_n200_leaf15": RandomForestRegressor(
            n_estimators=200, max_depth=5, min_samples_leaf=15, random_state=42, n_jobs=-1
        ),
        "Multi_ExtraTrees_d5_n200_leaf15": ExtraTreesRegressor(
            n_estimators=200, max_depth=5, min_samples_leaf=15, random_state=42, n_jobs=-1
        ),
        "Multi_Ridge_alpha10": MultiOutputRegressor(Ridge(alpha=10.0, random_state=42)),
        "Multi_XGB_d3_n120_lr002": MultiOutputRegressor(
            XGBRegressor(n_estimators=120, max_depth=3, learning_rate=0.02, random_state=42, n_jobs=-1)
        ),
    }

    from sklearn.base import clone
    from sklearn.model_selection import KFold
    n_splits = 5 if len(X_train) >= 200 else 3
    kf = KFold(n_splits=n_splits, shuffle=True, random_state=42)

    for k in k_candidates:
        if k > X.shape[1]:
            continue
        # Select best k features against MFE target
        selector = SelectKBest(score_func=f_regression, k=k)
        selector.fit(X_train, Y_train.iloc[:, 0])
        selected_cols = list(X.columns[selector.get_support()])

        X_tr_k = X_train[selected_cols]
        scaler_k = RobustScaler()
        X_tr_k_scaled = scaler_k.fit_transform(X_tr_k)

        for m_name, model in models.items():
            cv_r2_scores = []
            for tr_idx, val_idx in kf.split(X_tr_k_scaled):
                X_cv_tr, X_cv_val = X_tr_k_scaled[tr_idx], X_tr_k_scaled[val_idx]
                Y_cv_tr, Y_cv_val = Y_train.iloc[tr_idx].values, Y_train.iloc[val_idx].values

                m_cv = clone(model)
                m_cv.fit(X_cv_tr, Y_cv_tr)
                preds = m_cv.predict(X_cv_val)
                # Average R2 across both targets [MFE, MAE]
                r2_mfe = r2_score(Y_cv_val[:, 0], preds[:, 0])
                r2_mae = r2_score(Y_cv_val[:, 1], preds[:, 1])
                cv_r2_scores.append((r2_mfe + r2_mae) / 2.0)

            mean_cv_r2 = float(np.mean(cv_r2_scores))
            candidate_id = f"{m_name}_f{k}"

            if mean_cv_r2 > best_score:
                best_score = mean_cv_r2
                best_name = candidate_id
                best_features = selected_cols
                best_scaler = scaler_k
                # Refit fresh clone on full train fold
                fresh_fit = clone(model)
                fresh_fit.fit(X_tr_k_scaled, Y_train.values)
                best_model = fresh_fit

    logger.info("🏆 [{}] Winner: {} (Joint CV R2={:.4f})", target_name, best_name, best_score)
    return best_model, best_scaler, best_features, best_name


def main() -> int:
    output_dir = PYTHON_DIR / "valuecell" / "models" / "saved" / "filter_latest"
    dataset_path = output_dir / "dataset_v9_unconstrained.csv"

    logger.info("=== ML Prediction v10 Walk-Forward (Multi-Output Joint MFE-MAE) ===")
    dataset = pd.read_csv(dataset_path)
    logger.info("Dataset loaded: {} samples ({} - {})", len(dataset), dataset["year"].min(), dataset["year"].max())

    # Price-Ratio Dynamic Scaling
    price_ratio_safe = (dataset["entry_price"] / BASE_REFERENCE_PRICE).clip(lower=1.0 / BASE_REFERENCE_PRICE)
    dataset["mfe_target_norm"] = dataset["mfe_target"] / price_ratio_safe
    dataset["mae_target_norm"] = dataset["mae_target"] / price_ratio_safe

    model_df, numeric_cols, cat_cols = build_feature_matrix_v5(dataset)
    model_df = model_df.drop(columns=["mfe_target_norm", "mae_target_norm"], errors="ignore")

    Y_df = dataset[["mfe_target_norm", "mae_target_norm"]].copy()

    fold_summaries = []
    scored_folds = []

    for test_year in TEST_YEARS:
        train_mask = dataset["year"] < test_year
        test_mask = dataset["year"] == test_year
        n_train, n_test = int(train_mask.sum()), int(test_mask.sum())

        if n_train < 30 or n_test == 0:
            continue

        logger.info("--- Fold v10: train < {} ({} samples) -> test {} ({} samples) ---", test_year, n_train, test_year, n_test)

        # Fit Joint Multi-Output Regressor
        joint_model, joint_scaler, joint_features, joint_winner = select_and_fit_joint_regressor(
            model_df, Y_df, train_mask, f"Joint_v10_fold{test_year}"
        )

        # Predict out-of-sample
        X_test_scaled = joint_scaler.transform(model_df.loc[test_mask, joint_features])
        preds_norm = joint_model.predict(X_test_scaled)

        # Denormalize to points
        pr_test = price_ratio_safe.loc[test_mask].values
        pred_mfe = preds_norm[:, 0] * pr_test
        pred_mae = preds_norm[:, 1] * pr_test

        # Ensure valid ranges
        pred_mfe = np.maximum(0.0, pred_mfe)
        pred_mae = np.maximum(1.0, pred_mae)

        act_mfe = dataset.loc[test_mask, "mfe_target"].values
        act_mae = dataset.loc[test_mask, "mae_target"].values

        mfe_r2 = float(r2_score(act_mfe, pred_mfe))
        mae_r2 = float(r2_score(act_mae, pred_mae))

        logger.info(
            "Fold v10 {} (test N={}) -> Winner: {} | OOS MFE R2={:.3f}, MAE R2={:.3f}",
            test_year, n_test, joint_winner, mfe_r2, mae_r2
        )

        fold_summaries.append({
            "test_year": test_year,
            "train_samples": n_train,
            "test_samples": n_test,
            "joint_winner": joint_winner,
            "mfe_test_r2": mfe_r2,
            "mae_test_r2": mae_r2,
            "joint_features": joint_features,
        })

        fold_df = dataset.loc[test_mask].copy()
        fold_df["predicted_mfe"] = pred_mfe
        fold_df["predicted_mae"] = pred_mae
        fold_df["fold_test_year"] = test_year
        fold_df["fold_train_samples"] = n_train
        scored_folds.append(fold_df)

    # Save artifacts
    report_df = pd.DataFrame(fold_summaries).drop(columns=["joint_features"])
    report_path = output_dir / "walk_forward_fold_report_v10.csv"
    report_df.to_csv(report_path, index=False)

    scored_combined = pd.concat(scored_folds, axis=0).reset_index(drop=True)
    scored_path = output_dir / "scored_v10_walk_forward.csv"
    scored_combined.to_csv(scored_path, index=False)

    summary = {
        "model_type": "regression_v10_multi_output_joint",
        "training_script": "train_ml_prediction_v10_walk_forward.py",
        "normalization": "price_ratio",
        "base_reference_price": BASE_REFERENCE_PRICE,
        "n_samples_total": len(dataset),
        "folds": fold_summaries,
    }
    summary_path = output_dir / "summary_v10.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    logger.info("✅ Walk-Forward v10 complete! Summary saved to: {}", summary_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
