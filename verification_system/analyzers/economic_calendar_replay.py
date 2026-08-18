"""
Economic Calendar (Replay-Safe) - Time-Anchored Event Lookup

Time-anchored version of economic_calendar_service untuk replay trades.
PENTING: tidak baca "datetime.now()" — semua event lookup di-anchor ke
timestamp yang diberikan. Aman untuk backtesting tanpa look-ahead bias.

Cakupan:
- FOMC 2023-2026 (jadwal resmi Fed)
- NFP (Jumat pertama setiap bulan, 13:30 UTC)
- CPI (Rabu ke-2 setiap bulan, 13:30 UTC)
- GDP Advance Estimate (kuartalan)
- Initial Jobless Claims (setiap Kamis, 13:30 UTC)
- 2023 major events dari market_context_2023 (CPI/FOMC/NFP spesifik)

Ponytail: stateless, time-anchored, no cache, no DB.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any

from loguru import logger


# ── FOMC schedule (resmi Federal Reserve) ──────────────────────────────────
# https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
# Format: datetime dengan 13:30 UTC untuk press release (saat decision diumumkan)

FOMC_SCHEDULE_UTC: List[datetime] = [
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


# ── Data class ─────────────────────────────────────────────────────────────

@dataclass
class EconomicEvent:
    name: str
    time: datetime
    impact: str  # "high" | "medium" | "low"
    avoid_trading: bool
    description: str
    category: str  # "fomc" | "nfp" | "cpi" | "gdp" | "jobless" | "other"

    def hours_until(self, anchor: datetime) -> float:
        return (self.time - anchor).total_seconds() / 3600

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["time"] = self.time.isoformat()
        return d


# ── Rule-based generators ──────────────────────────────────────────────────

def _get_first_friday(year: int, month: int) -> datetime:
    """Jumat pertama bulan tersebut (NFP)."""
    d = datetime(year, month, 1, 13, 30, tzinfo=timezone.utc)
    days_until_friday = (4 - d.weekday()) % 7
    return d + timedelta(days=days_until_friday)


def _get_second_wednesday(year: int, month: int) -> datetime:
    """Rabu ke-2 bulan tersebut (CPI)."""
    d = datetime(year, month, 1, 13, 30, tzinfo=timezone.utc)
    days_until_wednesday = (2 - d.weekday()) % 7
    first_wednesday = d + timedelta(days=days_until_wednesday)
    return first_wednesday + timedelta(weeks=1)


def _get_thursdays_in_range(start: datetime, end: datetime) -> List[datetime]:
    """Semua Kamis 13:30 UTC antara start dan end (Jobless Claims)."""
    thursdays = []
    current = start
    # Cari Kamis pertama >= start
    days_until_thursday = (3 - current.weekday()) % 7
    if days_until_thursday == 0 and current.hour >= 13:
        days_until_thursday = 7
    current = current + timedelta(days=days_until_thursday)
    current = current.replace(hour=13, minute=30, second=0, microsecond=0, tzinfo=timezone.utc)

    while current <= end:
        thursdays.append(current)
        current += timedelta(days=7)
    return thursdays


def _build_monthly_events(year: int, month: int) -> List[EconomicEvent]:
    """NFP, CPI, GDP untuk satu bulan."""
    events = []

    nfp_dt = _get_first_friday(year, month)
    events.append(
        EconomicEvent(
            name="Non-Farm Payrolls (NFP)",
            time=nfp_dt,
            impact="high",
            avoid_trading=True,
            description="US monthly employment report - major market mover",
            category="nfp",
        )
    )

    cpi_dt = _get_second_wednesday(year, month)
    events.append(
        EconomicEvent(
            name="CPI Inflation Data",
            time=cpi_dt,
            impact="high",
            avoid_trading=False,
            description="US Consumer Price Index - key inflation indicator",
            category="cpi",
        )
    )

    # GDP Advance Estimate (akhir bulan di quarter start: Jan, Apr, Jul, Oct)
    if month in [1, 4, 7, 10]:
        gdp_dt = datetime(year, month, 30, 13, 30, tzinfo=timezone.utc)
        events.append(
            EconomicEvent(
                name="GDP Advance Estimate",
                time=gdp_dt,
                impact="high",
                avoid_trading=False,
                description="US GDP growth rate - quarterly economic health",
                category="gdp",
            )
        )

    return events


def _build_fomc_events() -> List[EconomicEvent]:
    """Semua FOMC events dari schedule."""
    return [
        EconomicEvent(
            name="FOMC Rate Decision",
            time=dt,
            impact="high",
            avoid_trading=True,
            description="Federal Reserve interest rate decision + press conference",
            category="fomc",
        )
        for dt in FOMC_SCHEDULE_UTC
    ]


def _build_jobless_events(start: datetime, end: datetime) -> List[EconomicEvent]:
    """Initial Jobless Claims (Kamis)."""
    thursdays = _get_thursdays_in_range(start, end)
    return [
        EconomicEvent(
            name="Initial Jobless Claims",
            time=t,
            impact="medium",
            avoid_trading=False,
            description="Weekly US unemployment insurance claims",
            category="jobless",
        )
        for t in thursdays
    ]


# ── Public API ─────────────────────────────────────────────────────────────

def _all_events_in_range(start: datetime, end: datetime) -> List[EconomicEvent]:
    """
    Bangun semua event antara start dan end.
    Cover 1 tahun buffer supaya window query tidak miss event di edge.
    """
    events: List[EconomicEvent] = []

    # FOMC (semua years, di-filter by range di caller)
    events.extend(_build_fomc_events())

    # NFP/CPI/GDP untuk ±1 tahun
    start_year = start.year - 1
    end_year = end.year + 1
    for y in range(start_year, end_year + 1):
        for m in range(1, 13):
            events.extend(_build_monthly_events(y, m))

    # Jobless Claims (Kamis) untuk range
    events.extend(_build_jobless_events(start, end))

    return events


def get_events_for_timestamp(
    ts: datetime,
    window_hours: int = 72,
    impact_filter: Optional[str] = None,
) -> List[EconomicEvent]:
    """
    Ambil event ekonomi dalam window_hours SEBELUM dan SESUDAH ts.

    Time-anchored: tidak baca "now". Aman untuk replay.

    Args:
        ts: Anchor timestamp (UTC recommended)
        window_hours: Window look-back + look-forward dalam jam
        impact_filter: "high" | "medium" | "low" | None (all)

    Returns:
        List of EconomicEvent, sorted by time
    """
    # Normalize ke UTC
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    win_start = ts - timedelta(hours=window_hours)
    win_end = ts + timedelta(hours=window_hours)

    # Build events untuk range
    all_events = _all_events_in_range(win_start, win_end)

    # Filter by time window
    in_window = [e for e in all_events if win_start <= e.time <= win_end]

    # Filter by impact
    if impact_filter:
        in_window = [e for e in in_window if e.impact == impact_filter]

    in_window.sort(key=lambda e: e.time)
    return in_window


def get_next_high_impact(
    ts: datetime,
    max_hours_ahead: int = 72,
) -> Optional[EconomicEvent]:
    """
    Event high-impact berikutnya setelah ts.

    Untuk LLM context: "FOMC dalam 6 jam" → avoid_trading=True → wide SL atau skip
    """
    upcoming = get_events_for_timestamp(
        ts, window_hours=max_hours_ahead, impact_filter="high"
    )
    future = [e for e in upcoming if e.time > ts]
    return future[0] if future else None


def should_avoid_trading(
    ts: datetime,
    pre_hours: int = 2,
    post_hours: int = 1,
) -> tuple:
    """
    Cek apakah pada ts ada event high-impact yang harus dihindari.

    Returns:
        (avoid: bool, reason: str, event: Optional[EconomicEvent])
    """
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    events = get_events_for_timestamp(
        ts, window_hours=max(pre_hours, post_hours), impact_filter="high"
    )
    for e in events:
        hours_until = e.hours_until(ts)
        if -post_hours <= hours_until <= pre_hours and e.avoid_trading:
            reason = (
                f"{e.name} dalam {hours_until:+.1f}h "
                f"(pre={pre_hours}h, post={post_hours}h)"
            )
            return True, reason, e
    return False, "no_avoid_event", None


# ── CLI smoke test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Smoke test: query events around FOMC, NFP, CPI di 2023.
    """
    # Test 1: 24 jam sebelum FOMC Maret 2023 (saat SVB crisis)
    ts_fomc = datetime(2023, 3, 22, 12, 0, tzinfo=timezone.utc)
    events = get_events_for_timestamp(ts_fomc, window_hours=24, impact_filter="high")
    print(f"=== Events around FOMC 2023-03-22 12:00 UTC (24h window) ===")
    for e in events:
        print(f"  {e.time.strftime('%Y-%m-%d %H:%M')} | {e.name} | "
              f"hours_until={e.hours_until(ts_fomc):+.1f} | avoid={e.avoid_trading}")

    # Test 2: Next high impact
    next_ev = get_next_high_impact(ts_fomc, max_hours_ahead=72)
    print(f"\n=== Next high-impact from FOMC time ===")
    if next_ev:
        print(f"  {next_ev.name} @ {next_ev.time} ({next_ev.hours_until(ts_fomc):.1f}h)")

    # Test 3: Should avoid trading?
    avoid, reason, ev = should_avoid_trading(ts_fomc, pre_hours=2, post_hours=1)
    print(f"\n=== Should avoid trading @ FOMC time ===")
    print(f"  avoid={avoid}, reason={reason}")
    if ev:
        print(f"  event={ev.name} @ {ev.time}")

    # Test 4: Random mid-quarter (no event nearby)
    ts_quiet = datetime(2023, 4, 15, 12, 0, tzinfo=timezone.utc)
    events_quiet = get_events_for_timestamp(ts_quiet, window_hours=48, impact_filter="high")
    print(f"\n=== Events 2023-04-15 quiet day (48h window) ===")
    print(f"  {len(events_quiet)} high-impact events found")
    for e in events_quiet[:5]:
        print(f"  {e.time.strftime('%Y-%m-%d %H:%M')} | {e.name}")
