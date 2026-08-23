import time
from itertools import product
from multiprocessing import Pool, cpu_count

import importlib.util

spec = importlib.util.spec_from_file_location("gs2", r"B:\Project MT5\scratch\gridsearch_2019_phase2.py")
gs2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gs2)

NET_MIN = 1000.0


def rank_risk(row):
    return (row["dd_pct"], -row["pf"], -row["wr"], -row["net"])


def run_chunk(chunk):
    return [gs2.sim(*c) for c in chunk]


def main():
    t0 = time.time()
    sets, bb, br = gs2.load_all()
    gs2.init_worker(sets, bb, br)
    combos = list(product(gs2.BASE_REF, gs2.TP_D, gs2.TRAIL_D,
                          gs2.MAX_HOLD_H, gs2.TP_EXP_OPTS, gs2.BOS_EXIT_OPTS, gs2.CYCLE))
    rows = []
    for c in combos:
        rows.append(gs2.sim(*c))

    qual = [r for r in rows if r["net"] >= NET_MIN]
    print(f"[GRID] {len(rows)} kombinasi | NetPnL >= {NET_MIN:.0f}: {len(qual)} kombinasi | {time.time()-t0:.1f}s")

    strict = [r for r in qual if r["pf"] >= 1.5]
    pool_sorted = sorted(strict, key=rank_risk)
    fallback = sorted(qual, key=rank_risk)
    use = pool_sorted if len(pool_sorted) >= 5 else fallback
    label = "PF>=1.5" if len(pool_sorted) >= 5 else "tanpa filter PF"

    hdr = (f"{'Rk':<3} {'Base':>6} {'TP':>6} {'Trail':>6} {'Hold':>5} {'TpExp':>6} "
           f"{'BosX':>5} {'Cyc':>4} {'N':>4} {'NetPnL':>9} {'FinalBal':>9} {'DD%':>7} {'PF':>7} {'WR%':>7}")
    print(f"\n=== TOP 10 SETUP TERBAIK DENGAN NET PNL >= {NET_MIN:.0f} (urut DD% asc, PF desc, WR desc) [{label}] ===")
    print(hdr)
    print("-" * len(hdr))
    for i, r in enumerate(use[:10], 1):
        tag = "" if r["pf"] >= 1.5 else "  [PF<1.5]"
        print(f"{i:<3} {r['base']:>6g} {r['tp']:>6g} {r['trail']:>6g} {r['hold']:>5g} {r['tpexp']:>6} "
              f"{r['bosexit']:>5} {r['cycle']:>4} {r['n']:>4} {r['net']:>9.2f} {r['final']:>9.2f} "
              f"{r['dd_pct']:>7.2f} {(f'{r[chr(112)+chr(102)]:.2f}' if r['pf'] != float('inf') else 'inf'):>7} {r['wr']:>7.2f}{tag}")

    base_row = next((r for r in rows if (r["base"], r["tp"], r["trail"], r["hold"],
                                         r["tpexp"], r["bosexit"], r["cycle"]) ==
                    (4025, 100, 10, 24, "on", "on", 2)), None)
    if base_row and base_row["net"] >= NET_MIN:
        pos = next((i for i, r in enumerate(sorted(strict, key=rank_risk), 1)
                    if (r["base"], r["tp"], r["trail"], r["hold"], r["tpexp"], r["bosexit"], r["cycle"]) ==
                    (4025, 100, 10, 24, "on", "on", 2)), None)
        print(f"\nBaseline setting EA saat ini: Net={base_row['net']:.2f} DD={base_row['dd_pct']:.2f}% "
              f"PF={base_row['pf']:.2f} -> peringkat risiko #{pos}" if pos else
              f"\nBaseline setting EA saat ini: Net={base_row['net']:.2f} DD={base_row['dd_pct']:.2f}% PF={base_row['pf']:.2f} (di luar PF>=1.5)")


if __name__ == "__main__":
    main()
