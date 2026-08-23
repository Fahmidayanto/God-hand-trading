import csv
from datetime import datetime

ea_file = r"b:\Project MT5\Backtest_result_v1\Backtest_Results_XAUUSD_2026-08-20.csv"
replay_file = r"b:\Project MT5\Backtest_result_v1\Backtest_Results_XAUUSD_2026-08-21.csv"

def load_csv(filepath):
    trades = []
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for row in reader:
            clean_row = {k.strip(): v.strip() for k, v in row.items() if k}
            trades.append(clean_row)
    return trades

ea_trades = load_csv(ea_file)
replay_trades = load_csv(replay_file)

ea_exec = [t for t in ea_trades if t.get("Status", "").upper() not in ("REJECTED", "FILTERED")]
replay_exec = [t for t in replay_trades if t.get("Status", "").upper() not in ("REJECTED", "FILTERED")]

def parse_time(ts_str):
    if not ts_str or ts_str in ("0", "N/A", ""):
        return None
    for fmt in ("%Y.%m.%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y.%m.%d %H:%M", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(ts_str, fmt)
        except ValueError:
            pass
    return None

matched_pairs = []
unmatched_ea = []
unmatched_replay = list(replay_exec)

for eat in ea_exec:
    ea_t = parse_time(eat.get("EntryTime"))
    ea_type = eat.get("Type", "").upper()
    found = None
    for rept in unmatched_replay:
        rep_t = parse_time(rept.get("EntryTime"))
        rep_type = rept.get("Type", "").upper()
        if ea_t and rep_t and ea_type == rep_type:
            diff_sec = abs((ea_t - rep_t).total_seconds())
            if diff_sec <= 1800:
                found = rept
                break
    if found:
        matched_pairs.append((eat, found))
        unmatched_replay.remove(found)
    else:
        unmatched_ea.append(eat)

print("=== CONTOH MATCHED TRADE PERTAMA (2026.01.05 CHoCH BUY) ===")
eat, rept = matched_pairs[0]
print(f"EA     -> EntryTime: {eat.get('EntryTime')} | EntryPrice: {eat.get('EntryPrice')} | ExitTime: {eat.get('ExitTime')} | ExitPrice: {eat.get('ExitPrice')} | PnL: {eat.get('Net_Profit')}")
print(f"Replay -> EntryTime: {rept.get('EntryTime')} | EntryPrice: {rept.get('EntryPrice')} | ExitTime: {rept.get('ExitTime')} | ExitPrice: {rept.get('ExitPrice')} | PnL: {rept.get('Net_Profit')}")

print("\n=== 6 TRADE HANYA DI EA MT5 ===")
for t in unmatched_ea:
    print(f"Ticket: {t.get('Ticket')} | Time: {t.get('EntryTime')} | Type: {t.get('Type')} | Struct: {t.get('EntryStructure')} | PnL: {t.get('Net_Profit')} USD")

print("\n=== 8 TRADE HANYA DI REPLAY TRADES ===")
for t in unmatched_replay:
    print(f"Ticket: {t.get('Ticket')} | Time: {t.get('EntryTime')} | Type: {t.get('Type')} | Struct: {t.get('EntryStructure')} | CloseType: {t.get('CloseType')} | PnL: {t.get('Net_Profit')} USD")
