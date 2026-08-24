"""Uji 3 opsi konfigurasi ML gate di atas trade EXECUTED EA (walk-forward OOS).

Opsi 1: Grid threshold RR (ML gate aktif semua tahun).
Opsi 2: ML gate aktif hanya jika fold punya >= MIN_SAMPLES sampel training.
Opsi 3: Kombinasi threshold optimal + min-samples.
"""

from __future__ import annotations

import pandas as pd

SCORED = r"..\python\valuecell\models\saved\filter_latest\scored_v8_walk_forward.csv"
MIN_SAMPLES = 1000


def main() -> None:
    df = pd.read_csv(SCORED)
    df["expected_rr"] = df["predicted_mfe"] / df["predicted_mae"].clip(lower=1.0)
    ea = df[df["ea_status"].str.upper() == "EXECUTED"].copy()
    ea["year"] = ea["year"].astype(int)
    ea_pnl_total = round(ea["actual_net_profit"].sum(), 2)
    n_ea = len(ea)

    print("=== OPSI 1: Grid Threshold RR (ML gate aktif semua tahun) ===")
    print(f"{'thr':>5} | {'trades':>6} | {'pnl':>10} | {'vs EA':>9} | {'pnl/trade':>9}")
    print(f"{'EA':>5} | {n_ea:>6} | {ea_pnl_total:>10.2f} | {'-':>9} | {ea_pnl_total / n_ea:>9.2f}")
    best_thr = None
    for thr in [0.8, 1.0, 1.2, 1.4, 1.5, 1.65, 1.8, 2.0, 2.25, 2.5]:
        keep = ea[ea["expected_rr"] >= thr]
        pnl = round(keep["actual_net_profit"].sum(), 2)
        diff = round(pnl - ea_pnl_total, 2)
        print(f"{thr:>5} | {len(keep):>6} | {pnl:>10.2f} | {diff:>+9.2f} | {pnl / max(len(keep), 1):>9.2f}")
        if best_thr is None or pnl > best_thr[1]:
            best_thr = (thr, pnl, len(keep))
    print(f"\nOpsi 1 optimal: threshold={best_thr[0]} | PnL={best_thr[1]} | trades={best_thr[2]}\n")

    print(f"=== OPSI 2: ML gate aktif hanya untuk fold >= {MIN_SAMPLES} sampel training ===")
    for min_n in [500, 742, 1000, 1274]:
        active = ea["fold_train_samples"] >= min_n
        keep_mask = (~active) | (ea["expected_rr"] >= 1.2)  # fold kecil: lolos semua
        keep = ea[keep_mask]
        pnl = round(keep["actual_net_profit"].sum(), 2)
        diff = round(pnl - ea_pnl_total, 2)
        print(f"min_samples={min_n:>5} | trades={len(keep):>4} | PnL={pnl:>10.2f} | vs EA={diff:>+9.2f}")
    print()

    print("=== OPSI 3: Kombinasi threshold x min-samples ===")
    combos = []
    for thr in [1.0, 1.2, 1.4, 1.5, 1.65, 1.8, 2.0]:
        for min_n in [0, 500, 742, 1000, 1274]:
            active = ea["fold_train_samples"] >= min_n
            keep_mask = (~active) | (ea["expected_rr"] >= thr)
            keep = ea[keep_mask]
            pnl = round(keep["actual_net_profit"].sum(), 2)
            combos.append((thr, min_n, len(keep), pnl))
    combos.sort(key=lambda x: -x[3])
    print(f"{'thr':>5} | {'min_n':>5} | {'trades':>6} | {'pnl':>10} | {'vs EA':>9}")
    for thr, min_n, n, pnl in combos[:8]:
        diff = round(pnl - ea_pnl_total, 2)
        print(f"{thr:>5} | {min_n:>5} | {n:>6} | {pnl:>10.2f} | {diff:>+9.2f}")

    # Detail per tahun untuk kombinasi terbaik
    b_thr, b_min, _, _ = combos[0]
    active = ea["fold_train_samples"] >= b_min
    ea["_keep"] = (~active) | (ea["expected_rr"] >= b_thr)
    print(f"\n=== Detail per tahun kombinasi terbaik (thr={b_thr}, min_n={b_min}) ===")
    g = ea.groupby("year").apply(
        lambda x: pd.Series({
            "ea_trades": len(x),
            "ea_pnl": round(x["actual_net_profit"].sum(), 2),
            "kept": int(x["_keep"].sum()),
            "kept_pnl": round(x.loc[x["_keep"], "actual_net_profit"].sum(), 2),
        }),
        include_groups=False,
    )
    print(g.to_string())
    print(f"\nEA baseline: {ea_pnl_total} USD")


if __name__ == "__main__":
    main()
