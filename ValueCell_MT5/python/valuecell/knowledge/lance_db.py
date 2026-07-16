"""
LanceDB Manager - Vector Database for Pattern Similarity Search

Manages 4 collections:
1. historical_structures - Market structure patterns (CHoCH, BoS, HH, LL)
2. market_conditions - OHLCV + indicators for context
3. session_patterns - Session-specific behaviors
4. trade_outcomes - Historical trades for ML training
"""

import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

import lancedb
import pandas as pd
import numpy as np
from loguru import logger


class LanceDBManager:
    """
    Manages LanceDB vector database for pattern similarity search.
    
    Purpose:
    - Store historical market structure patterns as vectors
    - Find similar patterns using cosine similarity
    - Support agent decision-making with historical context
    """
    
    def __init__(self, db_path: str = None):
        """
        Initialize LanceDB connection.
        
        Args:
            db_path: Path to LanceDB database (default: ./python/valuecell/data/lancedb)
        """
        if db_path is None:
            # Default path: ValueCell_MT5/python/valuecell/data/lancedb
            base_dir = Path(__file__).parent.parent
            db_path = base_dir / "data" / "lancedb"
        
        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)
        
        # Connect to LanceDB
        self.db = lancedb.connect(str(self.db_path))
        
        logger.info(f"[DB] LanceDB connected: {self.db_path}")
        
        # ponytail: simple dict cache for vector search results — avoid repeated IO for same pattern
        self._search_cache: Dict[tuple, List[Dict[str, Any]]] = {}
        self._cache_max = 200  # evict when full (FIFO)
        
        # Initialize collections
        self._init_collections()

    def _table_names(self) -> List[str]:
        res = self.db.list_tables()
        if isinstance(res, list):
            return res
        if hasattr(res, "tables"):
            return res.tables
        return list(res)
    
    def _init_collections(self):
        """Initialize all collections if they don't exist"""
        
        # Collection 1: Historical Structures
        if "historical_structures" not in self._table_names():
            logger.info("Creating collection: historical_structures")
            self._create_historical_structures_collection()
        
        # Collection 2: Market Conditions
        if "market_conditions" not in self._table_names():
            logger.info("Creating collection: market_conditions")
            self._create_market_conditions_collection()
        
        # Collection 3: Session Patterns
        if "session_patterns" not in self._table_names():
            logger.info("Creating collection: session_patterns")
            self._create_session_patterns_collection()
        
        # Collection 4: Trade Outcomes
        if "trade_outcomes" not in self._table_names():
            logger.info("Creating collection: trade_outcomes")
            self._create_trade_outcomes_collection()

        # Collection 5: News Sentiment Cache
        if "news_sentiment_cache" not in self._table_names():
            logger.info("Creating collection: news_sentiment_cache")
            self._create_news_sentiment_cache_collection()
        
        logger.info(f"[OK] LanceDB collections ready: {len(self._table_names())} collections")
    
    # ========== COLLECTION 1: Historical Structures ==========
    
    def _create_historical_structures_collection(self):
        """Create historical_structures collection with sample data"""
        
        # Sample pattern for schema definition
        sample_data = [{
            "id": "sample_1",
            "timestamp": datetime.now().isoformat(),
            "symbol": "XAUUSD",
            "timeframe": "M15",
            "event_type": "BoS",
            "direction": "Bullish",
            "price": 2350.50,
            "ema200": 2345.60,
            "ema_distance": 4.90,
            "session": "London",
            "hour": 14,
            "prior_choch": False,
            "outcome": "WIN",  # WIN/LOSS/PENDING
            "profit_pips": 40.0,
            "duration_minutes": 17,
            # Vector representation (will be calculated)
            "vector": [0.0] * 16  # 16-dimensional vector
        }]
        
        df = pd.DataFrame(sample_data)
        table = self.db.create_table("historical_structures", df)
        
        logger.info("✅ Collection 'historical_structures' created")
        return table

    def reset_historical_structures(self) -> bool:
        """Drop and recreate historical_structures collection (fresh start)."""
        try:
            if "historical_structures" in self._table_names():
                self.db.drop_table("historical_structures")
                logger.info("🗑️ Dropped historical_structures collection")
            self._create_historical_structures_collection()
            # Clear search cache so stale results don't persist
            self._search_cache.clear()
            logger.info("✅ historical_structures reset complete (fresh start)")
            return True
        except Exception as e:
            logger.error(f"Failed to reset historical_structures: {e}")
            return False
    
    def add_structure_pattern(self, pattern: Dict[str, Any]) -> bool:
        """
        Add a market structure pattern to the collection.
        
        Args:
            pattern: Dict with keys: timestamp, symbol, timeframe, event_type, 
                    direction, price, ema200, session, etc.
        
        Returns:
            True if added successfully
        """
        try:
            table = self.db.open_table("historical_structures")
            
            # Calculate vector representation
            vector = self._pattern_to_vector(pattern)
            
            # Prepare data
            data = {
                "id": f"{pattern['symbol']}_{pattern['timestamp']}",
                "timestamp": pattern["timestamp"],
                "symbol": pattern["symbol"],
                "timeframe": pattern["timeframe"],
                "event_type": pattern["event_type"],
                "direction": pattern["direction"],
                "price": float(pattern["price"]),
                "ema200": float(pattern.get("ema200", 0)),
                "ema_distance": float(pattern["price"]) - float(pattern.get("ema200", 0)),
                "session": pattern.get("session", "Unknown"),
                "hour": datetime.fromisoformat(pattern["timestamp"]).hour,
                "prior_choch": bool(pattern.get("prior_choch", False)),
                "outcome": pattern.get("outcome", "PENDING"),
                "profit_pips": float(pattern.get("profit_pips", 0)),
                "duration_minutes": int(pattern.get("duration_minutes", 0)),
                "vector": vector
            }
            
            # Add to table
            table.add([data])
            
            logger.debug(f"Added pattern: {pattern['event_type']} at {pattern['timestamp']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add structure pattern: {e}")
            return False

    def add_structure_patterns_batch(self, patterns: List[Dict[str, Any]]) -> bool:
        """
        Add multiple market structure patterns in a single batch (highly optimized).
        """
        if not patterns:
            return True
        try:
            table = self.db.open_table("historical_structures")
            data_list = []
            for pattern in patterns:
                vector = self._pattern_to_vector(pattern)
                data = {
                    "id": f"{pattern['symbol']}_{pattern['timestamp']}",
                    "timestamp": pattern["timestamp"],
                    "symbol": pattern["symbol"],
                    "timeframe": pattern["timeframe"],
                    "event_type": pattern["event_type"],
                    "direction": pattern["direction"],
                    "price": float(pattern["price"]),
                    "ema200": float(pattern.get("ema200", 0)),
                    "ema_distance": float(pattern["price"]) - float(pattern.get("ema200", 0)),
                    "session": pattern.get("session", "Unknown"),
                    "hour": datetime.fromisoformat(pattern["timestamp"]).hour,
                    "prior_choch": bool(pattern.get("prior_choch", False)),
                    "outcome": pattern.get("outcome", "PENDING"),
                    "profit_pips": float(pattern.get("profit_pips", 0)),
                    "duration_minutes": int(pattern.get("duration_minutes", 0)),
                    "vector": vector
                }
                data_list.append(data)
            
            table.add(data_list)
            logger.info(f"✅ Successfully batch added {len(data_list)} patterns to LanceDB")
            return True
        except Exception as e:
            logger.error(f"Failed to batch add structure patterns: {e}")
            return False
    
    def search_similar_patterns(
        self, 
        current_pattern: Dict[str, Any], 
        limit: int = 10,
        min_similarity: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Find similar historical patterns using vector similarity.
        
        Args:
            current_pattern: Current market structure pattern
            limit: Max number of results
            min_similarity: Minimum cosine similarity (0-1)
        
        Returns:
            List of similar patterns with outcome stats
        """
        try:
            table = self.db.open_table("historical_structures")
            
            # Calculate query vector
            query_vector = self._pattern_to_vector(current_pattern)
            
            # Check cache first
            cache_key = (tuple(query_vector), limit, min_similarity)
            if cache_key in self._search_cache:
                logger.debug("[DB] Cache hit for pattern search")
                return self._search_cache[cache_key]
            
            # Search similar patterns
            results = (
                table.search(query_vector)
                .limit(limit)
                .to_pandas()
            )
            
            if results.empty:
                logger.warning("No similar patterns found")
                return []
            
            # Filter by similarity threshold
            # results['_distance'] is L2 distance, convert to similarity
            results['similarity'] = 1 / (1 + results['_distance'])
            results = results[results['similarity'] >= min_similarity]
            
            # Convert to list of dicts
            similar_patterns = results.to_dict('records')
            
            # Store in cache (evict oldest if full)
            if len(self._search_cache) >= self._cache_max:
                oldest_key = next(iter(self._search_cache))
                del self._search_cache[oldest_key]
            self._search_cache[cache_key] = similar_patterns
            
            logger.debug(f"Found {len(similar_patterns)} similar patterns")
            return similar_patterns
            
        except Exception as e:
            logger.error(f"Failed to search similar patterns: {e}")
            return []
    
    def _pattern_to_vector(self, pattern: Dict[str, Any]) -> List[float]:
        """
        Convert pattern to 16-dimensional vector for similarity search.
        
        Vector components:
        [0-3]: Event type encoding (BoS, CHoCH, HH, LL)
        [4]: Direction (1=Bullish, -1=Bearish)
        [5]: EMA distance normalized
        [6-9]: Session encoding (London, NY, Asia, Sydney)
        [10]: Hour normalized (0-1)
        [11]: Timeframe (M15=1, H1=2, H4=3)
        [12-15]: Reserved for future features
        
        Returns:
            16-dimensional vector
        """
        vector = [0.0] * 16
        
        # [0-3] Event type encoding
        event_map = {"BoS": 0, "CHoCH": 1, "HH": 2, "LL": 3}
        event_idx = event_map.get(pattern.get("event_type", "BoS"), 0)
        vector[event_idx] = 1.0
        
        # [4] Direction
        vector[4] = 1.0 if pattern.get("direction") == "Bullish" else -1.0
        
        # [5] EMA distance (normalized to -1 to 1, assume max distance 50 pips)
        price = float(pattern.get("price", 0))
        ema200 = float(pattern.get("ema200", price))
        ema_distance = (price - ema200) / 50.0  # Normalize
        vector[5] = max(-1.0, min(1.0, ema_distance))
        
        # [6-9] Session encoding
        session_map = {"London": 6, "NewYork": 7, "Asia": 8, "Sydney": 9}
        session_idx = session_map.get(pattern.get("session", "London"), 6)
        vector[session_idx] = 1.0
        
        # [10] Hour normalized (0-23 → 0-1)
        try:
            timestamp = pattern.get("timestamp", datetime.now().isoformat())
            hour = datetime.fromisoformat(timestamp).hour
            vector[10] = hour / 23.0
        except:
            vector[10] = 0.5
        
        # [11] Timeframe
        timeframe_map = {"M15": 1.0, "H1": 2.0, "H4": 3.0}
        vector[11] = timeframe_map.get(pattern.get("timeframe", "M15"), 1.0) / 3.0
        
        # [12] Prior CHoCH context: was this pattern formed after a CHoCH? (1=yes, 0=no)
        vector[12] = 1.0 if pattern.get("prior_choch", False) else 0.0
        
        # [13-15] Reserved (zeros for now)
        
        return vector
    
    # ========== COLLECTION 2: Market Conditions ==========
    
    def _create_market_conditions_collection(self):
        """Create market_conditions collection"""
        
        sample_data = [{
            "id": "sample_mc_1",
            "timestamp": datetime.now().isoformat(),
            "symbol": "XAUUSD",
            "timeframe": "M15",
            "open": 2350.00,
            "high": 2351.50,
            "low": 2348.50,
            "close": 2350.80,
            "volume": 1523,
            "ema200": 2345.60,
            "atr": 8.5,
            "session": "London",
            "vector": [0.0] * 8
        }]
        
        df = pd.DataFrame(sample_data)
        self.db.create_table("market_conditions", df)
        logger.info("✅ Collection 'market_conditions' created")
    
    # ========== COLLECTION 3: Session Patterns ==========
    
    def _create_session_patterns_collection(self):
        """Create session_patterns collection"""
        
        sample_data = [{
            "id": "sample_sp_1",
            "session": "London",
            "date": datetime.now().date().isoformat(),
            "win_rate": 0.65,
            "avg_profit_pips": 25.5,
            "total_trades": 10,
            "best_event_type": "BoS",
            "vector": [0.0] * 4
        }]
        
        df = pd.DataFrame(sample_data)
        self.db.create_table("session_patterns", df)
        logger.info("✅ Collection 'session_patterns' created")
    
    # ========== COLLECTION 4: Trade Outcomes ==========
    
    def _create_trade_outcomes_collection(self):
        """Create trade_outcomes collection for ML training"""
        
        sample_data = [{
            "id": "sample_to_1",
            "ticket": 123456789,
            "timestamp": datetime.now().isoformat(),
            "symbol": "XAUUSD",
            "type": "BUY",
            "entry_price": 2350.50,
            "exit_price": 2354.50,
            "profit_pips": 40.0,
            "duration_minutes": 17,
            "outcome": "WIN",
            "structure_event": "BoS",
            "session": "London",
            "consensus_score": 0.754,
            "body_ratio": 0.75,
            "body_ratio_min": 0.40,
            "body_ratio_passed": "YES",
            "body_ratio_mode": "H4_STRETCHED_STRICT",
            "initial_sl": 2340.50,
            "initial_tp": 2370.50,
            "final_sl": 2340.50,
            "final_tp": 2370.50,
            "initial_risk_points": 3000,
            "initial_reward_points": 3000,
            "final_risk_points": 3000,
            "final_reward_points": 3000,
            "trailing_modified": "YES",
            "trailing_count": 32,
            "tp_expanded": "NO",
            "tp_expand_count": 0,
            "max_favorable_points": 2085,
            "max_adverse_points": 2997,
            "close_reason": "TAKE_PROFIT",
            "vector": [0.0] * 12
        }]
        
        df = pd.DataFrame(sample_data)
        self.db.create_table("trade_outcomes", df)
        logger.info("✅ Collection 'trade_outcomes' created")
    
    def add_trade_outcome(self, trade: Dict[str, Any]) -> bool:
        """Add completed trade to outcomes collection"""
        try:
            table = self.db.open_table("trade_outcomes")
            
            # Calculate vector
            vector = self._trade_to_vector(trade)
            
            data = {
                "id": f"trade_{trade['ticket']}",
                "ticket": int(trade["ticket"]),
                "timestamp": trade["timestamp"],
                "symbol": trade["symbol"],
                "type": trade["type"],
                "entry_price": float(trade["entry_price"]),
                "exit_price": float(trade.get("exit_price", 0)),
                "profit_pips": float(trade.get("profit_pips", 0)),
                "duration_minutes": int(trade.get("duration_minutes", 0)),
                "outcome": trade.get("outcome", "PENDING"),
                "structure_event": trade.get("structure_event", "Unknown"),
                "session": trade.get("session", "Unknown"),
                "consensus_score": float(trade.get("consensus_score", 0)),
                "body_ratio": float(trade.get("body_ratio")) if trade.get("body_ratio") is not None else None,
                "body_ratio_min": float(trade.get("body_ratio_min")) if trade.get("body_ratio_min") is not None else None,
                "body_ratio_passed": str(trade.get("body_ratio_passed", "NO")),
                "body_ratio_mode": str(trade.get("body_ratio_mode", "N/A")),
                "initial_sl": float(trade.get("initial_sl")) if trade.get("initial_sl") is not None else None,
                "initial_tp": float(trade.get("initial_tp")) if trade.get("initial_tp") is not None else None,
                "final_sl": float(trade.get("final_sl")) if trade.get("final_sl") is not None else None,
                "final_tp": float(trade.get("final_tp")) if trade.get("final_tp") is not None else None,
                "initial_risk_points": int(trade.get("initial_risk_points")) if trade.get("initial_risk_points") is not None else None,
                "initial_reward_points": int(trade.get("initial_reward_points")) if trade.get("initial_reward_points") is not None else None,
                "final_risk_points": int(trade.get("final_risk_points")) if trade.get("final_risk_points") is not None else None,
                "final_reward_points": int(trade.get("final_reward_points")) if trade.get("final_reward_points") is not None else None,
                "trailing_modified": str(trade.get("trailing_modified", "NO")),
                "trailing_count": int(trade.get("trailing_count")) if trade.get("trailing_count") is not None else None,
                "tp_expanded": str(trade.get("tp_expanded", "NO")),
                "tp_expand_count": int(trade.get("tp_expand_count")) if trade.get("tp_expand_count") is not None else None,
                "max_favorable_points": int(trade.get("max_favorable_points")) if trade.get("max_favorable_points") is not None else None,
                "max_adverse_points": int(trade.get("max_adverse_points")) if trade.get("max_adverse_points") is not None else None,
                "close_reason": str(trade.get("close_reason", "Unknown")),
                "vector": vector
            }
            
            table.add([data])
            logger.debug(f"Added trade outcome: #{trade['ticket']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add trade outcome: {e}")
            return False

    def add_trade_outcomes_batch(self, trades: List[Dict[str, Any]]) -> bool:
        """Add multiple trade outcomes in a single batch (highly optimized)"""
        if not trades:
            return True
        try:
            table = self.db.open_table("trade_outcomes")
            data_list = []
            for trade in trades:
                vector = self._trade_to_vector(trade)
                data = {
                    "id": f"trade_{trade['ticket']}",
                    "ticket": int(trade["ticket"]),
                    "timestamp": trade["timestamp"],
                    "symbol": trade["symbol"],
                    "type": trade["type"],
                    "entry_price": float(trade["entry_price"]),
                    "exit_price": float(trade.get("exit_price", 0)),
                    "profit_pips": float(trade.get("profit_pips", 0)),
                    "duration_minutes": int(trade.get("duration_minutes", 0)),
                    "outcome": trade.get("outcome", "PENDING"),
                    "structure_event": trade.get("structure_event", "Unknown"),
                    "session": trade.get("session", "Unknown"),
                    "consensus_score": float(trade.get("consensus_score", 0)),
                    "body_ratio": float(trade.get("body_ratio")) if trade.get("body_ratio") is not None else None,
                    "body_ratio_min": float(trade.get("body_ratio_min")) if trade.get("body_ratio_min") is not None else None,
                    "body_ratio_passed": str(trade.get("body_ratio_passed", "NO")),
                    "body_ratio_mode": str(trade.get("body_ratio_mode", "N/A")),
                    "initial_sl": float(trade.get("initial_sl")) if trade.get("initial_sl") is not None else None,
                    "initial_tp": float(trade.get("initial_tp")) if trade.get("initial_tp") is not None else None,
                    "final_sl": float(trade.get("final_sl")) if trade.get("final_sl") is not None else None,
                    "final_tp": float(trade.get("final_tp")) if trade.get("final_tp") is not None else None,
                    "initial_risk_points": int(trade.get("initial_risk_points")) if trade.get("initial_risk_points") is not None else None,
                    "initial_reward_points": int(trade.get("initial_reward_points")) if trade.get("initial_reward_points") is not None else None,
                    "final_risk_points": int(trade.get("final_risk_points")) if trade.get("final_risk_points") is not None else None,
                    "final_reward_points": int(trade.get("final_reward_points")) if trade.get("final_reward_points") is not None else None,
                    "trailing_modified": str(trade.get("trailing_modified", "NO")),
                    "trailing_count": int(trade.get("trailing_count")) if trade.get("trailing_count") is not None else None,
                    "tp_expanded": str(trade.get("tp_expanded", "NO")),
                    "tp_expand_count": int(trade.get("tp_expand_count")) if trade.get("tp_expand_count") is not None else None,
                    "max_favorable_points": int(trade.get("max_favorable_points")) if trade.get("max_favorable_points") is not None else None,
                    "max_adverse_points": int(trade.get("max_adverse_points")) if trade.get("max_adverse_points") is not None else None,
                    "close_reason": str(trade.get("close_reason", "Unknown")),
                    "vector": vector
                }
                data_list.append(data)
            table.add(data_list)
            logger.info(f"✅ Successfully batch added {len(data_list)} trade outcomes to LanceDB")
            return True
        except Exception as e:
            logger.error(f"Failed to batch add trade outcomes: {e}")
            return False
    
    def _trade_to_vector(self, trade: Dict[str, Any]) -> List[float]:
        """Convert trade to vector (12-dim)"""
        vector = [0.0] * 12
        
        # [0] Trade type (1=BUY, -1=SELL)
        vector[0] = 1.0 if trade.get("type") == "BUY" else -1.0
        
        # [1] Outcome (1=WIN, -1=LOSS)
        vector[1] = 1.0 if trade.get("outcome") == "WIN" else -1.0
        
        # [2] Profit pips normalized
        vector[2] = float(trade.get("profit_pips", 0)) / 100.0
        
        # [3] Duration normalized (max 120 min)
        vector[3] = min(1.0, float(trade.get("duration_minutes", 0)) / 120.0)
        
        # [4] Consensus score
        vector[4] = float(trade.get("consensus_score", 0))
        
        # [5-8] Structure event encoding
        event_map = {"BoS": 5, "CHoCH": 6, "HH": 7, "LL": 8}
        event_idx = event_map.get(trade.get("structure_event", "BoS"), 5)
        vector[event_idx] = 1.0
        
        # [9-11] Reserved
        
        return vector
    
    # ========== UTILITY METHODS ==========
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about all collections"""
        stats = {
            "collections": [],
            "total_patterns": 0
        }
        
        for table_name in self._table_names():
            try:
                table = self.db.open_table(table_name)
                count = table.count_rows()
                
                stats["collections"].append({
                    "name": table_name,
                    "count": count
                })
                stats["total_patterns"] += count
                
            except Exception as e:
                logger.error(f"Failed to get stats for {table_name}: {e}")
        
        return stats
    
    def clear_collection(self, collection_name: str) -> bool:
        """Clear all data from a collection (for testing)"""
        try:
            if collection_name in self._table_names():
                self.db.drop_table(collection_name)
                logger.info(f"Cleared collection: {collection_name}")
                
                # Recreate empty collection
                if collection_name == "historical_structures":
                    self._create_historical_structures_collection()
                elif collection_name == "market_conditions":
                    self._create_market_conditions_collection()
                elif collection_name == "session_patterns":
                    self._create_session_patterns_collection()
                elif collection_name == "trade_outcomes":
                    self._create_trade_outcomes_collection()
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to clear collection: {e}")
            return False
    
    def _create_news_sentiment_cache_collection(self):
        """Create news_sentiment_cache collection with sample data"""
        sample_data = [{
            "id": "sample_news_1",
            "timestamp": "2020-01-01 00:00:00",
            "event_type": "SAMPLE",
            "news_headlines": "[]",
            "upcoming_events": "[]",
            "vector": [0.0, 0.0]
        }]
        df = pd.DataFrame(sample_data)
        table = self.db.create_table("news_sentiment_cache", df)
        logger.info("✅ Collection 'news_sentiment_cache' created")
        return table

    def read_news_cache(self, timestamp: str) -> Optional[Dict[str, Any]]:
        """
        Read cached news sentiment data for a specific timestamp or date.
        Supports exact timestamp lookup or date-only lookup.
        """
        try:
            if "news_sentiment_cache" not in self._table_names():
                return None
            tbl = self.db.open_table("news_sentiment_cache")
            # First try exact timestamp
            results = tbl.search().where(f"timestamp = '{timestamp}'").limit(1).to_pandas()
            if not results.empty:
                row = results.iloc[0]
                import json
                return {
                    "news_headlines": json.loads(row["news_headlines"]),
                    "upcoming_events": json.loads(row["upcoming_events"]),
                    "event_type": row["event_type"],
                }
            
            # Date-only fallback: if timestamp has space, extract YYYY-MM-DD
            if " " in timestamp:
                date_str = timestamp.split(" ")[0]
                results = tbl.search().where(f"timestamp LIKE '{date_str}%'").limit(1).to_pandas()
                if not results.empty:
                    row = results.iloc[0]
                    import json
                    return {
                        "news_headlines": json.loads(row["news_headlines"]),
                        "upcoming_events": json.loads(row["upcoming_events"]),
                        "event_type": row["event_type"],
                    }
            return None
        except Exception as e:
            logger.error(f"Failed to read news cache from LanceDB: {e}")
            return None

    def write_news_cache(self, timestamp: str, event_type: str, news_headlines: List[Dict[str, Any]], upcoming_events: List[Dict[str, Any]]):
        """Write news sentiment data to cache in LanceDB"""
        try:
            import json
            tbl = self.db.open_table("news_sentiment_cache")
            # Check if it already exists to avoid duplicates
            existing = tbl.search().where(f"timestamp = '{timestamp}'").limit(1).to_pandas()
            import uuid
            row_id = str(uuid.uuid4())
            if not existing.empty:
                # Update (lancedb update via delete then add)
                tbl.delete(f"timestamp = '{timestamp}'")
                row_id = existing.iloc[0]["id"]
            
            new_data = [{
                "id": row_id,
                "timestamp": timestamp,
                "event_type": event_type,
                "news_headlines": json.dumps(news_headlines),
                "upcoming_events": json.dumps(upcoming_events),
                "vector": [0.0, 0.0]
            }]
            tbl.add(new_data)
            logger.info(f"✅ News sentiment cache written to LanceDB for {timestamp} ({event_type})")
            return True
        except Exception as e:
            logger.error(f"Failed to write news cache to LanceDB: {e}")
            return False

    def close(self):
        """Close database connection"""
        # LanceDB doesn't need explicit close
        logger.info("📊 LanceDB connection closed")


# ========== STANDALONE USAGE ==========

if __name__ == "__main__":
    # Test LanceDB setup
    logger.info("Testing LanceDB setup...")
    
    db = LanceDBManager()
    
    # Test adding a pattern
    sample_pattern = {
        "timestamp": datetime.now().isoformat(),
        "symbol": "XAUUSD",
        "timeframe": "M15",
        "event_type": "BoS",
        "direction": "Bullish",
        "price": 2350.50,
        "ema200": 2345.60,
        "session": "London",
        "outcome": "WIN",
        "profit_pips": 40.0,
        "duration_minutes": 17
    }
    
    success = db.add_structure_pattern(sample_pattern)
    logger.info(f"Add pattern: {'✅ Success' if success else '❌ Failed'}")
    
    # Test search
    similar = db.search_similar_patterns(sample_pattern, limit=5)
    logger.info(f"Found {len(similar)} similar patterns")
    
    # Get stats
    stats = db.get_stats()
    logger.info(f"Database stats: {stats}")
    
    logger.info("✅ LanceDB test complete!")
