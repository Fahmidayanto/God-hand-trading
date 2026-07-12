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
