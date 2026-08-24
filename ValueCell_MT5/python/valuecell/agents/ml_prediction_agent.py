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
        is_regression = self.model_type in ("regression_v5", "regression_v5_unconstrained") or self.model_type.startswith("regression_v8")
        if is_regression and self.metadata and "optimal_rr_threshold" in self.metadata:
            self.threshold = float(self.metadata["optimal_rr_threshold"])

        # ML gate config (anti-overfit, dipilih dari struktur walk-forward, bukan grid search):
        # - RR_GATE_THRESHOLD=1.0: hanya veto trade dengan expected RR ekstrem buruk.
        #   Grid OOS menunjukkan 0.8-1.2 semua profit; 1.0 = tengah zona stabil.
        # - GATE_MIN_TRAIN_SAMPLES=500: gate OFF saat fold dilatih < 500 sampel
        #   (fold awal 2020-2021 terbukti salah pilah karena data tipis).
        self.rr_gate_threshold = 1.0
        self.gate_min_train_samples = int(
            (self.metadata or {}).get("gate_min_train_samples", 500)
        )
        # Jumlah sampel training fold produksi aktif (dari metadata jika ada).
        self.production_train_samples = int(
            (self.metadata or {}).get("production_train_samples", 10**9)
        )
        
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
            
            # Targets are normalized in v8+; predictions must be denormalized to points.
            # Price-Ratio Dynamic Scaling (EA Dev_Bot_v11_Gold: BaseReferencePrice=4500):
            # training target = target_points / (entry_price / 4500), so inference
            # multiplies back by entry_price / 4500.
            self.norm_target = self.model_type.startswith("regression_v8")
            self.base_reference_price = float(
                self.metadata.get("base_reference_price", 4500.0)
            )

            if self.model_type in ("regression_v5", "regression_v5_unconstrained"):
                # Load MFE model and scaler
                self.mfe_model = joblib.load(self.model_path / "model_v5_mfe.pkl")
                self.mfe_scaler = joblib.load(self.model_path / "scaler_v5_mfe.pkl")

                # Load MAE model and scaler
                self.mae_model = joblib.load(self.model_path / "model_v5_mae.pkl")
                self.mae_scaler = joblib.load(self.model_path / "scaler_v5_mae.pkl")

                logger.info("✅ v5 Dual Regression Models and Scalers loaded successfully.")
            elif self.model_type.startswith("regression_v8"):
                # v8: walk-forward fold model, trained with price-ratio normalized
                # targets (fixes extrapolation failure across gold's price regime shift).
                fold = self.metadata.get("production_fold", "2026")
                self.mfe_model = joblib.load(self.model_path / f"model_v8_fold{fold}_mfe.pkl")
                self.mfe_scaler = joblib.load(self.model_path / f"scaler_v8_fold{fold}_mfe.pkl")

                self.mae_model = joblib.load(self.model_path / f"model_v8_fold{fold}_mae.pkl")
                self.mae_scaler = joblib.load(self.model_path / f"scaler_v8_fold{fold}_mae.pkl")

                logger.info(f"✅ v8 Dual Regression Models (fold{fold}, price-ratio normalized) and Scalers loaded successfully.")
            else:
                # Load standard classification model and scaler
                model_file = self.model_path / "filter_model_xgb.pkl"
                self.model = joblib.load(model_file)
                logger.info(f"✅ Model loaded: {model_file}")
                
                scaler_file = self.model_path / "filter_scaler.pkl"
                self.scaler = joblib.load(scaler_file)
                logger.info(f"✅ Scaler loaded: {scaler_file}")

            if self.model_type.startswith("regression_v"):
                self.mfe_feature_names = self._artifact_feature_names("mfe")
                self.mae_feature_names = self._artifact_feature_names("mae")
                
        except Exception as e:
            logger.error(f"❌ Failed to load model: {e}")
            raise RuntimeError(f"Model loading failed: {e}")

    def _artifact_feature_names(self, target: str) -> List[str]:
        """Use fitted artifacts as feature contract; metadata is fallback only."""
        model_names = list(getattr(getattr(self, f"{target}_model"), "feature_names_in_", []))
        scaler_names = list(getattr(getattr(self, f"{target}_scaler"), "feature_names_in_", []))
        metadata_names = list(self.metadata.get(f"{target}_features", []))

        if model_names and scaler_names and model_names != scaler_names:
            raise ValueError(f"{target.upper()} model/scaler feature contracts do not match")

        artifact_names = model_names or scaler_names
        if artifact_names and metadata_names != artifact_names:
            logger.warning(
                f"⚠️ {target.upper()} metadata feature list is stale; "
                "using fitted artifact feature_names_in_"
            )
        return artifact_names or metadata_names

    def _extract_v5_features(
        self,
        market_data: Dict[str, Any],
        entry_price: float,
        signal: str
    ) -> Dict[str, Any]:
        """Extract all engineered features required for v5 regression models."""
        import numpy as np

        def numeric_or_default(value: Any, default: float) -> float:
            """Coerce nullable simulation inputs to a finite model-safe float."""
            try:
                number = float(value)
            except (TypeError, ValueError):
                return default
            return number if np.isfinite(number) else default
        
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
        atr_14 = numeric_or_default(base_features.get("atr_14"), 7.5)
        if atr_14 <= 0:
            atr_14 = 7.5

        atr_14_pct = (atr_14 / entry_price) * 100.0 if entry_price > 0 else 0.0

        # Spread calculation
        spread = numeric_or_default(market_data.get("spread"), 0.15) # in price units, default 15 points
        if m15_history is not None and not m15_history.empty and "spread" in m15_history.columns:
            spread = numeric_or_default(m15_history.iloc[-1].get("spread"), spread)
        spread_pct = (spread / entry_price) * 100.0 if entry_price > 0 else 0.0
        spread_to_atr_ratio = spread / atr_14
        
        # Body Ratio EA
        body_ratio_ea = base_features.get("body_ratio", 0.5)
        
        # Initial planned R:R (Defaulting to 1.0 setup if not passed)
        init_risk_points = numeric_or_default(market_data.get("init_risk_points"), 300.0) # in points
        init_reward_points = numeric_or_default(market_data.get("init_reward_points"), 300.0)
        init_risk_pct = (init_risk_points / entry_price) * 100.0 if entry_price > 0 else 0.0
        
        # Momentum lookbacks
        momentum_3_atr = 0.0
        momentum_5_atr = 0.0
        momentum_10_atr = 0.0
        if m15_history is not None and not m15_history.empty and len(m15_history) > 5:
            close_3 = float(m15_history.iloc[-4].get("close", entry_price))
            momentum_3_atr = (entry_price - close_3) / atr_14
            close_5 = float(m15_history.iloc[-6].get("close", entry_price))
            momentum_5_atr = (entry_price - close_5) / atr_14
        if m15_history is not None and not m15_history.empty and len(m15_history) > 10:
            close_10 = float(m15_history.iloc[-11].get("close", entry_price))
            momentum_10_atr = (entry_price - close_10) / atr_14
            
        # H1 and H4 context -- ATR-14 history is capped to "since Jan 1 of the
        # entry's own year" to match the offline training dataset, which is built
        # from per-year CSV files and so never has prior-year bars to draw on for
        # early-January entries (see train_ml_prediction_v5_unconstrained.py's
        # per-year file loop). Below ~15 bars into the year this yields the same
        # 0.0 the training data has; once >=15 bars have accumulated, the ATR-14
        # window is entirely within the current year anyway, so this cap is a
        # no-op and matches an uncapped calculation exactly.
        entry_time = market_data.get("current_bar", {}).get("time")
        year_start = pd.Timestamp(entry_time).replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0) if entry_time is not None else None

        h1_atr_14 = 0.0
        if h1_history is not None and not h1_history.empty:
            h1_hist_capped = h1_history[h1_history["time"] >= year_start] if year_start is not None and "time" in h1_history.columns else h1_history
            high = h1_hist_capped["high"].astype(float).to_numpy()
            low = h1_hist_capped["low"].astype(float).to_numpy()
            close = h1_hist_capped["close"].astype(float).to_numpy()
            if len(close) >= 15:
                tr = np.maximum.reduce([high[1:] - low[1:], abs(high[1:] - close[:-1]), abs(low[1:] - close[:-1])])
                h1_atr_14 = float(tr[-14:].mean())

        h1_atr_14_pct = (h1_atr_14 / entry_price) * 100.0 if entry_price > 0 else 0.0

        h4_atr_14 = 0.0
        if h4_history is not None and not h4_history.empty:
            h4_hist_capped = h4_history[h4_history["time"] >= year_start] if year_start is not None and "time" in h4_history.columns else h4_history
            high = h4_hist_capped["high"].astype(float).to_numpy()
            low = h4_hist_capped["low"].astype(float).to_numpy()
            close = h4_hist_capped["close"].astype(float).to_numpy()
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
            
        # ponytail: calculate M15 EMA 200 features as requested
        m15_ema200_distance_atr = 0.0
        m15_ema200_distance_pct = 0.0
        if m15_history is not None and not m15_history.empty:
            m15_history = m15_history.copy()
            m15_history['ema200'] = m15_history['close'].ewm(span=200, adjust=False).mean()
            m15_ema = float(m15_history.iloc[-1].get("ema200", entry_price))
            m15_ema200_distance_atr = (entry_price - m15_ema) / atr_14 if atr_14 > 0 else 0.0
            m15_ema200_distance_pct = (m15_ema200_distance_atr * atr_14 / entry_price) * 100.0 if entry_price > 0 else 0.0

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
        
        session_zone = market_data.get("session_zone")
        if session_zone:
            session = session_zone.get("session", "Other")
            session_is_dst = session_zone.get("is_dst", "NO")
            
            session_start = session_zone.get("start_time")
            session_end = session_zone.get("end_time")
            if isinstance(session_start, str):
                session_start = pd.to_datetime(session_start)
            if isinstance(session_end, str):
                session_end = pd.to_datetime(session_end)
                
            if session_start and session_start.tzinfo is not None:
                session_start = session_start.replace(tzinfo=None)
            if session_end and session_end.tzinfo is not None:
                session_end = session_end.replace(tzinfo=None)
            current_time_naive = current_time.replace(tzinfo=None) if current_time.tzinfo is not None else current_time
            
            session_range_points = float(session_zone.get("range_points", 0.0))
            session_high = float(session_zone.get("high_price", entry_price))
            session_low = float(session_zone.get("low_price", entry_price))
            
            minutes_from_session_open = float((current_time_naive - session_start).total_seconds() / 60.0) if session_start else 0.0
            minutes_to_session_close = float((session_end - current_time_naive).total_seconds() / 60.0) if session_end else 0.0
            price_position_session_range = (entry_price - session_low) / (session_high - session_low) if (session_high > session_low) else 0.5
            distance_to_session_high_atr = (session_high - entry_price) / atr_14 if atr_14 > 0 else 0.0
            distance_to_session_low_atr = (entry_price - session_low) / atr_14 if atr_14 > 0 else 0.0
            
            session_priority = 0.0
            if session == "Asia":
                session_priority = 1.0
            elif session == "London":
                session_priority = 2.0
            elif session in ["NY", "NewYork", "NewYork_London_Overlap", "London_NewYork_Overlap", "London_NY_Overlap"]:
                session_priority = 3.0
                
            session_is_dst_NO = 1.0 if session_is_dst == "NO" else 0.0
        else:
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
            
            # DST Check -- must be based on the event's own historical date
            # (current_time), not the server's real-world clock. Approximates
            # Northern Hemisphere DST (~April-October) to match the IsDST field
            # recorded in the historical SessionZone_XAUUSD_*.csv data.
            session_is_dst_NO = 0.0 if 4 <= current_time.month <= 10 else 1.0
            
        # Swing distance features (structural SL/TP context)
        structure_events = market_data.get("structure_events", [])
        pip_size = 0.1  # XAUUSD: 1 pip = 0.1 USD
        last_ll_price = None
        last_hh_price = None
        for evt in reversed(structure_events):
            etype = str(evt.get("type", "")).upper()
            eprice = evt.get("price")
            if eprice is None:
                continue
            if last_ll_price is None and "LL" in etype:
                last_ll_price = float(eprice)
            if last_hh_price is None and "HH" in etype:
                last_hh_price = float(eprice)
            if last_ll_price is not None and last_hh_price is not None:
                break
        distance_to_last_ll_pips = (entry_price - last_ll_price) / pip_size if last_ll_price is not None else 0.0
        distance_to_last_hh_pips = (last_hh_price - entry_price) / pip_size if last_hh_price is not None else 0.0

        # additional normalized features for training compatibility
        h1_ext_atr_14_pct = h1_atr_14_pct
        h4_aligned = 1.0 if (signal == "BUY" and h4_ema200_distance_atr > 0) or (signal == "SELL" and h4_ema200_distance_atr < 0) else 0.0
        h1_aligned = 1.0 if (signal == "BUY" and h1_ext_ema200_distance_atr > 0) or (signal == "SELL" and h1_ext_ema200_distance_atr < 0) else 0.0
        double_trend_aligned = 1.0 if (h4_aligned == 1.0 and h1_aligned == 1.0) else 0.0
        session_name = session
        session_is_dst = "NO" if session_is_dst_NO == 1.0 else "YES"

        # ponytail: merge base_features to ensure is_overlap and other model-required fields are present
        features = {
            **base_features,
            "h4_ema200_distance_pct": h4_ema200_distance_pct,
            "spread_to_atr_ratio": spread_to_atr_ratio,
            "spread": spread,
            "body_ratio_ea": body_ratio_ea,
            "distance_to_session_high_atr": distance_to_session_high_atr,
            "h4_atr_14": h4_atr_14,
            "h1_atr_14": h1_atr_14,
            "h4_atr_14_pct": h4_atr_14_pct,
            "h1_atr_14_pct": h1_atr_14_pct,
            "h1_ext_ema200_distance_atr": h1_ext_ema200_distance_atr,
            "price_position_session_range": price_position_session_range,
            "session_range_points": session_range_points,
            "session_is_dst_NO": session_is_dst_NO,
            "momentum_3_atr": momentum_3_atr,
            "momentum_5_atr": momentum_5_atr,
            "momentum_10_atr": momentum_10_atr,
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
            "distance_to_last_ll_pips": distance_to_last_ll_pips,
            "distance_to_last_hh_pips": distance_to_last_hh_pips,
            "m15_ema200_distance_atr": m15_ema200_distance_atr,
            "m15_ema200_distance_pct": m15_ema200_distance_pct,
            "h1_ext_atr_14_pct": h1_ext_atr_14_pct,
            "double_trend_aligned": double_trend_aligned,
            "init_risk_pct": init_risk_pct,
            "session_name": session_name,
            "session_is_dst": session_is_dst,
        }
        
        return features

    def _resolve_feature_value(self, features: Dict[str, Any], name: str) -> float:
        """Resolve a model feature value, deriving one-hot dummy columns
        (e.g. 'session_name_Asia') from their categorical source field when
        the exact column isn't already present in `features`."""
        if name in features:
            return features[name]

        for cat_col in ("session_name", "session_is_dst", "session_zone_name", "session_zone_is_dst", "signal"):
            prefix = f"{cat_col}_"
            if name.startswith(prefix):
                category_value = features.get(cat_col)
                return 1.0 if str(category_value) == name[len(prefix):] else 0.0

        logger.warning(f"⚠️ {self.name} feature '{name}' not found and not a recognized dummy; defaulting to 0.0")
        return 0.0

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
                
            is_regression = self.model_type in ("regression_v5", "regression_v5_unconstrained") or self.model_type.startswith("regression_v8")
            if is_regression:
                # Extract v5/v8 regression features (shared extractor; v8 reuses
                # the same feature set plus a few additions like momentum_10_atr)
                features = self._extract_v5_features(market_data, entry_price, structure_signal)

                # Make prediction for MFE
                mfe_feat_names = self.mfe_feature_names
                mfe_df = pd.DataFrame(
                    [[self._resolve_feature_value(features, name) for name in mfe_feat_names]],
                    columns=mfe_feat_names,
                )
                mfe_scaled = self.mfe_scaler.transform(mfe_df)
                mfe_scaled_df = pd.DataFrame(mfe_scaled, columns=mfe_feat_names)
                predicted_mfe = float(self.mfe_model.predict(mfe_scaled_df)[0])

                # Make prediction for MAE
                mae_feat_names = self.mae_feature_names
                mae_df = pd.DataFrame(
                    [[self._resolve_feature_value(features, name) for name in mae_feat_names]],
                    columns=mae_feat_names,
                )
                mae_scaled = self.mae_scaler.transform(mae_df)
                mae_scaled_df = pd.DataFrame(mae_scaled, columns=mae_feat_names)
                predicted_mae = float(self.mae_model.predict(mae_scaled_df)[0])

                # v8 targets are price-ratio normalized (target/(entry_price/4500)) --
                # convert back to points by multiplying with entry_price / 4500
                if getattr(self, "norm_target", False):
                    price_ratio_now = max(entry_price, 1.0) / self.base_reference_price
                    predicted_mfe *= price_ratio_now
                    predicted_mae *= price_ratio_now

                # Ensure predicted values are reasonable/positive
                predicted_mfe = max(0.0, predicted_mfe)
                predicted_mae = max(1.0, predicted_mae)

                expected_rr = predicted_mfe / predicted_mae

                # ML gate anti-overfit: gate hanya VETO jika (a) fold produksi
                # dilatih dengan cukup sampel, dan (b) expected RR di bawah
                # ambang veto. Di atas ambang = teruskan tanpa menyentuh sinyal
                # (EA filter tetap otoritatif). Fold tipis = gate pasif.
                gate_active = self.production_train_samples >= self.gate_min_train_samples
                if not gate_active or expected_rr >= self.rr_gate_threshold:
                    signal = structure_signal
                    confidence = min(1.0, max(0.65, expected_rr / 3.0))
                    if not gate_active:
                        reasoning = (
                            f"ML gate pasif (fold training {self.production_train_samples} < "
                            f"{self.gate_min_train_samples} sampel). Sinyal {structure_signal} diteruskan "
                            f"dengan prediksi R:R = {expected_rr:.2f} (MFE: {predicted_mfe:.1f} pts, MAE: {predicted_mae:.1f} pts)."
                        )
                    else:
                        reasoning = (
                            f"Model predicts favorable dynamic R:R = {expected_rr:.2f} "
                            f"(predicted MFE: {predicted_mfe:.1f} pts, MAE: {predicted_mae:.1f} pts) "
                            f"which is above the veto threshold ({self.rr_gate_threshold:.2f})."
                        )
                else:
                    signal = "HOLD"
                    confidence = max(0.0, min(1.0, 1.0 - (expected_rr / self.rr_gate_threshold) if self.rr_gate_threshold > 0 else 0.5))
                    reasoning = (
                        f"Model predicts unfavorable dynamic R:R = {expected_rr:.2f} "
                        f"(predicted MFE: {predicted_mfe:.1f} pts, MAE: {predicted_mae:.1f} pts) "
                        f"which is below the veto threshold ({self.rr_gate_threshold:.2f}). Filtering setup."
                    )
                
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
                    "threshold": self.rr_gate_threshold,
                    "gate_active": gate_active,
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
