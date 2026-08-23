import csv

market_data_path = r"b:\Project MT5\Backtest_result\MarketData_XAUUSD_M15_2026-08-21.csv"
ea_csv_path = r"b:\Project MT5\Backtest_result_v1\Backtest_Results_XAUUSD_2026-08-20.csv"
replay_csv_path = r"b:\Project MT5\Backtest_result_v1\Backtest_Results_XAUUSD_2026-08-21.csv"

print("--- 1. Market Data M15 (Candlestick Data) ---")
with open(market_data_path, "r", encoding="utf-8", errors="ignore") as f:
    r = csv.DictReader(f)
    for row in r:
        if "2026.01.05" in row.get("Time", "") and ("04:45" in row.get("Time", "") or "05:00" in row.get("Time", "")):
            print(row)

print("\n--- 2. Replay Trades Result (Row 1) ---")
with open(replay_csv_path, "r", encoding="utf-8", errors="ignore") as f:
    r = csv.DictReader(f)
    for row in r:
        if row.get("Ticket") == "2" or "2026.01.05" in row.get("EntryTime", ""):
            print({k: row[k] for k in ["Ticket", "Type", "EntryTime", "EntryPrice", "FinalSL", "FinalTP", "ExitTime", "ExitPrice", "Net_Profit"]})
            break

print("\n--- 3. EA MT5 Backtest Result (Row 1) ---")
with open(ea_csv_path, "r", encoding="utf-8", errors="ignore") as f:
    r = csv.DictReader(f)
    for row in r:
        if row.get("Ticket") == "2" or "2026.01.05" in row.get("EntryTime", ""):
            print({k: row[k] for k in ["Ticket", "Type", "EntryTime", "EntryPrice", "FinalSL", "FinalTP", "ExitTime", "ExitPrice", "Spread_Cost", "Net_Profit"]})
            break
