"""
Hitung semua skenario Dynamic PnL dari v8 hingga v9.2
Menampilkan persen perubahan relatif terhadap v8 sebagai baseline.
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

t_dt = pd.to_datetime(ea['entry_time'], utc=True)
is_friday_late = (t_dt.dt.weekday == 4) & (t_dt.dt.hour >= 18)
is_monday_open = ((t_dt.dt.weekday == 6) & (t_dt.dt.hour >= 22)) | \
                 ((t_dt.dt.weekday == 0) & (t_dt.dt.hour < 1))
is_weekend_veto = is_friday_late | is_monday_open

# Kolom filter berita & spread
is_news = ea['is_news_blackout'].astype(bool)
spread_pts = ea['spread'].astype(float).values

# R:R Gross (tanpa diskon spread)
rr_gross = pmfe / np.maximum(1.0, pmae)

# R:R Net (diskon spread dari MFE, tambah spread ke MAE)
net_mfe = np.maximum(0.0, pmfe - spread_pts)
net_mae = np.maximum(1.0, pmae + spread_pts)
rr_net = net_mfe / net_mae

def get_lot(r):
    if r >= 2.0: return 0.07
    elif r >= 1.5: return 0.04
    elif r >= 1.2: return 0.02
    elif r >= 1.05: return 0.01
    return 0.0

lots_gross = np.array([get_lot(r) for r in rr_gross])
lots_net   = np.array([get_lot(r) for r in rr_net])

actual_np = ea['actual_net_profit'].values

# ─── SKENARIO ───────────────────────────────────────────────────────────────
# S1: v8 - Gross R:R, TANPA filter berita, TANPA weekend veto
mask_v8 = (rr_gross >= 1.05)
trades_v8 = mask_v8.sum()
pnl_v8 = (actual_np * (lots_gross / 0.01))[mask_v8].sum()

# S2: v9 Awal - Gross R:R, DENGAN filter berita ekonomi SAJA, DENGAN weekend veto
mask_v9a = (rr_gross >= 1.05) & (~is_news) & (~is_weekend_veto)
trades_v9a = mask_v9a.sum()
pnl_v9a = (actual_np * (lots_gross / 0.01))[mask_v9a].sum()

# S3: v9 Full - Gross R:R, filter berita+geopolitik, weekend veto
# (is_news sudah include semua 884 event termasuk geopolitik dari LanceDB)
mask_v9f = mask_v9a  # sama karena is_news sudah gabungan
trades_v9f = trades_v9a
pnl_v9f   = pnl_v9a

# S4: v9 + Diskon Spread - Net R:R, filter berita+geopolitik, weekend veto
mask_v9s = (rr_net >= 1.05) & (~is_news) & (~is_weekend_veto)
trades_v9s = mask_v9s.sum()
pnl_v9s = (actual_np * (lots_net / 0.01))[mask_v9s].sum()

# S5: v9.2 Age Decay (simulasi sederhana: veto trade di jam "stale" strukturnya)
# Pakai kolom bos_age jika tersedia
if 'bos_age_hours' in ea.columns:
    bos_age = ea['bos_age_hours'].astype(float).values
    age_ok = bos_age <= 24.0  # hanya fresh structure <= 24 jam
elif 'distance_to_last_bos_pips' in ea.columns:
    age_ok = np.ones(len(ea), dtype=bool)
else:
    age_ok = np.ones(len(ea), dtype=bool)

mask_v92 = mask_v9s & age_ok
trades_v92 = mask_v92.sum()
pnl_v92 = (actual_np * (lots_net / 0.01))[mask_v92].sum()

# ─── OUTPUT ─────────────────────────────────────────────────────────────────
def win_rate(mask):
    sub = actual_np[mask]
    return (sub > 0).sum() / len(sub) * 100 if len(sub) > 0 else 0.0

def avg_win(mask):
    sub = actual_np[mask]
    wins = sub[sub > 0]
    return wins.mean() if len(wins) > 0 else 0.0

def avg_loss(mask):
    sub = actual_np[mask]
    losses = sub[sub < 0]
    return losses.mean() if len(losses) > 0 else 0.0

# Coba load model v11
pnl_v11 = None
trades_v11 = None
wr_v11 = None
try:
    mfe11 = joblib.load(models_dir / 'model_v11_final_mfe.pkl')
    smfe11 = joblib.load(models_dir / 'scaler_v11_final_mfe.pkl')
    mae11 = joblib.load(models_dir / 'model_v11_final_mae.pkl')
    smae11 = joblib.load(models_dir / 'scaler_v11_final_mae.pkl')

    # Build v11 feature matrix (tambah planned_rr & reject cols)
    v11_extra_cols = ['planned_rr', 'init_risk_points', 'init_reward_points',
                      'reject_group_NONE', 'reject_group_TREND_FILTER_EMA',
                      'reject_group_CYCLE_LIMIT', 'reject_group_UNCONSTRAINED_SIM']
    for col in v11_extra_cols:
        if col not in mdf.columns:
            if col in ea.columns:
                mdf[col] = ea[col].astype(float).values
            else:
                mdf[col] = 0.0

    feat_v11_mfe = smfe11.feature_names_in_
    feat_v11_mae = smae11.feature_names_in_
    pmfe11 = mfe11.predict(smfe11.transform(mdf[feat_v11_mfe])) * pr
    pmae11 = mae11.predict(smae11.transform(mdf[feat_v11_mae])) * pr
    rr_v11 = pmfe11 / np.maximum(1.0, pmae11)
    lots_v11 = np.array([get_lot(r) for r in rr_v11])
    mask_v11 = (rr_v11 >= 1.05) & (~is_news) & (~is_weekend_veto)
    trades_v11 = mask_v11.sum()
    pnl_v11 = (actual_np * (lots_v11 / 0.01))[mask_v11].sum()
    wr_v11 = win_rate(mask_v11)
    avg_w_v11 = avg_win(mask_v11)
    avg_l_v11 = avg_loss(mask_v11)
except Exception as e:
    print(f"[v11 load skip: {e}]")

results = [
    ("v8  (Base, tanpa filter)", mask_v8,  pnl_v8),
    ("v9  Awal (Berita+Weekend)", mask_v9a, pnl_v9a),
    ("v9  Net Spread Broker",     mask_v9s, pnl_v9s),
    ("v9.2 Age Decay (simulasi)", mask_v92, pnl_v92),
]

BASE = pnl_v8
print("="*90)
print(f"{'SKENARIO':<35} {'TRADE':>6} {'WIN RATE':>9} {'AVG WIN':>8} {'AVG LOSS':>9} {'DYNAMIC PnL':>14} {'% vs v8':>8}")
print("="*90)
for name, mask, pnl in results:
    trd  = mask.sum()
    wr   = win_rate(mask)
    aw   = avg_win(mask)
    al   = avg_loss(mask)
    pct  = (pnl - BASE) / abs(BASE) * 100
    pct_str = f"{pct:+.1f}%" if name != "v8  (Base, tanpa filter)" else "baseline"
    print(f"{name:<35} {trd:>6} {wr:>8.1f}% {aw:>+8.1f} {al:>+9.1f} {pnl:>+14,.2f} {pct_str:>8}")

if pnl_v11 is not None:
    pct = (pnl_v11 - BASE) / abs(BASE) * 100
    print(f"{'v11 (Planned R:R + Reject-Aware)':<35} {trades_v11:>6} {wr_v11:>8.1f}% {avg_w_v11:>+8.1f} {avg_l_v11:>+9.1f} {pnl_v11:>+14,.2f} {pct:>+.1f}%")

print("="*90)
print(f"\nBaseline v8: {BASE:+,.2f} USD  |  Kolom AVG WIN/LOSS = rata-rata profit per trade (flat 0.01 lot)")
