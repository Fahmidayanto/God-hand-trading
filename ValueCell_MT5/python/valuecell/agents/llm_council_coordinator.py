"""Coordinate specialist review, decision synthesis, and deterministic voting."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Mapping, Optional

from valuecell.agents.llm_council import DeterministicCouncilVotingGate
from valuecell.agents.llm_msa_agent import LLMMSAAgent
from valuecell.agents.llm_specialist_agents import (
    LLMDecisionAgent,
    LLMMLAgent,
    LLMSentimentAgent,
)


class LLMCouncilCoordinator:
    """Run three specialists, one cross-review, then the decision agent."""

    def __init__(
        self,
        msa_agent: Optional[LLMMSAAgent] = None,
        ml_agent: Optional[LLMMLAgent] = None,
        sentiment_agent: Optional[LLMSentimentAgent] = None,
        decision_agent: Optional[LLMDecisionAgent] = None,
        approval_threshold: float = 0.60,
        wait_timeout_seconds: float = 8.0,
    ) -> None:
        self.msa_agent = msa_agent or LLMMSAAgent()
        self.ml_agent = ml_agent or LLMMLAgent()
        self.sentiment_agent = sentiment_agent or LLMSentimentAgent()
        self.decision_agent = decision_agent or LLMDecisionAgent()
        self.voting_gate = DeterministicCouncilVotingGate(approval_threshold)
        self.wait_timeout_seconds = max(float(wait_timeout_seconds), 0.1)

    def evaluate(
        self,
        setup_id: str,
        msa_result: Mapping[str, Any],
        ml_result: Optional[Mapping[str, Any]],
        sentiment_result: Optional[Mapping[str, Any]],
    ) -> Dict[str, Any]:
        msa_signal = str(msa_result.get("signal", "HOLD")).upper()
        msa_phase = str(msa_result.get("phase", "IDLE"))
        if msa_signal not in {"BUY", "SELL"} or msa_phase != "BOS_TRIGGERED":
            result = self.voting_gate.decide(msa_signal, msa_phase, [])
            return {
                **result,
                "setup_id": setup_id,
                "initial_assessments": [],
                "reviewed_assessments": [],
                "decision_assessment": self._abstention(
                    "llm_decision", "MSA has no confirmed BoS trade direction"
                ),
            }

        initial = self._run_specialists(
            phase_id=f"{setup_id}:initial",
            msa_result=msa_result,
            ml_result=ml_result,
            sentiment_result=sentiment_result,
            peers=None,
        )
        reviewed = self._run_specialists(
            phase_id=f"{setup_id}:review",
            msa_result=msa_result,
            ml_result=ml_result,
            sentiment_result=sentiment_result,
            peers=initial,
        )

        decision_id = f"{setup_id}:decision"
        self.decision_agent.analyze(
            setup_id=decision_id,
            deterministic_result={
                "msa_signal": msa_signal,
                "msa_phase": msa_phase,
                "ml_result": deepcopy(dict(ml_result or {})),
                "sentiment_result": deepcopy(dict(sentiment_result or {})),
            },
            peer_assessments=reviewed,
        )
        decision = self.decision_agent.wait_for_result(
            decision_id,
            timeout=self.wait_timeout_seconds,
        )
        gate_result = self.voting_gate.decide(
            msa_signal=msa_signal,
            msa_phase=msa_phase,
            assessments=[*reviewed, decision],
        )
        return {
            **gate_result,
            "setup_id": setup_id,
            "initial_assessments": initial,
            "reviewed_assessments": reviewed,
            "decision_assessment": decision,
        }

    def _run_specialists(
        self,
        phase_id: str,
        msa_result: Mapping[str, Any],
        ml_result: Optional[Mapping[str, Any]],
        sentiment_result: Optional[Mapping[str, Any]],
        peers: Optional[list[Dict[str, Any]]],
    ) -> list[Dict[str, Any]]:
        msa_snapshot = deepcopy(dict(msa_result.get("evidence_snapshot") or {}))
        msa_snapshot["setup_id"] = phase_id
        if peers is not None:
            msa_snapshot["peer_assessments"] = deepcopy(peers)

        self.msa_agent.analyze(msa_snapshot)
        self.ml_agent.analyze(
            setup_id=phase_id,
            deterministic_result=ml_result or {},
            peer_assessments=peers,
        )
        self.sentiment_agent.analyze(
            setup_id=phase_id,
            deterministic_result=sentiment_result or {},
            peer_assessments=peers,
        )
        return [
            self.msa_agent.wait_for_result(phase_id, self.wait_timeout_seconds),
            self.ml_agent.wait_for_result(phase_id, self.wait_timeout_seconds),
            self.sentiment_agent.wait_for_result(phase_id, self.wait_timeout_seconds),
        ]

    @staticmethod
    def _abstention(agent: str, reason: str) -> Dict[str, Any]:
        return {
            "schema_version": "llm-council-v1",
            "agent": agent,
            "status": "unavailable",
            "vote": "ABSTAIN",
            "confidence": 0.0,
            "data_quality": 0.0,
            "effective_score": 0.0,
            "verdict": "INSUFFICIENT_DATA",
            "supporting_factors": [],
            "contradicting_factors": [],
            "risk_flags": [],
            "reasoning": reason,
        }