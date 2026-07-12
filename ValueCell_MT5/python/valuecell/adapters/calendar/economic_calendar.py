"""
Economic Calendar Adapter (Sprint 2) - Jadwal event ekonomi berdampak tinggi untuk XAUUSD.

Ponytail: copied from backend/app/services/economic_calendar_service.py
because the FastAPI backend and the valuecell trading system live in
separate packages with separate dependency footprints. Cross-package
import would mean sys.path hacks or a shared package — both worse than
~200 lines of stdlib-only calendar math.

Drift risk: low (FOMC dates + monthly rule-of-thumb don't change often).
If divergence becomes a problem, promote this to a shared package.

Adds ``get_upcoming_events_naive()`` wrapper that strips tzinfo so the
return value can be safely mixed with MT5 tz-naive bar times inside
SentimentAgent.

Original Indonesian strategy (kept for provenance):
1. FOMC 2025-2026 official schedule (fixed)
2. NFP: first Friday each month, 13:30 UTC
3. CPI: 2nd Wednesday each month, 13:30 UTC
4. Unemployment/Initial Claims: every Thursday, 13:30 UTC
5. Output events within N-hour lookahead window
No API key needed — based on official published calendars.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def get_upcoming_events_naive(hours_ahead: int = 24) -> List[Dict[str, Any]]:
    """Same as ``get_upcoming_events`` but with tz-naive UTC timestamps.

    SentimentAgent compares event times against MT5's tz-naive bar time;
    mixing tz-aware events with tz-naive current_time raises TypeError.
    Ponytail: normalize at the boundary, not inside the agent.
    """
    events = get_upcoming_events(hours_ahead=hours_ahead)
    out: List[Dict[str, Any]] = []
    for ev in events:
        ev = dict(ev)
        t = ev.get("time")
        if isinstance(t, datetime) and t.tzinfo is not None:
            ev["time"] = t.astimezone(timezone.utc).replace(tzinfo=None)
        out.append(ev)
    return out

# ─── Cache sederhana ────────────────────────────────────────────────────────────
import time
_EVENT_CACHE: Optional[List[Dict[str, Any]]] = None
_EVENT_CACHE_TIME: float = 0
_EVENT_CACHE_TTL = 3600  # 1 jam (jadwal tidak berubah-berubah)


# ─── Jadwal FOMC 2025-2026 (Dari Federal Reserve resmi) ─────────────────────
# https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
FOMC_SCHEDULE_UTC = [
    # 2025
    datetime(2025, 1, 29, 19, 0, tzinfo=timezone.utc),
    datetime(2025, 3, 19, 18, 0, tzinfo=timezone.utc),
    datetime(2025, 5, 7, 18, 0, tzinfo=timezone.utc),
    datetime(2025, 6, 18, 18, 0, tzinfo=timezone.utc),
    datetime(2025, 7, 30, 18, 0, tzinfo=timezone.utc),
    datetime(2025, 9, 17, 18, 0, tzinfo=timezone.utc),
    datetime(2025, 10, 29, 18, 0, tzinfo=timezone.utc),
    datetime(2025, 12, 10, 19, 0, tzinfo=timezone.utc),
    # 2026
    datetime(2026, 1, 28, 19, 0, tzinfo=timezone.utc),
    datetime(2026, 3, 18, 18, 0, tzinfo=timezone.utc),
    datetime(2026, 4, 29, 18, 0, tzinfo=timezone.utc),
    datetime(2026, 6, 17, 18, 0, tzinfo=timezone.utc),
    datetime(2026, 7, 29, 18, 0, tzinfo=timezone.utc),
    datetime(2026, 9, 16, 18, 0, tzinfo=timezone.utc),
    datetime(2026, 10, 28, 18, 0, tzinfo=timezone.utc),
    datetime(2026, 12, 9, 19, 0, tzinfo=timezone.utc),
]


def _get_first_friday(year: int, month: int) -> datetime:
    """Dapatkan Jumat pertama bulan tersebut (NFP release day)."""
    d = datetime(year, month, 1, 13, 30, tzinfo=timezone.utc)
    # Weekday: Monday=0, Friday=4
    days_until_friday = (4 - d.weekday()) % 7
    return d + timedelta(days=days_until_friday)


def _get_second_wednesday(year: int, month: int) -> datetime:
    """Dapatkan Rabu ke-2 bulan tersebut (CPI release day)."""
    d = datetime(year, month, 1, 13, 30, tzinfo=timezone.utc)
    days_until_wednesday = (2 - d.weekday()) % 7  # Wednesday=2
    first_wednesday = d + timedelta(days=days_until_wednesday)
    return first_wednesday + timedelta(weeks=1)


def _get_next_thursday(from_dt: datetime) -> datetime:
    """Dapatkan Kamis berikutnya (Initial Jobless Claims)."""
    days_until_thursday = (3 - from_dt.weekday()) % 7  # Thursday=3
    if days_until_thursday == 0:
        days_until_thursday = 7  # Sudah Kamis hari ini, ambil minggu depan
    return from_dt.replace(hour=13, minute=30, second=0, microsecond=0, tzinfo=timezone.utc) + timedelta(days=days_until_thursday)


def _build_calendar(year: int, month: int) -> List[Dict[str, Any]]:
    """Bangun kalender event untuk satu bulan tertentu."""
    events = []

    # NFP - Non-Farm Payrolls (Jumat pertama, 13:30 UTC)
    nfp_dt = _get_first_friday(year, month)
    events.append({
        "name": "Non-Farm Payrolls (NFP)",
        "time": nfp_dt,
        "impact": "high",
        "avoid_trading": True,
        "description": "US monthly employment report - major market mover"
    })

    # CPI - Consumer Price Index (Rabu ke-2, 13:30 UTC)
    cpi_dt = _get_second_wednesday(year, month)
    events.append({
        "name": "CPI Inflation Data",
        "time": cpi_dt,
        "impact": "high",
        "avoid_trading": False,
        "description": "US Consumer Price Index - key inflation indicator"
    })

    # GDP rilis kuartalan (awal bulan pertama setiap kuartal: Jan, Apr, Jul, Oct)
    if month in [1, 4, 7, 10]:
        gdp_dt = datetime(year, month, 30, 13, 30, tzinfo=timezone.utc)
        events.append({
            "name": "GDP Advance Estimate",
            "time": gdp_dt,
            "impact": "high",
            "avoid_trading": False,
            "description": "US GDP growth rate - quarterly economic health indicator"
        })

    return events


def _build_fomc_events() -> List[Dict[str, Any]]:
    """Bangun daftar event FOMC dari jadwal resmi."""
    return [
        {
            "name": "FOMC Rate Decision",
            "time": dt,
            "impact": "high",
            "avoid_trading": True,
            "description": "Federal Open Market Committee interest rate decision"
        }
        for dt in FOMC_SCHEDULE_UTC
    ]


def _get_weekly_events(from_dt: datetime, weeks_ahead: int = 2) -> List[Dict[str, Any]]:
    """Dapatkan event mingguan (Initial Jobless Claims tiap Kamis)."""
    events = []
    current = from_dt
    for _ in range(weeks_ahead):
        thursday = _get_next_thursday(current)
        events.append({
            "name": "Initial Jobless Claims",
            "time": thursday,
            "impact": "medium",
            "avoid_trading": False,
            "description": "Weekly US unemployment insurance claims"
        })
        current = thursday + timedelta(days=1)
    return events


def get_upcoming_events(hours_ahead: int = 24) -> List[Dict[str, Any]]:
    """
    Dapatkan daftar event ekonomi berdampak tinggi dalam window waktu tertentu.

    Event yang dicakup:
    - FOMC Rate Decision (jadwal resmi 2025-2026)
    - NFP Non-Farm Payrolls (Jumat pertama setiap bulan)
    - CPI Inflation Data (Rabu ke-2 setiap bulan)
    - GDP Advance Estimate (kuartalan)
    - Initial Jobless Claims (setiap Kamis)

    Args:
        hours_ahead: Window waktu ke depan dalam jam (default: 24 jam)

    Returns:
        List of event dicts dengan field: name, time, impact, avoid_trading, description
        Diurutkan dari yang paling dekat
    """
    global _EVENT_CACHE, _EVENT_CACHE_TIME

    now_utc = datetime.now(timezone.utc)

    # Cek cache (1 jam)
    if _EVENT_CACHE is not None and (time.time() - _EVENT_CACHE_TIME) < _EVENT_CACHE_TTL:
        # Filter dari cache sesuai window
        window_end = now_utc + timedelta(hours=hours_ahead)
        upcoming = [e for e in _EVENT_CACHE if now_utc <= e["time"] <= window_end]
        logger.debug(f"[EconCalendar] Cache hit: {len(upcoming)} events in next {hours_ahead}h")
        return sorted(upcoming, key=lambda x: x["time"])

    try:
        all_events: List[Dict[str, Any]] = []

        # 1. Tambahkan FOMC events (jadwal resmi)
        all_events.extend(_build_fomc_events())

        # 2. Tambahkan event bulanan untuk 3 bulan ke depan
        for month_offset in range(-1, 3):
            month = (now_utc.month - 1 + month_offset) % 12 + 1
            year = now_utc.year + ((now_utc.month - 1 + month_offset) // 12)
            all_events.extend(_build_calendar(year, month))

        # 3. Tambahkan event mingguan (Jobless Claims 4 minggu ke depan)
        all_events.extend(_get_weekly_events(now_utc, weeks_ahead=4))

        # Simpan ke cache
        _EVENT_CACHE = all_events
        _EVENT_CACHE_TIME = time.time()

        # Filter sesuai window
        window_end = now_utc + timedelta(hours=hours_ahead)
        upcoming = [e for e in all_events if now_utc <= e["time"] <= window_end]
        upcoming_sorted = sorted(upcoming, key=lambda x: x["time"])

        logger.info(
            f"[EconCalendar] {len(upcoming_sorted)} events in next {hours_ahead}h "
            f"(from {len(all_events)} total scheduled)"
        )

        if upcoming_sorted:
            for ev in upcoming_sorted:
                hours_away = (ev["time"] - now_utc).total_seconds() / 3600
                logger.info(
                    f"[EconCalendar]   → {ev['name']} | "
                    f"{ev['time'].strftime('%Y-%m-%d %H:%M')} UTC | "
                    f"Impact: {ev['impact']} | "
                    f"~{hours_away:.1f}h away"
                )

        return upcoming_sorted

    except Exception as exc:
        logger.warning(f"[EconCalendar] Failed to build calendar: {exc}")
        return []


def get_next_major_event() -> Optional[Dict[str, Any]]:
    """
    Shortcut: Dapatkan event HIGH IMPACT berikutnya dalam 72 jam ke depan.
    Berguna untuk LLM reasoning context.
    """
    events = get_upcoming_events(hours_ahead=72)
    high_impact = [e for e in events if e.get("impact") == "high"]
    return high_impact[0] if high_impact else None
