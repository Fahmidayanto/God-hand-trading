"""
High-Speed & Exact Parity ML Prediction v12 Walk-Forward Engine.
Uses the exact feature ranking (XGBoost importance), StandardScaler, and Ridge/RF architectures
from v8/v9/v11, with 0 thread contention and sub-30s runtime.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Tuple

import numpy as np
import pandas as pd
from loguru import logger
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.multioutput import MultiOutputRegressor
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

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


def get_dynamic_lot(rr: float) -> float:
    if rr >= 2.0:
        return 0.07
    elif rr >= 1.5:
        return 0.04
    elif rr >= 1.2:
        return 0.02
    elif rr >= 1.05:
        return 0.01
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


def fit_mfe_regressor_exact(X_tr: pd.DataFrame, y_mfe: pd.Series, X_te: pd.DataFrame, top_k: int = 30) -> np.ndarray:
    # 1. Feature ranking via fast XGBoost
    scaler_init = StandardScaler()
    X_tr_sc = scaler_init.fit_transform(X_tr)
    pre_xgb = XGBRegressor(n_estimators=80, max_depth=3, learning_rate=0.03, random_state=42, n_jobs=1)
    pre_xgb.fit(X_tr_sc, y_mfe)
    imp = pre_xgb.feature_importances_
    ranked = [col for col, _ in sorted(zip(X_tr.columns, imp), key=lambda x: x[1], reverse=True)]
    selected_cols = ranked[: min(top_k, len(ranked))]

    # 2. Fit Ridge alpha=10.0 on selected features
    scaler = StandardScaler()
    X_tr_sel = scaler.fit_transform(X_tr[selected_cols])
    X_te_sel = scaler.transform(X_te[selected_cols])
    model = Ridge(alpha=10.0, random_state=42)
    model.fit(X_tr_sel, y_mfe.values)
    return model.predict(X_te_sel)


def fit_mae_regressor_exact(X_tr: pd.DataFrame, y_mae: pd.Series, X_te: pd.DataFrame, top_k: int = 25) -> np.ndarray:
    scaler_init = StandardScaler()
    X_tr_sc = scaler_init.fit_transform(X_tr)
    pre_xgb = XGBRegressor(n_estimators=80, max_depth=3, learning_rate=0.03, random_state=42, n_jobs=1)
    pre_xgb.fit(X_tr_sc, y_mae)
    imp = pre_xgb.feature_importances_
    ranked = [col for col, _ in sorted(zip(X_tr.columns, imp), key=lambda x: x[1], reverse=True)]
    selected_cols = ranked[: min(top_k, len(ranked))]

    scaler = StandardScaler()
    X_tr_sel = scaler.fit_transform(X_tr[selected_cols])
    X_te_sel = scaler.transform(X_te[selected_cols])
    model = RandomForestRegressor(n_estimators=150, max_depth=5, min_samples_leaf=15, random_state=42, n_jobs=1)
    model.fit(X_tr_sel, y_mae.values)
    return model.predict(X_te_sel)


def run_exact_experiment(
    df: pd.DataFrame,
    extra_feature_cols: list[str],
    name: str,
    top_k_mfe: int = 30,
    top_k_mae: int = 25,
    use_news_filter: bool = True,
    weekend_rule: str = "penalty_50",  # 'veto', 'penalty_50', 'none'
) -> dict:
    price_ratio = (df["entry_price"] / BASE_REFERENCE_PRICE).clip(lower=1.0 / BASE_REFERENCE_PRICE)
    df["mfe_norm"] = df["mfe_target"] / price_ratio
    df["mae_norm"] = df["mae_target"] / price_ratio

    base_df, _, _ = build_feature_matrix_v5(df)
    base_df = base_df.drop(columns=["mfe_norm", "mae_norm", "mfe_target_norm", "mae_target_norm"], errors="ignore")

    for c in extra_feature_cols:
        if c in df.columns and c not in base_df.columns:
            base_df[c] = df[c].astype(float)

    scored_folds = []

    for yr in TEST_YEARS:
        tr_mask = df["year"] < yr
        te_mask = df["year"] == yr
        if tr_mask.sum() < 30 or te_mask.sum() == 0:
            continue

        X_tr = base_df.loc[tr_mask]
        X_te = base_df.loc[te_mask]
        y_m = df.loc[tr_mask, "mfe_norm"]
        y_a = df.loc[tr_mask, "mae_norm"]
        pr_te = price_ratio.loc[te_mask].values

        p_m_norm = fit_mfe_regressor_exact(X_tr, y_m, X_te, top_k=top_k_mfe)
        p_a_norm = fit_mae_regressor_exact(X_tr, y_a, X_te, top_k=top_k_mae)

        f_df = df.loc[te_mask].copy()
        f_df["predicted_mfe"] = p_m_norm * pr_te
        f_df["predicted_mae"] = p_a_norm * pr_te
        scored_folds.append(f_df)

    comb = pd.concat(scored_folds, axis=0).reset_index(drop=True)
    ea = comb[comb["ea_status"] == "EXECUTED"].copy().reset_index(drop=True)
    ea["expected_rr"] = ea["predicted_mfe"] / np.maximum(1.0, ea["predicted_mae"])

    t_dt = pd.to_datetime(ea["entry_time"], utc=True)
    is_fri = (t_dt.dt.weekday == 4) & (t_dt.dt.hour >= 18)
    is_mon = ((t_dt.dt.weekday == 6) & (t_dt.dt.hour >= 22)) | ((t_dt.dt.weekday == 0) & (t_dt.dt.hour < 1))
    is_wk = is_fri | is_mon

    pass_mask = ea["expected_rr"] >= 1.05
    if use_news_filter and "is_news_blackout" in ea.columns:
        pass_mask = pass_mask & (ea["is_news_blackout"] == 0)

    lots = np.array([get_dynamic_lot(r) for r in ea["expected_rr"]])
    if weekend_rule == "penalty_50":
        lots = np.where(is_wk, lots * 0.5, lots)
    elif weekend_rule == "veto":
        pass_mask = pass_mask & (~is_wk)

    ea["lot"] = np.where(pass_mask, lots, 0.0)
    ea["dyn_pnl"] = ea["actual_net_profit"] * (ea["lot"] / 0.01)

    passed = ea[pass_mask].copy()
    n_trd = len(passed)
    n_w = int((passed["actual_net_profit"] > 0).sum())
    wr = (n_w / n_trd * 100.0) if n_trd > 0 else 0.0
    flat_pnl = float(passed["actual_net_profit"].sum())
    dyn_pnl = float(passed["dyn_pnl"].sum())
    pf = profit_factor(passed["dyn_pnl"])
    dd = max_drawdown(passed["dyn_pnl"])

    # Per year breakdown
    by_yr = {}
    for yr in sorted(ea["year"].unique()):
        sub = passed[passed["year"] == yr]
        t = len(sub)
        w = int((sub["actual_net_profit"] > 0).sum())
        r = (w / t * 100.0) if t > 0 else 0.0
        f_p = float(sub["actual_net_profit"].sum())
        d_p = float(sub["dyn_pnl"].sum())
        by_yr[int(yr)] = {"trades": t, "wins": w, "wr": r, "flat_pnl": f_p, "dyn_pnl": d_p}

    # BUY vs SELL
    buy_sub = passed[passed["signal"] == "BUY"]
    sell_sub = passed[passed["signal"] == "SELL"]

    return {
        "name": name,
        "trades": n_trd,
        "wins": n_w,
        "wr": wr,
        "flat_pnl": flat_pnl,
        "dyn_pnl": dyn_pnl,
        "pf": pf,
        "max_dd": dd,
        "buy_trades": len(buy_sub),
        "buy_wr": float((buy_sub["actual_net_profit"] > 0).mean() * 100.0) if len(buy_sub) else 0.0,
        "buy_dyn_pnl": float(buy_sub["dyn_pnl"].sum()) if len(buy_sub) else 0.0,
        "sell_trades": len(sell_sub),
        "sell_wr": float((sell_sub["actual_net_profit"] > 0).mean() * 100.0) if len(sell_sub) else 0.0,
        "sell_dyn_pnl": float(sell_sub["dyn_pnl"].sum()) if len(sell_sub) else 0.0,
        "by_year": by_yr,
        "scored_df": comb,
    }


def main():
    models_dir = PYTHON_DIR / "valuecell" / "models" / "saved" / "filter_latest"
    df = pd.read_csv(models_dir / "dataset_v12_unconstrained.csv")

    v11_cols = [
        "planned_rr", "init_risk_points", "init_reward_points",
        "reject_group_NONE", "reject_group_TREND_FILTER_EMA", "reject_group_CYCLE_LIMIT", "reject_group_UNCONSTRAINED_SIM",
        "is_news_blackout", "minutes_to_next_news", "minutes_since_last_news", "is_fomc_day", "hours_to_next_fomc"
    ]
    f1_mtf = ["m15_ema200_slope", "h1_ema200_slope", "h4_ema200_slope", "h1_trend_align", "h4_trend_align", "mtf_alignment_score", "price_to_h1_ema_atr", "price_to_h4_ema_atr"]
    f2_struct = ["structure_age_hours", "struct_count_5b", "struct_count_10b", "struct_count_20b", "trend_strength_ratio", "is_confluence_zone"]
    f3_candle = ["candle_body_ratio", "upper_wick_ratio", "lower_wick_ratio", "vol_spike_ratio", "vol_regime_ratio", "range_expansion_5b"]
    f4_sess = ["session_range_exp", "is_prev_high_break", "is_prev_low_break", "session_progress_pct"]
    f5_cost = ["spread_to_atr_ratio", "risk_to_atr_ratio"]

    all_v12 = list(set(v11_cols + f1_mtf + f2_struct + f3_candle + f4_sess + f5_cost))

    experiments = [
        ("v8_Canonical_NoFilter", [], 30, 25, False, "none"),
        ("v9_Replicated_Veto", v11_cols[:7] + v11_cols[7:], 30, 25, True, "veto"),
        ("v11_Replicated_Veto", v11_cols, 35, 15, True, "veto"),
        ("v12_Ablation_MTF", v11_cols + f1_mtf, 35, 20, True, "penalty_50"),
        ("v12_Ablation_Struct", v11_cols + f2_struct, 35, 20, True, "penalty_50"),
        ("v12_Ablation_Candle", v11_cols + f3_candle, 35, 20, True, "penalty_50"),
        ("v12_Ablation_Session", v11_cols + f4_sess, 35, 20, True, "penalty_50"),
        ("v12_Comprehensive_Full", all_v12, 35, 25, True, "penalty_50"),
        ("v12_Tuned_PureAlpha", all_v12, 30, 20, True, "penalty_50"),
    ]

    print("=" * 110)
    print(f"{'Experiment Name':32} | {'Trades':6} | {'WinRate':8} | {'Flat Net PnL':14} | {'Dynamic Net PnL':16} | {'PF':6} | {'Max DD':9}")
    print("=" * 110)

    results = []
    best_res = None
    best_pnl = -999999.0

    for name, cols, km, ka, nf, wk in experiments:
        res = run_exact_experiment(df, cols, name, top_k_mfe=km, top_k_mae=ka, use_news_filter=nf, weekend_rule=wk)
        results.append(res)
        print(f"{res['name']:32} | {res['trades']:6} | {res['wr']:7.1f}% | {res['flat_pnl']:12.2f} USD | {res['dyn_pnl']:14.2f} USD | {res['pf']:5.2f} | {res['max_dd']:8.2f}")
        if res["dyn_pnl"] > best_pnl:
            best_pnl = res["dyn_pnl"]
            best_res = res

    print("=" * 110)

    if best_res is not None:
        best_res["scored_df"].to_csv(models_dir / "scored_v12_walk_forward.csv", index=False)
        print(f"\nSaved Best Scored Dataset to: {models_dir / 'scored_v12_walk_forward.csv'}")

    print("\nPER TAHUN DYNAMIC NET PNL (USD):")
    header = f"{'Year':6} | " + " | ".join([f"{r['name'][:10]:10}" for r in results])
    print(header)
    print("-" * len(header))
    for yr in TEST_YEARS:
        row = f"{yr:6} | "
        for r in results:
            pnl = r["by_year"].get(yr, {}).get("dyn_pnl", 0.0)
            row += f"{pnl:10.2f} | "
        print(row)

    print("\nPER TAHUN FLAT NET PNL 0.01 LOT (USD):")
    header = f"{'Year':6} | " + " | ".join([f"{r['name'][:10]:10}" for r in results])
    print(header)
    print("-" * len(header))
    for yr in TEST_YEARS:
        row = f"{yr:6} | "
        for r in results:
            pnl = r["by_year"].get(yr, {}).get("flat_pnl", 0.0)
            row += f"{pnl:10.2f} | "
        print(row)

    summary_data = []
    for r in results:
        summary_data.append({
            "name": r["name"],
            "trades": r["trades"],
            "win_rate": r["wr"],
            "flat_net_pnl": r["flat_pnl"],
            "dynamic_net_pnl": r["dyn_pnl"],
            "profit_factor": r["pf"],
            "max_drawdown": r["max_dd"],
            "buy_trades": r["buy_trades"],
            "buy_wr": r["buy_wr"],
            "buy_dyn_pnl": r["buy_dyn_pnl"],
            "sell_trades": r["sell_trades"],
            "sell_wr": r["sell_wr"],
            "sell_dyn_pnl": r["sell_dyn_pnl"],
            "by_year": r["by_year"],
        })
    with open(models_dir / "walk_forward_v12_exact_summary.json", "w") as f:
        json.dump(summary_data, f, indent=2)


if __name__ == "__main__":
    main()
