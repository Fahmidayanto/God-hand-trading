"""Validasi anti-overfit konfigurasi ML gate (thr=1.0, min_n=500).

Cek 1: Sensitivitas threshold di zona tetangga (0.9-1.2).
Cek 2: Stabilitas antar rezim (split paruh waktu).
Cek 3: Bootstrap 200x untuk confidence interval profit delta.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

SCORED = r"..\python\valuecell\models\saved\filter_latest\scored_v8_walk_forward.csv"


def main() -> None:
    df = pd.read_csv(SCORED)
    df["expected_rr"] = df["predicted_mfe"] / df["predicted_mae"].clip(lower=1.0)
    ea = df[df["ea_status"].str.upper() == "EXECUTED"].copy()
    ea["year"] = ea["year"].astype(int)
    base = ea["actual_net_profit"].sum()

    print("=== CEK 1: Sensitivitas threshold (min_n=500) ===")
    active = ea["fold_train_samples"] >= 500
    for thr in [0.9, 0.95, 1.0, 1.05, 1.1, 1.15, 1.2]:
        keep = ea[(~active) | (ea["expected_rr"] >= thr)]
        pnl = keep["actual_net_profit"].sum()
        print(f"thr={thr:>5} | PnL={pnl:>10.2f} | vs EA={pnl - base:>+9.2f}")
    print()

    print("=== CEK 2: Stabilitas antar rezim (thr=1.0, min_n=500) ===")
    ea["_keep"] = (~active) | (ea["expected_rr"] >= 1.0)
    for label, mask in [("Awal 2020-2022", ea["year"] <= 2022), ("Akhir 2023-2026", ea["year"] >= 2023)]:
        sub = ea[mask]
        ea_pnl = sub["actual_net_profit"].sum()
        kept_pnl = sub.loc[sub["_keep"], "actual_net_profit"].sum()
        print(f"{label}: EA={ea_pnl:>9.2f} | EA+ML={kept_pnl:>9.2f} | delta={kept_pnl - ea_pnl:>+8.2f}")
    print()

    print("=== CEK 3: Bootstrap 200x (zona gate aktif, tahun >= 2022) ===")
    rng = np.random.default_rng(42)
    sub = ea[active & (ea["year"] >= 2022)]
    deltas = []
    for _ in range(200):
        idx = rng.choice(len(sub), size=len(sub), replace=True)
        s = sub.iloc[idx]
        d = s.loc[s["_keep"], "actual_net_profit"].sum() - s["actual_net_profit"].sum()
        deltas.append(d)
    deltas = pd.Series(deltas)
    print(f"delta mean={deltas.mean():.2f} | median={deltas.median():.2f}")
    print(f"P5={deltas.quantile(0.05):.2f} | P95={deltas.quantile(0.95):.2f}")
    print(f"P(delta > 0) = {(deltas > 0).mean() * 100:.1f}% (probabilitas gate menambah profit)")


if __name__ == "__main__":
    main()
