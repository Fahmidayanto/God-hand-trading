from valuecell.agents.llm_council_coordinator import LLMCouncilCoordinator
from valuecell.agents.llm_msa_agent import LLMMSAAgent
from valuecell.agents.llm_specialist_agents import (
    LLMDecisionAgent,
    LLMMLAgent,
    LLMSentimentAgent,
)


def assessment(vote):
    return {
        "vote": vote,
        "verdict": "SUPPORT",
        "confidence": 0.9,
        "data_quality": 1.0,
        "risk_flags": [],
        "supporting_factors": ["support"],
        "contradicting_factors": [],
        "historical_read": "Positive analogs",
        "reasoning": "Evidence supports the deterministic direction.",
    }


def test_coordinator_runs_initial_review_decision_and_gate():
    calls = {"msa": 0, "ml": 0, "sentiment": 0, "decision": 0}

    def evaluator(name):
        def run(_payload):
            calls[name] += 1
            return assessment("BUY")

        return run

    coordinator = LLMCouncilCoordinator(
        msa_agent=LLMMSAAgent(evaluator=evaluator("msa"), timeout_seconds=1.0),
        ml_agent=LLMMLAgent(evaluator=evaluator("ml"), timeout_seconds=1.0),
        sentiment_agent=LLMSentimentAgent(
            evaluator=evaluator("sentiment"), timeout_seconds=1.0
        ),
        decision_agent=LLMDecisionAgent(
            evaluator=evaluator("decision"), timeout_seconds=1.0
        ),
        approval_threshold=0.60,
        wait_timeout_seconds=1.0,
    )

    result = coordinator.evaluate(
        setup_id="council-1",
        msa_result={
            "signal": "BUY",
            "phase": "BOS_TRIGGERED",
            "evidence_snapshot": {"setup_id": "council-1"},
        },
        ml_result={"signal": "BUY", "confidence": 0.9},
        sentiment_result={"final_signal": "BUY", "final_confidence": 0.8},
    )

    assert result["approved"] is True
    assert result["final_signal"] == "BUY"
    assert calls == {"msa": 2, "ml": 2, "sentiment": 2, "decision": 1}
    assert len(result["initial_assessments"]) == 3
    assert len(result["reviewed_assessments"]) == 3


def test_coordinator_hard_holds_when_msa_has_no_bos():
    coordinator = LLMCouncilCoordinator(approval_threshold=0.60)

    result = coordinator.evaluate(
        setup_id="council-2",
        msa_result={"signal": "HOLD", "phase": "PENDING_SETUP"},
        ml_result=None,
        sentiment_result=None,
    )

    assert result["approved"] is False
    assert result["final_signal"] == "HOLD"
    assert result["gate_reason"] == "MSA has no confirmed BoS trade direction"


def test_coordinator_missing_specialist_becomes_abstention():
    coordinator = LLMCouncilCoordinator(
        msa_agent=LLMMSAAgent(evaluator=lambda _payload: assessment("BUY")),
        approval_threshold=0.60,
        wait_timeout_seconds=1.0,
    )

    result = coordinator.evaluate(
        setup_id="council-3",
        msa_result={
            "signal": "BUY",
            "phase": "BOS_TRIGGERED",
            "evidence_snapshot": {"setup_id": "council-3"},
        },
        ml_result={"signal": "BUY"},
        sentiment_result={"final_signal": "BUY"},
    )

    assert result["approved"] is False
    assert result["abstentions"] >= 3