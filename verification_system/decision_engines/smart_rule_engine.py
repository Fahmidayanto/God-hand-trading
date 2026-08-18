"""
Smart Rule Engine - Rule-Based Trade Decision

Deterministic rule-based decision engine yang consume ReplayContext
(dari verification_system.analyzers.replay_structure_provider) dan menghasilkan
TradeSetup lengkap: entry, SL, TP, lot, confidence, reasoning.

Logic overview (priority order):
1. PRE-FILTER: block trade jika ada high-impact event imminent
2. REGIME CHECK: block atau reduce confidence jika transitioning
3. ENTRY: confluence dari structure + OB + FVG + regime alignment
4. SL: priority SSL → OB zone → ATR fallback
5. TP: priority BSL → OB zone → FVG CE → R:R 2:1
6. LOT SIZE: fixed % risk, position sizing dari SL distance

Output TradeSetup kompatibel dengan LLMTradeSetup format (untuk A/B test).

Ponytail:
- Pure function, no I/O
- Deterministic (same input → same output)
- No external state, replay-safe
- Configurable thresholds via constructor
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any

from loguru import logger

# Reuse analyzer output structure (compatible with package or standalone mode)
try:
    from ..analyzers.replay_structure_provider import ReplayContext
except ImportError:
    try:
        from verification_system.analyzers.replay_structure_provider import ReplayContext
    except ImportError:
        # Standalone script — add path dynamically
        import os
        import sys
        _here = os.path.dirname(os.path.abspath(__file__))
        _parent = os.path.dirname(_here)  # verification_system/
        _root = os.path.dirname(_parent)  # B:/Project MT5/
        if _root not in sys.path:
            sys.path.insert(0, _root)
        from verification_system.analyzers.replay_structure_provider import ReplayContext


# ── Enums ──────────────────────────────────────────────────────────────────

class Signal(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"           # No trade, dengan reasoning
    BLOCKED = "BLOCKED"     # Hard block (event imminent, etc.)


# ── Output dataclass ───────────────────────────────────────────────────────

@dataclass
class TradeSetup:
    """Final trade decision. Compatible dengan LLMTradeSetup output."""
    signal: Signal
    entry_price: float
    sl: float
    tp1: float
    tp2: Optional[float] = None
    lot_size: float = 0.0
    risk_pct: float = 1.0
    rr_ratio: float = 0.0          # R:R dari SL ke TP1
    confidence: float = 0.0         # 0-1
    reasoning: str = ""
    confluences: List[str] = field(default_factory=list)
    filters_applied: List[str] = field(default_factory=list)
    block_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["signal"] = self.signal.value
        return d


# ── Engine ─────────────────────────────────────────────────────────────────

class SmartRuleEngine:
    """
    Rule-based decision engine. Stateless, deterministic.

    Constructor params:
        risk_pct: % balance to risk per trade (default 1.0)
        min_rr: minimum R:R ratio (default 2.0)
        sl_atr_mult: SL distance sebagai ATR multiplier (fallback)
        tp_atr_mult: TP distance sebagai ATR multiplier (fallback)
        contract_size: contract size untuk lot calculation (XAUUSD = 100)
        min_confidence: minimum confidence untuk take trade (default 0.5)
    """

    def __init__(
        self,
        risk_pct: float = 1.0,
        min_rr: float = 2.0,
        sl_atr_mult: float = 1.5,
        tp_atr_mult: float = 3.0,
        contract_size: float = 100.0,
        min_confidence: float = 0.5,
        balance: float = 1000.0,
    ):
        self.risk_pct = risk_pct
        self.min_rr = min_rr
        self.sl_atr_mult = sl_atr_mult
        self.tp_atr_mult = tp_atr_mult
        self.contract_size = contract_size
        self.min_confidence = min_confidence
        self.balance = balance

    def decide(self, context: ReplayContext) -> TradeSetup:
        """
        Run rule-based decision pada ReplayContext.

        Returns TradeSetup dengan signal, SL, TP, lot, confidence, reasoning.
        """
        reasoning_parts: List[str] = []
        confluences: List[str] = []
        filters: List[str] = []

        # ── 1. PRE-FILTERS ──
        blocked_signal, block_reason = self._pre_filter(context, filters)
        if blocked_signal:
            return TradeSetup(
                signal=Signal.BLOCKED,
                entry_price=context.market_data.get("current_price", 0.0),
                sl=0.0,
                tp1=0.0,
                confidence=0.0,
                reasoning=f"BLOCKED: {block_reason}",
                filters_applied=filters,
                block_reason=block_reason,
            )

        # ── 2. REGIME CHECK ──
        regime, regime_ok, regime_conf = self._regime_check(context, reasoning_parts)
        if not regime_ok:
            return TradeSetup(
                signal=Signal.HOLD,
                entry_price=context.market_data.get("current_price", 0.0),
                sl=0.0,
                tp1=0.0,
                confidence=regime_conf,
                reasoning="; ".join(reasoning_parts),
                filters_applied=filters,
            )

        # ── 3. SIGNAL DIRECTION ──
        signal, direction_conf, dir_reasons = self._direction(context, regime, confluences)
        reasoning_parts.extend(dir_reasons)

        if signal == Signal.HOLD:
            return TradeSetup(
                signal=Signal.HOLD,
                entry_price=context.market_data.get("current_price", 0.0),
                sl=0.0,
                tp1=0.0,
                confidence=regime_conf * direction_conf,
                reasoning="; ".join(reasoning_parts),
                filters_applied=filters,
            )

        # ── 4. ENTRY PRICE ──
        entry = context.market_data.get("current_price", 0.0)
        atr = context.market_data.get("atr", 0.0)

        # ── 5. STOP LOSS ──
        sl, sl_reasons = self._calc_sl(context, signal, entry, atr, confluences)
        reasoning_parts.extend(sl_reasons)

        # ── 6. TAKE PROFIT ──
        tp1, tp2, tp_reasons = self._calc_tp(context, signal, entry, sl, atr, confluences)
        reasoning_parts.extend(tp_reasons)

        # ── 7. R:R VALIDATION ──
        rr = self._calc_rr(entry, sl, tp1)
        if rr < self.min_rr:
            filters.append(f"rr_below_min({rr:.2f}<{self.min_rr})")
            return TradeSetup(
                signal=Signal.HOLD,
                entry_price=entry,
                sl=sl,
                tp1=tp1,
                confidence=regime_conf * direction_conf * 0.3,
                reasoning=f"Low R:R {rr:.2f} < {self.min_rr}; " + "; ".join(reasoning_parts),
                filters_applied=filters,
            )

        # ── 8. LOT SIZE ──
        lot = self._calc_lot_size(entry, sl)

        # ── 9. CONFIDENCE ──
        confidence = self._calc_confidence(
            regime_conf, direction_conf, len(confluences), rr
        )

        return TradeSetup(
            signal=signal,
            entry_price=entry,
            sl=sl,
            tp1=tp1,
            tp2=tp2,
            lot_size=lot,
            risk_pct=self.risk_pct,
            rr_ratio=rr,
            confidence=confidence,
            reasoning="; ".join(reasoning_parts),
            confluences=confluences,
            filters_applied=filters,
        )

    # ── PRE-FILTER ──
    def _pre_filter(
        self, context: ReplayContext, filters: List[str]
    ) -> tuple:
        """Hard block: high-impact event imminent."""
        events = context.events or {}
        if events.get("should_avoid_trading"):
            reason = events.get("avoid_reason", "high_impact_event_imminent")
            filters.append(f"event:{reason}")
            return True, reason
        return False, ""

    # ── REGIME CHECK ──
    def _regime_check(
        self, context: ReplayContext, reasoning: List[str]
    ) -> tuple:
        """Cek regime. Return (regime_name, is_ok, confidence)."""
        regime_data = context.regime or {}
        overall = regime_data.get("overall_regime", "unknown")
        confluence = regime_data.get("confluence", False)

        if overall == "unknown":
            reasoning.append("regime unknown → low confidence")
            return overall, True, 0.3

        if overall == "transitioning":
            reasoning.append("regime transitioning → BLOCKED")
            return overall, False, 0.0

        if not confluence and overall in ("trending_up", "trending_down"):
            reasoning.append(
                f"regime {overall} tapi H1/H4 tidak align → reduce conf"
            )
            return overall, True, 0.5

        return overall, True, 0.8

    # ── DIRECTION ──
    def _direction(
        self,
        context: ReplayContext,
        regime: str,
        confluences: List[str],
    ) -> tuple:
        """
        Tentukan signal BUY/SELL/HOLD berdasarkan confluence.

        Confluence factors (weighted):
        - OB bullish/bearish fresh di sisi bawah/atas price: +0.3
        - FVG bullish/bearish fresh: +0.2
        - Liquidity BSL di atas (TP available for BUY): +0.2
        - Regime alignment (trending): +0.3
        """
        ob = context.order_blocks or {}
        fvg = context.fvg or {}
        liq = context.liquidity or {}

        score_buy = 0.0
        score_sell = 0.0
        reasons = []

        # OB confluence
        if ob.get("fresh_bullish_near"):
            score_buy += 0.3
            confluences.append("OB_demand_below")
        if ob.get("fresh_bearish_near"):
            score_sell += 0.3
            confluences.append("OB_supply_above")
        if ob.get("mitigated_bullish_recent"):
            score_buy += 0.15
            confluences.append("OB_mitigated_bullish")
        if ob.get("mitigated_bearish_recent"):
            score_sell += 0.15
            confluences.append("OB_mitigated_bearish")

        # FVG confluence
        if fvg.get("fresh_bullish_near"):
            score_buy += 0.2
            confluences.append("FVG_bullish_below")
        if fvg.get("fresh_bearish_near"):
            score_sell += 0.2
            confluences.append("FVG_bearish_above")

        # Liquidity target
        if liq.get("nearest_bsl"):
            score_buy += 0.2
            confluences.append("BSL_target_above")
        if liq.get("nearest_ssl"):
            score_sell += 0.2
            confluences.append("SSL_target_below")

        # Regime boost
        if regime == "trending_up":
            score_buy += 0.3
            confluences.append("regime_trending_up")
        elif regime == "trending_down":
            score_sell += 0.3
            confluences.append("regime_trending_down")

        # Decision
        signal = Signal.HOLD
        direction_conf = max(score_buy, score_sell)
        if score_buy > score_sell and score_buy >= 0.3:
            signal = Signal.BUY
            reasons.append(f"BUY score={score_buy:.2f}, confluences={len(confluences)}")
        elif score_sell > score_buy and score_sell >= 0.3:
            signal = Signal.SELL
            reasons.append(f"SELL score={score_sell:.2f}, confluences={len(confluences)}")
        else:
            reasons.append(f"No clear direction (buy={score_buy:.2f}, sell={score_sell:.2f})")
            direction_conf = 0.0

        return signal, min(1.0, direction_conf), reasons

    # ── SL ──
    def _calc_sl(
        self,
        context: ReplayContext,
        signal: Signal,
        entry: float,
        atr: float,
        confluences: List[str],
    ) -> tuple:
        """Hitung SL priority: SSL > OB > ATR fallback."""
        liq = context.liquidity or {}
        ob = context.order_blocks or {}
        reasons = []

        if signal == Signal.BUY:
            # Priority 1: nearest SSL di bawah
            ssl = liq.get("nearest_ssl")
            if ssl and ssl.get("price", 0) < entry:
                sl = float(ssl["price"]) - atr * 0.1  # buffer di bawah SSL
                confluences.append("SL_at_SSL")
                reasons.append(f"SL at SSL {sl:.2f}")
                return sl, reasons

            # Priority 2: below fresh bullish OB
            ob_bull = ob.get("fresh_bullish_near")
            if ob_bull and ob_bull.get("bottom", 0) < entry:
                sl = float(ob_bull["bottom"]) - atr * 0.1
                confluences.append("SL_below_OB_demand")
                reasons.append(f"SL below OB demand {sl:.2f}")
                return sl, reasons

            # Fallback: ATR
            sl = entry - atr * self.sl_atr_mult
            confluences.append("SL_atr_fallback")
            reasons.append(f"SL at {self.sl_atr_mult}x ATR {sl:.2f}")
            return sl, reasons

        else:  # SELL
            # Priority 1: nearest BSL di atas
            bsl = liq.get("nearest_bsl")
            if bsl and bsl.get("price", 0) > entry:
                sl = float(bsl["price"]) + atr * 0.1
                confluences.append("SL_at_BSL")
                reasons.append(f"SL at BSL {sl:.2f}")
                return sl, reasons

            # Priority 2: above fresh bearish OB
            ob_bear = ob.get("fresh_bearish_near")
            if ob_bear and ob_bear.get("top", 0) > entry:
                sl = float(ob_bear["top"]) + atr * 0.1
                confluences.append("SL_above_OB_supply")
                reasons.append(f"SL above OB supply {sl:.2f}")
                return sl, reasons

            # Fallback
            sl = entry + atr * self.sl_atr_mult
            confluences.append("SL_atr_fallback")
            reasons.append(f"SL at {self.sl_atr_mult}x ATR {sl:.2f}")
            return sl, reasons

    # ── TP ──
    def _calc_tp(
        self,
        context: ReplayContext,
        signal: Signal,
        entry: float,
        sl: float,
        atr: float,
        confluences: List[str],
    ) -> tuple:
        """Hitung TP priority: BSL/SSL > OB opposite > FVG CE > ATR fallback."""
        liq = context.liquidity or {}
        ob = context.order_blocks or {}
        fvg = context.fvg or {}
        reasons = []

        sl_distance = abs(entry - sl)
        min_tp_distance = sl_distance * self.min_rr

        if signal == Signal.BUY:
            # Priority 1: nearest BSL di atas
            bsl = liq.get("nearest_bsl")
            if bsl and bsl.get("price", 0) > entry:
                tp1 = float(bsl["price"])
                # TP2: above BSL (extended target) atau next structural
                tp2_candidates = []
                if ob.get("fresh_bearish_near"):
                    tp2_candidates.append(float(ob["fresh_bearish_near"]["top"]))
                if fvg.get("fresh_bearish_near"):
                    tp2_candidates.append(float(fvg["fresh_bearish_near"]["ce"]))
                tp2 = max(tp2_candidates) if tp2_candidates else None
                confluences.append("TP_at_BSL")
                reasons.append(f"TP1 at BSL {tp1:.2f}")
                return tp1, tp2, reasons

            # Priority 2: OB supply di atas
            ob_bear = ob.get("fresh_bearish_near")
            if ob_bear and ob_bear.get("bottom", 0) > entry:
                tp1 = float(ob_bear["bottom"])
                tp2 = float(ob_bear["top"])
                confluences.append("TP_at_OB_supply")
                reasons.append(f"TP1 at OB supply bottom {tp1:.2f}")
                return tp1, tp2, reasons

            # Priority 3: FVG CE di atas
            fvg_bear = fvg.get("fresh_bearish_near")
            if fvg_bear and fvg_bear.get("ce", 0) > entry:
                tp1 = float(fvg_bear["ce"])
                tp2 = float(fvg_bear["top"])
                confluences.append("TP_at_FVG_ce")
                reasons.append(f"TP1 at FVG CE {tp1:.2f}")
                return tp1, tp2, reasons

            # Fallback: ATR dengan min R:R
            tp1 = entry + max(atr * self.tp_atr_mult, min_tp_distance)
            confluences.append("TP_atr_fallback")
            reasons.append(f"TP1 at {self.tp_atr_mult}x ATR {tp1:.2f}")
            return tp1, None, reasons

        else:  # SELL
            # Priority 1: nearest SSL di bawah
            ssl = liq.get("nearest_ssl")
            if ssl and ssl.get("price", 0) < entry:
                tp1 = float(ssl["price"])
                tp2_candidates = []
                if ob.get("fresh_bullish_near"):
                    tp2_candidates.append(float(ob["fresh_bullish_near"]["bottom"]))
                if fvg.get("fresh_bullish_near"):
                    tp2_candidates.append(float(fvg["fresh_bullish_near"]["ce"]))
                tp2 = min(tp2_candidates) if tp2_candidates else None
                confluences.append("TP_at_SSL")
                reasons.append(f"TP1 at SSL {tp1:.2f}")
                return tp1, tp2, reasons

            # Priority 2: OB demand di bawah
            ob_bull = ob.get("fresh_bullish_near")
            if ob_bull and ob_bull.get("top", 0) < entry:
                tp1 = float(ob_bull["top"])
                tp2 = float(ob_bull["bottom"])
                confluences.append("TP_at_OB_demand")
                reasons.append(f"TP1 at OB demand top {tp1:.2f}")
                return tp1, tp2, reasons

            # Priority 3: FVG CE di bawah
            fvg_bull = fvg.get("fresh_bullish_near")
            if fvg_bull and fvg_bull.get("ce", 0) < entry:
                tp1 = float(fvg_bull["ce"])
                tp2 = float(fvg_bull["bottom"])
                confluences.append("TP_at_FVG_ce")
                reasons.append(f"TP1 at FVG CE {tp1:.2f}")
                return tp1, tp2, reasons

            # Fallback
            tp1 = entry - max(atr * self.tp_atr_mult, min_tp_distance)
            confluences.append("TP_atr_fallback")
            reasons.append(f"TP1 at {self.tp_atr_mult}x ATR {tp1:.2f}")
            return tp1, None, reasons

    # ── R:R ──
    def _calc_rr(self, entry: float, sl: float, tp: float) -> float:
        if entry == sl:
            return 0.0
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        return reward / risk if risk > 0 else 0.0

    # ── LOT SIZE ──
    def _calc_lot_size(self, entry: float, sl: float) -> float:
        """Position sizing dari fixed % risk."""
        sl_distance = abs(entry - sl)
        if sl_distance <= 0:
            return 0.0
        risk_amount = self.balance * (self.risk_pct / 100.0)
        # XAUUSD: 1 lot = 100 oz, $1 price move = $100 per lot
        # Risk per lot = sl_distance * contract_size
        risk_per_lot = sl_distance * self.contract_size
        if risk_per_lot <= 0:
            return 0.0
        lot = risk_amount / risk_per_lot
        # Round ke 0.01 (MT5 standard)
        return round(lot, 2)

    # ── CONFIDENCE ──
    def _calc_confidence(
        self,
        regime_conf: float,
        direction_conf: float,
        n_confluences: int,
        rr: float,
    ) -> float:
        """
        Composite confidence:
        - regime_conf (0-0.8)
        - direction_conf (0-1)
        - confluence bonus: 0.05 per confluence, max 0.3
        - R:R bonus: 0.1 if rr >= 3, 0.05 if rr >= 2
        """
        conf = regime_conf * direction_conf
        conf += min(0.3, n_confluences * 0.05)
        if rr >= 3.0:
            conf += 0.1
        elif rr >= 2.0:
            conf += 0.05
        return min(1.0, max(0.0, conf))


# ── CLI smoke test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Smoke test: rule engine + ReplayStructureProvider integration.
    """
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    import numpy as np
    import pandas as pd

    from verification_system.analyzers.replay_structure_provider import (
        ReplayStructureProvider,
    )

    np.random.seed(42)
    n = 500
    base = 2000.0
    # Slight uptrend
    prices = base + np.cumsum(np.random.randn(n) * 0.5 + 0.2)

    df_m15 = pd.DataFrame(
        {
            "time": pd.date_range("2023-04-15", periods=n, freq="15min"),
            "open": prices + np.random.randn(n) * 0.3,
            "high": prices + abs(np.random.randn(n)) * 0.8,
            "low": prices - abs(np.random.randn(n)) * 0.8,
            "close": prices,
        }
    )
    df_h1 = df_m15.iloc[::4].reset_index(drop=True)
    df_h4 = df_m15.iloc[::16].reset_index(drop=True)

    provider = ReplayStructureProvider()
    engine = SmartRuleEngine(balance=1000.0, risk_pct=1.0, min_rr=2.0)

    print("=" * 60)
    print("SCENARIO 1: Trending market, no event nearby")
    print("=" * 60)
    anchor_ts = df_m15["time"].iloc[400].to_pydatetime()
    if anchor_ts.tzinfo is None:
        from datetime import timezone
        anchor_ts = anchor_ts.replace(tzinfo=timezone.utc)
    ctx1 = provider.build(
        ohlc_by_timeframe={"M15": df_m15, "H1": df_h1, "H4": df_h4},
        anchor_ts=anchor_ts,
        anchor_idx_by_timeframe={"M15": 400, "H1": 100, "H4": 25},
    )
    setup1 = engine.decide(ctx1)
    print(f"Signal: {setup1.signal.value}")
    print(f"Entry: {setup1.entry_price:.2f}")
    print(f"SL: {setup1.sl:.2f}  | TP1: {setup1.tp1:.2f}  | TP2: {setup1.tp2 if setup1.tp2 else 'N/A'}")
    print(f"Lot: {setup1.lot_size}  | R:R: {setup1.rr_ratio:.2f}  | Conf: {setup1.confidence:.2f}")
    print(f"Confluences: {setup1.confluences}")
    print(f"Reasoning: {setup1.reasoning}")
    print()

    print("=" * 60)
    print("SCENARIO 2: Near FOMC event (should BLOCK)")
    print("=" * 60)
    from datetime import datetime, timezone
    anchor_fomc = datetime(2023, 3, 22, 17, 0, tzinfo=timezone.utc)  # 1h before FOMC
    ctx2 = provider.build(
        ohlc_by_timeframe={"M15": df_m15, "H1": df_h1, "H4": df_h4},
        anchor_ts=anchor_fomc,
        anchor_idx_by_timeframe={"M15": 400, "H1": 100, "H4": 25},
    )
    setup2 = engine.decide(ctx2)
    print(f"Signal: {setup2.signal.value}")
    print(f"Block reason: {setup2.block_reason}")
    print(f"Filters: {setup2.filters_applied}")
    print()

    print("=" * 60)
    print("SCENARIO 3: Quiet range-bound market")
    print("=" * 60)
    anchor_quiet = datetime(2023, 4, 18, 12, 0, tzinfo=timezone.utc)
    ctx3 = provider.build(
        ohlc_by_timeframe={"M15": df_m15, "H1": df_h1, "H4": df_h4},
        anchor_ts=anchor_quiet,
        anchor_idx_by_timeframe={"M15": 400, "H1": 100, "H4": 25},
    )
    setup3 = engine.decide(ctx3)
    print(f"Signal: {setup3.signal.value}")
    print(f"Confidence: {setup3.confidence:.2f}")
    print(f"Confluences: {setup3.confluences}")
    print(f"Reasoning: {setup3.reasoning}")
