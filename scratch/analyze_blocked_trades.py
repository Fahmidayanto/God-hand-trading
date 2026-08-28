"""
Analisis 28 trade yang diblok v9 tapi diambil v8.
Tujuan: Temukan tuning window blackout yang optimal.
"""
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import joblib

sys.path.insert(0, str(Path('ValueCell_MT5/scripts').resolve()))
from train_ml_prediction_v5_unconstrained import build_feature_matrix_v5

models_dir = Path('ValueCell_MT5/python/valuecell/models/saved/filter_latest')
df = pd.read_csv(models_dir / 'dataset_v9_unconstrained.csv')
ea = df[df['ea_status'] == 'EXECUTED'].copy().reset_index(drop=True)

mfe = joblib.load(models_dir / 'model_v9_final_mfe.pkl')
smfe = joblib.load(models_dir / 'scaler_v9_final_mfe.pkl')
mae = joblib.load(models_dir / 'model_v9_final_mae.pkl')
smae = joblib.load(models_dir / 'scaler_v9_final_mae.pkl')

mdf, _, _ = build_feature_matrix_v5(ea)
pr = (ea['entry_price'] / 4500.0).clip(lower=1.0/4500.0).values
pmfe = mfe.predict(smfe.transform(mdf[smfe.feature_names_in_])) * pr
pmae = mae.predict(smae.transform(mdf[smae.feature_names_in_])) * pr
rr_gross = pmfe / np.maximum(1.0, pmae)

t_dt = pd.to_datetime(ea['entry_time'], utc=True)
is_friday_late = (t_dt.dt.weekday == 4) & (t_dt.dt.hour >= 18)
is_monday_open = ((t_dt.dt.weekday == 6) & (t_dt.dt.hour >= 22)) | ((t_dt.dt.weekday == 0) & (t_dt.dt.hour < 1))
is_weekend_veto = is_friday_late | is_monday_open
is_news = ea['is_news_blackout'].astype(bool)

def get_lot(r):
    if r >= 2.0: return 0.07
    elif r >= 1.5: return 0.04
    elif r >= 1.2: return 0.02
    elif r >= 1.05: return 0.01
    return 0.0

lots = np.array([get_lot(r) for r in rr_gross])
actual_np = ea['actual_net_profit'].values

# Trade yang diblok v9 (news blackout atau weekend) tapi LOLOS v8
mask_v8  = rr_gross >= 1.05
mask_v9  = mask_v8 & (~is_news) & (~is_weekend_veto)
blocked  = mask_v8 & ~mask_v9  # diblok oleh v9

# Breakdown blocked trade: karena news atau weekend?
blocked_news = mask_v8 & is_news & (~is_weekend_veto)
blocked_wknd = mask_v8 & is_weekend_veto

print(f"Total trade diblok v9: {blocked.sum()}")
print(f"  - Karena News Blackout : {blocked_news.sum()}")
print(f"  - Karena Weekend Veto  : {blocked_wknd.sum()}")
print()

# Analisis kualitas trade yang diblok (news saja)
sub_blocked = ea[blocked_news].copy()
sub_blocked['rr'] = rr_gross[blocked_news]
sub_blocked['lot'] = lots[blocked_news]
sub_blocked['dyn_pnl'] = actual_np[blocked_news] * (lots[blocked_news] / 0.01)
sub_blocked_wknd = ea[blocked_wknd].copy()
sub_blocked_wknd['rr'] = rr_gross[blocked_wknd]
sub_blocked_wknd['dyn_pnl'] = actual_np[blocked_wknd] * (lots[blocked_wknd] / 0.01)

# Breakdown per kolom tahun
sub_blocked['year'] = pd.to_datetime(sub_blocked['entry_time'], utc=True).dt.year
sub_blocked_wknd['year'] = pd.to_datetime(sub_blocked_wknd['entry_time'], utc=True).dt.year

print("="*70)
print("TRADE DIBLOK KARENA NEWS BLACKOUT:")
wr_blocked_news = (sub_blocked['actual_net_profit'] > 0).mean() * 100
pnl_blocked_news = sub_blocked['dyn_pnl'].sum()
print(f"  Win Rate  : {wr_blocked_news:.1f}%")
print(f"  Avg W     : +{sub_blocked[sub_blocked['actual_net_profit']>0]['actual_net_profit'].mean():.1f} USD")
print(f"  Avg L     : {sub_blocked[sub_blocked['actual_net_profit']<0]['actual_net_profit'].mean():.1f} USD")
print(f"  Total PnL (flat): {sub_blocked['actual_net_profit'].sum():+.1f} USD")
print(f"  Total PnL (dyn) : {pnl_blocked_news:+.1f} USD")
print()
print("  Per Tahun (News Blocked):")
for yr, grp in sub_blocked.groupby('year'):
    wr = (grp['actual_net_profit'] > 0).mean() * 100
    print(f"    {yr}: {len(grp):3d} trade | WR {wr:.0f}% | PnL flat {grp['actual_net_profit'].sum():+.1f} | dyn {grp['dyn_pnl'].sum():+.1f} USD")

print()
print("="*70)
print("TRADE DIBLOK KARENA WEEKEND VETO:")
if len(sub_blocked_wknd) > 0:
    wr_wknd = (sub_blocked_wknd['actual_net_profit'] > 0).mean() * 100
    pnl_wknd = sub_blocked_wknd['dyn_pnl'].sum()
    print(f"  Win Rate  : {wr_wknd:.1f}%")
    print(f"  Total PnL (dyn): {pnl_wknd:+.1f} USD")
    for yr, grp in sub_blocked_wknd.groupby('year'):
        wr = (grp['actual_net_profit'] > 0).mean() * 100
        print(f"    {yr}: {len(grp):3d} trade | WR {wr:.0f}% | dyn {grp['dyn_pnl'].sum():+.1f} USD")
else:
    print("  Tidak ada trade yang diblok karena weekend saja")

print()
print("="*70)
print("SIMULASI TUNING WINDOW BLACKOUT (±X menit → lebih sempit = lebih banyak trade lolos):")
print("Note: is_news_blackout di CSV sudah fixed ±30 menit. Simulasi ini asumsi")
print("      proporsi trade yang 'dekat batas window' bisa diestimasi.")
print()
print("Pendekatan realistis: Lihat apakah ada kolom 'minutes_to_news' di dataset...")
if 'minutes_to_news' in ea.columns:
    print("  Kolom 'minutes_to_news' TERSEDIA — bisa simulasi window berbeda!")
    for w in [10, 15, 20, 25, 30]:
        close_to_border = (ea['minutes_to_news'].abs() > w) & is_news
        mask_tuned = mask_v8 & (~close_to_border) & (~is_weekend_veto)
        dyn = (actual_np * (lots / 0.01))[mask_tuned].sum()
        wr = (actual_np[mask_tuned] > 0).mean() * 100
        pct = (dyn - (actual_np * (lots/0.01))[mask_v8].sum()) / abs((actual_np * (lots/0.01))[mask_v8].sum()) * 100
        print(f"  Window ±{w:2d} menit → {mask_tuned.sum():3d} trades | WR {wr:.1f}% | Dyn PnL {dyn:+,.0f} USD | {pct:+.1f}% vs v8")
else:
    print("  Kolom 'minutes_to_news' TIDAK ADA di CSV — window hanya bisa diubah di LanceDB query level.")
    print("  Rekomendasi: Kurangi window blackout di check_news_blackout() dari 30 → 15 menit.")
    print()
    # Estimasi berapa trade di area borderline dengan melihat news_blackout rate
    print(f"  Dari {blocked_news.sum()} trade diblok news:")
    print(f"  WR trade terblok = {wr_blocked_news:.1f}%")
    if wr_blocked_news > 55:
        print(f"  ⚠️  Win Rate > 55% — trade yang diblok ini MAJORITY PROFITABLE!")
        print(f"     Window terlalu lebar, bisa diciutkan ke ±15 menit")
    else:
        print(f"  ✅ Win Rate <= 55% — trade yang diblok ini mayoritas rugi, window sudah tepat")
