from pathlib import Path

ea_path = Path("B:/Project MT5/Other/Strategy_all/Dev_Bot_v12_GoldO.cs")
lines = ea_path.read_text(encoding="utf-8", errors="ignore").splitlines()

for i, line in enumerate(lines):
    if "postChoCH_HH_M15" in line or "postChoCH_LL_M15" in line or "absoluteHighestHH_M15" in line:
        print(f"{i+1}: {line.strip()}")

