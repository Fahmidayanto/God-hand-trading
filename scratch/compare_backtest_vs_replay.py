import csv
import os
import sys

ea_csv_path = r"C:\Users\fahmi\AppData\Roaming\MetaQuotes\Tester\D0E8209F77C8CF37AD8BF550E51FF075\Agent-127.0.0.1-3000\MQL5\Files\Backtest_Results_XAUUSD_2026-08-20.csv"
replay_csv_path = r"C:\Users\fahmi\Downloads\Backtest_Results_XAUUSD_2026-08-21.csv"

def load_csv(path):
    if not os.path.exists(path):
        print(f"File not found: {path}")
        return []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        return list(reader)

ea_rows = load_csv(ea_csv_path)
replay_rows = load_csv(replay_csv_path)

print(f"EA Rows: {len(ea_rows)}")
print(f"Replay Rows: {len(replay_rows)}")

# Filter non-rejected trades (closed / open)
ea_trades = [r for r in ea_rows if r.get("Status", "").upper() != "REJECTED"]
replay_trades = [r for r in replay_rows if r.get("Status", "").upper() != "REJECTED"]

print(f"EA Executed Trades: {len(ea_trades)}")
print(f"Replay Executed Trades: {len(replay_trades)}")

ea_net_profit = sum(float(r.get("Net_Profit", 0) or 0) for r in ea_trades)
replay_net_profit = sum(float(r.get("Net_Profit", 0) or 0) for r in replay_trades)

print(f"EA Total Net Profit: {ea_net_profit:.2f}")
print(f"Replay Total Net Profit: {replay_net_profit:.2f}")

# Group by CloseType / Status
from collections import Counter
ea_close_types = Counter(r.get("CloseType", "N/A") for r in ea_trades)
replay_close_types = Counter(r.get("CloseType", "N/A") for r in replay_trades)

print("\n--- Close Types ---")
print("EA Close Types:", dict(ea_close_types))
print("Replay Close Types:", dict(replay_close_types))

# Map trades by EntryTime (or approximate)
def normalize_time(t_str):
    if not t_str:
        return ""
    # Convert 'YYYY.MM.DD HH:MM:SS' or 'YYYY-MM-DD HH:MM:SS'
    return t_str.replace("-", ".").strip()

ea_by_time = {normalize_time(r.get("EntryTime", "")): r for r in ea_trades}
replay_by_time = {normalize_time(r.get("EntryTime", "")): r for r in replay_trades}

common_times = set(ea_by_time.keys()) & set(replay_by_time.keys())
ea_only_times = set(ea_by_time.keys()) - set(replay_by_time.keys())
replay_only_times = set(replay_by_time.keys()) - set(ea_by_time.keys())

print(f"\nCommon Entry Times: {len(common_times)}")
print(f"EA Only Entry Times: {len(ea_only_times)}")
print(f"Replay Only Entry Times: {len(replay_only_times)}")

# Compare common trades
profit_diffs = []
for t in sorted(common_times):
    e = ea_by_time[t]
    r = replay_by_time[t]
    e_p = float(e.get("Net_Profit", 0) or 0)
    r_p = float(r.get("Net_Profit", 0) or 0)
    e_lot = float(e.get("LotSize", 0) or 0)
    r_lot = float(r.get("LotSize", 0) or 0)
    diff = r_p - e_p
    if abs(diff) > 0.01:
        profit_diffs.append({
            "time": t,
            "type": e.get("Type", ""),
            "ea_lot": e_lot,
            "replay_lot": r_lot,
            "ea_entry": e.get("EntryPrice"),
            "replay_entry": r.get("EntryPrice"),
            "ea_exit": e.get("ExitPrice"),
            "replay_exit": r.get("ExitPrice"),
            "ea_sl": e.get("FinalSL"),
            "replay_sl": r.get("FinalSL"),
            "ea_tp": e.get("FinalTP"),
            "replay_tp": r.get("FinalTP"),
            "ea_close_type": e.get("CloseType"),
            "replay_close_type": r.get("CloseType"),
            "ea_profit": e_p,
            "replay_profit": r_p,
            "diff": diff
        })

print(f"\nTrades with Profit Discrepancies: {len(profit_diffs)}")
for d in profit_diffs[:15]:
    print(f"Time: {d['time']} | Type: {d['type']} | EA: {d['ea_profit']:.2f} ({d['ea_close_type']}, lot {d['ea_lot']}, exit {d['ea_exit']}) vs Replay: {d['replay_profit']:.2f} ({d['replay_close_type']}, lot {d['replay_lot']}, exit {d['replay_exit']}) | Diff: {d['diff']:+.2f}")

if ea_only_times:
    print("\n--- EA Only Trades (Sample) ---")
    for t in list(sorted(ea_only_times))[:5]:
        e = ea_by_time[t]
        print(f"Time: {t} | Type: {e.get('Type')} | Profit: {e.get('Net_Profit')} | CloseType: {e.get('CloseType')}")

if replay_only_times:
    print("\n--- Replay Only Trades (Sample) ---")
    for t in list(sorted(replay_only_times))[:5]:
        r = replay_by_time[t]
        print(f"Time: {t} | Type: {r.get('Type')} | Profit: {r.get('Net_Profit')} | CloseType: {r.get('CloseType')}")
