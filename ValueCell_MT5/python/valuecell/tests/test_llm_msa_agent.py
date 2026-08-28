import threading
import time

from valuecell.agents.llm_msa_agent import LLMMSAAgent


def snapshot(setup_id="msa-test-1"):
    return {
        "schema_version": "msa-evidence-v1",
        "setup_id": setup_id,
        "setup": {"direction": "Bullish", "status": "PENDING_SETUP"},
        "historical_evidence": {"total_count": 12},
        "llm_constraints": {"may_create_trade_signal": False},
    }


def valid_assessment():
    return {
        "vote": "BUY",
        "verdict": "CAUTION",
        "confidence": 0.72,
        "data_quality": 0.80,
        "risk_flags": ["High rejection similarity"],
        "supporting_factors": ["EMA alignment"],
        "contradicting_factors": ["Rejected analogs"],
        "historical_read": "Mixed evidence",
        "reasoning": "Executed samples are positive, but close rejected analogs exist.",
    }


def test_shadow_analysis_is_non_blocking_and_cached_by_setup_id():
    started = threading.Event()
    release = threading.Event()

    def evaluator(_evidence):
        started.set()
        release.wait(timeout=2)
        return valid_assessment()

    agent = LLMMSAAgent(evaluator=evaluator, timeout_seconds=1.0)

    pending = agent.analyze(snapshot())
    assert pending["status"] == "pending"
    assert pending["mode"] == "SHADOW"
    assert started.wait(timeout=1)

    release.set()
    completed = agent.wait_for_result("msa-test-1", timeout=1)
    assert completed["status"] == "completed"
    assert completed["verdict"] == "CAUTION"
    assert completed["vote"] == "BUY"
    assert completed["data_quality"] == 0.80
    assert completed["schema_version"] == "llm-council-v1"
    assert completed["setup_id"] == "msa-test-1"
    assert agent.analyze(snapshot()) == completed


def test_invalid_evaluator_output_falls_back_without_trade_authority():
    agent = LLMMSAAgent(
        evaluator=lambda _evidence: {"verdict": "BUY", "confidence": 9},
        timeout_seconds=1.0,
    )

    agent.analyze(snapshot("msa-invalid"))
    result = agent.wait_for_result("msa-invalid", timeout=1)

    assert result["status"] == "error"
    assert result["verdict"] == "INSUFFICIENT_DATA"
    assert result["vote"] == "ABSTAIN"
    assert result["data_quality"] == 0.0
    assert result["can_affect_consensus"] is False
    assert result["can_create_trade_signal"] is False


def test_missing_evaluator_returns_unavailable_without_starting_work():
    agent = LLMMSAAgent(evaluator=None)

    result = agent.analyze(snapshot("msa-unavailable"))

    assert result["status"] == "unavailable"
    assert result["verdict"] == "INSUFFICIENT_DATA"
    assert result["vote"] == "ABSTAIN"
    assert result["can_affect_consensus"] is False


def test_timeout_result_is_not_overwritten_by_late_evaluator():
    release = threading.Event()

    def evaluator(_evidence):
        release.wait(timeout=1)
        return valid_assessment()

    agent = LLMMSAAgent(evaluator=evaluator, timeout_seconds=0.1)
    agent.analyze(snapshot("msa-timeout"))

    result = agent.wait_for_result("msa-timeout", timeout=0.5)
    assert result["status"] == "timeout"
    assert result["verdict"] == "INSUFFICIENT_DATA"
    assert result["vote"] == "ABSTAIN"

    release.set()
    time.sleep(0.05)
    assert agent.get_cached_result("msa-timeout")["status"] == "timeout"


def test_cache_is_bounded_and_evicts_oldest_setup():
    agent = LLMMSAAgent(evaluator=None, max_cache_entries=2)

    agent.analyze(snapshot("msa-1"))
    agent.analyze(snapshot("msa-2"))
    agent.analyze(snapshot("msa-3"))

    assert agent.get_cached_result("msa-1")["status"] == "unavailable"
    assert agent.get_cached_result("msa-1")["reasoning"] == "No cached LLM MSA result"
    assert agent.get_cached_result("msa-2")["setup_id"] == "msa-2"
    assert agent.get_cached_result("msa-3")["setup_id"] == "msa-3"


def test_configured_model_response_parser_accepts_json_fence():
    parsed = LLMMSAAgent._parse_json_response(
        "```json\n{\"verdict\":\"SUPPORT\",\"confidence\":0.8}\n```"
    )

    assert parsed == {"verdict": "SUPPORT", "confidence": 0.8}
