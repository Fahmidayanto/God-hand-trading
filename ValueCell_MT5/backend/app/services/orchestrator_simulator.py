import sys
import threading
import time as _time
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone, timedelta

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
    NV_BASE = "https://integrate.api.nvidia.com/v1"
    AGENTROUTER_BASE = "https://agentrouter.org/v1"
    LLM_DESCRIPTION = "You are a historical financial market news and economic calendar archiver for Gold (XAUUSD)."

    model_chain = [
        ("Groq Qwen 3.6 27B", lambda: OpenAILike(
            id=os.getenv("GROQ_MODEL", "qwen/qwen3.6-27b"),
            api_key=os.getenv("GROQ_API_KEY", ""),
            base_url="https://api.groq.com/openai/v1",
            temperature=0.6, top_p=0.95, max_tokens=2048, timeout=15.0, max_retries=0,
        )),
        ("AgentRouter GLM-5.2", lambda: OpenAILike(
            id="glm-5.2",
            api_key=os.getenv("AGENTROUTER_API_KEY", ""),
            base_url=AGENTROUTER_BASE,
            temperature=0.6, top_p=0.95, max_tokens=4096, timeout=15.0, max_retries=0,
            default_headers={
                "User-Agent": "claude-cli/2.1.158 (external, sdk-cli)",
                "anthropic-version": "2023-06-01",
                "anthropic-beta": "claude-code-20250219",
                "x-app": "cli",
            },
        )),
        ("NVIDIA Nemotron 120B", lambda: OpenAILike(
            id="nvidia/nemotron-3-super-120b-a12b",
            api_key=os.getenv("NVIDIA_120B_API_KEY", os.getenv("NVIDIA_API_KEY", "")),
            base_url=NV_BASE, temperature=0.6, top_p=0.95, max_tokens=1024, timeout=15.0, max_retries=0,
        )),
        ("NVIDIA Nemotron 550B", lambda: OpenAILike(
            id="nvidia/nemotron-3-ultra-550b-a55b",
            api_key=os.getenv("NVIDIA_550B_API_KEY", os.getenv("NVIDIA_API_KEY", "")),
            base_url=NV_BASE, temperature=0.6, top_p=0.95, max_tokens=1024, timeout=15.0, max_retries=0,
        )),
        ("NVIDIA MiniMax M3", lambda: OpenAILike(
            id="minimaxai/minimax-m3",
            api_key=os.getenv("NVIDIA_MINIMAX_API_KEY", os.getenv("NVIDIA_API_KEY", "")),
            base_url=NV_BASE, temperature=0.6, top_p=0.95, max_tokens=1024, timeout=15.0, max_retries=0,
        )),
        ("NVIDIA Inkling", lambda: OpenAILike(
            id="thinkingmachines/inkling",
            api_key=os.getenv("NVIDIA_INKLING_API_KEY", os.getenv("NVIDIA_API_KEY", "")),
            base_url=NV_BASE, temperature=0.6, top_p=0.95, max_tokens=1024, timeout=15.0, max_retries=0,
        )),
        ("NVIDIA Laguna XS 2.1", lambda: OpenAILike(
            id="poolside/laguna-xs-2.1",
            api_key=os.getenv("NVIDIA_LAGUNA_API_KEY", os.getenv("NVIDIA_API_KEY", "")),
            base_url=NV_BASE, temperature=0.6, top_p=0.95, max_tokens=1024, timeout=15.0, max_retries=0,
        )),
        ("NVIDIA GLM 5.2", lambda: OpenAILike(
            id="z-ai/glm-5.2",
            api_key=os.getenv("NVIDIA_GLM_API_KEY", os.getenv("NVIDIA_API_KEY", "")),
            base_url=NV_BASE, temperature=0.6, top_p=0.95, max_tokens=1024, timeout=15.0, max_retries=0,
        )),
        ("Gemini Fallback", lambda: Gemini(
            id="gemini-2.5-flash",
            api_key=os.getenv("GOOGLE_API_KEY"),
            max_output_tokens=1024,
        )),
    ]

    MAX_FULL_RETRIES = 3
    for attempt in range(1, MAX_FULL_RETRIES + 1):
        for name, factory in model_chain:
            if name == "Gemini Fallback" and not os.getenv("GOOGLE_API_KEY"):
                logger.error("GOOGLE_API_KEY not found in environment for fallback.")
                continue
            try:
                logger.info(f"Initializing {name} for sentiment/news generation...")
                agent = Agent(model=factory(), description=LLM_DESCRIPTION)
                response = agent.run(prompt)
                if not response or not response.content:
                    raise ValueError(f"Empty response content from {name}")
                candidate = response.content.strip()
                if "Unknown model error" in candidate or ("{" not in candidate and "}" not in candidate):
                    raise ValueError(f"Invalid content returned from {name}: {candidate}")
                content = candidate
                logger.info(f"✅ Successfully generated sentiment data via {name}")
                break
            except Exception as model_err:
                logger.warning(f"{name} generation failed: {model_err}")
        if content:
            break
        if attempt < MAX_FULL_RETRIES:
            logger.warning(f"All {len(model_chain)} models failed on attempt {attempt}/{MAX_FULL_RETRIES} — retrying from tier 1")
        else:
            logger.error(f"All {len(model_chain)} models failed after {MAX_FULL_RETRIES} full retry cycles.")

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
        try:
            data = json.loads(cleaned_content, strict=False)
        except Exception:
            # Auto-repair truncated quotes and braces
            repaired = cleaned_content.strip()
            unescaped_quotes = len(re.findall(r'(?<!\\)"', repaired))
            if unescaped_quotes % 2 != 0:
                repaired += '"'
            open_b = repaired.count("{")
            close_b = repaired.count("}")
            if open_b > close_b:
                repaired += "}" * (open_b - close_b)
            data = json.loads(repaired, strict=False)
        
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


_daily_anchor_cache: Dict[str, Dict[int, Dict[str, Any]]] = {}
_daily_anchor_lock = threading.RLock()

# Every structure event (CHoCH/HH/LL/BOS) reuses a daily anchor instead of
# triggering its own fresh LLM call. Slots are UTC hours; the last slot
# (21:00) covers the rest of the day (21:00-23:59).
DAILY_ANCHOR_SLOTS = [0, 3, 6, 9, 12, 15, 18, 21]


def _dedup_news(*news_lists: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    merged = []
    for lst in news_lists:
        for item in lst:
            hl = item.get("headline", "").strip()
            if hl and hl not in seen:
                seen.add(hl)
                merged.append(item)
    return merged


def _dedup_events(*event_lists: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    merged = []
    for lst in event_lists:
        for item in lst:
            evt = item.get("event", "").strip()
            if evt and evt not in seen:
                seen.add(evt)
                merged.append(item)
    return merged


def _nearest_daily_anchor_slot(hour: int) -> int:
    """Largest anchor slot <= hour (the last slot absorbs the rest of the day)."""
    slot = DAILY_ANCHOR_SLOTS[0]
    for h in DAILY_ANCHOR_SLOTS:
        if h <= hour:
            slot = h
        else:
            break
    return slot


def _get_daily_anchor_slot(event_date, slot_hour: int, sentiment_agent=None) -> Dict[str, Any]:
    """Lazy per-day, per-slot cumulative cache of scored news anchors.

    Each slot combines its own fresh news with every earlier slot the same
    day (00:00 -> 03:00 -> ... -> 15:00), so later-day anchors carry more
    context. News is fetched and scored once per slot per date; every later
    event landing in the same 3h window/date reuses the cached score instead
    of re-invoking the LLM classifier.
    """
    date_str = event_date.strftime("%Y-%m-%d")
    with _daily_anchor_lock:
        day_cache = _daily_anchor_cache.setdefault(date_str, {})
        cached = day_cache.get(slot_hour)
        if cached is not None:
            return cached

        idx = DAILY_ANCHOR_SLOTS.index(slot_hour)
        if idx == 0:
            prev_news, prev_events = [], []
        else:
            prev = _get_daily_anchor_slot(event_date, DAILY_ANCHOR_SLOTS[idx - 1], sentiment_agent)
            prev_news, prev_events = prev["news_headlines"], prev["upcoming_events"]

        slot_dt = datetime(event_date.year, event_date.month, event_date.day, slot_hour, 0, 0, tzinfo=timezone.utc)
        fresh = _generate_historical_sentiment_data(slot_dt)
        news = _dedup_news(prev_news, fresh.get("news_headlines", []))
        events = _dedup_events(prev_events, fresh.get("upcoming_events", []))

        sentiment_analysis_raw = None
        if sentiment_agent is not None:
            try:
                sentiment_analysis_raw = sentiment_agent.score_news(news, slot_dt)
            except Exception as e:
                logger.warning(f"Anchor sentiment scoring failed for {date_str} slot {slot_hour:02d}:00: {e}")

        combined = {
            "news_headlines": news,
            "upcoming_events": events,
            "sentiment_analysis_raw": sentiment_analysis_raw,
        }
        day_cache[slot_hour] = combined
        logger.info(
            f"📌 Daily anchor slot {slot_hour:02d}:00 ready for {date_str}: {len(news)} headlines "
            f"scored once (reused by every structure event in this 3h window/date)"
        )
        return combined


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
    sentiment_agent=None,
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
    BASE_REFERENCE_PRICE = 4500.0
    close_price = float(current["close"])
    price_ratio = round(close_price / BASE_REFERENCE_PRICE, 6) if close_price > 0 else 1.0
    current_bar = {
        "time": current["time"],
        "open": float(current["open"]),
        "high": float(current["high"]),
        "low": float(current["low"]),
        "close": close_price,
        "volume": int(current["tick_volume"]) if "tick_volume" in df.columns else int(current["volume"]),
        "price_ratio": price_ratio,
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
    precomputed_sentiment = None
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
            # No structure event (CHoCH/HH/LL/BOS) triggers its own fresh LLM
            # call at its own timestamp anymore. Every event reuses the daily
            # anchor slot (00/03/06/09/12/15 UTC) that its timestamp falls
            # into, scored once per slot/date and shared by all events in
            # that 3h window.
            event_hour = _to_dt(event_time).hour
            slot_hour = _nearest_daily_anchor_slot(event_hour)
            anchor = _get_daily_anchor_slot(_to_dt(event_time).date(), slot_hour, sentiment_agent)
            news_headlines = anchor["news_headlines"]
            upcoming_events = anchor["upcoming_events"]
            precomputed_sentiment = anchor["sentiment_analysis_raw"]

    return {
        "df": df,
        "current_bar": current_bar,
        "structure_events": events_up_to,
        "m15_history": df,
        "price_ratio": price_ratio,
        "base_reference_price": BASE_REFERENCE_PRICE,
        "atr": atr,
        "session": session_zone.get("session") if session_zone else session,
        "session_zone": session_zone,
        "news_headlines": news_headlines,
        "upcoming_events": upcoming_events,
        "precomputed_sentiment": precomputed_sentiment,
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
        "llm_msa": _ar.get("llm_msa"),
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

    from dotenv import load_dotenv
    from valuecell.agents.orchestrator_agent import OrchestratorAgent

    load_dotenv(Path(__file__).resolve().parents[3] / ".env")

    base_kwargs = dict(
        enable_market_structure=True,
        enable_ml_prediction=True,
        enable_risk_management=True,
        enable_llm_msa=True,
        consensus_threshold=0.60,
        llm_msa={
            "provider": "suniesis",
            "timeout_seconds": 240.0,
            "suniesis_model_timeout_seconds": 220.0,
        },
    )
    try:
        _cached_orchestrator = OrchestratorAgent(enable_sentiment=True, **base_kwargs)
    except Exception as e:
        logger.warning(
            f"sim: sentiment-enabled orchestrator failed to build ({e}); "
            f"falling back to sentiment-disabled instance"
        )
        try:
            _cached_orchestrator = OrchestratorAgent(enable_sentiment=False, **base_kwargs)
        except ValueError as fallback_exc:
            if "SUNIESIS_API_KEY" not in str(fallback_exc):
                raise
            logger.warning(
                "sim: Suniesis credential unavailable; disabling shadow LLM MSA for this process"
            )
            fallback_kwargs = {**base_kwargs, "enable_llm_msa": False}
            fallback_kwargs.pop("llm_msa", None)
            _cached_orchestrator = OrchestratorAgent(
                enable_sentiment=False,
                **fallback_kwargs,
            )
    return _cached_orchestrator


def analyze_with_orchestrator_lock(orch, market_data, symbol="XAUUSD", timeframe="M15", veto_mode="hard"):
    """Protect stateful simulation agent and warm-up cache from concurrent requests."""
    with _orchestrator_lock:
        return orch.analyze(market_data=market_data, symbol=symbol, timeframe=timeframe, veto_mode=veto_mode)


def resolve_llm_msa_diagnostic_result(orch, result, timeout_seconds=245.0):
    """Wait for shadow LLM output only when building an explicit diagnostic response."""
    llm_result = (result.get("agent_results") or {}).get("llm_msa")
    if not isinstance(llm_result, dict) or llm_result.get("status") != "pending":
        return result

    setup_id = llm_result.get("setup_id")
    llm_agent = getattr(orch, "agents", {}).get("llm_msa")
    if not setup_id or llm_agent is None:
        return result

    resolved = llm_agent.wait_for_result(setup_id, timeout=timeout_seconds)
    result["agent_results"]["llm_msa"] = resolved
    return result


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

    sentiment_agent = getattr(orch, "agents", {}).get("sentiment")

    # BLIND clock-driven sentiment ticks (opsi A). The sentiment LLM is a fully
    # independent 3h-cadence job: it fires at every anchor boundary
    # (00/03/06/09/12/15 UTC) the replay clock crosses, WITHOUT ever peeking at
    # the event list to decide when to run/stop. The clock span is derived only
    # from the loaded candle data range (like live wall-clock would drive it);
    # ticks keep firing until the data runs out -- even on days/windows with zero
    # structure events. Each tick calls the sentiment scorer inline (B1),
    # generates+scores news for that window, logs the verdict, and caches it.
    # Structure events later just reuse the nearest already-fired slot.
    _boundaries: List[tuple] = []
    if sentiment_agent is not None and not base_df.empty:
        _replay_start = base_df["time"].iloc[0].to_pydatetime()
        _replay_end = base_df["time"].iloc[-1].to_pydatetime()
        if _replay_start.tzinfo is None:
            _replay_start = _replay_start.replace(tzinfo=timezone.utc)
        if _replay_end.tzinfo is None:
            _replay_end = _replay_end.replace(tzinfo=timezone.utc)
        _d = _replay_start.date()
        while _d <= _replay_end.date():
            if _d.weekday() < 5:  # weekend: market closed -> clock idle, no ticks
                for slot_hour in DAILY_ANCHOR_SLOTS:
                    slot_dt = datetime(_d.year, _d.month, _d.day, slot_hour, 0, 0, tzinfo=timezone.utc)
                    if _replay_start <= slot_dt <= _replay_end:
                        _boundaries.append((slot_dt, _d, slot_hour))
            _d += timedelta(days=1)
        _boundaries.sort(key=lambda x: x[0])
        logger.info(
            f"🕒 BLIND sentiment clock armed: {len(_boundaries)} 3h tick(s) over "
            f"{_replay_start.strftime('%Y-%m-%d %H:%M')} → {_replay_end.strftime('%Y-%m-%d %H:%M')} UTC "
            f"(fires independent of structure events)"
        )
    _bnd_i = 0

    def _fire_boundary_tick(b_dt, b_date, b_slot) -> None:
        """Run the independent 3h sentiment tick (B1: inline scorer call)."""
        anchor = _get_daily_anchor_slot(b_date, b_slot, sentiment_agent)
        _raw = anchor.get("sentiment_analysis_raw") or {}
        _sent = _raw.get("sentiment")
        _sent = getattr(_sent, "value", _sent) or "n/a"
        _score = _raw.get("score", 0.0) or 0.0
        _n = len(anchor.get("news_headlines") or [])
        logger.info(
            f"🕒 {b_dt.strftime('%m-%d %H:%M')} UTC tick | SENT LLM fired | "
            f"{_n} news | verdict={_sent} | score={_score:+.2f}"
        )

    for _ev_idx, ev in enumerate(structure_events, 1):
        ev_time = ev.get("time")
        if ev_time is None:
            continue

        # Advance the blind clock: fire every 3h tick whose boundary the replay
        # clock has passed up to this event's time. Cached -> reconstruct reuses.
        ev_dt = _to_dt(ev_time)
        while _bnd_i < len(_boundaries) and _boundaries[_bnd_i][0] <= ev_dt:
            _fire_boundary_tick(*_boundaries[_bnd_i])
            _bnd_i += 1

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
                h1_df=h1_df, h4_df=h4_df, target_event_id=ev.get("id"), session_zone=session_zone,
                sentiment_agent=sentiment_agent,
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

    # Blind clock keeps ticking after the last structure event until the replay
    # data runs out -- fire any remaining 3h sentiment ticks (no event will use
    # them; they run because the independent clock says so, mirroring live).
    while _bnd_i < len(_boundaries):
        _fire_boundary_tick(*_boundaries[_bnd_i])
        _bnd_i += 1

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
