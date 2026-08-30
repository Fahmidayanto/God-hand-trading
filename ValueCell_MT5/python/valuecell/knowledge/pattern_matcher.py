"""
Pattern Matcher - High-level interface for pattern similarity search

Provides easy-to-use methods for agents to query historical patterns.
"""

from collections import defaultdict
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timedelta

from loguru import logger
from .lance_db import LanceDBManager, VECTOR_VERSION


SIMILARITY_FACTOR_DIMENSIONS = (
    ("event_structure", range(0, 4)),
    ("direction", range(4, 5)),
    ("ema_distance_scaled", range(5, 6)),
    ("session", range(6, 10)),
    ("structure_hour", range(10, 11)),
    ("timeframe", range(11, 12)),
    ("prior_choch", range(12, 13)),
    ("body_ratio", range(13, 14)),
    ("range_atr_ratio", range(14, 15)),
    ("ema200_h1_h4_context", range(15, 16)),
)


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
        limit: int = 1000,
        min_similarity: float = 0.7,
        prior_choch: bool = False,
        timestamp: Optional[Union[datetime, str]] = None,
        price_ratio: Optional[float] = None,
        body_ratio: Optional[float] = None,
        range_atr_ratio: Optional[float] = None,
        ema200_h1_distance_scaled: Optional[float] = None,
        ema200_h4_distance_scaled: Optional[float] = None,
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
            market_timestamp = timestamp or datetime.now()
            if isinstance(market_timestamp, datetime):
                market_timestamp = market_timestamp.isoformat()

            current_pattern = {
                "timestamp": market_timestamp,
                "event_type": event_type,
                "direction": direction,
                "price": price,
                "ema200": ema200,
                "session": session,
                "timeframe": timeframe,
                "symbol": "XAUUSD",
                "prior_choch": prior_choch,
                "price_ratio": price_ratio,
                "body_ratio": body_ratio,
                "range_atr_ratio": range_atr_ratio,
                "ema200_h1_distance_scaled": ema200_h1_distance_scaled,
                "ema200_h4_distance_scaled": ema200_h4_distance_scaled,
            }
            
            # Search similar patterns
            similar_patterns = self.db.search_similar_patterns(
                current_pattern,
                limit=limit,
                min_similarity=min_similarity
            )
            
            if not similar_patterns:
                return self._empty_evidence("No similar historical patterns found")
            
            # Calculate statistics. Win rate only represents executed outcomes.
            total = len(similar_patterns)
            wins = sum(1 for p in similar_patterns if str(p.get("outcome", "")).upper() == "WIN")
            losses = sum(1 for p in similar_patterns if str(p.get("outcome", "")).upper() == "LOSS")
            rejected = sum(1 for p in similar_patterns if str(p.get("outcome", "")).upper() == "REJECTED")
            pending = sum(1 for p in similar_patterns if str(p.get("outcome", "")).upper() == "PENDING")
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
                win_rate, avg_profit, completed_trades, direction
            )
            
            # Generate reasoning
            reasoning = self._generate_reasoning(
                event_type, direction, win_rate, avg_profit, total, completed_trades, session
            )

            executed_net_profits = [
                float(pattern["net_profit"])
                for pattern in similar_patterns
                if str(pattern.get("outcome", "")).upper() in {"WIN", "LOSS"}
                and pattern.get("net_profit") is not None
            ]
            total_net_profit = sum(executed_net_profits)

            executed_patterns = [
                pattern
                for pattern in similar_patterns
                if str(pattern.get("outcome", "")).upper() in {"WIN", "LOSS"}
            ]
            winning_patterns = [
                pattern
                for pattern in executed_patterns
                if str(pattern.get("outcome", "")).upper() == "WIN"
            ]
            losing_patterns = [
                pattern
                for pattern in executed_patterns
                if str(pattern.get("outcome", "")).upper() == "LOSS"
            ]
            executed_similarity_weight = sum(
                float(pattern.get("similarity", 0.0))
                for pattern in executed_patterns
            )
            winning_similarity_weight = sum(
                float(pattern.get("similarity", 0.0))
                for pattern in winning_patterns
            )

            rejection_groups = defaultdict(list)
            for pattern in similar_patterns:
                if str(pattern.get("outcome", "")).upper() != "REJECTED":
                    continue
                reason_code = pattern.get("reject_reason_code") or "UNKNOWN"
                reason_raw = pattern.get("reject_reason_raw") or "Unknown"
                rejection_groups[(reason_code, reason_raw)].append(
                    float(pattern.get("similarity", 0.0))
                )

            reason_distribution = []
            for (reason_code, reason_raw), similarities in rejection_groups.items():
                count = len(similarities)
                reason_distribution.append({
                    "reason_code": reason_code,
                    "reason_raw": reason_raw,
                    "count": count,
                    "share_of_rejections": count / rejected if rejected else 0.0,
                    "average_similarity": sum(similarities) / count,
                    "max_similarity": max(similarities),
                })
            reason_distribution.sort(
                key=lambda item: (item["count"], item["max_similarity"]),
                reverse=True,
            )

            top_matches = sorted(
                similar_patterns,
                key=lambda pattern: float(pattern.get("similarity", 0.0)),
                reverse=True,
            )[:10]
            for rank, pattern in enumerate(top_matches[:3], start=1):
                pattern["similarity_breakdown_rank"] = rank
                pattern["similarity_breakdown"] = self._build_similarity_breakdown(
                    current_pattern,
                    pattern,
                )

            outcome_distribution = {
                "matches": total,
                "executed": completed_trades,
                "wins": wins,
                "losses": losses,
                "rejected": rejected,
                "pending": pending,
                "executed_win_rate": win_rate,
                "rejection_rate": rejected / total if total else 0.0,
                "completion_rate": completed_trades / total if total else 0.0,
            }
            
            result = {
                "vector_version": VECTOR_VERSION,
                "patterns": similar_patterns,  # Show all matching patterns
                "win_rate": win_rate,
                "avg_profit": avg_profit,
                "total_count": total,
                "completed_count": completed_trades,
                "recommendation": recommendation,
                "confidence": confidence,
                "reasoning": reasoning,
                "outcome_distribution": outcome_distribution,
                "net_profit_statistics": {
                    "total": total_net_profit,
                    "average": total_net_profit / len(executed_net_profits) if executed_net_profits else 0.0,
                },
                "weighted_statistics": {
                    "executed_similarity_weight": executed_similarity_weight,
                    "winning_similarity_weight": winning_similarity_weight,
                    "weighted_win_rate": (
                        winning_similarity_weight / executed_similarity_weight
                        if executed_similarity_weight else 0.0
                    ),
                    "average_executed_similarity": (
                        executed_similarity_weight / completed_trades
                        if completed_trades else 0.0
                    ),
                },
                "outcome_characteristics": {
                    "wins": self._summarize_outcome_group(winning_patterns),
                    "losses": self._summarize_outcome_group(losing_patterns),
                },
                "rejection_analysis": {
                    "total_rejected": rejected,
                    "reason_distribution": reason_distribution,
                },
                "top_matches": top_matches,
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
            return self._empty_evidence(f"Error: {str(e)}")

    @staticmethod
    def _empty_evidence(reasoning: str) -> Dict[str, Any]:
        return {
            "vector_version": VECTOR_VERSION,
            "patterns": [],
            "win_rate": 0.0,
            "avg_profit": 0.0,
            "total_count": 0,
            "completed_count": 0,
            "recommendation": "NEUTRAL",
            "confidence": 0.0,
            "reasoning": reasoning,
            "outcome_distribution": {
                "matches": 0,
                "executed": 0,
                "wins": 0,
                "losses": 0,
                "rejected": 0,
                "pending": 0,
                "executed_win_rate": 0.0,
                "rejection_rate": 0.0,
                "completion_rate": 0.0,
            },
            "net_profit_statistics": {"total": 0.0, "average": 0.0},
            "weighted_statistics": {
                "executed_similarity_weight": 0.0,
                "winning_similarity_weight": 0.0,
                "weighted_win_rate": 0.0,
                "average_executed_similarity": 0.0,
            },
            "outcome_characteristics": {
                "wins": PatternMatcher._summarize_outcome_group([]),
                "losses": PatternMatcher._summarize_outcome_group([]),
            },
            "rejection_analysis": {
                "total_rejected": 0,
                "reason_distribution": [],
            },
            "top_matches": [],
        }

    @staticmethod
    def _summarize_outcome_group(patterns: List[Dict[str, Any]]) -> Dict[str, Any]:
        def average(field: str) -> Optional[float]:
            values = [
                float(pattern[field])
                for pattern in patterns
                if pattern.get(field) is not None
            ]
            return sum(values) / len(values) if values else None

        return {
            "count": len(patterns),
            "average_similarity": average("similarity"),
            "average_net_profit": average("net_profit"),
            "average_ema_distance": average("ema_distance"),
            "average_range_atr_ratio": average("range_atr_ratio"),
        }

    @staticmethod
    def _build_similarity_breakdown(
        current_pattern: Dict[str, Any],
        historical_pattern: Dict[str, Any],
    ) -> Dict[str, Any]:
        vectorizer = LanceDBManager.__new__(LanceDBManager)
        current_vector = vectorizer._pattern_to_vector(current_pattern)
        historical_vector = vectorizer._pattern_to_vector(historical_pattern)
        total_squared_distance = sum(
            (current - historical) ** 2
            for current, historical in zip(current_vector, historical_vector)
        )

        raw_values = {
            "event_structure": (
                current_pattern.get("event_type"),
                historical_pattern.get("event_type"),
            ),
            "direction": (
                current_pattern.get("direction"),
                historical_pattern.get("direction"),
            ),
            "ema_distance_scaled": (
                PatternMatcher._scaled_ema_distance(current_pattern),
                PatternMatcher._scaled_ema_distance(historical_pattern),
            ),
            "session": (
                current_pattern.get("session"),
                historical_pattern.get("session"),
            ),
            "structure_hour": (
                PatternMatcher._timestamp_hour(current_pattern.get("timestamp")),
                PatternMatcher._timestamp_hour(historical_pattern.get("timestamp")),
            ),
            "timeframe": (
                current_pattern.get("timeframe"),
                historical_pattern.get("timeframe"),
            ),
            "prior_choch": (
                current_pattern.get("prior_choch"),
                historical_pattern.get("prior_choch"),
            ),
            "body_ratio": (
                current_pattern.get("body_ratio"),
                historical_pattern.get("body_ratio"),
            ),
            "range_atr_ratio": (
                current_pattern.get("range_atr_ratio"),
                historical_pattern.get("range_atr_ratio"),
            ),
            "ema200_h1_h4_context": (
                PatternMatcher._ema_context_values(current_pattern),
                PatternMatcher._ema_context_values(historical_pattern),
            ),
        }

        factors = []
        for factor_name, dimensions in SIMILARITY_FACTOR_DIMENSIONS:
            dimension_list = list(dimensions)
            squared_distance = sum(
                (current_vector[index] - historical_vector[index]) ** 2
                for index in dimension_list
            )
            vector_distance = squared_distance ** 0.5
            current_value, historical_value = raw_values[factor_name]
            available = PatternMatcher._factor_values_available(
                current_value,
                historical_value,
            )
            factors.append({
                "factor": factor_name,
                "current_value": current_value,
                "historical_value": historical_value,
                "vector_distance": vector_distance,
                "factor_similarity": 1.0 / (1.0 + vector_distance),
                "distance_contribution": (
                    squared_distance / total_squared_distance
                    if total_squared_distance > 0
                    else 0.0
                ),
                "available": available,
            })

        return {
            "total_similarity": float(historical_pattern.get("similarity", 0.0)),
            "method": "vector-v2-lite-squared-l2",
            "factors": factors,
            "not_used_in_similarity": [
                "outcome",
                "net_profit",
                "entry_time",
                "entry_price",
                "exit_time",
                "exit_price",
                "duration_minutes",
                "close_reason",
            ],
        }

    @staticmethod
    def _scaled_ema_distance(pattern: Dict[str, Any]) -> Optional[float]:
        price = pattern.get("price")
        ema200 = pattern.get("ema200")
        price_ratio = pattern.get("price_ratio")
        if price is None or ema200 is None:
            return None
        ratio = float(price_ratio) if price_ratio is not None and float(price_ratio) > 0 else 1.0
        return (float(price) - float(ema200)) / ratio

    @staticmethod
    def _timestamp_hour(timestamp: Any) -> Optional[float]:
        if timestamp is None:
            return None
        try:
            return datetime.fromisoformat(str(timestamp)).hour
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _ema_context_values(pattern: Dict[str, Any]) -> Optional[Dict[str, float]]:
        values = {}
        for field in ("ema200_h1_distance_scaled", "ema200_h4_distance_scaled"):
            value = pattern.get(field)
            if value is not None:
                values[field] = float(value)
        return values or None

    @staticmethod
    def _factor_values_available(current_value: Any, historical_value: Any) -> bool:
        if current_value is None or historical_value is None:
            return False
        if isinstance(current_value, dict) and isinstance(historical_value, dict):
            return bool(set(current_value) & set(historical_value))
        return True
    
    def _generate_recommendation(
        self,
        win_rate: float,
        avg_profit: float,
        sample_size: int,
        direction: str = "Bullish"
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
        
        is_bearish = direction.upper().startswith("BEAR")
        
        # Strong: high win rate + good profit
        if win_rate >= 0.75 and avg_profit >= 30.0:
            rec = "STRONG_SELL" if is_bearish else "STRONG_BUY"
            return rec, min(0.9, 0.75 + confidence_multiplier * 0.15)
        
        # Buy/Sell: decent win rate + profit
        elif win_rate >= 0.60 and avg_profit >= 20.0:
            rec = "SELL" if is_bearish else "BUY"
            return rec, min(0.75, 0.60 + confidence_multiplier * 0.15)
        
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
