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
BOS_CSV = os.path.join(DATA_DIR, "LLHHBOSData_XAUUSD_2019-12-30.csv")
OUT_CSV = r"B:\Project MT5\scratch\gridsearch_2019_phase2_top.csv"

INITIAL_BALANCE = 1000.0
BASE_LOT = 0.05
LOT_FLOOR = 0.01
CONTRACT = 100.0
MIN_STOP_USD = 1.50
NS_H = 3600 * 1_000_000_000
MAX_WIN_NS = 48 * NS_H
BOS_LOOKBACK_NS = 930 * 1_000_000_000

BASE_REF = [3950, 4000, 4025, 4050]
TP_D = [95, 100, 105]
TRAIL_D = [7.5, 10, 12.5]
MINSL_FIX = 7.0
BUF_FIX = 1.0
MAX_HOLD_H = [12, 24, 36, 48]
TP_EXP_OPTS = ["off", "on"]
BOS_EXIT_OPTS = ["off", "on"]
CYCLE = [1, 2, 3]

_T = None
_BOS_BULL = None
_BOS_BEAR = None


def to_ns(s):
    try:
        return int(pd.to_datetime(str(s).strip(), format="%Y.%m.%d %H:%M:%S")
                   .to_datetime64().astype("datetime64[ns]").astype("int64"))
    except Exception:
        return int(pd.to_datetime(str(s).strip()).to_datetime64()
                   .astype("datetime64[ns]").astype("int64"))


def load_all():
    m15 = pd.read_csv(M15_CSV)
    ts_all = (pd.to_datetime(m15["Time"], format="%Y.%m.%d %H:%M:%S")
              .to_numpy().astype("datetime64[ns]").astype("int64").tolist())
    hi_all = m15["High"].tolist()
    lo_all = m15["Low"].tolist()
    cl_all = m15["Close"].tolist()

    df = pd.read_csv(TRADES_CSV)
    ex = df[df["Status"] == "EXECUTED"].reset_index(drop=True)
    rej = df[(df["Status"] == "REJECTED") &
             (df["Reject_Reason"] == "Max BOS Cycle Limit (2)")].reset_index(drop=True)

    cpl_med = float(((ex["Swap"] + ex["Commission"]) / ex["LotSize"]).median())

    def make(row, struct):
        et = to_ns(row["EntryTime"])
        s = bisect_right(ts_all, et)
        e = bisect_right(ts_all, et + MAX_WIN_NS)
        lot_o = float(row["LotSize"])
        cpl_v = ((float(row["Swap"]) + float(row["Commission"])) / lot_o) if lot_o > 0 else cpl_med
        anchor = float(row["InitialSL"])
        return {
            "struct": struct,
            "side": 1 if str(row["Type"]).strip().upper() == "BUY" else -1,
            "entry": float(row["EntryPrice"]),
            "anchor": anchor if anchor > 0 else 0.0,
            "cpl": cpl_v,
            "et": et,
            "ts": ts_all[s:e], "hi": hi_all[s:e], "lo": lo_all[s:e], "cl": cl_all[s:e],
        }

    t_exec = [make(r, str(ex.iloc[i]["EntryStructure"]).strip()) for i, (_, r) in enumerate(ex.iterrows())]
    t_rej = [make(r, "CYC_REJ") for _, r in rej.iterrows()]

    sets = {
        1: [t for t in t_exec if t["struct"] != "BoS_2"],
        2: list(t_exec),
        3: list(t_exec) + t_rej,
    }

    bos = pd.read_csv(BOS_CSV, skiprows=1)
    bos = bos[bos["Timeframe"].astype(str).str.strip() == "M15"]
    bos = bos[bos["Type"].astype(str).str.strip() == "BoS"]
    bull, bear = [], []
    for _, r in bos.iterrows():
        d = str(r["Direction/Action"])
        if "Bullish" in d:
            bull.append(to_ns(r["Time"]))
        elif "Bearish" in d:
            bear.append(to_ns(r["Time"]))
    bull.sort()
    bear.sort()
    return sets, bull, bear


def init_worker(T, bb, br):
    global _T, _BOS_BULL, _BOS_BEAR
    _T = T
    _BOS_BULL = bb
    _BOS_BEAR = br


def sim(base, tp_d, trail_d, maxhold_h, tpexp, bosexit, cycle):
    trades = _T[cycle]
    maxhold_ns = maxhold_h * NS_H
    events = []
    total_net = 0.0
    wins = 0
    gp = 0.0
    gl = 0.0
    reasons = {}
    for tr in trades:
        side = tr["side"]
        entry = tr["entry"]
        anchor = tr["anchor"]
        cpl = tr["cpl"]
        et = tr["et"]
        ts_w = tr["ts"]
        fav_w = tr["hi"] if side > 0 else tr["lo"]
        adv_w = tr["lo"] if side > 0 else tr["hi"]
        cl_w = tr["cl"]
        r = entry / base
        lot = LOT_FLOOR if BASE_LOT / r < LOT_FLOOR else BASE_LOT / r
        tp_e = tp_d * r
        slmin_e = MINSL_FIX * r
        buf_e = BUF_FIX * r
        tr_e = trail_d * r
        trig_e = 20.0 * r if tpexp == "on" else 0.0
        exp_e = 40.0 * r if tpexp == "on" else 0.0
        blist = _BOS_BULL if side > 0 else _BOS_BEAR
        b_start = bisect_right(blist, et - BOS_LOOKBACK_NS)
        bp = b_start
        nb = len(blist)
        n = len(ts_w)
        tp = entry + side * tp_e
        if anchor > 0.0:
            sl = anchor - side * buf_e
        else:
            sl = entry - side * slmin_e
        if side * (entry - sl) < slmin_e:
            sl = entry - side * slmin_e
        ex_p = 0.0
        x_ns = 0
        reason = ""
        done = False
        i = 0
        while i < n:
            t_i = ts_w[i]
            hit_sl = (adv_w[i] <= sl) if side > 0 else (adv_w[i] >= sl)
            if hit_sl:
                ex_p = sl
                x_ns = t_i
                reason = "SL"
                done = True
                break
            hit_tp = (fav_w[i] >= tp) if side > 0 else (fav_w[i] <= tp)
            if hit_tp:
                ex_p = tp
                x_ns = t_i
                reason = "TP"
                done = True
                break
            c = cl_w[i]
            while bp < nb and blist[bp] <= t_i:
                bp += 1
            if bosexit == "on" and (bp - b_start) >= 3:
                ex_p = c
                x_ns = t_i
                reason = "BOS3"
                done = True
                break
            if t_i - et >= maxhold_ns:
                ex_p = c
                x_ns = t_i
                reason = "FORCE"
                done = True
                break
            cand = c - side * tr_e
            lim = c - side * MIN_STOP_USD
            if side * (cand - lim) > 0:
                cand = lim
            if side * (cand - sl) > 0:
                sl = cand
            if tpexp == "on":
                dist = side * (tp - c)
                if dist <= trig_e:
                    ntp = c + side * exp_e
                    if side * (ntp - tp) > 0:
                        tp = ntp
            i += 1
        if not done:
            if n > 0:
                ex_p = cl_w[-1]
                x_ns = ts_w[-1]
                reason = "WINEND"
            else:
                ex_p = entry
                x_ns = et + maxhold_ns
                reason = "NOWIN"
        gross = side * (ex_p - entry) * lot * CONTRACT
        net = gross + cpl * lot
        total_net += net
        if net > 0.0:
            wins += 1
            gp += net
        elif net < 0.0:
            gl += -net
        events.append((x_ns, net))
        reasons[reason] = reasons.get(reason, 0) + 1
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
    wr = wins / len(trades) * 100.0 if trades else 0.0
    return {
        "base": base, "tp": tp_d, "trail": trail_d, "hold": maxhold_h,
        "tpexp": tpexp, "bosexit": bosexit, "cycle": cycle,
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


def main():
    t0 = time.time()
    sets, bb, br = load_all()
    print(f"[LOAD] Sets: c1={len(sets[1])} c2={len(sets[2])} c3={len(sets[3])} | "
          f"BoS events: bull={len(bb)} bear={len(br)} | {time.time()-t0:.1f}s", flush=True)
    init_worker(sets, bb, br)

    combos = [c for c in product(BASE_REF, TP_D, TRAIL_D, MAX_HOLD_H, TP_EXP_OPTS, BOS_EXIT_OPTS, CYCLE)]
    print(f"[GRID] Combos={len(combos)}")

    chunks = [[c for c in combos if c[0] == b] for b in BASE_REF]
    rows = []
    t1 = time.time()
    done = 0
    with Pool(processes=min(4, cpu_count()), initializer=init_worker,
              initargs=(sets, bb, br)) as pool:
        for res in pool.imap_unordered(run_chunk, chunks):
            rows.extend(res)
            done += 1
            print(f"[RUN] chunk {done}/{len(chunks)} elapsed={time.time()-t1:.1f}s", flush=True)

    final_ranked = sorted(rows, key=rank_key)

    groups = {}
    group_order = []
    for r in final_ranked:
        k = (r["net"], r["dd_pct"], r["wr"], r["n"])
        if k not in groups:
            groups[k] = {"rep": r, "count": 0}
            group_order.append(k)
        groups[k]["count"] += 1

    print(f"\n[DONE] TotalEvaluated={len(rows)} Elapsed={time.time()-t0:.1f}s")
    hdr = (f"{'Rk':<3} {'Base':>6} {'TP':>6} {'Trail':>6} {'Hold':>5} {'TpExp':>6} "
           f"{'BosX':>5} {'Cyc':>4} {'N':>4} {'NetPnL':>10} {'FinalBal':>10} {'DD%':>7} {'PF':>7} {'WR%':>7} {'Equiv':>6}")
    print("\n=== TOP 10 (Ranking: PF>=1.5, NetPnL desc, DD% asc, WR desc) ===")
    print(hdr)
    print("-" * len(hdr))
    for i, k in enumerate(group_order[:10], 1):
        g = groups[k]
        r = g["rep"]
        tag = "" if r["pf"] >= 1.5 else "  [PF<1.5]"
        print(f"{i:<3} {r['base']:>6g} {r['tp']:>6g} {r['trail']:>6g} {r['hold']:>5g} {r['tpexp']:>6} "
              f"{r['bosexit']:>5} {r['cycle']:>4} {r['n']:>4} {r['net']:>10.2f} {r['final']:>10.2f} "
              f"{r['dd_pct']:>7.2f} {fmt_pf(r['pf']):>7} {r['wr']:>7.2f} {g['count']:>6}{tag}")

    base_row = next(r for r in rows if (r["base"], r["tp"], r["trail"], r["hold"],
                                        r["tpexp"], r["bosexit"], r["cycle"]) ==
                    (4025, 100, 10, 24, "on", "on", 2))
    print("\n=== BASELINE (setting EA saat ini: Base4025 TP100 Trail10 Hold24 TpExp=on BosExit=on Cyc=2) ===")
    print(f"N={base_row['n']} NetPnL={base_row['net']:.2f} FinalBal={base_row['final']:.2f} "
          f"DD%={base_row['dd_pct']:.2f} PF={fmt_pf(base_row['pf'])} WR%={base_row['wr']:.2f}")

    q = sum(1 for r in rows if r["pf"] >= 1.5)
    print(f"\nLolos PF>=1.5: {q} dari {len(rows)}")

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Rank", "BaseRef", "TP", "Trailing", "MaxHoldHours", "TpExpansion",
                    "BosExit3", "MaxBoSCycle", "Trades", "NetPnL", "FinalBalance",
                    "MaxDD_USD", "MaxDD_Pct", "ProfitFactor", "WinRate_Pct", "EquivCount"])
        for i, k in enumerate(group_order[:30], 1):
            r = groups[k]["rep"]
            w.writerow([i, r["base"], r["tp"], r["trail"], r["hold"], r["tpexp"],
                        r["bosexit"], r["cycle"], r["n"], r["net"], r["final"],
                        r["dd_usd"], r["dd_pct"], fmt_pf(r["pf"]), r["wr"], groups[k]["count"]])
    print(f"\n[SAVE] Top 30 grup -> {OUT_CSV}")


if __name__ == "__main__":
    main()
