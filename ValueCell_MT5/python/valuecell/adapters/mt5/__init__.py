"""
MT5 Adapter Module

This module provides MetaTrader 5 integration for real-time trading.
Part of Track 1 (Real-time Trading) in the Hybrid Approach.
"""

from .mt5_adapter import MT5Adapter
from .market_structure_detector import (
    MarketStructureDetector,
    StructureEvent,
    StructureType,
    StructureStatus
)

__all__ = [
    "MT5Adapter",
    "MarketStructureDetector",
    "StructureEvent",
    "StructureType",
    "StructureStatus"
]
