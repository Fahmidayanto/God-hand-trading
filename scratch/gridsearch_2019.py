import os
import csv
import time
from bisect import bisect_right
from itertools import product
from multiprocessing import Pool, cpu_count

import pandas as pd

DATA_DIR = r"B:\Project MT5\Backtest_result"
TRADES_CSV = os.path.join(DATA_DIR, "Backtest_Results_XAUUSD_2019-12-30.csv")
M15_CSV = os.path.join(DATA_DIR, "MarketData_XAUUSD_M15_2019-12-30.csv")
OUT_CSV = r"B:\Project MT5\scratch\gridsearch_2019_top.csv"

INITIAL_BALANCE = 1000.0
BASE_LOT = 0.05
LOT_FLOOR = 0.01
CONTRACT = 100.0
MIN_STOP_USD = 1.50
MAX_HOLD_NS = 24 * 3600 * 1_000_000_000

BASE_REF = [1100, 1200, 1300, 1350, 1400, 1450, 1500, 1600, 1700, 1800,
            2000, 2200, 2500, 3000, 3500, 4000, 4500, 5000]
TP_D = [15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 70, 80, 100]
MIN_SL_D = [8, 10, 12, 15, 18, 20, 25, 30]
BUF_D = [2, 3, 4, 5, 6, 8, 10, 12, 15]
TRAIL_D = [10, 15, 20, 25, 30, 35, 40, 50, 60, 75]

_T = None


def load_trades():
    m15 = pd.read_csv(M15_CSV)
    ts_all = (pd.to_datetime(m15["Time"], format="%Y.%m.%d %H:%M:%S")
              .to_numpy().astype("datetime64[ns]").astype("int64").tolist())
    hi_all = m15["High"].tolist()
    lo_all = m15["Low"].tolist()
    cl_all = m15["Close"].tolist()

    df = pd.read_csv(TRADES_CSV)
    df = df[df["Status"] == "EXECUTED"].copy()

    trades = []
    for _, row in df.iterrows():
        et = int(pd.to_datetime(str(row["EntryTime"]).strip(), format="%Y.%m.%d %H:%M:%S")
                 .to_datetime64().astype("datetime64[ns]").astype("int64"))
        s = bisect_right(ts_all, et)
        e = bisect_right(ts_all, et + MAX_HOLD_NS)
        trades.append((
            1 if str(row["Type"]).strip().upper() == "BUY" else -1,
            float(row["EntryPrice"]),
            float(row["InitialSL"]),
            float(row["LotSize"]),
            float(row["Swap"]),
            float(row["Commission"]),
            et,
            ts_all[s:e], hi_all[s:e], lo_all[s:e], cl_all[s:e],
        ))
    return trades


def _init(trades):
    global _T
    _T = trades


def sim(base, tp_d, minsl_d, buf_d, trail_d, noscale=False):
    trades = _T
    events = []
    total_net = 0.0
    wins = 0
    gp = 0.0
    gl = 0.0
    for (side, entry, anchor, lot_o, swap_o, comm_o, et, ts_w, hi_w, lo_w, cl_w) in trades:
        if noscale:
            r = 1.0
            lot = BASE_LOT
        else:
            r = entry / base
            lot = LOT_FLOOR if BASE_LOT / r < LOT_FLOOR else BASE_LOT / r
        tp_e = tp_d * r
        slmin_e = minsl_d * r
        buf_e = buf_d * r
        tr_e = trail_d * r
        n = len(ts_w)
        good_anchor = anchor > 0.0
        if side > 0:
            tp = entry + tp_e
            sl = anchor - buf_e if good_anchor else entry - slmin_e
            if sl >= entry or (entry - sl) < slmin_e:
                sl = entry - slmin_e
            ex = 0.0
            exit_ns = 0
            done = False
            i = 0
            while i < n:
                if lo_w[i] <= sl:
                    ex = sl
                    exit_ns = ts_w[i]
                    done = True
                    break
                if hi_w[i] >= tp:
                    ex = tp
                    exit_ns = ts_w[i]
                    done = True
                    break
                c = cl_w[i]
                cand = c - tr_e
                lim = c - MIN_STOP_USD
                if cand > lim:
                    cand = lim
                if cand > sl:
                    sl = cand
                i += 1
            if not done:
                if n > 0:
                    ex = cl_w[-1]
                    exit_ns = ts_w[-1]
                else:
                    ex = entry
                    exit_ns = et + MAX_HOLD_NS
            gross = (ex - entry) * lot * CONTRACT
        else:
            tp = entry - tp_e
            sl = anchor + buf_e if good_anchor else entry + slmin_e
            if sl <= entry or (sl - entry) < slmin_e:
                sl = entry + slmin_e
            ex = 0.0
            exit_ns = 0
            done = False
            i = 0
            while i < n:
                if hi_w[i] >= sl:
                    ex = sl
                    exit_ns = ts_w[i]
                    done = True
                    break
                if lo_w[i] <= tp:
                    ex = tp
                    exit_ns = ts_w[i]
                    done = True
                    break
                c = cl_w[i]
                cand = c + tr_e
                lim = c + MIN_STOP_USD
                if cand < lim:
                    cand = lim
                if cand < sl:
                    sl = cand
                i += 1
            if not done:
                if n > 0:
                    ex = cl_w[-1]
                    exit_ns = ts_w[-1]
                else:
                    ex = entry
                    exit_ns = et + MAX_HOLD_NS
            gross = (entry - ex) * lot * CONTRACT
        net = gross + ((swap_o + comm_o) / lot_o) * lot
        total_net += net
        if net > 0.0:
            wins += 1
            gp += net
        elif net < 0.0:
            gl += -net
        events.append((exit_ns, net))
    events.sort()
    balance = INITIAL_BALANCE
    peak = balance
    maxdd = 0.0
    maxddp = 0.0
    for _, net in events:
        balance += net
        if balance > peak:
            peak = balance
        else:
            dd = peak - balance
            if dd > maxdd:
                maxdd = dd
                maxddp = dd / peak * 100.0 if peak > 0 else 0.0
    pf = (gp / gl) if gl > 0.0 else float("inf")
    wr = wins / len(trades) * 100.0
    return {
        "base": base, "tp": tp_d, "minsl": minsl_d, "buf": buf_d, "trail": trail_d,
        "net": round(total_net, 2), "final": round(INITIAL_BALANCE + total_net, 2),
        "dd_usd": round(maxdd, 2), "dd_pct": round(maxddp, 2),
        "pf": round(pf, 4) if pf != float("inf") else float("inf"),
        "wr": round(wr, 2), "n": len(trades),
    }


def run_chunk(chunk):
    return [sim(*c) for c in chunk]


def rank_key(row):
    return (0 if row["pf"] >= 1.5 else 1, -row["net"], row["dd_pct"], -row["wr"])


def fmt_pf(x):
    return "inf" if x == float("inf") else f"{x:.2f}"


def print_rows(rows, title):
    print(f"\n=== {title} ===")
    hdr = f"{'Rank':<4} {'Base':>7} {'TP':>6} {'MinSL':>6} {'Buf':>5} {'Trail':>6} {'NetPnL':>11} {'FinalBal':>11} {'DD%':>7} {'DD_USD':>9} {'PF':>7} {'WR%':>7}"
    print(hdr)
    print("-" * len(hdr))
    for i, r in enumerate(rows, 1):
        tag = "" if r["pf"] >= 1.5 else "  [PF<1.5]"
        print(f"{i:<4} {r['base']:>7g} {r['tp']:>6g} {r['minsl']:>6g} {r['buf']:>5g} {r['trail']:>6g} "
              f"{r['net']:>11.2f} {r['final']:>11.2f} {r['dd_pct']:>7.2f} {r['dd_usd']:>9.2f} "
              f"{fmt_pf(r['pf']):>7} {r['wr']:>7.2f}{tag}")


def main():
    t0 = time.time()
    trades = load_trades()
    n_bars = sum(len(t[7]) for t in trades)
    avg_bars = n_bars / len(trades) if trades else 0
    print(f"[LOAD] Trades={len(trades)} AvgHoldBars={avg_bars:.1f} LoadTime={time.time()-t0:.1f}s")
    _init(trades)

    stage1 = [(b, t, m, bf, tr)
              for b in BASE_REF
              for t in TP_D
              for m in MIN_SL_D
              for bf in BUF_D
              for tr in TRAIL_D]
    print(f"[STAGE1] Combos={len(stage1)}")

    chunks = []
    for b in BASE_REF:
        chunks.append([c for c in stage1 if c[0] == b])
    rows = []
    t1 = time.time()
    done = 0
    with Pool(processes=min(8, cpu_count()), initializer=_init, initargs=(trades,)) as pool:
        for res in pool.imap_unordered(run_chunk, chunks):
            rows.extend(res)
            done += 1
            print(f"[RUN] chunk {done}/{len(chunks)} done, elapsed={time.time()-t1:.1f}s", flush=True)

    seen = set(stage1)
    ranked = sorted(rows, key=rank_key)
    top10 = ranked[:10]

    stage2_set = set()
    for r in top10:
        b, t, m, bf, tr = r["base"], r["tp"], r["minsl"], r["buf"], r["trail"]
        for nb in (b, b - 25.0, b + 25.0):
            for nt in (t, t - 2.5, t + 2.5):
                for nm in (m, m - 1.0, m + 1.0):
                    for nf in (bf, bf - 1.0, bf + 1.0):
                        for nr in (tr, tr - 2.5, tr + 2.5):
                            if nb <= 0:
                                continue
                            c = (float(nb), float(nt), float(nm), float(nf), float(nr))
                            if c not in seen:
                                stage2_set.add(c)
                                seen.add(c)
    stage2 = sorted(stage2_set)
    print(f"[STAGE2] NewCombos={len(stage2)}")
    rows2 = run_chunk(stage2) if stage2 else []

    all_rows = rows + rows2
    final_ranked = sorted(all_rows, key=rank_key)

    groups = {}
    group_order = []
    for r in final_ranked:
        k = (r["net"], r["dd_pct"], r["wr"])
        if k not in groups:
            groups[k] = {"rep": r, "count": 0}
            group_order.append(k)
        groups[k]["count"] += 1
    top_groups = [groups[k] for k in group_order[:5]]
    top5 = [g["rep"] for g in top_groups]
    print(f"[DONE] TotalEvaluated={len(all_rows)} Elapsed={time.time()-t0:.1f}s")

    print("\n=== TOP 5 KOMBINASI TERBAIK - GRUP DISTINKT (Ranking: NetPnL desc, DD% asc, PF>=1.5, WR) ===")
    hdr = f"{'Rank':<4} {'Base':>7} {'TP':>6} {'MinSL':>6} {'Buf':>5} {'Trail':>6} {'NetPnL':>11} {'FinalBal':>11} {'DD%':>7} {'DD_USD':>9} {'PF':>7} {'WR%':>7} {'Equiv':>6}"
    print(hdr)
    print("-" * len(hdr))
    for i, (g, r) in enumerate(zip(top_groups, top5), 1):
        tag = "" if r["pf"] >= 1.5 else "  [PF<1.5]"
        print(f"{i:<4} {r['base']:>7g} {r['tp']:>6g} {r['minsl']:>6g} {r['buf']:>5g} {r['trail']:>6g} "
              f"{r['net']:>11.2f} {r['final']:>11.2f} {r['dd_pct']:>7.2f} {r['dd_usd']:>9.2f} "
              f"{fmt_pf(r['pf']):>7} {r['wr']:>7.2f} {g['count']:>6}{tag}")

    wp = top5[0]
    print("\n=== PERBANDINGAN SCALING (parameter manajemen terbaik: "
          f"TP={wp['tp']:g}, MinSL={wp['minsl']:g}, Buf={wp['buf']:g}, Trail={wp['trail']:g}) ===")
    cmp_rows = [
        ("Tanpa Scaling (ratio=1, lot=0.05)", sim(0, wp["tp"], wp["minsl"], wp["buf"], wp["trail"], noscale=True)),
        ("Scaling Base 1500", sim(1500, wp["tp"], wp["minsl"], wp["buf"], wp["trail"])),
        ("Scaling Base 4500", sim(4500, wp["tp"], wp["minsl"], wp["buf"], wp["trail"])),
    ]
    hdr2 = f"{'Mode':<34} {'NetPnL':>11} {'FinalBal':>11} {'DD%':>7} {'DD_USD':>9} {'PF':>7} {'WR%':>7}"
    print(hdr2)
    print("-" * len(hdr2))
    for name, r in cmp_rows:
        print(f"{name:<34} {r['net']:>11.2f} {r['final']:>11.2f} {r['dd_pct']:>7.2f} {r['dd_usd']:>9.2f} "
              f"{fmt_pf(r['pf']):>7} {r['wr']:>7.2f}")

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Rank", "BaseRef", "TP", "MinSL", "Buffer", "Trailing",
                    "NetPnL", "FinalBalance", "MaxDD_USD", "MaxDD_Pct", "ProfitFactor", "WinRate_Pct", "Trades", "EquivCount"])
        for i, k in enumerate(group_order[:30], 1):
            r = groups[k]["rep"]
            w.writerow([i, r["base"], r["tp"], r["minsl"], r["buf"], r["trail"],
                        r["net"], r["final"], r["dd_usd"], r["dd_pct"],
                        fmt_pf(r["pf"]), r["wr"], r["n"], groups[k]["count"]])
    print(f"\n[SAVE] Top 30 grup distinkt -> {OUT_CSV}")

    print("\n=== REKOMENDASI ===")
    b = top5[0]
    q = sum(1 for r in final_ranked if r["pf"] >= 1.5)
    print(f"Param: BaseRef={b['base']:g}, TP={b['tp']:g}, MinSL={b['minsl']:g}, "
          f"Buffer={b['buf']:g}, Trailing={b['trail']:g}")
    print(f"NetPnL={b['net']:.2f} USD | FinalBal={b['final']:.2f} | DD={b['dd_pct']:.2f}% "
          f"({b['dd_usd']:.2f} USD) | PF={fmt_pf(b['pf'])} | WR={b['wr']:.2f}%")
    print(f"Kombinasi lolos PF>=1.5: {q} dari {len(final_ranked)}")


if __name__ == "__main__":
    main()
