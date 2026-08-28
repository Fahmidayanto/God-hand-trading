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

# 2. Load Model v9 Final
mfe_v9 = joblib.load(models_dir / 'model_v9_final_mfe.pkl')
scaler_v9_mfe = joblib.load(models_dir / 'scaler_v9_final_mfe.pkl')
mae_v9 = joblib.load(models_dir / 'model_v9_final_mae.pkl')
scaler_v9_mae = joblib.load(models_dir / 'scaler_v9_final_mae.pkl')

# 3. Load Model v10 Final (Multi-Output Joint)
joint_v10 = joblib.load(models_dir / 'model_v10_final_joint.pkl')
scaler_v10 = joblib.load(models_dir / 'scaler_v10_final_joint.pkl')

# Build feature matrix
model_df, _, _ = build_feature_matrix_v5(ea_executed)
price_ratio = (ea_executed['entry_price'] / 4500.0).clip(lower=1.0/4500.0)

# Predictions v9
feat_v9_mfe = scaler_v9_mfe.feature_names_in_
feat_v9_mae = scaler_v9_mae.feature_names_in_
pred_v9_mfe = mfe_v9.predict(scaler_v9_mfe.transform(model_df[feat_v9_mfe])) * price_ratio.values
pred_v9_mae = mae_v9.predict(scaler_v9_mae.transform(model_df[feat_v9_mae])) * price_ratio.values
rr_v9 = pred_v9_mfe / np.maximum(1.0, pred_v9_mae)

# Predictions v10 (Joint)
feat_v10 = scaler_v10.feature_names_in_
preds_v10_norm = joint_v10.predict(scaler_v10.transform(model_df[feat_v10]))
pred_v10_mfe = preds_v10_norm[:, 0] * price_ratio.values
pred_v10_mae = preds_v10_norm[:, 1] * price_ratio.values
rr_v10 = pred_v10_mfe / np.maximum(1.0, pred_v10_mae)

# Check weekend gap conditions (Friday >= 18:00 UTC, Monday < 01:00 UTC)
t_dt = pd.to_datetime(ea_executed['entry_time'], utc=True)
is_friday_late = (t_dt.dt.weekday == 4) & (t_dt.dt.hour >= 18)
is_monday_open = ((t_dt.dt.weekday == 6) & (t_dt.dt.hour >= 22)) | ((t_dt.dt.weekday == 0) & (t_dt.dt.hour < 1))
is_weekend_gap_veto = is_friday_late | is_monday_open

# Filter pass boolean
ea_executed['pass_v9'] = (rr_v9 >= 1.05) & (ea_executed['is_news_blackout'] == 0) & (~is_weekend_gap_veto)
ea_executed['pass_v10'] = (rr_v10 >= 1.05) & (ea_executed['is_news_blackout'] == 0) & (~is_weekend_gap_veto)

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
ea_executed['lot_v9'] = [get_lot(r) if p else 0.0 for r, p in zip(rr_v9, ea_executed['pass_v9'])]
ea_executed['dyn_pnl_v9'] = ea_executed['net_profit'] * (ea_executed['lot_v9'] / 0.01)

ea_executed['lot_v10'] = [get_lot(r) if p else 0.0 for r, p in zip(rr_v10, ea_executed['pass_v10'])]
ea_executed['dyn_pnl_v10'] = ea_executed['net_profit'] * (ea_executed['lot_v10'] / 0.01)

print("\n=== PERBANDINGAN PER TAHUN: EA vs MODEL v9 vs MODEL v10 (MULTI-OUTPUT JOINT) ===")
years = sorted(ea_executed['year'].unique())

tot_ea_trd, tot_ea_pnl, tot_ea_wins = 0, 0, 0
tot_v9_trd, tot_v9_pnl, tot_v9_dyn, tot_v9_wins = 0, 0, 0, 0
tot_v10_trd, tot_v10_pnl, tot_v10_dyn, tot_v10_wins = 0, 0, 0, 0

for yr in years:
    sub = ea_executed[ea_executed['year'] == yr]
    
    # EA baseline
    ea_trd = len(sub)
    ea_pnl = sub['net_profit'].sum()
    ea_wr = (sub['net_profit'] > 0).mean() * 100
    
    # v9
    sub_v9 = sub[sub['pass_v9']]
    v9_trd = len(sub_v9)
    v9_pnl = sub_v9['net_profit'].sum()
    v9_dyn = sub_v9['dyn_pnl_v9'].sum()
    v9_wr = (sub_v9['net_profit'] > 0).mean() * 100 if v9_trd > 0 else 0
    
    # v10
    sub_v10 = sub[sub['pass_v10']]
    v10_trd = len(sub_v10)
    v10_pnl = sub_v10['net_profit'].sum()
    v10_dyn = sub_v10['dyn_pnl_v10'].sum()
    v10_wr = (sub_v10['net_profit'] > 0).mean() * 100 if v10_trd > 0 else 0
    
    tot_ea_trd += ea_trd
    tot_ea_pnl += ea_pnl
    tot_ea_wins += (sub['net_profit'] > 0).sum()
    
    tot_v9_trd += v9_trd
    tot_v9_pnl += v9_pnl
    tot_v9_dyn += v9_dyn
    tot_v9_wins += (sub_v9['net_profit'] > 0).sum()
    
    tot_v10_trd += v10_trd
    tot_v10_pnl += v10_pnl
    tot_v10_dyn += v10_dyn
    tot_v10_wins += (sub_v10['net_profit'] > 0).sum()
    
    print(f"{yr} | EA: {ea_trd:3d} trd, {ea_pnl:+9.2f} USD ({ea_wr:4.1f}%) | v9 Flat: {v9_trd:3d} trd, {v9_pnl:+9.2f} USD ({v9_wr:4.1f}%) | v10 Flat: {v10_trd:3d} trd, {v10_pnl:+9.2f} USD ({v10_wr:4.1f}%) | v10 Dyn: {v10_dyn:+11.2f} USD")

print(f"TOTAL | EA: {tot_ea_trd:3d} trd, {tot_ea_pnl:+9.2f} USD ({(tot_ea_wins/tot_ea_trd)*100:4.1f}%) | v9 Flat: {tot_v9_trd:3d} trd, {tot_v9_pnl:+9.2f} USD ({(tot_v9_wins/tot_v9_trd)*100:4.1f}%) | v10 Flat: {tot_v10_trd:3d} trd, {tot_v10_pnl:+9.2f} USD ({(tot_v10_wins/tot_v10_trd)*100:4.1f}%) | v10 Dyn: {tot_v10_dyn:+11.2f} USD")
