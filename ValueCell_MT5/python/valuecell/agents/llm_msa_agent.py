"""Shadow-mode LLM critic for Market Structure Agent evidence."""

from __future__ import annotations

import json
import re
import threading
from copy import deepcopy
from typing import Any, Callable, Dict, Optional

from loguru import logger
from valuecell.agents.llm_council import CouncilVoteContract


Evaluator = Callable[[Dict[str, Any]], Dict[str, Any]]


class LLMMSAAgent:
    """Evaluate MSA evidence asynchronously without trade authority."""

    def __init__(
        self,
        evaluator: Optional[Evaluator] = None,
        timeout_seconds: float = 8.0,
        mode: str = "SHADOW",
        provider: Optional[str] = None,
        model_id: Optional[str] = None,
        max_cache_entries: int = 256,
    ) -> None:
        self.name = "LLMMSAAgent"
        self.version = "1.0.0"
        self.mode = mode.upper()
        self.provider = provider
        self.model_id = model_id
        self.evaluator = evaluator or (
            self._evaluate_with_configured_model if provider or model_id else None
        )
        self.timeout_seconds = max(float(timeout_seconds), 0.1)
        self.max_cache_entries = max(int(max_cache_entries), 1)
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._events: Dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    def analyze(self, evidence_snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """Start evaluation once and immediately return its current cached state."""
        setup_id = str(evidence_snapshot.get("setup_id") or "").strip()
        if not setup_id:
            return self._fallback("error", "Evidence snapshot has no setup_id")

        with self._lock:
            cached = self._cache.get(setup_id)
            if cached is not None:
                return deepcopy(cached)

            if self.evaluator is None:
                result = self._fallback(
                    "unavailable",
                    "LLM MSA evaluator is not configured",
                    setup_id,
                )
                self._evict_oldest_if_full()
                self._cache[setup_id] = result
                return deepcopy(result)

            pending = self._base_result(setup_id, "pending", "PENDING")
            self._evict_oldest_if_full()
            self._cache[setup_id] = pending
            self._events[setup_id] = threading.Event()

        worker = threading.Thread(
            target=self._evaluate,
            args=(setup_id, deepcopy(evidence_snapshot)),
            daemon=True,
            name=f"llm-msa-{setup_id}",
        )
        worker.start()

        timer = threading.Timer(self.timeout_seconds, self._mark_timeout, args=(setup_id,))
        timer.daemon = True
        timer.start()
        return deepcopy(pending)

    def wait_for_result(self, setup_id: str, timeout: Optional[float] = None) -> Dict[str, Any]:
        """Test/diagnostic helper; production callers should use non-blocking analyze()."""
        with self._lock:
            event = self._events.get(setup_id)
        if event is not None:
            event.wait(timeout=timeout)
        return self.get_cached_result(setup_id)

    def get_cached_result(self, setup_id: str) -> Dict[str, Any]:
        with self._lock:
            result = self._cache.get(setup_id)
            if result is None:
                return self._fallback("unavailable", "No cached LLM MSA result", setup_id)
            return deepcopy(result)

    def reset_state(self) -> None:
        with self._lock:
            self._cache.clear()
            self._events.clear()

    def _evaluate(self, setup_id: str, evidence_snapshot: Dict[str, Any]) -> None:
        try:
            raw_result = self.evaluator(evidence_snapshot)  # type: ignore[misc]
            assessment = self._validate_assessment(raw_result, evidence_snapshot)
            result = {
                **self._base_result(setup_id, "completed", assessment["verdict"]),
                **assessment,
            }
        except Exception as exc:
            logger.warning(f"LLM MSA shadow evaluation failed for {setup_id}: {exc}")
            result = self._fallback("error", str(exc), setup_id)

        self._complete_if_pending(setup_id, result)

    def _evaluate_with_configured_model(
        self,
        evidence_snapshot: Dict[str, Any],
    ) -> Dict[str, Any]:
        from agno.agent import Agent
        from valuecell.adapters.models.factory import create_model

        model = create_model(
            model_id=self.model_id,
            provider=self.provider,
            temperature=0.1,
            max_tokens=1200,
        )
        agent = Agent(
            model=model,
            description=(
                "You are a read-only XAUUSD market-structure context critic. "
                "You cannot create trades, reverse direction, size positions, "
                "change MSA state, or bypass risk management."
            ),
        )
        response = agent.run(self._build_prompt(evidence_snapshot))
        content = getattr(response, "content", None)
        if not content:
            raise ValueError("Configured LLM returned empty content")
        return self._parse_json_response(str(content))

    @staticmethod
    def _build_prompt(evidence_snapshot: Dict[str, Any]) -> str:
        return (
            "Review this pending MSA setup as a context critic. Return raw JSON only "
            "with exactly these fields: vote (the deterministic MSA direction, HOLD, "
            "or ABSTAIN), verdict (SUPPORT, CAUTION, OPPOSE, or INSUFFICIENT_DATA), "
            "confidence (0 to 1), data_quality (0 to 1), risk_flags (string array), "
            "supporting_factors (string array), contradicting_factors (string array), "
            "historical_read (string), reasoning (string). Treat REJECTED historical "
            "patterns as risk evidence, never as losses. Use Net_Profit only for "
            "executed WIN/LOSS records. Never invent or reverse direction: vote BUY or "
            "SELL only when it exactly matches setup.direction; otherwise vote HOLD or "
            "ABSTAIN. Do not output lot, SL, or TP.\n\n"
            f"MSA evidence:\n{json.dumps(evidence_snapshot, default=str, separators=(',', ':'))}"
        )

    @staticmethod
    def _parse_json_response(content: str) -> Dict[str, Any]:
        cleaned = content.strip()
        fenced = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
        if fenced:
            cleaned = fenced.group(1).strip()
        else:
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start >= 0 and end >= start:
                cleaned = cleaned[start:end + 1]
        parsed = json.loads(cleaned)
        if not isinstance(parsed, dict):
            raise ValueError("Configured LLM response must be a JSON object")
        return parsed

    def _mark_timeout(self, setup_id: str) -> None:
        self._complete_if_pending(
            setup_id,
            self._fallback(
                "timeout",
                f"LLM MSA evaluation exceeded {self.timeout_seconds:.1f}s",
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

    def _validate_assessment(
        self,
        result: Any,
        evidence_snapshot: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not isinstance(result, dict):
            raise ValueError("Evaluator output must be a dictionary")
        normalized_result = dict(result)
        if "vote" not in normalized_result:
            direction = str(
                (evidence_snapshot or {}).get("setup", {}).get("direction", "")
            ).upper()
            normalized_result["vote"] = {
                "BULLISH": "BUY",
                "BEARISH": "SELL",
                "BUY": "BUY",
                "SELL": "SELL",
            }.get(direction, "ABSTAIN")
        normalized_result.setdefault("data_quality", 1.0)
        assessment = CouncilVoteContract.validate(
            {
                **normalized_result,
                "agent": "llm_msa",
                "status": "completed",
            }
        )
        assessment["historical_read"] = self._required_string(result, "historical_read")
        return assessment

    @staticmethod
    def _required_string(result: Dict[str, Any], key: str) -> str:
        value = result.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} must be a non-empty string")
        return value.strip()

    def _fallback(
        self,
        status: str,
        reason: str,
        setup_id: Optional[str] = None,
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
            "historical_read": "Unavailable",
            "reasoning": reason,
        }

    def _base_result(
        self,
        setup_id: Optional[str],
        status: str,
        verdict: str,
    ) -> Dict[str, Any]:
        return {
            "schema_version": CouncilVoteContract.SCHEMA_VERSION,
            "agent": "llm_msa",
            "agent_name": self.name,
            "version": self.version,
            "mode": self.mode,
            "setup_id": setup_id,
            "status": status,
            "verdict": verdict,
            "can_affect_consensus": False,
            "can_create_trade_signal": False,
        }