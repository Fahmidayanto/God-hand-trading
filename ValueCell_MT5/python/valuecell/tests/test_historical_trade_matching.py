from datetime import datetime

import pandas as pd

from valuecell.knowledge.historical_trade_matching import (
    build_structure_trade_matches,
    normalize_entry_event,
    normalize_structure_direction,
    normalize_structure_event,
)


def test_normalize_entry_event_accepts_only_known_structure_prefixes():
    assert normalize_entry_event("BoS_2") == "BoS"
    assert normalize_entry_event("CHoCH") == "CHoCH"
    assert normalize_entry_event("REJECTED") is None
    assert normalize_entry_event(None) is None
    assert normalize_structure_event("Bullish CHoCH") == "CHoCH"
    assert normalize_structure_event("LL Update") == "LL"
    assert normalize_structure_direction("LL Update", "Update") == "Bearish"


def test_trade_first_matching_is_one_to_one_with_exact_event_then_fallback():
    structures = pd.DataFrame([
        {
            "event_key": "older-choch",
            "event_time": datetime(2026, 8, 28, 12, 45),
            "event_type": "CHoCH",
            "direction": "Bullish",
            "timeframe": "M15",
        },
        {
            "event_key": "newer-bos",
            "event_time": datetime(2026, 8, 28, 13, 0),
            "event_type": "BoS",
            "direction": "Bullish",
            "timeframe": "M15",
        },
        {
            "event_key": "latest-choch",
            "event_time": datetime(2026, 8, 28, 13, 15),
            "event_type": "CHoCH",
            "direction": "Bullish",
            "timeframe": "M15",
        },
        {
            "event_key": "latest-choch",
            "event_time": datetime(2026, 8, 28, 13, 15),
            "event_type": "CHoCH",
            "direction": "Bullish",
            "timeframe": "M15",
        },
    ])
    trades = pd.DataFrame([
        {
            "trade_key": "exact",
            "entry_time": datetime(2026, 8, 28, 13, 30),
            "type": "BUY",
            "timeframe": "M15",
            "entry_structure": "CHoCH",
        },
        {
            "trade_key": "fallback",
            "entry_time": datetime(2026, 8, 28, 13, 35),
            "type": "BUY",
            "timeframe": "M15",
            "entry_structure": "REJECTED",
        },
    ])

    matches, stats = build_structure_trade_matches(structures, trades)

    assert matches["latest-choch"]["trade_key"] == "exact"
    assert matches["newer-bos"]["trade_key"] == "fallback"
    assert len(matches) == 2
    assert stats == {
        "structures": 3,
        "trades": 2,
        "matched": 2,
        "unmatched": 0,
        "exact_event": 1,
        "fallback": 1,
    }


def test_trade_first_matching_accepts_an_empty_trade_frame():
    structures = pd.DataFrame([{
        "event_key": "structure",
        "event_time": datetime(2026, 8, 28, 13, 0),
        "event_type": "BoS",
        "direction": "Bullish",
        "timeframe": "M15",
    }])

    matches, stats = build_structure_trade_matches(structures, pd.DataFrame())

    assert matches == {}
    assert stats["structures"] == 1
    assert stats["trades"] == 0
    assert stats["matched"] == 0