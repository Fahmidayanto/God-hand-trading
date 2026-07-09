import pytest
from unittest.mock import MagicMock
from valuecell.agents.orchestrator_agent import OrchestratorAgent


def test_orchestrator_v5_regression_logic_approved():
    """Test that Orchestrator correctly integrates v5 regression and applies lot multiplier + SL/TP override."""
    orchestrator = OrchestratorAgent(
        enable_market_structure=True,
        enable_ml_prediction=True,
        enable_risk_management=True,
        enable_sentiment=False,
        consensus_threshold=0.60
    )

    # MSA returns BUY
    orchestrator.agents["market_structure"].analyze = MagicMock(return_value={
        "signal": "BUY",
        "confidence": 0.80,
        "reasoning": "Valid structure BUY",
    })

    # ML returns v5 regression BUY with RR >= 1.8 (triggers 4x Lot multiplier)
    orchestrator.agents["ml_prediction"].analyze = MagicMock(return_value={
        "signal": "BUY",
        "confidence": 0.90,
        "reasoning": "Model predicts R:R = 1.9",
        "predicted_mfe": 2000.0, # 20.00 USD
        "predicted_mae": 1000.0, # 10.00 USD
        "expected_rr": 2.0,
        "model_type": "regression_v5"
    })

    # Mock risk management agent baseline lot sizing calculation
    rm = orchestrator.agents["risk_management"]
    rm.analyze = MagicMock(return_value={
        "approved": True,
        "lot_size": 0.1,
        "risk_pct": 1.0,
        "risk_usd": 10.0,
        "entry_price": 2300.0,
        "sl_price": 2290.0,
        "tp_price": 2310.0,
        "sl_distance_pips": 100.0,
        "tp_distance_pips": 100.0,
        "rr_ratio": 1.0
    })
    
    # Dummy market data
    market_data = {
        "df": None,
        "current_bar": {"time": 123456789, "close": 2300.0},
        "session": "London"
    }

    result = orchestrator.analyze(market_data, symbol="XAUUSD", timeframe="M15")

    # Assertions for v5 dynamic output
    assert result["approved"] is True
    assert result["final_signal"] == "BUY"
    
    # Lot sizing: 0.1 baseline * 4x multiplier = 0.4 lot
    assert result["position_sizing"]["lot_size"] == 0.4
    assert result["position_sizing"]["multiplier"] == 4.0
    
    # SL/TP prices:
    # Entry: 2300.0
    # SL: Entry - (MAE / 100.0) = 2300 - 10 = 2290.00
    # TP: Entry + (MFE / 100.0) = 2300 + 20 = 2320.00
    assert result["sl_tp"]["sl_price"] == 2290.0
    assert result["sl_tp"]["tp_price"] == 2320.0
    assert result["sl_tp"]["rr_ratio"] == 2.0


def test_orchestrator_v5_regression_logic_rejected():
    """Test that Orchestrator filters the setup when ML Expected R:R is below threshold (< 1.05)."""
    orchestrator = OrchestratorAgent(
        enable_market_structure=True,
        enable_ml_prediction=True,
        enable_risk_management=True,
        enable_sentiment=False,
        consensus_threshold=0.60
    )

    # MSA returns BUY
    orchestrator.agents["market_structure"].analyze = MagicMock(return_value={
        "signal": "BUY",
        "confidence": 0.80,
        "reasoning": "Valid structure BUY",
    })

    # ML returns HOLD (RR = 0.8 < 1.05 threshold)
    orchestrator.agents["ml_prediction"].analyze = MagicMock(return_value={
        "signal": "HOLD",
        "confidence": 0.30,
        "reasoning": "Model predicts low expected R:R",
        "predicted_mfe": 400.0,
        "predicted_mae": 500.0,
        "expected_rr": 0.8,
        "model_type": "regression_v5"
    })

    # Dummy market data
    market_data = {
        "df": None,
        "current_bar": {"time": 123456789, "close": 2300.0},
        "session": "London"
    }

    result = orchestrator.analyze(market_data, symbol="XAUUSD", timeframe="M15")

    # Consensus must filter this setup
    assert result["approved"] is False
