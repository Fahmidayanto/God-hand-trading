import csv

path = r"b:\Project MT5\Backtest_result_v1\Backtest_Results_XAUUSD_2026-08-20.csv"
with open(path, "r", encoding="utf-8", errors="ignore") as f:
    rows = list(csv.DictReader(f))

for r in rows[:10]:
    if r.get("Status", "").upper() != "REJECTED":
        print(f"Ticket: {r.get('Ticket')} | Time: {r.get('EntryTime')} | Lot: {r.get('LotSize')} | Spread_Cost: {r.get('Spread_Cost')} | Entry: {r.get('EntryPrice')} | Exit: {r.get('ExitPrice')}")
