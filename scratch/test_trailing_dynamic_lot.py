import pandas as pd
import numpy as np

# Load scored walk-forward dataset (Out-of-Sample 2020-2026)
df = pd.read_csv('ValueCell_MT5/python/valuecell/models/saved/filter_latest/scored_v8_walk_forward.csv')

# Only consider trades executed by EA with real MT5 Trailing Stop
executed_df = df[df['ea_status'] == 'EXECUTED'].copy()
executed_df['expected_rr'] = executed_df['predicted_mfe'] / executed_df['predicted_mae'].clip(lower=1.0)

def get_lot_extended(rr, threshold=1.05):
    if rr < threshold:
        return 0.0
    elif rr < 1.5:
        return 0.05
    elif rr < 2.0:
        return 0.06
    elif rr < 3.0:
        return 0.08
    else:
        return 0.10

def get_lot_conservative(rr, threshold=1.05):
    if rr < threshold:
        return 0.0
    elif rr < 1.5:
        return 0.05
    elif rr < 2.2:
        return 0.06
    else:
        return 0.075

executed_df['lot_ext'] = executed_df['expected_rr'].apply(get_lot_extended)
executed_df['profit_ext'] = executed_df['actual_net_profit'] * (executed_df['lot_ext'] / 0.05)

executed_df['lot_cons'] = executed_df['expected_rr'].apply(get_lot_conservative)
executed_df['profit_cons'] = executed_df['actual_net_profit'] * (executed_df['lot_cons'] / 0.05)

executed_df['lot_flat'] = executed_df['expected_rr'].apply(lambda rr: 0.05 if rr >= 1.05 else 0.0)
executed_df['profit_flat'] = executed_df['actual_net_profit'] * (executed_df['lot_flat'] / 0.05)

def calc_metrics(series):
    equity = series.cumsum()
    peak = equity.cummax()
    dd = float((equity - peak).min())
    gross_win = series[series > 0].sum()
    gross_loss = abs(series[series < 0].sum())
    pf = gross_win / gross_loss if gross_loss > 0 else 999.0
    wr = (series > 0).sum() / (series != 0).sum() * 100 if (series != 0).sum() > 0 else 0.0
    return pf, dd, wr

print("\n" + "=" * 90)
print(f"{'Tahun':6} | {'Trades':6} | {'Flat Lot 0.05':16} | {'Dynamic Konservatif':22} | {'Dynamic Extended':20}")
print("=" * 90)

for y, grp in executed_df.groupby('year'):
    trades = (grp['lot_ext'] > 0).sum()
    p_flat = grp['profit_flat'].sum()
    p_cons = grp['profit_cons'].sum()
    p_ext = grp['profit_ext'].sum()
    print(f"{y:<6} | {trades:<6} | {p_flat:>12.2f} USD | {p_cons:>18.2f} USD | {p_ext:>16.2f} USD")

print("-" * 90)
t_trades = (executed_df['lot_ext'] > 0).sum()
t_flat = executed_df['profit_flat'].sum()
t_cons = executed_df['profit_cons'].sum()
t_ext = executed_df['profit_ext'].sum()
print(f"{'TOTAL':<6} | {t_trades:<6} | {t_flat:>12.2f} USD | {t_cons:>18.2f} USD | {t_ext:>16.2f} USD")
print("=" * 90 + "\n")

pf_flat, dd_flat, wr_flat = calc_metrics(executed_df['profit_flat'])
pf_cons, dd_cons, wr_cons = calc_metrics(executed_df['profit_cons'])
pf_ext, dd_ext, wr_ext = calc_metrics(executed_df['profit_ext'])

print(f"1. Flat 0.05 Lot           : Net Profit={t_flat:.2f} USD | Profit Factor={pf_flat:.2f} | Max DD={dd_flat:.2f} USD | Win Rate={wr_flat:.1f}%")
print(f"2. Dynamic Konservatif     : Net Profit={t_cons:.2f} USD | Profit Factor={pf_cons:.2f} | Max DD={dd_cons:.2f} USD | Win Rate={wr_cons:.1f}%")
print(f"3. Dynamic Extended        : Net Profit={t_ext:.2f} USD  | Profit Factor={pf_ext:.2f} | Max DD={dd_ext:.2f} USD | Win Rate={wr_ext:.1f}%")
