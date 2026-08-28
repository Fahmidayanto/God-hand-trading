"""Shared contracts and deterministic voting for the LLM trading council."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, Mapping


class CouncilVoteContract:
    """Validate one specialist or decision-agent assessment."""

    SCHEMA_VERSION = "llm-council-v1"
    ALLOWED_AGENTS = {"llm_msa", "llm_ml", "llm_sentiment", "llm_decision"}
    ALLOWED_STATUSES = {"completed", "pending", "timeout", "error", "unavailable"}
    ALLOWED_VOTES = {"BUY", "SELL", "HOLD", "ABSTAIN"}
    ALLOWED_VERDICTS = {"SUPPORT", "CAUTION", "OPPOSE", "INSUFFICIENT_DATA"}

    @classmethod
    def validate(cls, payload: Mapping[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, Mapping):
            raise ValueError("Council assessment must be a mapping")

        agent = cls._enum(payload, "agent", cls.ALLOWED_AGENTS, lowercase=True)
        status = cls._enum(payload, "status", cls.ALLOWED_STATUSES, lowercase=True)
        vote = cls._enum(payload, "vote", cls.ALLOWED_VOTES)
        verdict = cls._enum(payload, "verdict", cls.ALLOWED_VERDICTS)
        confidence = cls._score(payload, "confidence")
        data_quality = cls._score(payload, "data_quality")

        if status != "completed":
            vote = "ABSTAIN"
            confidence = 0.0
            data_quality = 0.0

        normalized = {
            "schema_version": cls.SCHEMA_VERSION,
            "agent": agent,
            "status": status,
            "vote": vote,
            "confidence": confidence,
            "data_quality": data_quality,
            "effective_score": confidence * data_quality if vote != "ABSTAIN" else 0.0,
            "verdict": verdict,
            "supporting_factors": cls._string_list(payload, "supporting_factors"),
            "contradicting_factors": cls._string_list(payload, "contradicting_factors"),
            "risk_flags": cls._string_list(payload, "risk_flags"),
            "reasoning": cls._required_string(payload, "reasoning"),
        }
        return normalized

    @staticmethod
    def _required_string(payload: Mapping[str, Any], key: str) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} must be a non-empty string")
        return value.strip()

    @staticmethod
    def _string_list(payload: Mapping[str, Any], key: str) -> list[str]:
        value = payload.get(key)
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise ValueError(f"{key} must be a list of strings")
        return list(value)

    @staticmethod
    def _score(payload: Mapping[str, Any], key: str) -> float:
        value = payload.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{key} must be numeric")
        score = float(value)
        if not 0.0 <= score <= 1.0:
            raise ValueError(f"{key} must be between 0 and 1")
        return score

    @staticmethod
    def _enum(
        payload: Mapping[str, Any],
        key: str,
        allowed: set[str],
        lowercase: bool = False,
    ) -> str:
        value = payload.get(key)
        if not isinstance(value, str):
            raise ValueError(f"{key} must be a string")
        normalized = value.strip().lower() if lowercase else value.strip().upper()
        if normalized not in allowed:
            raise ValueError(f"Invalid {key}: {normalized or 'missing'}")
        return normalized


class DeterministicCouncilVotingGate:
    """Approve only the confirmed MSA direction using weighted council votes."""

    DEFAULT_WEIGHTS = {
        "llm_msa": 0.35,
        "llm_ml": 0.35,
        "llm_sentiment": 0.15,
        "llm_decision": 0.15,
    }

    def __init__(
        self,
        approval_threshold: float = 0.60,
        weights: Mapping[str, float] | None = None,
    ) -> None:
        if not 0.0 <= approval_threshold <= 1.0:
            raise ValueError("approval_threshold must be between 0 and 1")
        self.approval_threshold = float(approval_threshold)
        self.weights = self._validate_weights(weights or self.DEFAULT_WEIGHTS)

    def decide(
        self,
        msa_signal: str,
        msa_phase: str,
        assessments: Iterable[Mapping[str, Any]],
    ) -> Dict[str, Any]:
        normalized = [CouncilVoteContract.validate(item) for item in assessments]
        scores = {"BUY": 0.0, "SELL": 0.0, "HOLD": 0.0}
        abstentions = 0

        for assessment in normalized:
            vote = assessment["vote"]
            if vote == "ABSTAIN":
                abstentions += 1
                continue
            weight = self.weights[assessment["agent"]]
            scores[vote] += weight * assessment["effective_score"]

        normalized_signal = str(msa_signal).upper()
        if normalized_signal not in {"BUY", "SELL"} or msa_phase != "BOS_TRIGGERED":
            return self._result(
                approved=False,
                final_signal="HOLD",
                scores=scores,
                abstentions=abstentions,
                assessments=normalized,
                reason="MSA has no confirmed BoS trade direction",
            )

        opposite = "SELL" if normalized_signal == "BUY" else "BUY"
        direction_score = scores[normalized_signal]
        approved = (
            direction_score >= self.approval_threshold
            and direction_score > scores[opposite]
        )
        reason = (
            "Council approved confirmed MSA direction"
            if approved
            else "Council support did not reach the confirmed MSA direction threshold"
        )
        return self._result(
            approved=approved,
            final_signal=normalized_signal if approved else "HOLD",
            scores=scores,
            abstentions=abstentions,
            assessments=normalized,
            reason=reason,
        )

    @staticmethod
    def _validate_weights(weights: Mapping[str, float]) -> Dict[str, float]:
        if set(weights) != CouncilVoteContract.ALLOWED_AGENTS:
            raise ValueError("weights must define all four council agents")
        normalized = {agent: float(weight) for agent, weight in weights.items()}
        if any(weight < 0.0 for weight in normalized.values()):
            raise ValueError("weights cannot be negative")
        if abs(sum(normalized.values()) - 1.0) > 1e-9:
            raise ValueError("weights must sum to 1.0")
        return normalized

    def _result(
        self,
        approved: bool,
        final_signal: str,
        scores: Dict[str, float],
        abstentions: int,
        assessments: list[Dict[str, Any]],
        reason: str,
    ) -> Dict[str, Any]:
        return {
            "schema_version": CouncilVoteContract.SCHEMA_VERSION,
            "approved": approved,
            "final_signal": final_signal,
            "approval_threshold": self.approval_threshold,
            "scores": {signal: round(score, 6) for signal, score in scores.items()},
            "abstentions": abstentions,
            "gate_reason": reason,
            "weights": deepcopy(self.weights),
            "assessments": assessments,
        }