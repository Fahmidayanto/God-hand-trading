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
