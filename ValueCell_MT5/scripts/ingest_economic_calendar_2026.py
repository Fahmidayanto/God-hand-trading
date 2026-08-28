"""
Ingest Economic Calendar Events for 2026 into LanceDB.
Covers FOMC, NFP, CPI, PPI, Retail Sales, GDP, and Weekly Jobless Claims.
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
    FOMC_SCHEDULE_UTC,
    _get_first_friday,
    _get_second_wednesday,
)


def generate_2026_events() -> list[dict]:
    events = []

    # 1. FOMC Schedule 2026 (Jan sd Aug)
    for dt in FOMC_SCHEDULE_UTC:
        if dt.year == 2026 and dt.month <= 8:
            events.append({
                "id": f"FOMC_{dt.strftime('%Y%m%d')}",
                "timestamp": dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "year": 2026,
                "time_dt": dt,
                "currency": "USD",
                "event_name": "FOMC Rate Decision & Fed Press Conference",
                "impact": "HIGH",
                "category": "CENTRAL_BANK",
            })

    # 2. Monthly NFP, CPI, PPI, Retail Sales
    for m in range(1, 9):
        # NFP (1st Friday, 13:30 UTC)
        nfp_dt = _get_first_friday(2026, m)
        events.append({
            "id": f"NFP_{nfp_dt.strftime('%Y%m%d')}",
            "timestamp": nfp_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "year": 2026,
            "time_dt": nfp_dt,
            "currency": "USD",
            "event_name": "Non-Farm Payrolls (NFP) & Unemployment Rate",
            "impact": "HIGH",
            "category": "EMPLOYMENT",
        })

        # CPI (2nd Wednesday, 13:30 UTC)
        cpi_dt = _get_second_wednesday(2026, m)
        events.append({
            "id": f"CPI_{cpi_dt.strftime('%Y%m%d')}",
            "timestamp": cpi_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "year": 2026,
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
            "year": 2026,
            "time_dt": ppi_dt,
            "currency": "USD",
            "event_name": "US PPI Producer Price Index",
            "impact": "MEDIUM_HIGH",
            "category": "INFLATION",
        })

        # Retail Sales (Mid-month, 13:30 UTC)
        retail_dt = datetime(2026, m, 15, 13, 30, tzinfo=timezone.utc)
        events.append({
            "id": f"RETAIL_{retail_dt.strftime('%Y%m%d')}",
            "timestamp": retail_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "year": 2026,
            "time_dt": retail_dt,
            "currency": "USD",
            "event_name": "US Core Retail Sales",
            "impact": "MEDIUM_HIGH",
            "category": "CONSUMER",
        })

    # 3. GDP Releases (Jan 30, Apr 30, Jul 30)
    for m in [1, 4, 7]:
        gdp_dt = datetime(2026, m, 30, 13, 30, tzinfo=timezone.utc)
        events.append({
            "id": f"GDP_{gdp_dt.strftime('%Y%m%d')}",
            "timestamp": gdp_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "year": 2026,
            "time_dt": gdp_dt,
            "currency": "USD",
            "event_name": "US GDP Advance Estimate (QoQ)",
            "impact": "HIGH",
            "category": "GROWTH",
        })

    # 4. Weekly Jobless Claims (Every Thursday 13:30 UTC)
    cur_dt = datetime(2026, 1, 1, 13, 30, tzinfo=timezone.utc)
    end_dt = datetime(2026, 8, 24, 23, 59, tzinfo=timezone.utc)
    while cur_dt <= end_dt:
        if cur_dt.weekday() == 3:  # Thursday
            events.append({
                "id": f"CLAIMS_{cur_dt.strftime('%Y%m%d')}",
                "timestamp": cur_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "year": 2026,
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
    logger.info("Initializing LanceDB Manager...")
    db = LanceDBManager()

    # Drop existing table if exists for a fresh clean insert
    if "economic_calendar_events" in db._table_names():
        try:
            db.db.drop_table("economic_calendar_events")
            logger.info("Dropped existing 'economic_calendar_events' table")
        except Exception as e:
            logger.warning(f"Drop table warning: {e}")

    events = generate_2026_events()
    logger.info(f"Generated {len(events)} economic events for 2026 (Jan - Aug)")

    success = db.add_economic_calendar_events(events)
    if not success:
        logger.error("Failed to insert economic events into LanceDB")
        return 1

    # Verify table contents
    tbl = db.db.open_table("economic_calendar_events")
    df = tbl.search().to_pandas()
    logger.info(f"✅ Ingestion complete! LanceDB 'economic_calendar_events' count: {len(df)} rows")

    # Test Blackout Check
    test_time = "2026-01-28T18:45:00Z"  # 15 mins before FOMC
    res = db.check_news_blackout(test_time)
    logger.info(f"🧪 Test Blackout Check for {test_time}: {res}")

    test_time_safe = "2026-01-28T12:00:00Z"  # Safe time
    res_safe = db.check_news_blackout(test_time_safe)
    logger.info(f"🧪 Test Safe Check for {test_time_safe}: {res_safe}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
