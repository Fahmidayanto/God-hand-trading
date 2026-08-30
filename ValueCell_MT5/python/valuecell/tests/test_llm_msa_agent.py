import threading
import time
from types import SimpleNamespace

import pytest

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
        "facts": ["13 of 21 executed patterns were wins."],
        "interpretation": "The current setup is closer to the winning group.",
        "recommended_action": "WAIT",
        "win_pattern_characteristics": ["Winners held above the H1 EMA200."],
        "loss_pattern_characteristics": ["Losses stayed close to the H1 EMA200."],
        "current_pattern_comparison": "Current EMA distance is closer to winners.",
        "confirmation_conditions": ["A valid BoS closes above the HH reference."],
        "invalidation_conditions": ["The bullish structure reference breaks."],
        "counter_scenario": "A failed breakout would invalidate the bullish reading.",
        "user_explanation": "Historical evidence is positive, but confirmation is missing.",
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
    assert completed["facts"] == ["13 of 21 executed patterns were wins."]
    assert completed["recommended_action"] == "WAIT"
    assert completed["counter_scenario"].startswith("A failed breakout")
    assert list(completed["display_report"]) == [
        "conclusion",
        "simple_explanation",
        "evidence_summary",
        "top_10_patterns",
        "top_3_breakdowns",
        "closest_pattern_detail",
        "win_loss_comparison",
        "confirmation_and_invalidation",
    ]
    assert agent.analyze(snapshot()) == completed


def test_display_report_preserves_top_10_and_top_3_numeric_breakdowns():
    evidence = snapshot("msa-display-report")
    top_matches = []
    for rank in range(1, 11):
        pattern = {
            "id": f"pattern-{rank}",
            "similarity": 1.0 - rank / 100.0,
            "outcome": "LOSS" if rank == 1 else "WIN",
            "timestamp": f"2026-03-{rank:02d}T10:30:00",
            "price": 5100.0 + rank,
            "entry_time": f"2026-03-{rank:02d}T10:45:00",
            "entry_price": 5101.0 + rank,
            "exit_time": f"2026-03-{rank:02d}T11:45:00",
            "exit_price": 5090.0 + rank,
            "net_profit": -97.0 if rank == 1 else 50.0,
            "duration_minutes": 60,
            "close_reason": "STOP_LOSS" if rank == 1 else "TAKE_PROFIT",
        }
        if rank <= 3:
            pattern["similarity_breakdown_rank"] = rank
            pattern["similarity_breakdown"] = {
                "total_similarity": pattern["similarity"],
                "method": "vector-v2-lite-squared-l2",
                "factors": [{
                    "factor": "event_structure",
                    "current_value": "BoS",
                    "historical_value": "BoS",
                    "vector_distance": 0.0,
                    "factor_similarity": 1.0,
                    "distance_contribution": 0.0,
                    "available": True,
                }],
                "not_used_in_similarity": ["outcome", "net_profit"],
            }
        top_matches.append(pattern)
    evidence["historical_evidence"] = {
        "total_count": 23,
        "completed_count": 21,
        "outcome_distribution": {
            "wins": 13,
            "losses": 8,
            "rejected": 2,
            "executed_win_rate": 13 / 21,
        },
        "weighted_statistics": {"weighted_win_rate": 0.6112},
        "net_profit_statistics": {"total": 1040.42, "average": 49.54},
        "outcome_characteristics": {
            "wins": {"count": 13, "average_similarity": 0.7632},
            "losses": {"count": 8, "average_similarity": 0.7889},
        },
        "top_matches": top_matches,
    }

    report = LLMMSAAgent._build_display_report(evidence, valid_assessment())

    assert len(report["top_10_patterns"]) == 10
    assert len(report["top_3_breakdowns"]) == 3
    assert report["top_10_patterns"][0]["net_profit"] == pytest.approx(-97.0)
    assert report["top_3_breakdowns"][0]["factors"][0]["factor_similarity"] == 1.0
    assert report["closest_pattern_detail"]["close_reason"] == "STOP_LOSS"
    assert report["evidence_summary"]["weighted_win_rate"] == pytest.approx(0.6112)


def test_display_report_normalizes_rejected_pattern_nan_values():
    evidence = snapshot("msa-rejected-report")
    evidence["historical_evidence"] = {
        "top_matches": [{
            "id": "rejected-1",
            "similarity": 0.85,
            "outcome": "REJECTED",
            "net_profit": float("nan"),
            "entry_price": float("nan"),
            "reject_reason_raw": "H4 EMA Filter",
            "reject_reason_code": "H4_EMA_FILTER",
        }],
    }

    pattern = LLMMSAAgent._build_display_report(
        evidence,
        valid_assessment(),
    )["top_10_patterns"][0]

    assert pattern["net_profit"] is None
    assert pattern["entry_price"] is None
    assert pattern["rejection_reason"] == "H4 EMA Filter"
    assert pattern["rejection_reason_code"] == "H4_EMA_FILTER"


def test_prompt_requires_relevance_weighting_separated_reasoning_and_counter_scenario():
    prompt = LLMMSAAgent._build_prompt(snapshot())

    assert "WAJIB gunakan Bahasa Indonesia" in prompt
    assert "Jangan terjemahkan nama field JSON" in prompt
    assert "Kesimpulan: ...; Alasan utama: ...; Tindakan: ..." in prompt
    assert "weighted_win_rate" in prompt
    assert "Facts must quote only supplied evidence" in prompt
    assert "Compare WIN and LOSS characteristics" in prompt
    assert "confirmation_conditions" in prompt
    assert "invalidation_conditions" in prompt
    assert "counter_scenario" in prompt
    assert "recommended_action must be WAIT" in prompt
    assert "entry_time, entry_price, exit_time, exit_price, Net_Profit, and close_reason" in prompt
    assert "unavailable instead of inventing it" in prompt
    assert "top 10 patterns" in prompt
    assert "numeric similarity_breakdown for the top 3" in prompt


def test_fallback_uses_indonesian_narrative_text():
    result = LLMMSAAgent()._fallback("timeout", "Evaluasi LLM MSA melewati batas waktu")

    assert result["historical_read"] == "Data tidak tersedia"
    assert result["facts"] == ["Penilaian LLM MSA tidak tersedia."]
    assert result["confirmation_conditions"] == ["Tunggu konfirmasi MSA deterministik."]
    assert result["counter_scenario"] == "Skenario tandingan yang andal belum dapat dievaluasi."


def test_pending_setup_rejects_monitor_action():
    assessment = valid_assessment()
    assessment["recommended_action"] = "MONITOR"
    agent = LLMMSAAgent(evaluator=lambda _evidence: assessment, timeout_seconds=1.0)

    agent.analyze(snapshot("msa-invalid-action"))
    result = agent.wait_for_result("msa-invalid-action", timeout=1)

    assert result["status"] == "error"
    assert result["recommended_action"] == "ABSTAIN"
    assert "PENDING_SETUP" in result["reasoning"]


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


def test_suniesis_provider_uses_expected_model_fallback_order(monkeypatch):
    attempted_requests = []

    class FakeResponse:
        def __init__(self, model_id):
            self.model_id = model_id

        def raise_for_status(self):
            if self.model_id != "gpt-5.6-terra":
                raise RuntimeError("model unavailable")

        def json(self):
            return {
                "choices": [{"message": {"content": '''{
                    "vote": "BUY",
                    "verdict": "SUPPORT",
                    "confidence": 0.8,
                    "data_quality": 0.9,
                    "risk_flags": [],
                    "supporting_factors": ["Confirmed structure"],
                    "contradicting_factors": [],
                    "historical_read": "Positive evidence",
                        "reasoning": "The evidence supports the deterministic direction.",
                        "facts": ["The deterministic structure is confirmed."],
                        "interpretation": "Historical evidence supports the setup.",
                        "recommended_action": "WAIT",
                        "win_pattern_characteristics": ["Winning patterns held structure."],
                        "loss_pattern_characteristics": ["Losing patterns broke structure."],
                        "current_pattern_comparison": "The current setup is closer to winners.",
                        "confirmation_conditions": ["Wait for deterministic confirmation."],
                        "invalidation_conditions": ["The structure reference breaks."],
                        "counter_scenario": "A failed confirmation would weaken the setup.",
                        "user_explanation": "Evidence is positive, but execution remains deterministic."
                }'''}}]
            }

    def fake_post(url, **kwargs):
        attempted_requests.append({"url": url, **kwargs})
        return FakeResponse(kwargs["json"]["model"])

    monkeypatch.setattr("httpx.post", fake_post)

    agent = LLMMSAAgent(
        provider="suniesis",
        suniesis_api_key="test-key",
        timeout_seconds=1.0,
    )
    agent.analyze(snapshot("msa-suniesis"))
    result = agent.wait_for_result("msa-suniesis", timeout=1)

    assert result["status"] == "completed"
    assert result["verdict"] == "SUPPORT"
    assert [request["json"]["model"] for request in attempted_requests] == [
        "gpt-5.6-luna",
        "gpt-5.6-sol",
        "gpt-5.6-terra",
    ]
    assert all(
        request["url"] == "https://llm.suniesis.ai/v1/chat/completions"
        for request in attempted_requests
    )
    assert all(
        request["headers"]["Authorization"] == "Bearer test-key"
        for request in attempted_requests
    )
    assert all(0 < request["timeout"] <= 1.0 for request in attempted_requests)
    assert all(request["json"]["max_tokens"] == 1800 for request in attempted_requests)


def test_suniesis_provider_requires_api_key(monkeypatch):
    monkeypatch.delenv("SUNIESIS_API_KEY", raising=False)

    with pytest.raises(ValueError, match="SUNIESIS_API_KEY"):
        LLMMSAAgent(provider="suniesis")
