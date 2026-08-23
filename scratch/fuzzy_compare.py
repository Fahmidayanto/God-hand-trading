import csv
import os
from datetime import datetime, timedelta

ea_csv_path = r"C:\Users\fahmi\AppData\Roaming\MetaQuotes\Tester\D0E8209F77C8CF37AD8BF550E51FF075\Agent-127.0.0.1-3000\MQL5\Files\Backtest_Results_XAUUSD_2026-08-20.csv"
replay_csv_path = r"C:\Users\fahmi\Downloads\Backtest_Results_XAUUSD_2026-08-21.csv"

def parse_time(t_str):
    if not t_str:
        return None
    t_str = t_str.replace("-", ".").strip()
    try:
        return datetime.strptime(t_str, "%Y.%m.%d %H:%M:%S")
    except:
        try:
            return datetime.strptime(t_str, "%Y.%m.%d %H:%M")
        except:
            return None

def load_csv(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        for r in rows:
            r["_entry_dt"] = parse_time(r.get("EntryTime"))
            r["_exit_dt"] = parse_time(r.get("ExitTime"))
        return rows

ea_rows = load_csv(ea_csv_path)
replay_rows = load_csv(replay_csv_path)

ea_trades = [r for r in ea_rows if r.get("Status", "").upper() != "REJECTED"]
replay_trades = [r for r in replay_rows if r.get("Status", "").upper() != "REJECTED"]

print(f"Total EA Executed: {len(ea_trades)}")
print(f"Total Replay Executed: {len(replay_trades)}")

# Fuzzy match by entry time within 30 minutes and same type
matched_ea = set()
matched_replay = set()
pairs = []

for e_idx, e in enumerate(ea_trades):
    e_dt = e["_entry_dt"]
    if not e_dt:
        continue
    best_r_idx = None
    best_diff = 999999
    for r_idx, r in enumerate(replay_trades):
        if r_idx in matched_replay:
            continue
        if e.get("Type", "").upper() != r.get("Type", "").upper():
            continue
        r_dt = r["_entry_dt"]
        if not r_dt:
            continue
        diff_sec = abs((e_dt - r_dt).total_seconds())
        if diff_sec <= 1800 and diff_sec < best_diff: # within 30 mins
            best_diff = diff_sec
            best_r_idx = r_idx
    if best_r_idx is not None:
        matched_ea.add(e_idx)
        matched_replay.add(best_r_idx)
        pairs.append((e, replay_trades[best_r_idx], best_diff))

print(f"Fuzzy Matched Trades (within 30 mins): {len(pairs)}")
print(f"EA Unmatched: {len(ea_trades) - len(matched_ea)}")
print(f"Replay Unmatched: {len(replay_trades) - len(matched_replay)}")

ea_matched_profit = sum(float(p[0].get("Net_Profit", 0) or 0) for p in pairs)
replay_matched_profit = sum(float(p[1].get("Net_Profit", 0) or 0) for p in pairs)

print(f"\nMatched Pairs EA Profit: {ea_matched_profit:.2f}")
print(f"Matched Pairs Replay Profit: {replay_matched_profit:.2f}")
print(f"Profit Diff in Matched Pairs: {replay_matched_profit - ea_matched_profit:+.2f}")

print("\n--- Top Profit Differences in Matched Pairs ---")
sorted_pairs = sorted(pairs, key=lambda p: abs(float(p[1].get("Net_Profit", 0) or 0) - float(p[0].get("Net_Profit", 0) or 0)), reverse=True)
for e, r, diff_sec in sorted_pairs[:15]:
    e_p = float(e.get("Net_Profit", 0) or 0)
    r_p = float(r.get("Net_Profit", 0) or 0)
    print(f"EA [{e.get('EntryTime')}] {e.get('Type')} {e.get('CloseType')} profit={e_p:.2f} (exit={e.get('ExitPrice')}) vs Replay [{r.get('EntryTime')}] {r.get('CloseType')} profit={r_p:.2f} (exit={r.get('ExitPrice')}) | Diff={r_p - e_p:+.2f}")

print("\n--- EA Unmatched Trades ---")
for idx, e in enumerate(ea_trades):
    if idx not in matched_ea:
        print(f"EA Only: [{e.get('EntryTime')}] {e.get('Type')} {e.get('CloseType')} profit={e.get('Net_Profit')} lot={e.get('LotSize')} structure={e.get('EntryStructure')}")

print("\n--- Replay Unmatched Trades ---")
for idx, r in enumerate(replay_trades):
    if idx not in matched_replay:
        print(f"Replay Only: [{r.get('EntryTime')}] {r.get('Type')} {r.get('CloseType')} profit={r.get('Net_Profit')} lot={r.get('LotSize')} structure={r.get('EntryStructure')}")
