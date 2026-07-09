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


# Orchestrator fires only on these structure-event types (confirmed design).
TRIGGER_TYPES = {"CHOCH", "HH", "LL", "BOS"}


def _to_dt(ts: int) -> datetime:
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def reconstruct_market_data(
    df: pd.DataFrame,
    event_time: int,
    structure_events: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build the market_data dict the orchestrator expects, as of event_time.

    Mirrors trading_system.TradingSystem._fetch_market_data but from history.
    `df` is the prebuilt base DataFrame (datetime index, sorted) produced once
    by `run_simulation`; this function only slices/filters it for `event_time`.
    """
    df = df[df["time"] <= _to_dt(event_time)].copy()
    if df.empty:
        raise ValueError("No candles up to event_time")
    if "tick_volume" not in df.columns and "volume" in df.columns:
        df["tick_volume"] = df["volume"]
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
    # Non-overlapping session partition. Overlaps resolved by preferring the
    # market that is open: London over Asia (7-9), NewYork over London (13-16).
    hour = current["time"].hour
    if 13 <= hour < 22:
        session = "NewYork"
    elif 7 <= hour < 16:
        session = "London"
    elif 0 <= hour < 7:
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


def _build_frame(ev: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize each agent's status for one structure event, for the UI panel."""
    is_error = bool(result.get("error"))

    def view(key: str) -> Dict[str, Any]:
        r = (result.get("agent_results") or {}).get(key)
        if is_error:
            return {"status": "error", "signal": None, "confidence": 0.0,
                    "approved": None, "filtered": None, "adjustment": None}
        if r is None:
            return {"status": "skipped", "signal": None, "confidence": 0.0,
                    "approved": None, "filtered": None, "adjustment": None}
        return {
            "status": "fired",
            "signal": r.get("signal") or r.get("final_signal"),
            "confidence": r.get("confidence", 0.0),
            "approved": r.get("approved"),
            "filtered": r.get("filtered"),
            "adjustment": r.get("confidence_adjustment"),
        }

    return {
        "event_time": ev.get("time"),
        "event_type": ev.get("type"),
        "event_direction": ev.get("direction"),
        "agents": {
            "market_structure": view("market_structure"),
            "ml_prediction": view("ml_prediction"),
            "sentiment": view("sentiment"),
            "risk_management": view("risk_management"),
        },
        "final_signal": result.get("final_signal"),
        "approved": result.get("approved"),
        "consensus_level": result.get("consensus_level"),
        "consensus_confidence": result.get("final_confidence"),
    }


def get_orchestrator():
    """Build the SEPARATE simulation orchestrator instance.

    Same OrchestratorAgent code as live, but its own instance + config.
    Sentiment disabled by default (may require an LLM); enable once the
    backend environment provides it.
    """
    from valuecell.agents.orchestrator_agent import OrchestratorAgent
    return OrchestratorAgent(
        enable_market_structure=True,
        enable_ml_prediction=True,
        enable_risk_management=True,
        enable_sentiment=True,
        consensus_threshold=0.60,
    )


def run_simulation(
    candles: List[Dict[str, Any]],
    structure_events: List[Dict[str, Any]],
    backtest_trades: List[Dict[str, Any]],
    symbol: str = "XAUUSD",
    timeframe: str = "M15",
    max_events: int = 300,
) -> Dict[str, Any]:
    orch = get_orchestrator()

    # Cap the number of structure events processed so the simulation always
    # returns in bounded time even for very wide date ranges. Processing
    # every event would run the (ML-heavy) orchestrator once per event and
    # can take minutes, which makes the caller hang.
    if max_events > 0 and len(structure_events) > max_events:
        logger.warning(
            f"sim: {len(structure_events)} structure events exceed cap {max_events}; "
            f"processing the first {max_events} only"
        )
        structure_events = structure_events[:max_events]

    # Keep only structure-event types the orchestrator should react to.
    structure_events = [e for e in structure_events if (e.get("type") or "").upper() in TRIGGER_TYPES]

    # Build the base DataFrame ONCE (datetime index, sorted) instead of
    # reconstructing the full frame on every structure event.
    base_df = pd.DataFrame(candles)
    base_df["time"] = pd.to_datetime(base_df["time"], unit="s", utc=True)
    if "tick_volume" not in base_df.columns and "volume" in base_df.columns:
        base_df["tick_volume"] = base_df["volume"]
    if "ema200" not in base_df.columns or base_df["ema200"].isna().all():
        base_df["ema200"] = base_df["close"].ewm(span=200, adjust=False).mean()
    base_df["high_low"] = base_df["high"] - base_df["low"]
    base_df = base_df.sort_values("time").reset_index(drop=True)

    signals: List[Dict[str, Any]] = []
    frames: List[Dict[str, Any]] = []
    for ev in structure_events:
        ev_time = ev.get("time")
        if ev_time is None:
            continue
        try:
            md = reconstruct_market_data(base_df, ev_time, structure_events)
        except Exception as e:
            logger.warning(f"sim: skip event {ev_time}: {e}")
            continue
        try:
            result = orch.analyze(market_data=md, symbol=symbol, timeframe=timeframe)
        except Exception as e:
            logger.warning(f"sim: orchestrator failed at {ev_time}: {e}")
            continue
        frames.append(_build_frame(ev, result))
        if not result.get("approved") or result.get("final_signal") not in ("BUY", "SELL"):
            continue
        sig = result["final_signal"]
        sl = (result.get("sl_tp") or {}).get("sl_price")
        tp = (result.get("sl_tp") or {}).get("tp_price")
        outcome = forward_walk_outcome(candles, ev_time, sig, sl, tp)
        signals.append({
            "time": ev_time,
            "signal": sig,
            "confidence": float(result.get("final_confidence", 0.0)),
            "consensus": result.get("consensus_level", ""),
            "sl": sl,
            "tp": tp,
            "lot": (result.get("position_sizing") or {}).get("lot_size"),
            "outcome": outcome["outcome"],
            "outcome_bar": outcome["outcome_bar"],
        })
    metrics = compute_metrics(signals, backtest_trades)
    return {"signals": signals, "metrics": metrics, "frames": frames}


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
                bt_type = str(t.get("type", "")).upper()
                # Only count agreement for explicitly valid backtest directions;
                # malformed/None types are skipped (neither BUY nor SELL).
                if bt_type == s["signal"]:
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
