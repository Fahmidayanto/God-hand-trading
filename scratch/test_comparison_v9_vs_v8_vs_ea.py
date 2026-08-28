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

# Load Model v8 Final
mfe_v8 = joblib.load(models_dir / 'model_v8_final_mfe.pkl')
scaler_v8_mfe = joblib.load(models_dir / 'scaler_v8_final_mfe.pkl')
mae_v8 = joblib.load(models_dir / 'model_v8_final_mae.pkl')
scaler_v8_mae = joblib.load(models_dir / 'scaler_v8_final_mae.pkl')

# Load Model v9 Final
mfe_v9 = joblib.load(models_dir / 'model_v9_final_mfe.pkl')
scaler_v9_mfe = joblib.load(models_dir / 'scaler_v9_final_mfe.pkl')
mae_v9 = joblib.load(models_dir / 'model_v9_final_mae.pkl')
scaler_v9_mae = joblib.load(models_dir / 'scaler_v9_final_mae.pkl')

# Build feature matrix
model_df, _, _ = build_feature_matrix_v5(df)
price_ratio = (df['entry_price'] / 4500.0).clip(lower=1.0/4500.0)

# Predictions v8
feat_v8_mfe = scaler_v8_mfe.feature_names_in_
feat_v8_mae = scaler_v8_mae.feature_names_in_
pred_v8_mfe = mfe_v8.predict(scaler_v8_mfe.transform(model_df[feat_v8_mfe])) * price_ratio.values
pred_v8_mae = mae_v8.predict(scaler_v8_mae.transform(model_df[feat_v8_mae])) * price_ratio.values
rr_v8 = pred_v8_mfe / np.maximum(1.0, pred_v8_mae)

# Predictions v9
feat_v9_mfe = scaler_v9_mfe.feature_names_in_
feat_v9_mae = scaler_v9_mae.feature_names_in_
pred_v9_mfe = mfe_v9.predict(scaler_v9_mfe.transform(model_df[feat_v9_mfe])) * price_ratio.values
pred_v9_mae = mae_v9.predict(scaler_v9_mae.transform(model_df[feat_v9_mae])) * price_ratio.values
rr_v9 = pred_v9_mfe / np.maximum(1.0, pred_v9_mae)

df['rr_v8'] = rr_v8
df['rr_v9'] = rr_v9

# Threshold R:R gate = 1.05
df['pass_v8'] = df['rr_v8'] >= 1.05
df['pass_v9'] = (df['rr_v9'] >= 1.05) & (df['is_news_blackout'] == 0)

def evaluate_subset(data_subset, name="Subset"):
    print(f"\n=======================================================")
    print(f"=== EVALUASI PER TAHUN: {name} (N = {len(data_subset)}) ===")
    print(f"=======================================================")
    
    years = sorted(data_subset['year'].unique())
    records = []
    
    for y in years:
        sub = data_subset[data_subset['year'] == y]
        
        # 1. Baseline EA Riil (All trades in subset)
        ea_n = len(sub)
        ea_profit = sub['actual_net_profit'].sum()
        ea_wins = (sub['actual_net_profit'] > 0).sum()
        ea_wr = (ea_wins / ea_n * 100) if ea_n > 0 else 0
        
        # 2. Model v8 (Filtered)
        v8_sub = sub[sub['pass_v8']]
        v8_n = len(v8_sub)
        v8_profit = v8_sub['actual_net_profit'].sum()
        v8_wins = (v8_sub['actual_net_profit'] > 0).sum()
        v8_wr = (v8_wins / v8_n * 100) if v8_n > 0 else 0
        
        # 3. Model v9 (Filtered + News Blackout)
        v9_sub = sub[sub['pass_v9']]
        v9_n = len(v9_sub)
        v9_profit = v9_sub['actual_net_profit'].sum()
        v9_wins = (v9_sub['actual_net_profit'] > 0).sum()
        v9_wr = (v9_wins / v9_n * 100) if v9_n > 0 else 0
        
        records.append({
            "Tahun": y,
            "EA_Trades": ea_n,
            "EA_NetProfit": f"{ea_profit:+,.2f}",
            "EA_WR": f"{ea_wr:.1f}%",
            "v8_Trades": v8_n,
            "v8_NetProfit": f"{v8_profit:+,.2f}",
            "v8_WR": f"{v8_wr:.1f}%",
            "v9_Trades": v9_n,
            "v9_NetProfit": f"{v9_profit:+,.2f}",
            "v9_WR": f"{v9_wr:.1f}%",
        })
        
    # TOTAL
    tot_ea_n = len(data_subset)
    tot_ea_profit = data_subset['actual_net_profit'].sum()
    tot_ea_wr = (data_subset['actual_net_profit'] > 0).sum() / tot_ea_n * 100
    
    v8_all = data_subset[data_subset['pass_v8']]
    tot_v8_n = len(v8_all)
    tot_v8_profit = v8_all['actual_net_profit'].sum()
    tot_v8_wr = (v8_all['actual_net_profit'] > 0).sum() / tot_v8_n * 100
    
    v9_all = data_subset[data_subset['pass_v9']]
    tot_v9_n = len(v9_all)
    tot_v9_profit = v9_all['actual_net_profit'].sum()
    tot_v9_wr = (v9_all['actual_net_profit'] > 0).sum() / tot_v9_n * 100
    
    records.append({
        "Tahun": "TOTAL",
        "EA_Trades": tot_ea_n,
        "EA_NetProfit": f"{tot_ea_profit:+,.2f}",
        "EA_WR": f"{tot_ea_wr:.1f}%",
        "v8_Trades": tot_v8_n,
        "v8_NetProfit": f"{tot_v8_profit:+,.2f}",
        "v8_WR": f"{tot_v8_wr:.1f}%",
        "v9_Trades": tot_v9_n,
        "v9_NetProfit": f"{tot_v9_profit:+,.2f}",
        "v9_WR": f"{tot_v9_wr:.1f}%",
    })
    
    res_df = pd.DataFrame(records)
    print(res_df.to_string(index=False))
    
    # Dynamic Lot Calculation
    def calc_dyn(sub_data, col_rr):
        p_list = []
        for _, r in sub_data.iterrows():
            rr_val = r[col_rr]
            p = r['actual_net_profit']
            if rr_val >= 2.0:
                lot = 0.07
            elif rr_val >= 1.5:
                lot = 0.04
            elif rr_val >= 1.2:
                lot = 0.02
            else:
                lot = 0.01
            p_list.append(p * (lot / 0.01))
        return sum(p_list)
    
    print(f"\n--- Ringkasan Profit Finansial (USD) ---")
    print(f"1. Baseline EA Riil (Flat 0.01 Lot) : {tot_ea_profit:+,.2f} USD (WR: {tot_ea_wr:.1f}%)")
    print(f"2. Model v8 (Flat 0.01 Lot)          : {tot_v8_profit:+,.2f} USD (WR: {tot_v8_wr:.1f}%) | Dynamic Lot: {calc_dyn(v8_all, 'rr_v8'):+,.2f} USD")
    print(f"3. Model v9 Terbaru (Flat 0.01 Lot)  : {tot_v9_profit:+,.2f} USD (WR: {tot_v9_wr:.1f}%) | Dynamic Lot: {calc_dyn(v9_all, 'rr_v9'):+,.2f} USD")

# Evaluasi 1: EXECUTED EA Trades (Trades yang benar-benar diambil EA MT5)
ea_executed = df[df['ea_status'] == 'EXECUTED'].copy().reset_index(drop=True)
evaluate_subset(ea_executed, "TRADE EKSEKUSI MT5 RIIL (EXECUTED TRADES)")
