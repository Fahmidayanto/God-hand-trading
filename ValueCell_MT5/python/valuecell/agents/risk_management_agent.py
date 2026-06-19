"""
Risk Management Agent - Position Sizing & SL/TP Calculation

This agent handles all risk-related decisions:
1. Position sizing based on account balance and confidence
2. Dynamic SL/TP calculation based on volatility
3. Risk validation and approval
4. Portfolio-level risk monitoring

Key Features:
- Dynamic lot calculation (1.5% STRONG, 1.0% GOOD, 0.5% WEAK)
- ATR-based SL/TP with volatility regime detection
- Session and time-of-day adjustments
- Maximum risk limits and validation
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum
from loguru import logger


class VolatilityRegime(Enum):
    """Market volatility classification"""
    LOW = "low"       # ATR < Q1
    NORMAL = "normal"  # Q1 <= ATR < Q3
    HIGH = "high"     # ATR >= Q3


class ConfidenceTier(Enum):
    """Trading confidence tiers"""
    STRONG = "STRONG"     # >80% confidence
    GOOD = "GOOD"         # 65-80%
    WEAK = "WEAK"         # 50-65%
    NO_TRADE = "NO_TRADE" # <50%


class RiskManagementAgent:
    """
    Risk Management Agent - Handles position sizing and SL/TP calculation.
    
    Purpose:
    - Calculate optimal lot size based on account balance and confidence
    - Determine dynamic SL/TP based on volatility (ATR)
    - Validate risk limits before trade execution
    - Provide risk assessment for each trade
    
    Configuration:
    - Account balance tracking
    - Risk percentages by confidence tier
    - Max lot size, max SL distance
    - Volatility regime thresholds
    """
    
    # Default risk percentages by tier
    RISK_PCT_BY_TIER = {
        ConfidenceTier.STRONG: 1.5,    # >80% confidence
        ConfidenceTier.GOOD: 1.0,      # 65-80%
        ConfidenceTier.WEAK: 0.5,      # 50-65%
        ConfidenceTier.NO_TRADE: 0.0,  # <50%
    }
    
    # SL multipliers by volatility regime (x ATR)
    SL_MULTIPLIERS = {
        VolatilityRegime.LOW: 2.5,     # Tight SL in quiet market
        VolatilityRegime.NORMAL: 4.0,  # Standard SL
        VolatilityRegime.HIGH: 6.0,    # Wide SL in volatile market
    }
    
    # TP multipliers by volatility regime (x ATR)
    TP_MULTIPLIERS = {
        VolatilityRegime.LOW: 3.5,     # Modest target
        VolatilityRegime.NORMAL: 5.0,  # Standard target
        VolatilityRegime.HIGH: 7.0,    # Wide target
    }
    
    # Session volatility adjustments
    SESSION_ADJUSTMENTS = {
        "Asia": 0.85,       # Quieter
        "London": 1.2,      # Peak volatility
        "NY": 1.15,         # High activity
        "Overlap": 1.3,     # London-NY overlap (highest volatility)
        "Other": 1.0,
    }
    
    # Hour-based volatility factors (0-23)
    HOUR_FACTORS = {
        0: 1.3, 1: 1.3, 2: 1.2,              # NY open
        3: 0.9, 4: 0.9, 5: 0.9,              # Asia quiet
        6: 1.0, 7: 1.3, 8: 1.4, 9: 1.3,      # London open
        10: 1.1, 11: 1.0,                     # London mid
        12: 1.2, 13: 1.3, 14: 1.1,           # Overlap
        15: 1.0, 16: 0.95,                    # Afternoon
        17: 1.0, 18: 1.0, 19: 1.05,          # Evening
        20: 1.1, 21: 1.2, 22: 1.15, 23: 1.2, # NY pre-open
    }
    
    def __init__(
        self,
        account_balance: float = 1000.0,
        max_lot: float = 10.0,
        min_lot: float = 0.01,
        max_sl_pips: float = 500.0,
        pip_value_per_lot: float = 10.0,  # XAUUSD standard
        base_atr: float = 7.5,
        atr_quartiles: Optional[Dict[str, float]] = None
    ):
        """
        Initialize Risk Management Agent.
        
        Args:
            account_balance: Current account balance in USD
            max_lot: Maximum lot size allowed
            min_lot: Minimum lot size allowed
            max_sl_pips: Maximum stop loss distance in pips
            pip_value_per_lot: Pip value for 1 standard lot (XAUUSD = $10)
            base_atr: Average ATR for market conditions
            atr_quartiles: Q1 and Q3 for volatility regime detection
        """
        self.name = "RiskManagementAgent"
        self.version = "1.0.0"
        
        # Account settings
        self.account_balance = account_balance
        self.max_lot = max_lot
        self.min_lot = min_lot
        self.max_sl_pips = max_sl_pips
        self.pip_value_per_lot = pip_value_per_lot
        
        # Volatility settings
        self.base_atr = base_atr
        self.atr_quartiles = atr_quartiles or {
            'Q1': 6.0,  # Default: 25th percentile
            'Q3': 8.5   # Default: 75th percentile
        }
        
        logger.info(
            f"✅ {self.name} v{self.version} initialized | "
            f"Balance: ${account_balance:,.2f} | "
            f"ATR Quartiles: Q1={self.atr_quartiles['Q1']:.1f}, Q3={self.atr_quartiles['Q3']:.1f}"
        )
    
    def update_balance(self, new_balance: float):
        """Update account balance dynamically"""
        self.account_balance = new_balance
        logger.info(f"💰 Balance updated: ${new_balance:,.2f}")
    
    def analyze(
        self,
        signal: str,
        confidence: float,
        entry_price: float,
        atr: float,
        current_time: datetime,
        session: str = "Other",
        symbol: str = "XAUUSD",
        balance_override: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Analyze and calculate risk parameters for a trade.
        
        Args:
            signal: Trade direction ("BUY" or "SELL")
            confidence: Agent confidence (0.0 to 1.0)
            entry_price: Proposed entry price
            atr: Current Average True Range
            current_time: Entry timestamp
            session: Trading session (Asia/London/NY/Overlap)
            symbol: Trading symbol
            balance_override: Override account balance for this calculation
        
        Returns:
            Dict with lot_size, sl_price, tp_price, risk assessment, and reasoning
        """
        try:
            logger.info(f"🎯 {self.name} analyzing {symbol} {signal}...")
            
            # Determine confidence tier
            tier = self._get_confidence_tier(confidence)
            
            # If NO_TRADE, return rejection
            if tier == ConfidenceTier.NO_TRADE:
                return self._rejection_response(
                    confidence, 
                    f"Confidence {confidence:.1%} below threshold (50%)"
                )
            
            # Calculate lot size
            lot_result = self._calculate_lot_size(
                tier=tier,
                atr=atr,
                confidence=confidence,
                balance_override=balance_override
            )
            
            # If lot size is 0, return rejection
            if lot_result["lot_size"] <= 0:
                return self._rejection_response(
                    confidence,
                    lot_result.get("note", "Invalid lot size calculation")
                )
            
            # Calculate dynamic SL/TP
            sltp_result = self._calculate_dynamic_sltp(
                entry_price=entry_price,
                atr=atr,
                signal=signal,
                current_time=current_time,
                session=session
            )
            
            # Validate risk parameters
            validation = self._validate_risk(
                lot_size=lot_result["lot_size"],
                sl_pips=sltp_result["sl_distance_pips"],
                balance=balance_override or self.account_balance
            )
            
            if not validation["approved"]:
                return self._rejection_response(
                    confidence,
                    validation["reason"]
                )
            
            # Build reasoning
            reasoning_parts = [
                f"Risk tier: {tier.value} ({confidence:.1%} confidence).",
                f"Lot size: {lot_result['lot_size']:.2f} (risk: {lot_result['risk_pct']:.2f}% = ${lot_result['risk_usd']:.2f}).",
                f"SL/TP: {sltp_result['volatility_regime']} volatility ({atr:.2f} ATR).",
                f"R/R ratio: {sltp_result['rr_ratio']:.2f}.",
                f"Session: {session} (adj: {sltp_result['vol_adjustment_factor']:.2f}x)."
            ]
            reasoning = " ".join(reasoning_parts)
            
            # Calculate potential profit/loss
            potential_loss = lot_result["risk_usd"]
            potential_profit = self._estimate_profit(
                lot_result["lot_size"],
                sltp_result["tp_distance_pips"]
            )
            
            # Build response
            response = {
                "agent": self.name,
                "version": self.version,
                "timestamp": current_time.isoformat(),
                "symbol": symbol,
                "signal": signal,
                "approved": True,
                "confidence": confidence,
                "reasoning": reasoning,
                
                # Position sizing
                "lot_size": lot_result["lot_size"],
                "risk_pct": lot_result["risk_pct"],
                "risk_usd": lot_result["risk_usd"],
                "tier": tier.value,
                
                # SL/TP
                "entry_price": entry_price,
                "sl_price": sltp_result["sl_price"],
                "tp_price": sltp_result["tp_price"],
                "sl_distance_pips": sltp_result["sl_distance_pips"],
                "tp_distance_pips": sltp_result["tp_distance_pips"],
                "rr_ratio": sltp_result["rr_ratio"],
                
                # Volatility context
                "atr": atr,
                "volatility_regime": sltp_result["volatility_regime"],
                "vol_adjustment_factor": sltp_result["vol_adjustment_factor"],
                
                # Risk assessment
                "potential_loss": potential_loss,
                "potential_profit": potential_profit,
                "balance_used": balance_override or self.account_balance,
                "session": session,
                "sltp_confidence": sltp_result["confidence"],
                
                # Metadata
                "validation": validation,
            }
            
            logger.info(
                f"✅ {self.name} approved | "
                f"Lot: {lot_result['lot_size']:.2f} | "
                f"Risk: {lot_result['risk_pct']:.2f}% | "
                f"R/R: {sltp_result['rr_ratio']:.2f}"
            )
            
            return response
            
        except Exception as e:
            logger.error(f"❌ {self.name} analysis failed: {e}")
            return self._error_response(str(e))
    
    def _get_confidence_tier(self, confidence: float) -> ConfidenceTier:
        """Map confidence to tier"""
        if confidence >= 0.80:
            return ConfidenceTier.STRONG
        elif confidence >= 0.65:
            return ConfidenceTier.GOOD
        elif confidence >= 0.50:
            return ConfidenceTier.WEAK
        else:
            return ConfidenceTier.NO_TRADE
    
    def _calculate_lot_size(
        self,
        tier: ConfidenceTier,
        atr: float,
        confidence: float,
        balance_override: Optional[float] = None
    ) -> Dict[str, Any]:
        """Calculate position size based on tier and ATR"""
        
        balance = balance_override or self.account_balance
        risk_pct = self.RISK_PCT_BY_TIER[tier]
        risk_usd = balance * (risk_pct / 100.0)
        
        # Estimate SL distance (will be refined by dynamic calculator)
        vol_regime = self._classify_volatility(atr)
        estimated_sl_pips = atr * self.SL_MULTIPLIERS[vol_regime]
        
        # Validate SL distance
        if estimated_sl_pips > self.max_sl_pips:
            return {
                "lot_size": 0.0,
                "risk_pct": risk_pct,
                "risk_usd": 0.0,
                "note": f"SL distance ({estimated_sl_pips:.0f} pips) exceeds max ({self.max_sl_pips:.0f})"
            }
        
        # Calculate lot size: Lot = RiskUSD / (SL_pips × PipValue)
        lot_raw = risk_usd / (estimated_sl_pips * self.pip_value_per_lot)
        
        # Round to nearest 0.01
        lot_size = round(round(lot_raw / 0.01) * 0.01, 2)
        
        # Clamp to min/max
        lot_size = max(self.min_lot, min(self.max_lot, lot_size))
        
        # Recalculate actual risk
        actual_risk_usd = lot_size * estimated_sl_pips * self.pip_value_per_lot
        actual_risk_pct = (actual_risk_usd / balance) * 100 if balance > 0 else 0
        
        return {
            "lot_size": lot_size,
            "risk_pct": round(actual_risk_pct, 3),
            "risk_usd": round(actual_risk_usd, 2),
            "risk_pct_target": risk_pct,
            "estimated_sl_pips": estimated_sl_pips,
            "tier": tier.value,
            "confidence": confidence,
        }
    
    def _calculate_dynamic_sltp(
        self,
        entry_price: float,
        atr: float,
        signal: str,
        current_time: datetime,
        session: str
    ) -> Dict[str, Any]:
        """Calculate dynamic SL/TP based on volatility"""
        
        # Classify volatility
        vol_regime = self._classify_volatility(atr)
        
        # Get multipliers
        sl_mult = self.SL_MULTIPLIERS[vol_regime]
        tp_mult = self.TP_MULTIPLIERS[vol_regime]
        
        # Get volatility adjustment factor
        vol_adjustment = self._get_vol_adjustment(current_time, session)
        
        # Calculate distances
        sl_distance = atr * sl_mult * vol_adjustment
        tp_distance = atr * tp_mult * vol_adjustment
        
        # Calculate prices
        if signal.upper() == "BUY":
            sl_price = entry_price - sl_distance
            tp_price = entry_price + tp_distance
        else:  # SELL
            sl_price = entry_price + sl_distance
            tp_price = entry_price - tp_distance
        
        # Calculate R/R ratio
        rr_ratio = tp_distance / sl_distance if sl_distance > 0 else 0
        
        # Calculate confidence
        if vol_regime == VolatilityRegime.NORMAL:
            confidence = 0.8
        elif vol_regime == VolatilityRegime.LOW:
            confidence = 0.75
        else:  # HIGH
            confidence = 0.7
        
        # Reduce confidence during market opens
        hour = current_time.hour
        if hour in [0, 1, 7, 8, 19, 20, 21]:
            confidence *= 0.85
        
        return {
            "sl_price": round(sl_price, 2),
            "tp_price": round(tp_price, 2),
            "sl_distance_pips": round(sl_distance, 2),
            "tp_distance_pips": round(tp_distance, 2),
            "rr_ratio": round(rr_ratio, 2),
            "volatility_regime": vol_regime.value,
            "vol_adjustment_factor": round(vol_adjustment, 2),
            "sl_multiplier": sl_mult,
            "tp_multiplier": tp_mult,
            "confidence": round(confidence, 2),
        }
    
    def _classify_volatility(self, atr: float) -> VolatilityRegime:
        """Classify ATR into volatility regime"""
        if atr < self.atr_quartiles['Q1']:
            return VolatilityRegime.LOW
        elif atr < self.atr_quartiles['Q3']:
            return VolatilityRegime.NORMAL
        else:
            return VolatilityRegime.HIGH
    
    def _get_vol_adjustment(self, current_time: datetime, session: str) -> float:
        """Calculate volatility adjustment based on time and session"""
        hour_factor = self.HOUR_FACTORS.get(current_time.hour, 1.0)
        session_factor = self.SESSION_ADJUSTMENTS.get(session, 1.0)
        return hour_factor * session_factor
    
    def _validate_risk(
        self,
        lot_size: float,
        sl_pips: float,
        balance: float
    ) -> Dict[str, Any]:
        """Validate risk parameters"""
        
        # Check lot size
        if lot_size < self.min_lot:
            return {
                "approved": False,
                "reason": f"Lot size ({lot_size:.2f}) below minimum ({self.min_lot})"
            }
        
        if lot_size > self.max_lot:
            return {
                "approved": False,
                "reason": f"Lot size ({lot_size:.2f}) exceeds maximum ({self.max_lot})"
            }
        
        # Check SL distance
        if sl_pips > self.max_sl_pips:
            return {
                "approved": False,
                "reason": f"SL distance ({sl_pips:.0f} pips) exceeds maximum ({self.max_sl_pips:.0f})"
            }
        
        # Check total risk
        risk_usd = lot_size * sl_pips * self.pip_value_per_lot
        risk_pct = (risk_usd / balance) * 100
        
        if risk_pct > 5.0:  # Hard limit: 5% max risk per trade
            return {
                "approved": False,
                "reason": f"Risk ({risk_pct:.2f}%) exceeds maximum (5.0%)"
            }
        
        return {
            "approved": True,
            "reason": "All risk parameters within limits",
            "risk_usd": risk_usd,
            "risk_pct": risk_pct
        }
    
    def _estimate_profit(self, lot_size: float, tp_pips: float) -> float:
        """Estimate profit if TP is hit"""
        return round(lot_size * tp_pips * self.pip_value_per_lot, 2)
    
    def _rejection_response(self, confidence: float, reason: str) -> Dict[str, Any]:
        """Generate rejection response"""
        return {
            "agent": self.name,
            "version": self.version,
            "timestamp": datetime.now().isoformat(),
            "approved": False,
            "confidence": confidence,
            "reasoning": reason,
            "lot_size": 0.0,
            "risk_pct": 0.0,
            "risk_usd": 0.0,
        }
    
    def _error_response(self, error: str) -> Dict[str, Any]:
        """Generate error response"""
        return {
            "agent": self.name,
            "version": self.version,
            "timestamp": datetime.now().isoformat(),
            "approved": False,
            "confidence": 0.0,
            "reasoning": f"Risk analysis error: {error}",
            "lot_size": 0.0,
            "risk_pct": 0.0,
            "risk_usd": 0.0,
            "error": error,
        }
    
    def get_info(self) -> Dict[str, Any]:
        """Get agent information"""
        return {
            "name": self.name,
            "version": self.version,
            "type": "risk_management",
            "description": "Position sizing and dynamic SL/TP calculation",
            "configuration": {
                "account_balance": self.account_balance,
                "max_lot": self.max_lot,
                "min_lot": self.min_lot,
                "max_sl_pips": self.max_sl_pips,
                "pip_value_per_lot": self.pip_value_per_lot,
                "base_atr": self.base_atr,
                "atr_quartiles": self.atr_quartiles,
            },
            "risk_tiers": {
                tier.value: f"{pct}%" 
                for tier, pct in self.RISK_PCT_BY_TIER.items()
            },
            "volatility_regimes": [regime.value for regime in VolatilityRegime],
            "capabilities": [
                "Dynamic position sizing (0.5% - 1.5% risk)",
                "ATR-based SL/TP calculation",
                "Volatility regime detection (LOW/NORMAL/HIGH)",
                "Session-based adjustments",
                "Time-of-day volatility factors",
                "Risk validation and approval",
                "R/R ratio optimization",
            ]
        }


# ========== STANDALONE TESTING ==========

if __name__ == "__main__":
    logger.info("Testing RiskManagementAgent...")
    
    # Initialize agent
    agent = RiskManagementAgent(
        account_balance=1000.0,
        max_lot=10.0,
        min_lot=0.01,
        max_sl_pips=500.0
    )
    
    # Get agent info
    info = agent.get_info()
    logger.info(f"Agent: {info['name']} v{info['version']}")
    logger.info(f"Balance: ${info['configuration']['account_balance']:,.2f}")
    
    # Test scenarios
    test_cases = [
        {
            "name": "STRONG Confidence - LOW Volatility",
            "signal": "BUY",
            "confidence": 0.85,
            "entry_price": 2350.0,
            "atr": 5.5,
            "session": "London"
        },
        {
            "name": "GOOD Confidence - NORMAL Volatility",
            "signal": "SELL",
            "confidence": 0.72,
            "entry_price": 2350.0,
            "atr": 7.2,
            "session": "NY"
        },
        {
            "name": "WEAK Confidence - HIGH Volatility",
            "signal": "BUY",
            "confidence": 0.58,
            "entry_price": 2350.0,
            "atr": 9.5,
            "session": "Overlap"
        },
        {
            "name": "NO TRADE - Low Confidence",
            "signal": "BUY",
            "confidence": 0.45,
            "entry_price": 2350.0,
            "atr": 7.0,
            "session": "Asia"
        },
    ]
    
    for i, test in enumerate(test_cases, 1):
        logger.info("=" * 70)
        logger.info(f"TEST {i}: {test['name']}")
        logger.info("=" * 70)
        
        result = agent.analyze(
            signal=test["signal"],
            confidence=test["confidence"],
            entry_price=test["entry_price"],
            atr=test["atr"],
            current_time=datetime.now().replace(hour=13, minute=0),
            session=test["session"],
            symbol="XAUUSD"
        )
        
        logger.info(f"\n📊 Result:")
        logger.info(f"   Approved: {result['approved']}")
        logger.info(f"   Reasoning: {result['reasoning']}")
        
        if result['approved']:
            logger.info(f"\n💼 Position:")
            logger.info(f"   Lot Size: {result['lot_size']:.2f}")
            logger.info(f"   Risk: {result['risk_pct']:.2f}% (${result['risk_usd']:.2f})")
            logger.info(f"\n🎯 SL/TP:")
            logger.info(f"   Entry: {result['entry_price']:.2f}")
            logger.info(f"   SL: {result['sl_price']:.2f} ({result['sl_distance_pips']:.2f} pips)")
            logger.info(f"   TP: {result['tp_price']:.2f} ({result['tp_distance_pips']:.2f} pips)")
            logger.info(f"   R/R: {result['rr_ratio']:.2f}")
            logger.info(f"\n📈 Potential:")
            logger.info(f"   Loss: ${result['potential_loss']:.2f}")
            logger.info(f"   Profit: ${result['potential_profit']:.2f}")
        
        logger.info("")
    
    logger.info("=" * 70)
    logger.info("✅ RiskManagementAgent test complete!")
