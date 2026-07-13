"""
Feature Engineer - Transform market data into model-ready features

This module extracts and engineers the 19 features required by the Entry Filter Model:
1. Market structure features (BoS/CHoCH age, direction, alignment)
2. H1 trend indicators (EMA200, ATR, volume ratio)
3. Price action features (body ratio, volume ratio, ATR)
4. Time/session features (hour, day, session, London/NY/overlap)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from loguru import logger


class FeatureEngineer:
    """
    Transform raw market data into model-ready features.
    
    Required Features (19):
    - Market Structure: last_bos_age_hours, last_choch_age_hours, choch_to_bos_hours,
                       last_bos_direction, last_choch_direction, bos_choch_aligned
    - H1 Trend: h1_trend_aligned, h1_above_ema200, h1_atr_14, h1_vol_ratio
    - Price Action: body_ratio, vol_ratio, atr_14
    - Time/Session: hour_of_day, day_of_week, session_priority, is_london, is_ny, is_overlap
    """
    
    def __init__(self):
        """Initialize Feature Engineer"""
        self.feature_names = [
            "last_bos_age_hours",
            "last_choch_age_hours",
            "choch_to_bos_hours",
            "last_bos_direction",
            "last_choch_direction",
            "bos_choch_aligned",
            "h1_trend_aligned",
            "h1_above_ema200",
            "h1_atr_14",
            "h1_vol_ratio",
            "body_ratio",
            "vol_ratio",
            "atr_14",
            "hour_of_day",
            "day_of_week",
            "session_priority",
            "is_london",
            "is_ny",
            "is_overlap",
            "distance_to_last_ll_pips",
            "distance_to_last_hh_pips",
        ]
        
        logger.info(f"✅ FeatureEngineer initialized | Features: {len(self.feature_names)}")
    
    def extract_features(
        self,
        current_bar: Dict[str, Any],
        structure_events: List[Dict[str, Any]],
        h1_data: Optional[pd.DataFrame] = None,
        m15_history: Optional[pd.DataFrame] = None
    ) -> Dict[str, float]:
        """
        Extract all 19 features from market data.
        
        Args:
            current_bar: Current M15 bar data
                {
                    "time": datetime,
                    "open": float,
                    "high": float,
                    "low": float,
                    "close": float,
                    "volume": int
                }
            structure_events: Recent structure events (HH/LL/CHoCH/BoS)
                [
                    {
                        "type": "BOS_BULLISH" | "CHOCH_BEARISH" | etc.,
                        "price": float,
                        "time": datetime
                    },
                    ...
                ]
            h1_data: Optional H1 timeframe data (for trend indicators)
            m15_history: Optional M15 history (for ATR calculation)
        
        Returns:
            Dict with 19 features
        """
        try:
            features = {}
            current_time = current_bar["time"]
            
            # === 1. MARKET STRUCTURE FEATURES ===
            structure_features = self._extract_structure_features(
                current_time, structure_events
            )
            features.update(structure_features)
            
            # === 2. H1 TREND FEATURES ===
            if h1_data is not None and len(h1_data) > 0:
                h1_features = self._extract_h1_features(h1_data)
                features.update(h1_features)
            else:
                # Default values if H1 data not available
                features.update({
                    "h1_trend_aligned": 0,
                    "h1_above_ema200": 0,
                    "h1_atr_14": 0.0,
                    "h1_vol_ratio": 1.0
                })
            
            # === 3. PRICE ACTION FEATURES ===
            price_features = self._extract_price_features(
                current_bar, m15_history
            )
            features.update(price_features)
            
            # === 4. TIME/SESSION FEATURES ===
            time_features = self._extract_time_features(current_time)
            features.update(time_features)

            # === 5. SWING DISTANCE FEATURES ===
            entry_price = current_bar.get("close", current_bar.get("open", 0.0))
            swing_features = self._extract_swing_distances(entry_price, structure_events)
            features.update(swing_features)

            # Validate all features present
            missing = set(self.feature_names) - set(features.keys())
            if missing:
                logger.warning(f"Missing features: {missing}")
                # Fill missing with defaults
                for feat in missing:
                    features[feat] = 0.0
            
            return features
            
        except Exception as e:
            logger.error(f"Feature extraction failed: {e}")
            # Return default features
            return {feat: 0.0 for feat in self.feature_names}
    
    def _extract_structure_features(
        self,
        current_time: datetime,
        events: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Extract market structure features (6 features)"""
        
        # Find last BoS and CHoCH events
        last_bos = None
        last_choch = None
        
        for event in reversed(events):
            event_type = event.get("type", "")
            
            if last_bos is None and "BOS" in event_type:
                last_bos = event
            
            if last_choch is None and "CHOCH" in event_type:
                last_choch = event
            
            if last_bos and last_choch:
                break
        
        # Calculate ages (hours since event)
        if last_bos:
            bos_age = (current_time - last_bos["time"]).total_seconds() / 3600
            bos_direction = 1 if "BULLISH" in last_bos["type"] else -1
        else:
            bos_age = 999.0  # No recent BoS
            bos_direction = 0
        
        if last_choch:
            choch_age = (current_time - last_choch["time"]).total_seconds() / 3600
            choch_direction = 1 if "BULLISH" in last_choch["type"] else -1
        else:
            choch_age = 999.0
            choch_direction = 0
        
        # CHoCH to BoS time
        if last_bos and last_choch:
            choch_to_bos = abs(bos_age - choch_age)
        else:
            choch_to_bos = 0.0
        
        # Alignment (both same direction)
        bos_choch_aligned = 1 if (bos_direction == choch_direction and bos_direction != 0) else 0
        
        return {
            "last_bos_age_hours": bos_age,
            "last_choch_age_hours": choch_age,
            "choch_to_bos_hours": choch_to_bos,
            "last_bos_direction": bos_direction,
            "last_choch_direction": choch_direction,
            "bos_choch_aligned": bos_choch_aligned
        }
    
    def _extract_h1_features(self, h1_data: pd.DataFrame) -> Dict[str, float]:
        """Extract H1 trend features (4 features)"""
        
        try:
            # Get last H1 bar
            last_h1 = h1_data.iloc[-1]
            
            # H1 above EMA200
            if "ema200" in h1_data.columns:
                h1_above_ema200 = 1 if last_h1["close"] > last_h1["ema200"] else 0
            else:
                h1_above_ema200 = 0
            
            # H1 ATR (14 periods)
            if len(h1_data) >= 14:
                h1_atr = self._calculate_atr(h1_data, period=14)
            else:
                h1_atr = 0.0
            
            # H1 volume ratio (current / average)
            if len(h1_data) >= 20 and "volume" in h1_data.columns:
                avg_vol = h1_data["volume"].tail(20).mean()
                h1_vol_ratio = last_h1["volume"] / avg_vol if avg_vol > 0 else 1.0
            else:
                h1_vol_ratio = 1.0
            
            # H1 trend aligned (simplified: price above EMA200)
            h1_trend_aligned = h1_above_ema200
            
            return {
                "h1_trend_aligned": h1_trend_aligned,
                "h1_above_ema200": h1_above_ema200,
                "h1_atr_14": h1_atr,
                "h1_vol_ratio": h1_vol_ratio
            }
            
        except Exception as e:
            logger.error(f"H1 feature extraction failed: {e}")
            return {
                "h1_trend_aligned": 0,
                "h1_above_ema200": 0,
                "h1_atr_14": 0.0,
                "h1_vol_ratio": 1.0
            }
    
    def _extract_price_features(
        self,
        current_bar: Dict[str, Any],
        m15_history: Optional[pd.DataFrame]
    ) -> Dict[str, float]:
        """Extract price action features (3 features)"""
        
        open_price = current_bar["open"]
        close_price = current_bar["close"]
        high_price = current_bar["high"]
        low_price = current_bar["low"]
        volume = current_bar.get("volume", 0)
        
        # Body ratio: abs(close - open) / (high - low)
        range_size = high_price - low_price
        body_size = abs(close_price - open_price)
        body_ratio = body_size / range_size if range_size > 0 else 0.0
        
        # Volume ratio: current / average
        if m15_history is not None and len(m15_history) >= 20 and "volume" in m15_history.columns:
            avg_vol = m15_history["volume"].tail(20).mean()
            vol_ratio = volume / avg_vol if avg_vol > 0 else 1.0
        else:
            vol_ratio = 1.0
        
        # ATR (14 periods)
        if m15_history is not None and len(m15_history) >= 14:
            atr_14 = self._calculate_atr(m15_history, period=14)
        else:
            atr_14 = 0.0
        
        return {
            "body_ratio": body_ratio,
            "vol_ratio": vol_ratio,
            "atr_14": atr_14
        }
    
    def _extract_time_features(self, current_time: datetime) -> Dict[str, float]:
        """Extract time and session features (6 features)"""
        
        hour = current_time.hour
        day = current_time.weekday()  # 0=Monday, 6=Sunday
        
        # Session detection (UTC times)
        # London: 08:00-17:00 UTC
        # New York: 13:00-22:00 UTC
        # Overlap: 13:00-17:00 UTC
        
        is_london = 1 if 8 <= hour < 17 else 0
        is_ny = 1 if 13 <= hour < 22 else 0
        is_overlap = 1 if 13 <= hour < 17 else 0
        
        # Session priority (London=3, Overlap=2, NY=1, Other=0)
        if is_overlap:
            session_priority = 2
        elif is_london:
            session_priority = 3
        elif is_ny:
            session_priority = 1
        else:
            session_priority = 0
        
        return {
            "hour_of_day": hour,
            "day_of_week": day,
            "session_priority": session_priority,
            "is_london": is_london,
            "is_ny": is_ny,
            "is_overlap": is_overlap
        }
    
    def _extract_swing_distances(
        self,
        entry_price: float,
        events: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Extract distance (in pips) from entry to last LL and last HH swing levels.

        For XAUUSD: 1 pip = 0.1 USD. So distance_pips = (price_diff / 0.1).
        Defaults to 0.0 when no matching swing is found in event history.
        """
        last_ll_price = None
        last_hh_price = None

        for event in reversed(events):
            event_type = str(event.get("type", "")).upper()
            price = event.get("price")
            if price is None:
                continue
            if last_ll_price is None and "LL" in event_type:
                last_ll_price = float(price)
            if last_hh_price is None and "HH" in event_type:
                last_hh_price = float(price)
            if last_ll_price is not None and last_hh_price is not None:
                break

        # Distance = absolute price diff / pip_size (0.1 for XAUUSD)
        pip_size = 0.1
        dist_ll = (entry_price - last_ll_price) / pip_size if last_ll_price is not None else 0.0
        dist_hh = (last_hh_price - entry_price) / pip_size if last_hh_price is not None else 0.0

        return {
            "distance_to_last_ll_pips": dist_ll,
            "distance_to_last_hh_pips": dist_hh,
        }

    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average True Range"""
        try:
            if len(df) < period:
                return 0.0
            
            # True Range = max(high-low, abs(high-prev_close), abs(low-prev_close))
            high = df["high"].values
            low = df["low"].values
            close = df["close"].values
            
            tr_list = []
            for i in range(1, len(df)):
                tr = max(
                    high[i] - low[i],
                    abs(high[i] - close[i-1]),
                    abs(low[i] - close[i-1])
                )
                tr_list.append(tr)
            
            # ATR = average of last 'period' TRs
            if len(tr_list) >= period:
                atr = np.mean(tr_list[-period:])
                return float(atr)
            else:
                return 0.0
                
        except Exception as e:
            logger.error(f"ATR calculation failed: {e}")
            return 0.0
    
    def get_feature_names(self) -> List[str]:
        """Get list of feature names"""
        return self.feature_names.copy()


# ========== STANDALONE TESTING ==========

if __name__ == "__main__":
    logger.info("Testing FeatureEngineer...")
    
    # Initialize
    engineer = FeatureEngineer()
    
    # Sample data
    current_bar = {
        "time": datetime.now(),
        "open": 2350.0,
        "high": 2352.5,
        "low": 2348.0,
        "close": 2351.0,
        "volume": 1500
    }
    
    structure_events = [
        {
            "type": "CHOCH_BULLISH",
            "price": 2345.0,
            "time": datetime.now() - timedelta(hours=2)
        },
        {
            "type": "BOS_BULLISH",
            "price": 2350.0,
            "time": datetime.now() - timedelta(hours=0.5)
        }
    ]
    
    # Extract features
    features = engineer.extract_features(
        current_bar=current_bar,
        structure_events=structure_events
    )
    
    # Print results
    logger.info("=" * 60)
    logger.info("Extracted Features:")
    for feat_name in engineer.feature_names:
        logger.info(f"  {feat_name:25} = {features.get(feat_name, 0.0):.4f}")
    logger.info("=" * 60)
    logger.info(f"Total features: {len(features)}")
    logger.info("✅ FeatureEngineer test complete!")
