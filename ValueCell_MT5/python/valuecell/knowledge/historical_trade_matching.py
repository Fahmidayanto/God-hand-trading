"""One-to-one matching between historical structures and trade outcomes."""

from datetime import timedelta
from typing import Any, Optional

import pandas as pd


VALID_EVENT_TYPES = ("CHoCH", "BoS", "HH", "LL")


def normalize_structure_event(value: Any) -> str:
    """Normalize a structure row type to the LanceDB event contract."""
    raw_value = str(value or "").lower()
    if "choch" in raw_value:
        return "CHoCH"
    if "hh" in raw_value:
        return "HH"
    if "ll" in raw_value:
        return "LL"
    return "BoS"


def normalize_structure_direction(raw_type: Any, raw_direction: Any) -> str:
    """Normalize structure direction using the same rules as historical producers."""
    type_value = str(raw_type or "").lower()
    direction_value = str(raw_direction or "").lower()
    if "bearish" in direction_value or "bearish" in type_value:
        return "Bearish"
    if "update" in direction_value and ("ll" in type_value or "bearish" in type_value):
        return "Bearish"
    return "Bullish"


def normalize_entry_event(value: Any) -> Optional[str]:
    """Return a canonical event type only when the trade metadata provides one."""
    raw_value = str(value or "").strip()
    for event_type in VALID_EVENT_TYPES:
        if raw_value.lower().startswith(event_type.lower()):
            return event_type
    return None


def build_structure_trade_matches(
    structures: pd.DataFrame,
    trades: pd.DataFrame,
) -> tuple[dict[Any, dict[str, Any]], dict[str, int]]:
    """Assign each trade to at most one unique structure in its prior one-hour window."""
    unique_structures = structures.drop_duplicates("event_key", keep="first").copy()
    unique_structures["event_time"] = pd.to_datetime(unique_structures["event_time"])
    unique_structures["_assigned"] = False

    ordered_trades = trades.copy()
    if ordered_trades.empty:
        return {}, {
            "structures": len(unique_structures),
            "trades": 0,
            "matched": 0,
            "unmatched": 0,
            "exact_event": 0,
            "fallback": 0,
        }
    ordered_trades["entry_time"] = pd.to_datetime(ordered_trades["entry_time"])
    ordered_trades = ordered_trades.sort_values("entry_time")

    matches: dict[Any, dict[str, Any]] = {}
    exact_event = 0
    fallback = 0

    for _, trade in ordered_trades.iterrows():
        entry_time = trade["entry_time"]
        if pd.isna(entry_time):
            continue

        direction = "Bullish" if str(trade.get("type", "")).upper() == "BUY" else "Bearish"
        timeframe = str(trade.get("timeframe", "")).strip()
        event_type = normalize_entry_event(trade.get("entry_structure"))
        candidates = unique_structures[
            (~unique_structures["_assigned"])
            & (unique_structures["direction"] == direction)
            & (unique_structures["timeframe"] == timeframe)
            & (unique_structures["event_time"] <= entry_time)
            & (unique_structures["event_time"] >= entry_time - timedelta(hours=1))
        ]

        exact_candidates = candidates[candidates["event_type"] == event_type] if event_type else candidates.iloc[0:0]
        if not exact_candidates.empty:
            candidates = exact_candidates
            exact_event += 1
        elif not candidates.empty:
            fallback += 1
        else:
            continue

        selected_index = candidates["event_time"].idxmax()
        event_key = unique_structures.at[selected_index, "event_key"]
        unique_structures.at[selected_index, "_assigned"] = True
        matches[event_key] = trade.to_dict()

    matched = len(matches)
    stats = {
        "structures": len(unique_structures),
        "trades": len(ordered_trades),
        "matched": matched,
        "unmatched": len(ordered_trades) - matched,
        "exact_event": exact_event,
        "fallback": fallback,
    }
    return matches, stats