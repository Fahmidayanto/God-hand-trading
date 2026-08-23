import csv
from pathlib import Path

BACKTEST_DIR = Path("Backtest_result")
lf = list(BACKTEST_DIR.glob("LLHHBOSData_XAUUSD_*2024*.csv"))[0]

with open(lf, "r", encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()

header = [h.strip() for h in lines[1].split(",")]
reader = csv.DictReader(lines[2:], fieldnames=header)

seen = set()
duplicates = 0
for row in reader:
    key = (row.get("Time"), row.get("Timeframe"), row.get("Type"), row.get("Price"))
    if key in seen:
        duplicates += 1
    else:
        seen.add(key)

print(f"Total baris di CSV : {len(lines) - 2}")
print(f"Baris Unik         : {len(seen)}")
print(f"Baris Duplikat CSV : {duplicates}")
