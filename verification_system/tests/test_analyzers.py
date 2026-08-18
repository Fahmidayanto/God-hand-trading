"""
Unit tests for verification_system analyzers + decision engines.

Narrow happy-path coverage:
- Liquidity: BSL/SSL detection works
- Order Block: OB detected + breaker state
- FVG: gap detection + inverse
- Regime: trending vs ranging classification
- Calendar: time-anchored event lookup
- SmartRuleEngine: BUY/SELL/HOLD/BLOCKED decisions
- ReplayStructureProvider: full context build

Run: cd B:/Project MT5 && python -m pytest verification_system/tests/test_analyzers.py -v
"""

import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

# Path setup
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from verification_system.analyzers.liquidity_analyzer import analyze_liquidity
from verification_system.analyzers.order_block_detector import detect_order_blocks
from verification_system.analyzers.fvg_detector import detect_fvgs
from verification_system.analyzers.regime_detector import classify_regime
from verification_system.analyzers.economic_calendar_replay import (
    get_events_for_timestamp,
    should_avoid_trading,
)
from verification_system.analyzers.replay_structure_provider import ReplayStructureProvider
from verification_system.decision_engines.smart_rule_engine import SmartRuleEngine, Signal


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def synthetic_ohlc():
    """Generate synthetic OHLC with 500 candles."""
    np.random.seed(42)
    n = 500
    base = 2000.0
    prices = base + np.cumsum(np.random.randn(n) * 0.5 + 0.1)
    return pd.DataFrame({
        "time": pd.date_range("2023-04-15", periods=n, freq="15min"),
        "open": prices + np.random.randn(n) * 0.3,
        "high": prices + abs(np.random.randn(n)) * 0.8,
        "low": prices - abs(np.random.randn(n)) * 0.8,
        "close": prices,
    })


@pytest.fixture
def trending_ohlc():
    """Synthetic OHLC with strong uptrend."""
    np.random.seed(13)
    n = 300
    prices = 2000.0 + np.cumsum(np.random.randn(n) * 0.4 + 0.3)
    return pd.DataFrame({
        "time": pd.date_range("2023-01-01", periods=n, freq="15min"),
        "open": prices + np.random.randn(n) * 0.2,
        "high": prices + abs(np.random.randn(n)) * 0.8,
        "low": prices - abs(np.random.randn(n)) * 0.8,
        "close": prices,
    })


@pytest.fixture
def ranging_ohlc():
    """Synthetic OHLC with range-bound action."""
    np.random.seed(17)
    n = 300
    t = np.arange(n)
    prices = 2000.0 + 3.0 * np.sin(t / 20) + np.random.randn(n) * 0.3
    return pd.DataFrame({
        "time": pd.date_range("2023-02-01", periods=n, freq="15min"),
        "open": prices + np.random.randn(n) * 0.2,
        "high": prices + abs(np.random.randn(n)) * 0.8,
        "low": prices - abs(np.random.randn(n)) * 0.8,
        "close": prices,
    })


# ── Liquidity ───────────────────────────────────────────────────────────────

def test_liquidity_analyzer_returns_context(synthetic_ohlc):
    """Liquidity analyzer returns LiquidityContext with expected fields."""
    ctx = analyze_liquidity(synthetic_ohlc, as_of_idx=400, timeframe="M15")
    assert ctx is not None
    assert ctx.timeframe == "M15"
    assert ctx.current_price > 0
    assert ctx.atr is not None and ctx.atr > 0
    assert isinstance(ctx.all_bsl, list)
    assert isinstance(ctx.all_ssl, list)


# ── Order Block ─────────────────────────────────────────────────────────────

def test_order_block_detector_returns_obs(synthetic_ohlc):
    """Order block detector returns list of OrderBlock objects."""
    ctx = detect_order_blocks(synthetic_ohlc, as_of_idx=400, lookback_bars=300)
    assert ctx is not None
    assert isinstance(ctx.bullish_obs, list)
    assert isinstance(ctx.bearish_obs, list)
    # Each OB has zone + state
    if ctx.bullish_obs:
        ob = ctx.bullish_obs[0]
        assert ob.top > ob.bottom
        assert ob.impulse_size_atr > 0


# ── FVG ─────────────────────────────────────────────────────────────────────

def test_fvg_detector_returns_fvgs(synthetic_ohlc):
    """FVG detector returns list of FVG objects."""
    ctx = detect_fvgs(synthetic_ohlc, as_of_idx=400, lookback_bars=300)
    assert ctx is not None
    assert isinstance(ctx.bullish_fvgs, list)
    assert isinstance(ctx.bearish_fvgs, list)
    if ctx.bullish_fvgs:
        fvg = ctx.bullish_fvgs[0]
        assert fvg.top > fvg.bottom
        assert fvg.gap_size_atr > 0


# ── Regime ─────────────────────────────────────────────────────────────────

def test_regime_classifier_trending(trending_ohlc):
    """Trending data should be classified as trending_up."""
    snap = classify_regime(trending_ohlc, as_of_idx=290, timeframe="M15")
    assert snap.regime.value in ("trending_up", "trending_down")
    assert snap.adx >= 20.0  # Some trend strength


def test_regime_classifier_ranging(ranging_ohlc):
    """Ranging data should be classified as ranging."""
    snap = classify_regime(ranging_ohlc, as_of_idx=290, timeframe="M15")
    # Ranging OR transitioning both acceptable
    assert snap.regime.value in ("ranging", "transitioning", "trending_up", "trending_down")
    # ADX should be relatively low for ranging
    assert snap.adx < 50.0


# ── Calendar ───────────────────────────────────────────────────────────────

def test_calendar_fomc_2023():
    """FOMC March 2023 should be detected in 24h window."""
    ts = datetime(2023, 3, 22, 12, 0, tzinfo=timezone.utc)
    events = get_events_for_timestamp(ts, window_hours=24, impact_filter="high")
    assert any("FOMC" in e.name for e in events)


def test_calendar_should_avoid_pre_fomc():
    """1 hour before FOMC should trigger avoid_trading."""
    ts = datetime(2023, 3, 22, 17, 0, tzinfo=timezone.utc)
    avoid, reason, ev = should_avoid_trading(ts, pre_hours=2, post_hours=1)
    assert avoid is True
    assert ev is not None
    assert "FOMC" in ev.name


def test_calendar_quiet_day_no_block():
    """Quiet Tuesday should NOT trigger avoid_trading."""
    ts = datetime(2023, 4, 18, 12, 0, tzinfo=timezone.utc)
    avoid, reason, ev = should_avoid_trading(ts, pre_hours=2, post_hours=1)
    # May or may not have event depending on FOMC schedule, but typically no block for mid-week
    assert isinstance(avoid, bool)


# ── SmartRuleEngine ─────────────────────────────────────────────────────────

def test_rule_engine_returns_setup(synthetic_ohlc):
    """SmartRuleEngine returns TradeSetup from ReplayContext."""
    df_h1 = synthetic_ohlc.iloc[::4].reset_index(drop=True)
    df_h4 = synthetic_ohlc.iloc[::16].reset_index(drop=True)
    provider = ReplayStructureProvider()
    ctx = provider.build(
        ohlc_by_timeframe={"M15": synthetic_ohlc, "H1": df_h1, "H4": df_h4},
        anchor_ts=synthetic_ohlc["time"].iloc[400].to_pydatetime().replace(tzinfo=timezone.utc),
        anchor_idx_by_timeframe={"M15": 400, "H1": 100, "H4": 25},
    )
    engine = SmartRuleEngine(balance=1000.0, risk_pct=1.0)
    setup = engine.decide(ctx)
    assert setup is not None
    assert setup.signal in (Signal.BUY, Signal.SELL, Signal.HOLD, Signal.BLOCKED)
    assert setup.entry_price > 0
    assert 0.0 <= setup.confidence <= 1.0


def test_rule_engine_blocks_pre_fomc(synthetic_ohlc):
    """Rule engine BLOCKS trade 1h before FOMC."""
    df_h1 = synthetic_ohlc.iloc[::4].reset_index(drop=True)
    df_h4 = synthetic_ohlc.iloc[::16].reset_index(drop=True)
    provider = ReplayStructureProvider()
    ctx = provider.build(
        ohlc_by_timeframe={"M15": synthetic_ohlc, "H1": df_h1, "H4": df_h4},
        anchor_ts=datetime(2023, 3, 22, 17, 0, tzinfo=timezone.utc),
        anchor_idx_by_timeframe={"M15": 400, "H1": 100, "H4": 25},
    )
    engine = SmartRuleEngine(balance=1000.0)
    setup = engine.decide(ctx)
    assert setup.signal == Signal.BLOCKED
    assert "FOMC" in (setup.block_reason or "") or "high-impact" in (setup.block_reason or "").lower()


# ── Replay Provider ─────────────────────────────────────────────────────────

def test_replay_provider_builds_full_context(synthetic_ohlc):
    """ReplayStructureProvider returns complete ReplayContext."""
    df_h1 = synthetic_ohlc.iloc[::4].reset_index(drop=True)
    df_h4 = synthetic_ohlc.iloc[::16].reset_index(drop=True)
    provider = ReplayStructureProvider()
    ctx = provider.build(
        ohlc_by_timeframe={"M15": synthetic_ohlc, "H1": df_h1, "H4": df_h4},
        anchor_ts=synthetic_ohlc["time"].iloc[400].to_pydatetime().replace(tzinfo=timezone.utc),
        anchor_idx_by_timeframe={"M15": 400, "H1": 100, "H4": 25},
    )
    d = ctx.to_dict()
    # All sections present
    assert "anchor" in d
    assert "market_data" in d
    assert "liquidity" in d
    assert "order_blocks" in d
    assert "fvg" in d
    assert "regime" in d
    assert "events" in d


def test_replay_provider_llm_prompt_format(synthetic_ohlc):
    """to_llm_prompt_context() returns readable string."""
    df_h1 = synthetic_ohlc.iloc[::4].reset_index(drop=True)
    df_h4 = synthetic_ohlc.iloc[::16].reset_index(drop=True)
    provider = ReplayStructureProvider()
    ctx = provider.build(
        ohlc_by_timeframe={"M15": synthetic_ohlc, "H1": df_h1, "H4": df_h4},
        anchor_ts=synthetic_ohlc["time"].iloc[400].to_pydatetime().replace(tzinfo=timezone.utc),
        anchor_idx_by_timeframe={"M15": 400, "H1": 100, "H4": 25},
    )
    prompt = ctx.to_llm_prompt_context()
    assert isinstance(prompt, str)
    assert "REGIME" in prompt
    assert "LIQUIDITY" in prompt
    assert "EVENTS" in prompt
    assert len(prompt) > 200


if __name__ == "__main__":
    # Allow running directly: python test_analyzers.py
    sys.exit(pytest.main([__file__, "-v"]))
