import sys
from pathlib import Path
import pandas as pd
import numpy as np
import joblib

sys.path.insert(0, 'ValueCell_MT5/python')
sys.path.insert(0, 'ValueCell_MT5/scripts')

from train_ml_prediction_v5_unconstrained import build_feature_matrix_v5

models_dir = Path('ValueCell_MT5/python/valuecell/models/saved/filter_latest')

# 1. Load dataset v9
df = pd.read_csv(models_dir / 'dataset_v9_unconstrained.csv')
ea_executed = df[df['ea_status'] == 'EXECUTED'].copy().reset_index(drop=True)

# 2. Load Model v9 Final
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
rr_v9 = pred_v9_mfe / np.maximum(1.0, pred_v9_mae)

ea_executed['rr_v9'] = rr_v9
ea_executed['pass_v9'] = (ea_executed['rr_v9'] >= 1.05) & (ea_executed['is_news_blackout'] == 0)

# Dynamic lot assignment
def get_lot(rr):
    if rr >= 2.0:
        return 0.07
    elif rr >= 1.5:
        return 0.04
    elif rr >= 1.2:
        return 0.02
    else:
        return 0.01

ea_executed['dynamic_lot'] = ea_executed['rr_v9'].apply(get_lot)
ea_executed['dynamic_net_profit'] = ea_executed['actual_net_profit'] * (ea_executed['dynamic_lot'] / 0.01)

years = sorted(ea_executed['year'].unique())
rows = []

for y in years:
    sub_all = ea_executed[ea_executed['year'] == y]
    sub_v9 = sub_all[sub_all['pass_v9']]
    
    # EA Riil
    ea_n = len(sub_all)
    ea_p = sub_all['actual_net_profit'].sum()
    ea_wr = (sub_all['actual_net_profit'] > 0).sum() / ea_n * 100
    
    # ML v9 Flat 0.01
    v9_n = len(sub_v9)
    v9_flat_p = sub_v9['actual_net_profit'].sum()
    v9_wr = (sub_v9['actual_net_profit'] > 0).sum() / v9_n * 100
    
    # ML v9 Dynamic Lot
    v9_dyn_p = sub_v9['dynamic_net_profit'].sum()
    
    rows.append({
        "Tahun": y,
        "EA_Trades": ea_n,
        "EA_Profit_USD": ea_p,
        "EA_WR": ea_wr,
        "v9_Trades": v9_n,
        "v9_Flat_Profit_USD": v9_flat_p,
        "v9_WR": v9_wr,
        "v9_Dyn_Profit_USD": v9_dyn_p,
    })

# Total
tot_ea_n = len(ea_executed)
tot_ea_p = ea_executed['actual_net_profit'].sum()
tot_ea_wr = (ea_executed['actual_net_profit'] > 0).sum() / tot_ea_n * 100

v9_all = ea_executed[ea_executed['pass_v9']]
tot_v9_n = len(v9_all)
tot_v9_flat_p = v9_all['actual_net_profit'].sum()
tot_v9_wr = (v9_all['actual_net_profit'] > 0).sum() / tot_v9_n * 100
tot_v9_dyn_p = v9_all['dynamic_net_profit'].sum()

rows.append({
    "Tahun": "TOTAL",
    "EA_Trades": tot_ea_n,
    "EA_Profit_USD": tot_ea_p,
    "EA_WR": tot_ea_wr,
    "v9_Trades": tot_v9_n,
    "v9_Flat_Profit_USD": tot_v9_flat_p,
    "v9_WR": tot_v9_wr,
    "v9_Dyn_Profit_USD": tot_v9_dyn_p,
})

res_table = pd.DataFrame(rows)
for _, r in res_table.iterrows():
    print(f"{r['Tahun']} | EA: {r['EA_Trades']} trd, {r['EA_Profit_USD']:+10.2f} USD ({r['EA_WR']:5.1f}%) | "
          f"v9 Flat: {r['v9_Trades']} trd, {r['v9_Flat_Profit_USD']:+10.2f} USD ({r['v9_WR']:5.1f}%) | "
          f"v9 Dynamic: {r['v9_Dyn_Profit_USD']:+11.2f} USD")
