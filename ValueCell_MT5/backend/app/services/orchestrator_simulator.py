import sys
import threading
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


def _detect_session(ts: int) -> str:
    """Return trading session name based on UTC hour of timestamp."""
    hour = datetime.fromtimestamp(ts, tz=timezone.utc).hour
    if 0 <= hour < 8:
        return "Tokyo"
    if 8 <= hour < 12:
        return "London"
    if 12 <= hour < 17:
        return "London_NY_Overlap"
    if 17 <= hour < 21:
        return "NewYork"
    return "Offmarket"


def _generate_historical_sentiment_data(event_time_dt: datetime) -> Dict[str, Any]:
    """Uses LLM (Gemini/OpenAI) to generate realistic historical news headlines and calendar events."""
    import os
    import json
    from datetime import timedelta
    from dotenv import load_dotenv
    
    date_str = event_time_dt.strftime("%Y-%m-%d")
    time_str = event_time_dt.strftime("%H%M%S")
    
    # Check LanceDB cache first to avoid slow LLM API calls on replay
    try:
        from valuecell.knowledge.lance_db import LanceDBManager
        db_mgr = LanceDBManager()
        cached_db_data = db_mgr.read_news_cache(event_time_dt.strftime("%Y-%m-%d %H:%M:%S"))
        if cached_db_data is not None:
            logger.info(f"💾 Loaded sentiment/news data from LanceDB cache for {date_str} {event_time_dt.strftime('%H:%M:%S')}")
            return cached_db_data
    except Exception as dbe:
        logger.warning(f"Failed to read from LanceDB cache: {dbe}")

    # Check local file cache as fallback
    cache_dir = Path(__file__).resolve().parent.parent.parent / "data" / "news_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"news_{date_str}_{time_str}.json"
    
    if cache_file.exists():
        try:
            with open(cache_file, "r") as f:
                cached_data = json.load(f)
            logger.info(f"💾 Loaded sentiment/news data from file cache for {date_str} {event_time_dt.strftime('%H:%M:%S')}")
            return cached_data
        except Exception as e:
            logger.warning(f"Failed to read news file cache: {e}")

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
Generate realistic XAUUSD/USD news + calendar events on {date_str} {event_time_dt.strftime('%H:%M:%S')}.
JSON output format:
{{
  "news_headlines": [
    {{
      "headline": "headline text (use keywords like inflation/safe haven/yield)",
      "timestamp": "YYYY-MM-DD HH:MM:SS" (1-4h before {event_time_dt.strftime('%H:%M:%S')})
    }}
  ],
  "upcoming_events": [
    {{
      "event": "CPI"|"FOMC"|"NFP"|"GDP"|"Unemployment Rate",
      "impact": "high"|"medium",
      "time": "YYYY-MM-DD HH:MM:SS" (30m-6h after {event_time_dt.strftime('%H:%M:%S')})
    }}
  ]
}}
Generate exactly 3 news_headlines and 1-2 upcoming_events.
Return raw JSON ONLY. No markdown code blocks.
"""

    content = None

    # 1. Try AgentRouter GLM-5.2
    try:
        logger.info("Initializing AgentRouter GLM-5.2 for sentiment/news generation...")
        model_glm = OpenAILike(
            id="glm-5.2",
            api_key="sk-lHCp3TY8vQ8OvM422AtXGqr8gC5iGDsuQ9MYL6BDzACfmWzR",
            base_url="https://agentrouter.org/v1",
            temperature=0.6,
            top_p=0.95,
            max_tokens=4096,
            timeout=15.0,
            max_retries=0,
            default_headers={
                "User-Agent": "claude-cli/2.1.158 (external, sdk-cli)",
                "anthropic-version": "2023-06-01",
                "anthropic-beta": "claude-code-20250219",
                "x-app": "cli"
            }
        )
        agent_glm = Agent(
            model=model_glm,
            description="You are a historical financial market news and economic calendar archiver for Gold (XAUUSD).",
        )
        response = agent_glm.run(prompt)
        if not response or not response.content:
            raise ValueError("Empty response content from AgentRouter GLM-5.2")
        content = response.content.strip()
        if "Unknown model error" in content or ("{" not in content and "}" not in content):
            raise ValueError(f"Invalid content returned from AgentRouter GLM-5.2: {content}")
        logger.info("✅ Successfully generated sentiment data via AgentRouter GLM-5.2")
    except Exception as glm_err:
        logger.warning(f"AgentRouter GLM-5.2 generation failed, trying Qwen 397B: {glm_err}")

        # 2. Try NVIDIA Qwen 397B
        try:
            logger.info("Initializing NVIDIA Qwen 397B for sentiment/news generation...")
            model_397b = OpenAILike(
                id="qwen/qwen3.5-397b-a17b",
                api_key="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",
                base_url="https://integrate.api.nvidia.com/v1",
                temperature=0.6,
                top_p=0.95,
                max_tokens=1024,
                timeout=15.0,
                max_retries=0,
            )
            agent_397b = Agent(
                model=model_397b,
                description="You are a historical financial market news and economic calendar archiver for Gold (XAUUSD).",
            )
            response = agent_397b.run(prompt)
            if not response or not response.content:
                raise ValueError("Empty response content from NVIDIA Qwen 397B")
            content = response.content.strip()
            if "Unknown model error" in content or ("{" not in content and "}" not in content):
                raise ValueError(f"Invalid content returned from NVIDIA Qwen 397B: {content}")
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
                timeout=15.0,
                max_retries=0,
            )
            agent_122b = Agent(
                model=model_122b,
                description="You are a historical financial market news and economic calendar archiver for Gold (XAUUSD).",
            )
            response = agent_122b.run(prompt)
            if not response or not response.content:
                raise ValueError("Empty response content from NVIDIA Qwen 122B")
            content = response.content.strip()
            if "Unknown model error" in content or ("{" not in content and "}" not in content):
                raise ValueError(f"Invalid content returned from NVIDIA Qwen 122B: {content}")
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
                    max_output_tokens=1024,
                )
                agent_gemini = Agent(
                    model=model_gemini,
                    description="You are a historical financial market news and economic calendar archiver for Gold (XAUUSD).",
                )
                response = agent_gemini.run(prompt)
                if not response or not response.content:
                    raise ValueError("Empty response content from Gemini Fallback")
                content = response.content.strip()
                if "Unknown model error" in content or ("{" not in content and "}" not in content):
                    raise ValueError(f"Invalid content returned from Gemini Fallback: {content}")
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

    # Save to LanceDB cache
    try:
        from valuecell.knowledge.lance_db import LanceDBManager
        db_mgr = LanceDBManager()
        db_mgr.write_news_cache(
            timestamp=event_time_dt.strftime("%Y-%m-%d %H:%M:%S"),
            event_type="SIM",
            news_headlines=result["news_headlines"],
            upcoming_events=result["upcoming_events"]
        )
    except Exception as dbe:
        logger.warning(f"Failed to write to LanceDB cache: {dbe}")

    # Save to local file cache as fallback
    try:
        with open(cache_file, "w") as f:
            json.dump(result, f, indent=4)
        logger.info(f"💾 Saved generated sentiment/news data to file cache: {cache_file.name}")
    except Exception as e:
        logger.warning(f"Failed to write news file cache: {e}")

    return result


def reconstruct_market_data(
    df: pd.DataFrame,
    event_time: int,
    structure_events: List[Dict[str, Any]],
    generate_news: bool = False,
    event_type_hint: Optional[str] = None,
    h1_df: Optional[pd.DataFrame] = None,
    h4_df: Optional[pd.DataFrame] = None,
    target_event_id: Optional[int] = None,
    session_zone: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    df = df[df["time"] <= _to_dt(event_time)].copy()
    if h1_df is not None and not h1_df.empty:
        h1_df = h1_df[h1_df["time"] <= _to_dt(event_time)].copy()
    if h4_df is not None and not h4_df.empty:
        h4_df = h4_df[h4_df["time"] <= _to_dt(event_time)].copy()
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
    # Multiple structure events can share one candle timestamp.  Preserve the
    # CSV/DB sequence so replaying an earlier row cannot see a later same-time
    # event (and replaying LL cannot accidentally execute the preceding BOS).
    events_up_to = [
        e for e in structure_events
        if e.get("time", 0) < event_time
        or (
            e.get("time", 0) == event_time
            and (target_event_id is None or e.get("id") is None or e.get("id") <= target_event_id)
        )
    ]

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
            if "CHOCH" in ev_type or "BOS" in ev_type:
                recent_baseline = "CHOCH" if "CHOCH" in ev_type else "BOS"
                if "CHOCH" in ev_type:
                    recent_choch_dir = "BULLISH" if "BULL" in ev_type or "BULL" in str(ev.get("direction", "")).upper() else "BEARISH"
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
        
        core_type = target_ev_type.split("_")[0]
        is_bos = core_type == "BOS"
        is_choch = core_type == "CHOCH"
        is_hh_ll = core_type in ("HH", "LL")
        
        is_counter_swing = (core_type != "CHOCH") and (is_post_bos or (is_setup_active and (
            (core_type == "LL" and recent_choch_dir == "BULLISH") or
            (core_type == "HH" and recent_choch_dir == "BEARISH")
        )))

        should_run_llm = is_bos or is_choch or (is_hh_ll and is_setup_active and not is_counter_swing)

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
        "session": session_zone.get("session") if session_zone else session,
        "session_zone": session_zone,
        "news_headlines": news_headlines,
        "upcoming_events": upcoming_events,
        "is_counter_swing": is_counter_swing if generate_news else False,
        "h1_data": h1_df,
        "h4_data": h4_df,
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
                        "event_type": p.get("event_type"),
                        "timeframe": p.get("timeframe"),
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

    ev_ts = ev.get("time") or 0
    _ar = result.get("agent_results") or {}
    _ms = _ar.get("market_structure") or {}
    is_first_bos = "BOS" in (ev.get("type") or "").upper() and _ms.get("pre_signal") is not None

    return {
        "event_time": ev_ts,
        "event_type": ev.get("type"),
        "event_direction": ev.get("direction"),
        "session": _detect_session(ev_ts) if ev_ts else None,
        "is_first_bos": is_first_bos,
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
_orchestrator_lock = threading.Lock()


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


def analyze_with_orchestrator_lock(orch, market_data, symbol="XAUUSD", timeframe="M15", veto_mode="hard"):
    """Protect stateful simulation agent and warm-up cache from concurrent requests."""
    with _orchestrator_lock:
        return orch.analyze(market_data=market_data, symbol=symbol, timeframe=timeframe, veto_mode=veto_mode)


def reset_simulation_orchestrator():
    """Reset simulation state without racing an in-flight analysis."""
    with _orchestrator_lock:
        get_orchestrator().reset_state()


def run_simulation(
    candles: List[Dict[str, Any]],
    structure_events: List[Dict[str, Any]],
    backtest_trades: List[Dict[str, Any]],
    symbol: str = "XAUUSD",
    timeframe: str = "M15",
    max_events: int = 300,
    h1_candles: Optional[List[Dict[str, Any]]] = None,
    h4_candles: Optional[List[Dict[str, Any]]] = None,
    veto_mode: str = "hard",
) -> Dict[str, Any]:
    orch = get_orchestrator()

    # Keep only structure-event types the orchestrator should react to.
    structure_events = [e for e in structure_events if any(t in (e.get("type") or "").upper() for t in TRIGGER_TYPES)]

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

    # Load session zones for simulation range in bulk
    session_zones = []
    try:
        from app.core.database import get_db_conn
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT session, is_dst, start_time, end_time, open_price, high_price, low_price, close_price, range_points "
                    "FROM sessionzone_xauusd WHERE DATE(start_time) >= %s AND DATE(end_time) <= %s ORDER BY start_time ASC",
                    (_to_dt(_first_ts).date(), _to_dt(_last_ts).date()),
                )
                session_zones = [
                    {
                        "session": r[0],
                        "is_dst": r[1],
                        "start_time": r[2],
                        "end_time": r[3],
                        "open_price": float(r[4]) if r[4] is not None else None,
                        "high_price": float(r[5]) if r[5] is not None else None,
                        "low_price": float(r[6]) if r[6] is not None else None,
                        "close_price": float(r[7]) if r[7] is not None else None,
                        "range_points": float(r[8]) if r[8] is not None else None,
                    }
                    for r in cur.fetchall()
                ]
        logger.info(f"Loaded {len(session_zones)} session zones for simulation range")
    except Exception as e:
        logger.warning(f"Could not load session zones for simulation bulk run: {e}")

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

    h1_df = pd.DataFrame(h1_candles) if h1_candles else None
    if h1_df is not None and not h1_df.empty:
        h1_df["time"] = pd.to_datetime(h1_df["time"], unit="s", utc=True)
        if "ema200" not in h1_df.columns or h1_df["ema200"].isna().all():
            h1_df["ema200"] = h1_df["close"].ewm(span=200, adjust=False).mean()
        h1_df = h1_df.sort_values("time").reset_index(drop=True)

    h4_df = pd.DataFrame(h4_candles) if h4_candles else None
    if h4_df is not None and not h4_df.empty:
        h4_df["time"] = pd.to_datetime(h4_df["time"], unit="s", utc=True)
        if "ema200" not in h4_df.columns or h4_df["ema200"].isna().all():
            h4_df["ema200"] = h4_df["close"].ewm(span=200, adjust=False).mean()
        h4_df = h4_df.sort_values("time").reset_index(drop=True)

    signals: List[Dict[str, Any]] = []
    frames: List[Dict[str, Any]] = []
    _total_ev = len(structure_events)
    last_event_date = None
    for _ev_idx, ev in enumerate(structure_events, 1):
        ev_time = ev.get("time")
        if ev_time is None:
            continue
        try:
            ev_dt = _to_dt(ev_time)
            current_date = ev_dt.date()
            if last_event_date is not None and current_date > last_event_date:
                # Skenario 2: Skip weekend
                if ev_dt.weekday() < 5:
                    events_before = [e for e in structure_events if e.get("time", 0) < ev_time]
                    recent_baseline = None
                    for old_ev in reversed(events_before):
                        old_ev_type = old_ev.get("type", "").upper()
                        if old_ev_type in ("CHOCH", "BOS"):
                            recent_baseline = old_ev_type
                            break
                    if recent_baseline == "CHOCH":
                        prefetch_time = datetime(current_date.year, current_date.month, current_date.day, 1, 0, 0, tzinfo=timezone.utc)
                        logger.info(f"🌅 Day Change Setup Active: Pre-fetching news for {current_date} at 01:00:00...")
                        import threading
                        threading.Thread(
                            target=_generate_historical_sentiment_data,
                            args=(prefetch_time,),
                            daemon=True
                        ).start()
            last_event_date = current_date
        except Exception as pfe:
            logger.warning(f"Failed to check day change pre-fetch: {pfe}")
        session_zone = None
        for sz in session_zones:
            sz_start = int(sz["start_time"].timestamp())
            sz_end = int(sz["end_time"].timestamp())
            if sz_start <= ev_time <= sz_end:
                session_zone = sz
                break
        if session_zone is None:
            sz_candidates = [sz for sz in session_zones if int(sz["start_time"].timestamp()) <= ev_time]
            if sz_candidates:
                session_zone = sz_candidates[-1]

        try:
            md = reconstruct_market_data(
                base_df, ev_time, structure_events, generate_news=True, event_type_hint=ev.get("type"),
                h1_df=h1_df, h4_df=h4_df, target_event_id=ev.get("id"), session_zone=session_zone
            )
        except Exception as e:
            logger.warning(f"sim: skip event {ev_time}: {e}")
            continue
        try:
            result = analyze_with_orchestrator_lock(orch, md, symbol, timeframe, veto_mode=veto_mode)
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
            _ar = result.get("agent_results") or {}
            _ms = _ar.get("market_structure") or {}
            is_first_bos = "BOS" in _ev_type and _ms.get("pre_signal") is not None
            
            if is_first_bos:
                # Log rejected decisions to NeonDB
                try:
                    from app.services.simulation_logger import _sim_logger
                    _ml = _ar.get("ml_prediction") or {}
                    _st = _ar.get("sentiment") or {}
                    _sim_logger.log_decision({
                        "symbol": symbol, "timeframe": timeframe,
                        "event_time": _to_dt(ev_time),
                        "event_type": ev.get("type"),
                        "event_price": ev.get("price"),
                        "session": _detect_session(ev_time),
                        "entry_session": _detect_session(ev_time),
                        "final_signal": result.get("final_signal"),
                        "final_confidence": result.get("final_confidence"),
                        "consensus_level": result.get("consensus_level"),
                        "approved": False,
                        "reasoning": result.get("reasoning"),
                        "reject_reason": result.get("reasoning") or result.get("error") or "consensus_failed",
                        "close_reason": "REJECTED",
                        "ms_signal": _ms.get("signal"), "ms_confidence": _ms.get("confidence"),
                        "ml_signal": _ml.get("signal"), "ml_confidence": _ml.get("confidence"),
                        "sent_signal": _st.get("final_signal"), "sent_confidence": _st.get("final_confidence"),
                        "ml_model_version": _ml.get("model_type") or "regression_v5_unconstrained",
                        "news_context": md.get("news_headlines"),
                        "calendar_context": md.get("upcoming_events"),
                        "top_sentiment_headlines": _st.get("sentiment", {}).get("keyword_matches"),
                        "net_profit_usd": 0.0,
                    })
                except Exception as _le:
                    logger.debug(f"[SimLogger] rejected log skipped: {_le}")
                
                signals.append({
                    "time": ev_time,
                    "signal": result.get("final_signal", "HOLD"),
                    "confidence": float(result.get("final_confidence", 0.0)),
                    "consensus": result.get("consensus_level", ""),
                    "sl": None,
                    "tp": None,
                    "lot": 0.0,
                    "outcome": "REJECTED",
                    "outcome_bar": None,
                    "session": _detect_session(ev_time),
                })
            continue
        sig = result["final_signal"]
        sl = (result.get("sl_tp") or {}).get("sl_price")
        tp = (result.get("sl_tp") or {}).get("tp_price")
        entry_p = (result.get("sl_tp") or {}).get("entry_price") or md.get("current_bar", {}).get("close")
        outcome = forward_walk_outcome(candles, ev_time, sig, sl, tp)
        pnl_pips = None
        if outcome["outcome"] == "TP" and entry_p and tp:
            pnl_pips = round(abs(tp - entry_p) / 0.1, 1)
        elif outcome["outcome"] == "SL" and entry_p and sl:
            pnl_pips = -round(abs(sl - entry_p) / 0.1, 1)
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
            "session": _detect_session(ev_time),
        })
        # Log approved decisions to NeonDB
        try:
            from app.services.simulation_logger import _sim_logger
            _ar = result.get("agent_results") or {}
            _ms = _ar.get("market_structure") or {}
            _ml = _ar.get("ml_prediction") or {}
            _st = _ar.get("sentiment") or {}
            lot_size = (result.get("position_sizing") or {}).get("lot_size") or 0.01
            net_profit_usd = round(pnl_pips * lot_size * 10.0, 2) if pnl_pips is not None else None
            outcome_str = outcome.get("outcome", "NONE")
            close_reason = "TAKE_PROFIT" if outcome_str == "TP" else ("STOP_LOSS" if outcome_str == "SL" else "TIMEOUT")
            _sim_logger.log_decision({
                "symbol": symbol, "timeframe": timeframe,
                "event_time": _to_dt(ev_time),
                "event_type": ev.get("type"),
                "event_price": ev.get("price"),
                "session": _detect_session(ev_time),
                "entry_session": _detect_session(ev_time),
                "final_signal": sig,
                "final_confidence": result.get("final_confidence"),
                "consensus_level": result.get("consensus_level"),
                "approved": True,
                "reasoning": result.get("reasoning"),
                "close_reason": close_reason,
                "ms_signal": _ms.get("signal"), "ms_confidence": _ms.get("confidence"),
                "ml_signal": _ml.get("signal"), "ml_confidence": _ml.get("confidence"),
                "sent_signal": _st.get("final_signal"), "sent_confidence": _st.get("final_confidence"),
                "ml_model_version": _ml.get("model_type") or "regression_v5_unconstrained",
                "entry_price": entry_p,
                "sl_price": sl, "tp_price": tp,
                "lot_size": lot_size,
                "outcome": outcome_str,
                "outcome_bar_time": _to_dt(_obar) if _obar else None,
                "pnl_pips": pnl_pips,
                "net_profit_usd": net_profit_usd,
                "news_context": md.get("news_headlines"),
                "calendar_context": md.get("upcoming_events"),
                "top_sentiment_headlines": _st.get("sentiment", {}).get("keyword_matches"),
            })
        except Exception as _le:
            logger.debug(f"[SimLogger] approved log skipped: {_le}")
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

    # Filter out rejected signals for metrics calculations
    exec_signals = [s for s in signals if s.get("outcome") != "REJECTED"]

    total = len(exec_signals)
    buy = sum(1 for s in exec_signals if s["signal"] == "BUY")
    sell = sum(1 for s in exec_signals if s["signal"] == "SELL")
    wins = sum(1 for s in exec_signals if s["outcome"] == "TP")
    losses = sum(1 for s in exec_signals if s["outcome"] == "SL")
    decided = wins + losses
    win_rate = (wins / decided) if decided else 0.0
    avg_conf = (sum(s["confidence"] for s in exec_signals) / total) if total else 0.0
    bt_sorted = sorted(
        [t for t in backtest_trades if t.get("entry_time") is not None],
        key=lambda t: t["entry_time"],
    )
    matched = 0
    for s in exec_signals:
        for t in bt_sorted:
            if abs(t["entry_time"] - s["time"]) <= 4 * 3600:
                bt_type = str(t.get("type", "")).upper()
                # Only count agreement for explicitly valid backtest directions;
                # malformed/None types are skipped (neither BUY nor SELL).
                if bt_type == s["signal"]:
                    matched += 1
                break
    agreement_rate = (matched / total) if total else 0.0
    avg_consensus = Counter(s.get("consensus", "") for s in exec_signals).most_common(1)[0][0] if total else ""
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
