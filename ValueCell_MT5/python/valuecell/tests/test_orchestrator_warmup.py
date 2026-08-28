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
    assert kwargs_sent.get("confidence") == 0.40  # from pre_signal initial_confidence in parallel execution
    
    # Risk management should not be called since consensus is HOLD/not approved
    orchestrator.agents["risk_management"].analyze.assert_not_called()


def test_warmup_results_caching_and_reuse():
    """Test that ML & Sentiment results are cached during warmup and reused in subsequent analyses until reset."""
    orchestrator = OrchestratorAgent(
        enable_market_structure=True,
        enable_ml_prediction=True,
        enable_risk_management=True,
        enable_sentiment=True,
        consensus_threshold=0.60
    )

    # Mock agents
    orchestrator.agents["market_structure"].analyze = MagicMock(side_effect=[
        # 1. Warmup initial event (HH)
        {
            "signal": "HOLD",
            "confidence": 0.40,
            "phase": "PENDING_SETUP",
            "pre_signal": {
                "direction": "Bullish",
                "initial_confidence": 0.40,
                "status": "PENDING_SETUP - menunggu BoS"
            }
        },
        # 2. Intermediate event (LL) - still in warmup
        {
            "signal": "HOLD",
            "confidence": 0.40,
            "phase": "PENDING_SETUP",
            "pre_signal": {
                "direction": "Bullish",
                "initial_confidence": 0.40,
                "status": "PENDING_SETUP - menunggu BoS"
            }
        },
        # 3. Reset event - setup invalidated
        {
            "signal": "HOLD",
            "confidence": 0.30,
            "phase": "IDLE",
            "pre_signal": None
        }
    ])

    orchestrator.agents["ml_prediction"].analyze = MagicMock(return_value={
        "signal": "BUY",
        "confidence": 0.75,
        "probability": 0.75,
        "reasoning": "ML matches historical structures"
    })
    orchestrator.agents["sentiment"].analyze = MagicMock(return_value={
        "final_signal": "BUY",
        "final_confidence": 0.80,
        "confidence_adjustment": 0.05,
        "filtered": False
    })
    orchestrator.agents["risk_management"].analyze = MagicMock()

    market_data = {
        "df": None,
        "current_bar": {"time": 123456789, "close": 2300.0},
        "session": "London"
    }

    # First run (HH) - should run ML and Sentiment analysis once
    result1 = orchestrator.analyze(market_data, symbol="XAUUSD", timeframe="M15")
    assert orchestrator._latest_warmup_results is not None
    orchestrator.agents["ml_prediction"].analyze.assert_called_once()
    orchestrator.agents["sentiment"].analyze.assert_called_once()

    # Second run (LL) - should reuse cache, NOT run ML and Sentiment again
    result2 = orchestrator.analyze(market_data, symbol="XAUUSD", timeframe="M15")
    assert orchestrator._latest_warmup_results is not None
    # Call count should still be 1 (meaning it was not called again)
    assert orchestrator.agents["ml_prediction"].analyze.call_count == 1
    assert orchestrator.agents["sentiment"].analyze.call_count == 1

    # Third run (Reset) - should clear the cache
    result3 = orchestrator.analyze(market_data, symbol="XAUUSD", timeframe="M15")
    assert orchestrator._latest_warmup_results is None


def test_llm_msa_shadow_result_is_reported_but_not_counted_in_consensus():
    orchestrator = OrchestratorAgent(
        enable_market_structure=True,
        enable_ml_prediction=False,
        enable_risk_management=False,
        enable_sentiment=False,
        enable_llm_msa=True,
    )
    orchestrator.agents["market_structure"].analyze = MagicMock(return_value={
        "signal": "HOLD",
        "confidence": 0.40,
        "phase": "PENDING_SETUP",
        "is_new_setup": True,
        "pre_signal": {
            "setup_id": "msa-shadow-1",
            "direction": "Bullish",
            "initial_confidence": 0.40,
        },
        "evidence_snapshot": {
            "schema_version": "msa-evidence-v1",
            "setup_id": "msa-shadow-1",
        },
    })
    orchestrator.agents["llm_msa"].analyze = MagicMock(return_value={
        "status": "pending",
        "mode": "SHADOW",
        "setup_id": "msa-shadow-1",
        "verdict": "PENDING",
        "can_affect_consensus": False,
        "can_create_trade_signal": False,
    })

    result = orchestrator.analyze({
        "df": None,
        "current_bar": {"time": 123456789, "close": 2300.0},
        "session": "London",
    })

    assert result["final_signal"] == "HOLD"
    assert result["vote_scores"] == {"BUY": 0.0, "SELL": 0.0, "HOLD": 0.1}
    assert result["agent_results"]["llm_msa"]["status"] == "pending"
    orchestrator.agents["llm_msa"].analyze.assert_called_once_with(
        orchestrator.agents["market_structure"].analyze.return_value["evidence_snapshot"]
    )


def test_llm_msa_completed_cache_is_exposed_on_next_same_setup_analysis():
    orchestrator = OrchestratorAgent(
        enable_market_structure=True,
        enable_ml_prediction=False,
        enable_risk_management=False,
        enable_sentiment=False,
        enable_llm_msa=True,
        llm_msa={
            "evaluator": lambda _evidence: {
                "verdict": "SUPPORT",
                "confidence": 0.81,
                "risk_flags": [],
                "supporting_factors": ["Historical execution edge"],
                "contradicting_factors": [],
                "historical_read": "Supportive",
                "reasoning": "Executed analogs support the pending direction.",
            }
        },
    )
    msa_result = {
        "signal": "HOLD",
        "confidence": 0.40,
        "phase": "PENDING_SETUP",
        "is_new_setup": False,
        "pre_signal": {"setup_id": "msa-cache-1", "direction": "Bullish"},
        "evidence_snapshot": {
            "schema_version": "msa-evidence-v1",
            "setup_id": "msa-cache-1",
        },
    }
    orchestrator.agents["market_structure"].analyze = MagicMock(return_value=msa_result)
    market_data = {
        "df": None,
        "current_bar": {"time": 123456789, "close": 2300.0},
        "session": "London",
    }

    first = orchestrator.analyze(market_data)
    assert first["agent_results"]["llm_msa"]["status"] in {"pending", "completed"}

    completed = orchestrator.agents["llm_msa"].wait_for_result("msa-cache-1", timeout=1)
    assert completed["status"] == "completed"

    second = orchestrator.analyze(market_data)
    assert second["agent_results"]["llm_msa"]["status"] == "completed"
    assert second["agent_results"]["llm_msa"]["verdict"] == "SUPPORT"
    assert second["final_signal"] == "HOLD"

