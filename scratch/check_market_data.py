import csv

path = r"b:\Project MT5\Backtest_result\MarketData_XAUUSD_M15_2026-08-21.csv"
with open(path, "r", encoding="utf-8", errors="ignore") as f:
    for row in csv.DictReader(f):
        t_str = row.get("Time", "") or row.get("time", "")
        if "2026.01.06" in t_str and ("04:" in t_str or "05:" in t_str):
            print(f"Time: {t_str} | Open: {row.get('Open')} | High: {row.get('High')} | Low: {row.get('Low')} | Close: {row.get('Close')} | Spread: {row.get('Spread')}")
