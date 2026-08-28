"""Hitung flat PnL (0.01 lot fixed) per skenario untuk catatan Obsidian."""
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
mae_m = joblib.load(models_dir / 'model_v9_final_mae.pkl')
smae = joblib.load(models_dir / 'scaler_v9_final_mae.pkl')

mdf, _, _ = build_feature_matrix_v5(ea)
pr = (ea['entry_price'] / 4500.0).clip(lower=1.0/4500.0).values
pmfe = mfe.predict(smfe.transform(mdf[smfe.feature_names_in_])) * pr
pmae = mae_m.predict(smae.transform(mdf[smae.feature_names_in_])) * pr
rr_gross = pmfe / np.maximum(1.0, pmae)

spread_pts = ea['spread'].astype(float).values
net_mfe_v = np.maximum(0.0, pmfe - spread_pts)
net_mae_v = np.maximum(1.0, pmae + spread_pts)
rr_net = net_mfe_v / net_mae_v

t_dt = pd.to_datetime(ea['entry_time'], utc=True)
is_friday_late = (t_dt.dt.weekday == 4) & (t_dt.dt.hour >= 18)
is_monday_open = ((t_dt.dt.weekday == 6) & (t_dt.dt.hour >= 22)) | ((t_dt.dt.weekday == 0) & (t_dt.dt.hour < 1))
is_weekend_veto = is_friday_late | is_monday_open
is_news = ea['is_news_blackout'].astype(bool)
actual_np = ea['actual_net_profit'].values

mask_v8  = rr_gross >= 1.05
mask_v9a = mask_v8 & (~is_news) & (~is_weekend_veto)
mask_v9s = (rr_net >= 1.05) & (~is_news) & (~is_weekend_veto)

def stats(mask):
    sub = actual_np[mask]
    wr = (sub > 0).mean() * 100
    flat_pnl = sub.sum()
    wins = sub[sub > 0]
    losses = sub[sub < 0]
    avg_w = wins.mean() if len(wins) > 0 else 0.0
    avg_l = losses.mean() if len(losses) > 0 else 0.0
    return len(sub), wr, flat_pnl, avg_w, avg_l

# EA raw (semua trade tanpa filter ML)
ea_all = df[df['ea_status'] == 'EXECUTED']
ea_n, ea_wr, ea_flat, ea_aw, ea_al = stats(np.ones(len(actual_np), dtype=bool))

print("=== FLAT PnL (0.01 lot fixed) ===")
for name, mask in [
    ("EA Raw (no ML)", np.ones(len(actual_np), dtype=bool)),
    ("v8 (Gross RR, no filter)", mask_v8),
    ("v9 Awal (Berita+Weekend Veto)", mask_v9a),
    ("v9 Net Spread Broker", mask_v9s),
]:
    n, wr, flat, aw, al = stats(mask)
    print(f"{name:<35} | {n:>3} trd | WR {wr:.1f}% | Flat PnL {flat:+,.1f} | AvgW {aw:+.1f} | AvgL {al:+.1f}")

# v11
try:
    mfe11 = joblib.load(models_dir / 'model_v11_final_mfe.pkl')
    smfe11 = joblib.load(models_dir / 'scaler_v11_final_mfe.pkl')
    mae11 = joblib.load(models_dir / 'model_v11_final_mae.pkl')
    smae11 = joblib.load(models_dir / 'scaler_v11_final_mae.pkl')
    v11_extra = ['planned_rr','init_risk_points','init_reward_points',
                 'reject_group_NONE','reject_group_TREND_FILTER_EMA',
                 'reject_group_CYCLE_LIMIT','reject_group_UNCONSTRAINED_SIM']
    for col in v11_extra:
        if col not in mdf.columns:
            mdf[col] = ea[col].astype(float).values if col in ea.columns else 0.0
    pmfe11 = mfe11.predict(smfe11.transform(mdf[smfe11.feature_names_in_])) * pr
    pmae11 = mae11.predict(smae11.transform(mdf[smae11.feature_names_in_])) * pr
    rr11 = pmfe11 / np.maximum(1.0, pmae11)
    mask_v11 = (rr11 >= 1.05) & (~is_news) & (~is_weekend_veto)
    n, wr, flat, aw, al = stats(mask_v11)
    print(f"{'v11 (Planned RR + Reject-Aware)':<35} | {n:>3} trd | WR {wr:.1f}% | Flat PnL {flat:+,.1f} | AvgW {aw:+.1f} | AvgL {al:+.1f}")
except Exception as e:
    print(f"[v11 skip: {e}]")
