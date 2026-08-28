"""Uji IN-SAMPLE m03_session_joint: latih dari seluruh 2019-2026 lalu score semua tahun.
Paritas metode dengan scratch/calculate_all_models_reproduced.py (sumber angka 63%/144K)."""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "ValueCell_MT5" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))
sys.stdout.reconfigure(encoding="utf-8")

from train_ml_prediction_v5_unconstrained import build_feature_matrix_v5  # noqa: E402
from train_ml_prediction_v10_walk_forward import select_and_fit_joint_regressor  # noqa: E402
from evaluate_walk_forward_trades import evaluate_scored  # noqa: E402

EXP = Path(__file__).resolve().parents[1] / "ValueCell_MT5" / "python" / "valuecell" / "models" / "saved" / "experiments" / "v12opencode"
V5_PATH = SCRIPT_DIR.parent / "python" / "valuecell" / "models" / "saved" / "filter_latest" / "dataset_v5_unconstrained.csv"
BASE_REF = 4500.0
F_SESSION = ["session_range_exp", "is_prev_high_break", "is_prev_low_break", "session_progress_pct"]

df = pd.read_csv(EXP / "dataset_v12opencode_unconstrained.csv")
v5_cols = set(pd.read_csv(V5_PATH, nrows=0).columns)
keep = [c for c in df.columns if c in v5_cols or c in F_SESSION]
df = df[keep]

ratio = (df["entry_price"] / BASE_REF).clip(lower=1.0 / BASE_REF)
df["mfe_target_norm"] = df["mfe_target"] / ratio
df["mae_target_norm"] = df["mae_target"] / ratio

model_df, _, _ = build_feature_matrix_v5(df)
model_df = model_df.drop(columns=["mfe_target_norm", "mae_target_norm"], errors="ignore")

Y = pd.DataFrame(
    {"MFEnorm": df["mfe_target_norm"].values, "MAEnorm": df["mae_target_norm"].values},
    index=df.index,
)
full_mask = pd.Series(True, index=df.index)

print("Melatih joint model pada SELURUH data 2019-2026 (in-sample parity dengan v8_final)...")
joint_model, scaler, feats, winner = select_and_fit_joint_regressor(model_df, Y, full_mask, "Joint_INSP")
print("Winner:", winner)

preds = joint_model.predict(scaler.transform(model_df[feats]))
pmfe = np.clip(preds[:, 0] * ratio.values, 0.0, None)
pmae = np.clip(preds[:, 1] * ratio.values, 1.0, None)

meta_cols = ["year", "entry_time", "signal", "entry_price", "ea_status", "actual_net_profit"]
for c in ("session_name", "entry_structure", "is_news_blackout", "atr_14_pct"):
    if c in df.columns:
        meta_cols.append(c)
out = df[meta_cols].copy()
out["predicted_mfe"] = pmfe
out["predicted_mae"] = pmae

scored_path = EXP / "runs" / "scored_insample_m03.csv"
out.to_csv(scored_path, index=False)

v8_insample = {"trades": 405, "win_rate": 63.0, "flat_net_pnl": 28759.16, "dynamic_net_pnl": 144075.42}

for thr in (1.05, 1.00):
    r = evaluate_scored(scored_path, f"m03_insample_thr{thr:.2f}", threshold=thr)
    print(f"\n=== IN-SAMPLE threshold {thr:.2f} ===")
    print(f"m03 : tr {r['trades']} | WR {r['win_rate']:.2f}% | flat {r['flat_net_pnl']:.2f} | dyn {r['dynamic_net_pnl']:.2f} | PF {min(r['profit_factor_dynamic'],99):.3f} | DD {r['max_drawdown_dynamic']:.2f}")
    print(f"v8  : tr {v8_insample['trades']} | WR {v8_insample['win_rate']:.2f}% | flat {v8_insample['flat_net_pnl']:.2f} | dyn {v8_insample['dynamic_net_pnl']:.2f}")
