import sys
from pathlib import Path
import pandas as pd
import numpy as np
import joblib

sys.stdout.reconfigure(encoding="utf-8")
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "ValueCell_MT5" / "scripts"))
sys.path.insert(0, str(repo_root / "ValueCell_MT5" / "python"))

from train_ml_prediction_v5_unconstrained import build_feature_matrix_v5

models_dir = repo_root / "ValueCell_MT5" / "python" / "valuecell" / "models" / "saved" / "filter_latest"

# 1. Load Dataset v11
df = pd.read_csv(models_dir / "dataset_v11_unconstrained.csv")
ea = df[df["ea_status"] == "EXECUTED"].copy().reset_index(drop=True)
ea["net_profit"] = ea["actual_net_profit"]

# 2. Build base feature matrix
model_df, _, _ = build_feature_matrix_v5(ea)
price_ratio = (ea["entry_price"] / 4500.0).clip(lower=1.0/4500.0)

# Add v11 columns
v11_cols = [
    "planned_rr", "init_risk_points", "init_reward_points",
    "reject_group_NONE", "reject_group_TREND_FILTER_EMA",
    "reject_group_CYCLE_LIMIT", "reject_group_UNCONSTRAINED_SIM"
]
for col in v11_cols:
    if col in ea.columns:
        model_df[col] = ea[col].astype(float)

# Weekend filter
t_dt = pd.to_datetime(ea["entry_time"], utc=True)
is_friday_late = (t_dt.dt.weekday == 4) & (t_dt.dt.hour >= 18)
is_monday_open = ((t_dt.dt.weekday == 6) & (t_dt.dt.hour >= 22)) | ((t_dt.dt.weekday == 0) & (t_dt.dt.hour < 1))
is_weekend_gap_veto = is_friday_late | is_monday_open

def get_lot(rr):
    if rr >= 2.0:
        return 0.07
    elif rr >= 1.5:
        return 0.04
    elif rr >= 1.2:
        return 0.02
    elif rr >= 1.05:
        return 0.01
    return 0.0

def evaluate_pred(pred_mfe, pred_mae, name, use_news=False, use_weekend=False):
    rr = pred_mfe / np.maximum(1.0, pred_mae)
    pass_mask = rr >= 1.05
    if use_news:
        pass_mask = pass_mask & (ea["is_news_blackout"] == 0)
    if use_weekend:
        pass_mask = pass_mask & (~is_weekend_gap_veto)

    passed = ea[pass_mask].copy()
    passed["lot"] = [get_lot(r) for r in rr[pass_mask]]
    passed["dyn_pnl"] = passed["net_profit"] * (passed["lot"] / 0.01)

    n_trades = len(passed)
    n_wins = (passed["net_profit"] > 0).sum()
    wr = (n_wins / n_trades * 100.0) if n_trades > 0 else 0.0
    flat_pnl = passed["net_profit"].sum()
    dyn_pnl = passed["dyn_pnl"].sum()

    # Per year breakdown
    by_year = {}
    for yr in sorted(ea["year"].unique()):
        sub = passed[passed["year"] == yr]
        t = len(sub)
        w = (sub["net_profit"] > 0).sum()
        r = (w / t * 100.0) if t > 0 else 0.0
        f_p = sub["net_profit"].sum()
        d_p = sub["dyn_pnl"].sum()
        by_year[int(yr)] = {"trades": t, "wins": w, "wr": r, "flat_pnl": f_p, "dyn_pnl": d_p}

    return {
        "name": name,
        "trades": n_trades,
        "wins": n_wins,
        "wr": wr,
        "flat_pnl": flat_pnl,
        "dyn_pnl": dyn_pnl,
        "by_year": by_year,
    }

# 1. Model v8 Final
mfe_v8 = joblib.load(models_dir / "model_v8_final_mfe.pkl")
smfe_v8 = joblib.load(models_dir / "scaler_v8_final_mfe.pkl")
mae_v8 = joblib.load(models_dir / "model_v8_final_mae.pkl")
smae_v8 = joblib.load(models_dir / "scaler_v8_final_mae.pkl")
pmfe_v8 = mfe_v8.predict(smfe_v8.transform(model_df[smfe_v8.feature_names_in_])) * price_ratio.values
pmae_v8 = mae_v8.predict(smae_v8.transform(model_df[smae_v8.feature_names_in_])) * price_ratio.values

res_v8_no_filter = evaluate_pred(pmfe_v8, pmae_v8, "Model v8 (No News/Weekend)")
res_v8_news_filter = evaluate_pred(pmfe_v8, pmae_v8, "Model v8 (With News+Weekend)", use_news=True, use_weekend=True)

# 2. Model v9 Final
mfe_v9 = joblib.load(models_dir / "model_v9_final_mfe.pkl")
smfe_v9 = joblib.load(models_dir / "scaler_v9_final_mfe.pkl")
mae_v9 = joblib.load(models_dir / "model_v9_final_mae.pkl")
smae_v9 = joblib.load(models_dir / "scaler_v9_final_mae.pkl")
pmfe_v9 = mfe_v9.predict(smfe_v9.transform(model_df[smfe_v9.feature_names_in_])) * price_ratio.values
pmae_v9 = mae_v9.predict(smae_v9.transform(model_df[smae_v9.feature_names_in_])) * price_ratio.values
res_v9 = evaluate_pred(pmfe_v9, pmae_v9, "Model v9 (News+Weekend)", use_news=True, use_weekend=True)

# 3. Model v10 Final
joint_v10 = joblib.load(models_dir / "model_v10_final_joint.pkl")
s_v10 = joblib.load(models_dir / "scaler_v10_final_joint.pkl")
preds_v10 = joint_v10.predict(s_v10.transform(model_df[s_v10.feature_names_in_]))
pmfe_v10 = preds_v10[:, 0] * price_ratio.values
pmae_v10 = preds_v10[:, 1] * price_ratio.values
res_v10 = evaluate_pred(pmfe_v10, pmae_v10, "Model v10 (Joint, News+Weekend)", use_news=True, use_weekend=True)

# 4. Model v11 Final
mfe_v11 = joblib.load(models_dir / "model_v11_final_mfe.pkl")
smfe_v11 = joblib.load(models_dir / "scaler_v11_final_mfe.pkl")
mae_v11 = joblib.load(models_dir / "model_v11_final_mae.pkl")
smae_v11 = joblib.load(models_dir / "scaler_v11_final_mae.pkl")
pmfe_v11 = mfe_v11.predict(smfe_v11.transform(model_df[smfe_v11.feature_names_in_])) * price_ratio.values
pmae_v11 = mae_v11.predict(smae_v11.transform(model_df[smae_v11.feature_names_in_])) * price_ratio.values
res_v11 = evaluate_pred(pmfe_v11, pmae_v11, "Model v11 (Planned R:R, News+Weekend)", use_news=True, use_weekend=True)

# EA Raw baseline
ea_raw_wr = (ea["net_profit"] > 0).mean() * 100.0
ea_raw_flat = ea["net_profit"].sum()
print("=" * 90)
print(f"{'Model Configuration':38} | {'Trades':6} | {'WinRate':8} | {'Flat Net PnL':14} | {'Dynamic Net PnL':16}")
print("=" * 90)
print(f"{'EA Raw Baseline (No ML)':38} | {len(ea):6} | {ea_raw_wr:7.1f}% | {ea_raw_flat:12.2f} USD | {'-':16}")
for r in [res_v8_no_filter, res_v8_news_filter, res_v9, res_v10, res_v11]:
    print(f"{r['name']:38} | {r['trades']:6} | {r['wr']:7.1f}% | {r['flat_pnl']:12.2f} USD | {r['dyn_pnl']:14.2f} USD")
print("=" * 90)

print("\nPER TAHUN DYNAMIC NET PNL:")
models = [res_v8_no_filter, res_v8_news_filter, res_v9, res_v10, res_v11]
years = sorted(ea["year"].unique())
header = f"{'Year':6} | " + " | ".join([f"{r['name'][:12]:12}" for r in models])
print(header)
print("-" * len(header))
for yr in years:
    row = f"{yr:6} | "
    for r in models:
        row += f"{r['by_year'][yr]['dyn_pnl']:12.2f} | "
    print(row)

print("\nPER TAHUN FLAT NET PNL (0.01 LOT):")
header = f"{'Year':6} | " + " | ".join([f"{r['name'][:12]:12}" for r in models])
print(header)
print("-" * len(header))
for yr in years:
    row = f"{yr:6} | "
    for r in models:
        row += f"{r['by_year'][yr]['flat_pnl']:12.2f} | "
    print(row)
