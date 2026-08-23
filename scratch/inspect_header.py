import csv

path = r"b:\Project MT5\Backtest_result_v1\Backtest_Results_XAUUSD_2026-08-21.csv"
with open(path, "r", encoding="utf-8", errors="ignore") as f:
    reader = csv.reader(f)
    header = next(reader)
    print("HEADER:")
    print(header)
    print("\nFIRST 5 ROWS:")
    for i in range(5):
        row = next(reader, None)
        if row:
            print(row)
