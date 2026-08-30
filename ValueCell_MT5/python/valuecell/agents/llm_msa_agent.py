"""Shadow-mode LLM critic for Market Structure Agent evidence."""

from __future__ import annotations

import json
import math
import os
import re
import threading
import time
from copy import deepcopy
from typing import Any, Callable, Dict, Optional, Sequence

from loguru import logger
from valuecell.agents.llm_council import CouncilVoteContract


Evaluator = Callable[[Dict[str, Any]], Dict[str, Any]]

SUNIESIS_MODEL_IDS = (
    "gpt-5.6-luna",
    "gpt-5.6-sol",
    "gpt-5.6-terra",
    "gpt-5.5",
    "gpt-5.4",
    "gpt-5.4-mini",
    "gpt-5.3-codex-spark",
    "codex-auto-review",
)


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
        suniesis_api_key: Optional[str] = None,
        suniesis_base_url: str = "https://llm.suniesis.ai/v1",
        suniesis_model_ids: Optional[Sequence[str]] = None,
        suniesis_model_timeout_seconds: float = 3.0,
    ) -> None:
        self.name = "LLMMSAAgent"
        self.version = "1.0.0"
        self.mode = mode.upper()
        self.provider = provider.lower() if provider else None
        self.model_id = model_id
        self.timeout_seconds = max(float(timeout_seconds), 0.1)
        self.suniesis_api_key = suniesis_api_key or os.getenv("SUNIESIS_API_KEY", "")
        self.suniesis_base_url = suniesis_base_url.rstrip("/")
        self.suniesis_model_ids = tuple(suniesis_model_ids or SUNIESIS_MODEL_IDS)
        self.suniesis_model_timeout_seconds = max(
            min(float(suniesis_model_timeout_seconds), self.timeout_seconds),
            0.1,
        )
        if self.provider == "suniesis" and not self.suniesis_api_key:
            raise ValueError("SUNIESIS_API_KEY is required for the Suniesis provider")
        self.evaluator = evaluator or (
            self._evaluate_with_configured_model if provider or model_id else None
        )
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
                "display_report": self._build_display_report(
                    evidence_snapshot,
                    assessment,
                ),
            }
        except Exception as exc:
            logger.warning(f"LLM MSA shadow evaluation failed for {setup_id}: {exc}")
            result = self._fallback("error", str(exc), setup_id)

        self._complete_if_pending(setup_id, result)

    def _evaluate_with_configured_model(
        self,
        evidence_snapshot: Dict[str, Any],
    ) -> Dict[str, Any]:
        if self.provider == "suniesis":
            return self._evaluate_with_suniesis(evidence_snapshot)

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

    def _evaluate_with_suniesis(
        self,
        evidence_snapshot: Dict[str, Any],
    ) -> Dict[str, Any]:
        import httpx

        failures = []
        deadline = time.monotonic() + self.timeout_seconds
        for model_id in self.suniesis_model_ids:
            remaining_seconds = deadline - time.monotonic()
            if remaining_seconds <= 0:
                break
            try:
                response = httpx.post(
                    f"{self.suniesis_base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.suniesis_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model_id,
                        "messages": [
                            {
                                "role": "system",
                                "content": (
                                    "You are a read-only XAUUSD market-structure "
                                    "context critic. You cannot create trades, reverse "
                                    "direction, size positions, change MSA state, or "
                                    "bypass risk management."
                                ),
                            },
                            {
                                "role": "user",
                                "content": self._build_prompt(evidence_snapshot),
                            },
                        ],
                        "temperature": 0.1,
                        "max_tokens": 1800,
                    },
                    timeout=min(
                        self.suniesis_model_timeout_seconds,
                        remaining_seconds,
                    ),
                )
                response.raise_for_status()
                payload = response.json()
                content = payload["choices"][0]["message"]["content"]
                if not content:
                    raise ValueError("empty response")
                return self._parse_json_response(str(content))
            except Exception as exc:
                failures.append(f"{model_id}: {type(exc).__name__}")
                logger.warning(
                    f"Suniesis LLM MSA model {model_id} failed: {type(exc).__name__}"
                )

        raise RuntimeError(
            "All Suniesis LLM MSA models failed (" + ", ".join(failures) + ")"
        )

    @staticmethod
    def _build_prompt(evidence_snapshot: Dict[str, Any]) -> str:
        return (
            "Tinjau setup MSA yang masih pending ini sebagai pengkritik konteks. "
            "WAJIB gunakan Bahasa Indonesia untuk seluruh nilai teks naratif, termasuk "
            "risk_flags, supporting_factors, contradicting_factors, historical_read, "
            "reasoning, facts, interpretation, win_pattern_characteristics, "
            "loss_pattern_characteristics, current_pattern_comparison, "
            "confirmation_conditions, invalidation_conditions, counter_scenario, dan "
            "user_explanation. Jangan terjemahkan nama field JSON, nilai enum kontrak, "
            "kode teknis, nama sesi, nama timeframe, WIN, LOSS, REJECTED, HOLD, WAIT, "
            "MONITOR, ABSTAIN, SUPPORT, CAUTION, OPPOSE, INSUFFICIENT_DATA, atau "
            "Net_Profit. Kembalikan raw JSON saja dengan tepat field berikut: vote "
            "(arah MSA deterministik, HOLD, atau ABSTAIN), verdict (SUPPORT, CAUTION, "
            "OPPOSE, atau INSUFFICIENT_DATA), confidence (0 sampai 1), data_quality "
            "(0 sampai 1), risk_flags (array string), supporting_factors (array string), "
            "contradicting_factors (array string), historical_read (string), reasoning "
            "(string), facts (array string), interpretation (string), recommended_action "
            "(WAIT, MONITOR, atau ABSTAIN), win_pattern_characteristics (array string), "
            "loss_pattern_characteristics (array string), current_pattern_comparison "
            "(string), confirmation_conditions (array string), invalidation_conditions "
            "(array string), counter_scenario (string), user_explanation (string). "
            "Tulis user_explanation secara ringkas dalam tepat tiga baris dengan format: "
            "Kesimpulan: ...; Alasan utama: ...; Tindakan: .... Pisahkan setiap bagian "
            "dengan karakter baris baru dan gunakan kalimat yang mudah dipahami. "
            "Facts must quote only supplied evidence; "
            "separate facts, interpretation, and action. Evaluate relevance using direction, "
            "structure sequence, timeframe, session, EMA context, ATR context, similarity, "
            "weighted_win_rate, and average_executed_similarity instead of raw win rate "
            "alone. Compare WIN and LOSS characteristics and state which group the current "
            "setup resembles, with evidence. State the strongest scenario against your own "
            "conclusion in counter_scenario. When the most similar pattern is a LOSS and "
            "its trade fields are supplied, user_explanation must state its entry_time, "
            "entry_price, exit_time, exit_price, Net_Profit, and close_reason. Treat "
            "close_reason as the factual execution reason and keep any market-cause "
            "interpretation explicitly separate. If a trade field is absent, say that it "
            "is unavailable instead of inventing it. Summarize all supplied top 10 "
            "patterns with their numeric total similarity, "
            "outcome, entry/exit facts, Net_Profit, and close/rejection reason. Explain the "
            "numeric similarity_breakdown for the top 3 using current_value, "
            "historical_value, vector_distance, factor_similarity, and "
            "distance_contribution. Never replace these values with vague labels such as "
            "similar or close. "
            "Treat REJECTED historical patterns as risk evidence, never as losses. "
            "Use Net_Profit only for "
            "executed WIN/LOSS records. Never invent or reverse direction: vote BUY or "
            "SELL only when it exactly matches setup.direction; otherwise vote HOLD or "
            "ABSTAIN. While setup.status is PENDING_SETUP, recommended_action must be WAIT "
            "or ABSTAIN. Do not output lot, SL, or TP.\n\n"
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
        assessment["facts"] = self._required_string_list(result, "facts")
        assessment["interpretation"] = self._required_string(result, "interpretation")
        assessment["recommended_action"] = self._required_action(
            result, evidence_snapshot
        )
        assessment["win_pattern_characteristics"] = self._required_string_list(
            result, "win_pattern_characteristics"
        )
        assessment["loss_pattern_characteristics"] = self._required_string_list(
            result, "loss_pattern_characteristics"
        )
        assessment["current_pattern_comparison"] = self._required_string(
            result, "current_pattern_comparison"
        )
        assessment["confirmation_conditions"] = self._required_string_list(
            result, "confirmation_conditions"
        )
        assessment["invalidation_conditions"] = self._required_string_list(
            result, "invalidation_conditions"
        )
        assessment["counter_scenario"] = self._required_string(result, "counter_scenario")
        assessment["user_explanation"] = self._required_string(result, "user_explanation")
        return assessment

    @staticmethod
    def _build_display_report(
        evidence_snapshot: Dict[str, Any],
        assessment: Dict[str, Any],
    ) -> Dict[str, Any]:
        evidence = evidence_snapshot.get("historical_evidence") or {}
        top_matches = list(evidence.get("top_matches") or [])[:10]
        outcome_distribution = evidence.get("outcome_distribution") or {}
        weighted_statistics = evidence.get("weighted_statistics") or {}
        net_profit_statistics = evidence.get("net_profit_statistics") or {}
        outcome_characteristics = evidence.get("outcome_characteristics") or {}

        top_10_patterns = []
        for rank, pattern in enumerate(top_matches, start=1):
            top_10_patterns.append({
                "rank": rank,
                "id": pattern.get("id"),
                "structure_time": pattern.get("timestamp"),
                "structure_price": pattern.get("price"),
                "event_type": pattern.get("event_type"),
                "direction": pattern.get("direction"),
                "session": pattern.get("session"),
                "timeframe": pattern.get("timeframe"),
                "total_similarity": pattern.get("similarity"),
                "outcome": pattern.get("outcome"),
                "net_profit": LLMMSAAgent._json_value(pattern.get("net_profit")),
                "entry_time": LLMMSAAgent._json_value(pattern.get("entry_time")),
                "entry_price": LLMMSAAgent._json_value(pattern.get("entry_price")),
                "exit_time": LLMMSAAgent._json_value(pattern.get("exit_time")),
                "exit_price": LLMMSAAgent._json_value(pattern.get("exit_price")),
                "duration_minutes": LLMMSAAgent._json_value(
                    pattern.get("duration_minutes")
                ),
                "close_reason": LLMMSAAgent._json_value(pattern.get("close_reason")),
                "rejection_reason": LLMMSAAgent._json_value(
                    pattern.get("reject_reason_raw")
                    or pattern.get("rejection_reason")
                ),
                "rejection_reason_code": LLMMSAAgent._json_value(
                    pattern.get("reject_reason_code")
                ),
            })

        top_3_breakdowns = []
        for pattern in top_matches[:3]:
            breakdown = pattern.get("similarity_breakdown")
            if not isinstance(breakdown, dict):
                continue
            top_3_breakdowns.append({
                "rank": pattern.get("similarity_breakdown_rank"),
                "pattern_id": pattern.get("id"),
                "total_similarity": breakdown.get("total_similarity"),
                "method": breakdown.get("method"),
                "factors": deepcopy(breakdown.get("factors") or []),
                "not_used_in_similarity": deepcopy(
                    breakdown.get("not_used_in_similarity") or []
                ),
            })

        closest_pattern_detail = deepcopy(top_10_patterns[0]) if top_10_patterns else None
        return {
            "conclusion": {
                "verdict": assessment.get("verdict"),
                "vote": assessment.get("vote"),
                "confidence": assessment.get("confidence"),
                "data_quality": assessment.get("data_quality"),
                "recommended_action": assessment.get("recommended_action"),
                "mode": "SHADOW",
            },
            "simple_explanation": assessment.get("user_explanation"),
            "evidence_summary": {
                "total_patterns": evidence.get("total_count", 0),
                "completed_patterns": evidence.get("completed_count", 0),
                "wins": outcome_distribution.get("wins", 0),
                "losses": outcome_distribution.get("losses", 0),
                "rejected": outcome_distribution.get("rejected", 0),
                "executed_win_rate": outcome_distribution.get("executed_win_rate"),
                "weighted_win_rate": weighted_statistics.get("weighted_win_rate"),
                "total_net_profit": net_profit_statistics.get("total"),
                "average_net_profit": net_profit_statistics.get("average"),
            },
            "top_10_patterns": top_10_patterns,
            "top_3_breakdowns": top_3_breakdowns,
            "closest_pattern_detail": closest_pattern_detail,
            "win_loss_comparison": {
                "wins": deepcopy(outcome_characteristics.get("wins") or {}),
                "losses": deepcopy(outcome_characteristics.get("losses") or {}),
                "current_pattern_comparison": assessment.get(
                    "current_pattern_comparison"
                ),
                "win_pattern_characteristics": deepcopy(
                    assessment.get("win_pattern_characteristics") or []
                ),
                "loss_pattern_characteristics": deepcopy(
                    assessment.get("loss_pattern_characteristics") or []
                ),
            },
            "confirmation_and_invalidation": {
                "confirmation_conditions": deepcopy(
                    assessment.get("confirmation_conditions") or []
                ),
                "invalidation_conditions": deepcopy(
                    assessment.get("invalidation_conditions") or []
                ),
                "counter_scenario": assessment.get("counter_scenario"),
            },
        }

    @staticmethod
    def _json_value(value: Any) -> Any:
        if isinstance(value, float) and not math.isfinite(value):
            return None
        return value

    @staticmethod
    def _required_string(result: Dict[str, Any], key: str) -> str:
        value = result.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} must be a non-empty string")
        return value.strip()

    @staticmethod
    def _required_string_list(result: Dict[str, Any], key: str) -> list[str]:
        value = result.get(key)
        if not isinstance(value, list) or not value or any(
            not isinstance(item, str) or not item.strip() for item in value
        ):
            raise ValueError(f"{key} must be a non-empty list of strings")
        return [item.strip() for item in value]

    @staticmethod
    def _required_action(
        result: Dict[str, Any],
        evidence_snapshot: Optional[Dict[str, Any]] = None,
    ) -> str:
        value = result.get("recommended_action")
        if not isinstance(value, str) or value.strip().upper() not in {
            "WAIT", "MONITOR", "ABSTAIN"
        }:
            raise ValueError("recommended_action must be WAIT, MONITOR, or ABSTAIN")
        action = value.strip().upper()
        setup_status = str(
            (evidence_snapshot or {}).get("setup", {}).get("status", "")
        ).upper()
        if setup_status == "PENDING_SETUP" and action not in {"WAIT", "ABSTAIN"}:
            raise ValueError(
                "recommended_action for PENDING_SETUP must be WAIT or ABSTAIN"
            )
        return action

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
            "historical_read": "Data tidak tersedia",
            "reasoning": reason,
            "facts": ["Penilaian LLM MSA tidak tersedia."],
            "interpretation": reason,
            "recommended_action": "ABSTAIN",
            "win_pattern_characteristics": ["Data tidak tersedia"],
            "loss_pattern_characteristics": ["Data tidak tersedia"],
            "current_pattern_comparison": "Data tidak tersedia",
            "confirmation_conditions": ["Tunggu konfirmasi MSA deterministik."],
            "invalidation_conditions": ["Evidence masih belum tersedia."],
            "counter_scenario": "Skenario tandingan yang andal belum dapat dievaluasi.",
            "user_explanation": reason,
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