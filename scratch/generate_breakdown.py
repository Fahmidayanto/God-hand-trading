import pandas as pd
import numpy as np

def dynamic_exit_points_pnl(row):
    p_mfe = row["predicted_mfe"]
    p_mae = row["predicted_mae"]
    act_mfe = row["mfe_target"]
    act_mae = row["mae_target"]

    if act_mae >= p_mae and act_mfe >= p_mfe:
        return -p_mae
    elif act_mae >= p_mae:
        return -p_mae
    elif act_mfe >= p_mfe:
        return p_mfe
    else:
        return row["actual_net_profit"] / 0.05

def process_file(file_path, output_md_path, title):
    df_struct = pd.read_csv('D:/Project/Project MT5/Backtest_result/LLHHBOSData_XAUUSD_2020-12-30.csv', skiprows=1)
    df_data = pd.read_csv(file_path)
    
    df_data_2020 = df_data[df_data['year']==2020].copy()
    
    df_struct['Time_std'] = pd.to_datetime(df_struct['Time'].str.replace('.', '-'))
    df_data_2020['entry_time_std'] = pd.to_datetime(df_data_2020['entry_time'])
    
    merged = pd.merge(df_data_2020, df_struct, left_on='entry_time_std', right_on='Time_std', how='inner')
    merged = merged[merged['Type'].isin(['BoS', 'CHoCH', 'BOS'])]
    
    merged["expected_rr"] = merged["predicted_mfe"] / merged["predicted_mae"].clip(lower=1.0)
    
    # Calculate SL and TP prices
    # For BUY: SL = entry - predicted_mae/100, TP = entry + predicted_mfe/100
    # For SELL: SL = entry + predicted_mae/100, TP = entry - predicted_mfe/100
    merged['SL_price'] = np.where(merged['signal'] == 'BUY', 
                                  merged['entry_price'] - (merged['predicted_mae'] / 100.0),
                                  merged['entry_price'] + (merged['predicted_mae'] / 100.0))
    
    merged['TP_price'] = np.where(merged['signal'] == 'BUY', 
                                  merged['entry_price'] + (merged['predicted_mfe'] / 100.0),
                                  merged['entry_price'] - (merged['predicted_mfe'] / 100.0))
    
    # Scenario 4
    merged['s4_active'] = merged['expected_rr'] >= 1.0
    merged['s4_lot'] = np.where(merged['expected_rr'] >= 1.5, 0.08,
                                np.where(merged['expected_rr'] >= 1.2, 0.06,
                                         np.where(merged['expected_rr'] >= 1.0, 0.05, 0.0)))
    merged['s4_pnl_pts'] = merged.apply(dynamic_exit_points_pnl, axis=1)
    merged['s4_profit'] = np.where(merged['s4_active'], 
                                   (merged['s4_pnl_pts'] / 10.0) * (merged['s4_lot'] / 0.1),
                                   0.0)
    
    # Scenario 5
    best_th = 1.05
    merged['s5_active'] = merged['expected_rr'] >= best_th
    merged['s5_lot'] = np.where(merged['expected_rr'] >= 3.0, 0.10,
                                np.where(merged['expected_rr'] >= 1.5, 0.08,
                                         np.where(merged['expected_rr'] >= 1.2, 0.06,
                                                  np.where(merged['expected_rr'] >= 1.05, 0.05, 0.0))))
    merged['s5_profit'] = np.where(merged['s5_active'], 
                                   (merged['s4_pnl_pts'] / 10.0) * (merged['s5_lot'] / 0.1),
                                   0.0)
    
    # Select columns
    res = merged[['entry_time', 'Type', 'signal', 'entry_price', 'SL_price', 'TP_price', 'expected_rr', 'mae_target', 'mfe_target', 's4_active', 's4_lot', 's4_profit', 's5_active', 's5_lot', 's5_profit']].copy()
    res.columns = ['Time', 'Structure', 'Signal', 'Entry', 'SL', 'TP', 'Pred_RR', 'MAE_pts', 'MFE_pts', 'S4_Active', 'S4_Lot', 'S4_Profit', 'S5_Active', 'S5_Lot', 'S5_Profit']
    
    # Sort by time
    res = res.sort_values(by='Time')
    
    # Write markdown table
    with open(output_md_path, 'a') as f:
        f.write(f"\n## {title}\n\n")
        f.write(f"Total entries: {len(res)}\n")
        f.write(f"Scenario 4 Active entries: {res['S4_Active'].sum()}, Total Profit: ${res['S4_Profit'].sum():.2f}\n")
        f.write(f"Scenario 5 Active entries: {res['S5_Active'].sum()}, Total Profit: ${res['S5_Profit'].sum():.2f}\n\n")
        
        f.write("| Time | Structure | Signal | Entry | SL | TP | Pred RR | MAE (pts) | MFE (pts) | S4 Active | S4 Lot | S4 Profit | S5 Active | S5 Lot | S5 Profit |\n")
        f.write("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n")
        for _, r in res.iterrows():
            f.write(f"| {r['Time']} | {r['Structure']} | {r['Signal']} | {r['Entry']:.2f} | {r['SL']:.2f} | {r['TP']:.2f} | {r['Pred_RR']:.2f} | {r['MAE_pts']:.1f} | {r['MFE_pts']:.1f} | {'Yes' if r['S4_Active'] else 'No'} | {r['S4_Lot']:.2f} | ${r['S4_Profit']:.2f} | {'Yes' if r['S5_Active'] else 'No'} | {r['S5_Lot']:.2f} | ${r['S5_Profit']:.2f} |\n")

# Main execution
open('D:/Project/Project MT5/scratch/breakdown_2020.md', 'w').write("# 2020 Trade Breakdown: Scenario 4 and Scenario 5 (v8)\n\n")
process_file('D:/Project/Project MT5/ValueCell_MT5/python/valuecell/models/saved/filter_latest/scored_v8_walk_forward.csv', 
             'D:/Project/Project MT5/scratch/breakdown_2020.md', 
             'Walk-Forward Model (Out-Of-Sample)')
process_file('D:/Project/Project MT5/ValueCell_MT5/python/valuecell/models/saved/filter_latest/scored_v8_final.csv', 
             'D:/Project/Project MT5/scratch/breakdown_2020.md', 
             'Final Model (No-Holdout / Trained on 2017-2026)')
print("Done!")
