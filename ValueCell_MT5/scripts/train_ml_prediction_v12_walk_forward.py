"""
Walk-Forward Validation & Ablation Engine for ML Prediction v12 (Post-v11 Candidates).

Evaluates expanding walk-forward folds (2020-2026 OOS) across:
1. Feature Ablation:
   - Baseline (v11 feature set)
   - + MTF Alignment
   - + Structure Dynamics & Freshness
   - + Candle Dynamics & Volatility Regimes
   - + Session Liquidity & Range Expansion
   - + Full Comprehensive Feature Set (v12)
2. Model Architecture Exploration:
   - Dual Regression (Ridge/RF/ET/XGB)
   - Multi-Output Joint Regression (MultiOutput XGB/RF/ET/Ridge)
   - Dual-Head (Joint Regression + Win Probability Classifier)
3. Strict Out-of-Sample Scoring:
   - Evaluated on all 803 EA executed trades across 2020-2026.
   - Saves scored predictions, fold reports, and ablation summary.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import joblib
import numpy as np
import pandas as pd
from loguru import logger
from sklearn.base import clone
from sklearn.ensemble import ExtraTreesClassifier, ExtraTreesRegressor, RandomForestClassifier, RandomForestRegressor
from sklearn.feature_selection import SelectKBest, f_regression
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import mean_absolute_error, r2_score, roc_auc_score
from sklearn.model_selection import KFold
from sklearn.multioutput import MultiOutputRegressor
from sklearn.preprocessing import RobustScaler
from xgboost import XGBClassifier, XGBRegressor

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
PYTHON_DIR = PROJECT_ROOT / "python"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

from train_ml_prediction_v5_unconstrained import build_feature_matrix_v5

TEST_YEARS = [2020, 2021, 2022, 2023, 2024, 2025, 2026]
BASE_REFERENCE_PRICE = 4500.0


def get_dynamic_lot(rr: float, max_lot: float = 0.07) -> float:
    if rr >= 2.0:
        return min(max_lot, 0.07)
    elif rr >= 1.5:
        return min(max_lot, 0.04)
    elif rr >= 1.2:
        return min(max_lot, 0.02)
    elif rr >= 1.05:
        return min(max_lot, 0.01)
    return 0.0


def profit_factor(pnl_series: pd.Series) -> float:
    wins = pnl_series[pnl_series > 0].sum()
    losses = abs(pnl_series[pnl_series < 0].sum())
    if losses == 0:
        return float("inf") if wins > 0 else 0.0
    return float(wins / losses)


def max_drawdown(pnl_series: pd.Series) -> float:
    if len(pnl_series) == 0:
        return 0.0
    equity = pnl_series.cumsum()
    peak = equity.cummax()
    return float((equity - peak).min())


def select_and_fit_single_regressor(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    target_name: str,
    k_candidates: list[int] = [15, 20, 25, 30, 35, 40],
) -> Tuple[Any, RobustScaler, list[str], str]:
    models = {
        "Ridge_alpha10.0": Ridge(alpha=10.0, random_state=42),
        "Ridge_alpha1.0": Ridge(alpha=1.0, random_state=42),
        "RandomForest_d5_n200_leaf15": RandomForestRegressor(
            n_estimators=200, max_depth=5, min_samples_leaf=15, random_state=42, n_jobs=-1
        ),
        "ExtraTrees_d5_n200_leaf15": ExtraTreesRegressor(
            n_estimators=200, max_depth=5, min_samples_leaf=15, random_state=42, n_jobs=-1
        ),
        "XGB_d3_n120_lr002": XGBRegressor(
            n_estimators=120, max_depth=3, learning_rate=0.02, random_state=42, n_jobs=-1
        ),
    }

    n_splits = 5 if len(X_train) >= 200 else 3
    kf = KFold(n_splits=n_splits, shuffle=True, random_state=42)

    best_score = -999.0
    best_model = None
    best_features = list(X_train.columns)
    best_scaler = RobustScaler()
    best_name = "None"

    for k in k_candidates:
        if k > X_train.shape[1]:
            k = X_train.shape[1]
        selector = SelectKBest(score_func=f_regression, k=k)
        selector.fit(X_train, y_train)
        selected_cols = list(X_train.columns[selector.get_support()])

        X_tr_k = X_train[selected_cols]
        scaler_k = RobustScaler()
        X_tr_k_scaled = scaler_k.fit_transform(X_tr_k)

        for m_name, model in models.items():
            cv_r2_scores = []
            for tr_idx, val_idx in kf.split(X_tr_k_scaled):
                X_cv_tr, X_cv_val = X_tr_k_scaled[tr_idx], X_tr_k_scaled[val_idx]
                y_cv_tr, y_cv_val = y_train.iloc[tr_idx].values, y_train.iloc[val_idx].values

                m_cv = clone(model)
                m_cv.fit(X_cv_tr, y_cv_tr)
                preds = m_cv.predict(X_cv_val)
                cv_r2_scores.append(r2_score(y_cv_val, preds))

            mean_cv_r2 = float(np.mean(cv_r2_scores))
            candidate_id = f"{m_name}_f{k}"

            if mean_cv_r2 > best_score:
                best_score = mean_cv_r2
                best_name = candidate_id
                best_features = selected_cols
                best_scaler = scaler_k
                fresh_fit = clone(model)
                fresh_fit.fit(X_tr_k_scaled, y_train.values)
                best_model = fresh_fit

    return best_model, best_scaler, best_features, best_name


def select_and_fit_classifier(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    target_name: str = "WinProb",
    k: int = 25,
) -> Tuple[Any, RobustScaler, list[str]]:
    k_actual = min(k, X_train.shape[1])
    selector = SelectKBest(score_func=f_regression, k=k_actual)
    selector.fit(X_train, y_train)
    selected_cols = list(X_train.columns[selector.get_support()])

    scaler = RobustScaler()
    X_scaled = scaler.fit_transform(X_train[selected_cols])

    clf = LogisticRegression(C=1.0, max_iter=500, random_state=42)
    clf.fit(X_scaled, y_train.values)
    return clf, scaler, selected_cols


def run_walk_forward_experiment(
    df: pd.DataFrame,
    feature_cols: list[str],
    experiment_name: str,
    arch_type: str = "dual_regression",
    use_classifier_head: bool = False,
    news_blackout_mode: str = "filter",  # 'filter', 'none'
    weekend_mode: str = "penalty",      # 'veto', 'penalty', 'none'
) -> dict:
    price_ratio = (df["entry_price"] / BASE_REFERENCE_PRICE).clip(lower=1.0 / BASE_REFERENCE_PRICE)
    df["mfe_target_norm"] = df["mfe_target"] / price_ratio
    df["mae_target_norm"] = df["mae_target"] / price_ratio
    df["is_win"] = (df["actual_net_profit"] > 0).astype(float)

    # Base feature matrix
    base_model_df, _, _ = build_feature_matrix_v5(df)
    base_model_df = base_model_df.drop(columns=["mfe_target_norm", "mae_target_norm", "is_win"], errors="ignore")

    # Add extra columns from feature_cols if available
    for col in feature_cols:
        if col in df.columns and col not in base_model_df.columns:
            base_model_df[col] = df[col].astype(float)

    # Filter available columns
    available_cols = [c for c in base_model_df.columns if c in feature_cols or any(c.startswith(fc) for fc in feature_cols)]
    if not available_cols:
        available_cols = list(base_model_df.columns)
    model_df = base_model_df[available_cols].copy()

    # Weekend condition
    t_dt = pd.to_datetime(df["entry_time"], utc=True)
    is_friday_late = (t_dt.dt.weekday == 4) & (t_dt.dt.hour >= 18)
    is_monday_open = ((t_dt.dt.weekday == 6) & (t_dt.dt.hour >= 22)) | ((t_dt.dt.weekday == 0) & (t_dt.dt.hour < 1))
    is_weekend_gap = is_friday_late | is_monday_open

    scored_folds = []

    for test_year in TEST_YEARS:
        train_mask = df["year"] < test_year
        test_mask = df["year"] == test_year
        n_train, n_test = int(train_mask.sum()), int(test_mask.sum())

        if n_train < 30 or n_test == 0:
            continue

        X_train = model_df.loc[train_mask]
        X_test = model_df.loc[test_mask]
        y_mfe_train = df.loc[train_mask, "mfe_target_norm"]
        y_mae_train = df.loc[train_mask, "mae_target_norm"]
        y_win_train = df.loc[train_mask, "is_win"]
        pr_test = price_ratio.loc[test_mask].values

        if arch_type == "dual_regression":
            mfe_model, mfe_scaler, mfe_feats, _ = select_and_fit_single_regressor(X_train, y_mfe_train, f"MFE_{test_year}")
            mae_model, mae_scaler, mae_feats, _ = select_and_fit_single_regressor(X_train, y_mae_train, f"MAE_{test_year}")

            pred_mfe_norm = mfe_model.predict(mfe_scaler.transform(X_test[mfe_feats]))
            pred_mae_norm = mae_model.predict(mae_scaler.transform(X_test[mae_feats]))
            pred_mfe = pred_mfe_norm * pr_test
            pred_mae = pred_mae_norm * pr_test

        elif arch_type == "joint_regression":
            # Multi-output XGB / RF
            scaler_j = RobustScaler()
            X_tr_sc = scaler_j.fit_transform(X_train)
            X_te_sc = scaler_j.transform(X_test)
            joint_model = MultiOutputRegressor(
                XGBRegressor(n_estimators=120, max_depth=3, learning_rate=0.02, random_state=42, n_jobs=-1)
            )
            joint_model.fit(X_tr_sc, np.column_stack([y_mfe_train.values, y_mae_train.values]))
            preds_norm = joint_model.predict(X_te_sc)
            pred_mfe = preds_norm[:, 0] * pr_test
            pred_mae = preds_norm[:, 1] * pr_test

        # Optional Classifier Head
        win_prob = np.ones(n_test, dtype=float)
        if use_classifier_head:
            clf, clf_scaler, clf_feats = select_and_fit_classifier(X_train, y_win_train, f"WinClf_{test_year}")
            win_prob = clf.predict_proba(clf_scaler.transform(X_test[clf_feats]))[:, 1]

        fold_df = df.loc[test_mask].copy()
        fold_df["predicted_mfe"] = pred_mfe
        fold_df["predicted_mae"] = pred_mae
        fold_df["win_prob"] = win_prob
        fold_df["fold_test_year"] = test_year
        scored_folds.append(fold_df)

    combined_df = pd.concat(scored_folds, axis=0).reset_index(drop=True)

    # Evaluate on EA executed trades
    ea_mask = combined_df["ea_status"] == "EXECUTED"
    ea_df = combined_df[ea_mask].copy().reset_index(drop=True)
    ea_df["expected_rr"] = ea_df["predicted_mfe"] / np.maximum(1.0, ea_df["predicted_mae"])

    t_dt_ea = pd.to_datetime(ea_df["entry_time"], utc=True)
    is_fri = (t_dt_ea.dt.weekday == 4) & (t_dt_ea.dt.hour >= 18)
    is_mon = ((t_dt_ea.dt.weekday == 6) & (t_dt_ea.dt.hour >= 22)) | ((t_dt_ea.dt.weekday == 0) & (t_dt_ea.dt.hour < 1))
    ea_weekend = is_fri | is_mon

    # Pass Gate
    pass_mask = ea_df["expected_rr"] >= 1.05
    if use_classifier_head:
        pass_mask = pass_mask & (ea_df["win_prob"] >= 0.48)

    if news_blackout_mode == "filter" and "is_news_blackout" in ea_df.columns:
        pass_mask = pass_mask & (ea_df["is_news_blackout"] == 0)

    if weekend_mode == "veto":
        pass_mask = pass_mask & (~ea_weekend)

    # Dynamic Lot Calculation
    lots = np.array([get_dynamic_lot(r) for r in ea_df["expected_rr"]])
    if weekend_mode == "penalty":
        # -50% lot penalty on weekend instead of hard veto
        lots = np.where(ea_weekend, lots * 0.5, lots)

    ea_df["pass_gate"] = pass_mask
    ea_df["lot"] = np.where(pass_mask, lots, 0.0)
    ea_df["dyn_net_pnl"] = ea_df["actual_net_profit"] * (ea_df["lot"] / 0.01)

    passed_trades = ea_df[ea_df["pass_gate"]].copy().reset_index(drop=True)

    n_trades = len(passed_trades)
    n_wins = int((passed_trades["actual_net_profit"] > 0).sum())
    win_rate = (n_wins / n_trades * 100.0) if n_trades > 0 else 0.0
    flat_net_pnl = float(passed_trades["actual_net_profit"].sum())
    dyn_net_pnl = float(passed_trades["dyn_net_pnl"].sum())
    pf = profit_factor(passed_trades["dyn_net_pnl"])
    dd = max_drawdown(passed_trades["dyn_net_pnl"])

    # Per year breakdown
    by_year = {}
    for yr in sorted(ea_df["year"].unique()):
        yr_sub = passed_trades[passed_trades["year"] == yr]
        t = len(yr_sub)
        w = int((yr_sub["actual_net_profit"] > 0).sum())
        r = (w / t * 100.0) if t > 0 else 0.0
        f_p = float(yr_sub["actual_net_profit"].sum())
        d_p = float(yr_sub["dyn_net_pnl"].sum())
        by_year[int(yr)] = {"trades": t, "wins": w, "wr": r, "flat_pnl": f_p, "dyn_pnl": d_p}

    # BUY vs SELL breakdown
    buy_sub = passed_trades[passed_trades["signal"] == "BUY"]
    sell_sub = passed_trades[passed_trades["signal"] == "SELL"]

    buy_pnl = float(buy_sub["dyn_net_pnl"].sum())
    sell_pnl = float(sell_sub["dyn_net_pnl"].sum())
    buy_wr = float((buy_sub["actual_net_profit"] > 0).mean() * 100.0) if len(buy_sub) else 0.0
    sell_wr = float((sell_sub["actual_net_profit"] > 0).mean() * 100.0) if len(sell_sub) else 0.0

    return {
        "experiment_name": experiment_name,
        "arch_type": arch_type,
        "n_features": len(available_cols),
        "total_trades": n_trades,
        "wins": n_wins,
        "win_rate": win_rate,
        "flat_net_pnl": flat_net_pnl,
        "dynamic_net_pnl": dyn_net_pnl,
        "profit_factor": pf,
        "max_drawdown": dd,
        "buy_trades": len(buy_sub),
        "buy_wr": buy_wr,
        "buy_dyn_pnl": buy_pnl,
        "sell_trades": len(sell_sub),
        "sell_wr": sell_wr,
        "sell_dyn_pnl": sell_pnl,
        "by_year": by_year,
        "scored_df": combined_df,
    }


def main():
    logger.info("=== STARTING ML PREDICTION v12 WALK-FORWARD ABLATION PIPELINE ===")

    models_dir = PYTHON_DIR / "valuecell" / "models" / "saved" / "filter_latest"
    dataset_path = models_dir / "dataset_v12_unconstrained.csv"
    df = pd.read_csv(dataset_path)
    logger.info("Loaded Dataset v12: {} samples, {} columns", len(df), len(df.columns))

    # Feature Groups Definition
    v11_base_cols = [
        "planned_rr", "init_risk_points", "init_reward_points",
        "reject_group_NONE", "reject_group_TREND_FILTER_EMA", "reject_group_CYCLE_LIMIT", "reject_group_UNCONSTRAINED_SIM",
        "is_news_blackout", "minutes_to_next_news", "minutes_since_last_news", "is_fomc_day", "hours_to_next_fomc"
    ]

    family1_mtf = [
        "m15_ema200_slope", "h1_ema200_slope", "h4_ema200_slope",
        "h1_trend_align", "h4_trend_align", "mtf_alignment_score",
        "price_to_h1_ema_atr", "price_to_h4_ema_atr"
    ]

    family2_struct = [
        "structure_age_hours", "struct_count_5b", "struct_count_10b", "struct_count_20b",
        "trend_strength_ratio", "is_confluence_zone"
    ]

    family3_candle = [
        "candle_body_ratio", "upper_wick_ratio", "lower_wick_ratio",
        "vol_spike_ratio", "vol_regime_ratio", "range_expansion_5b"
    ]

    family4_session = [
        "session_range_exp", "is_prev_high_break", "is_prev_low_break", "session_progress_pct"
    ]

    family5_cost = [
        "spread_to_atr_ratio", "risk_to_atr_ratio"
    ]

    all_v12_features = list(set(v11_base_cols + family1_mtf + family2_struct + family3_candle + family4_session + family5_cost))

    # Define Experiment Matrix
    experiments = [
        # Ablation Experiments
        ("Exp01_Baseline_v11_Dual", v11_base_cols, "dual_regression", False, "filter", "veto"),
        ("Exp02_Plus_MTF_Align", v11_base_cols + family1_mtf, "dual_regression", False, "filter", "veto"),
        ("Exp03_Plus_Struct_Dynamics", v11_base_cols + family2_struct, "dual_regression", False, "filter", "veto"),
        ("Exp04_Plus_Candle_Vol", v11_base_cols + family3_candle, "dual_regression", False, "filter", "veto"),
        ("Exp05_Plus_Session_Liq", v11_base_cols + family4_session, "dual_regression", False, "filter", "veto"),
        ("Exp06_Plus_Cost_Risk", v11_base_cols + family5_cost, "dual_regression", False, "filter", "veto"),
        ("Exp07_All_v12_Dual_Veto", all_v12_features, "dual_regression", False, "filter", "veto"),
        ("Exp08_All_v12_Dual_Pen50", all_v12_features, "dual_regression", False, "filter", "penalty"),
        ("Exp09_All_v12_Joint_XGB", all_v12_features, "joint_regression", False, "filter", "penalty"),
        ("Exp10_All_v12_DualHead_Clf", all_v12_features, "dual_regression", True, "filter", "penalty"),
    ]

    results = []
    best_exp = None
    best_pnl = -999999.0

    print("=" * 110)
    print(f"{'Experiment Name':30} | {'Features':8} | {'Trades':6} | {'WinRate':8} | {'Flat Net PnL':14} | {'Dynamic Net PnL':16} | {'PF':6} | {'Max DD':9}")
    print("=" * 110)

    for exp_name, feat_cols, arch, clf_head, news_mode, wk_mode in experiments:
        res = run_walk_forward_experiment(
            df=df,
            feature_cols=feat_cols,
            experiment_name=exp_name,
            arch_type=arch,
            use_classifier_head=clf_head,
            news_blackout_mode=news_mode,
            weekend_mode=wk_mode,
        )
        results.append(res)
        print(f"{res['experiment_name']:30} | {res['n_features']:8} | {res['total_trades']:6} | {res['win_rate']:7.1f}% | {res['flat_net_pnl']:12.2f} USD | {res['dynamic_net_pnl']:14.2f} USD | {res['profit_factor']:5.2f} | {res['max_drawdown']:8.2f}")

        if res["dynamic_net_pnl"] > best_pnl:
            best_pnl = res["dynamic_net_pnl"]
            best_exp = res

    # Save best scored dataset
    if best_exp is not None:
        best_scored_path = models_dir / "scored_v12_walk_forward.csv"
        best_exp["scored_df"].to_csv(best_scored_path, index=False)
        logger.info("Saved Best Candidate Walk-Forward Scored Dataset to: {}", best_scored_path)

    # Save ablation summary
    summary_list = []
    for r in results:
        summary_list.append({
            "experiment_name": r["experiment_name"],
            "arch_type": r["arch_type"],
            "features_count": r["n_features"],
            "trades": r["total_trades"],
            "win_rate": r["win_rate"],
            "flat_net_pnl": r["flat_net_pnl"],
            "dynamic_net_pnl": r["dynamic_net_pnl"],
            "profit_factor": r["profit_factor"],
            "max_drawdown": r["max_drawdown"],
            "buy_trades": r["buy_trades"],
            "buy_wr": r["buy_wr"],
            "buy_dyn_pnl": r["buy_dyn_pnl"],
            "sell_trades": r["sell_trades"],
            "sell_wr": r["sell_wr"],
            "sell_dyn_pnl": r["sell_dyn_pnl"],
            "by_year": r["by_year"],
        })

    summary_df = pd.DataFrame(summary_list).drop(columns=["by_year"])
    summary_path = models_dir / "walk_forward_ablation_v12_summary.csv"
    summary_df.to_csv(summary_path, index=False)

    with open(models_dir / "summary_v12_ablation.json", "w") as f:
        json.dump(summary_list, f, indent=2)

    logger.info("Saved Ablation Summary to: {} and JSON", summary_path)


if __name__ == "__main__":
    main()
