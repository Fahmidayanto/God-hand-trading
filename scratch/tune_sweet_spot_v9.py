import sys
from pathlib import Path
import pandas as pd
import numpy as np
import joblib

sys.path.insert(0, 'ValueCell_MT5/scripts')
sys.path.insert(0, 'ValueCell_MT5/python')
from train_ml_prediction_v5_unconstrained import build_feature_matrix_v5

models_dir = Path('ValueCell_MT5/python/valuecell/models/saved/filter_latest')

# Load Dataset v9
df = pd.read_csv(models_dir / 'dataset_v9_unconstrained.csv')
ea_executed = df[df['ea_status'] == 'EXECUTED'].copy().reset_index(drop=True)

# Load Model v9 Final
mfe_v9 = joblib.load(models_dir / 'model_v9_final_mfe.pkl')
scaler_v9_mfe = joblib.load(models_dir / 'scaler_v9_final_mfe.pkl')
mae_v9 = joblib.load(models_dir / 'model_v9_final_mae.pkl')
scaler_v9_mae = joblib.load(models_dir / 'scaler_v9_final_mae.pkl')

model_df, _, _ = build_feature_matrix_v5(ea_executed)
price_ratio = (ea_executed['entry_price'] / 4500.0).clip(lower=1.0/4500.0)

feat_v9_mfe = scaler_v9_mfe.feature_names_in_
feat_v9_mae = scaler_v9_mae.feature_names_in_
pred_v9_mfe = mfe_v9.predict(scaler_v9_mfe.transform(model_df[feat_v9_mfe])) * price_ratio.values
pred_v9_mae = mae_v9.predict(scaler_v9_mae.transform(model_df[feat_v9_mae])) * price_ratio.values

# Weekend gap
t_dt = pd.to_datetime(ea_executed['entry_time'], utc=True)
is_friday_late = (t_dt.dt.weekday == 4) & (t_dt.dt.hour >= 18)
is_monday_open = ((t_dt.dt.weekday == 6) & (t_dt.dt.hour >= 22)) | ((t_dt.dt.weekday == 0) & (t_dt.dt.hour < 1))
is_weekend_gap_veto = is_friday_late | is_monday_open

bos_age = ea_executed['last_bos_age_hours'].fillna(999.0).values
spread_pts = ea_executed['spread'].astype(float).values
ea_executed['net_profit'] = ea_executed['actual_net_profit']

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

def eval_config(name, spread_deduct, max_spread, age_threshold_hours, age_max_penalty):
    if spread_deduct:
        net_mfe = np.maximum(0.0, pred_v9_mfe - spread_pts)
        net_mae = np.maximum(1.0, pred_v9_mae + spread_pts)
    else:
        net_mfe = np.maximum(0.0, pred_v9_mfe)
        net_mae = np.maximum(1.0, pred_v9_mae)
    
    base_rr = net_mfe / net_mae
    
    if age_threshold_hours > 0:
        age_penalty = np.maximum(0.0, (bos_age - age_threshold_hours) / 48.0) * age_max_penalty
        rr = base_rr - age_penalty
    else:
        rr = base_rr
        
    mask = (rr >= 1.05) & (ea_executed['is_news_blackout'] == 0) & (~is_weekend_gap_veto) & (spread_pts <= max_spread)
    
    sub = ea_executed[mask]
    n_trd = len(sub)
    win_trd = (sub['net_profit'] > 0).sum()
    wr = (win_trd / n_trd) * 100 if n_trd > 0 else 0
    pnl_flat = sub['net_profit'].sum()
    profit_per_trd = pnl_flat / n_trd if n_trd > 0 else 0
    
    lots = [get_lot(r) for r in rr[mask]]
    pnl_dyn = (sub['net_profit'] * (np.array(lots) / 0.01)).sum()
    
    print(f"[{name}]")
    print(f"  • Total Trade     : {n_trd:3d} trade")
    print(f"  • Win Rate        : {wr:5.2f}%")
    print(f"  • Net Profit Flat : {pnl_flat:+10.2f} USD")
    print(f"  • Profit / Trade  : {profit_per_trd:+10.2f} USD")
    print(f"  • Net Profit Dyn  : {pnl_dyn:+10.2f} USD\n")

print("=== PENCARIAN TITIK KESEIMBANGAN (SWEET SPOT) MODEL v9 ===\n")
eval_config("A. v9 Asli (Tanpa Penalti Spread & Usia)", spread_deduct=False, max_spread=999, age_threshold_hours=0, age_max_penalty=0.0)
eval_config("B. v9 Konservatif Ketat (Spread 35 + Age Decay 12h)", spread_deduct=True, max_spread=35, age_threshold_hours=12, age_max_penalty=0.15)
eval_config("C. v9 Sweet Spot Ringan (Spread 50 + Age Decay 24h/0.08)", spread_deduct=True, max_spread=50, age_threshold_hours=24, age_max_penalty=0.08)
eval_config("D. v9 Sweet Spot Ultra-Optimal (Spread 60 + Age Decay 36h/0.05)", spread_deduct=True, max_spread=60, age_threshold_hours=36, age_max_penalty=0.05)
