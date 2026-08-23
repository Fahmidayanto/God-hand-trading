"""
LLM Decision Engine - LLM-Based Trade Decision with 7-Step Reasoning

LLM-based decision engine yang consume ReplayContext (dari Fase 1) dan
menghasilkan TradeSetup dengan output schema yang SAMA dengan SmartRuleEngine
(untuk A/B test nanti).

Key differentiator dari SmartRuleEngine:
- Prompt memaksa 7-step reasoning chain (regime → structure → catalyst →
  risk asymmetry → path dependency → decision → invalidation)
- LLM bisa "berpikir dalam" — tidak cuma pattern matching
- Confidence + reasoning dalam natural language
- Lebih lambat (LLM call), lebih boros cost, tapi potentially lebih pintar

Ponytail:
- Schema-compatible dengan SmartRuleEngine (A/B test ready)
- Reuse 9-tier fallback chain pattern dari LLMTradeSetup existing
- Time-anchored, replay-safe (tidak baca datetime.now())
- Pure function untuk prompt building + response parsing
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
from loguru import logger

# Reuse analyzer + SmartRuleEngine schema
try:
    from ..analyzers.replay_structure_provider import ReplayContext
    from .smart_rule_engine import TradeSetup, Signal
except ImportError:
    try:
        from verification_system.analyzers.replay_structure_provider import ReplayContext
        from verification_system.decision_engines.smart_rule_engine import TradeSetup, Signal
    except ImportError:
        import os
        import sys
        _here = os.path.dirname(os.path.abspath(__file__))
        _root = os.path.dirname(os.path.dirname(_here))
        if _root not in sys.path:
            sys.path.insert(0, _root)
        from verification_system.analyzers.replay_structure_provider import ReplayContext
        from verification_system.decision_engines.smart_rule_engine import TradeSetup, Signal


# ── 7-step reasoning prompt template ───────────────────────────────────────

REASONING_CHAIN_SYSTEM_PROMPT = """You are an elite XAUUSD trader with 15+ years of experience in ICT/SMC methodology.

Given a structured market context, you MUST reason through 7 explicit steps before producing a trade decision. Do NOT skip steps. Do NOT produce a decision without completing all 7. Even if the decision is HOLD or BLOCKED, you MUST provide explicit analysis for all reasoning categories.

REASONING CHAIN (mandatory):

1. REGIME — What is the current market regime across timeframes? Is M15/H1/H4 aligned? Volatility expanding or contracting? Confidence in regime reading (0-1)?

2. STRUCTURE — Where are the nearest liquidity pools (BSL above, SSL below)? Are there fresh order blocks or FVGs near price? What is the most recent BoS/CHoCH direction?

3. CATALYST — Any high-impact event in the next 2-72 hours (FOMC, CPI, NFP)? How might it move price?

4. RISK ASYMMETRY — For BUY case: probability and target. For SELL case: probability and target. Which has better expected value? R:R calculation.

5. PATH DEPENDENCY — Is price more likely to hit SL first or TP first? Why? Any liquidity sweep expected before move?

6. DECISION — Final signal (BUY/SELL/HOLD/BLOCKED), entry price, SL (with structural reason), TP1 (with target reason), TP2 (extended target if applicable), lot size for 1% risk on $1000.

7. INVALIDATION — What specific price action or event would invalidate this trade and require immediate exit or reassessment?

OUTPUT FORMAT (strict JSON, no prose outside):
{
    "reasoning": {
        "regime": "<Analysis of M15/H1/H4 trend alignment, ADX, and volatility state>",
        "structure": "<Analysis of BSL/SSL liquidity, Order Blocks, and FVGs near price>",
        "catalyst": "<Analysis of upcoming high-impact economic calendar events or state of news catalyst>",
        "risk_asymmetry": "<Analysis of BUY vs SELL probability and R:R expected value comparison>",
        "path_dependency": "<Analysis of whether SL or TP will be hit first and liquidity sweep path>",
        "invalidation": "<Specific price level or event that invalidates this scenario>"
    },
    "decision": {
        "signal": "BUY" | "SELL" | "HOLD" | "BLOCKED",
        "entry_price": <float>,
        "sl": <float>,
        "tp1": <float>,
        "tp2": <float or null>,
        "lot_size": <float, 2 decimals>,
        "confidence": <float 0-1>,
        "summary": "<one-sentence executive summary of the decision>"
    }
}

Be concise but precise in reasoning. Each step max 2-3 sentences. Use technical language (liquidity sweep, mitigation, breaker, etc.). Language: Indonesian or English."""


# ── LLM provider config (mirror LLMTradeSetup) ─────────────────────────────

class LLMProvider:
    """Single LLM provider config."""
    def __init__(self, name: str, base_url: str, api_key: str, model_id: str):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model_id = model_id

    def call(self, system_prompt: str, user_prompt: str, timeout: int = 30) -> Optional[str]:
        """Call LLM API. Return content string or None on failure."""
        try:
            url = f"{self.base_url}/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": self.model_id,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 1500,
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            logger.debug(f"[{self.name}] LLM call OK ({len(content)} chars)")
            return content
        except Exception as exc:
            logger.warning(f"[{self.name}] LLM call failed: {exc}")
            return None


# ── Main engine ─────────────────────────────────────────────────────────────

class LLMDecisionEngine:
    """
    LLM-based decision engine dengan fallback chain.
    Output schema compatible dengan SmartRuleEngine.TradeSetup.
    """

    def __init__(
        self,
        balance: float = 1000.0,
        risk_pct: float = 1.0,
        min_rr: float = 2.0,
        contract_size: float = 100.0,
    ):
        self.balance = balance
        self.risk_pct = risk_pct
        self.min_rr = min_rr
        self.contract_size = contract_size

        # Build fallback chain (priorities: 9inference → Groq → NVIDIA models)
        self.providers: List[LLMProvider] = self._build_default_providers()
        logger.info(
            f"LLMDecisionEngine initialized | "
            f"{len(self.providers)} providers in chain"
        )

    def _build_default_providers(self) -> List[LLMProvider]:
        """Build default 9-tier fallback chain."""
        return [
            LLMProvider(
                "9inference-DeepSeek",
                "https://9inference.cloud/v1/package",
                os.getenv("NINEINFERENCE_API_KEY", ""),
                "deepseek-v4-flash-0731",
            ),
            LLMProvider(
                "Groq-Qwen",
                "https://api.groq.com/openai/v1",
                os.getenv("GROQ_API_KEY", ""),
                "qwen/qwen3.6-27b",
            ),
            LLMProvider(
                "NVIDIA-MiniMax-M3",
                "https://integrate.api.nvidia.com/v1",
                os.getenv("NVIDIA_MINIMAX_API_KEY", os.getenv("NVIDIA_API_KEY", "")),
                "minimaxai/minimax-m3",
            ),
        ]

    def decide(self, context: ReplayContext) -> TradeSetup:
        """
        Run LLM-based decision pada ReplayContext.

        Returns TradeSetup (same schema as SmartRuleEngine).
        On LLM failure: returns HOLD with low confidence.
        """
        # Pre-flight: block trade if high-impact event imminent
        events = context.events or {}
        if events.get("should_avoid_trading"):
            return TradeSetup(
                signal=Signal.BLOCKED,
                entry_price=context.market_data.get("current_price", 0.0),
                sl=0.0,
                tp1=0.0,
                confidence=0.0,
                reasoning=f"BLOCKED pre-LLM: {events.get('avoid_reason')}",
                block_reason=events.get("avoid_reason"),
            )

        # Build prompt dari ReplayContext
        user_prompt = self._build_user_prompt(context)

        # Call LLM dengan fallback chain
        response_text = None
        for provider in self.providers:
            response_text = provider.call(REASONING_CHAIN_SYSTEM_PROMPT, user_prompt)
            if response_text:
                break

        if not response_text:
            return TradeSetup(
                signal=Signal.HOLD,
                entry_price=context.market_data.get("current_price", 0.0),
                sl=0.0,
                tp1=0.0,
                confidence=0.0,
                reasoning="LLM call failed across all providers",
            )

        # Parse response ke TradeSetup
        return self._parse_response(response_text, context)

    def _build_user_prompt(self, context: ReplayContext) -> str:
        """
        Build user prompt dari ReplayContext.
        Gunakan ReplayContext.to_llm_prompt_context() yang sudah formatted.
        Plus tambahkan balance/risk info.
        """
        ctx_text = context.to_llm_prompt_context()
        return f"""{ctx_text}

=== ACCOUNT CONFIG ===
Balance: ${self.balance:.2f}
Risk per trade: {self.risk_pct}%
Contract size (XAUUSD): {self.contract_size} oz/lot
Minimum R:R: {self.min_rr}

=== TASK ===
Apply the 7-step reasoning chain. Output strict JSON only.
Compute lot_size for {self.risk_pct}% risk on ${self.balance:.2f} balance.
SL distance = |entry_price - sl|. Lot = (balance * risk_pct/100) / (sl_distance * contract_size)."""

    def _parse_response(
        self, response_text: str, context: ReplayContext
    ) -> TradeSetup:
        """Parse LLM JSON response → TradeSetup."""
        # Try to extract JSON dari response (LLM kadang tambah prose)
        json_match = re.search(r"\{[\s\S]*\}", response_text)
        if not json_match:
            return TradeSetup(
                signal=Signal.HOLD,
                entry_price=context.market_data.get("current_price", 0.0),
                sl=0.0,
                tp1=0.0,
                confidence=0.0,
                reasoning=f"LLM response not parseable: {response_text[:200]}",
            )

        try:
            data = json.loads(json_match.group(0))
        except json.JSONDecodeError as exc:
            return TradeSetup(
                signal=Signal.HOLD,
                entry_price=context.market_data.get("current_price", 0.0),
                sl=0.0,
                tp1=0.0,
                confidence=0.0,
                reasoning=f"LLM JSON parse error: {exc}",
            )

        decision = data.get("decision", {})
        reasoning = data.get("reasoning", {})

        # Map signal string to enum
        sig_str = decision.get("signal", "HOLD").upper()
        try:
            signal = Signal(sig_str)
        except ValueError:
            signal = Signal.HOLD

        # Compose rich structured reasoning text with all 6 categories
        reasoning_parts = []
        summary = str(decision.get("summary", "")).strip()
        if summary:
            reasoning_parts.append(f"📌 Ringkasan: {summary}\n")

        labels = {
            "regime": "1. Regime & Multi-Timeframe",
            "structure": "2. Struktur Pasar (SMC / Liquidity / OB / FVG)",
            "catalyst": "3. Katalis Berita Ekonomi",
            "risk_asymmetry": "4. Asimetri Risiko & R:R",
            "path_dependency": "5. Jalur Pergerakan Harga",
            "invalidation": "6. Syarat Pembatalan (Invalidation)",
        }
        for step, label in labels.items():
            val = reasoning.get(step, "")
            if val:
                reasoning_parts.append(f"• {label}: {str(val).strip()}")

        reasoning_text = "\n".join(reasoning_parts) if len(reasoning_parts) > 1 else (summary or "Analisis 7-step reasoning selesai.")

        # Validate numbers (handle None gracefully — LLM can return null for HOLD/no-trade)
        def _safe_float(value, default):
            if value is None:
                return default
            try:
                return float(value)
            except (TypeError, ValueError):
                return default

        default_entry = context.market_data.get("current_price", 0.0) or 0.0
        entry = _safe_float(decision.get("entry_price"), default_entry)
        sl = _safe_float(decision.get("sl"), 0.0)
        tp1 = _safe_float(decision.get("tp1"), 0.0)
        tp2_val = decision.get("tp2")
        tp2 = _safe_float(tp2_val, 0.0) if tp2_val is not None else None
        confidence = _safe_float(decision.get("confidence"), 0.5)
        confidence = max(0.0, min(1.0, confidence))

        # If signal is HOLD/BLOCKED, normalize entry/sl/tp to 0
        if signal in (Signal.HOLD, Signal.BLOCKED):
            entry = default_entry if default_entry else 0.0
            sl = 0.0
            tp1 = 0.0
            tp2 = None

        # Recompute lot size defensively (LLM sometimes hallucinate)
        lot_size = self._calc_lot_size(entry, sl, decision.get("lot_size"))

        # Compute R:R
        rr = 0.0
        if entry != sl and tp1 != 0:
            risk = abs(entry - sl)
            reward = abs(tp1 - entry)
            rr = reward / risk if risk > 0 else 0.0

        # Collect confluences from reasoning (best-effort)
        confluences = []
        if "OB" in reasoning.get("structure", "") or "order block" in reasoning.get("structure", "").lower():
            confluences.append("LLM_OB_mentioned")
        if "FVG" in reasoning.get("structure", "") or "fair value" in reasoning.get("structure", "").lower():
            confluences.append("LLM_FVG_mentioned")
        if "liquidity" in reasoning.get("structure", "").lower():
            confluences.append("LLM_liquidity_mentioned")

        return TradeSetup(
            signal=signal,
            entry_price=entry,
            sl=sl,
            tp1=tp1,
            tp2=tp2,
            lot_size=lot_size,
            risk_pct=self.risk_pct,
            rr_ratio=rr,
            confidence=confidence,
            reasoning=reasoning_text,
            confluences=confluences,
            filters_applied=["llm_based"],
        )

    def _calc_lot_size(
        self, entry: float, sl: float, llm_lot: Optional[float]
    ) -> float:
        """Defensive lot size calc — trust our math over LLM's."""
        if entry == 0 or sl == 0:
            return float(llm_lot) if llm_lot else 0.0
        sl_distance = abs(entry - sl)
        if sl_distance <= 0:
            return 0.0
        risk_amount = self.balance * (self.risk_pct / 100.0)
        risk_per_lot = sl_distance * self.contract_size
        if risk_per_lot <= 0:
            return 0.0
        return round(risk_amount / risk_per_lot, 2)


# ── CLI smoke test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Smoke test: LLMDecisionEngine + ReplayStructureProvider integration.

    Note: ini real LLM call. Butuh API key aktif (sudah di-hardcode).
    Untuk mock test, set DRY_RUN=1.
    """
    import sys
    import os
    import numpy as np
    import pandas as pd

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    from verification_system.analyzers.replay_structure_provider import ReplayStructureProvider

    np.random.seed(42)
    n = 500
    base = 2000.0
    prices = base + np.cumsum(np.random.randn(n) * 0.5 + 0.2)
    df_m15 = pd.DataFrame(
        {
            "time": pd.date_range("2023-04-15", periods=n, freq="15min"),
            "open": prices + np.random.randn(n) * 0.3,
            "high": prices + abs(np.random.randn(n)) * 0.8,
            "low": prices - abs(np.random.randn(n)) * 0.8,
            "close": prices,
        }
    )
    df_h1 = df_m15.iloc[::4].reset_index(drop=True)
    df_h4 = df_m15.iloc[::16].reset_index(drop=True)

    provider = ReplayStructureProvider()
    engine = LLMDecisionEngine(balance=1000.0, risk_pct=1.0)

    if os.getenv("DRY_RUN"):
        print("DRY_RUN mode — testing prompt builder only, no LLM call")
        ctx = provider.build(
            ohlc_by_timeframe={"M15": df_m15, "H1": df_h1, "H4": df_h4},
            anchor_ts=datetime(2023, 4, 18, 12, 0, tzinfo=timezone.utc),
            anchor_idx_by_timeframe={"M15": 400, "H1": 100, "H4": 25},
        )
        prompt = engine._build_user_prompt(ctx)
        print("=" * 60)
        print("USER PROMPT (sent to LLM):")
        print("=" * 60)
        print(prompt[:2000])
        print("...")
    else:
        print("LIVE mode — calling LLM (real API)")
        ctx = provider.build(
            ohlc_by_timeframe={"M15": df_m15, "H1": df_h1, "H4": df_h4},
            anchor_ts=datetime(2023, 4, 18, 12, 0, tzinfo=timezone.utc),
            anchor_idx_by_timeframe={"M15": 400, "H1": 100, "H4": 25},
        )
        setup = engine.decide(ctx)
        print("=" * 60)
        print("LLM TRADE SETUP:")
        print("=" * 60)
        print(f"Signal: {setup.signal.value}")
        print(f"Entry: {setup.entry_price}")
        print(f"SL: {setup.sl}  | TP1: {setup.tp1}  | TP2: {setup.tp2}")
        print(f"Lot: {setup.lot_size}  | R:R: {setup.rr_ratio:.2f}  | Conf: {setup.confidence:.2f}")
        print(f"Reasoning: {setup.reasoning}")
        print(f"Confluences: {setup.confluences}")
