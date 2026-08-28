from unittest.mock import MagicMock

from valuecell.agents.orchestrator_agent import OrchestratorAgent


def msa_assessment(vote="BUY", confidence=0.9):
    return {
        "vote": vote,
        "verdict": "SUPPORT",
        "confidence": confidence,
        "data_quality": 1.0,
        "risk_flags": [],
        "supporting_factors": ["structure evidence"],
        "contradicting_factors": [],
        "historical_read": "Supportive",
        "reasoning": "Structure evidence supports the deterministic direction.",
    }


def specialist_assessment(vote="BUY", confidence=0.9):
    result = msa_assessment(vote, confidence)
    result.pop("historical_read")
    return result


def build_orchestrator(council_vote="BUY", council_confidence=0.9):
    evaluator = lambda _payload: specialist_assessment(
        council_vote, council_confidence
    )
    orchestrator = OrchestratorAgent(
        enable_market_structure=True,
        enable_ml_prediction=True,
        enable_risk_management=True,
        enable_sentiment=True,
        enable_llm_council=True,
        llm_msa={
            "evaluator": lambda _payload: msa_assessment(
                council_vote, council_confidence
            ),
            "timeout_seconds": 1.0,
        },
        llm_ml={"evaluator": evaluator, "timeout_seconds": 1.0},
        llm_sentiment={"evaluator": evaluator, "timeout_seconds": 1.0},
        llm_decision={"evaluator": evaluator, "timeout_seconds": 1.0},
        llm_council={"wait_timeout_seconds": 1.0},
    )
    orchestrator.agents["market_structure"].analyze = MagicMock(return_value={
        "signal": "BUY",
        "confidence": 0.9,
        "phase": "BOS_TRIGGERED",
        "pre_signal": None,
        "reasoning": "Confirmed bullish BoS",
        "evidence_snapshot": {
            "setup_id": "orchestrator-council-1",
            "setup": {"direction": "Bullish"},
        },
    })
    orchestrator.agents["ml_prediction"].analyze = MagicMock(return_value={
        "signal": "BUY",
        "confidence": 0.9,
        "probability": 0.9,
        "reasoning": "ML supports BUY",
        "model_type": "classification",
    })
    orchestrator.agents["sentiment"].analyze = MagicMock(return_value={
        "final_signal": "BUY",
        "final_confidence": 0.9,
        "confidence_adjustment": 0.0,
        "filtered": False,
        "reasoning": "No sentiment veto",
    })
    orchestrator.agents["risk_management"].analyze = MagicMock(return_value={
        "approved": True,
        "lot_size": 0.1,
        "risk_pct": 1.0,
        "risk_usd": 10.0,
        "entry_price": 2300.0,
        "sl_price": 2290.0,
        "tp_price": 2320.0,
        "sl_distance_pips": 100.0,
        "tp_distance_pips": 200.0,
        "rr_ratio": 2.0,
    })
    return orchestrator


def market_data():
    return {
        "df": None,
        "current_bar": {"time": 123456789, "close": 2300.0},
        "session": "London",
    }


def test_approved_council_runs_risk_management_after_voting():
    orchestrator = build_orchestrator()

    result = orchestrator.analyze(market_data())

    assert result["approved"] is True
    assert result["final_signal"] == "BUY"
    assert result["agent_results"]["llm_council"]["approved"] is True
    assert result["deterministic_consensus"]["approved"] is True
    orchestrator.agents["risk_management"].analyze.assert_called_once()


def test_rejected_council_stops_before_risk_management():
    orchestrator = build_orchestrator(council_vote="HOLD", council_confidence=0.9)

    result = orchestrator.analyze(market_data())

    assert result["approved"] is False
    assert result["final_signal"] == "HOLD"
    assert result["agent_results"]["llm_council"]["approved"] is False
    orchestrator.agents["risk_management"].analyze.assert_not_called()