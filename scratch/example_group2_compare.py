import csv

ea_path = r"b:\Project MT5\Backtest_result_v1\Backtest_Results_XAUUSD_2026-08-20.csv"
replay_path = r"b:\Project MT5\Backtest_result_v1\Backtest_Results_XAUUSD_2026-08-21.csv"

def find_rows(path, search_str):
    res = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for r in csv.DictReader(f):
            if search_str in r.get("EntryTime", "") or search_str in str(r.get("Ticket", "")):
                res.append(r)
    return res

print("================ CONTOH 1: Tanggal 2026.04.08 (Trade Rugi di EA) ================")
print("--- Data di File EA MT5 ---")
for r in find_rows(ea_path, "2026.04.08"):
    print(f"Ticket: {r.get('Ticket')} | Type: {r.get('Type')} | Structure: {r.get('EntryStructure')} | Status: {r.get('Status')} | Reason: {r.get('Reject_Reason')} | PnL: {r.get('Net_Profit')}")

print("\n--- Data di File Replay Trades ---")
for r in find_rows(replay_path, "2026.04.08"):
    print(f"Ticket: {r.get('Ticket')} | Type: {r.get('Type')} | Structure: {r.get('EntryStructure')} | Status: {r.get('Status')} | Reason: {r.get('Reject_Reason')} | PnL: {r.get('Net_Profit')}")

print("\n================ CONTOH 2: Tanggal 2026.01.08 (Trade Profit di EA) ================")
print("--- Data di File EA MT5 ---")
for r in find_rows(ea_path, "2026.01.08"):
    print(f"Ticket: {r.get('Ticket')} | Type: {r.get('Type')} | Structure: {r.get('EntryStructure')} | Status: {r.get('Status')} | Reason: {r.get('Reject_Reason')} | PnL: {r.get('Net_Profit')}")

print("\n--- Data di File Replay Trades ---")
for r in find_rows(replay_path, "2026.01.08"):
    print(f"Ticket: {r.get('Ticket')} | Type: {r.get('Type')} | Structure: {r.get('EntryStructure')} | Status: {r.get('Status')} | Reason: {r.get('Reject_Reason')} | PnL: {r.get('Net_Profit')}")
