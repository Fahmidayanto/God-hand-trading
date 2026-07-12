"""
ML Prediction Agent - Entry Filter Model

This agent uses a trained entry-filter model to predict
whether a market structure signal should be taken or filtered out.

Model Details:
- Type: XGBoost Binary Classifier
- Features: 19 (market structure, H1 trend, price action, time/session)
- Optimal Threshold: 0.7
"""

import os
import joblib
import json
import pandas as pd
from typing import Dict, Any, List, Optional
from datetime import datetime
from datetime import datetime
from pathlib import Path
from loguru import logger

from valuecell.models.feature_engineer import FeatureEngineer


class MLPredictionAgent:
    """
    ML Prediction Agent - Uses Entry Filter Model for signal validation.
    
    Purpose:
    - Predict whether to take or filter a market structure signal
    - Uses XGBoost model trained on historical trade data
    - Provides confidence score and feature importance explanation
    
    Decision Logic:
    - Probability >= 0.7 → BUY/SELL (based on structure signal)
    - Probability 0.5-0.7 → NEUTRAL (uncertain)
    - Probability < 0.5 → HOLD (likely losing trade)
    """
    
    def __init__(
        self,
        model_path: Optional[str] = None,
        threshold: float = 0.7
    ):
        """
        Initialize ML Prediction Agent.
        
        Args:
            model_path: Path to model directory (auto-detects if None)
            threshold: Probability threshold or R:R threshold (default: 0.7)
        """
        self.name = "MLPredictionAgent"
        self.version = "1.0.0"
        self.threshold = threshold
        
        # Auto-detect model path if not provided
        if model_path is None:
            module_dir = Path(__file__).parent.parent
            model_path = module_dir / "models" / "saved" / "filter_latest"
        else:
            model_path = Path(model_path)
        
        self.model_path = model_path
        
        # Load model components
        self.model = None
        self.scaler = None
        self.metadata = None
        self.model_type = "classification"
        self._load_model()
        
        # Initialize feature engineer
        self.feature_engineer = FeatureEngineer()
        
        # Override threshold if regression metadata defines a custom optimal_rr_threshold
        if self.model_type == "regression_v5" and self.metadata and "optimal_rr_threshold" in self.metadata:
            self.threshold = float(self.metadata["optimal_rr_threshold"])
        
        logger.info(
            f"✅ {self.name} v{self.version} initialized | "
            f"Model type: {self.model_type} | Threshold/RR Th: {self.threshold} | "
            f"Accuracy: {self.metadata.get('cv_accuracy_mean', 0.5):.1%}"
        )
    
    def _load_model(self):
        """Load model, scaler, and metadata"""
        try:
            # Load metadata
            meta_file = self.model_path / "filter_model_meta.json"
            with open(meta_file, 'r') as f:
                self.metadata = json.load(f)
            logger.info(f"✅ Metadata loaded: {meta_file}")
            
            # Check model type
            self.model_type = self.metadata.get("model_type", "classification")
            
            if self.model_type == "regression_v5":
                # Load MFE model and scaler
                self.mfe_model = joblib.load(self.model_path / "model_v5_mfe.pkl")
                self.mfe_scaler = joblib.load(self.model_path / "scaler_v5_mfe.pkl")
                
                # Load MAE model and scaler
                self.mae_model = joblib.load(self.model_path / "model_v5_mae.pkl")
                self.mae_scaler = joblib.load(self.model_path / "scaler_v5_mae.pkl")
                
                logger.info("✅ v5 Dual Regression Models and Scalers loaded successfully.")
            else:
                # Load standard classification model and scaler
                model_file = self.model_path / "filter_model_xgb.pkl"
                self.model = joblib.load(model_file)
                logger.info(f"✅ Model loaded: {model_file}")
                
                scaler_file = self.model_path / "filter_scaler.pkl"
                self.scaler = joblib.load(scaler_file)
                logger.info(f"✅ Scaler loaded: {scaler_file}")
                
        except Exception as e:
            logger.error(f"❌ Failed to load model: {e}")
            raise RuntimeError(f"Model loading failed: {e}")

    def _extract_v5_features(
        self,
        market_data: Dict[str, Any],
        entry_price: float,
        signal: str
    ) -> Dict[str, Any]:
        """Extract all engineered features required for v5 regression models."""
        import numpy as np
        
        # Base features from standard FeatureEngineer
        base_features = self.feature_engineer.extract_features(
            current_bar=market_data.get("current_bar"),
            structure_events=market_data.get("structure_events", []),
            h1_data=market_data.get("h1_data"),
            m15_history=market_data.get("m15_history")
        )
        
        m15_history = market_data.get("m15_history")
        h1_history = market_data.get("h1_data")
        h4_history = market_data.get("h4_data")
        
        # Calculate ATR on M15
        atr_14 = base_features.get("atr_14", 7.5)
        if atr_14 <= 0:
            atr_14 = 7.5
            
        atr_14_pct = (atr_14 / entry_price) * 100.0 if entry_price > 0 else 0.0
        
        # Spread calculation
        spread = market_data.get("spread", 0.15) # in price units, default 15 points
        if m15_history is not None and not m15_history.empty and "spread" in m15_history.columns:
            spread = float(m15_history.iloc[-1].get("spread", 0.15))
        spread_pct = (spread / entry_price) * 100.0 if entry_price > 0 else 0.0
        spread_to_atr_ratio = spread / atr_14
        
        # Body Ratio EA
        body_ratio_ea = base_features.get("body_ratio", 0.5)
        
        # Initial planned R:R (Defaulting to 1.0 setup if not passed)
        init_risk_points = market_data.get("init_risk_points", 300.0) # in points
        init_reward_points = market_data.get("init_reward_points", 300.0)
        init_risk_pct = (init_risk_points / entry_price) * 100.0 if entry_price > 0 else 0.0
        
        # Momentum lookbacks
        momentum_3_atr = 0.0
        momentum_5_atr = 0.0
        if m15_history is not None and not m15_history.empty and len(m15_history) > 5:
            close_3 = float(m15_history.iloc[-4].get("close", entry_price))
            momentum_3_atr = (entry_price - close_3) / atr_14
            close_5 = float(m15_history.iloc[-6].get("close", entry_price))
            momentum_5_atr = (entry_price - close_5) / atr_14
            
        # H1 and H4 context
        h1_atr_14 = atr_14 * 1.5
        if h1_history is not None and not h1_history.empty:
            high = h1_history["high"].astype(float).to_numpy()
            low = h1_history["low"].astype(float).to_numpy()
            close = h1_history["close"].astype(float).to_numpy()
            if len(close) >= 15:
                tr = np.maximum.reduce([high[1:] - low[1:], abs(high[1:] - close[:-1]), abs(low[1:] - close[:-1])])
                h1_atr_14 = float(tr[-14:].mean())
                
        h1_atr_14_pct = (h1_atr_14 / entry_price) * 100.0 if entry_price > 0 else 0.0
        
        h4_atr_14 = atr_14 * 2.0
        if h4_history is not None and not h4_history.empty:
            high = h4_history["high"].astype(float).to_numpy()
            low = h4_history["low"].astype(float).to_numpy()
            close = h4_history["close"].astype(float).to_numpy()
            if len(close) >= 15:
                tr = np.maximum.reduce([high[1:] - low[1:], abs(high[1:] - close[:-1]), abs(low[1:] - close[:-1])])
                h4_atr_14 = float(tr[-14:].mean())
                
        h4_atr_14_pct = (h4_atr_14 / entry_price) * 100.0 if entry_price > 0 else 0.0
        
        # H4 and H1 EMA distances
        h4_ema200_distance_atr = 0.0
        h4_ema200_distance_pct = 0.0
        if h4_history is not None and not h4_history.empty:
            h4_history = h4_history.copy()
            h4_history['ema200'] = h4_history['close'].ewm(span=200, adjust=False).mean()
            h4_ema = float(h4_history.iloc[-1].get("ema200", entry_price))
            h4_ema200_distance_atr = (entry_price - h4_ema) / h4_atr_14 if h4_atr_14 > 0 else 0.0
            h4_ema200_distance_pct = (h4_ema200_distance_atr * h4_atr_14 / entry_price) * 100.0 if entry_price > 0 else 0.0
            
        h1_ext_ema200_distance_atr = 0.0
        h1_ext_ema200_distance_pct = 0.0
        if h1_history is not None and not h1_history.empty:
            h1_history = h1_history.copy()
            h1_history['ema200'] = h1_history['close'].ewm(span=200, adjust=False).mean()
            h1_ema = float(h1_history.iloc[-1].get("ema200", entry_price))
            h1_ext_ema200_distance_atr = (entry_price - h1_ema) / h1_atr_14 if h1_atr_14 > 0 else 0.0
            h1_ext_ema200_distance_pct = (h1_ext_ema200_distance_atr * h1_atr_14 / entry_price) * 100.0 if entry_price > 0 else 0.0
            
        h4_vol_ratio = 1.0
        if h4_history is not None and not h4_history.empty:
            avg_h4_vol = h4_history["volume"].tail(20).mean() if "volume" in h4_history.columns and len(h4_history) >= 20 else 0.0
            h4_vol_ratio = float(h4_history.iloc[-1].get("volume", 0.0)) / avg_h4_vol if avg_h4_vol else 1.0

        # Session Dynamic Features
        session = market_data.get("session", "Other")
        current_time = market_data["current_bar"]["time"]
        if isinstance(current_time, str):
            current_time = pd.to_datetime(current_time)
            
        day_of_week = float(current_time.weekday())
        
        # Session opens/closes and priority maps
        session_priority = 0.0
        session_start = current_time.replace(hour=22, minute=0, second=0)
        session_end = current_time.replace(hour=7, minute=0, second=0)
        
        if session == "Asia":
            session_priority = 1.0
            session_start = current_time.replace(hour=0, minute=0, second=0)
            session_end = current_time.replace(hour=9, minute=0, second=0)
        elif session == "London":
            session_priority = 2.0
            session_start = current_time.replace(hour=7, minute=0, second=0)
            session_end = current_time.replace(hour=16, minute=0, second=0)
        elif session in ["NY", "NewYork"]:
            session_priority = 3.0
            session_start = current_time.replace(hour=13, minute=0, second=0)
            session_end = current_time.replace(hour=22, minute=0, second=0)
            
        minutes_from_session_open = float((current_time - session_start).total_seconds() / 60.0)
        minutes_to_session_close = float((session_end - current_time).total_seconds() / 60.0)
        
        # Calculate dynamic high/low of current session
        session_high = entry_price
        session_low = entry_price
        if m15_history is not None and not m15_history.empty:
            sess_mask = (m15_history["time"] >= session_start) & (m15_history["time"] <= current_time)
            session_bars = m15_history[sess_mask]
            if not session_bars.empty:
                session_high = float(session_bars["high"].max())
                session_low = float(session_bars["low"].min())
                
        session_range_points = (session_high - session_low) * 100.0 # gold points (1 USD = 100 points)
        price_position_session_range = (entry_price - session_low) / (session_high - session_low) if (session_high > session_low) else 0.5
        
        distance_to_session_high_atr = (session_high - entry_price) / atr_14 if atr_14 > 0 else 0.0
        distance_to_session_low_atr = (entry_price - session_low) / atr_14 if atr_14 > 0 else 0.0
        
        # DST Check
        session_is_dst_NO = 1.0 # default to NO (standard time, winter)
        # Check standard DST offset
        import time as pytime
        if pytime.localtime().tm_isdst > 0:
            session_is_dst_NO = 0.0
            
        features = {
            "h4_ema200_distance_pct": h4_ema200_distance_pct,
            "spread_to_atr_ratio": spread_to_atr_ratio,
            "body_ratio_ea": body_ratio_ea,
            "distance_to_session_high_atr": distance_to_session_high_atr,
            "h4_atr_14": h4_atr_14,
            "h1_atr_14_pct": h1_atr_14_pct,
            "h1_ext_ema200_distance_atr": h1_ext_ema200_distance_atr,
            "price_position_session_range": price_position_session_range,
            "session_is_dst_NO": session_is_dst_NO,
            "momentum_3_atr": momentum_3_atr,
            "momentum_5_atr": momentum_5_atr,
            "h4_ema200_distance_atr": h4_ema200_distance_atr,
            "h1_ext_ema200_distance_pct": h1_ext_ema200_distance_pct,
            "h4_vol_ratio": h4_vol_ratio,
            "minutes_from_session_open": minutes_from_session_open,
            "minutes_to_session_close": minutes_to_session_close,
            "spread_pct": spread_pct,
            "distance_to_session_low_atr": distance_to_session_low_atr,
            "init_risk_points": init_risk_points,
            "session_priority": session_priority,
            "day_of_week": day_of_week,
            "atr_14_pct": atr_14_pct,
        }
        
        return features

    def analyze(
        self,
        market_data: Dict[str, Any],
        structure_signal: str = "BUY",
        symbol: str = "XAUUSD",
        timeframe: str = "M15"
    ) -> Dict[str, Any]:
        """
        Analyze whether to take the structure signal.
        """
        try:
            logger.debug(f"🔍 {self.name} analyzing {symbol} {timeframe} using model type '{self.model_type}'...")
            
            entry_price = float(market_data.get("current_bar", {}).get("close", 0.0))
            if entry_price <= 0:
                raise ValueError("Entry price must be greater than zero")
                
            if self.model_type == "regression_v5":
                # Extract v5 regression features
                features = self._extract_v5_features(market_data, entry_price, structure_signal)
                
                # Make prediction for MFE
                mfe_feat_names = self.metadata["mfe_features"]
                mfe_df = pd.DataFrame(
                    [[features[name] for name in mfe_feat_names]],
                    columns=mfe_feat_names,
                )
                mfe_scaled = self.mfe_scaler.transform(mfe_df)
                predicted_mfe = float(self.mfe_model.predict(mfe_scaled)[0])
                
                # Make prediction for MAE
                mae_feat_names = self.metadata["mae_features"]
                mae_df = pd.DataFrame(
                    [[features[name] for name in mae_feat_names]],
                    columns=mae_feat_names,
                )
                mae_scaled = self.mae_scaler.transform(mae_df)
                predicted_mae = float(self.mae_model.predict(mae_scaled)[0])
                
                # Ensure predicted values are reasonable/positive
                predicted_mfe = max(0.0, predicted_mfe)
                predicted_mae = max(1.0, predicted_mae)
                
                expected_rr = predicted_mfe / predicted_mae
                
                # Consensus signal based on expected_rr vs threshold
                if expected_rr >= self.threshold:
                    signal = structure_signal
                    confidence = min(1.0, expected_rr / 2.0) # Map to confidence score
                    reasoning = f"Model predicts favorable dynamic R:R = {expected_rr:.2f} (predicted MFE: {predicted_mfe:.1f} pts, MAE: {predicted_mae:.1f} pts) which is above the threshold ({self.threshold:.2f})."
                else:
                    signal = "HOLD"
                    confidence = max(0.0, min(1.0, 1.0 - (expected_rr / self.threshold) if self.threshold > 0 else 0.5))
                    reasoning = f"Model predicts unfavorable dynamic R:R = {expected_rr:.2f} (predicted MFE: {predicted_mfe:.1f} pts, MAE: {predicted_mae:.1f} pts) which is below the threshold ({self.threshold:.2f}). Filtering setup."
                
                # Top contributing features
                top_features = [{"name": name, "value": features[name], "importance": 1.0} for name in mfe_feat_names[:5]]
                
                response = {
                    "agent": self.name,
                    "version": self.version,
                    "timestamp": datetime.now().isoformat(),
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "signal": signal,
                    "confidence": round(confidence, 3),
                    "reasoning": reasoning,
                    "predicted_mfe": round(predicted_mfe, 2),
                    "predicted_mae": round(predicted_mae, 2),
                    "expected_rr": round(expected_rr, 3),
                    "threshold": self.threshold,
                    "features": features,
                    "top_features": top_features,
                    "model_type": self.model_type,
                }
                
                logger.debug(
                    f"✅ {self.name} v5 dynamic R:R: {expected_rr:.2f} | "
                    f"MFE: {predicted_mfe:.1f} | MAE: {predicted_mae:.1f} | Signal: {signal}"
                )
                return response
                
            else:
                # Standard v4 classification model
                features = self.feature_engineer.extract_features(
                    current_bar=market_data.get("current_bar"),
                    structure_events=market_data.get("structure_events", []),
                    h1_data=market_data.get("h1_data"),
                    m15_history=market_data.get("m15_history")
                )
                
                # Prepare feature array (in correct order)
                feature_names = self.metadata["feature_names"]
                feature_array = pd.DataFrame(
                    [[features[name] for name in feature_names]],
                    columns=feature_names,
                )
                
                # Scale features
                feature_scaled = self.scaler.transform(feature_array)
                
                # Predict probability
                probability = self.model.predict_proba(feature_scaled)[0][1]  # Prob of class 1 (WIN)
                
                # Generate signal based on probability
                signal_result = self._generate_signal(
                    probability=probability,
                    structure_signal=structure_signal,
                    features=features
                )
                
                # Get top features (for explanation)
                top_features = self._get_top_features(features)
                
                # Build response
                response = {
                    "agent": self.name,
                    "version": self.version,
                    "timestamp": datetime.now().isoformat(),
                    "symbol": symbol,
                    "timeframe": timeframe,
                    **signal_result,
                    "probability": round(probability, 3),
                    "threshold": self.threshold,
                    "features": features,
                    "top_features": top_features,
                    "model_accuracy": self.metadata.get("cv_accuracy_mean", 0)
                }
                
                logger.debug(
                    f"✅ {self.name} signal: {response['signal']} | "
                    f"Confidence: {response['confidence']:.2f} | "
                    f"Probability: {probability:.3f}"
                )
                
                return response
            
        except Exception as e:
            logger.error(f"❌ {self.name} analysis failed: {e}")
            return self._error_response(str(e))
    

    def _generate_signal(
        self,
        probability: float,
        structure_signal: str,
        features: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Generate trading signal based on model probability.
        
        Decision Logic:
        - probability >= threshold → Follow structure signal (BUY/SELL)
        - 0.5 <= probability < threshold → NEUTRAL (uncertain)
        - probability < 0.5 → HOLD (filter out)
        """
        
        # Convert probability to confidence
        if probability >= self.threshold:
            signal = structure_signal  # Follow structure agent
            confidence = probability
            reasoning_parts = [
                f"Model predicts HIGH WIN probability: {probability:.1%}.",
                f"Supports {structure_signal} signal."
            ]
        
        elif probability >= 0.5:
            signal = "NEUTRAL"
            confidence = 0.5
            reasoning_parts = [
                f"Model shows MODERATE probability: {probability:.1%}.",
                f"Below threshold ({self.threshold:.1%}), suggesting caution."
            ]
        
        else:
            signal = "HOLD"
            confidence = 1.0 - probability  # Confidence in filtering
            reasoning_parts = [
                f"Model predicts LOW WIN probability: {probability:.1%}.",
                f"Filtering {structure_signal} signal to avoid likely loss."
            ]
        
        # Add top feature insights
        top_3 = self._get_top_contributing_features(features)
        if top_3:
            reasoning_parts.append(
                f"Key factors: {', '.join(f'{k}={v:.2f}' for k, v in top_3[:3])}"
            )
        
        reasoning = " ".join(reasoning_parts)
        
        return {
            "signal": signal,
            "confidence": round(confidence, 3),
            "reasoning": reasoning
        }
    
    def _get_top_features(self, features: Dict[str, float], top_n: int = 5) -> List[Dict[str, Any]]:
        """Get top N most important features with their values"""
        feature_importance = self.metadata.get("feature_importance_shap", {})
        
        # Sort by importance
        sorted_features = sorted(
            feature_importance.items(),
            key=lambda x: x[1],
            reverse=True
        )[:top_n]
        
        return [
            {
                "name": name,
                "value": features.get(name, 0.0),
                "importance": importance
            }
            for name, importance in sorted_features
        ]
    
    def _get_top_contributing_features(
        self,
        features: Dict[str, float],
        top_n: int = 3
    ) -> List[tuple]:
        """Get top contributing features (importance * value)"""
        feature_importance = self.metadata.get("feature_importance_shap", {})
        
        # Calculate contribution (importance * abs(value))
        contributions = []
        for name, value in features.items():
            importance = feature_importance.get(name, 0.0)
            contribution = importance * abs(value)
            contributions.append((name, value, contribution))
        
        # Sort by contribution
        contributions.sort(key=lambda x: x[2], reverse=True)
        
        return [(name, value) for name, value, _ in contributions[:top_n]]
    
    def _error_response(self, error: str) -> Dict[str, Any]:
        """Generate error response"""
        return {
            "agent": self.name,
            "version": self.version,
            "timestamp": datetime.now().isoformat(),
            "signal": "HOLD",
            "confidence": 0.0,
            "reasoning": f"Analysis error: {error}",
            "probability": 0.0,
            "features": {},
            "top_features": [],
            "error": error
        }
    
    def get_info(self) -> Dict[str, Any]:
        """Get agent information"""
        return {
            "name": self.name,
            "version": self.version,
            "type": "ml_prediction",
            "description": (
                "Entry filter model using "
                f"{self.metadata.get('model_type', 'ML classifier')}"
            ),
            "model_info": {
                "type": self.metadata.get("model_type", "ML classifier"),
                "n_features": self.metadata.get("n_features", 0),
                "accuracy": self.metadata.get("cv_accuracy_mean", 0),
                "f1_score": self.metadata.get("cv_f1_mean", 0),
                "threshold": self.threshold
            },
            "capabilities": [
                "Binary classification (WIN/LOSS prediction)",
                "19 feature engineering",
                "Probability estimation",
                "Feature importance explanation",
                "Signal filtering"
            ]
        }


# ========== STANDALONE TESTING ==========


if __name__ == "__main__":
    logger.info("Testing MLPredictionAgent...")
    
    # Initialize agent
    agent = MLPredictionAgent()
    
    # Get agent info
    info = agent.get_info()
    logger.info(f"Agent info: {info}")
    
    # Sample market data
    from datetime import timedelta
    
    market_data = {
        "current_bar": {
            "time": datetime.now(),
            "open": 2350.0,
            "high": 2352.5,
            "low": 2348.0,
            "close": 2351.0,
            "volume": 1500
        },
        "structure_events": [
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
    }
    
    # Analyze
    result = agent.analyze(
        market_data=market_data,
        structure_signal="BUY",
        symbol="XAUUSD",
        timeframe="M15"
    )
    
    # Print results
    logger.info("=" * 70)
    logger.info(f"Signal: {result['signal']}")
    logger.info(f"Confidence: {result['confidence']:.3f}")
    if "probability" in result:
        logger.info(f"Probability: {result['probability']:.3f}")
    if "expected_rr" in result:
        logger.info(f"Expected RR: {result['expected_rr']:.2f} (MFE: {result['predicted_mfe']:.1f}, MAE: {result['predicted_mae']:.1f})")
    logger.info(f"Reasoning: {result['reasoning']}")
    logger.info("")
    logger.info("Top Features:")
    for feat in result['top_features'][:5]:
        logger.info(f"  {feat['name']:25} = {feat['value']:.4f} (importance: {feat['importance']:.4f})")
    logger.info("=" * 70)
    logger.info("✅ MLPredictionAgent test complete!")
