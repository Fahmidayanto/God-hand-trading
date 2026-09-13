import csv
from datetime import datetime
from pathlib import Path

csv_path = Path("B:/Project MT5/Backtest_result/LLHHBOSData_XAUUSD_2026-09-04.csv")

events = []
with open(csv_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()
    header_idx = -1
    for i, line in enumerate(lines):
        if line.startswith("Type,Direction"):
            header_idx = i
            break
    
    reader = csv.DictReader(lines[header_idx:])
    for row_idx, row in enumerate(reader):
        t = row.get("Type", "").strip()
        d = row.get("Direction/Action", "").strip()
        p = row.get("Price", "").strip()
        tm = row.get("Time", "").strip()
        tf = row.get("Timeframe", "").strip()
        st = row.get("Status", "").strip()
        prev_p = row.get("PreviousPrice", "").strip()
        prev_tm = row.get("PreviousTime", "").strip()
        
        if not t or not tm:
            continue
        events.append({
            "idx": row_idx + 3,
            "type": t,
            "direction": d,
            "price": float(p) if p else 0.0,
            "time": tm,
            "timeframe": tf,
            "status": st,
            "prev_price": float(prev_p) if prev_p else 0.0,
            "prev_time": prev_tm
        })

print(f"Total events: {len(events)}")
print("\nLast 25 events as written in CSV:")
for ev in events[-25:]:
    print(f"Line {ev['idx']}: {ev['time']} | {ev['type']} | {ev['direction']} | {ev['price']} | {ev['status']}")

# Now sort by time to see chronological sequence
events_sorted = sorted(events, key=lambda x: x["time"])

print("\nLast 25 events sorted chronologically by time:")
for ev in events_sorted[-25:]:
    print(f"Line {ev['idx']}: {ev['time']} | {ev['type']} | {ev['direction']} | {ev['price']} | {ev['status']}")

