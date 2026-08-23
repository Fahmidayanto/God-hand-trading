import importlib.util
from bisect import bisect_right

spec = importlib.util.spec_from_file_location("gs2", r"B:\Project MT5\scratch\gridsearch_2019_phase2.py")
gs2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gs2)

sets, bb, br = gs2.load_all()
gs2.init_worker(sets, bb, br)

for label, base, tp, trail, hold, tpexp, bosexit, cyc in [
    ("baseline", 4025, 100, 10, 24, "on", "on", 2),
    ("trail_lebar", 4025, 100, 60, 48, "on", "on", 2),
    ("trail_lebar_nobos", 4025, 100, 60, 48, "on", "off", 2),
]:
    r = gs2.sim(base, tp, trail, hold, tpexp, bosexit, cyc)
    print(label, "net=", r["net"], "dd=", r["dd_pct"], "pf=", r["pf"], "wr=", r["wr"])

NS_H = gs2.NS_H
LOOK = gs2.BOS_LOOKBACK_NS
for cyc in (1, 2, 3):
    c24 = 0
    c48 = 0
    for t in sets[cyc]:
        b = gs2._BOS_BULL if t["side"] > 0 else gs2._BOS_BEAR
        n24 = bisect_right(b, t["et"] + 24 * NS_H) - bisect_right(b, t["et"] - LOOK)
        n48 = bisect_right(b, t["et"] + 48 * NS_H) - bisect_right(b, t["et"] - LOOK)
        if n24 >= 3:
            c24 += 1
        if n48 >= 3:
            c48 += 1
    print(f"cycle={cyc}: trade dgn >=3 BoS searah dalam 24j = {c24}/{len(sets[cyc])}, dalam 48j = {c48}/{len(sets[cyc])}")
