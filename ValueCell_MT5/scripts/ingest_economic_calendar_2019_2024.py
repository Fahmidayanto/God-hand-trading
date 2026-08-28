"""
Ingest Economic Calendar Events for Full Historical Years (2019-2024) into LanceDB.
Covers FOMC, NFP, CPI, PPI, Retail Sales, GDP, and Weekly Jobless Claims for 2019-2024.
"""

from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from loguru import logger

# Add python module path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
PYTHON_DIR = PROJECT_ROOT / "python"
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

from valuecell.knowledge.lance_db import LanceDBManager
from valuecell.adapters.calendar.economic_calendar import (
    _get_first_friday,
    _get_second_wednesday,
)

# Official FOMC Schedules 2019-2024 (from Federal Reserve Historical Records)
FOMC_SCHEDULE_2019_2024 = [
    # 2019
    datetime(2019, 1, 30, 19, 0, tzinfo=timezone.utc),
    datetime(2019, 3, 20, 18, 0, tzinfo=timezone.utc),
    datetime(2019, 5, 1, 18, 0, tzinfo=timezone.utc),
    datetime(2019, 6, 19, 18, 0, tzinfo=timezone.utc),
    datetime(2019, 7, 31, 18, 0, tzinfo=timezone.utc),
    datetime(2019, 9, 18, 18, 0, tzinfo=timezone.utc),
    datetime(2019, 10, 30, 18, 0, tzinfo=timezone.utc),
    datetime(2019, 12, 11, 19, 0, tzinfo=timezone.utc),
    # 2020
    datetime(2020, 1, 29, 19, 0, tzinfo=timezone.utc),
    datetime(2020, 3, 3, 15, 0, tzinfo=timezone.utc),   # Emergency Cut
    datetime(2020, 3, 15, 21, 0, tzinfo=timezone.utc),  # Emergency Cut to 0%
    datetime(2020, 4, 29, 18, 0, tzinfo=timezone.utc),
    datetime(2020, 6, 10, 18, 0, tzinfo=timezone.utc),
    datetime(2020, 7, 29, 18, 0, tzinfo=timezone.utc),
    datetime(2020, 9, 16, 18, 0, tzinfo=timezone.utc),
    datetime(2020, 11, 5, 19, 0, tzinfo=timezone.utc),
    datetime(2020, 12, 16, 19, 0, tzinfo=timezone.utc),
    # 2021
    datetime(2021, 1, 27, 19, 0, tzinfo=timezone.utc),
    datetime(2021, 3, 17, 18, 0, tzinfo=timezone.utc),
    datetime(2021, 4, 28, 18, 0, tzinfo=timezone.utc),
    datetime(2021, 6, 16, 18, 0, tzinfo=timezone.utc),
    datetime(2021, 7, 28, 18, 0, tzinfo=timezone.utc),
    datetime(2021, 9, 22, 18, 0, tzinfo=timezone.utc),
    datetime(2021, 11, 3, 18, 0, tzinfo=timezone.utc),
    datetime(2021, 12, 15, 19, 0, tzinfo=timezone.utc),
    # 2022
    datetime(2022, 1, 26, 19, 0, tzinfo=timezone.utc),
    datetime(2022, 3, 16, 18, 0, tzinfo=timezone.utc),
    datetime(2022, 5, 4, 18, 0, tzinfo=timezone.utc),
    datetime(2022, 6, 15, 18, 0, tzinfo=timezone.utc),
    datetime(2022, 7, 27, 18, 0, tzinfo=timezone.utc),
    datetime(2022, 9, 21, 18, 0, tzinfo=timezone.utc),
    datetime(2022, 11, 2, 18, 0, tzinfo=timezone.utc),
    datetime(2022, 12, 14, 19, 0, tzinfo=timezone.utc),
    # 2023
    datetime(2023, 2, 1, 19, 0, tzinfo=timezone.utc),
    datetime(2023, 3, 22, 18, 0, tzinfo=timezone.utc),
    datetime(2023, 5, 3, 18, 0, tzinfo=timezone.utc),
    datetime(2023, 6, 14, 18, 0, tzinfo=timezone.utc),
    datetime(2023, 7, 26, 18, 0, tzinfo=timezone.utc),
    datetime(2023, 9, 20, 18, 0, tzinfo=timezone.utc),
    datetime(2023, 11, 1, 18, 0, tzinfo=timezone.utc),
    datetime(2023, 12, 13, 19, 0, tzinfo=timezone.utc),
    # 2024
    datetime(2024, 1, 31, 19, 0, tzinfo=timezone.utc),
    datetime(2024, 3, 20, 18, 0, tzinfo=timezone.utc),
    datetime(2024, 5, 1, 18, 0, tzinfo=timezone.utc),
    datetime(2024, 6, 12, 18, 0, tzinfo=timezone.utc),
    datetime(2024, 7, 31, 18, 0, tzinfo=timezone.utc),
    datetime(2024, 9, 18, 18, 0, tzinfo=timezone.utc),
    datetime(2024, 11, 7, 19, 0, tzinfo=timezone.utc),
    datetime(2024, 12, 18, 19, 0, tzinfo=timezone.utc),
]


def generate_events_2019_2024() -> list[dict]:
    events = []

    # 1. FOMC Schedule
    for dt in FOMC_SCHEDULE_2019_2024:
        events.append({
            "id": f"FOMC_{dt.strftime('%Y%m%d_%H%M')}",
            "timestamp": dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "year": dt.year,
            "time_dt": dt,
            "currency": "USD",
            "event_name": "FOMC Rate Decision & Fed Press Conference",
            "impact": "HIGH",
            "category": "CENTRAL_BANK",
        })

    # 2. Monthly NFP, CPI, PPI, Retail Sales for years 2019-2024
    for y in range(2019, 2025):
        for m in range(1, 13):
            # NFP (1st Friday, 13:30 UTC)
            nfp_dt = _get_first_friday(y, m)
            events.append({
                "id": f"NFP_{nfp_dt.strftime('%Y%m%d')}",
                "timestamp": nfp_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "year": y,
                "time_dt": nfp_dt,
                "currency": "USD",
                "event_name": "Non-Farm Payrolls (NFP) & Unemployment Rate",
                "impact": "HIGH",
                "category": "EMPLOYMENT",
            })

            # CPI (2nd Wednesday, 13:30 UTC)
            cpi_dt = _get_second_wednesday(y, m)
            events.append({
                "id": f"CPI_{cpi_dt.strftime('%Y%m%d')}",
                "timestamp": cpi_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "year": y,
                "time_dt": cpi_dt,
                "currency": "USD",
                "event_name": "US CPI Inflation Data (MoM / YoY)",
                "impact": "HIGH",
                "category": "INFLATION",
            })

            # PPI (Thursday after CPI, 13:30 UTC)
            ppi_dt = cpi_dt + timedelta(days=1)
            events.append({
                "id": f"PPI_{ppi_dt.strftime('%Y%m%d')}",
                "timestamp": ppi_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "year": y,
                "time_dt": ppi_dt,
                "currency": "USD",
                "event_name": "US PPI Producer Price Index",
                "impact": "MEDIUM_HIGH",
                "category": "INFLATION",
            })

            # Retail Sales (Mid-month, 13:30 UTC)
            retail_dt = datetime(y, m, 15, 13, 30, tzinfo=timezone.utc)
            events.append({
                "id": f"RETAIL_{retail_dt.strftime('%Y%m%d')}",
                "timestamp": retail_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "year": y,
                "time_dt": retail_dt,
                "currency": "USD",
                "event_name": "US Core Retail Sales",
                "impact": "MEDIUM_HIGH",
                "category": "CONSUMER",
            })

        # 3. GDP Releases (Jan 30, Apr 30, Jul 30, Oct 30)
        for m in [1, 4, 7, 10]:
            gdp_dt = datetime(y, m, 30, 13, 30, tzinfo=timezone.utc)
            events.append({
                "id": f"GDP_{gdp_dt.strftime('%Y%m%d')}",
                "timestamp": gdp_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "year": y,
                "time_dt": gdp_dt,
                "currency": "USD",
                "event_name": "US GDP Advance Estimate (QoQ)",
                "impact": "HIGH",
                "category": "GROWTH",
            })

        # 4. Weekly Jobless Claims (Every Thursday)
        cur_dt = datetime(y, 1, 1, 13, 30, tzinfo=timezone.utc)
        end_dt = datetime(y, 12, 31, 23, 59, tzinfo=timezone.utc)
        while cur_dt <= end_dt:
            if cur_dt.weekday() == 3:  # Thursday
                events.append({
                    "id": f"CLAIMS_{cur_dt.strftime('%Y%m%d')}",
                    "timestamp": cur_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "year": y,
                    "time_dt": cur_dt,
                    "currency": "USD",
                    "event_name": "US Initial Jobless Claims",
                    "impact": "MEDIUM_HIGH",
                    "category": "EMPLOYMENT",
                })
            cur_dt += timedelta(days=1)

    # Sort chronologically
    events.sort(key=lambda x: x["time_dt"])

    # Calculate Blackout Windows (+-30 mins)
    for ev in events:
        dt = ev["time_dt"]
        ev["blackout_start"] = (dt - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        ev["blackout_end"] = (dt + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        ev["vector"] = [0.0, 0.0]
        del ev["time_dt"]

    return events


def main() -> int:
    logger.info("Initializing LanceDB Manager for 2019-2024 Ingestion...")
    db = LanceDBManager()

    events = generate_events_2019_2024()
    logger.info(f"Generated {len(events)} economic events for 2019-2024")

    # Add events to LanceDB
    success = db.add_economic_calendar_events(events)
    if not success:
        logger.error("Failed to insert 2019-2024 economic events into LanceDB")
        return 1

    # Verify total table contents
    tbl = db.db.open_table("economic_calendar_events")
    df = tbl.search().to_pandas()
    logger.info(f"✅ Ingestion complete! LanceDB 'economic_calendar_events' total count: {len(df)} rows")
    logger.info(f"Breakdown per Year:\n{df['year'].value_counts().sort_index().to_string()}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
