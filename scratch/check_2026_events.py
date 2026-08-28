import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, 'ValueCell_MT5/python')
from valuecell.adapters.calendar.economic_calendar import _build_calendar

events_2026 = []
for m in range(1, 9):  # Jan sd Aug
    events_2026.extend(_build_calendar(2026, m))

# Sort by time
events_2026.sort(key=lambda x: x["time"])

print(f"\nTotal Event Jan - Agt 2026: {len(events_2026)} events\n")
print(f"{'Waktu (UTC)':16} | {'Nama Event':35} | {'Impact':8} | {'Type':10}")
print("-" * 75)

for ev in events_2026:
    t_str = ev["time"].strftime("%Y-%m-%d %H:%M")
    name = ev.get("name", "Unknown")
    impact = ev.get("impact", "HIGH")
    ev_type = ev.get("type", "news")
    print(f"{t_str:16} | {name:35} | {impact:8} | {ev_type:10}")
