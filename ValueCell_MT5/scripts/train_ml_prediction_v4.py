"""
Train/evaluate ML Prediction v4 from Backtest_result signal candidates.

v4 keeps the v3 no-leakage dataset builder, then improves optimization:
- select model by validation trading performance, not only CV AUC;
- optimize a fine-grained acceptance threshold using actual Net_Profit;
- compare several feature-count/model combinations with a faster search;
- write JSON with finite values only, so reports are standard-parseable.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from loguru import logger
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.preprocessing import StandardScaler

try:
    from xgboost import XGBClassifier
except Exception as exc:
    raise RuntimeError("xgboost is required for v4 training") from exc

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from train_ml_prediction_v3 import (  # noqa: E402
    PYTHON_DIR,
    REPO_ROOT,
    build_dataset,
    build_feature_matrix,
)


THRESHOLDS = [round(x, 2) for x in np.arange(0.30, 0.951, 0.01)]
FEATURE_COUNTS = [12, 16, 20, 24, 30, 40]


def sanitize_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): sanitize_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize_json(v) for v in value]
    if isinstance(value, tuple):
        return [sanitize_json(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        v = float(value)
        return v if np.isfinite(v) else None
    return value


def classification_metrics(y_true: pd.Series, prob: np.ndarray, threshold: float) -> dict[str, float]:
    if len(y_true) == 0:
        return {}
    pred = (prob >= threshold).astype(int)
    metrics = {
        "threshold": threshold,
        "accuracy": accuracy_score(y_true, pred),
        "precision": precision_score(y_true, pred, zero_division=0),
        "recall": recall_score(y_true, pred, zero_division=0),
        "f1": f1_score(y_true, pred, zero_division=0),
    }
    metrics["auc"] = roc_auc_score(y_true, prob) if y_true.nunique() > 1 else 0.0
    return {k: float(v) for k, v in metrics.items()}


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


def accepted_trading_metrics(df: pd.DataFrame, threshold: float, split_name: str) -> dict[str, Any]:
    accepted = df if threshold <= 0 else df[df["probability"] >= threshold]
    returns = accepted["actual_net_profit"].astype(float) if not accepted.empty else pd.Series(dtype=float)
    labels = accepted["label_win"].astype(int) if not accepted.empty else pd.Series(dtype=int)
    candidates = len(df)
    return {
        "split": split_name,
        "threshold": float(threshold),
        "candidates": int(candidates),
        "accepted": int(len(accepted)),
        "accepted_rate": float(len(accepted) / candidates) if candidates else 0.0,
        "winrate": float(labels.mean()) if len(labels) else 0.0,
        "net_profit": float(returns.sum()) if len(returns) else 0.0,
        "avg_net_profit": float(returns.mean()) if len(returns) else 0.0,
        "profit_factor": profit_factor(returns) if len(returns) else 0.0,
        "max_drawdown": max_drawdown(returns) if len(returns) else 0.0,
        "expectancy": float(returns.mean()) if len(returns) else 0.0,
    }


def threshold_report(df: pd.DataFrame, split_name: str) -> pd.DataFrame:
    rows = [accepted_trading_metrics(df, 0.0, split_name)]
    rows.extend(accepted_trading_metrics(df, threshold, split_name) for threshold in THRESHOLDS)
    return pd.DataFrame(rows)


def choose_threshold(report: pd.DataFrame, min_accepted: int) -> dict[str, Any]:
    candidates = report[(report["threshold"] > 0) & (report["accepted"] >= min_accepted)].copy()
    if candidates.empty:
        candidates = report[(report["threshold"] > 0) & (report["accepted"] > 0)].copy()
    if candidates.empty:
        return report.iloc[0].to_dict() if not report.empty else {}
    candidates["profit_factor_rank"] = candidates["profit_factor"].replace(np.inf, 1e9)
    candidates = candidates.sort_values(
        ["net_profit", "profit_factor_rank", "winrate", "accepted"],
        ascending=[False, False, False, False],
    )
    return candidates.iloc[0].drop(labels=["profit_factor_rank"], errors="ignore").to_dict()


def make_model_candidates(scale_pos_weight: float) -> list[tuple[str, Any]]:
    xgb_common = dict(
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=42,
        n_jobs=-1,
        scale_pos_weight=scale_pos_weight,
    )
    return [
        (
            "XGBoost_d2_n120_lr003",
            XGBClassifier(
                n_estimators=120,
                max_depth=2,
                learning_rate=0.03,
                subsample=0.80,
                colsample_bytree=0.80,
                min_child_weight=6,
                gamma=0.1,
                reg_alpha=0.5,
                reg_lambda=2.0,
                **xgb_common,
            ),
        ),
        (
            "XGBoost_d3_n160_lr002",
            XGBClassifier(
                n_estimators=160,
                max_depth=3,
                learning_rate=0.02,
                subsample=0.75,
                colsample_bytree=0.70,
                min_child_weight=8,
                gamma=0.2,
                reg_alpha=0.8,
                reg_lambda=2.5,
                **xgb_common,
            ),
        ),
        (
            "LogisticRegression_C001",
            LogisticRegression(C=0.01, max_iter=1000, random_state=42, class_weight="balanced"),
        ),
        (
            "LogisticRegression_C003",
            LogisticRegression(C=0.03, max_iter=1000, random_state=42, class_weight="balanced"),
        ),
        (
            "RandomForest_d3_n220_leaf10",
            RandomForestClassifier(
                max_depth=3,
                n_estimators=220,
                min_samples_leaf=10,
                max_features="sqrt",
                random_state=42,
                class_weight="balanced",
                n_jobs=-1,
            ),
        ),
        (
            "RandomForest_d4_n220_leaf12",
            RandomForestClassifier(
                max_depth=4,
                n_estimators=220,
                min_samples_leaf=12,
                max_features="sqrt",
                random_state=42,
                class_weight="balanced",
                n_jobs=-1,
            ),
        ),
    ]


def rank_features(model_df: pd.DataFrame, train_mask: pd.Series, y_train: pd.Series, scale_pos_weight: float) -> list[str]:
    scaler = StandardScaler()
    x_train = scaler.fit_transform(model_df.loc[train_mask])
    ranker = XGBClassifier(
        n_estimators=180,
        max_depth=3,
        learning_rate=0.01,
        subsample=0.75,
        colsample_bytree=0.70,
        min_child_weight=8,
        gamma=0.1,
        reg_alpha=0.3,
        reg_lambda=1.5,
        scale_pos_weight=scale_pos_weight,
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=42,
        n_jobs=-1,
    )
    ranker.fit(x_train, y_train, verbose=False)
    importance = dict(zip(model_df.columns, ranker.feature_importances_))
    return [k for k, _ in sorted(importance.items(), key=lambda item: item[1], reverse=True)]


def candidate_score(row: dict[str, Any]) -> tuple[float, float, float, int, int]:
    pf = row.get("profit_factor", 0.0)
    pf_rank = 1e9 if pf == float("inf") else float(pf or 0.0)
    return (
        float(row.get("net_profit", 0.0)),
        pf_rank,
        float(row.get("winrate", 0.0)),
        int(row.get("accepted", 0)),
        -int(row.get("feature_count", 0)),
    )


def train_and_evaluate(
    dataset: pd.DataFrame,
) -> tuple[Any, StandardScaler, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    model_df, _, _ = build_feature_matrix(dataset)

    train_mask = dataset["year"] <= 2024
    val_mask = dataset["year"] == 2025
    test_mask = dataset["year"] >= 2026

    y_train = dataset.loc[train_mask, "label_win"].astype(int)
    counts = y_train.value_counts()
    scale_pos_weight = float(counts.get(0, 1) / counts.get(1, 1))
    logger.info("Train label distribution: {}", counts.to_dict())
    logger.info("scale_pos_weight={:.3f}", scale_pos_weight)

    ranked_features = rank_features(model_df, train_mask, y_train, scale_pos_weight)
    logger.info("Top ranked features: {}", ranked_features[:20])

    min_validation_accepted = max(5, int(np.ceil(int(val_mask.sum()) * 0.10)))
    model_candidates = make_model_candidates(scale_pos_weight)
    selection_rows: list[dict[str, Any]] = []
    best: dict[str, Any] | None = None

    for feature_count in FEATURE_COUNTS:
        feature_columns = ranked_features[: min(feature_count, len(ranked_features))]
        feature_df = model_df[feature_columns]
        scaler_probe = StandardScaler()
        x_train = scaler_probe.fit_transform(feature_df.loc[train_mask])
        x_all = scaler_probe.transform(feature_df)

        for model_name, model in model_candidates:
            model.fit(x_train, y_train)
            scored_probe = dataset.copy()
            scored_probe["probability"] = model.predict_proba(x_all)[:, 1]
            val_report = threshold_report(scored_probe.loc[val_mask], "validation_2025")
            best_threshold = choose_threshold(val_report, min_validation_accepted)
            row = {
                "model_name": model_name,
                "feature_count": int(len(feature_columns)),
                "features": "|".join(feature_columns),
                **best_threshold,
            }
            selection_rows.append(row)
            row_score = candidate_score(row)
            if best is None or row_score > best["score"]:
                best = {
                    "score": row_score,
                    "model_name": model_name,
                    "model": model,
                    "feature_columns": feature_columns,
                    "threshold": float(row.get("threshold", 0.5)),
                    "selection_row": row,
                }

    if best is None:
        raise RuntimeError("No v4 candidate could be selected.")

    feature_columns = best["feature_columns"]
    feature_df = model_df[feature_columns]
    scaler = StandardScaler()
    x_train = scaler.fit_transform(feature_df.loc[train_mask])
    x_all = scaler.transform(feature_df)

    model = best["model"]
    model.fit(x_train, y_train)

    selected_threshold = float(best["threshold"])
    scored = dataset.copy()
    scored["probability"] = model.predict_proba(x_all)[:, 1]
    scored["accepted_v4"] = scored["probability"] >= selected_threshold

    split_masks = {
        "train_2020_2024": train_mask,
        "validation_2025": val_mask,
        "test_2026": test_mask,
        "all": dataset["year"] >= 2020,
    }
    threshold_reports = pd.concat(
        [threshold_report(scored.loc[mask], split_name) for split_name, mask in split_masks.items() if mask.any()],
        ignore_index=True,
    )
    selected_threshold_metrics = {
        split_name: accepted_trading_metrics(scored.loc[mask], selected_threshold, split_name)
        for split_name, mask in split_masks.items()
        if mask.any()
    }

    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_auc = cross_val_score(model, x_train, y_train, cv=skf, scoring="roc_auc")
    cv_f1 = cross_val_score(model, x_train, y_train, cv=skf, scoring="f1")

    metrics: dict[str, Any] = {
        "feature_columns": list(feature_columns),
        "n_features": len(feature_columns),
        "winner_name": best["model_name"],
        "selected_threshold": selected_threshold,
        "selection_basis": "validation_2025_net_profit_then_profit_factor_then_winrate",
        "min_validation_accepted": min_validation_accepted,
        "best_validation_threshold": best["selection_row"],
        "selected_threshold_metrics": selected_threshold_metrics,
        "cv_auc_mean": float(cv_auc.mean()),
        "cv_auc_std": float(cv_auc.std()),
        "cv_f1_mean": float(cv_f1.mean()),
        "cv_f1_std": float(cv_f1.std()),
        "train": classification_metrics(
            dataset.loc[train_mask, "label_win"].astype(int),
            scored.loc[train_mask, "probability"].to_numpy(),
            selected_threshold,
        ),
        "validation": classification_metrics(
            dataset.loc[val_mask, "label_win"].astype(int),
            scored.loc[val_mask, "probability"].to_numpy(),
            selected_threshold,
        ) if val_mask.any() else {},
        "test": classification_metrics(
            dataset.loc[test_mask, "label_win"].astype(int),
            scored.loc[test_mask, "probability"].to_numpy(),
            selected_threshold,
        ) if test_mask.any() else {},
        "rows": {
            "train": int(train_mask.sum()),
            "validation": int(val_mask.sum()),
            "test": int(test_mask.sum()),
            "total": int(len(dataset)),
        },
    }

    if hasattr(model, "feature_importances_"):
        raw_imp = dict(zip(feature_columns, model.feature_importances_))
    elif hasattr(model, "coef_"):
        raw_imp = dict(zip(feature_columns, np.abs(model.coef_[0])))
    else:
        raw_imp = {col: 1.0 for col in feature_columns}
    metrics["top_features"] = {
        k: float(v) for k, v in sorted(raw_imp.items(), key=lambda item: item[1], reverse=True)
    }
    try:
        model.feature_names_in_ = np.array(feature_columns, dtype=object)
    except Exception:
        pass

    logger.info(
        "Winning v4 model: {} | threshold={:.2f} | validation net={:.2f} | accepted={} | winrate={:.2%}",
        metrics["winner_name"],
        selected_threshold,
        metrics["best_validation_threshold"].get("net_profit", 0.0),
        metrics["best_validation_threshold"].get("accepted", 0),
        metrics["best_validation_threshold"].get("winrate", 0.0),
    )

    return model, scaler, scored, threshold_reports, pd.DataFrame(selection_rows), metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backtest-dir", type=Path, default=REPO_ROOT / "Backtest_result")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PYTHON_DIR / "valuecell" / "models" / "experiments" / "ml_prediction_v4",
    )
    parser.add_argument(
        "--save-to-filter-latest",
        action="store_true",
        help="Also copy best model to filter_latest/ (requires explicit flag)",
    )
    args = parser.parse_args()

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = args.output_dir / stamp
    run_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=== ML Prediction v4 Training ===")
    logger.info("Backtest dir: {}", args.backtest_dir)
    logger.info("Output dir:   {}", run_dir)

    dataset, info = build_dataset(args.backtest_dir)
    if dataset.empty:
        raise RuntimeError("No v4 samples built.")

    logger.info("Dataset built: {} samples | labels={}", len(dataset), dataset["label_win"].value_counts().to_dict())
    logger.info("Label sources: {}", dataset["label_source"].value_counts().to_dict())
    logger.info("Skipped: {}", info["skipped"])

    dataset_path = run_dir / "dataset_v4.csv"
    dataset.to_csv(dataset_path, index=False)

    model, scaler, scored, threshold_reports, selection_report, metrics = train_and_evaluate(dataset)

    scored_path = run_dir / "scored_v4.csv"
    scored.to_csv(scored_path, index=False)

    report_path = run_dir / "threshold_report_v4.csv"
    threshold_reports.to_csv(report_path, index=False)

    selection_path = run_dir / "model_selection_v4.csv"
    selection_report.to_csv(selection_path, index=False)

    model_path = run_dir / "model_v4.pkl"
    scaler_path = run_dir / "scaler_v4.pkl"
    joblib.dump(model, model_path)
    joblib.dump(scaler, scaler_path)

    summary = {
        "version": f"v4_{stamp}",
        "created_at": datetime.now().isoformat(),
        "model_type": type(model).__name__,
        "winner_name": metrics["winner_name"],
        "training_script": "train_ml_prediction_v4.py",
        "source_backtest_dir": str(args.backtest_dir.resolve()),
        "run_dir": str(run_dir.resolve()),
        "dataset_path": str(dataset_path.resolve()),
        "n_samples_total": len(dataset),
        "label_counts": {str(k): int(v) for k, v in dataset["label_win"].value_counts().items()},
        "label_sources": {str(k): int(v) for k, v in dataset["label_source"].value_counts().items()},
        "source_counts": {str(k): int(v) for k, v in dataset["source"].value_counts().items()},
        "skipped": info["skipped"],
        "metrics": metrics,
    }
    summary_path = run_dir / "summary_v4.json"
    summary_path.write_text(json.dumps(sanitize_json(summary), indent=2, allow_nan=False), encoding="utf-8")

    logger.info("=== v4 RESULTS ===")
    logger.info("Total samples  : {}", len(dataset))
    logger.info("Winning Model  : {}", metrics["winner_name"])
    logger.info("Threshold      : {:.2f}", metrics["selected_threshold"])
    logger.info("Val   AUC      : {:.4f}", metrics.get("validation", {}).get("auc", 0))
    logger.info("Test  AUC      : {:.4f}", metrics.get("test", {}).get("auc", 0))
    logger.info("Val trading    : {}", metrics["selected_threshold_metrics"].get("validation_2025", {}))
    logger.info("Test trading   : {}", metrics["selected_threshold_metrics"].get("test_2026", {}))
    logger.info("Summary saved  : {}", summary_path)

    if args.save_to_filter_latest:
        latest_dir = PYTHON_DIR / "valuecell" / "models" / "saved" / "filter_latest"
        if latest_dir.exists():
            backup = latest_dir.parent / f"filter_latest_backup_{stamp}"
            shutil.copytree(latest_dir, backup)
            logger.info("Backed up filter_latest to {}", backup)
        latest_dir.mkdir(parents=True, exist_ok=True)

        meta = {
            "version": stamp,
            "trained_at": datetime.now().isoformat(),
            "model_type": type(model).__name__,
            "winner_name": metrics["winner_name"],
            "training_version": "v4",
            "n_features": len(metrics["feature_columns"]),
            "feature_names": metrics["feature_columns"],
            "threshold": float(metrics["selected_threshold"]),
            "optimal_threshold": float(metrics["selected_threshold"]),
            "train_rows": int(metrics["rows"]["train"]),
            "label_counts": summary["label_counts"],
            "source_backtest_dir": str(args.backtest_dir.resolve()),
            "train_accuracy": metrics["train"].get("accuracy", 0),
            "train_precision": metrics["train"].get("precision", 0),
            "train_recall": metrics["train"].get("recall", 0),
            "train_f1": metrics["train"].get("f1", 0),
            "train_auc": metrics["train"].get("auc", 0),
            "test_accuracy": metrics.get("test", {}).get("accuracy", 0),
            "test_precision": metrics.get("test", {}).get("precision", 0),
            "test_recall": metrics.get("test", {}).get("recall", 0),
            "test_f1": metrics.get("test", {}).get("f1", 0),
            "test_auc": metrics.get("test", {}).get("auc", 0),
            "selected_threshold_metrics": metrics["selected_threshold_metrics"],
            "top_features": metrics.get("top_features", {}),
        }
        shutil.copy(model_path, latest_dir / "filter_model_xgb.pkl")
        shutil.copy(scaler_path, latest_dir / "filter_scaler.pkl")
        (latest_dir / "filter_model_meta.json").write_text(
            json.dumps(sanitize_json(meta), indent=2, allow_nan=False),
            encoding="utf-8",
        )
        logger.info("Saved v4 model to filter_latest/")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
