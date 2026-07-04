import pytest
from unittest.mock import MagicMock, patch
from valuecell.agents.orchestrator_agent import OrchestratorAgent


def test_warmup_skipped_on_normal_hold():
    """Test that ML & Sentiment agents are NOT called when MSA returns HOLD without pre_signal."""
    # Initialize Orchestrator
    orchestrator = OrchestratorAgent(
        enable_market_structure=True,
        enable_ml_prediction=True,
        enable_risk_management=True,
        enable_sentiment=True,
        consensus_threshold=0.60
    )

    # Mock agents
    orchestrator.agents["market_structure"].analyze = MagicMock(return_value={
        "signal": "HOLD",
        "confidence": 0.30,
        "reasoning": "Normal neutral state",
        "pre_signal": None
    })
    orchestrator.agents["ml_prediction"].analyze = MagicMock()
    orchestrator.agents["sentiment"].analyze = MagicMock()
    orchestrator.agents["risk_management"].analyze = MagicMock()

    # Dummy market data
    market_data = {
        "df": None,
        "current_bar": {"time": 123456789, "close": 2300.0},
        "session": "London"
    }

    # Run analysis
    result = orchestrator.analyze(market_data, symbol="XAUUSD", timeframe="M15")

    # Assertions
    assert result["final_signal"] == "HOLD"
    assert result["approved"] is False
    orchestrator.agents["ml_prediction"].analyze.assert_not_called()
    orchestrator.agents["sentiment"].analyze.assert_not_called()
    orchestrator.agents["risk_management"].analyze.assert_not_called()


def test_warmup_triggered_on_pending_setup():
    """Test that ML & Sentiment agents ARE called for warmup when MSA returns HOLD with pre_signal."""
    # Initialize Orchestrator
    orchestrator = OrchestratorAgent(
        enable_market_structure=True,
        enable_ml_prediction=True,
        enable_risk_management=True,
        enable_sentiment=True,
        consensus_threshold=0.60
    )

    # Mock agents
    orchestrator.agents["market_structure"].analyze = MagicMock(return_value={
        "signal": "HOLD",
        "confidence": 0.40,
        "reasoning": "CHoCH + HH formed, pending setup",
        "pre_signal": {
            "direction": "Bullish",
            "initial_confidence": 0.40,
            "status": "PENDING_SETUP - menunggu BoS"
        }
    })
    
    # ML prediction mock
    orchestrator.agents["ml_prediction"].analyze = MagicMock(return_value={
        "signal": "BUY",
        "confidence": 0.75,
        "probability": 0.75,
        "reasoning": "ML matches historical structures"
    })
    
    # Sentiment mock
    orchestrator.agents["sentiment"].analyze = MagicMock(return_value={
        "final_signal": "BUY",
        "final_confidence": 0.80,
        "confidence_adjustment": 0.05,
        "filtered": False
    })
    
    orchestrator.agents["risk_management"].analyze = MagicMock()

    # Dummy market data
    market_data = {
        "df": None,
        "current_bar": {"time": 123456789, "close": 2300.0},
        "session": "London"
    }

    # Run analysis
    result = orchestrator.analyze(market_data, symbol="XAUUSD", timeframe="M15")

    # Assertions
    # Final signal must still be HOLD (no real trigger yet)
    assert result["final_signal"] == "HOLD"
    assert result["approved"] is False
    
    # ML & Sentiment should be called for warmup
    orchestrator.agents["ml_prediction"].analyze.assert_called_once()
    # Check that warmup signal is translated to "BUY" (Bullish -> BUY)
    args, kwargs = orchestrator.agents["ml_prediction"].analyze.call_args
    assert kwargs.get("structure_signal") == "BUY"
    
    # Sentiment should be called with warmup info
    orchestrator.agents["sentiment"].analyze.assert_called_once()
    args_sent, kwargs_sent = orchestrator.agents["sentiment"].analyze.call_args
    assert kwargs_sent.get("signal") == "BUY"
    assert kwargs_sent.get("confidence") == 0.75  # from ML confidence
    
    # Risk management should not be called since consensus is HOLD/not approved
    orchestrator.agents["risk_management"].analyze.assert_not_called()
