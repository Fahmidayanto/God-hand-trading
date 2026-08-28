"""Async shadow agents for ML, sentiment, and council decision review."""

from __future__ import annotations

import threading
from copy import deepcopy
from typing import Any, Callable, Dict, Iterable, Mapping, Optional

from loguru import logger

from valuecell.agents.llm_council import CouncilVoteContract


Evaluator = Callable[[Dict[str, Any]], Dict[str, Any]]


class _LLMSpecialistAgent:
    agent_id = ""
    deterministic_signal_key = "signal"
    requires_peers = False

    def __init__(
        self,
        evaluator: Optional[Evaluator] = None,
        timeout_seconds: float = 8.0,
        mode: str = "SHADOW",
        max_cache_entries: int = 256,
    ) -> None:
        self.evaluator = evaluator
        self.timeout_seconds = max(float(timeout_seconds), 0.1)
        self.mode = mode.upper()
        self.max_cache_entries = max(int(max_cache_entries), 1)
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._events: Dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    def analyze(
        self,
        setup_id: str,
        deterministic_result: Mapping[str, Any],
        peer_assessments: Optional[Iterable[Mapping[str, Any]]] = None,
    ) -> Dict[str, Any]:
        normalized_setup_id = str(setup_id).strip()
        if not normalized_setup_id:
            return self._fallback("error", "setup_id is required", None)

        peers = [deepcopy(dict(item)) for item in (peer_assessments or [])]
        if self.requires_peers and len(peers) < 3:
            return self._fallback(
                "unavailable",
                "Decision agent requires all three specialist assessments",
                normalized_setup_id,
            )

        with self._lock:
            cached = self._cache.get(normalized_setup_id)
            if cached is not None:
                return deepcopy(cached)
            if self.evaluator is None:
                result = self._fallback(
                    "unavailable",
                    f"{self.agent_id} evaluator is not configured",
                    normalized_setup_id,
                )
                self._evict_oldest_if_full()
                self._cache[normalized_setup_id] = result
                return deepcopy(result)

            pending = self._base_result(normalized_setup_id, "pending", "PENDING")
            self._evict_oldest_if_full()
            self._cache[normalized_setup_id] = pending
            self._events[normalized_setup_id] = threading.Event()

        payload = {
            "setup_id": normalized_setup_id,
            "deterministic_result": deepcopy(dict(deterministic_result)),
            "peer_assessments": peers,
            "constraints": {
                "may_create_trade_signal": False,
                "may_call_risk_management": False,
                "review_rounds": 1,
            },
        }
        worker = threading.Thread(
            target=self._evaluate,
            args=(normalized_setup_id, payload),
            daemon=True,
            name=f"{self.agent_id}-{normalized_setup_id}",
        )
        worker.start()
        timer = threading.Timer(
            self.timeout_seconds,
            self._mark_timeout,
            args=(normalized_setup_id,),
        )
        timer.daemon = True
        timer.start()
        return deepcopy(pending)

    def wait_for_result(self, setup_id: str, timeout: Optional[float] = None) -> Dict[str, Any]:
        with self._lock:
            event = self._events.get(setup_id)
        if event is not None:
            event.wait(timeout=timeout)
        return self.get_cached_result(setup_id)

    def get_cached_result(self, setup_id: str) -> Dict[str, Any]:
        with self._lock:
            result = self._cache.get(setup_id)
        if result is None:
            return self._fallback("unavailable", "No cached specialist result", setup_id)
        return deepcopy(result)

    def _evaluate(self, setup_id: str, payload: Dict[str, Any]) -> None:
        try:
            raw_result = self.evaluator(payload)  # type: ignore[misc]
            assessment = CouncilVoteContract.validate(
                {
                    **raw_result,
                    "agent": self.agent_id,
                    "status": "completed",
                }
            )
            self._validate_direction(payload["deterministic_result"], assessment["vote"])
            result = {
                **self._base_result(setup_id, "completed", assessment["verdict"]),
                **assessment,
            }
        except Exception as exc:
            logger.warning(f"{self.agent_id} shadow evaluation failed for {setup_id}: {exc}")
            result = self._fallback("error", str(exc), setup_id)
        self._complete_if_pending(setup_id, result)

    def _validate_direction(
        self,
        deterministic_result: Mapping[str, Any],
        vote: str,
    ) -> None:
        if vote not in {"BUY", "SELL"}:
            return
        direction = str(deterministic_result.get(self.deterministic_signal_key, "")).upper()
        if direction in {"BUY", "SELL"} and vote != direction:
            raise ValueError(
                f"{self.agent_id} cannot reverse deterministic direction {direction}"
            )

    def _mark_timeout(self, setup_id: str) -> None:
        self._complete_if_pending(
            setup_id,
            self._fallback(
                "timeout",
                f"{self.agent_id} evaluation exceeded {self.timeout_seconds:.1f}s",
                setup_id,
            ),
        )

    def _complete_if_pending(self, setup_id: str, result: Dict[str, Any]) -> None:
        with self._lock:
            current = self._cache.get(setup_id)
            if current is None or current.get("status") != "pending":
                return
            self._cache[setup_id] = result
            event = self._events.get(setup_id)
            if event is not None:
                event.set()

    def _evict_oldest_if_full(self) -> None:
        while len(self._cache) >= self.max_cache_entries:
            oldest_setup_id = next(iter(self._cache))
            self._cache.pop(oldest_setup_id, None)
            self._events.pop(oldest_setup_id, None)

    def _fallback(
        self,
        status: str,
        reason: str,
        setup_id: Optional[str],
    ) -> Dict[str, Any]:
        return {
            **self._base_result(setup_id, status, "INSUFFICIENT_DATA"),
            "vote": "ABSTAIN",
            "confidence": 0.0,
            "data_quality": 0.0,
            "effective_score": 0.0,
            "risk_flags": [],
            "supporting_factors": [],
            "contradicting_factors": [],
            "reasoning": reason,
        }

    def _base_result(self, setup_id: Optional[str], status: str, verdict: str) -> Dict[str, Any]:
        return {
            "schema_version": CouncilVoteContract.SCHEMA_VERSION,
            "agent": self.agent_id,
            "mode": self.mode,
            "setup_id": setup_id,
            "status": status,
            "verdict": verdict,
            "can_affect_consensus": False,
            "can_create_trade_signal": False,
            "can_call_risk_management": False,
        }


class LLMMLAgent(_LLMSpecialistAgent):
    agent_id = "llm_ml"
    deterministic_signal_key = "signal"


class LLMSentimentAgent(_LLMSpecialistAgent):
    agent_id = "llm_sentiment"
    deterministic_signal_key = "final_signal"


class LLMDecisionAgent(_LLMSpecialistAgent):
    agent_id = "llm_decision"
    deterministic_signal_key = "msa_signal"
    requires_peers = True