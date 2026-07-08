"""
Retrain ML Prediction Agent from Backtest_result CSV files.

Builds a supervised dataset from executed backtest trades:
Backtest trade entry context -> WIN/LOSS label from Net_Profit.

Output is compatible with MLPredictionAgent:
- filter_model_xgb.pkl
- filter_scaler.pkl
- filter_model_meta.json
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
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.preprocessing import StandardScaler

try:
    from xgboost import XGBClassifier
except Exception:  # pragma: no cover - optional dependency fallback
    XGBClassifier = None

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_ROOT.parent
PYTHON_DIR = PROJECT_ROOT / "python"

if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

from valuecell.models.feature_engineer import FeatureEngineer  # noqa: E402


def parse_time(value: Any) -> pd.Timestamp:
    return pd.to_datetime(value, format="%Y.%m.%d %H:%M:%S", errors="coerce")


def normalize_market_df(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    df["time"] = df["time"].map(parse_time)
    df = df.dropna(subset=["time"]).sort_values("time").reset_index(drop=True)
    return df


def load_structure_events(path: Path) -> pd.DataFrame:
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    header_idx = 0
    for idx, line in enumerate(lines):
        if line.startswith("Type,Direction/Action"):
            header_idx = idx
            break

    df = pd.read_csv(path, skiprows=header_idx)
    df.columns = [c.strip() for c in df.columns]
    df["time"] = df["Time"].map(parse_time)
    df = df.dropna(subset=["time"]).sort_values("time").reset_index(drop=True)
    return df


def event_type(row: pd.Series) -> str:
    raw_type = str(row.get("Type", "")).strip().upper()
    raw_direction = str(row.get("Direction/Action", "")).strip().upper()

    if "BULL" in raw_direction:
        direction = "BULLISH"
    elif "BEAR" in raw_direction:
        direction = "BEARISH"
    elif raw_type == "HH":
        direction = "BULLISH"
    elif raw_type == "LL":
        direction = "BEARISH"
    else:
        direction = "NEUTRAL"

    if "BOS" in raw_type:
        kind = "BOS"
    elif "CHOCH" in raw_type:
        kind = "CHOCH"
    else:
        kind = raw_type

    return f"{kind}_{direction}"


def row_to_event(row: pd.Series) -> dict[str, Any]:
    return {
        "type": event_type(row),
        "price": float(row.get("Price", 0.0) or 0.0),
        "time": row["time"].to_pydatetime(),
    }


def last_rows_at_or_before(df: pd.DataFrame, when: pd.Timestamp, count: int) -> pd.DataFrame:
    idx = np.searchsorted(df["time"].values, np.datetime64(when), side="right")
    return df.iloc[max(0, idx - count) : idx].copy()


def current_bar_at_or_before(df: pd.DataFrame, when: pd.Timestamp) -> dict[str, Any] | None:
    rows = last_rows_at_or_before(df, when, 1)
    if rows.empty:
        return None

    row = rows.iloc[-1]
    return {
        "time": row["time"].to_pydatetime(),
        "open": float(row["open"]),
        "high": float(row["high"]),
        "low": float(row["low"]),
        "close": float(row["close"]),
        "volume": float(row.get("volume", 0.0) or 0.0),
    }


def build_dataset(backtest_dir: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    engineer = FeatureEngineer()
    rows: list[dict[str, Any]] = []
    years: list[str] = []
    skipped: dict[str, int] = {
        "missing_files": 0,
        "non_executed": 0,
        "bad_time": 0,
        "missing_bar": 0,
    }

    for results_path in sorted(backtest_dir.glob("Backtest_Results_XAUUSD_*.csv")):
        suffix = results_path.stem.replace("Backtest_Results_XAUUSD_", "")
        years.append(suffix)

        structure_path = backtest_dir / f"LLHHBOSData_XAUUSD_{suffix}.csv"
        m15_path = backtest_dir / f"MarketData_XAUUSD_M15_{suffix}.csv"
        h1_path = backtest_dir / f"MarketData_XAUUSD_H1_{suffix}.csv"

        if not structure_path.exists() or not m15_path.exists() or not h1_path.exists():
            logger.warning("Skipping {}: missing structure/M15/H1 CSV", suffix)
            skipped["missing_files"] += 1
            continue

        trades = pd.read_csv(results_path)
        trades.columns = [c.strip() for c in trades.columns]
        trades["entry_time"] = trades["EntryTime"].map(parse_time)

        structures = load_structure_events(structure_path)
        m15 = normalize_market_df(m15_path)
        h1 = normalize_market_df(h1_path)

        for _, trade in trades.iterrows():
            if str(trade.get("Status", "")).upper() != "EXECUTED":
                skipped["non_executed"] += 1
                continue

            entry_time = trade["entry_time"]
            if pd.isna(entry_time):
                skipped["bad_time"] += 1
                continue

            current_bar = current_bar_at_or_before(m15, entry_time)
            if current_bar is None:
                skipped["missing_bar"] += 1
                continue

            recent_structures = structures[structures["time"] <= entry_time].tail(50)
            structure_events = [row_to_event(r) for _, r in recent_structures.iterrows()]
            h1_history = last_rows_at_or_before(h1, entry_time, 220)
            m15_history = last_rows_at_or_before(m15, entry_time, 220)

            features = engineer.extract_features(
                current_bar=current_bar,
                structure_events=structure_events,
                h1_data=h1_history,
                m15_history=m15_history,
            )

            net_profit = float(trade.get("Net_Profit", 0.0) or 0.0)
            sample = {
                "source_year": suffix,
                "ticket": trade.get("Ticket"),
                "entry_time": entry_time,
                "symbol": trade.get("Symbol", "XAUUSD"),
                "timeframe": trade.get("Timeframe", "M15"),
                "structure_signal": trade.get("Type", "UNKNOWN"),
                "net_profit": net_profit,
                "label_win": 1 if net_profit > 0 else 0,
            }
            sample.update({name: float(features[name]) for name in engineer.feature_names})
            rows.append(sample)

        logger.info("Loaded {} training samples from {}", len(rows), suffix)

    dataset = pd.DataFrame(rows)
    info = {
        "years": years,
        "skipped": skipped,
        "feature_names": engineer.feature_names,
    }
    return dataset, info


def metric_dict(y_true: np.ndarray, y_pred: np.ndarray, y_prob: np.ndarray) -> dict[str, float]:
    metrics = {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
    }
    if len(set(y_true)) > 1:
        metrics["auc"] = roc_auc_score(y_true, y_prob)
    else:
        metrics["auc"] = 0.0
    return {k: float(v) for k, v in metrics.items()}


def backup_existing_model(output_dir: Path, stamp: str) -> Path | None:
    if not output_dir.exists() or not any(output_dir.iterdir()):
        return None

    backup_dir = output_dir.parent / f"{output_dir.name}_backup_{stamp}"
    shutil.copytree(output_dir, backup_dir)
    return backup_dir


def make_model(y: pd.Series, random_state: int) -> Any:
    if XGBClassifier is not None:
        counts = y.value_counts()
        scale_pos_weight = 1.0
        if 0 in counts and 1 in counts and counts[1] > 0:
            scale_pos_weight = float(counts[0] / counts[1])

        return XGBClassifier(
            n_estimators=350,
            max_depth=4,
            learning_rate=0.04,
            subsample=0.85,
            colsample_bytree=0.85,
            objective="binary:logistic",
            eval_metric="logloss",
            scale_pos_weight=scale_pos_weight,
            random_state=random_state,
            n_jobs=-1,
        )

    return RandomForestClassifier(
        n_estimators=500,
        max_depth=8,
        min_samples_leaf=3,
        class_weight="balanced",
        random_state=random_state,
        n_jobs=-1,
    )


def train(dataset: pd.DataFrame, feature_names: list[str], random_state: int) -> dict[str, Any]:
    x = dataset[feature_names].astype(float).replace([np.inf, -np.inf], 0.0).fillna(0.0)
    y = dataset["label_win"].astype(int)

    if y.nunique() < 2:
        raise RuntimeError("Training dataset has one class only; need WIN and LOSS samples.")

    scaler = StandardScaler()
    x_scaled = scaler.fit_transform(x)

    model = make_model(y, random_state)

    stratify = y if y.value_counts().min() >= 2 else None
    x_train, x_test, y_train, y_test = train_test_split(
        x_scaled,
        y,
        test_size=0.2,
        random_state=random_state,
        stratify=stratify,
    )

    model.fit(x_train, y_train)

    train_prob = model.predict_proba(x_train)[:, 1]
    train_pred = (train_prob >= 0.5).astype(int)
    test_prob = model.predict_proba(x_test)[:, 1]
    test_pred = (test_prob >= 0.5).astype(int)

    class_counts = y.value_counts().to_dict()
    cv_f1 = []
    cv_accuracy = []
    min_class = int(y.value_counts().min())
    if min_class >= 2:
        folds = min(5, min_class)
        cv = StratifiedKFold(n_splits=folds, shuffle=True, random_state=random_state)
        cv_f1 = cross_val_score(model, x_scaled, y, cv=cv, scoring="f1").tolist()
        cv_accuracy = cross_val_score(model, x_scaled, y, cv=cv, scoring="accuracy").tolist()

    model.fit(x_scaled, y)

    importances = {
        name: float(value)
        for name, value in zip(feature_names, model.feature_importances_, strict=True)
    }
    importances = dict(sorted(importances.items(), key=lambda item: item[1], reverse=True))

    return {
        "model": model,
        "scaler": scaler,
        "train_metrics": metric_dict(y_train.to_numpy(), train_pred, train_prob),
        "test_metrics": metric_dict(y_test.to_numpy(), test_pred, test_prob),
        "cv_f1": cv_f1,
        "cv_accuracy": cv_accuracy,
        "class_counts": {str(k): int(v) for k, v in class_counts.items()},
        "feature_importance": importances,
        "model_type": type(model).__name__,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backtest-dir", type=Path, default=REPO_ROOT / "Backtest_result")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PYTHON_DIR / "valuecell" / "models" / "saved" / "filter_latest",
    )
    parser.add_argument("--threshold", type=float, default=0.7)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    logger.info("Building dataset from {}", args.backtest_dir)
    dataset, info = build_dataset(args.backtest_dir)

    if dataset.empty:
        raise RuntimeError("No executed trades found for training.")

    dataset_dir = PYTHON_DIR / "valuecell" / "models" / "datasets"
    dataset_dir.mkdir(parents=True, exist_ok=True)
    dataset_path = dataset_dir / f"ml_prediction_training_dataset_{stamp}.csv"
    dataset.to_csv(dataset_path, index=False)

    logger.info(
        "Dataset ready: {} rows | wins={} losses={}",
        len(dataset),
        int(dataset["label_win"].sum()),
        int((dataset["label_win"] == 0).sum()),
    )

    result = train(dataset, info["feature_names"], args.random_state)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    backup_dir = backup_existing_model(args.output_dir, stamp)

    joblib.dump(result["model"], args.output_dir / "filter_model_xgb.pkl")
    joblib.dump(result["scaler"], args.output_dir / "filter_scaler.pkl")

    meta = {
        "version": stamp,
        "trained_at": datetime.now().isoformat(),
        "model_type": result["model_type"],
        "n_features": len(info["feature_names"]),
        "feature_names": info["feature_names"],
        "threshold": args.threshold,
        "optimal_threshold": args.threshold,
        "train_rows": int(len(dataset)),
        "label_counts": result["class_counts"],
        "source_backtest_dir": str(args.backtest_dir.resolve()),
        "source_years": info["years"],
        "skipped": info["skipped"],
        "dataset_path": str(dataset_path.resolve()),
        "backup_dir": str(backup_dir.resolve()) if backup_dir else None,
        "train_accuracy": result["train_metrics"]["accuracy"],
        "train_precision": result["train_metrics"]["precision"],
        "train_recall": result["train_metrics"]["recall"],
        "train_f1": result["train_metrics"]["f1"],
        "train_auc": result["train_metrics"]["auc"],
        "test_accuracy": result["test_metrics"]["accuracy"],
        "test_precision": result["test_metrics"]["precision"],
        "test_recall": result["test_metrics"]["recall"],
        "test_f1": result["test_metrics"]["f1"],
        "test_auc": result["test_metrics"]["auc"],
        "cv_accuracy_mean": float(np.mean(result["cv_accuracy"])) if result["cv_accuracy"] else 0.0,
        "cv_accuracy_std": float(np.std(result["cv_accuracy"])) if result["cv_accuracy"] else 0.0,
        "cv_f1_mean": float(np.mean(result["cv_f1"])) if result["cv_f1"] else 0.0,
        "cv_f1_std": float(np.std(result["cv_f1"])) if result["cv_f1"] else 0.0,
        "feature_importance_shap": result["feature_importance"],
    }

    (args.output_dir / "filter_model_meta.json").write_text(
        json.dumps(meta, indent=2),
        encoding="utf-8",
    )

    logger.info("Model saved to {}", args.output_dir)
    logger.info("Dataset saved to {}", dataset_path)
    if backup_dir:
        logger.info("Previous model backup: {}", backup_dir)
    logger.info("Holdout test F1={:.3f} AUC={:.3f}", meta["test_f1"], meta["test_auc"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
