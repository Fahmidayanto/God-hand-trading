import csv
from datetime import datetime

ea_csv_path = r"C:\Users\fahmi\AppData\Roaming\MetaQuotes\Tester\D0E8209F77C8CF37AD8BF550E51FF075\Agent-127.0.0.1-3000\MQL5\Files\Backtest_Results_XAUUSD_2026-08-20.csv"
replay_csv_path = r"C:\Users\fahmi\Downloads\Backtest_Results_XAUUSD_2026-08-21.csv"

def parse_dt(s):
    if not s: return None
    s = s.replace("-", ".").strip()
    try: return datetime.strptime(s, "%Y.%m.%d %H:%M:%S")
    except:
        try: return datetime.strptime(s, "%Y.%m.%d %H:%M")
        except: return None

with open(ea_csv_path, "r", encoding="utf-8", errors="ignore") as f:
    ea_rows = list(csv.DictReader(f))
with open(replay_csv_path, "r", encoding="utf-8", errors="ignore") as f:
    replay_rows = list(csv.DictReader(f))

ea_trades = [r for r in ea_rows if r.get("Status", "").upper() != "REJECTED"]
replay_trades = [r for r in replay_rows if r.get("Status", "").upper() != "REJECTED"]

for r in ea_trades: r["_dt"] = parse_dt(r.get("EntryTime"))
for r in replay_trades: r["_dt"] = parse_dt(r.get("EntryTime"))

print("================ SUMMARY COMPARISON ================")
print(f"Initial Balance: 1000.00")
ea_net = sum(float(r.get("Net_Profit", 0) or 0) for r in ea_trades)
replay_net = sum(float(r.get("Net_Profit", 0) or 0) for r in replay_trades)
print(f"EA Net Profit: {ea_net:.2f} -> Balance: {1000 + ea_net:.2f} (User stated: 3852.44)")
print(f"Replay Net Profit: {replay_net:.2f} -> Balance: {1000 + replay_net:.2f} (User stated: 4834.00)")
print(f"Total Discrepancy: {replay_net - ea_net:.2f} USD")

# Category 1: Unmatched EA Trades (Trades EA took but Replay did not)
# Category 2: Unmatched Replay Trades (Trades Replay took but EA did not)
# Category 3: Matched Trades with different Exit Types or Exit Prices

matched_pairs = []
unmatched_ea = []
used_replay = set()

for e in ea_trades:
    e_dt = e["_dt"]
    best_r = None
    best_diff = 999999
    best_idx = None
    for idx, r in enumerate(replay_trades):
        if idx in used_replay: continue
        if e.get("Type") != r.get("Type"): continue
        diff_s = abs((e_dt - r["_dt"]).total_seconds())
        if diff_s <= 1800 and diff_s < best_diff:
            best_diff = diff_s
            best_r = r
            best_idx = idx
    if best_r is not None:
        used_replay.add(best_idx)
        matched_pairs.append((e, best_r))
    else:
        unmatched_ea.append(e)

unmatched_replay = [r for idx, r in enumerate(replay_trades) if idx not in used_replay]

print(f"\n1. Matched Trades Count: {len(matched_pairs)}")
print(f"2. EA Only Trades Count: {len(unmatched_ea)}")
print(f"3. Replay Only Trades Count: {len(unmatched_replay)}")

ea_only_pnl = sum(float(r.get("Net_Profit", 0) or 0) for r in unmatched_ea)
replay_only_pnl = sum(float(r.get("Net_Profit", 0) or 0) for r in unmatched_replay)
print(f"\nNet Impact of EA-Only Trades: {ea_only_pnl:+.2f} USD")
print(f"Net Impact of Replay-Only Trades: {replay_only_pnl:+.2f} USD")

matched_ea_pnl = sum(float(p[0].get("Net_Profit", 0) or 0) for p in matched_pairs)
matched_replay_pnl = sum(float(p[1].get("Net_Profit", 0) or 0) for p in matched_pairs)
print(f"Net Impact of Differences within Matched Trades: {matched_replay_pnl - matched_ea_pnl:+.2f} USD")

print("\n--- Detailed breakdown of differences within matched pairs ---")
diff_categories = {
    "EA Premature Exit / SL vs Replay Hold": [],
    "24H Force Exit Price Difference": [],
    "TP Reached in Replay vs SL in EA": [],
    "Spread / Slippage / Point Precision": []
}

for e, r in matched_pairs:
    e_p = float(e.get("Net_Profit", 0) or 0)
    r_p = float(r.get("Net_Profit", 0) or 0)
    diff = r_p - e_p
    e_close = e.get("CloseType")
    r_close = r.get("CloseType")
    
    if abs(diff) < 0.05:
        continue
        
    if e_close != r_close:
        diff_categories["EA Premature Exit / SL vs Replay Hold"].append((e, r, diff))
    elif "24H" in str(e_close) and "24H" in str(r_close):
        diff_categories["24H Force Exit Price Difference"].append((e, r, diff))
    else:
        diff_categories["Spread / Slippage / Point Precision"].append((e, r, diff))

for cat, items in diff_categories.items():
    cat_diff = sum(item[2] for item in items)
    print(f"\n>> Category: {cat} (Total Diff: {cat_diff:+.2f} USD, Count: {len(items)})")
    for e, r, diff in items[:4]:
        print(f"   [{e.get('EntryTime')}] EA: {e.get('Type')} {e.get('CloseType')} {float(e.get('Net_Profit',0)):.2f} (exit {e.get('ExitPrice')}) vs Replay: {r.get('CloseType')} {float(r.get('Net_Profit',0)):.2f} (exit {r.get('ExitPrice')}) | Diff: {diff:+.2f}")
