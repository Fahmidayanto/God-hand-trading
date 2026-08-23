import csv

ea_csv_path = r"C:\Users\fahmi\AppData\Roaming\MetaQuotes\Tester\D0E8209F77C8CF37AD8BF550E51FF075\Agent-127.0.0.1-3000\MQL5\Files\Backtest_Results_XAUUSD_2026-08-20.csv"
replay_csv_path = r"C:\Users\fahmi\Downloads\Backtest_Results_XAUUSD_2026-08-21.csv"

def load_csv(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return list(csv.DictReader(f))

ea_rows = load_csv(ea_csv_path)
replay_rows = load_csv(replay_csv_path)

targets = ["2026.06.05", "2026.05.27", "2026.02.20", "2026.01.27"]

for target in targets:
    print(f"\n================ Target: {target} ================")
    print("--- EA Trade(s) ---")
    for r in ea_rows:
        if target in r.get("EntryTime", ""):
            print(f"Ticket: {r.get('Ticket')} | Type: {r.get('Type')} | Entry: {r.get('EntryTime')} @ {r.get('EntryPrice')} | Exit: {r.get('ExitTime')} @ {r.get('ExitPrice')} | CloseType: {r.get('CloseType')} | Profit: {r.get('Net_Profit')} | SL: {r.get('FinalSL')} | TP: {r.get('FinalTP')}")
    
    print("--- Replay Trade(s) ---")
    for r in replay_rows:
        if target in r.get("EntryTime", ""):
            print(f"Ticket: {r.get('Ticket')} | Type: {r.get('Type')} | Entry: {r.get('EntryTime')} @ {r.get('EntryPrice')} | Exit: {r.get('ExitTime')} @ {r.get('ExitPrice')} | CloseType: {r.get('CloseType')} | Profit: {r.get('Net_Profit')} | SL: {r.get('FinalSL')} | TP: {r.get('FinalTP')}")
