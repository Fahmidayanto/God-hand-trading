import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.services.orchestrator_simulator import reconstruct_market_data
import pandas as pd

def _candles():
    base = 1_700_000_000
    return [
        {"time": base + i * 60, "open": 100 + i, "high": 101 + i, "low": 99 + i,
         "close": 100 + i, "volume": 10, "ema200": 100.0}
        for i in range(5)
    ]

def test_reconstruct_market_data():
    candles = _candles()
    df = pd.DataFrame(candles)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df["high_low"] = df["high"] - df["low"]
    md = reconstruct_market_data(df, candles[-1]["time"], [])
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

import app.services.orchestrator_simulator as sim_mod

class FakeOrchestrator:
    def analyze(self, market_data, symbol="XAUUSD", timeframe="M15"):
        return {
            "approved": True,
            "final_signal": "BUY",
            "final_confidence": 0.8,
            "consensus_level": "strong",
            "agent_results": {
                "market_structure": {"signal": "BUY", "confidence": 0.7},
                "ml_prediction": {"signal": "BUY", "confidence": 0.8},
                "sentiment": {"final_signal": "BUY", "confidence": 0.75,
                              "confidence_adjustment": 0.05, "filtered": False},
                "risk_management": {"signal": "BUY", "confidence": 0.8, "approved": True},
            },
            "sl_tp": {"sl_price": 98.0, "tp_price": 105.0},
            "position_sizing": {"lot_size": 0.1},
        }

def test_run_simulation_mocked(monkeypatch):
    monkeypatch.setattr(sim_mod, "get_orchestrator", lambda: FakeOrchestrator())
    candles = [{"time": 1_700_000_000 + i * 60, "open": 100 + i, "high": 102 + i,
                "low": 98 + i, "close": 101 + i, "volume": 10, "ema200": 100.0}
               for i in range(10)]
    events = [{"type": "BOS", "direction": "bullish", "price": 101.0,
               "time": candles[3]["time"], "timeframe": "M15", "status": "active",
               "previous_price": 100.0, "previous_time": candles[2]["time"]}]
    result = sim_mod.run_simulation(candles, events, [], symbol="XAUUSD", timeframe="M15")
    assert len(result["signals"]) == 1
    sig = result["signals"][0]
    assert sig["signal"] == "BUY"
    assert sig["outcome"] in ("TP", "SL", "NONE")
    assert "win_rate" in result["metrics"]
    # Frame capture (new requirement).
    assert len(result["frames"]) >= 1
    assert set(result["frames"][0]["agents"].keys()) == {
        "market_structure", "ml_prediction", "sentiment", "risk_management"}
    assert result["frames"][0]["agents"]["market_structure"]["status"] == "fired"
    assert result["frames"][0]["agents"]["risk_management"]["approved"] is True
    # Trade execution context must reach the frame so the frontend
    # TradesOverlayPrimitive can draw SL/TP zones. Regression guard.
    frame = result["frames"][0]
    assert frame["sl_tp"] == {"sl_price": 98.0, "tp_price": 105.0}
    assert frame["position_sizing"] == {"lot_size": 0.1}
    assert frame["event_price"] == events[0]["price"]


def test_run_simulation_filters_trigger_types(monkeypatch):
    monkeypatch.setattr(sim_mod, "get_orchestrator", lambda: FakeOrchestrator())
    candles = [{"time": 1_700_000_000 + i * 60, "open": 100 + i, "high": 102 + i,
                "low": 98 + i, "close": 101 + i, "volume": 10, "ema200": 100.0}
               for i in range(10)]
    types = ["LH", "HL", "BOS"]
    events = [{"type": t, "direction": "bullish", "price": 101.0,
               "time": candles[3 + i]["time"], "timeframe": "M15", "status": "active",
               "previous_price": 100.0, "previous_time": candles[2 + i]["time"]}
              for i, t in enumerate(types)]
    result = sim_mod.run_simulation(candles, events, [], symbol="XAUUSD", timeframe="M15")
    # Only BOS is a trigger type; LH and HL must be filtered out.
    assert len(result["frames"]) == 1
    assert result["frames"][0]["event_type"] == "BOS"


def test_run_simulation_caps_events(monkeypatch):
    monkeypatch.setattr(sim_mod, "get_orchestrator", lambda: FakeOrchestrator())
    candles = [{"time": 1_700_000_000 + i * 60, "open": 100 + i, "high": 102 + i,
                "low": 98 + i, "close": 101 + i, "volume": 10, "ema200": 100.0}
                for i in range(50)]
    events = [{"type": "BOS", "direction": "bullish", "price": 101.0,
                "time": candles[3 + i]["time"], "timeframe": "M15", "status": "active",
                "previous_price": 100.0, "previous_time": candles[2 + i]["time"]}
               for i in range(10)]
    # With max_events=3 only the first 3 events should produce signals (orchestrator
    # approves every event), bounding the work regardless of total event count.
    result = sim_mod.run_simulation(candles, events, [], max_events=3)
    assert len(result["signals"]) == 3


class SkippedOrchestrator:
    """Returns approved=True but with no per-agent results (all agents skipped)."""
    def analyze(self, market_data, symbol="XAUUSD", timeframe="M15"):
        return {
            "approved": True,
            "final_signal": "BUY",
            "final_confidence": 0.8,
            "consensus_level": "strong",
            "agent_results": {},
        }


def test_build_frame_skipped(monkeypatch):
    monkeypatch.setattr(sim_mod, "get_orchestrator", lambda: SkippedOrchestrator())
    candles = [{"time": 1_700_000_000 + i * 60, "open": 100 + i, "high": 102 + i,
                "low": 98 + i, "close": 101 + i, "volume": 10, "ema200": 100.0}
               for i in range(10)]
    events = [{"type": "BOS", "direction": "bullish", "price": 101.0,
                "time": candles[3]["time"], "timeframe": "M15", "status": "active",
                "previous_price": 100.0, "previous_time": candles[2]["time"]}]
    result = sim_mod.run_simulation(candles, events, [], symbol="XAUUSD", timeframe="M15")
    assert len(result["frames"]) == 1
    frame = result["frames"][0]
    for key in ("market_structure", "ml_prediction", "sentiment", "risk_management"):
        assert frame["agents"][key]["status"] == "skipped"


class ErrorOrchestrator:
    def analyze(self, market_data, symbol="XAUUSD", timeframe="M15"):
        raise RuntimeError("boom")


def test_build_frame_error(monkeypatch):
    monkeypatch.setattr(sim_mod, "get_orchestrator", lambda: ErrorOrchestrator())
    candles = [{"time": 1_700_000_000 + i * 60, "open": 100 + i, "high": 102 + i,
                "low": 98 + i, "close": 101 + i, "volume": 10, "ema200": 100.0}
               for i in range(10)]
    events = [{"type": "BOS", "direction": "bullish", "price": 101.0,
                "time": candles[3]["time"], "timeframe": "M15", "status": "active",
                "previous_price": 100.0, "previous_time": candles[2]["time"]}]
    result = sim_mod.run_simulation(candles, events, [], symbol="XAUUSD", timeframe="M15")
    assert len(result["frames"]) >= 1
    assert result["frames"][0]["agents"]["market_structure"]["status"] == "error"


def test_run_simulation_empty():
    result = sim_mod.run_simulation([], [], [])
    assert result["frames"] == []
    assert result["signals"] == []


def test_run_simulation_cap_after_filter(monkeypatch):
    monkeypatch.setattr(sim_mod, "get_orchestrator", lambda: FakeOrchestrator())
    candles = [{"time": 1_700_000_000 + i * 60, "open": 100 + i, "high": 102 + i,
                "low": 98 + i, "close": 101 + i, "volume": 10, "ema200": 100.0}
               for i in range(20)]
    # 4 non-trigger (LH) events followed by 3 trigger (BOS) events. With
    # max_events=5, the cap must apply to the filtered trigger list, so all 3
    # BOS frames must survive (not 0 from capping raw, not all 4 LH dropped).
    events = [
        {"type": "LH", "direction": "bearish", "price": 101.0,
         "time": candles[1 + i]["time"], "timeframe": "M15", "status": "active",
         "previous_price": 100.0, "previous_time": candles[i]["time"]}
        for i in range(4)
    ]
    events += [
        {"type": "BOS", "direction": "bullish", "price": 101.0,
         "time": candles[6 + i]["time"], "timeframe": "M15", "status": "active",
         "previous_price": 100.0, "previous_time": candles[5 + i]["time"]}
        for i in range(3)
    ]
    result = sim_mod.run_simulation(candles, events, [], max_events=5)
    assert len(result["frames"]) == 3
    assert all(f["event_type"] == "BOS" for f in result["frames"])

from app.main import app
from fastapi.testclient import TestClient

class FakeOrchestrator:
    def analyze(self, market_data, symbol="XAUUSD", timeframe="M15"):
        return {"approved": True, "final_signal": "BUY", "final_confidence": 0.8,
                "consensus_level": "strong", "sl_tp": {"sl_price": 98.0, "tp_price": 105.0},
                "position_sizing": {"lot_size": 0.1},
                "agent_results": {
                    "market_structure": {"signal": "BUY", "confidence": 0.7},
                    "ml_prediction": {"signal": "BUY", "confidence": 0.8},
                    "sentiment": {"final_signal": "BUY", "confidence": 0.75,
                                  "confidence_adjustment": 0.05, "filtered": False},
                    "risk_management": {"signal": "BUY", "confidence": 0.8, "approved": True},
                }}

def test_simulate_endpoint(monkeypatch):
    monkeypatch.setattr(sim_mod, "get_orchestrator", lambda: FakeOrchestrator())

    class FakeCursor:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        # Route: execute() stores rows for the current query; fetchall() returns them.
        def execute(self, q, params=None):
            if "marketdata" in q:
                self._rows = candle_rows
            elif "llhhbos" in q:
                self._rows = struct_rows
            else:
                self._rows = trade_rows
        def fetchall(self):
            return self._rows
    candle_rows = [(__import__("datetime").datetime(2024,1,1,0,0), 100,102,98,101,10,100.0)]
    struct_rows = [("BOS","bullish",101.0,__import__("datetime").datetime(2024,1,1,0,0),"M15","active",100.0,__import__("datetime").datetime(2024,1,1,0,0))]
    trade_rows = [("T1","BUY",100.0,105.0,98.0,200.0,2.0,"Asia",__import__("datetime").datetime(2024,1,1,0,0),__import__("datetime").datetime(2024,1,1,1,0),0.1)]

    class FakeConn:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def cursor(self): return FakeCursor()
    monkeypatch.setattr("app.core.database.get_db_conn", lambda: FakeConn())
    monkeypatch.setattr("app.core.database.is_pool_ready", lambda: True)

    client = TestClient(app)
    r = client.get("/api/v1/trading/simulate", params={
        "year_from": 2024, "month_from": 1, "year_to": 2024, "month_to": 1, "timeframe": "M15"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "signals" in body and "metrics" in body
    assert isinstance(body["signals"], list)
    assert "win_rate" in body["metrics"]
    assert "frames" in body
    assert isinstance(body["frames"], list)
