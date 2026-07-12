"""
Sentiment Agent - News & Economic Calendar Analysis (MVP)

This agent provides basic sentiment analysis for trading decisions:
1. Keyword-based news sentiment detection
2. Economic calendar event awareness
3. Time-based news filtering (recency matters)
4. Simple confidence scoring

MVP Features:
- Predefined keyword dictionaries (bullish/bearish/neutral)
- High-impact event detection
- News recency weighting (recent news = higher impact)
- Confidence adjustment based on sentiment strength

Sprint 1 additions (2026-07-10):
- Recency filter + exponential decay weighting in _analyze_news_sentiment
- Shadow mode (log decision without intervening) for safe backtest comparison
- Accepts either List[str] or List[Dict] with {headline, timestamp} for headlines

Sprint 2 additions (2026-07-10):
- Economic calendar wired via adapters/calendar/economic_calendar.py
- Soft time-to-event proximity penalty in _calculate_confidence_adjustment
  (6h→-10%, 1h→-25%, <30m→-50%, capped at -15% total). Replaces the old
  binary `-0.05 * count` heuristic so confidence degrades smoothly as we
  approach high-impact events instead of in fixed steps.
"""

from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from enum import Enum
import math
import re
from difflib import SequenceMatcher
from loguru import logger


class SentimentType(Enum):
    """Sentiment classification"""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class ImpactLevel(Enum):
    """Economic event impact classification"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SentimentAgent:
    """
    Sentiment Agent - MVP version for news and economic calendar analysis.
    
    Purpose:
    - Analyze recent news headlines for bullish/bearish sentiment
    - Detect high-impact economic events
    - Adjust trading confidence based on sentiment
    - Filter out trades during high-risk news periods
    
    MVP Implementation:
    - Keyword-based sentiment detection (no NLP/LLM required)
    - Predefined economic calendar events
    - Simple scoring algorithm
    - Fast execution (<10ms)
    """
    
    # Negation words: if any appears within NEG_WINDOW words BEFORE a
    # keyword, the keyword is treated as negated and skipped (not inverted —
    # "despite inflation" doesn't mean bearish, it means unclear, so drop it).
    # Sprint 3 #7.
    NEGATION_WORDS = (
        "no", "not", "nor", "never",
        "despite", "spite",
        "without", "lacks", "lacking", "fails", "failing",
        "denies", "denied", "rejects", "rejected",
        "isnt", "wasnt", "arent", "werent", "wont", "didnt", "doesnt", "cant", "cannot",
    )
    NEG_WINDOW_WORDS = 3

    # Bullish keywords for XAUUSD (Gold)
    BULLISH_KEYWORDS = [
        # Economic concerns (good for gold)
        "inflation", "inflación", "inflasi",
        "recession", "crisis", "crash",
        "uncertainty", "fear", "risk",
        "war", "conflict", "tension",
        "debt", "default",
        
        # Dollar weakness (good for gold)
        "dollar weakness", "dollar decline", "weaker dollar",
        "fed dovish", "rate cut", "stimulus",
        "quantitative easing", "qe",
        
        # Gold positive
        "gold rally", "gold surge", "gold bullish",
        "safe haven", "flight to safety",
        "central bank buying", "gold demand",
    ]
    
    # Bearish keywords for XAUUSD
    BEARISH_KEYWORDS = [
        # Economic strength (bad for gold)
        "strong economy", "economic growth", "recovery",
        "employment gains", "job growth",
        
        # Dollar strength (bad for gold)
        "dollar strength", "dollar rally", "stronger dollar",
        "fed hawkish", "rate hike", "tightening",
        "yield rise", "higher yields",
        
        # Gold negative
        "gold decline", "gold bearish", "gold selloff",
        "profit taking", "gold overbought",
        "central bank selling",
    ]
    
    # High-impact economic events (UTC times)
    HIGH_IMPACT_EVENTS = {
        # US Events (major market movers)
        "FOMC": {"time_utc": [14, 19], "impact": ImpactLevel.HIGH, "avoid_trading": True},
        "NFP": {"time_utc": [13, 30], "impact": ImpactLevel.HIGH, "avoid_trading": True},
        "CPI": {"time_utc": [13, 30], "impact": ImpactLevel.HIGH, "avoid_trading": False},
        "PPI": {"time_utc": [13, 30], "impact": ImpactLevel.MEDIUM, "avoid_trading": False},
        "GDP": {"time_utc": [13, 30], "impact": ImpactLevel.HIGH, "avoid_trading": False},
        "Unemployment": {"time_utc": [13, 30], "impact": ImpactLevel.HIGH, "avoid_trading": False},
        
        # Fed Chair speech
        "Powell Speech": {"time_utc": None, "impact": ImpactLevel.HIGH, "avoid_trading": True},
        "Fed Minutes": {"time_utc": [19, 0], "impact": ImpactLevel.MEDIUM, "avoid_trading": False},
    }
    
    def __init__(
        self,
        news_recency_hours: int = 24,
        sentiment_threshold: float = 0.3,
        enable_event_filtering: bool = True,
        recency_decay_hours: float = 12.0,
        shadow_mode: bool = False,
        use_llm: bool = True,
        iamhc_api_key: str = "sk-Ruln6P7FIrqb3INnYwcfQy6btxMkFPkHKgAFfr2mEfGbmFqP",
        iamhc_base_url: str = "https://api.iamhc.cn/v1",
        iamhc_model_id: str = "DeepSeek-V4-Pro",
        nvidia_397b_api_key: str = "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",
        nvidia_397b_base_url: str = "https://integrate.api.nvidia.com/v1",
        nvidia_397b_model_id: str = "qwen/qwen3.5-397b-a17b",
        nvidia_122b_api_key: str = "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",
        nvidia_122b_base_url: str = "https://integrate.api.nvidia.com/v1",
        nvidia_122b_model_id: str = "qwen/qwen3.5-122b-a10b",
        agentrouter_api_key: str = "sk-lHCp3TY8vQ8OvM422AtXGqr8gC5iGDsuQ9MYL6BDzACfmWzR",
        agentrouter_base_url: str = "https://agentrouter.org/v1",
        agentrouter_model_id: str = "glm-5.2",
    ):
        """
        Initialize Sentiment Agent.

        Args:
            news_recency_hours: Consider news from last N hours (default: 24).
                Headlines outside this window are dropped entirely.
            sentiment_threshold: Minimum sentiment strength to affect confidence (0-1)
            enable_event_filtering: Whether to filter trades during high-impact events
            recency_decay_hours: Half-life for recency weighting. Headlines exactly
                this many hours old contribute 0.5 weight; newer contributes more,
                older less. Set equal to ``news_recency_hours`` for a linear decay
                over the window. Default 12.
            shadow_mode: When True, compute veto/adjustment as usual but DO NOT
                apply them to ``final_signal`` / ``final_confidence``. The would-be
                decision is exposed under ``shadow_decision`` so it can be logged
                and replayed offline. Production behavior is unchanged when False.
            use_llm: Enable LLM-based sentiment analysis with Gemini fallback.
            iamhc_api_key: IAMHC API Key for DeepSeek.
            iamhc_base_url: IAMHC Base URL.
            iamhc_model_id: IAMHC Model ID.
            nvidia_397b_api_key: NVIDIA 397B API Key.
            nvidia_397b_base_url: NVIDIA 397B Base URL.
            nvidia_397b_model_id: NVIDIA 397B Model ID.
            nvidia_122b_api_key: NVIDIA 122B API Key.
            nvidia_122b_base_url: NVIDIA 122B Base URL.
            nvidia_122b_model_id: NVIDIA 122B Model ID.
            agentrouter_api_key: AgentRouter API Key.
            agentrouter_base_url: AgentRouter Base URL.
            agentrouter_model_id: AgentRouter Model ID.
        """
        self.name = "SentimentAgent"
        self.version = "1.1.0-sprint1"

        self.news_recency_hours = news_recency_hours
        self.sentiment_threshold = sentiment_threshold
        self.enable_event_filtering = enable_event_filtering
        self.recency_decay_hours = float(recency_decay_hours) if recency_decay_hours > 0 else float(news_recency_hours)
        self.shadow_mode = shadow_mode
        self.use_llm = use_llm
        
        self.iamhc_api_key = iamhc_api_key
        self.iamhc_base_url = iamhc_base_url
        self.iamhc_model_id = iamhc_model_id
        
        self.nvidia_397b_api_key = nvidia_397b_api_key
        self.nvidia_397b_base_url = nvidia_397b_base_url
        self.nvidia_397b_model_id = nvidia_397b_model_id
        
        self.nvidia_122b_api_key = nvidia_122b_api_key
        self.nvidia_122b_base_url = nvidia_122b_base_url
        self.nvidia_122b_model_id = nvidia_122b_model_id

        self.agentrouter_api_key = agentrouter_api_key
        self.agentrouter_base_url = agentrouter_base_url
        self.agentrouter_model_id = agentrouter_model_id

        # Convert keywords to lowercase for case-insensitive matching
        self.bullish_keywords = [kw.lower() for kw in self.BULLISH_KEYWORDS]
        self.bearish_keywords = [kw.lower() for kw in self.BEARISH_KEYWORDS]

        logger.info(
            f"✅ {self.name} v{self.version} initialized | "
            f"News window: {news_recency_hours}h | "
            f"Recency decay: {self.recency_decay_hours:.1f}h | "
            f"Sentiment threshold: {sentiment_threshold} | "
            f"Event filtering: {enable_event_filtering} | "
            f"Shadow mode: {shadow_mode} | "
            f"Use LLM: {use_llm} (GLM-5.2 -> Qwen-397B -> Qwen-122B -> Gemini)"
        )


    
    def analyze(
        self,
        signal: str,
        confidence: float,
        current_time: datetime,
        news_headlines: Optional[Union[List[str], List[Dict[str, Any]]]] = None,
        upcoming_events: Optional[List[Dict[str, Any]]] = None,
        symbol: str = "XAUUSD"
    ) -> Dict[str, Any]:
        """
        Analyze sentiment and adjust trading confidence.

        Args:
            signal: Proposed trade direction ("BUY" or "SELL")
            confidence: Current confidence from other agents (0.0 to 1.0)
            current_time: Current timestamp
            news_headlines: Either ``List[str]`` (legacy — treated as "now",
                no recency weight) or ``List[Dict]`` with ``{"headline": str,
                "timestamp": datetime|str}`` for recency-aware weighting.
            upcoming_events: List of upcoming economic events
            symbol: Trading symbol

        Returns:
            Dict with adjusted confidence, sentiment analysis, and reasoning.
            In ``shadow_mode``, ``final_signal`` / ``final_confidence`` reflect
            the original (un-overridden) decision; the would-be production
            decision is exposed under ``shadow_decision``.
        """
        try:
            logger.info(f"🔍 {self.name} analyzing {symbol} {signal}...")

            # Analyze news sentiment
            if news_headlines:
                sentiment_analysis = self._analyze_news_sentiment(
                    news_headlines, current_time
                )
            else:
                sentiment_analysis = {
                    "sentiment": SentimentType.NEUTRAL,
                    "score": 0.0,
                    "strength": "none",
                    "keyword_matches": [],
                    "weighted_bullish_count": 0.0,
                    "weighted_bearish_count": 0.0,
                    "headlines_total": 0,
                    "headlines_kept": 0,
                    "headlines_filtered_by_recency": 0,
                    "oldest_kept": None,
                    "newest_kept": None,
                }

            # Check upcoming economic events
            event_analysis = self._analyze_economic_events(
                upcoming_events, current_time
            )

            # Calculate sentiment adjustment
            adjustment = self._calculate_confidence_adjustment(
                sentiment_analysis=sentiment_analysis,
                event_analysis=event_analysis,
                signal=signal,
                original_confidence=confidence
            )

            # Determine if trade should be filtered (production decision)
            should_filter = self._should_filter_trade(
                event_analysis, sentiment_analysis, adjustment
            )

            # Build reasoning (production-flavored; shadow note appended later if needed)
            reasoning_parts = self._build_reasoning(
                sentiment_analysis, event_analysis, adjustment, should_filter
            )

            # === Compute production decision (what we WOULD output) ===
            if should_filter:
                prod_final_confidence = 0.0
                prod_final_signal = "HOLD"
                prod_approved = False
            else:
                prod_final_confidence = max(0.0, min(1.0, confidence + adjustment["total"]))
                prod_final_signal = signal if prod_final_confidence >= 0.5 else "HOLD"
                prod_approved = prod_final_confidence >= 0.5

            # === Shadow-mode gate ===
            if self.shadow_mode:
                # In shadow mode, do NOT apply the veto or adjustment — the
                # orchestrator continues with the upstream signal + confidence
                # unchanged. The "would-have-been" production decision is
                # exposed for offline comparison.
                final_signal = signal
                final_confidence = float(confidence)
                approved = signal in ("BUY", "SELL") and confidence >= 0.5
                filtered = False  # by definition: shadow mode doesn't filter
                filter_reason = ""
                reasoning_parts.append(
                    f"[shadow] would_have: signal={prod_final_signal} "
                    f"conf={prod_final_confidence:.3f} "
                    f"adj={adjustment['total']:+.3f} "
                    f"filtered={should_filter}"
                )
            else:
                final_signal = prod_final_signal
                final_confidence = prod_final_confidence
                approved = prod_approved
                filtered = should_filter
                filter_reason = adjustment.get("filter_reason", "")

            # Build response
            response = {
                "agent": self.name,
                "version": self.version,
                "timestamp": current_time.isoformat(),
                "symbol": symbol,
                "original_signal": signal,
                "final_signal": final_signal,
                "approved": approved,
                "original_confidence": confidence,
                "final_confidence": round(final_confidence, 3),
                "confidence_adjustment": round(adjustment["total"], 3),
                "reasoning": " ".join(reasoning_parts),

                # Sentiment details
                "sentiment": {
                    "type": sentiment_analysis["sentiment"].value,
                    "score": round(sentiment_analysis["score"], 3),
                    "strength": sentiment_analysis["strength"],
                    "keyword_matches": sentiment_analysis["keyword_matches"],
                    "adjustment": round(adjustment["sentiment"], 3),
                    "weighted_bullish_count": round(sentiment_analysis.get("weighted_bullish_count", 0.0), 3),
                    "weighted_bearish_count": round(sentiment_analysis.get("weighted_bearish_count", 0.0), 3),
                    "headlines_total": sentiment_analysis.get("headlines_total", 0),
                    "headlines_kept": sentiment_analysis.get("headlines_kept", 0),
                    "headlines_filtered_by_recency": sentiment_analysis.get("headlines_filtered_by_recency", 0),
                    "headlines_filtered_by_dedup": sentiment_analysis.get("headlines_filtered_by_dedup", 0),
                },

                # Event details
                "events": {
                    "upcoming": event_analysis["event_count"],
                    "high_impact": event_analysis["high_impact_count"],
                    "should_avoid": event_analysis["avoid_trading"],
                    "next_event": event_analysis.get("next_event"),
                    "adjustment": round(adjustment["events"], 3),
                },

                # Decision
                "filtered": filtered,
                "filter_reason": filter_reason,
                "shadow_mode": self.shadow_mode,
            }

            # Expose the would-have-been production decision in shadow mode
            if self.shadow_mode:
                response["shadow_decision"] = {
                    "would_signal": prod_final_signal,
                    "would_confidence": round(prod_final_confidence, 3),
                    "would_be_filtered": should_filter,
                    "would_filter_reason": adjustment.get("filter_reason", ""),
                    "would_approved": prod_approved,
                }

            logger.debug(
                f"✅ {self.name} | "
                f"Sentiment: {sentiment_analysis['sentiment'].value} | "
                f"Adjustment: {adjustment['total']:+.3f} | "
                f"Final: {final_confidence:.3f} | "
                f"Shadow={self.shadow_mode}"
            )

            return response

        except Exception as e:
            logger.error(f"❌ {self.name} analysis failed: {e}")
            return self._error_response(str(e), signal, confidence)
    
    def _analyze_news_sentiment_llm(
        self,
        kept_headlines: List[Dict[str, Any]],
        current_time: datetime,
    ) -> Optional[Dict[str, Any]]:
        """Run LLM-based sentiment analysis with sequential fallback: DeepSeek -> Qwen 397B -> Qwen 122B -> Gemini."""
        import json
        import os
        import re
        from agno.agent import Agent
        from agno.models.openai import OpenAILike
        
        headlines_str = ""
        for i, item in enumerate(kept_headlines, 1):
            text = item["text"]
            ts = item["timestamp"]
            
            from datetime import timezone as _tz
            ref = current_time
            ts_ref = ts
            if ref.tzinfo is None and ts_ref.tzinfo is not None:
                ts_ref = ts_ref.astimezone(_tz.utc).replace(tzinfo=None)
            elif ref.tzinfo is not None and ts_ref.tzinfo is None:
                ref = ref.astimezone(_tz.utc).replace(tzinfo=None)

            hours_old = (ref - ts_ref).total_seconds() / 3600.0 if ts.year > 2000 else 0.0
            time_desc = f"{hours_old:.1f}h ago" if hours_old > 0 else "recent"
            headlines_str += f"{i}. ({time_desc}) {text}\n"

        prompt = f"""
Analyze XAUUSD sentiment from headlines (ordered newest first, factor recency).
JSON output format:
{{
  "sentiment": "bullish"|"bearish"|"neutral",
  "score": float (-1.0 to 1.0),
  "strength": "strong"|"moderate"|"weak"|"none",
  "reasoning": "brief explanation"
}}
Return raw JSON ONLY. No markdown code blocks.

Headlines:
{headlines_str}
"""

        content = None
        data = None

        # 1. AgentRouter GLM-5.2
        try:
            logger.info("Initializing AgentRouter GLM-5.2 for sentiment analysis...")
            model_glm = OpenAILike(
                id=self.agentrouter_model_id,
                api_key=self.agentrouter_api_key,
                base_url=self.agentrouter_base_url,
                temperature=0.6,
                top_p=0.95,
                max_tokens=4096,
                default_headers={
                    "User-Agent": "claude-cli/2.1.158 (external, sdk-cli)",
                    "anthropic-version": "2023-06-01",
                    "anthropic-beta": "claude-code-20250219",
                    "x-app": "cli"
                }
            )
            agent_glm = Agent(
                model=model_glm,
                description="You are a market sentiment analyst for Gold (XAUUSD).",
            )
            response = agent_glm.run(prompt)
            if not response or not response.content:
                raise ValueError("Empty response content from AgentRouter GLM-5.2")
            content = response.content.strip()
            
            # Clean markdown code block or extract JSON object robustly via regex
            cleaned_content = content.strip()
            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned_content)
            if match:
                cleaned_content = match.group(1).strip()
            else:
                brace_match = re.search(r"(\{[\s\S]*\})", cleaned_content)
                if brace_match:
                    cleaned_content = brace_match.group(1).strip()
                    
            data = json.loads(cleaned_content)
            logger.info("✅ Successfully analyzed sentiment via AgentRouter GLM-5.2")
        except Exception as glm_err:
            logger.warning(f"AgentRouter GLM-5.2 sentiment analysis failed, trying Qwen 397B: {glm_err}")
            if content:
                logger.warning(f"Raw LLM content was: {content}")

            # 2. NVIDIA Qwen 397B
            try:
                logger.info("Initializing NVIDIA Qwen 397B for sentiment analysis...")
                model_397b = OpenAILike(
                    id=self.nvidia_397b_model_id,
                    api_key=self.nvidia_397b_api_key,
                    base_url=self.nvidia_397b_base_url,
                    temperature=0.6,
                    top_p=0.95,
                    max_tokens=1024,
                )
                agent_397b = Agent(
                    model=model_397b,
                    description="You are a market sentiment analyst for Gold (XAUUSD).",
                )
                response = agent_397b.run(prompt)
                if not response or not response.content:
                    raise ValueError("Empty response content from NVIDIA Qwen 397B")
                content = response.content.strip()
                
                # Clean markdown code block or extract JSON object robustly via regex
                cleaned_content = content.strip()
                match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned_content)
                if match:
                    cleaned_content = match.group(1).strip()
                else:
                    brace_match = re.search(r"(\{[\s\S]*\})", cleaned_content)
                    if brace_match:
                        cleaned_content = brace_match.group(1).strip()
                        
                data = json.loads(cleaned_content)
                logger.info("✅ Successfully analyzed sentiment via NVIDIA Qwen 397B")
            except Exception as qwen397_err:
                logger.warning(f"NVIDIA Qwen 397B sentiment analysis failed, trying Qwen 122B: {qwen397_err}")
                if content:
                    logger.warning(f"Raw LLM content was: {content}")
            
                # 3. NVIDIA Qwen 122B (DeepSeek V4 Pro bypassed)
                try:
                    logger.info("Initializing NVIDIA Qwen 122B for sentiment analysis...")
                    model_122b = OpenAILike(
                        id=self.nvidia_122b_model_id,
                        api_key=self.nvidia_122b_api_key,
                        base_url=self.nvidia_122b_base_url,
                        temperature=0.6,
                        top_p=0.95,
                        max_tokens=1024,
                    )
                    agent_122b = Agent(
                        model=model_122b,
                        description="You are a market sentiment analyst for Gold (XAUUSD).",
                    )
                    response = agent_122b.run(prompt)
                    if not response or not response.content:
                        raise ValueError("Empty response content from NVIDIA Qwen 122B")
                    content = response.content.strip()
                    
                    # Clean markdown code block or extract JSON object robustly via regex
                    cleaned_content = content.strip()
                    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned_content)
                    if match:
                        cleaned_content = match.group(1).strip()
                    else:
                        brace_match = re.search(r"(\{[\s\S]*\})", cleaned_content)
                        if brace_match:
                            cleaned_content = brace_match.group(1).strip()
                            
                    data = json.loads(cleaned_content)
                    logger.info("✅ Successfully analyzed sentiment via NVIDIA Qwen 122B")
                except Exception as qwen122_err:
                    logger.warning(f"NVIDIA Qwen 122B sentiment analysis failed, trying Gemini: {qwen122_err}")
                    if content:
                        logger.warning(f"Raw LLM content was: {content}")
                    
                    # 4. Gemini Fallback
                    try:
                        google_api_key = os.getenv("GOOGLE_API_KEY")
                        if not google_api_key:
                            raise ValueError("GOOGLE_API_KEY not found in environment.")
    
                        from agno.models.google import Gemini
    
                        model_gemini = Gemini(
                            id="gemini-2.5-flash",
                            api_key=google_api_key,
                            max_output_tokens=1024,
                        )
                        agent_gemini = Agent(
                            model=model_gemini,
                            description="You are a market sentiment analyst for Gold (XAUUSD).",
                        )
                        response = agent_gemini.run(prompt)
                        if not response or not response.content:
                            raise ValueError("Empty response content from Gemini Fallback")
                        content = response.content.strip()
                        
                        # Clean markdown code block or extract JSON object robustly via regex
                        cleaned_content = content.strip()
                        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned_content)
                        if match:
                            cleaned_content = match.group(1).strip()
                        else:
                            brace_match = re.search(r"(\{[\s\S]*\})", cleaned_content)
                            if brace_match:
                                cleaned_content = brace_match.group(1).strip()
                                
                        data = json.loads(cleaned_content)
                        logger.info("✅ Successfully analyzed sentiment via Gemini Fallback")
                    except Exception as gemini_err:
                        logger.error(f"Gemini fallback also failed: {gemini_err}")
                        if content:
                            logger.error(f"Raw LLM content was: {content}")
                        return None


        # Parse data safely
        try:
            sentiment_str = data.get("sentiment", "neutral").lower()
            if sentiment_str == "bullish":
                sentiment_type = SentimentType.BULLISH
            elif sentiment_str == "bearish":
                sentiment_type = SentimentType.BEARISH
            else:
                sentiment_type = SentimentType.NEUTRAL

            return {
                "sentiment": sentiment_type,
                "score": float(data.get("score", 0.0)),
                "strength": str(data.get("strength", "none")).lower(),
                "reasoning": str(data.get("reasoning", "")),
            }
        except Exception as parse_err:
            logger.error(f"Error parsing LLM response JSON structure: {parse_err}")
            return None

    def _analyze_news_sentiment(
        self,
        headlines: Union[List[str], List[Dict[str, Any]]],
        current_time: datetime,
    ) -> Dict[str, Any]:
        """Analyze sentiment from news headlines with recency weighting.

        Accepts two input shapes (backward-compatible):

        1. ``List[str]`` — legacy format. Each headline is treated as published
           *now* and given weight ``1.0``. No recency filter is applied.
        2. ``List[Dict]`` — each item should contain a ``headline`` key (or
           ``text`` / ``title``) and an optional ``timestamp`` key (ISO string
           or ``datetime``). Headlines outside the ``news_recency_hours``
           window are dropped. Surviving headlines are weighted by
           ``exp(-hours_old / recency_decay_hours)``.

        Sprint 3 additions:
        - Dedup pass (exact + fuzzy ≥0.85) before keyword matching
          (Tier 2 #8): kill Reuters+Bloomberg copy-paste inflation.
        - Negation-aware matching (Tier 2 #7): ``"despite inflation"``
          no longer counts bullish. Negated matches are still reported
          for observability but contribute zero weight.
        """
        if not headlines:
            return {
                "sentiment": SentimentType.NEUTRAL,
                "score": 0.0,
                "strength": "none",
                "keyword_matches": [],
                "weighted_bullish_count": 0.0,
                "weighted_bearish_count": 0.0,
                "headlines_total": 0,
                "headlines_kept": 0,
                "headlines_filtered_by_recency": 0,
                "headlines_filtered_by_dedup": 0,
                "oldest_kept": None,
                "newest_kept": None,
            }

        normalized = self._normalize_headlines(headlines, current_time)
        deduped, dup_count = self._dedup_headlines(normalized)

        weighted_bullish = 0.0
        weighted_bearish = 0.0
        matched_keywords: List[tuple] = []
        oldest_kept = None
        newest_kept = None
        kept_count = 0
        filtered_by_recency = 0
        total_count = len(normalized)

        kept_headlines = []
        for item in deduped:
            text = item["text"]
            ts = item["timestamp"]
            weight = item["weight"]

            if weight <= 0.0:
                # Outside the recency window — drop silently.
                filtered_by_recency += 1
                continue

            kept_count += 1
            if oldest_kept is None or ts < oldest_kept:
                oldest_kept = ts
            if newest_kept is None or ts > newest_kept:
                newest_kept = ts
            
            kept_headlines.append(item)

        if not kept_headlines:
            return {
                "sentiment": SentimentType.NEUTRAL,
                "score": 0.0,
                "strength": "none",
                "keyword_matches": [],
                "weighted_bullish_count": 0.0,
                "weighted_bearish_count": 0.0,
                "headlines_total": total_count,
                "headlines_kept": 0,
                "headlines_filtered_by_recency": filtered_by_recency,
                "headlines_filtered_by_dedup": dup_count,
                "oldest_kept": None,
                "newest_kept": None,
            }

        # LLM Sentiment Analysis Flow if enabled
        if self.use_llm:
            llm_result = self._analyze_news_sentiment_llm(kept_headlines, current_time)
            if llm_result:
                return {
                    "sentiment": llm_result["sentiment"],
                    "score": llm_result["score"],
                    "strength": llm_result["strength"],
                    "reasoning": llm_result["reasoning"],
                    "keyword_matches": [("llm_reasoning", llm_result["reasoning"], 1.0)],
                    "weighted_bullish_count": 1.0 if llm_result["sentiment"] == SentimentType.BULLISH else 0.0,
                    "weighted_bearish_count": 1.0 if llm_result["sentiment"] == SentimentType.BEARISH else 0.0,
                    "headlines_total": total_count,
                    "headlines_kept": kept_count,
                    "headlines_filtered_by_recency": filtered_by_recency,
                    "headlines_filtered_by_dedup": dup_count,
                    "oldest_kept": oldest_kept.isoformat() if oldest_kept else None,
                    "newest_kept": newest_kept.isoformat() if newest_kept else None,
                }
            else:
                logger.warning("LLM sentiment analysis failed/returned empty, falling back to keyword-based analysis.")

        # Fallback keyword-based analysis
        for item in kept_headlines:
            text = item["text"]
            weight = item["weight"]
            text_lower = text.lower()
            for keyword in self.bullish_keywords:
                if keyword in text_lower and not self._is_negated(text_lower, keyword):
                    weighted_bullish += weight
                    matched_keywords.append(("bullish", keyword, round(weight, 3)))
                elif keyword in text_lower:
                    matched_keywords.append(("negated_bullish", keyword, round(weight, 3)))
            for keyword in self.bearish_keywords:
                if keyword in text_lower and not self._is_negated(text_lower, keyword):
                    weighted_bearish += weight
                    matched_keywords.append(("bearish", keyword, round(weight, 3)))
                elif keyword in text_lower:
                    matched_keywords.append(("negated_bearish", keyword, round(weight, 3)))

        total_weight = weighted_bullish + weighted_bearish
        if total_weight == 0.0:
            sentiment_score = 0.0
            sentiment_type = SentimentType.NEUTRAL
        else:
            sentiment_score = (weighted_bullish - weighted_bearish) / total_weight

            if sentiment_score > 0.2:
                sentiment_type = SentimentType.BULLISH
            elif sentiment_score < -0.2:
                sentiment_type = SentimentType.BEARISH
            else:
                sentiment_type = SentimentType.NEUTRAL

        # Determine strength based on absolute score AND evidence volume.
        abs_score = abs(sentiment_score)
        evidence = total_weight
        if abs_score == 0:
            strength = "none"
        elif abs_score >= 0.8 and evidence >= 0.8:
            strength = "strong"
        elif abs_score >= 0.5 and evidence >= 2.5:
            strength = "strong"
        elif abs_score >= 0.4:
            strength = "moderate"
        else:
            strength = "weak"

        return {
            "sentiment": sentiment_type,
            "score": sentiment_score,
            "strength": strength,
            "keyword_matches": matched_keywords,
            "weighted_bullish_count": weighted_bullish,
            "weighted_bearish_count": weighted_bearish,
            "headlines_total": total_count,
            "headlines_kept": kept_count,
            "headlines_filtered_by_recency": filtered_by_recency,
            "headlines_filtered_by_dedup": dup_count,
            "oldest_kept": oldest_kept.isoformat() if oldest_kept else None,
            "newest_kept": newest_kept.isoformat() if newest_kept else None,
        }


    @staticmethod
    def _is_negated(text_lower: str, keyword: str) -> bool:
        """True if any ``NEGATION_WORDS`` token appears within
        ``NEG_WINDOW_WORDS`` words immediately before any occurrence of
        ``keyword`` in ``text_lower``. Sprint 3 #7.

        Ponytail: re.findall per call is O(n*w) but headlines are short
        (<400 chars) and keywords <20, so it's fine. If profiling ever
        shows this hot, precompile one regex per (neg_word, keyword) pair.
        """
        pos = 0
        kw_len = len(keyword)
        while True:
            idx = text_lower.find(keyword, pos)
            if idx < 0:
                return False
            prefix = text_lower[max(0, idx - 60):idx]
            words = re.findall(r"[a-z']+", prefix)
            window = words[-SentimentAgent.NEG_WINDOW_WORDS:] if words else []
            if any(w in SentimentAgent.NEGATION_WORDS for w in window):
                return True
            pos = idx + kw_len
        return False

    @staticmethod
    def _dedup_headlines(
        items: List[Dict[str, Any]],
        threshold: float = 0.85,
    ) -> tuple:
        """Drop near-duplicate headlines (Tier 2 #8). Returns (kept, dup_count).

        Algorithm: O(n²) pairwise SequenceMatcher. Ponytail: ~30 headlines max,
        so 900 comparisons per cycle is nothing. If the cap ever grows past
        ~200 headlines, switch to a shingled MinHash/LSH index.
        """
        kept: List[Dict[str, Any]] = []
        dup_count = 0
        for item in items:
            text = item["text"]
            is_dup = False
            for kept_item in kept:
                ratio = SequenceMatcher(None, text, kept_item["text"]).ratio()
                if ratio >= threshold:
                    is_dup = True
                    break
            if is_dup:
                dup_count += 1
            else:
                kept.append(item)
        return kept, dup_count

    def _normalize_headlines(
        self,
        headlines: Union[List[str], List[Dict[str, Any]]],
        current_time: datetime,
    ) -> List[Dict[str, Any]]:
        """Coerce input into a uniform ``List[{text, timestamp, weight}]`` shape.

        For ``List[str]`` (legacy), ``timestamp`` falls back to a sentinel far
        in the past that ``_recency_weight`` maps to ``1.0``, preserving
        pre-Sprint 1 behavior exactly.

        For ``List[Dict]``, ``timestamp`` is parsed from common key variants
        and weight is computed via the recency filter + exponential decay.
        """
        from datetime import datetime as _dt

        normalized: List[Dict[str, Any]] = []
        if not headlines:
            return normalized

        if isinstance(headlines[0], str):
            # Legacy: every headline treated as fully-recent.
            for s in headlines:  # type: ignore[union-attr]
                if not isinstance(s, str) or not s.strip():
                    continue
                normalized.append(
                    {"text": s.strip(), "timestamp": _dt(1970, 1, 1), "weight": 1.0}
                )
            return normalized

        # Dict shape.
        ts_keys = ("timestamp", "published_at", "published", "time", "datetime", "date")
        text_keys = ("headline", "text", "title", "content")
        for item in headlines:  # type: ignore[union-attr]
            if not isinstance(item, dict):
                continue
            text = None
            for k in text_keys:
                v = item.get(k)
                if isinstance(v, str) and v.strip():
                    text = v.strip()
                    break
            if text is None:
                continue

            ts_value = None
            for k in ts_keys:
                if k in item:
                    ts_value = item[k]
                    break

            ts = self._coerce_timestamp(ts_value) if ts_value is not None else None
            if ts is None:
                # Treat as legacy input if we can't parse a timestamp.
                ts = _dt(1970, 1, 1)

            weight = self._recency_weight(ts, current_time)
            normalized.append({"text": text, "timestamp": ts, "weight": weight})
        return normalized

    def _coerce_timestamp(self, value: Any) -> Optional[datetime]:
        """Best-effort conversion to ``datetime``; ``None`` on failure."""
        from datetime import datetime as _dt
        if isinstance(value, _dt):
            return value
        if isinstance(value, (int, float)):
            # Assume Unix seconds; fall back to ms if the number is too big.
            try:
                if value > 1e12:
                    return _dt.utcfromtimestamp(value / 1000.0)
                return _dt.utcfromtimestamp(value)
            except (OverflowError, OSError, ValueError):
                return None
        if isinstance(value, str):
            s = value.strip()
            if not s:
                return None
            # Try ISO-8601 (with/without trailing Z).
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            try:
                return _dt.fromisoformat(s)
            except ValueError:
                pass
            try:
                # Common alternate: "YYYY-MM-DD HH:MM:SS"
                return _dt.strptime(s, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return None
        return None

    def _recency_weight(self, ts: datetime, current_time: datetime) -> float:
        """Compute exponential-decay weight for a headline, plus recency filter.

        Returns ``0.0`` for headlines outside the ``news_recency_hours`` window,
        otherwise ``exp(-hours_old / recency_decay_hours)``. Decay is anchored
        to ``current_time`` (caller-supplied, must be tz-naive UTC or tz-aware
        both work — we strip tz for arithmetic).
        """
        from datetime import datetime as _dt, timezone as _tz

        if ts.year < 2000:
            # Sentinel value from legacy str-only input — accept with full weight.
            return 1.0

        ref = current_time
        if ref.tzinfo is None and ts.tzinfo is not None:
            ts = ts.astimezone(_tz.utc).replace(tzinfo=None)
        elif ref.tzinfo is not None and ts.tzinfo is None:
            ref = ref.astimezone(_tz.utc).replace(tzinfo=None)

        hours_old = (ref - ts).total_seconds() / 3600.0

        if hours_old < 0:
            # Future-dated headline (clock skew, timezone drift) — treat as
            # "just published" so it still contributes.
            hours_old = 0.0

        if hours_old > self.news_recency_hours:
            return 0.0

        if self.recency_decay_hours <= 0:
            return 1.0

        return math.exp(-hours_old / self.recency_decay_hours)
    
    def _analyze_economic_events(
        self,
        events: Optional[List[Dict[str, Any]]],
        current_time: datetime
    ) -> Dict[str, Any]:
        """Analyze upcoming economic events.

        Sprint 2: also computes ``proximity_penalty`` — the sum of
        :meth:`_proximity_penalty` across all high-impact events within the
        next 6h. Consumed by ``_calculate_confidence_adjustment``.
        """
        
        empty = {
            "event_count": 0,
            "high_impact_count": 0,
            "avoid_trading": False,
            "next_event": None,
            "proximity_penalty": 0.0,
        }
        if not events:
            return empty
        
        high_impact_count = 0
        avoid_trading = False
        next_event = None
        proximity_penalty = 0.0
        
        for event in events:
            event_name = event.get("name", "")
            event_time = event.get("time")
            impact = event.get("impact", "low").lower()
            
            # Check if high impact
            if impact == "high":
                high_impact_count += 1
                # Sprint 2: add proximity penalty for high-impact events
                if event_time is not None:
                    try:
                        hours_to = (event_time - current_time).total_seconds() / 3600.0
                        proximity_penalty += self._proximity_penalty(hours_to)
                    except TypeError:
                        # tz-aware vs tz-naive mismatch — skip silently.
                        # Ponytail: trust the upstream wrapper to normalize.
                        pass
            
            # Check if we should avoid trading
            for known_event, config in self.HIGH_IMPACT_EVENTS.items():
                if known_event.lower() in event_name.lower():
                    if config["avoid_trading"]:
                        avoid_trading = True
            
            # Track next event
            if event_time and (next_event is None or event_time < next_event.get("time", datetime.max)):
                next_event = {
                    "name": event_name,
                    "time": event_time,
                    "impact": impact
                }
        
        return {
            "event_count": len(events),
            "high_impact_count": high_impact_count,
            "avoid_trading": avoid_trading and self.enable_event_filtering,
            "next_event": next_event,
            "proximity_penalty": proximity_penalty,
        }
    
    def _calculate_confidence_adjustment(
        self,
        sentiment_analysis: Dict[str, Any],
        event_analysis: Dict[str, Any],
        signal: str,
        original_confidence: float
    ) -> Dict[str, float]:
        """Calculate confidence adjustment based on sentiment and events.

        Sprint 2: event penalty is now a time-to-event proximity curve
        (see :meth:`_proximity_penalty`) summed across high-impact events,
        capped at -15%. The old `count * -0.05` heuristic is gone.
        """
        
        sentiment_adj = 0.0
        event_adj = 0.0
        filter_reason = ""
        
        # === Sentiment Adjustment ===
        sentiment_score = sentiment_analysis["score"]
        sentiment_type = sentiment_analysis["sentiment"]
        
        if abs(sentiment_score) >= self.sentiment_threshold:
            # Check alignment
            sentiment_aligns = (
                (signal == "BUY" and sentiment_type == SentimentType.BULLISH) or
                (signal == "SELL" and sentiment_type == SentimentType.BEARISH)
            )
            
            if sentiment_aligns:
                # Sentiment aligns with signal - boost confidence
                sentiment_adj = abs(sentiment_score) * 0.15  # Max +15%
            else:
                # Sentiment conflicts with signal - reduce confidence
                sentiment_adj = -abs(sentiment_score) * 0.15  # Max -15%
        
        # === Event Adjustment (Sprint 2: proximity curve) ===
        event_adj = -float(event_analysis.get("proximity_penalty", 0.0))
        # ponytail: cap at -50% per spec (closest single event penalty);
        # the curve itself is the safety mechanism, no aggregate cap needed.
        event_adj = max(event_adj, -0.50)
        
        # === Filter Decision ===
        if event_analysis["avoid_trading"]:
            filter_reason = "High-impact event imminent - avoiding trade"
        
        total_adj = sentiment_adj + event_adj
        
        return {
            "sentiment": sentiment_adj,
            "events": event_adj,
            "total": total_adj,
            "filter_reason": filter_reason
        }
    
    @staticmethod
    def _proximity_penalty(hours_to_event: float) -> float:
        """Confidence penalty as we approach a high-impact event.

        Piecewise (per Sprint 2 spec): 6h→0.10, 1h→0.25, <30m→0.50.
        Future-dated or >6h away: 0.0. Already-past events: 0.0
        (the dust has settled, treat as cleared).
        """
        if hours_to_event <= 0 or hours_to_event > 6:
            return 0.0
        if hours_to_event > 1:
            return 0.10
        if hours_to_event > 0.5:
            return 0.25
        return 0.50
    
    def _should_filter_trade(
        self,
        event_analysis: Dict[str, Any],
        sentiment_analysis: Dict[str, Any],
        adjustment: Dict[str, float]
    ) -> bool:
        """Determine if trade should be filtered out"""
        
        # Filter if avoiding high-impact event
        if event_analysis["avoid_trading"]:
            return True
        
        # Filter if sentiment is extremely negative
        if adjustment["total"] < -0.20:  # More than -20% adjustment
            return True
        
        return False
    
    def _build_reasoning(
        self,
        sentiment_analysis: Dict[str, Any],
        event_analysis: Dict[str, Any],
        adjustment: Dict[str, float],
        should_filter: bool,
    ) -> List[str]:
        """Build human-readable reasoning"""
        
        parts = []
        
        # Sentiment reasoning
        sentiment = sentiment_analysis["sentiment"].value
        strength = sentiment_analysis["strength"]
        if strength != "none":
            parts.append(f"News sentiment: {strength} {sentiment}.")
            
            if adjustment["sentiment"] > 0:
                parts.append(f"Sentiment supports signal (+{adjustment['sentiment']:.1%}).")
            elif adjustment["sentiment"] < 0:
                parts.append(f"Sentiment conflicts with signal ({adjustment['sentiment']:.1%}).")
        else:
            parts.append("Neutral news sentiment.")
        
        # Recency note (only when we actually had the chance to filter)
        total = sentiment_analysis.get("headlines_total", 0)
        kept = sentiment_analysis.get("headlines_kept", 0)
        dropped = sentiment_analysis.get("headlines_filtered_by_recency", 0)
        if total > 0 and dropped > 0:
            parts.append(
                f"{dropped}/{total} headlines older than {self.news_recency_hours}h "
                f"ignored (recency filter)."
            )
        
        # Event reasoning
        if event_analysis["event_count"] > 0:
            parts.append(
                f"{event_analysis['event_count']} upcoming event(s), "
                f"{event_analysis['high_impact_count']} high-impact."
            )
            
            if event_analysis["avoid_trading"]:
                parts.append("⚠️ Major event imminent - trade filtered.")
            elif adjustment["events"] < 0:
                parts.append(f"Event uncertainty reduces confidence ({adjustment['events']:.1%}).")
        else:
            parts.append("No major events scheduled.")
        
        # LLM explanation
        if sentiment_analysis.get("reasoning"):
            parts.append(f"LLM explanation: {sentiment_analysis['reasoning']}")

        # Filter decision
        if should_filter:
            if adjustment.get("filter_reason"):
                parts.append(adjustment["filter_reason"])
        
        # Final adjustment
        if not should_filter:
            if adjustment["total"] > 0:
                parts.append(f"Net confidence boost: +{adjustment['total']:.1%}.")
            elif adjustment["total"] < 0:
                parts.append(f"Net confidence reduction: {adjustment['total']:.1%}.")
        
        return parts
    
    def _error_response(self, error: str, signal: str, confidence: float) -> Dict[str, Any]:
        """Generate error response"""
        return {
            "agent": self.name,
            "version": self.version,
            "timestamp": datetime.now().isoformat(),
            "original_signal": signal,
            "final_signal": "HOLD",
            "approved": False,
            "original_confidence": confidence,
            "final_confidence": 0.0,
            "confidence_adjustment": 0.0,
            "reasoning": f"Sentiment analysis error: {error}",
            "sentiment": {
                "type": "neutral",
                "score": 0.0,
                "strength": "none",
                "keyword_matches": [],
                "adjustment": 0.0,
                "weighted_bullish_count": 0.0,
                "weighted_bearish_count": 0.0,
                "headlines_total": 0,
                "headlines_kept": 0,
                "headlines_filtered_by_recency": 0,
                "headlines_filtered_by_dedup": 0,
            },
            "events": {
                "upcoming": 0,
                "high_impact": 0,
                "should_avoid": False,
                "next_event": None,
                "adjustment": 0.0,
            },
            "filtered": True,
            "filter_reason": f"Error: {error}",
            "shadow_mode": self.shadow_mode,
            "error": error,
        }
    
    def get_info(self) -> Dict[str, Any]:
        """Get agent information"""
        return {
            "name": self.name,
            "version": self.version,
            "type": "sentiment_analysis",
            "description": "Keyword-based news sentiment and economic calendar analysis (MVP + Sprint 1 recency)",
            "configuration": {
                "news_recency_hours": self.news_recency_hours,
                "recency_decay_hours": self.recency_decay_hours,
                "sentiment_threshold": self.sentiment_threshold,
                "enable_event_filtering": self.enable_event_filtering,
                "shadow_mode": self.shadow_mode,
            },
            "capabilities": [
                "Keyword-based sentiment detection",
                "Bullish/bearish/neutral classification",
                f"{len(self.bullish_keywords)} bullish keywords",
                f"{len(self.bearish_keywords)} bearish keywords",
                "Economic calendar event awareness",
                "High-impact event filtering",
                "Confidence adjustment (-15% to +15%)",
                "Recency filter + exponential decay weighting",
                "Accepts Dict-shaped headlines with timestamps",
                "Shadow mode for safe prod-vs-shadow comparison",
            ],
            "sentiment_types": [s.value for s in SentimentType],
            "impact_levels": [i.value for i in ImpactLevel],
            "high_impact_events": list(self.HIGH_IMPACT_EVENTS.keys()),
        }


# ========== STANDALONE TESTING ==========

if __name__ == "__main__":
    logger.info("Testing SentimentAgent...")
    
    # Initialize agent
    agent = SentimentAgent(
        news_recency_hours=24,
        sentiment_threshold=0.3,
        enable_event_filtering=True,
    )
    
    # Get agent info
    info = agent.get_info()
    logger.info(f"Agent: {info['name']} v{info['version']}")
    logger.info(f"Capabilities: {len(info['capabilities'])} features")
    
    # Test scenarios (legacy str format — pre-Sprint 1 behavior)
    test_cases = [
        {
            "name": "Bullish News + No Events",
            "signal": "BUY",
            "confidence": 0.75,
            "news": [
                "Gold rallies on inflation fears",
                "Dollar weakness supports safe haven demand",
                "Central banks increase gold reserves"
            ],
            "events": []
        },
        {
            "name": "Bearish News + Conflicts with BUY",
            "signal": "BUY",
            "confidence": 0.70,
            "news": [
                "Strong US economy pressures gold",
                "Fed hawkish stance leads to gold selloff",
                "Dollar strength weighs on commodities"
            ],
            "events": []
        },
        {
            "name": "Neutral News + High-Impact Event",
            "signal": "BUY",
            "confidence": 0.75,
            "news": [
                "Markets await economic data",
                "Trading ranges persist"
            ],
            "events": [
                {"name": "FOMC Meeting", "time": datetime.now() + timedelta(hours=2), "impact": "high"}
            ]
        },
        {
            "name": "No News + No Events",
            "signal": "SELL",
            "confidence": 0.70,
            "news": None,
            "events": None
        },
    ]
    
    for i, test in enumerate(test_cases, 1):
        logger.info("=" * 70)
        logger.info(f"TEST {i}: {test['name']}")
        logger.info("=" * 70)
        
        result = agent.analyze(
            signal=test["signal"],
            confidence=test["confidence"],
            current_time=datetime.now(),
            news_headlines=test["news"],
            upcoming_events=test["events"],
            symbol="XAUUSD"
        )
        
        logger.info(f"\n📊 Result:")
        logger.info(f"   Original: {result['original_signal']} @ {result['original_confidence']:.3f}")
        logger.info(f"   Final: {result['final_signal']} @ {result['final_confidence']:.3f}")
        logger.info(f"   Adjustment: {result['confidence_adjustment']:+.3f}")
        logger.info(f"   Approved: {result['approved']}")
        logger.info(f"\n📰 Sentiment:")
        logger.info(f"   Type: {result['sentiment']['type']}")
        logger.info(f"   Score: {result['sentiment']['score']:.3f}")
        logger.info(f"   Strength: {result['sentiment']['strength']}")
        logger.info(f"\n📅 Events:")
        logger.info(f"   Upcoming: {result['events']['upcoming']}")
        logger.info(f"   High Impact: {result['events']['high_impact']}")
        logger.info(f"   Avoid Trading: {result['events']['should_avoid']}")
        logger.info(f"\n📝 Reasoning:")
        logger.info(f"   {result['reasoning']}")
        logger.info("")
    
    logger.info("=" * 70)
    logger.info("✅ SentimentAgent basic tests complete!")
    logger.info("")

    # ============================================================
    # Sprint 1: recency + shadow mode tests
    # ============================================================
    logger.info("=" * 70)
    logger.info("SPRINT 1: RECENCY-WEIGHTED HEADLINES")
    logger.info("=" * 70)

    now = datetime.now()
    sprint1_news = [
        # 30 min old — freshest, should dominate
        {"headline": "Gold rallies on inflation fears", "timestamp": now - timedelta(minutes=30)},
        # 6 hours old — moderate weight
        {"headline": "Fed dovish hints at rate cut, dollar weakness", "timestamp": now - timedelta(hours=6)},
        # 18 hours old — already near decay boundary
        {"headline": "Central banks increase gold reserves", "timestamp": now - timedelta(hours=18)},
        # 48 hours old — OUTSIDE the 24h window, must be dropped
        {"headline": "Old news about gold decline", "timestamp": now - timedelta(hours=48)},
        # 5 days old — way out, dropped
        {"headline": "Profit taking in equities", "timestamp": now - timedelta(days=5)},
        # Future-dated (clock skew test) — should still count
        {"headline": "Safe haven demand surges", "timestamp": now + timedelta(minutes=2)},
    ]

    sprint1_result = agent.analyze(
        signal="BUY",
        confidence=0.70,
        current_time=now,
        news_headlines=sprint1_news,
        upcoming_events=None,
        symbol="XAUUSD",
    )
    logger.info(f"   sentiment.type: {sprint1_result['sentiment']['type']}")
    logger.info(f"   sentiment.score: {sprint1_result['sentiment']['score']:.3f}")
    logger.info(f"   sentiment.strength: {sprint1_result['sentiment']['strength']}")
    logger.info(f"   weighted_bullish_count: {sprint1_result['sentiment']['weighted_bullish_count']}")
    logger.info(f"   weighted_bearish_count: {sprint1_result['sentiment']['weighted_bearish_count']}")
    logger.info(f"   headlines_total: {sprint1_result['sentiment']['headlines_total']}")
    logger.info(f"   headlines_kept: {sprint1_result['sentiment']['headlines_kept']}")
    logger.info(f"   headlines_filtered_by_recency: {sprint1_result['sentiment']['headlines_filtered_by_recency']}")
    logger.info(f"   final: {sprint1_result['final_signal']} @ {sprint1_result['final_confidence']:.3f}")
    logger.info(f"   reasoning: {sprint1_result['reasoning']}")
    logger.info("")

    # Sanity invariants
    assert sprint1_result["sentiment"]["headlines_total"] == 6, "Should keep all 6 in input set (filter is internal)"
    assert sprint1_result["sentiment"]["headlines_kept"] == 4, "Fresh + 6h + 18h + future-skip = 4 kept, 48h+5d dropped"
    assert sprint1_result["sentiment"]["headlines_filtered_by_recency"] == 2, "48h and 5d head drop"
    assert sprint1_result["sentiment"]["weighted_bullish_count"] > 0, "Bullish matches expected"

    # ============================================================
    # Sprint 1: SHADOW MODE comparison
    # ============================================================
    logger.info("=" * 70)
    logger.info("SPRINT 1: SHADOW MODE")
    logger.info("=" * 70)

    prod_agent = SentimentAgent(
        news_recency_hours=24,
        sentiment_threshold=0.3,
        enable_event_filtering=True,
        shadow_mode=False,
    )
    shadow_agent = SentimentAgent(
        news_recency_hours=24,
        sentiment_threshold=0.3,
        enable_event_filtering=True,
        shadow_mode=True,
    )

    # Same input — FOMC imminent → production should HOLD, shadow should pass through
    fmc_event = {"name": "FOMC Meeting", "time": now + timedelta(hours=1), "impact": "high"}

    prod_out = prod_agent.analyze(
        signal="BUY",
        confidence=0.78,
        current_time=now,
        news_headlines=["Markets await Fed decision on rates today"],
        upcoming_events=[fmc_event],
        symbol="XAUUSD",
    )
    shadow_out = shadow_agent.analyze(
        signal="BUY",
        confidence=0.78,
        current_time=now,
        news_headlines=["Markets await Fed decision on rates today"],
        upcoming_events=[fmc_event],
        symbol="XAUUSD",
    )

    logger.info(f"   production: signal={prod_out['final_signal']} conf={prod_out['final_confidence']:.3f} filtered={prod_out['filtered']}")
    logger.info(f"   shadow:     signal={shadow_out['final_signal']} conf={shadow_out['final_confidence']:.3f} filtered={shadow_out['filtered']}")
    logger.info(f"   shadow.would_be: {shadow_out.get('shadow_decision')}")

    assert prod_out["final_signal"] == "HOLD", "Production must HOLD on FOMC"
    assert prod_out["filtered"] is True
    assert shadow_out["final_signal"] == "BUY", "Shadow must pass original signal through"
    assert shadow_out["filtered"] is False
    assert shadow_out["final_confidence"] == 0.78
    assert shadow_out["shadow_decision"]["would_signal"] == "HOLD", "Shadow should record what would've happened"
    assert shadow_out["shadow_decision"]["would_be_filtered"] is True

    logger.info("")
    logger.info("   ✅ Production vetoes, shadow passes through — comparison logged.")
    logger.info("")
    logger.info("=" * 70)
    logger.info("✅ Sprint 1 tests complete!")
