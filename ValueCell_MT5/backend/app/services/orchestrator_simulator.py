import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

import pandas as pd

# Make the `valuecell` package importable from the backend process.
_PYTHON_DIR = str(Path(__file__).resolve().parents[3] / "python")
if _PYTHON_DIR not in sys.path:
    sys.path.insert(0, _PYTHON_DIR)

from loguru import logger


def _to_dt(ts: int) -> datetime:
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def reconstruct_market_data(
    candles: List[Dict[str, Any]],
    event_time: int,
    structure_events: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build the market_data dict the orchestrator expects, as of event_time.

    Mirrors trading_system.TradingSystem._fetch_market_data but from history.
    """
    df = pd.DataFrame(candles)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    if "tick_volume" not in df.columns and "volume" in df.columns:
        df["tick_volume"] = df["volume"]
    df = df[df["time"] <= _to_dt(event_time)].copy()
    if df.empty:
        raise ValueError("No candles up to event_time")
    if "ema200" not in df.columns or df["ema200"].isna().all():
        df["ema200"] = df["close"].ewm(span=200, adjust=False).mean()
    df["high_low"] = df["high"] - df["low"]
    atr = float(df["high_low"].tail(14).mean())
    current = df.iloc[-1]
    current_bar = {
        "time": current["time"],
        "open": float(current["open"]),
        "high": float(current["high"]),
        "low": float(current["low"]),
        "close": float(current["close"]),
        "volume": int(current["tick_volume"]) if "tick_volume" in df.columns else int(current["volume"]),
    }
    hour = current["time"].hour
    if 7 <= hour < 16:
        session = "London"
    elif 13 <= hour < 22:
        session = "NewYork"
    elif 0 <= hour < 9:
        session = "Asia"
    else:
        session = "Sydney"
    events_up_to = [e for e in structure_events if e.get("time", 0) <= event_time]
    return {
        "df": df,
        "current_bar": current_bar,
        "structure_events": events_up_to,
        "m15_history": df,
        "atr": atr,
        "session": session,
        "news_headlines": [],
        "upcoming_events": [],
    }


def forward_walk_outcome(
    candles: List[Dict[str, Any]],
    signal_time: int,
    signal: str,
    sl: Optional[float],
    tp: Optional[float],
    max_bars: int = 200,
) -> Dict[str, Any]:
    """Walk forward from signal_time to decide if TP or SL hits first."""
    if signal not in ("BUY", "SELL"):
        return {"outcome": "NONE", "outcome_bar": None}


def compute_metrics(
    signals: List[Dict[str, Any]],
    backtest_trades: List[Dict[str, Any]],
) -> Dict[str, Any]:
    from collections import Counter

    total = len(signals)
    buy = sum(1 for s in signals if s["signal"] == "BUY")
    sell = sum(1 for s in signals if s["signal"] == "SELL")
    wins = sum(1 for s in signals if s["outcome"] == "TP")
    losses = sum(1 for s in signals if s["outcome"] == "SL")
    decided = wins + losses
    win_rate = (wins / decided) if decided else 0.0
    avg_conf = (sum(s["confidence"] for s in signals) / total) if total else 0.0
    bt_sorted = sorted(
        [t for t in backtest_trades if t.get("entry_time") is not None],
        key=lambda t: t["entry_time"],
    )
    matched = 0
    for s in signals:
        for t in bt_sorted:
            if abs(t["entry_time"] - s["time"]) <= 4 * 3600:
                bt_dir = "BUY" if str(t.get("type", "")).upper() == "BUY" else "SELL"
                if bt_dir == s["signal"]:
                    matched += 1
                break
    agreement_rate = (matched / total) if total else 0.0
    avg_consensus = Counter(s.get("consensus", "") for s in signals).most_common(1)[0][0] if total else ""
    return {
        "total_signals": total,
        "buy": buy,
        "sell": sell,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "avg_confidence": avg_conf,
        "avg_consensus": avg_consensus,
        "matched_backtest_trades": matched,
        "agreement_rate": agreement_rate,
    }
    future = [c for c in candles if c["time"] > signal_time]
    for c in future[:max_bars]:
        high = float(c["high"])
        low = float(c["low"])
        if signal == "BUY":
            if sl is not None and low <= sl:
                return {"outcome": "SL", "outcome_bar": c["time"]}
            if tp is not None and high >= tp:
                return {"outcome": "TP", "outcome_bar": c["time"]}
        else:
            if sl is not None and high >= sl:
                return {"outcome": "SL", "outcome_bar": c["time"]}
            if tp is not None and low <= tp:
                return {"outcome": "TP", "outcome_bar": c["time"]}
    return {"outcome": "NONE", "outcome_bar": None}
