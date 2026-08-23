import time
from itertools import product

import importlib.util

spec = importlib.util.spec_from_file_location("gs3", r"B:\Project MT5\scratch\gridsearch_2019_phase3.py")
gs3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gs3)

trades, bb, br = gs3.load_all()
gs3.init_worker(trades, bb, br)

BASES = [3950, 4000, 4025, 4050]
TPS = [95, 100, 105]
TRAILS = [10, 15, 20, 25, 30, 40]
HOLDS = [24, 36, 48]

rows = []
t0 = time.time()
for b, t, tr_, h in product(BASES, TPS, TRAILS, HOLDS):
    r_fav = gs3.sim(b, t, tr_, h, "off", "off", "fav_first")
    r_adv = gs3.sim(b, t, tr_, h, "off", "off", "adv_first")
    rows.append({
        "base": b, "tp": t, "trail": tr_, "hold": h,
        "net_fav": r_fav["net"], "net_adv": r_adv["net"],
        "blend": round((r_fav["net"] + r_adv["net"]) / 2.0, 2),
        "worst": min(r_fav["net"], r_adv["net"]),
        "dd_fav": r_fav["dd_pct"], "dd_adv": r_adv["dd_pct"],
        "pf_fav": r_fav["pf"], "pf_adv": r_adv["pf"],
    })

print(f"[EVAL] {len(rows)} kombinasi x 2 model | {time.time()-t0:.1f}s")

both_pos = [r for r in rows if r["net_fav"] > 0 and r["net_adv"] > 0]
print(f"Positif di kedua model: {len(both_pos)} dari {len(rows)}")

ranked = sorted(both_pos, key=lambda r: (-r["worst"], -r["blend"]))
hdr = f"{'Rk':<3} {'Base':>6} {'TP':>5} {'Trail':>6} {'Hold':>5} {'NetFav':>9} {'NetAdv':>9} {'Blend':>9} {'Worst':>9} {'DDfav':>6} {'DDadv':>6}"
print("\n=== TOP 15 ROBUST (urut Worst-case desc, lalu Blend desc) ===")
print(hdr)
print("-" * len(hdr))
for i, r in enumerate(ranked[:15], 1):
    print(f"{i:<3} {r['base']:>6g} {r['tp']:>5g} {r['trail']:>6g} {r['hold']:>5g} "
          f"{r['net_fav']:>9.2f} {r['net_adv']:>9.2f} {r['blend']:>9.2f} {r['worst']:>9.2f} "
          f"{r['dd_fav']:>6.2f} {r['dd_adv']:>6.2f}")

cur = next(r for r in rows if (r["base"], r["tp"], r["trail"], r["hold"]) == (4025, 100, 10, 24))
print(f"\nSetting saat ini (4025/100/10/24): NetFav={cur['net_fav']:.2f} NetAdv={cur['net_adv']:.2f} "
      f"Blend={cur['blend']:.2f} Worst={cur['worst']:.2f}")
pos_cur = next((i for i, r in enumerate(ranked, 1)
                if (r["base"], r["tp"], r["trail"], r["hold"]) == (4025, 100, 10, 24)), None)
print(f"Peringkat robust setting saat ini: #{pos_cur}")
