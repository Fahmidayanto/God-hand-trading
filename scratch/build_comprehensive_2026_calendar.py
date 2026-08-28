import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
import pandas as pd

sys.path.insert(0, 'ValueCell_MT5/python')
from valuecell.adapters.calendar.economic_calendar import (
    _build_calendar,
    FOMC_SCHEDULE_UTC,
    _get_first_friday,
    _get_second_wednesday
)

events = []

# 1. FOMC Schedule 2026 (Jan sd Aug)
for dt in FOMC_SCHEDULE_UTC:
    if dt.year == 2026 and dt.month <= 8:
        events.append({
            "id": f"FOMC_{dt.strftime('%Y%m%d')}",
            "timestamp": dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "time_dt": dt,
            "currency": "USD",
            "event_name": "FOMC Rate Decision & Fed Press Conference",
            "impact": "HIGH",
            "category": "CENTRAL_BANK"
        })

# 2. NFP, CPI, GDP (Monthly/Quarterly)
for m in range(1, 9):
    # NFP (1st Friday, 13:30 UTC)
    nfp_dt = _get_first_friday(2026, m)
    events.append({
        "id": f"NFP_{nfp_dt.strftime('%Y%m%d')}",
        "timestamp": nfp_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "time_dt": nfp_dt,
        "currency": "USD",
        "event_name": "Non-Farm Payrolls (NFP) & Unemployment Rate",
        "impact": "HIGH",
        "category": "EMPLOYMENT"
    })
    
    # CPI (2nd Wednesday, 13:30 UTC)
    cpi_dt = _get_second_wednesday(2026, m)
    events.append({
        "id": f"CPI_{cpi_dt.strftime('%Y%m%d')}",
        "timestamp": cpi_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "time_dt": cpi_dt,
        "currency": "USD",
        "event_name": "US CPI Inflation Data (MoM / YoY)",
        "impact": "HIGH",
        "category": "INFLATION"
    })
    
    # PPI (Thursday after CPI, 13:30 UTC)
    ppi_dt = cpi_dt + timedelta(days=1)
    events.append({
        "id": f"PPI_{ppi_dt.strftime('%Y%m%d')}",
        "timestamp": ppi_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "time_dt": ppi_dt,
        "currency": "USD",
        "event_name": "US PPI Producer Price Index",
        "impact": "MEDIUM_HIGH",
        "category": "INFLATION"
    })
    
    # Retail Sales (Mid-month Tuesday/Friday, 13:30 UTC)
    retail_dt = datetime(2026, m, 15, 13, 30, tzinfo=timezone.utc)
    events.append({
        "id": f"RETAIL_{retail_dt.strftime('%Y%m%d')}",
        "timestamp": retail_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "time_dt": retail_dt,
        "currency": "USD",
        "event_name": "US Core Retail Sales",
        "impact": "MEDIUM_HIGH",
        "category": "CONSUMER"
    })

# 3. GDP Releases (Jan 30, Apr 30, Jul 30)
for m in [1, 4, 7]:
    gdp_dt = datetime(2026, m, 30, 13, 30, tzinfo=timezone.utc)
    events.append({
        "id": f"GDP_{gdp_dt.strftime('%Y%m%d')}",
        "timestamp": gdp_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "time_dt": gdp_dt,
        "currency": "USD",
        "event_name": "US GDP Advance Estimate (QoQ)",
        "impact": "HIGH",
        "category": "GROWTH"
    })

# 4. Weekly Initial Jobless Claims (Every Thursday 13:30 UTC from 2026-01-01 to 2026-08-24)
cur_dt = datetime(2026, 1, 1, 13, 30, tzinfo=timezone.utc)
end_dt = datetime(2026, 8, 24, 23, 59, tzinfo=timezone.utc)
while cur_dt <= end_dt:
    if cur_dt.weekday() == 3:  # Thursday
        events.append({
            "id": f"CLAIMS_{cur_dt.strftime('%Y%m%d')}",
            "timestamp": cur_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "time_dt": cur_dt,
            "currency": "USD",
            "event_name": "US Initial Jobless Claims",
            "impact": "MEDIUM_HIGH",
            "category": "EMPLOYMENT"
        })
    cur_dt += timedelta(days=1)

events.sort(key=lambda x: x["time_dt"])

# Add Blackout windows (+-30 mins)
for ev in events:
    dt = ev["time_dt"]
    ev["blackout_start"] = (dt - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    ev["blackout_end"] = (dt + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    # Clean temporary field
    del ev["time_dt"]

df = pd.DataFrame(events)
print(f"Total Economic News Events (Jan - Agt 2026): {len(df)} events")
print(df["category"].value_counts())
print("\nContoh 10 Event Pertama:")
print(df[["timestamp", "event_name", "impact", "category"]].head(10).to_string())
