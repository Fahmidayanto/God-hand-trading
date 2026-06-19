"""
Market Context Provider for 2023 Gold (XAUUSD) Analysis

This module provides market context data for the year 2023, including:
- Quarterly price ranges and trends (Q1-Q4)
- Major support and resistance levels
- Significant market events with dates

The market context is used to enrich trading signal analysis with relevant
historical market conditions.
"""

from typing import Dict, List, Any


# Market context data for 2023
market_context_2023: Dict[str, Any] = {
    "Q1": {
        "period": "Jan-Mar",
        "price_range": "$1,810 → $2,050",
        "trend": "rally kuat",
        "events": [
            "Fed pivot expectation",
            "ATH baru Maret 2023",
            "SVB banking crisis Maret"
        ],
        "description": "$1,810 → $2,050 rally kuat, Fed pivot expectation, ATH baru Maret 2023, SVB banking crisis Maret"
    },
    "Q2": {
        "period": "Apr-Jun",
        "price_range": "$2,048 → $1,900",
        "trend": "koreksi signifikan",
        "events": [
            "US debt ceiling",
            "bank crisis resolution",
            "FOMC pause signal Mei"
        ],
        "description": "$2,048 → $1,900 koreksi signifikan, US debt ceiling, bank crisis resolution, FOMC pause signal Mei"
    },
    "Q3": {
        "period": "Jul-Sep",
        "price_range": "$1,893 → $1,820",
        "trend": "bearish lanjutan",
        "events": [
            "Fed hawkish stance",
            "dollar kuat",
            "low September di $1,820"
        ],
        "description": "$1,893 → $1,820 bearish lanjutan, Fed hawkish stance, dollar kuat, low September di $1,820"
    },
    "Q4": {
        "period": "Oct-Dec",
        "price_range": "$1,820 → $2,078",
        "trend": "recovery kuat akhir tahun",
        "events": [
            "ekspektasi rate cut Fed",
            "year-end rally"
        ],
        "description": "$1,820 → $2,078 recovery kuat akhir tahun, ekspektasi rate cut Fed, year-end rally"
    },
    "support_levels": [
        {"price": 1820, "description": "Sep low"},
        {"price": 1900, "description": "major support"},
        {"price": 1930, "description": "Q1 support"},
        {"price": 1940, "description": "Q1 support"}
    ],
    "resistance_levels": [
        {"price": 2000, "description": "psychological"},
        {"price": 2050, "description": "ATH Mei"},
        {"price": 1987, "description": "Jul high"}
    ],
    "major_events": [
        {"date": "2023.01.04", "event": "NFP week", "description": "Strong employment data expected"},
        {"date": "2023.01.11", "event": "CPI release", "description": "Inflation data release"},
        {"date": "2023.02.01", "event": "FOMC decision", "description": "Federal Reserve policy meeting"},
        {"date": "2023.02.03", "event": "NFP", "description": "Strong NFP data"},
        {"date": "2023.02.14", "event": "CPI release", "description": "February inflation data"},
        {"date": "2023.03.10", "event": "SVB collapse", "description": "Silicon Valley Bank banking crisis"},
        {"date": "2023.03.14", "event": "CPI release", "description": "March inflation data"},
        {"date": "2023.03.22", "event": "FOMC decision", "description": "Fed rate decision amid banking crisis"},
        {"date": "2023.04.12", "event": "CPI release", "description": "April inflation data"},
        {"date": "2023.05.03", "event": "FOMC", "description": "FOMC pause signal"},
        {"date": "2023.05.05", "event": "NFP", "description": "May employment data"},
        {"date": "2023.05.10", "event": "CPI release", "description": "May inflation data"},
        {"date": "2023.06.01", "event": "US debt ceiling", "description": "Debt ceiling resolution"},
        {"date": "2023.06.02", "event": "NFP", "description": "June employment data"},
        {"date": "2023.06.13", "event": "CPI release", "description": "June inflation data"},
        {"date": "2023.06.14", "event": "FOMC decision", "description": "Fed pauses rate hikes"},
        {"date": "2023.07.07", "event": "NFP", "description": "July employment data"},
        {"date": "2023.07.12", "event": "CPI release", "description": "July inflation data"},
        {"date": "2023.07.26", "event": "FOMC decision", "description": "Fed hawkish stance"},
        {"date": "2023.08.04", "event": "NFP", "description": "August employment data"},
        {"date": "2023.08.10", "event": "CPI release", "description": "August inflation data"},
        {"date": "2023.09.01", "event": "NFP", "description": "September employment data"},
        {"date": "2023.09.13", "event": "CPI release", "description": "September inflation data"},
        {"date": "2023.09.20", "event": "FOMC decision", "description": "Fed maintains hawkish stance"},
        {"date": "2023.10.06", "event": "NFP", "description": "October employment data"},
        {"date": "2023.10.11", "event": "CPI release", "description": "October inflation data"},
        {"date": "2023.11.01", "event": "FOMC decision", "description": "Fed signals possible pause"},
        {"date": "2023.11.03", "event": "NFP", "description": "November employment data"},
        {"date": "2023.11.14", "event": "CPI release", "description": "November inflation data"},
        {"date": "2023.12.01", "event": "NFP", "description": "December employment data"},
        {"date": "2023.12.12", "event": "CPI release", "description": "December inflation data"},
        {"date": "2023.12.13", "event": "FOMC decision", "description": "Fed signals rate cut expectations for 2024"}
    ]
}
