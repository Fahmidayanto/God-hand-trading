import csv
import sys
sys.path.insert(0, r"B:\Project MT5\scratch")
from gridsearch_2019 import load_trades, _init, sim

with open(r"B:\Project MT5\scratch\gridsearch_2019_top.csv", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

seen = set()
distinct = []
for r in rows:
    key = (r["BaseRef"], r["TP"], r["MinSL"], r["Buffer"], r["Trailing"])
    if key not in seen:
        seen.add(key)
        distinct.append(r)
    if len(distinct) >= 8:
        break

print("=== TOP 8 DISTINKT (dari Top 50 CSV) ===")
for i, r in enumerate(distinct, 1):
    print(f"{i}. Base={r['BaseRef']} TP={r['TP']} MinSL={r['MinSL']} Buf={r['Buffer']} "
          f"Trail={r['Trailing']} | Net={r['NetPnL']} Final={r['FinalBalance']} "
          f"DD%={r['MaxDD_Pct']} PF={r['ProfitFactor']} WR={r['WinRate_Pct']}")

trades = load_trades()
_init(trades)

TP, MINSL, BUF, TRAIL, BASE = 100.0, 7.0, 1.0, 10.0, 4025.0

import pandas as pd
raw = pd.read_csv(r"B:\Project MT5\Backtest_result\Backtest_Results_XAUUSD_2019-12-30.csv")
raw = raw[raw["Status"] == "EXECUTED"].reset_index(drop=True)

events = []
print("\n=== TRADE DETAIL WINNER (Base=4025 TP=100 MinSL=7 Buf=1 Trail=10) ===")
for k, t in enumerate(trades):
    side, entry, anchor, lot_o, swap_o, comm_o, et, ts_w, hi_w, lo_w, cl_w = t
    r = entry / BASE
    lot = max(0.01, 0.05 / r)
    tp = entry + TP * r * (1 if side > 0 else -1)
    slmin_e = MINSL * r
    buf_e = BUF * r
    tr_e = TRAIL * r
    if side > 0:
        sl = anchor - buf_e if anchor > 0 else entry - slmin_e
        if sl >= entry or (entry - sl) < slmin_e:
            sl = entry - slmin_e
        ex = None
        reason = "FORCE24H"
        for i in range(len(ts_w)):
            if lo_w[i] <= sl:
                ex = sl; reason = "SL"; break
            if hi_w[i] >= tp:
                ex = tp; reason = "TP"; break
            c = cl_w[i]
            cand = c - tr_e
            lim = c - 1.50
            if cand > lim:
                cand = lim
            if cand > sl:
                sl = cand
        if ex is None:
            ex = cl_w[-1] if len(cl_w) else entry
        gross = (ex - entry) * lot * 100.0
    else:
        tp = entry + TP * r * -1
        slmin_e = MINSL * r
        buf_e = BUF * r
        tr_e = TRAIL * r
        sl = anchor + buf_e if anchor > 0 else entry + slmin_e
        if sl <= entry or (sl - entry) < slmin_e:
            sl = entry + slmin_e
        ex = None
        reason = "FORCE24H"
        for i in range(len(ts_w)):
            if hi_w[i] >= sl:
                ex = sl; reason = "SL"; break
            if lo_w[i] <= tp:
                ex = tp; reason = "TP"; break
            c = cl_w[i]
            cand = c + tr_e
            lim = c + 1.50
            if cand < lim:
                cand = lim
            if cand < sl:
                sl = cand
        if ex is None:
            ex = cl_w[-1] if len(cl_w) else entry
        gross = (entry - ex) * lot * 100.0
    net = gross + ((swap_o + comm_o) / lot_o) * lot
    events.append((et, net))
    orig = raw.iloc[k]
    print(f"T{k+1:>3} {orig['Type']:<4} {orig['EntryStructure']:<6} entry={entry:.2f} exit={ex:.2f} "
          f"lot={lot:.3f} r={r:.4f} {reason:<8} net={net:>8.2f} | orig_net={orig['Net_Profit']:>8.2f} ({orig['CloseReason'][:20]})")

total = sum(n for _, n in events)
wins = sum(1 for _, n in events if n > 0)
gp = sum(n for _, n in events if n > 0)
gl = sum(-n for _, n in events if n <= 0)
print(f"\nTotalNet={total:.2f} Wins={wins}/78 GP={gp:.2f} GL={gl:.2f}")
reasons = {}
print("\nExit mix (dari print di atas, hitung manual oleh pembaca tidak perlu):")
