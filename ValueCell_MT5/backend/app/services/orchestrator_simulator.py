import sys
import time as _time
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


def _generate_historical_sentiment_data(event_time_dt: datetime) -> Dict[str, Any]:
    """Uses LLM (Gemini/OpenAI) to generate realistic historical news headlines and calendar events."""
    import os
    import json
    from datetime import timedelta
    from dotenv import load_dotenv
    
    date_str = event_time_dt.strftime("%Y-%m-%d")
    time_str = event_time_dt.strftime("%H%M%S")
    
    # Check cache first to avoid slow LLM API calls on replay
    cache_dir = Path(__file__).resolve().parent.parent.parent / "data" / "news_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"news_{date_str}_{time_str}.json"
    
    if cache_file.exists():
        try:
            with open(cache_file, "r") as f:
                cached_data = json.load(f)
            logger.info(f"💾 Loaded sentiment/news data from cache for {date_str} {event_time_dt.strftime('%H:%M:%S')}")
            return cached_data
        except Exception as e:
            logger.warning(f"Failed to read news cache: {e}")

    # Explicitly load the backend .env file
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=str(env_path))
    try:
        from agno.agent import Agent
        from agno.models.openai import OpenAILike
        from agno.models.google import Gemini
    except Exception as ie:
        logger.error(f"Failed to import agno components: {ie}")
        return {"news_headlines": [], "upcoming_events": []}

    news = []
    events = []

    date_str = event_time_dt.strftime("%Y-%m-%d")
    prompt = f"""
    Provide a historical or realistic reconstruction of market news and economic calendar events for Gold (XAUUSD) and USD on {date_str}.
    Return a JSON object containing:
    1. "news_headlines": A list of 3 news headline objects. Each object must have:
       - "headline": A news headline string (e.g., "Gold spikes on inflation worries", "US Dollar rallies following retail sales"). Include relevant keywords like inflation, hawkish, dovish, recession, yield, safe haven.
       - "timestamp": A timestamp string in "YYYY-MM-DD HH:MM:SS" format (set this between 1 and 4 hours BEFORE the time {event_time_dt.strftime('%H:%M:%S')}).
    2. "upcoming_events": A list of 1-2 upcoming economic calendar event objects. Each object must have:
       - "event": The event name (e.g., "CPI", "FOMC", "NFP", "GDP", "Unemployment Rate").
       - "impact": "high" or "medium".
       - "time": A timestamp string in "YYYY-MM-DD HH:MM:SS" format (set this between 30 minutes and 6 hours AFTER the time {event_time_dt.strftime('%H:%M:%S')}).

    Return ONLY the raw JSON object. Do not include markdown code block syntax (like ```json).
    """

    content = None

    # 1. Try NVIDIA Qwen 397B
    try:
        logger.info("Initializing NVIDIA Qwen 397B for sentiment/news generation...")
        model_397b = OpenAILike(
            id="qwen/qwen3.5-397b-a17b",
            api_key="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",
            base_url="https://integrate.api.nvidia.com/v1",
            temperature=0.6,
            top_p=0.95,
            max_tokens=1024,
        )
        agent_397b = Agent(
            model=model_397b,
            description="You are a historical financial market news and economic calendar archiver for Gold (XAUUSD).",
        )
        response = agent_397b.run(prompt)
        if not response or not response.content:
            raise ValueError("Empty response content from NVIDIA Qwen 397B")
        content = response.content.strip()
        logger.info("✅ Successfully generated sentiment data via NVIDIA Qwen 397B")
    except Exception as qwen397_err:
        logger.warning(f"NVIDIA Qwen 397B generation failed, trying Qwen 122B: {qwen397_err}")

        # 3. Try NVIDIA Qwen-122B (DeepSeek V4 Pro bypassed)
        try:
            logger.info("Initializing NVIDIA Qwen 122B for sentiment/news generation...")
            model_122b = OpenAILike(
                id="qwen/qwen3.5-122b-a10b",
                api_key="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",
                base_url="https://integrate.api.nvidia.com/v1",
                temperature=0.6,
                top_p=0.95,
                max_tokens=1024,
            )
            agent_122b = Agent(
                model=model_122b,
                description="You are a historical financial market news and economic calendar archiver for Gold (XAUUSD).",
            )
            response = agent_122b.run(prompt)
            if not response or not response.content:
                raise ValueError("Empty response content from NVIDIA Qwen 122B")
            content = response.content.strip()
            logger.info("✅ Successfully generated sentiment data via NVIDIA Qwen 122B")
        except Exception as qwen122_err:
            logger.warning(f"NVIDIA Qwen 122B generation failed, falling back to Gemini: {qwen122_err}")
            
            # 4. Fallback to Gemini
            try:
                google_api_key = os.getenv("GOOGLE_API_KEY")
                if not google_api_key:
                    logger.error("GOOGLE_API_KEY not found in environment for fallback.")
                    return {"news_headlines": [], "upcoming_events": []}
                    
                model_gemini = Gemini(
                    id="gemini-2.5-flash",
                    api_key=google_api_key,
                    max_tokens=1024,
                )
                agent_gemini = Agent(
                    model=model_gemini,
                    description="You are a historical financial market news and economic calendar archiver for Gold (XAUUSD).",
                )
                response = agent_gemini.run(prompt)
                if not response or not response.content:
                    raise ValueError("Empty response content from Gemini Fallback")
                content = response.content.strip()
                logger.info("✅ Successfully generated sentiment data via Gemini Fallback")
            except Exception as gemini_err:
                logger.error(f"Gemini fallback also failed: {gemini_err}")
                return {"news_headlines": [], "upcoming_events": []}

    if not content:
        return {"news_headlines": [], "upcoming_events": []}

    # Clean markdown code block or extract JSON object robustly via regex
    cleaned_content = content.strip()
    import re
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned_content)
    if match:
        cleaned_content = match.group(1).strip()
    else:
        brace_match = re.search(r"(\{[\s\S]*\})", cleaned_content)
        if brace_match:
            cleaned_content = brace_match.group(1).strip()

    try:
        data = json.loads(cleaned_content)
        
        # Parse headlines
        for item in data.get("news_headlines", []):
            hl = item.get("headline", "")
            ts_str = item.get("timestamp")
            try:
                ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            except:
                ts = event_time_dt - timedelta(hours=2)
            news.append({
                "headline": hl,
                "timestamp": ts.isoformat()
            })

        # Parse upcoming events
        for item in data.get("upcoming_events", []):
            evt = item.get("event", "")
            impact = item.get("impact", "high")
            ts_str = item.get("time")
            try:
                ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            except:
                ts = event_time_dt + timedelta(hours=3)
            events.append({
                "event": evt,
                "impact": impact,
                "time": ts.isoformat()
            })

        logger.info(f"✅ Generated {len(news)} headlines and {len(events)} economic events for {date_str} via LLM")

    except Exception as e:
        logger.error(f"Error generating historical sentiment data via LLM: {e}")
        logger.error(f"Raw LLM content was: {content}")

    result = {
        "news_headlines": news,
        "upcoming_events": events,
    }

    # Save to local cache
    try:
        with open(cache_file, "w") as f:
            json.dump(result, f, indent=4)
        logger.info(f"💾 Saved generated sentiment/news data to cache: {cache_file.name}")
    except Exception as e:
        logger.warning(f"Failed to write news cache: {e}")

    return result


def reconstruct_market_data(
    df: pd.DataFrame,
    event_time: int,
    structure_events: List[Dict[str, Any]],
    generate_news: bool = False,
    event_type_hint: Optional[str] = None,
) -> Dict[str, Any]:
    logger.info(f"--- reconstruct_market_data called: generate_news={generate_news} ---")
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

    news_headlines = []
    upcoming_events = []
    if generate_news:
        # Use the API-provided event type hint (reliable) or fall back to DB lookup
        # DB lookup can fail when multiple events share the same timestamp
        if event_type_hint:
            target_ev_type = event_type_hint.upper()
        else:
            current_events = [e for e in structure_events if e.get("time", 0) == event_time]
            target_ev_type = current_events[0].get("type", "").upper() if current_events else ""

        # Determine if the setup is active by looking at the most recent baseline event (CHOCH or BOS) in the history
        # before the current event
        recent_baseline = None
        recent_choch_dir = None
        for ev in reversed(events_up_to):
            if ev.get("time", 0) == event_time:
                continue
            ev_type = ev.get("type", "").upper()
            if ev_type in ("CHOCH", "BOS"):
                recent_baseline = ev_type
                if ev_type == "CHOCH":
                    recent_choch_dir = ev.get("direction", "").upper()
                break

        # LLM only searches for news when:
        # 1. Target event is BOS (triggers a trade)
        # 2. Target event is HH or LL, and the most recent baseline is CHOCH (meaning setup cycle is active)
        #    BUT NOT if it's a counter-swing (LL after Bullish CHoCH, HH after Bearish CHoCH)
        is_setup_active = recent_baseline == "CHOCH"

        # Detect counter-swing: skip LLM for the pullback leg
        # Bullish setup: CHoCH Bull + HH (setup swing) -> LL is counter-swing -> IDLE
        # Bearish setup: CHoCH Bear + LL (setup swing) -> HH is counter-swing -> IDLE
        # Post-BoS: any HH/LL after BoS is ignored until next CHoCH resets the cycle
        is_post_bos = recent_baseline == "BOS"
        is_counter_swing = is_post_bos or (is_setup_active and (
            (target_ev_type == "LL" and recent_choch_dir and ("BULL" in recent_choch_dir or "UP" in recent_choch_dir)) or
            (target_ev_type == "HH" and recent_choch_dir and "BEAR" in recent_choch_dir)
        ))

        should_run_llm = target_ev_type == "BOS" or (target_ev_type in ("HH", "LL") and is_setup_active and not is_counter_swing)

        if not should_run_llm:
            logger.info(f"💤 Simulator orchestrator is IDLE (event: {target_ev_type}) -> Skipping news LLM generation")
        else:
            # Rely on the local file cache inside _generate_historical_sentiment_data.
            # This avoids reusing news across different dates/events from the singleton orchestrator memory.
            sentiment_data = _generate_historical_sentiment_data(_to_dt(event_time))
            news_headlines = sentiment_data["news_headlines"]
            upcoming_events = sentiment_data["upcoming_events"]

    return {
        "df": df,
        "current_bar": current_bar,
        "structure_events": events_up_to,
        "m15_history": df,
        "atr": atr,
        "session": session,
        "news_headlines": news_headlines,
        "upcoming_events": upcoming_events,
        "is_counter_swing": is_counter_swing if generate_news else False,
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
                    "approved": None, "filtered": None, "adjustment": None,
                    "reasoning": None, "meta": None}
        if r is None:
            return {"status": "skipped", "signal": None, "confidence": 0.0,
                    "approved": None, "filtered": None, "adjustment": None,
                    "reasoning": None, "meta": None}
        meta = {}
        if key == "market_structure":
            win_rate = r.get("win_rate")
            if win_rate is None and isinstance(r.get("pre_signal"), dict):
                win_rate = r.get("pre_signal", {}).get("win_rate_historical")
            if win_rate is None and isinstance(r.get("pattern_analysis"), dict):
                win_rate = r.get("pattern_analysis", {}).get("win_rate")
            meta["win_rate"] = win_rate

            pattern_count = r.get("pattern_count")
            if pattern_count is None and isinstance(r.get("pre_signal"), dict):
                pattern_count = r.get("pre_signal", {}).get("pattern_count")
            if pattern_count is None and isinstance(r.get("pattern_analysis"), dict):
                pattern_count = r.get("pattern_analysis", {}).get("total_count")
            meta["pattern_count"] = pattern_count
            
            meta["tf_score"] = r.get("tf_score")

            patterns = None
            if isinstance(r.get("pattern_analysis"), dict):
                raw_patterns = r.get("pattern_analysis", {}).get("patterns") or []
                patterns = [
                    {
                        "timestamp": p.get("timestamp"),
                        "session": p.get("session"),
                        "outcome": p.get("outcome"),
                        "profit_pips": p.get("profit_pips"),
                        "similarity": p.get("similarity"),
                        "price": p.get("price"),
                        "direction": p.get("direction"),
                    }
                    for p in raw_patterns
                ]
            meta["patterns"] = patterns
        elif key == "ml_prediction":
            meta["probability"] = r.get("probability")
            meta["expected_rr"] = r.get("expected_rr")
        elif key == "sentiment":
            meta["sentiment_type"] = (r.get("sentiment") or {}).get("type") if isinstance(r.get("sentiment"), dict) else None
            meta["sentiment_score"] = (r.get("sentiment") or {}).get("score") if isinstance(r.get("sentiment"), dict) else None

        return {
            "status": "fired",
            "signal": r.get("signal") or r.get("final_signal"),
            "confidence": r.get("confidence") if r.get("confidence") is not None else r.get("final_confidence", 0.0),
            "approved": r.get("approved"),
            "filtered": r.get("filtered"),
            "adjustment": r.get("confidence_adjustment"),
            "reasoning": r.get("reasoning"),
            "meta": meta,
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
        # Trade execution context — frontend chart uses these to draw SL/TP
        # zones and entry line via TradesOverlayPrimitive. Without these the
        # primitive filters trades out (sl/tp == null → skip → no visual).
        "sl_tp": result.get("sl_tp"),
        "position_sizing": result.get("position_sizing"),
        "event_price": (result.get("sl_tp") or {}).get("entry_price") or ev.get("price"),
        # Counter-swing flag — tells frontend to freeze the Agent Consensus panel
        # and not update it (the warm-up values from setup swing are still valid)
        "is_counter_swing": result.get("is_counter_swing", False),
    }


_cached_orchestrator = None


def get_orchestrator():
    """Build the SEPARATE simulation orchestrator instance.

    Same OrchestratorAgent code as live, but its own instance + config.
    Sentiment is ENABLED so all four agents (Market Structure, ML Filter,
    Sentiment, Risk Manager) actually run during the simulation.

    Defensive: if building with sentiment enabled raises (e.g. a missing
    dependency or bad config in the backend environment), fall back to a
    sentiment-disabled instance so the whole simulation does not 500.
    """
    global _cached_orchestrator
    if _cached_orchestrator is not None:
        return _cached_orchestrator

    from valuecell.agents.orchestrator_agent import OrchestratorAgent

    base_kwargs = dict(
        enable_market_structure=True,
        enable_ml_prediction=True,
        enable_risk_management=True,
        consensus_threshold=0.60,
    )
    try:
        _cached_orchestrator = OrchestratorAgent(enable_sentiment=True, **base_kwargs)
    except Exception as e:
        logger.warning(
            f"sim: sentiment-enabled orchestrator failed to build ({e}); "
            f"falling back to sentiment-disabled instance"
        )
        _cached_orchestrator = OrchestratorAgent(enable_sentiment=False, **base_kwargs)
    return _cached_orchestrator


def run_simulation(
    candles: List[Dict[str, Any]],
    structure_events: List[Dict[str, Any]],
    backtest_trades: List[Dict[str, Any]],
    symbol: str = "XAUUSD",
    timeframe: str = "M15",
    max_events: int = 300,
) -> Dict[str, Any]:
    orch = get_orchestrator()

    # Keep only structure-event types the orchestrator should react to.
    structure_events = [e for e in structure_events if (e.get("type") or "").upper() in TRIGGER_TYPES]

    # Cap the number of structure events processed so the simulation always
    # returns in bounded time even for very wide date ranges. Processing
    # every event would run the (ML-heavy) orchestrator once per event and
    # can take minutes, which makes the caller hang. The cap applies to the
    # already-filtered trigger list (orchestrator runs only happen on trigger
    # events), so non-trigger events never count against it.
    if max_events > 0 and len(structure_events) > max_events:
        logger.warning(
            f"sim: {len(structure_events)} trigger events exceed cap {max_events}; "
            f"processing the first {max_events} only"
        )
        structure_events = structure_events[:max_events]

    # No (trigger) events to simulate -> nothing to run the orchestrator on.
    if not structure_events:
        logger.info("📅 SIM | No trigger events to process")
        metrics = compute_metrics([], backtest_trades)
        return {"signals": [], "metrics": metrics, "frames": []}

    # --- Log: simulation start ---
    _first_ts = structure_events[0].get("time", 0)
    _last_ts = structure_events[-1].get("time", 0)
    _date_from = _to_dt(_first_ts).strftime("%Y-%m-%d") if _first_ts else "?"
    _date_to = _to_dt(_last_ts).strftime("%Y-%m-%d") if _last_ts else "?"
    _has_sent = "sentiment" in (orch.agents if hasattr(orch, "agents") else {})
    logger.info(
        f"📅 SIM START | {_date_from} → {_date_to} | "
        f"{len(structure_events)} events | "
        f"Sentiment: {'ON' if _has_sent else 'OFF'} | News: OFF"
    )
    _sim_t0 = _time.monotonic()

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
    _total_ev = len(structure_events)
    for _ev_idx, ev in enumerate(structure_events, 1):
        ev_time = ev.get("time")
        if ev_time is None:
            continue
        try:
            md = reconstruct_market_data(base_df, ev_time, structure_events, generate_news=True, event_type_hint=ev.get("type"))
        except Exception as e:
            logger.warning(f"sim: skip event {ev_time}: {e}")
            continue
        try:
            result = orch.analyze(market_data=md, symbol=symbol, timeframe=timeframe)
        except Exception as e:
            logger.warning(f"sim: orchestrator failed at {ev_time}: {e}")
            err_result = {
                "error": str(e),
                "agent_results": {},
                "final_signal": "HOLD",
                "approved": False,
                "consensus_level": "no_consensus",
                "final_confidence": 0.0,
            }
            frames.append(_build_frame(ev, err_result))
            continue
        frames.append(_build_frame(ev, result))

        # --- Log: per-trigger summary ---
        _ar = result.get("agent_results") or {}
        _ms = _ar.get("market_structure", {})
        _ml = _ar.get("ml_prediction", {})
        _st = _ar.get("sentiment", {})
        _ev_dt = _to_dt(ev_time).strftime("%m-%d %H:%M")
        _ev_type = (ev.get("type") or "?").upper()
        _ev_dir = (ev.get("direction") or "?")[:4]
        _fsig = result.get("final_signal", "HOLD")
        _fconf = result.get("final_confidence", 0.0)
        _appr = "✅" if result.get("approved") else "⛔"
        logger.info(
            f"🎯 #{_ev_idx}/{_total_ev} | {_ev_dt} {_ev_type} {_ev_dir} | "
            f"MS:{_ms.get('signal', '-')}({_ms.get('confidence', 0):.2f}) "
            f"ML:{_ml.get('signal', '-')}({_ml.get('confidence', 0):.2f}) "
            f"SENT:{(_st.get('final_signal') or '-')[:4]}({_st.get('final_confidence', 0):.2f}) "
            f"→ {_fsig} {_fconf:.2f} {_appr}"
        )

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
    frames.sort(key=lambda f: f["event_time"])

    # --- Log: simulation complete ---
    _elapsed = _time.monotonic() - _sim_t0
    _tp = sum(1 for s in signals if s["outcome"] == "TP")
    _sl = sum(1 for s in signals if s["outcome"] == "SL")
    _none = sum(1 for s in signals if s["outcome"] == "NONE")
    logger.info(
        f"🏁 SIM DONE | {_total_ev} events → {len(signals)} signals | "
        f"{_tp}TP {_sl}SL {_none}NONE | {_elapsed:.1f}s"
    )

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
