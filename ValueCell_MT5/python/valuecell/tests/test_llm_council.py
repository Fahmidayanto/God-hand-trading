import pytest

from valuecell.agents.llm_council import (
    CouncilVoteContract,
    DeterministicCouncilVotingGate,
)


def vote(agent, direction, confidence, data_quality, status="completed"):
    return {
        "agent": agent,
        "status": status,
        "vote": direction,
        "confidence": confidence,
        "data_quality": data_quality,
        "verdict": "SUPPORT" if direction in {"BUY", "SELL"} else "CAUTION",
        "supporting_factors": ["support"],
        "contradicting_factors": [],
        "risk_flags": [],
        "reasoning": "Structured assessment.",
    }


def test_shared_vote_contract_normalizes_valid_payload():
    normalized = CouncilVoteContract.validate(
        vote("llm_msa", "buy", 0.8, 0.9)
    )

    assert normalized["vote"] == "BUY"
    assert normalized["confidence"] == pytest.approx(0.8)
    assert normalized["data_quality"] == pytest.approx(0.9)
    assert normalized["schema_version"] == "llm-council-v1"


def test_non_completed_agent_is_normalized_to_abstain():
    normalized = CouncilVoteContract.validate(
        vote("llm_ml", "BUY", 0.9, 0.9, status="timeout")
    )

    assert normalized["vote"] == "ABSTAIN"
    assert normalized["effective_score"] == 0.0


def test_invalid_vote_contract_is_rejected():
    payload = vote("llm_sentiment", "BUY", 1.2, 0.9)

    with pytest.raises(ValueError, match="confidence"):
        CouncilVoteContract.validate(payload)


def test_gate_approves_only_msa_direction_after_bos():
    gate = DeterministicCouncilVotingGate(approval_threshold=0.60)
    assessments = [
        vote("llm_msa", "BUY", 0.90, 0.95),
        vote("llm_ml", "BUY", 0.85, 0.95),
        vote("llm_sentiment", "SELL", 0.60, 0.80),
        vote("llm_decision", "BUY", 0.85, 0.90),
    ]

    result = gate.decide(msa_signal="BUY", msa_phase="BOS_TRIGGERED", assessments=assessments)

    assert result["approved"] is True
    assert result["final_signal"] == "BUY"
    assert result["scores"]["BUY"] >= 0.60
    assert result["scores"]["SELL"] > 0.0


def test_gate_forces_hold_before_bos_even_with_unanimous_buy():
    gate = DeterministicCouncilVotingGate(approval_threshold=0.60)
    assessments = [
        vote("llm_msa", "BUY", 1.0, 1.0),
        vote("llm_ml", "BUY", 1.0, 1.0),
        vote("llm_sentiment", "BUY", 1.0, 1.0),
        vote("llm_decision", "BUY", 1.0, 1.0),
    ]

    result = gate.decide(msa_signal="HOLD", msa_phase="PENDING_SETUP", assessments=assessments)

    assert result["approved"] is False
    assert result["final_signal"] == "HOLD"
    assert result["gate_reason"] == "MSA has no confirmed BoS trade direction"


def test_gate_rejects_opposite_council_direction():
    gate = DeterministicCouncilVotingGate(approval_threshold=0.60)
    assessments = [
        vote("llm_msa", "SELL", 0.9, 1.0),
        vote("llm_ml", "SELL", 0.9, 1.0),
        vote("llm_sentiment", "SELL", 0.9, 1.0),
        vote("llm_decision", "SELL", 0.9, 1.0),
    ]

    result = gate.decide(msa_signal="BUY", msa_phase="BOS_TRIGGERED", assessments=assessments)

    assert result["approved"] is False
    assert result["final_signal"] == "HOLD"
    assert result["scores"]["SELL"] > result["scores"]["BUY"]


def test_abstaining_agents_do_not_increase_score():
    gate = DeterministicCouncilVotingGate(approval_threshold=0.60)
    assessments = [
        vote("llm_msa", "BUY", 0.9, 1.0),
        vote("llm_ml", "BUY", 0.9, 1.0, status="timeout"),
        vote("llm_sentiment", "ABSTAIN", 0.0, 0.0),
        vote("llm_decision", "BUY", 0.9, 1.0, status="error"),
    ]

    result = gate.decide(msa_signal="BUY", msa_phase="BOS_TRIGGERED", assessments=assessments)

    assert result["approved"] is False
    assert result["abstentions"] == 3
    assert result["scores"]["BUY"] == pytest.approx(0.315)
