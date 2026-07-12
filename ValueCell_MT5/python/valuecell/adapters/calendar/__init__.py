"""Economic calendar adapter - FOMC/NFP/CPI/GDP schedule for XAUUSD."""
from .economic_calendar import (
    get_upcoming_events,
    get_upcoming_events_naive,
    get_next_major_event,
)

__all__ = ["get_upcoming_events", "get_upcoming_events_naive", "get_next_major_event"]