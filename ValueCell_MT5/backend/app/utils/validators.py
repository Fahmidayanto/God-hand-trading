"""Data validators."""

from datetime import datetime
from typing import Optional


def validate_symbol(symbol: str) -> bool:
    """Validate trading symbol format."""
    if not symbol or len(symbol) < 3:
        return False
    return symbol.isalnum()


def validate_lot_size(lot_size: float, min_lot: float = 0.01, max_lot: float = 10.0) -> bool:
    """Validate lot size."""
    return min_lot <= lot_size <= max_lot


def validate_timeframe(timeframe: str) -> bool:
    """Validate timeframe string."""
    valid_timeframes = ["M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1", "MN1"]
    return timeframe in valid_timeframes


def validate_date_range(
    start_date: Optional[datetime],
    end_date: Optional[datetime],
    max_days: int = 365,
) -> bool:
    """Validate date range."""
    if not start_date or not end_date:
        return True
    
    if end_date < start_date:
        return False
    
    delta = (end_date - start_date).days
    return delta <= max_days


def validate_price(price: float) -> bool:
    """Validate price value."""
    return price > 0
