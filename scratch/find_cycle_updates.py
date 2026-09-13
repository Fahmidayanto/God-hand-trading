import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path

ea_path = Path("B:/Project MT5/Other/Strategy_all/Dev_Bot_v12_GoldO.cs")
lines = ea_path.read_text(encoding="utf-8", errors="ignore").splitlines()

for i, line in enumerate(lines):
    if "entryCountBuy_M15" in line or "bosCycleBuy_M15" in line:
        print(f"{i+1}: {line.strip()}")

