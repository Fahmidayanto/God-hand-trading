from valuecell.agents.llm_specialist_agents import (
    LLMDecisionAgent,
    LLMMLAgent,
    LLMSentimentAgent,
)


def assessment(vote="BUY"):
    return {
        "vote": vote,
        "verdict": "SUPPORT",
        "confidence": 0.8,
        "data_quality": 0.9,
        "risk_flags": [],
        "supporting_factors": ["deterministic evidence"],
        "contradicting_factors": [],
        "reasoning": "The deterministic result supports the setup.",
    }


def test_ml_specialist_reads_deterministic_result_and_cross_review():
    captured = {}

    def evaluator(payload):
        captured.update(payload)
        return assessment("BUY")

    agent = LLMMLAgent(evaluator=evaluator, timeout_seconds=1.0)
    pending = agent.analyze(
        setup_id="setup-1",
        deterministic_result={"signal": "BUY", "confidence": 0.82},
        peer_assessments=[{"agent": "llm_msa", "vote": "BUY"}],
    )
    result = agent.wait_for_result("setup-1", timeout=1.0)

    assert pending["status"] == "pending"
    assert result["agent"] == "llm_ml"
    assert result["vote"] == "BUY"
    assert captured["deterministic_result"]["signal"] == "BUY"
    assert captured["peer_assessments"][0]["agent"] == "llm_msa"


def test_sentiment_specialist_cannot_reverse_deterministic_direction():
    agent = LLMSentimentAgent(
        evaluator=lambda _payload: assessment("SELL"),
        timeout_seconds=1.0,
    )

    agent.analyze(
        setup_id="setup-2",
        deterministic_result={"final_signal": "BUY", "final_confidence": 0.7},
    )
    result = agent.wait_for_result("setup-2", timeout=1.0)

    assert result["status"] == "error"
    assert result["vote"] == "ABSTAIN"


def test_decision_agent_requires_specialist_assessments():
    agent = LLMDecisionAgent(evaluator=lambda _payload: assessment("BUY"))

    result = agent.analyze(setup_id="setup-3", deterministic_result={})

    assert result["status"] == "unavailable"
    assert result["vote"] == "ABSTAIN"


def test_decision_agent_synthesizes_reviewed_specialists():
    captured = {}

    def evaluator(payload):
        captured.update(payload)
        return assessment("BUY")

    agent = LLMDecisionAgent(evaluator=evaluator, timeout_seconds=1.0)
    specialists = [
        {"agent": "llm_msa", "status": "completed", "vote": "BUY"},
        {"agent": "llm_ml", "status": "completed", "vote": "BUY"},
        {"agent": "llm_sentiment", "status": "completed", "vote": "HOLD"},
    ]
    agent.analyze(
        setup_id="setup-4",
        deterministic_result={"msa_signal": "BUY"},
        peer_assessments=specialists,
    )
    result = agent.wait_for_result("setup-4", timeout=1.0)

    assert result["status"] == "completed"
    assert result["agent"] == "llm_decision"
    assert len(captured["peer_assessments"]) == 3


def test_specialist_unavailable_is_an_abstention():
    agent = LLMMLAgent(evaluator=None)

    result = agent.analyze(
        setup_id="setup-5",
        deterministic_result={"signal": "BUY", "confidence": 0.8},
    )

    assert result["status"] == "unavailable"
    assert result["vote"] == "ABSTAIN"
    assert result["can_create_trade_signal"] is False