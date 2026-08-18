"""
Replay Decision API - Endpoint untuk toggle LLM/Rule engine di replay UI.

POST /api/v1/replay/decision
    Body: {symbol, anchor_timestamp, engine: "rule"|"llm", ohlc: {M15, H1, H4}}
    Returns: TradeSetup dict (schema-compatible rule vs LLM)

GET /api/v1/replay/health
    Returns: status info

Pattern: pure delegation ke verification_system.decision_engines.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter()

# Setup path ke verification_system (B:/Project MT5/)
# File: backend/app/api/v1/replay_decision.py
# parents[0]=api/v1, [1]=app, [2]=backend, [3]=ValueCell_MT5, [4]=Project MT5 (root)
from pathlib import Path as _Path
_REPO_ROOT = str(_Path(__file__).parents[5])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

try:
    from verification_system.analyzers.replay_structure_provider import ReplayStructureProvider
    from verification_system.decision_engines.smart_rule_engine import SmartRuleEngine
    from verification_system.decision_engines.llm_decision_engine import LLMDecisionEngine
    _ENGINES_AVAILABLE = True
    logger.info("Replay decision engines loaded successfully")
except ImportError as exc:
    _ENGINES_AVAILABLE = False
    logger.warning(f"Decision engines not available: {exc}")


# ── Pydantic models ─────────────────────────────────────────────────────────

class OHLCBar(BaseModel):
    time: str  # ISO format
    open: float
    high: float
    low: float
    close: float


class OHLCSet(BaseModel):
    M15: List[OHLCBar]
    H1: Optional[List[OHLCBar]] = None
    H4: Optional[List[OHLCBar]] = None


class DecisionRequest(BaseModel):
    symbol: str = "XAUUSD"
    anchor_timestamp: str  # ISO format
    engine: str = Field("rule", description="'rule' or 'llm'")
    ohlc: OHLCSet
    balance: float = 1000.0
    risk_pct: float = 1.0
    min_rr: float = 2.0


class DecisionResponse(BaseModel):
    success: bool
    engine: str
    signal: str
    entry_price: float
    sl: float
    tp1: float
    tp2: Optional[float] = None
    lot_size: float
    risk_pct: float
    rr_ratio: float
    confidence: float
    reasoning: str
    confluences: List[str] = []
    filters_applied: List[str] = []
    block_reason: Optional[str] = None
    regime: Optional[str] = None
    event_proximity: Optional[str] = None


# ── Helpers ─────────────────────────────────────────────────────────────────

def _ohlc_to_dataframe(bars: List[OHLCBar]) -> pd.DataFrame:
    """Convert list of OHLCBar to pandas DataFrame."""
    if not bars:
        return pd.DataFrame(columns=["time", "open", "high", "low", "close"])
    df = pd.DataFrame([b.model_dump() for b in bars])
    df["time"] = pd.to_datetime(df["time"])
    return df.sort_values("time").reset_index(drop=True)


def _resolve_anchor_idx(df: pd.DataFrame, anchor_ts: datetime) -> int:
    """Find candle index for anchor timestamp. Return closest <= anchor."""
    if df.empty:
        return 0
    anchor = pd.Timestamp(anchor_ts)
    # Find last candle with time <= anchor
    mask = df["time"] <= anchor
    if not mask.any():
        return 0
    return int(df[mask].index[-1])


# ── Endpoints ───────────────────────────────────────────────────────────────

@router.post("/decision", response_model=DecisionResponse)
async def get_replay_decision(req: DecisionRequest) -> DecisionResponse:
    """
    Get trade decision (rule-based or LLM-based) untuk replay context.

    Pilih engine via `engine` field: "rule" atau "llm".
    """
    if not _ENGINES_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Decision engines not loaded. Check verification_system path.",
        )

    if req.engine not in ("rule", "llm"):
        raise HTTPException(
            status_code=400,
            detail=f"engine must be 'rule' or 'llm', got '{req.engine}'",
        )

    # Parse anchor timestamp
    try:
        anchor_ts = datetime.fromisoformat(req.anchor_timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid timestamp: {exc}")

    # Convert OHLC to DataFrames
    try:
        ohlc_by_tf: Dict[str, pd.DataFrame] = {"M15": _ohlc_to_dataframe(req.ohlc.M15)}
        if req.ohlc.H1:
            ohlc_by_tf["H1"] = _ohlc_to_dataframe(req.ohlc.H1)
        if req.ohlc.H4:
            ohlc_by_tf["H4"] = _ohlc_to_dataframe(req.ohlc.H4)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid OHLC: {exc}")

    # Validate minimum data
    if len(ohlc_by_tf["M15"]) < 50:
        raise HTTPException(
            status_code=400,
            detail=f"M15 OHLC too short: {len(ohlc_by_tf['M15'])} bars (need >= 50)",
        )

    # Resolve anchor indices per timeframe
    anchor_idx_by_tf: Dict[str, int] = {}
    for tf, df in ohlc_by_tf.items():
        anchor_idx_by_tf[tf] = _resolve_anchor_idx(df, anchor_ts)

    # Build context
    try:
        provider = ReplayStructureProvider()
        ctx = provider.build(
            ohlc_by_timeframe=ohlc_by_tf,
            anchor_ts=anchor_ts,
            anchor_idx_by_timeframe=anchor_idx_by_tf,
        )
    except Exception as exc:
        logger.exception("Context build failed")
        raise HTTPException(status_code=500, detail=f"Context build failed: {exc}")

    # Run selected engine
    try:
        if req.engine == "rule":
            engine = SmartRuleEngine(
                balance=req.balance,
                risk_pct=req.risk_pct,
                min_rr=req.min_rr,
            )
        else:  # llm
            engine = LLMDecisionEngine(
                balance=req.balance,
                risk_pct=req.risk_pct,
                min_rr=req.min_rr,
            )
        setup = engine.decide(ctx)
    except Exception as exc:
        logger.exception(f"{req.engine} engine failed")
        raise HTTPException(status_code=500, detail=f"{req.engine} engine failed: {exc}")

    # Extract regime & event info dari context
    regime = (ctx.regime or {}).get("overall_regime", "unknown")
    event_proximity = "none"
    if (ctx.events or {}).get("should_avoid_trading"):
        event_proximity = "pre_event"
    elif (ctx.events or {}).get("next_high_impact"):
        next_ev = ctx.events["next_high_impact"]
        if isinstance(next_ev, dict):
            hours = next_ev.get("hours_until", 24) or 24
            event_proximity = "near_event" if hours < 6 else "none"

    return DecisionResponse(
        success=True,
        engine=req.engine,
        signal=setup.signal.value,
        entry_price=setup.entry_price,
        sl=setup.sl,
        tp1=setup.tp1,
        tp2=setup.tp2,
        lot_size=setup.lot_size,
        risk_pct=setup.risk_pct,
        rr_ratio=setup.rr_ratio,
        confidence=setup.confidence,
        reasoning=setup.reasoning,
        confluences=setup.confluences,
        filters_applied=setup.filters_applied,
        block_reason=setup.block_reason,
        regime=regime,
        event_proximity=event_proximity,
    )


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check untuk replay decision services."""
    return {
        "status": "ok" if _ENGINES_AVAILABLE else "degraded",
        "engines_available": _ENGINES_AVAILABLE,
        "supported_engines": ["rule", "llm"],
        "repo_root": _REPO_ROOT,
    }
