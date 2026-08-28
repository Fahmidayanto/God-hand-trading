import pandas as pd
import numpy as np

df = pd.read_csv('ValueCell_MT5/python/valuecell/models/saved/filter_latest/dataset_v9_unconstrained.csv')
ea_trades = df[df['ea_status'] == 'EXECUTED'].copy()

print(f"=== ANALISIS HUBUNGAN USIA STRUKTUR (last_bos_age_hours) TERHADAP HASIL TRADING ===")
print(f"Total Trade EA yang Dianalisis: {len(ea_trades)} trade\n")

# Binning last_bos_age_hours
# 1. Fresh: <= 4 jam (16 candle M15)
# 2. Moderate: 4 sd 12 jam (16 sd 48 candle M15)
# 3. Aging: 12 sd 24 jam (48 sd 96 candle M15)
# 4. Stale/Basi: > 24 jam (> 96 candle M15 / > 1 hari)

bins = [0, 4, 12, 24, 999]
labels = [
    "1. Fresh (<= 4 Jam / <= 16 Bar)",
    "2. Moderate (4 - 12 Jam / 16 - 48 Bar)",
    "3. Aging (12 - 24 Jam / 48 - 96 Bar)",
    "4. Stale / Basi (> 24 Jam / > 96 Bar)"
]

ea_trades['age_group'] = pd.cut(ea_trades['last_bos_age_hours'], bins=bins, labels=labels, right=True)

# Group analysis
res = ea_trades.groupby('age_group', observed=False).agg(
    total_trades=('actual_net_profit', 'count'),
    win_rate=('actual_net_profit', lambda s: (s > 0).mean() * 100),
    total_net_profit=('actual_net_profit', 'sum'),
    avg_profit_per_trade=('actual_net_profit', 'mean'),
    avg_mfe=('mfe_target', 'mean'),
    avg_mae=('mae_target', 'mean')
).reset_index()

res['rr_ratio'] = res['avg_mfe'] / res['avg_mae']

print(res.to_string(index=False))

# Contoh trade nyata yang gagal karena struktur basi vs berhasil karena struktur fresh
stale_fails = ea_trades[(ea_trades['last_bos_age_hours'] > 24) & (ea_trades['actual_net_profit'] < 0)].head(3)
fresh_wins = ea_trades[(ea_trades['last_bos_age_hours'] <= 4) & (ea_trades['actual_net_profit'] > 0)].head(3)

print("\n--- CONTOH KASUS TRADE NYATA DI DATASET ---")
print("Contoh Trade GAGAL saat Struktur Sudah Basi (> 24 Jam):")
for _, r in stale_fails.iterrows():
    print(f"- Waktu: {r['entry_time']} | Usia BoS: {r['last_bos_age_hours']:.1f} jam | Net Profit: {r['actual_net_profit']:+7.2f} USD | MAE: {r['mae_target']:.0f} pts | MFE: {r['mfe_target']:.0f} pts")

print("\nContoh Trade BERHASIL saat Struktur Masih Segar (<= 4 Jam):")
for _, r in fresh_wins.iterrows():
    print(f"- Waktu: {r['entry_time']} | Usia BoS: {r['last_bos_age_hours']:.1f} jam | Net Profit: {r['actual_net_profit']:+7.2f} USD | MAE: {r['mae_target']:.0f} pts | MFE: {r['mfe_target']:.0f} pts")
