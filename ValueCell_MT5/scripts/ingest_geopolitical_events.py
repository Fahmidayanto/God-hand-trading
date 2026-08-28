"""
Ingest Major Geopolitical & Crisis Events (2019-2026) into LanceDB.
Covers major war escalations, bank runs, emergency Fed cuts, weekend gap triggers, and pandemic events.
"""

from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from loguru import logger
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
PYTHON_DIR = PROJECT_ROOT / "python"
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

from valuecell.knowledge.lance_db import LanceDBManager

GEOPOLITICAL_CRISIS_EVENTS = [
    # 2019
    {
        "id": "GEO_20190801",
        "timestamp": "2019-08-01T17:30:00Z",
        "year": 2019,
        "currency": "USD",
        "event_name": "US Announces 10% Tariffs on 300B Chinese Imports",
        "impact": "HIGH",
        "category": "GEOPOLITICAL",
        "blackout_start": "2019-08-01T16:00:00Z",
        "blackout_end": "2019-08-01T21:00:00Z",
    },
    {
        "id": "GEO_20190914",
        "timestamp": "2019-09-14T03:00:00Z",  # Saturday
        "year": 2019,
        "currency": "USD",
        "event_name": "Saudi Aramco Abqaiq Drone Attack (Weekend Gap Trigger)",
        "impact": "HIGH",
        "category": "GEOPOLITICAL",
        "blackout_start": "2019-09-13T20:00:00Z",
        "blackout_end": "2019-09-16T04:00:00Z",
    },
    # 2020
    {
        "id": "GEO_20200103",
        "timestamp": "2020-01-03T01:00:00Z",
        "year": 2020,
        "currency": "USD",
        "event_name": "US Airstrike in Baghdad (Soleimani Escalation)",
        "impact": "HIGH",
        "category": "GEOPOLITICAL",
        "blackout_start": "2020-01-03T00:00:00Z",
        "blackout_end": "2020-01-03T06:00:00Z",
    },
    {
        "id": "GEO_20200303",
        "timestamp": "2020-03-03T15:00:00Z",
        "year": 2020,
        "currency": "USD",
        "event_name": "Fed Emergency 50bps Inter-Meeting Rate Cut (COVID Shock)",
        "impact": "HIGH",
        "category": "CRISIS",
        "blackout_start": "2020-03-03T14:00:00Z",
        "blackout_end": "2020-03-03T18:00:00Z",
    },
    {
        "id": "GEO_20200311",
        "timestamp": "2020-03-11T16:30:00Z",
        "year": 2020,
        "currency": "USD",
        "event_name": "WHO Officially Declares COVID-19 Global Pandemic",
        "impact": "HIGH",
        "category": "CRISIS",
        "blackout_start": "2020-03-11T15:00:00Z",
        "blackout_end": "2020-03-11T20:00:00Z",
    },
    {
        "id": "GEO_20200315",
        "timestamp": "2020-03-15T21:00:00Z",  # Sunday Emergency
        "year": 2020,
        "currency": "USD",
        "event_name": "Fed Emergency Sunday 100bps Cut to 0% and 700B QE",
        "impact": "HIGH",
        "category": "CRISIS",
        "blackout_start": "2020-03-13T20:00:00Z",
        "blackout_end": "2020-03-16T04:00:00Z",
    },
    {
        "id": "GEO_20200323",
        "timestamp": "2020-03-23T12:00:00Z",
        "year": 2020,
        "currency": "USD",
        "event_name": "Fed Announces Unlimited QE (Historic Gold Bottom Reversal)",
        "impact": "HIGH",
        "category": "CRISIS",
        "blackout_start": "2020-03-23T11:00:00Z",
        "blackout_end": "2020-03-23T16:00:00Z",
    },
    {
        "id": "GEO_20201109",
        "timestamp": "2020-11-09T11:45:00Z",
        "year": 2020,
        "currency": "USD",
        "event_name": "Pfizer-BioNTech Vaccine 90% Efficacy Release (Gold Flash Dump)",
        "impact": "HIGH",
        "category": "CRISIS",
        "blackout_start": "2020-11-09T11:00:00Z",
        "blackout_end": "2020-11-09T16:00:00Z",
    },
    # 2021
    {
        "id": "GEO_20210809",
        "timestamp": "2021-08-09T00:30:00Z",
        "year": 2021,
        "currency": "USD",
        "event_name": "Asian Session Gold Flash Crash (Liquidity Vacuum 1760 to 1680)",
        "impact": "HIGH",
        "category": "CRISIS",
        "blackout_start": "2021-08-08T22:00:00Z",
        "blackout_end": "2021-08-09T04:00:00Z",
    },
    # 2022
    {
        "id": "GEO_20220224",
        "timestamp": "2022-02-24T03:00:00Z",
        "year": 2022,
        "currency": "USD",
        "event_name": "Russia Military Operation in Ukraine (War Escalation)",
        "impact": "HIGH",
        "category": "GEOPOLITICAL",
        "blackout_start": "2022-02-24T02:00:00Z",
        "blackout_end": "2022-02-24T12:00:00Z",
    },
    {
        "id": "GEO_20220308",
        "timestamp": "2022-03-08T16:30:00Z",
        "year": 2022,
        "currency": "USD",
        "event_name": "US Bans Russian Oil & Energy Imports (Gold Peak $2070)",
        "impact": "HIGH",
        "category": "GEOPOLITICAL",
        "blackout_start": "2022-03-08T15:00:00Z",
        "blackout_end": "2022-03-08T20:00:00Z",
    },
    {
        "id": "GEO_20220926",
        "timestamp": "2022-09-26T00:00:00Z",
        "year": 2022,
        "currency": "USD",
        "event_name": "Nord Stream Pipeline Sabotage Explosions",
        "impact": "HIGH",
        "category": "GEOPOLITICAL",
        "blackout_start": "2022-09-25T22:00:00Z",
        "blackout_end": "2022-09-26T06:00:00Z",
    },
    # 2023
    {
        "id": "GEO_20230310",
        "timestamp": "2023-03-10T16:00:00Z",
        "year": 2023,
        "currency": "USD",
        "event_name": "Silicon Valley Bank (SVB) Collapses (US Banking Crisis)",
        "impact": "HIGH",
        "category": "CRISIS",
        "blackout_start": "2023-03-10T15:00:00Z",
        "blackout_end": "2023-03-10T21:00:00Z",
    },
    {
        "id": "GEO_20230319",
        "timestamp": "2023-03-19T18:00:00Z",  # Sunday
        "year": 2023,
        "currency": "USD",
        "event_name": "UBS Emergency Takeover of Credit Suisse & Fed Liquidity Swap",
        "impact": "HIGH",
        "category": "CRISIS",
        "blackout_start": "2023-03-17T20:00:00Z",
        "blackout_end": "2023-03-20T04:00:00Z",
    },
    {
        "id": "GEO_20231007",
        "timestamp": "2023-10-07T04:00:00Z",  # Saturday
        "year": 2023,
        "currency": "USD",
        "event_name": "Middle East Conflict Escalation (Gaza Outbreak - Massive Weekend Gap)",
        "impact": "HIGH",
        "category": "GEOPOLITICAL",
        "blackout_start": "2023-10-06T20:00:00Z",
        "blackout_end": "2023-10-09T04:00:00Z",
    },
    {
        "id": "GEO_20231204",
        "timestamp": "2023-12-04T00:00:00Z",
        "year": 2023,
        "currency": "USD",
        "event_name": "Asian Session Extreme Spike to New All-Time High $2148",
        "impact": "HIGH",
        "category": "CRISIS",
        "blackout_start": "2023-12-03T22:00:00Z",
        "blackout_end": "2023-12-04T04:00:00Z",
    },
    # 2024
    {
        "id": "GEO_20240413",
        "timestamp": "2024-04-13T20:00:00Z",  # Saturday
        "year": 2024,
        "currency": "USD",
        "event_name": "Iran Launches Drone & Missile Attack Toward Israel (Weekend Gap)",
        "impact": "HIGH",
        "category": "GEOPOLITICAL",
        "blackout_start": "2024-04-12T20:00:00Z",
        "blackout_end": "2024-04-15T04:00:00Z",
    },
    {
        "id": "GEO_20240419",
        "timestamp": "2024-04-19T01:30:00Z",
        "year": 2024,
        "currency": "USD",
        "event_name": "Israel Retaliatory Strikes Near Isfahan Iran (Intraday Spike $2417)",
        "impact": "HIGH",
        "category": "GEOPOLITICAL",
        "blackout_start": "2024-04-19T00:00:00Z",
        "blackout_end": "2024-04-19T06:00:00Z",
    },
    {
        "id": "GEO_20240805",
        "timestamp": "2024-08-05T01:00:00Z",
        "year": 2024,
        "currency": "USD",
        "event_name": "Black Monday Global Liquidity Crunch & Yen Carry Trade Unwind",
        "impact": "HIGH",
        "category": "CRISIS",
        "blackout_start": "2024-08-04T22:00:00Z",
        "blackout_end": "2024-08-05T08:00:00Z",
    },
    {
        "id": "GEO_20241001",
        "timestamp": "2024-10-01T16:30:00Z",
        "year": 2024,
        "currency": "USD",
        "event_name": "Iran Fires 180 Ballistic Missiles into Israel",
        "impact": "HIGH",
        "category": "GEOPOLITICAL",
        "blackout_start": "2024-10-01T15:00:00Z",
        "blackout_end": "2024-10-01T21:00:00Z",
    },
    # 2025
    {
        "id": "GEO_20250120",
        "timestamp": "2025-01-20T17:00:00Z",
        "year": 2025,
        "currency": "USD",
        "event_name": "US Presidential Transition & Global Tariff Policy Shift",
        "impact": "HIGH",
        "category": "GEOPOLITICAL",
        "blackout_start": "2025-01-20T15:00:00Z",
        "blackout_end": "2025-01-20T22:00:00Z",
    },
    {
        "id": "GEO_20250512",
        "timestamp": "2025-05-12T02:00:00Z",
        "year": 2025,
        "currency": "USD",
        "event_name": "Global Central Bank Reserve Diversification Surge Announcement",
        "impact": "HIGH",
        "category": "GEOPOLITICAL",
        "blackout_start": "2025-05-11T22:00:00Z",
        "blackout_end": "2025-05-12T06:00:00Z",
    },
    # 2026
    {
        "id": "GEO_20260215",
        "timestamp": "2026-02-15T10:00:00Z",  # Sunday
        "year": 2026,
        "currency": "USD",
        "event_name": "Emergency Global Diplomatic & Trade Coalition Talks (Weekend Gap)",
        "impact": "HIGH",
        "category": "GEOPOLITICAL",
        "blackout_start": "2026-02-13T20:00:00Z",
        "blackout_end": "2026-02-16T04:00:00Z",
    },
]


def main() -> int:
    logger.info("Initializing LanceDB Manager to Ingest Geopolitical Events...")
    db = LanceDBManager()

    logger.info("Inserting {} major geopolitical and crisis events...", len(GEOPOLITICAL_CRISIS_EVENTS))
    success = db.add_economic_calendar_events(GEOPOLITICAL_CRISIS_EVENTS)
    if not success:
        logger.error("Failed to insert geopolitical events")
        return 1

    tbl = db.db.open_table("economic_calendar_events")
    df = tbl.search().to_pandas()
    logger.info("✅ Geopolitical events ingestion complete! Total events in LanceDB: {} rows", len(df))
    logger.info("Breakdown by Category:\n{}", df["category"].value_counts().to_string())

    # Test Blackout on a weekend crisis (e.g. Hamas Attack Sunday 2023-10-08 or Monday morning)
    test_time = "2023-10-09T00:30:00Z"
    res = db.check_news_blackout(test_time)
    logger.info("🧪 Test Blackout Check for 2023 Middle East Weekend Gap ({}): {}", test_time, res)

    return 0


if __name__ == "__main__":
    sys.exit(main())
