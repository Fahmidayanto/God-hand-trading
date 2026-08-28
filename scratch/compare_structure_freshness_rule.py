import sys
from pathlib import Path
import pandas as pd
import numpy as np
import joblib

sys.path.insert(0, 'ValueCell_MT5/scripts')
sys.path.insert(0, 'ValueCell_MT5/python')
from train_ml_prediction_v5_unconstrained import build_feature_matrix_v5

models_dir = Path('ValueCell_MT5/python/valuecell/models/saved/filter_latest')

# 1. Load Dataset v9
df = pd.read_csv(models_dir / 'dataset_v9_unconstrained.csv')
ea_executed = df[df['ea_status'] == 'EXECUTED'].copy().reset_index(drop=True)

# 2. Load Model v9 Final (Ridge MFE + RF MAE)
mfe_v9 = joblib.load(models_dir / 'model_v9_final_mfe.pkl')
scaler_v9_mfe = joblib.load(models_dir / 'scaler_v9_final_mfe.pkl')
mae_v9 = joblib.load(models_dir / 'model_v9_final_mae.pkl')
scaler_v9_mae = joblib.load(models_dir / 'scaler_v9_final_mae.pkl')

# Build feature matrix
model_df, _, _ = build_feature_matrix_v5(ea_executed)
price_ratio = (ea_executed['entry_price'] / 4500.0).clip(lower=1.0/4500.0)

# Predictions v9
feat_v9_mfe = scaler_v9_mfe.feature_names_in_
feat_v9_mae = scaler_v9_mae.feature_names_in_
pred_v9_mfe = mfe_v9.predict(scaler_v9_mfe.transform(model_df[feat_v9_mfe])) * price_ratio.values
pred_v9_mae = mae_v9.predict(scaler_v9_mae.transform(model_df[feat_v9_mae])) * price_ratio.values

# Spread penalty & Net R:R (spread in dataset is already points)
spread_pts = ea_executed['spread'].astype(float)
net_mfe = np.maximum(0.0, pred_v9_mfe - spread_pts.values)
net_mae = np.maximum(1.0, pred_v9_mae + spread_pts.values)
rr_v9 = net_mfe / net_mae

# Weekend gap veto
t_dt = pd.to_datetime(ea_executed['entry_time'], utc=True)
is_friday_late = (t_dt.dt.weekday == 4) & (t_dt.dt.hour >= 18)
is_monday_open = ((t_dt.dt.weekday == 6) & (t_dt.dt.hour >= 22)) | ((t_dt.dt.weekday == 0) & (t_dt.dt.hour < 1))
is_weekend_gap_veto = is_friday_late | is_monday_open

# Base v9 filter (No Age Filter)
pass_base = (rr_v9 >= 1.05) & (ea_executed['is_news_blackout'] == 0) & (~is_weekend_gap_veto) & (spread_pts <= 35.0)

# Filter with Structure Age Rules:
# Rule 1: Max BoS Age <= 48 Jam (2 Hari)
bos_age = ea_executed['last_bos_age_hours'].fillna(999.0)
pass_age_48h = pass_base & (bos_age <= 48.0)

# Rule 2: Max BoS Age <= 36 Jam (1.5 Hari)
pass_age_36h = pass_base & (bos_age <= 36.0)

# Rule 3: Dynamic Decay (Diskon R:R jika usia > 12 jam)
age_penalty = np.maximum(0.0, (bos_age.values - 12.0) / 48.0) * 0.15
rr_decay = rr_v9 - age_penalty
pass_age_decay = (rr_decay >= 1.05) & (ea_executed['is_news_blackout'] == 0) & (~is_weekend_gap_veto) & (spread_pts <= 35.0)

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

ea_executed['net_profit'] = ea_executed['actual_net_profit']

variants = {
    "1. Model v9 Standar (Tanpa Rule Usia)": pass_base,
    "2. Model v9 + Fresh Rule (Max 48 Jam)": pass_age_48h,
    "3. Model v9 + Fresh Rule (Max 36 Jam)": pass_age_36h,
    "4. Model v9 + Dynamic Age Decay": pass_age_decay
}

print("=== HASIL KOMPARASI LENGKAP: MODEL v9 TANPA RULE USIA vs DENGAN RULE USIA STRUKTUR ===")
print("Rentang Data: 2019 - 2026 (Total 803 Trade EA Riil)\n")

for name, mask in variants.items():
    sub = ea_executed[mask]
    n_trd = len(sub)
    win_trd = (sub['net_profit'] > 0).sum()
    wr = (win_trd / n_trd) * 100 if n_trd > 0 else 0
    pnl_flat = sub['net_profit'].sum()
    profit_per_trd = pnl_flat / n_trd if n_trd > 0 else 0
    
    lots = [get_lot(r) for r in rr_v9[mask]]
    pnl_dyn = (sub['net_profit'] * (np.array(lots) / 0.01)).sum()
    
    print(f"[{name}]")
    print(f"  • Total Trade     : {n_trd:3d} trade (Menyaring {803 - n_trd} trade sampah)")
    print(f"  • Win Rate        : {wr:5.2f}%")
    print(f"  • Net Profit Flat : {pnl_flat:+10.2f} USD")
    print(f"  • Profit / Trade  : {profit_per_trd:+10.2f} USD")
    print(f"  • Net Profit Dyn  : {pnl_dyn:+10.2f} USD\n")

print("--- PERBANDINGAN PER TAHUN (Flat 0.01 Lot) ---")
years = sorted(ea_executed['year'].unique())
for yr in years:
    sub_yr = ea_executed[ea_executed['year'] == yr]
    
    pnl_std = sub_yr[pass_base[ea_executed['year'] == yr]]['net_profit'].sum()
    wr_std = (sub_yr[pass_base[ea_executed['year'] == yr]]['net_profit'] > 0).mean() * 100
    
    pnl_opt = sub_yr[pass_age_48h[ea_executed['year'] == yr]]['net_profit'].sum()
    wr_opt = (sub_yr[pass_age_48h[ea_executed['year'] == yr]]['net_profit'] > 0).mean() * 100
    
    print(f"{yr} | v9 Standar: {pnl_std:+8.1f} USD ({wr_std:4.1f}%) | v9 + Fresh Rule (48h): {pnl_opt:+8.1f} USD ({wr_opt:4.1f}%)")
