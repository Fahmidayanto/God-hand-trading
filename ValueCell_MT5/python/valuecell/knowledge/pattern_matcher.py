"""
Pattern Matcher - High-level interface for pattern similarity search

Provides easy-to-use methods for agents to query historical patterns.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from loguru import logger
from .lance_db import LanceDBManager


class PatternMatcher:
    """
    High-level pattern matching interface for agents.
    
    Purpose:
    - Provide simple API for agents to find similar patterns
    - Calculate win rate and statistics
    - Support decision-making with historical context
    """
    
    def __init__(self, db_manager: LanceDBManager = None):
        """
        Initialize PatternMatcher.
        
        Args:
            db_manager: LanceDB instance (creates new if None)
        """
        self.db = db_manager if db_manager else LanceDBManager()
        logger.info("[SEARCH] PatternMatcher initialized")
    
    def find_similar_patterns(
        self,
        event_type: str,
        direction: str,
        price: float,
        ema200: float,
        session: str,
        timeframe: str = "M15",
        limit: int = 20,
        min_similarity: float = 0.7,
        prior_choch: bool = False,
    ) -> Dict[str, Any]:
        """
        Find similar historical patterns and calculate statistics.
        
        Args:
            event_type: BoS, CHoCH, HH, LL
            direction: Bullish, Bearish
            price: Current price
            ema200: EMA200 value
            session: London, NewYork, Asia, Sydney
            timeframe: M15, H1, H4
            limit: Max results
            min_similarity: Minimum similarity score
        
        Returns:
            Dict with:
            - patterns: List of similar patterns
            - win_rate: % of patterns that resulted in WIN
            - avg_profit: Average profit in pips
            - total_count: Total patterns found
            - recommendation: "STRONG_BUY", "BUY", "NEUTRAL", "AVOID"
        """
        try:
            # Build current pattern
            current_pattern = {
                "timestamp": datetime.now().isoformat(),
                "event_type": event_type,
                "direction": direction,
                "price": price,
                "ema200": ema200,
                "session": session,
                "timeframe": timeframe,
                "symbol": "XAUUSD",
                "prior_choch": prior_choch,
            }
            
            # Search similar patterns
            similar_patterns = self.db.search_similar_patterns(
                current_pattern,
                limit=limit,
                min_similarity=min_similarity
            )
            
            if not similar_patterns:
                return {
                    "patterns": [],
                    "win_rate": 0.0,
                    "avg_profit": 0.0,
                    "total_count": 0,
                    "recommendation": "NEUTRAL",
                    "confidence": 0.0,
                    "reasoning": "No similar historical patterns found"
                }
            
            # Calculate statistics (exclude PENDING from win rate calculation)
            total = len(similar_patterns)
            wins = sum(1 for p in similar_patterns if p.get("outcome") == "WIN")
            losses = sum(1 for p in similar_patterns if p.get("outcome") == "LOSS")
            completed_trades = wins + losses
            win_rate = wins / completed_trades if completed_trades > 0 else 0.0
            
            # Calculate average profit (only winning trades)
            winning_trades = [p for p in similar_patterns if p.get("outcome") == "WIN"]
            avg_profit = (
                sum(p.get("profit_pips", 0) for p in winning_trades) / len(winning_trades)
                if winning_trades else 0.0
            )
            
            # Generate recommendation (based on completed trades for statistical significance)
            recommendation, confidence = self._generate_recommendation(
                win_rate, avg_profit, completed_trades
            )
            
            # Generate reasoning
            reasoning = self._generate_reasoning(
                event_type, direction, win_rate, avg_profit, total, completed_trades, session
            )
            
            result = {
                "patterns": similar_patterns[:10],  # Top 10 most similar
                "win_rate": win_rate,
                "avg_profit": avg_profit,
                "total_count": total,
                "completed_count": completed_trades,
                "recommendation": recommendation,
                "confidence": confidence,
                "reasoning": reasoning
            }
            
            logger.info(
                f"Pattern match: {event_type} {direction} | "
                f"Win rate (completed: {completed_trades}/{total}): {win_rate:.1%} | "
                f"Avg profit: {avg_profit:.1f} pips | "
                f"Rec: {recommendation}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Pattern matching failed: {e}")
            return {
                "patterns": [],
                "win_rate": 0.0,
                "avg_profit": 0.0,
                "total_count": 0,
                "recommendation": "NEUTRAL",
                "confidence": 0.0,
                "reasoning": f"Error: {str(e)}"
            }
    
    def _generate_recommendation(
        self,
        win_rate: float,
        avg_profit: float,
        sample_size: int
    ) -> tuple[str, float]:
        """
        Generate trading recommendation based on statistics.
        
        Returns:
            (recommendation, confidence)
        """
        # Insufficient data
        if sample_size < 5:
            return "NEUTRAL", 0.0
        
        # Calculate confidence based on sample size
        confidence_multiplier = min(1.0, sample_size / 20.0)
        
        # Strong buy: high win rate + good profit
        if win_rate >= 0.75 and avg_profit >= 30.0:
            return "STRONG_BUY", min(0.9, 0.75 + confidence_multiplier * 0.15)
        
        # Buy: decent win rate + profit
        elif win_rate >= 0.60 and avg_profit >= 20.0:
            return "BUY", min(0.75, 0.60 + confidence_multiplier * 0.15)
        
        # Neutral: moderate win rate
        elif win_rate >= 0.45:
            return "NEUTRAL", 0.50
        
        # Avoid: low win rate
        else:
            return "AVOID", min(0.75, 0.40 + confidence_multiplier * 0.15)
    
    def _generate_reasoning(
        self,
        event_type: str,
        direction: str,
        win_rate: float,
        avg_profit: float,
        total: int,
        completed: int,
        session: str
    ) -> str:
        """Generate human-readable reasoning"""
        
        reasoning_parts = [
            f"Historical analysis: {event_type} {direction} in {session} session.",
            f"Found {total} similar patterns (completed: {completed}, win rate: {win_rate:.1%}).",
        ]
        
        if completed == 0:
            reasoning_parts.append("No completed trades found for this setup in history.")
        elif win_rate >= 0.75:
            reasoning_parts.append(f"Excellent historical performance (avg profit: {avg_profit:.1f} pips).")
        elif win_rate >= 0.60:
            reasoning_parts.append(f"Good historical performance (avg profit: {avg_profit:.1f} pips).")
        elif win_rate >= 0.45:
            reasoning_parts.append(f"Moderate historical performance (avg profit: {avg_profit:.1f} pips).")
        else:
            reasoning_parts.append(f"Poor historical performance (avg profit: {avg_profit:.1f} pips).")
        
        if completed < 5:
            reasoning_parts.append("Note: Limited historical trade data, treat with caution.")
        
        return " ".join(reasoning_parts)
    
    def get_session_performance(self, session: str, days: int = 30) -> Dict[str, Any]:
        """
        Get performance statistics for a specific session.
        
        Args:
            session: London, NewYork, Asia, Sydney
            days: Look back period
        
        Returns:
            Dict with session performance metrics
        """
        try:
            # This would query session_patterns collection
            # For now, return placeholder
            logger.info(f"Getting session performance for {session} (last {days} days)")
            
            return {
                "session": session,
                "win_rate": 0.65,
                "avg_profit": 25.5,
                "total_trades": 10,
                "best_event": "BoS",
                "recommendation": "ENABLED"
            }
            
        except Exception as e:
            logger.error(f"Failed to get session performance: {e}")
            return {}
    
    def analyze_trade_correlation(
        self,
        event_type: str,
        session: str,
        timeframe: str
    ) -> Dict[str, Any]:
        """
        Analyze correlation between event type, session, and outcome.
        
        Returns:
            Dict with correlation analysis
        """
        try:
            # Placeholder for future implementation
            logger.info(f"Analyzing correlation: {event_type} in {session} ({timeframe})")
            
            return {
                "event_type": event_type,
                "session": session,
                "timeframe": timeframe,
                "correlation_score": 0.72,
                "sample_size": 45,
                "recommendation": "STRONG"
            }
            
        except Exception as e:
            logger.error(f"Correlation analysis failed: {e}")
            return {}


# ========== STANDALONE USAGE ==========

if __name__ == "__main__":
    logger.info("Testing PatternMatcher...")
    
    # Initialize
    matcher = PatternMatcher()
    
    # Test pattern matching
    result = matcher.find_similar_patterns(
        event_type="BoS",
        direction="Bullish",
        price=2350.50,
        ema200=2345.60,
        session="London",
        timeframe="M15"
    )
    
    logger.info(f"Result: {result}")
    logger.info("✅ PatternMatcher test complete!")
