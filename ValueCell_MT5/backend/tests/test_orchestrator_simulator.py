import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.services.orchestrator_simulator import reconstruct_market_data

def _candles():
    base = 1_700_000_000
    return [
        {"time": base + i * 60, "open": 100 + i, "high": 101 + i, "low": 99 + i,
         "close": 100 + i, "volume": 10, "ema200": 100.0}
        for i in range(5)
    ]

def test_reconstruct_market_data():
    candles = _candles()
    md = reconstruct_market_data(candles, candles[-1]["time"], [])
    assert "df" in md and "current_bar" in md
    assert md["current_bar"]["close"] == candles[-1]["close"]
    assert md["atr"] > 0
    assert md["session"] in ("Asia", "London", "NewYork", "Sydney")
    assert md["news_headlines"] == []

from app.services.orchestrator_simulator import forward_walk_outcome

def _fw_candles():
    base = 1_700_000_000
    return [{"time": base + i * 60, "high": 100 + i, "low": 100 - i} for i in range(10)]

def test_forward_walk_buy_tp():
    c = _fw_candles()
    r = forward_walk_outcome(c, c[0]["time"], "BUY", sl=90.0, tp=105.0)
    assert r["outcome"] == "TP"

def test_forward_walk_buy_sl():
    c = _fw_candles()
    r = forward_walk_outcome(c, c[0]["time"], "BUY", sl=95.0, tp=200.0)
    assert r["outcome"] == "SL"

def test_forward_walk_none():
    c = _fw_candles()
    r = forward_walk_outcome(c, c[0]["time"], "BUY", sl=50.0, tp=500.0, max_bars=5)
    assert r["outcome"] == "NONE"

from app.services.orchestrator_simulator import compute_metrics

def test_compute_metrics():
    signals = [
        {"signal": "BUY", "confidence": 0.7, "consensus": "strong", "outcome": "TP", "time": 100},
        {"signal": "SELL", "confidence": 0.6, "consensus": "moderate", "outcome": "SL", "time": 200},
        {"signal": "BUY", "confidence": 0.8, "consensus": "strong", "outcome": "NONE", "time": 300},
    ]
    bt = [{"type": "BUY", "entry_time": 100}, {"type": "SELL", "entry_time": 200}]
    m = compute_metrics(signals, bt)
    assert m["total_signals"] == 3
    assert m["wins"] == 1 and m["losses"] == 1
    assert abs(m["win_rate"] - 0.5) < 1e-9
    assert abs(m["avg_confidence"] - 0.7) < 1e-9
    assert m["matched_backtest_trades"] == 2
    assert abs(m["agreement_rate"] - (2 / 3)) < 1e-9
