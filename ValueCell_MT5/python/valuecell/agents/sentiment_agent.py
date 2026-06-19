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
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from enum import Enum
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
        enable_event_filtering: bool = True
    ):
        """
        Initialize Sentiment Agent.
        
        Args:
            news_recency_hours: Consider news from last N hours (default: 24)
            sentiment_threshold: Minimum sentiment strength to affect confidence (0-1)
            enable_event_filtering: Whether to filter trades during high-impact events
        """
        self.name = "SentimentAgent"
        self.version = "1.0.0-MVP"
        
        self.news_recency_hours = news_recency_hours
        self.sentiment_threshold = sentiment_threshold
        self.enable_event_filtering = enable_event_filtering
        
        # Convert keywords to lowercase for case-insensitive matching
        self.bullish_keywords = [kw.lower() for kw in self.BULLISH_KEYWORDS]
        self.bearish_keywords = [kw.lower() for kw in self.BEARISH_KEYWORDS]
        
        logger.info(
            f"✅ {self.name} v{self.version} initialized | "
            f"News window: {news_recency_hours}h | "
            f"Sentiment threshold: {sentiment_threshold} | "
            f"Event filtering: {enable_event_filtering}"
        )
    
    def analyze(
        self,
        signal: str,
        confidence: float,
        current_time: datetime,
        news_headlines: Optional[List[str]] = None,
        upcoming_events: Optional[List[Dict[str, Any]]] = None,
        symbol: str = "XAUUSD"
    ) -> Dict[str, Any]:
        """
        Analyze sentiment and adjust trading confidence.
        
        Args:
            signal: Proposed trade direction ("BUY" or "SELL")
            confidence: Current confidence from other agents (0.0 to 1.0)
            current_time: Current timestamp
            news_headlines: List of recent news headlines
            upcoming_events: List of upcoming economic events
            symbol: Trading symbol
        
        Returns:
            Dict with adjusted confidence, sentiment analysis, and reasoning
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
                    "keyword_matches": []
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
            
            # Determine if trade should be filtered
            should_filter = self._should_filter_trade(
                event_analysis, sentiment_analysis, adjustment
            )
            
            # Build reasoning
            reasoning_parts = self._build_reasoning(
                sentiment_analysis, event_analysis, adjustment, should_filter
            )
            
            # Calculate final confidence
            if should_filter:
                final_confidence = 0.0
                final_signal = "HOLD"
                approved = False
            else:
                final_confidence = max(0.0, min(1.0, confidence + adjustment["total"]))
                final_signal = signal if final_confidence >= 0.5 else "HOLD"
                approved = final_confidence >= 0.5
            
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
                    "adjustment": round(adjustment["sentiment"], 3)
                },
                
                # Event details
                "events": {
                    "upcoming": event_analysis["event_count"],
                    "high_impact": event_analysis["high_impact_count"],
                    "should_avoid": event_analysis["avoid_trading"],
                    "next_event": event_analysis.get("next_event"),
                    "adjustment": round(adjustment["events"], 3)
                },
                
                # Decision
                "filtered": should_filter,
                "filter_reason": adjustment.get("filter_reason", ""),
            }
            
            logger.info(
                f"✅ {self.name} | "
                f"Sentiment: {sentiment_analysis['sentiment'].value} | "
                f"Adjustment: {adjustment['total']:+.3f} | "
                f"Final: {final_confidence:.3f}"
            )
            
            return response
            
        except Exception as e:
            logger.error(f"❌ {self.name} analysis failed: {e}")
            return self._error_response(str(e), signal, confidence)
    
    def _analyze_news_sentiment(
        self,
        headlines: List[str],
        current_time: datetime
    ) -> Dict[str, Any]:
        """Analyze sentiment from news headlines"""
        
        if not headlines:
            return {
                "sentiment": SentimentType.NEUTRAL,
                "score": 0.0,
                "strength": "none",
                "keyword_matches": []
            }
        
        bullish_count = 0
        bearish_count = 0
        matched_keywords = []
        
        # Analyze each headline
        for headline in headlines:
            headline_lower = headline.lower()
            
            # Check bullish keywords
            for keyword in self.bullish_keywords:
                if keyword in headline_lower:
                    bullish_count += 1
                    matched_keywords.append(("bullish", keyword))
            
            # Check bearish keywords
            for keyword in self.bearish_keywords:
                if keyword in headline_lower:
                    bearish_count += 1
                    matched_keywords.append(("bearish", keyword))
        
        # Calculate sentiment score (-1 to +1)
        total_matches = bullish_count + bearish_count
        if total_matches == 0:
            sentiment_score = 0.0
            sentiment_type = SentimentType.NEUTRAL
        else:
            sentiment_score = (bullish_count - bearish_count) / total_matches
            
            if sentiment_score > 0.2:
                sentiment_type = SentimentType.BULLISH
            elif sentiment_score < -0.2:
                sentiment_type = SentimentType.BEARISH
            else:
                sentiment_type = SentimentType.NEUTRAL
        
        # Determine strength
        abs_score = abs(sentiment_score)
        if abs_score >= 0.7:
            strength = "strong"
        elif abs_score >= 0.4:
            strength = "moderate"
        elif abs_score > 0:
            strength = "weak"
        else:
            strength = "none"
        
        return {
            "sentiment": sentiment_type,
            "score": sentiment_score,
            "strength": strength,
            "keyword_matches": matched_keywords,
            "bullish_count": bullish_count,
            "bearish_count": bearish_count
        }
    
    def _analyze_economic_events(
        self,
        events: Optional[List[Dict[str, Any]]],
        current_time: datetime
    ) -> Dict[str, Any]:
        """Analyze upcoming economic events"""
        
        if not events:
            return {
                "event_count": 0,
                "high_impact_count": 0,
                "avoid_trading": False,
                "next_event": None
            }
        
        high_impact_count = 0
        avoid_trading = False
        next_event = None
        
        for event in events:
            event_name = event.get("name", "")
            event_time = event.get("time")
            impact = event.get("impact", "low")
            
            # Check if high impact
            if impact.lower() == "high":
                high_impact_count += 1
            
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
            "next_event": next_event
        }
    
    def _calculate_confidence_adjustment(
        self,
        sentiment_analysis: Dict[str, Any],
        event_analysis: Dict[str, Any],
        signal: str,
        original_confidence: float
    ) -> Dict[str, float]:
        """Calculate confidence adjustment based on sentiment and events"""
        
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
        
        # === Event Adjustment ===
        if event_analysis["high_impact_count"] > 0:
            # Reduce confidence before high-impact events (increased uncertainty)
            event_adj = -0.05 * event_analysis["high_impact_count"]
            event_adj = max(event_adj, -0.15)  # Max -15% reduction
        
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
        should_filter: bool
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
                "adjustment": 0.0
            },
            "events": {
                "upcoming": 0,
                "high_impact": 0,
                "should_avoid": False,
                "next_event": None,
                "adjustment": 0.0
            },
            "filtered": True,
            "filter_reason": f"Error: {error}",
            "error": error
        }
    
    def get_info(self) -> Dict[str, Any]:
        """Get agent information"""
        return {
            "name": self.name,
            "version": self.version,
            "type": "sentiment_analysis",
            "description": "Keyword-based news sentiment and economic calendar analysis (MVP)",
            "configuration": {
                "news_recency_hours": self.news_recency_hours,
                "sentiment_threshold": self.sentiment_threshold,
                "enable_event_filtering": self.enable_event_filtering,
            },
            "capabilities": [
                "Keyword-based sentiment detection",
                "Bullish/bearish/neutral classification",
                f"{len(self.bullish_keywords)} bullish keywords",
                f"{len(self.bearish_keywords)} bearish keywords",
                "Economic calendar event awareness",
                "High-impact event filtering",
                "Confidence adjustment (-15% to +15%)",
                "News recency weighting"
            ],
            "sentiment_types": [s.value for s in SentimentType],
            "impact_levels": [i.value for i in ImpactLevel],
            "high_impact_events": list(self.HIGH_IMPACT_EVENTS.keys())
        }


# ========== STANDALONE TESTING ==========

if __name__ == "__main__":
    logger.info("Testing SentimentAgent...")
    
    # Initialize agent
    agent = SentimentAgent(
        news_recency_hours=24,
        sentiment_threshold=0.3,
        enable_event_filtering=True
    )
    
    # Get agent info
    info = agent.get_info()
    logger.info(f"Agent: {info['name']} v{info['version']}")
    logger.info(f"Capabilities: {len(info['capabilities'])} features")
    
    # Test scenarios
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
    logger.info("✅ SentimentAgent test complete!")
