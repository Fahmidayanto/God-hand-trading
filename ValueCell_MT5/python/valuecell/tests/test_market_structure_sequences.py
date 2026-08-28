import pandas as pd
import pytest

from valuecell.agents.market_structure_agent import AgentPhase, MarketStructureAgent


def event(time, event_type, direction, price=2300.0):
    return {
        "time": time,
        "type": event_type,
        "direction": direction,
        "price": price,
        "timeframe": "M15",
        "status": "Confirmed",
    }


def frame(close, ema200):
    return pd.DataFrame({"close": [close], "ema200": [ema200]})


def analyze(agent, events, bullish=True):
    close, ema = (2400.0, 2200.0) if bullish else (2200.0, 2400.0)
    df = frame(close, ema)
    return agent.analyze(
        df_m15=df,
        df_h1=df,
        df_h4=df,
        structure_events=events,
        session="London",
    )


class CapturingPatternMatcher:
    def __init__(self):
        self.query = None

    def find_similar_patterns(self, **kwargs):
        self.query = kwargs
        return {
            "patterns": [],
            "win_rate": 0.0,
            "avg_profit": 0.0,
            "total_count": 0,
            "completed_count": 0,
        }


def test_pending_setup_uses_market_event_timestamp_and_price_ratio():
    agent = MarketStructureAgent(use_patterns=False)
    matcher = CapturingPatternMatcher()
    agent.use_patterns = True
    agent.pattern_matcher = matcher
    events = [
        event(1, "LL", "Update"),
        event(2, "CHoCH", "Bullish"),
        event(3, "HH", "Update", price=3378.6),
    ]
    df = frame(3380.0, 3350.0)

    result = agent.analyze(
        df_m15=df,
        df_h1=df,
        df_h4=df,
        structure_events=events,
        session="London",
        price_ratio=0.751111,
    )

    assert matcher.query["timestamp"] == 3
    assert matcher.query["price_ratio"] == pytest.approx(0.751111)
    assert result["pre_signal"]["market_event_timestamp"] == 3
    assert result["metadata"]["price_ratio"] == pytest.approx(0.751111)


def test_pending_setup_builds_stable_llm_evidence_snapshot():
    agent = MarketStructureAgent(use_patterns=False)
    events = [
        event(1, "LL", "Update", price=3300.0),
        event(2, "CHoCH", "Bullish", price=3340.0),
        event(3, "HH", "Update", price=3378.6),
    ]
    df_m15 = pd.DataFrame({
        "open": [3360.0],
        "high": [3385.0],
        "low": [3355.0],
        "close": [3380.0],
        "ema200": [3350.0],
        "atr": [24.0],
    })
    df_h1 = frame(3380.0, 3320.0)
    df_h4 = frame(3380.0, 3290.0)

    first = agent.analyze(
        df_m15=df_m15,
        df_h1=df_h1,
        df_h4=df_h4,
        structure_events=events,
        session="London",
        price_ratio=0.751111,
    )
    snapshot = first["evidence_snapshot"]

    assert snapshot["schema_version"] == "msa-evidence-v1"
    assert snapshot["setup_id"] == first["pre_signal"]["setup_id"]
    assert snapshot["market_event_timestamp"] == 3
    assert snapshot["market_context"]["ema200"] == {
        "M15": 3350.0,
        "H1": 3320.0,
        "H4": 3290.0,
    }
    assert snapshot["market_context"]["atr"]["value"] == pytest.approx(24.0)
    assert snapshot["market_context"]["candle_quality"]["body_ratio"] == pytest.approx(20 / 30)
    assert snapshot["structure_context"]["raw_distance_to_trigger"] == pytest.approx(1.4)
    assert snapshot["structure_context"]["price_ratio_scaled_distance"] == pytest.approx(1.4 / 0.751111)
    assert snapshot["llm_constraints"]["may_create_trade_signal"] is False
    assert snapshot["llm_constraints"]["may_change_msa_state"] is False

    agent.reset_state()
    second = agent.analyze(
        df_m15=df_m15,
        df_h1=df_h1,
        df_h4=df_h4,
        structure_events=events,
        session="London",
        price_ratio=0.751111,
    )
    assert second["evidence_snapshot"]["setup_id"] == snapshot["setup_id"]


@pytest.mark.parametrize(
    ("choch_direction", "setup_type", "counter_type", "bos_direction", "signal"),
    [
        ("Bullish", "HH", "LL", "Bullish", "BUY"),
        ("Bearish", "LL", "HH", "Bearish", "SELL"),
    ],
)
def test_counter_swing_does_not_overwrite_pending_setup(
    choch_direction, setup_type, counter_type, bos_direction, signal
):
    agent = MarketStructureAgent(use_patterns=False)
    seed = [event(1, "LL", "Update"), event(2, "HH", "Update")]
    choch = event(3, "CHoCH", choch_direction)
    setup = event(4, setup_type, "Update")
    counter = event(5, counter_type, "Update")
    bos = event(6, "BoS", bos_direction)

    pending = analyze(agent, seed + [choch, setup], bullish=signal == "BUY")
    assert pending["phase"] == AgentPhase.PENDING_SETUP.value
    assert agent.get_pending_setup()["direction"] == choch_direction

    analyze(agent, seed + [choch, setup, counter], bullish=signal == "BUY")
    assert agent.get_pending_setup()["direction"] == choch_direction

    triggered = analyze(agent, seed + [choch, setup, counter, bos], bullish=signal == "BUY")
    assert triggered["signal"] == signal
    assert triggered["phase"] == AgentPhase.BOS_TRIGGERED.value


def test_newer_opposite_choch_blocks_stale_setup_direction():
    agent = MarketStructureAgent(use_patterns=False)
    events = [
        event(1, "HH", "Update"),
        event(2, "CHoCH", "Bearish"),
        event(3, "LL", "Update"),
        event(4, "CHoCH", "Bullish"),
        event(5, "LL", "Update"),
    ]

    result = analyze(agent, events)

    assert result["signal"] == "HOLD"
    assert result["pre_signal"] is None
    assert agent.get_pending_setup() is None


def test_bos_ends_old_choch_cycle():
    agent = MarketStructureAgent(use_patterns=False)
    events = [
        event(1, "LL", "Update"),
        event(2, "CHoCH", "Bullish"),
        event(3, "HH", "Update"),
        event(4, "BoS", "Bullish"),
        event(5, "HH", "Update"),
    ]

    result = analyze(agent, events)

    assert result["signal"] == "HOLD"
    assert result["pre_signal"] is None
    assert agent.get_pending_setup() is None
