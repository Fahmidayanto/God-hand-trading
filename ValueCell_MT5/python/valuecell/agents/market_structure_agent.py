"""
Market Structure Agent - Analyzes market structure patterns

This agent:
1. Detects market structure events (HH/LL/CHoCH/BoS)
2. Queries historical patterns from LanceDB
3. Generates trading signals with confidence scores
4. Provides reasoning based on historical context
"""

import pandas as pd
from typing import Dict, Any, List, Optional
from datetime import datetime
from loguru import logger

from valuecell.adapters.mt5.market_structure_detector import (
    MarketStructureDetector,
    StructureEvent,
    StructureType,
    StructureStatus
)
from valuecell.knowledge.pattern_matcher import PatternMatcher


class MarketStructureAgent:
    """
    Market Structure Agent - First agent in the multi-agent system.
    
    Purpose:
    - Analyze market structure (Smart Money Concepts)
    - Detect HH/LL (Higher Highs/Lower Lows)
    - Detect CHoCH (Change of Character)
    - Detect BoS (Break of Structure)
    - Query historical patterns for similar setups
    - Generate buy/sell signals with confidence
    
    Decision Logic:
    - STRONG_BUY: Confirmed BoS + high historical win rate (>75%)
    - BUY: Confirmed BoS + good win rate (>60%)
    - NEUTRAL: CHoCH or moderate patterns (45-60%)
    - AVOID: Low win rate patterns (<45%)
    """
    
    def __init__(
        self,
        swing_length: int = 5,
        timeframe: str = "M15",
        use_patterns: bool = True
    ):
        """
        Initialize Market Structure Agent.
        
        Args:
            swing_length: Number of bars to look left/right for swing detection (default: 5)
            timeframe: Timeframe string (M15, H1, H4)
            use_patterns: Whether to use historical pattern matching
        """
        self.name = "MarketStructureAgent"
        self.version = "1.0.0"
        self.swing_length = swing_length
        self.timeframe = timeframe
        self.use_patterns = use_patterns
        
        # Initialize detector
        self.detector = MarketStructureDetector(
            swing_length=swing_length,
            timeframe=timeframe,
            realtime_mode=False  # Use backtest mode for analysis
        )
        
        # Initialize pattern matcher
        self.pattern_matcher = PatternMatcher() if use_patterns else None
        
        logger.info(
            f"✅ {self.name} v{self.version} initialized | "
            f"Swing length: {swing_length} | "
            f"Timeframe: {timeframe} | "
            f"Pattern matching: {use_patterns}"
        )
    
    def analyze(
        self,
        df: pd.DataFrame,
        symbol: str = "XAUUSD",
        timeframe: str = None,
        session: str = "Unknown"
    ) -> Dict[str, Any]:
        """
        Analyze market structure and generate trading signal.
        
        Args:
            df: OHLCV DataFrame with columns [time, open, high, low, close, volume, ema200]
            symbol: Trading symbol
            timeframe: M15, H1, H4 (uses self.timeframe if not provided)
            session: London, NewYork, Asia, Sydney
        
        Returns:
            Dict with:
            - signal: "BUY", "SELL", "HOLD"
            - confidence: 0.0 to 1.0
            - reasoning: Human-readable explanation
            - structure_events: List of detected events
            - pattern_analysis: Historical pattern statistics (if enabled)
            - metadata: Additional info
        """
        try:
            # Use agent's timeframe if not provided
            if timeframe is None:
                timeframe = self.timeframe
            
            logger.info(f"🔍 {self.name} analyzing {symbol} {timeframe}...")
            
            # Validate DataFrame
            required_cols = ["time", "open", "high", "low", "close", "volume"]
            if not all(col in df.columns for col in required_cols):
                raise ValueError(f"DataFrame missing required columns: {required_cols}")
            
            # Need at least swing_length * 2 + 1 bars for detection
            min_bars = self.swing_length * 2 + 1
            if len(df) < min_bars:
                logger.warning(
                    f"Insufficient data: {len(df)} bars (need at least {min_bars})"
                )
                return self._no_signal_response(
                    f"Insufficient data for analysis (need at least {min_bars} bars)"
                )
            
            # Run structure detection
            events = self.detector.detect(df)
            
            if not events:
                logger.info("No structure events detected")
                return self._no_signal_response(
                    "No market structure events detected"
                )
            
            # Get most recent event
            latest_event = events[-1]
            
            logger.info(
                f"Latest event: {latest_event.type.name} "
                f"@ {latest_event.price:.2f}"
            )
            
            # Get current market state
            current_state = self.detector.get_current_state()
            
            # Calculate EMA200 from last bar
            ema200 = df["ema200"].iloc[-1] if "ema200" in df.columns else df["close"].iloc[-1]
            current_price = df["close"].iloc[-1]
            
            # Analyze with historical patterns (if enabled)
            pattern_analysis = None
            if self.use_patterns and self.pattern_matcher:
                pattern_analysis = self._analyze_patterns(
                    latest_event,
                    current_price,
                    ema200,
                    session,
                    timeframe
                )
            
            # Generate signal
            signal_result = self._generate_signal(
                latest_event,
                current_state,
                current_price,
                ema200,
                pattern_analysis
            )
            
            # Build response
            response = {
                "agent": self.name,
                "version": self.version,
                "timestamp": datetime.now().isoformat(),
                "symbol": symbol,
                "timeframe": timeframe,
                "session": session,
                **signal_result,
                "structure_events": [e.to_dict() for e in events[-5:]],  # Last 5 events
                "current_state": current_state,
                "pattern_analysis": pattern_analysis,
                "metadata": {
                    "total_events": len(events),
                    "latest_event": latest_event.to_dict(),
                    "current_price": current_price,
                    "ema200": ema200,
                    "price_vs_ema": "ABOVE" if current_price > ema200 else "BELOW",
                    "ema_distance": current_price - ema200
                }
            }
            
            logger.info(
                f"✅ {self.name} signal: {response['signal']} | "
                f"Confidence: {response['confidence']:.2f} | "
                f"Event: {latest_event.type.name}"
            )
            
            return response
            
        except Exception as e:
            logger.error(f"❌ {self.name} analysis failed: {e}")
            return self._error_response(str(e))
    
    def _analyze_patterns(
        self,
        event: StructureEvent,
        price: float,
        ema200: float,
        session: str,
        timeframe: str
    ) -> Optional[Dict[str, Any]]:
        """Query historical patterns for similar setups"""
        try:
            # Map event type to string
            event_type_str = event.type.name  # BOS, CHOCH, HH, LL
            
            # Determine direction from event type
            if event_type_str in ["BOS_BULLISH", "CHOCH_BULLISH"]:
                direction_str = "Bullish"
                event_type_str = event_type_str.replace("_BULLISH", "")
            elif event_type_str in ["BOS_BEARISH", "CHOCH_BEARISH"]:
                direction_str = "Bearish"
                event_type_str = event_type_str.replace("_BEARISH", "")
            elif event_type_str == "HH":
                direction_str = "Bullish"
            elif event_type_str == "LL":
                direction_str = "Bearish"
            else:
                direction_str = "Neutral"
            
            # Query patterns
            pattern_result = self.pattern_matcher.find_similar_patterns(
                event_type=event_type_str,
                direction=direction_str,
                price=price,
                ema200=ema200,
                session=session,
                timeframe=timeframe,
                limit=20,
                min_similarity=0.7
            )
            
            logger.info(
                f"Pattern analysis: {pattern_result['total_count']} similar patterns | "
                f"Win rate: {pattern_result['win_rate']:.1%}"
            )
            
            return pattern_result
            
        except Exception as e:
            logger.error(f"Pattern analysis failed: {e}")
            return None
    
    def _generate_signal(
        self,
        event: StructureEvent,
        current_state: Dict,
        price: float,
        ema200: float,
        pattern_analysis: Optional[Dict]
    ) -> Dict[str, Any]:
        """
        Generate trading signal based on structure and patterns.
        
        Decision Logic:
        1. BOS_BULLISH + Price > EMA200 → BUY signal
        2. BOS_BEARISH + Price < EMA200 → SELL signal
        3. CHOCH → NEUTRAL (potential setup, wait for BoS)
        4. HH/LL → HOLD (just structure, not actionable)
        
        Confidence Scoring:
        - Base: 0.5 (structure confirmed)
        - +0.2: Price aligned with EMA200
        - +0.0 to +0.3: Pattern analysis (win rate based)
        """
        
        # Extract event details
        event_type = event.type.name  # BOS_BULLISH, BOS_BEARISH, CHOCH_BULLISH, etc.
        
        # Base signal from structure
        signal = "HOLD"
        confidence = 0.0
        reasoning_parts = []
        
        # ===== BOS SIGNAL =====
        if "BOS" in event_type:
            confidence = 0.5  # Base confidence for BoS
            
            if "BULLISH" in event_type:
                signal = "BUY"
                reasoning_parts.append(f"Confirmed Bullish BoS at {event.price:.2f}.")
                
                # Check EMA200 alignment
                if price > ema200:
                    confidence += 0.2
                    ema_dist = price - ema200
                    reasoning_parts.append(
                        f"Price above EMA200 by {ema_dist:.2f} pips (bullish confirmation)."
                    )
                else:
                    reasoning_parts.append(
                        "Price below EMA200 (caution: trend misalignment)."
                    )
            
            elif "BEARISH" in event_type:
                signal = "SELL"
                reasoning_parts.append(f"Confirmed Bearish BoS at {event.price:.2f}.")
                
                # Check EMA200 alignment
                if price < ema200:
                    confidence += 0.2
                    ema_dist = ema200 - price
                    reasoning_parts.append(
                        f"Price below EMA200 by {ema_dist:.2f} pips (bearish confirmation)."
                    )
                else:
                    reasoning_parts.append(
                        "Price above EMA200 (caution: trend misalignment)."
                    )
        
        # ===== CHOCH SIGNAL =====
        elif "CHOCH" in event_type:
            signal = "HOLD"  # Wait for BoS confirmation
            confidence = 0.4
            direction = "Bullish" if "BULLISH" in event_type else "Bearish"
            reasoning_parts.append(
                f"CHoCH detected ({direction}) - potential trend change. "
                f"Waiting for BoS confirmation."
            )
        
        # ===== HH/LL SIGNAL =====
        elif event_type in ["HH", "LL"]:
            signal = "HOLD"
            confidence = 0.3
            reasoning_parts.append(
                f"{event_type} detected at {event.price:.2f} - "
                f"structure noted, no actionable signal."
            )
        
        # ===== PATTERN ANALYSIS BOOST =====
        if pattern_analysis and signal in ["BUY", "SELL"]:
            win_rate = pattern_analysis.get("win_rate", 0.0)
            avg_profit = pattern_analysis.get("avg_profit", 0.0)
            total_count = pattern_analysis.get("total_count", 0)
            
            if total_count >= 5:  # Sufficient data
                # Boost confidence based on win rate
                if win_rate >= 0.75:
                    confidence = min(1.0, confidence + 0.3)
                    reasoning_parts.append(
                        f"Excellent historical performance: {win_rate:.1%} win rate "
                        f"({total_count} patterns, avg {avg_profit:.1f} pips)."
                    )
                elif win_rate >= 0.60:
                    confidence = min(1.0, confidence + 0.2)
                    reasoning_parts.append(
                        f"Good historical performance: {win_rate:.1%} win rate "
                        f"({total_count} patterns, avg {avg_profit:.1f} pips)."
                    )
                elif win_rate >= 0.45:
                    confidence = min(1.0, confidence + 0.1)
                    reasoning_parts.append(
                        f"Moderate historical performance: {win_rate:.1%} win rate "
                        f"({total_count} patterns)."
                    )
                else:
                    confidence = max(0.3, confidence - 0.1)
                    reasoning_parts.append(
                        f"Warning: Low historical win rate {win_rate:.1%} "
                        f"({total_count} patterns)."
                    )
            else:
                reasoning_parts.append(
                    f"Limited historical data ({total_count} patterns), "
                    f"treat with caution."
                )
        
        # Build reasoning
        reasoning = " ".join(reasoning_parts)
        
        # Ensure confidence is in valid range
        confidence = max(0.0, min(1.0, confidence))
        
        return {
            "signal": signal,
            "confidence": round(confidence, 3),
            "reasoning": reasoning
        }
    
    def _no_signal_response(self, reason: str) -> Dict[str, Any]:
        """Generate no signal response"""
        return {
            "agent": self.name,
            "version": self.version,
            "timestamp": datetime.now().isoformat(),
            "signal": "HOLD",
            "confidence": 0.0,
            "reasoning": reason,
            "structure_events": [],
            "current_state": {},
            "pattern_analysis": None,
            "metadata": {}
        }
    
    def _error_response(self, error: str) -> Dict[str, Any]:
        """Generate error response"""
        return {
            "agent": self.name,
            "version": self.version,
            "timestamp": datetime.now().isoformat(),
            "signal": "HOLD",
            "confidence": 0.0,
            "reasoning": f"Analysis error: {error}",
            "structure_events": [],
            "current_state": {},
            "pattern_analysis": None,
            "metadata": {"error": error}
        }
    
    def get_info(self) -> Dict[str, Any]:
        """Get agent information"""
        return {
            "name": self.name,
            "version": self.version,
            "type": "market_structure",
            "description": "Analyzes market structure patterns (HH/LL/CHoCH/BoS) and generates signals",
            "capabilities": [
                "Detect Higher Highs (HH)",
                "Detect Lower Lows (LL)",
                "Detect Change of Character (CHoCH)",
                "Detect Break of Structure (BoS)",
                "Historical pattern matching",
                "Win rate calculation",
                "Signal generation with confidence"
            ],
            "config": {
                "swing_length": self.swing_length,
                "timeframe": self.timeframe,
                "use_patterns": self.use_patterns
            }
        }


# ========== STANDALONE TESTING ==========

if __name__ == "__main__":
    logger.info("Testing MarketStructureAgent...")
    
    # Create sample data
    import numpy as np
    
    dates = pd.date_range(start="2024-01-01", periods=150, freq="15min")
    
    # Generate uptrend data
    base_price = 2300.0
    trend = np.linspace(0, 50, 150)  # Uptrend of 50 pips
    noise = np.random.normal(0, 5, 150)  # Random noise
    
    close_prices = base_price + trend + noise
    
    df = pd.DataFrame({
        "time": dates,
        "open": close_prices - np.random.uniform(1, 3, 150),
        "high": close_prices + np.random.uniform(2, 5, 150),
        "low": close_prices - np.random.uniform(2, 5, 150),
        "close": close_prices,
        "volume": np.random.randint(1000, 5000, 150),
        "ema200": base_price + trend * 0.8  # EMA follows trend slower
    })
    
    # Initialize agent
    agent = MarketStructureAgent(swing_length=5, timeframe="M15")
    
    # Get agent info
    info = agent.get_info()
    logger.info(f"Agent info: {info}")
    
    # Analyze market
    result = agent.analyze(
        df=df,
        symbol="XAUUSD",
        timeframe="M15",
        session="London"
    )
    
    # Print results
    logger.info("=" * 60)
    logger.info(f"Signal: {result['signal']}")
    logger.info(f"Confidence: {result['confidence']:.2f}")
    logger.info(f"Reasoning: {result['reasoning']}")
    logger.info(f"Events detected: {len(result['structure_events'])}")
    
    if result['pattern_analysis']:
        pa = result['pattern_analysis']
        logger.info(f"Pattern analysis: {pa['total_count']} patterns | Win rate: {pa['win_rate']:.1%}")
    
    logger.info("=" * 60)
    logger.info("✅ MarketStructureAgent test complete!")
