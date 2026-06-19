"""
ML Prediction Agent - Entry Filter Model

This agent uses a trained XGBoost model (92.6% accuracy) to predict
whether a market structure signal should be taken or filtered out.

Model Details:
- Type: XGBoost Binary Classifier
- Features: 19 (market structure, H1 trend, price action, time/session)
- Accuracy: 92.6%
- F1-Score: 79.3%
- Optimal Threshold: 0.7
"""

import os
import joblib
import json
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
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
            threshold: Probability threshold for positive prediction (default: 0.7)
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
        self._load_model()
        
        # Initialize feature engineer
        self.feature_engineer = FeatureEngineer()
        
        logger.info(
            f"✅ {self.name} v{self.version} initialized | "
            f"Model: XGBoost | Threshold: {threshold} | "
            f"Accuracy: {self.metadata.get('cv_accuracy_mean', 0):.1%}"
        )
    
    def _load_model(self):
        """Load model, scaler, and metadata"""
        try:
            # Load XGBoost model
            model_file = self.model_path / "filter_model_xgb.pkl"
            self.model = joblib.load(model_file)
            logger.info(f"✅ Model loaded: {model_file}")
            
            # Load scaler
            scaler_file = self.model_path / "filter_scaler.pkl"
            self.scaler = joblib.load(scaler_file)
            logger.info(f"✅ Scaler loaded: {scaler_file}")
            
            # Load metadata
            meta_file = self.model_path / "filter_model_meta.json"
            with open(meta_file, 'r') as f:
                self.metadata = json.load(f)
            logger.info(f"✅ Metadata loaded: {meta_file}")
            
        except Exception as e:
            logger.error(f"❌ Failed to load model: {e}")
            raise RuntimeError(f"Model loading failed: {e}")
    
    def analyze(
        self,
        market_data: Dict[str, Any],
        structure_signal: str = "BUY",
        symbol: str = "XAUUSD",
        timeframe: str = "M15"
    ) -> Dict[str, Any]:
        """
        Analyze whether to take the structure signal.
        
        Args:
            market_data: Market data dict containing:
                - current_bar: Current M15 bar
                - structure_events: Recent structure events
                - h1_data: Optional H1 DataFrame
                - m15_history: Optional M15 DataFrame
            structure_signal: Signal from Market Structure Agent ("BUY" or "SELL")
            symbol: Trading symbol
            timeframe: Timeframe
        
        Returns:
            Dict with:
            - signal: "BUY", "SELL", "HOLD"
            - confidence: 0.0 to 1.0
            - reasoning: Explanation
            - probability: Model probability
            - features: Feature values used
        """
        try:
            logger.info(f"🔍 {self.name} analyzing {symbol} {timeframe}...")
            
            # Extract features
            features = self.feature_engineer.extract_features(
                current_bar=market_data.get("current_bar"),
                structure_events=market_data.get("structure_events", []),
                h1_data=market_data.get("h1_data"),
                m15_history=market_data.get("m15_history")
            )
            
            # Prepare feature array (in correct order)
            feature_names = self.metadata["feature_names"]
            feature_array = np.array([features[name] for name in feature_names]).reshape(1, -1)
            
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
            
            logger.info(
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
            "description": "Entry filter model using XGBoost (92.6% accuracy)",
            "model_info": {
                "type": "XGBoost",
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
    logger.info(f"Probability: {result['probability']:.3f}")
    logger.info(f"Reasoning: {result['reasoning']}")
    logger.info("")
    logger.info("Top Features:")
    for feat in result['top_features'][:5]:
        logger.info(f"  {feat['name']:25} = {feat['value']:.4f} (importance: {feat['importance']:.4f})")
    logger.info("=" * 70)
    logger.info("✅ MLPredictionAgent test complete!")
