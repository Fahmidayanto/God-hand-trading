"""
LLM Trade Setup - Replay Trades Decision Engine

A dedicated LLM service for the Replay Trades feature. Given a market context
(structure, candles, ATR, balance, news), it asks an LLM to decide the full
trade setup: signal, SL, TP, lot size, and reasoning.

Uses a sequential 9-tier fallback chain, with 9inference DeepSeek V4 Flash as
the primary model (fast + cheap), then NVIDIA models, AgentRouter, Groq, and
Gemini as backups.

This is intentionally separate from the SentimentAgent's news-only analysis so
the replay feature can evolve independently.
"""

import json
import os
import re
from typing import Any, Dict, List, Optional

from loguru import logger


class LLMTradeSetup:
    """Decide a full trade setup (signal/SL/TP/lot) via LLM with fallback chain."""

    def __init__(
        self,
        # 9inference DeepSeek (primary)
        nineinference_api_key: str = "sk_live_66f741e252367899a56bef4608f5acf27003944a9e3b535f",
        nineinference_base_url: str = "https://9inference.cloud/v1/package",
        nineinference_model_id: str = "deepseek-v4-flash-0731",
        # AgentRouter GLM
        agentrouter_api_key: str = "sk-lHCp3TY8vQ8OvM422AtXGqr8gC5iGDsuQ9MYL6BDzACfmWzR",
        agentrouter_base_url: str = "https://agentrouter.org/v1",
        agentrouter_model_id: str = "glm-5.2",
        # Groq
        groq_api_key: str = "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",
        groq_base_url: str = "https://api.groq.com/openai/v1",
        groq_model_id: str = "qwen/qwen3.6-27b",
        # NVIDIA models
        nvidia_120b_api_key: str = "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",
        nvidia_550b_api_key: str = "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",
        nvidia_minimax_api_key: str = "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",
        nvidia_inkling_api_key: str = "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",
        nvidia_laguna_api_key: str = "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",
        nvidia_glm_api_key: str = "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",
        nvidia_base_url: str = "https://integrate.api.nvidia.com/v1",
    ):
        self.nineinference_api_key = nineinference_api_key
        self.nineinference_base_url = nineinference_base_url
        self.nineinference_model_id = nineinference_model_id

        self.agentrouter_api_key = agentrouter_api_key
        self.agentrouter_base_url = agentrouter_base_url
        self.agentrouter_model_id = agentrouter_model_id

        self.groq_api_key = os.getenv("GROQ_API_KEY", groq_api_key)
        self.groq_base_url = groq_base_url
        self.groq_model_id = os.getenv("GROQ_MODEL", groq_model_id)

        self.nvidia_base_url = nvidia_base_url
        self.nvidia_models = [
            ("NVIDIA MiniMax M3", nvidia_minimax_api_key, "minimaxai/minimax-m3"),
            ("NVIDIA GLM 5.2", nvidia_glm_api_key, "z-ai/glm-5.2"),
            ("NVIDIA Laguna XS", nvidia_laguna_api_key, "poolside/laguna-xs-2.1"),
            ("NVIDIA Inkling", nvidia_inkling_api_key, "thinkingmachines/inkling"),
            ("NVIDIA Nemotron 120B", nvidia_120b_api_key, "nvidia/nemotron-3-super-120b-a12b"),
            ("NVIDIA Nemotron 550B", nvidia_550b_api_key, "nvidia/nemotron-3-ultra-550b-a55b"),
        ]

        logger.info(f"✅ LLMTradeSetup initialized | primary: Groq Qwen ({self.groq_model_id})")

    # ── Prompt builder ──────────────────────────────────────────────────────

    def _build_prompt(self, context: Dict[str, Any]) -> str:
        """Build a prompt that asks the LLM to decide the full trade setup."""
        structure = context.get("structure", "unknown")
        atr = context.get("atr")
        balance = context.get("balance", 1000.0)
        risk_pct = context.get("risk_pct", 2.0)
        entry_price = context.get("entry_price")
        news = context.get("news", "no news")
        timeframe = context.get("timeframe", "M15")
        candles_summary = context.get("candles_summary", "n/a")
        ea_filters = context.get("ea_filters") or {}
        market_context = context.get("market_context") or {}

        atr_str = f"${atr:.2f}" if atr is not None else "n/a"
        h1_trend = market_context.get("h1_trend", "n/a")
        h1_ema = market_context.get("h1_ema200")
        h1_str = f"${h1_ema:.2f}" if h1_ema is not None else "n/a"
        h4_trend = market_context.get("h4_trend", "n/a")
        h4_ema = market_context.get("h4_ema200")
        h4_str = f"${h4_ema:.2f}" if h4_ema is not None else "n/a"
        candle_quality = market_context.get("candle_quality", "n/a")
        session_name = market_context.get("session_name", "n/a")

        bos_cycle = market_context.get("bos_cycle_count", 1)
        ema_stretch = market_context.get("ema_stretch_ratio")
        exhaustion_stage = market_context.get("exhaustion_stage", "n/a")
        ema_stretch_str = f"{ema_stretch:.2f}x ATR" if ema_stretch is not None else "n/a"

        nearest_supply = market_context.get("nearest_supply_zone")
        nearest_demand = market_context.get("nearest_demand_zone")
        nearest_bsl = market_context.get("nearest_bsl_target")
        nearest_ssl = market_context.get("nearest_ssl_target")

        smc_lines = []
        if nearest_supply:
            smc_lines.append(f"  * Nearest Supply (Resistance Obstacle): ${nearest_supply.get('bottom', 0):.2f} - ${nearest_supply.get('top', 0):.2f}")
        else:
            smc_lines.append("  * Nearest Supply (Resistance Obstacle): None nearby (Clean runway above)")

        if nearest_demand:
            smc_lines.append(f"  * Nearest Demand (Support Obstacle): ${nearest_demand.get('bottom', 0):.2f} - ${nearest_demand.get('top', 0):.2f}")
        else:
            smc_lines.append("  * Nearest Demand (Support Obstacle): None nearby (Clean runway below)")

        if nearest_bsl:
            smc_lines.append(f"  * Buy-Side Liquidity Target (BSL / EQH): ${nearest_bsl.get('price', 0):.2f}")
        if nearest_ssl:
            smc_lines.append(f"  * Sell-Side Liquidity Target (SSL / EQL): ${nearest_ssl.get('price', 0):.2f}")

        # Summarize which EA entry filters are active so the LLM can weigh them.
        filter_lines = []
        if ea_filters.get("h1_ema200"): filter_lines.append("- H1 EMA200 filter: ON (price must align with H1 EMA200 trend)")
        if ea_filters.get("h4_ema"): filter_lines.append("- H4 EMA filter: ON (price must align with H4 EMA trend)")
        if ea_filters.get("ema_slope"): filter_lines.append("- EMA slope filter: ON (M15 EMA200 must move in trade direction)")
        if ea_filters.get("body_ratio"): filter_lines.append("- Body ratio filter: ON (candle body must be >= 40% of range)")
        if ea_filters.get("session"): filter_lines.append("- Session filter: ON (block entries at 01:00 UTC)")
        if ea_filters.get("ema_stretch_filter"): filter_lines.append("- EMA Stretch Filter: ON (if price distance from M15 EMA200 > 3.5x ATR, must signal HOLD or reduce risk_pct to 1.0% due to mean-reversion risk)")
        if ea_filters.get("bos_cycle_filter"): filter_lines.append("- BOS Cycle Stage Filter: ON (if consecutive BOS >= 4 without pullback, must signal HOLD or reduce risk_pct to 1.0% due to trend exhaustion risk)")
        if not filter_lines:
            filter_lines.append("- No EA entry filters active")

        return f"""
You are an expert XAUUSD (Gold) institutional trade setup analyst for a replay simulator.
CRITICAL INSTRUCTION: Return valid raw JSON ONLY. Do NOT output <think> tags, monologue, thoughts, or text outside JSON. Start your response immediately with the '{' character and end with '}'.
Evaluate market direction, multi-timeframe conviction, and decide the FULL trade setup based on live market context.

Live Market & Multi-Timeframe Context:
- Timeframe: {timeframe}
- Market structure: {structure}
- Entry price: {entry_price}
- Volatility (ATR 14): {atr_str}
- Price Action Swing Range: {candles_summary}
- Multi-Timeframe Trend & Indicator Alignment:
  * H1 Trend: {h1_trend} (H1 EMA200: {h1_str})
  * H4 Trend: {h4_trend} (H4 EMA200: {h4_str})
  * Breakout Candle Quality: {candle_quality}
  * Active Trading Session: {session_name}
- Trend Cycle & Exhaustion Assessment:
  * Cycle Stage: {exhaustion_stage}
  * Consecutive BOS Count: #{bos_cycle}
  * Price Distance from M15 EMA200: {ema_stretch_str}
- Institutional Obstacles & Liquidity Pools:
{chr(10).join(smc_lines)}
- Account balance: ${balance}
- News/sentiment: {news}
- Active EA Entry Filters:
{chr(10).join(filter_lines)}

Take Profit (TP) Placement Rules:
- For BUY setup: If a Supply zone exists above entry, place TP 1.0 - 2.0 points BEFORE the Supply bottom edge (front-running resistance) or target the nearest BSL pool. If clean runway, target 1:2.0 R:R expansion.
- For SELL setup: If a Demand zone exists below entry, place TP 1.0 - 2.0 points BEFORE the Demand top edge (front-running support) or target the nearest SSL pool. If clean runway, target 1:2.0 R:R expansion.

Return raw JSON ONLY (no markdown, no preamble, no monologue). Format:
{{
  "signal": "BUY" | "SELL" | "HOLD",
  "confidence": 0.0 to 1.0,
  "risk_pct": 0.5 to 3.0,
  "sl_price": number,
  "tp_price": number,
  "lot_size": number,
  "cycle_stage": "{exhaustion_stage}",
  "reasoning": "• Arah & Struktur: Struktur M15 mengonfirmasi CHoCH Bullish valid sebagai awal pembalikan tren (Siklus #0).\n• Stop Loss & Invalidasi: SL dipasang di 4426.46 di bawah swing low terdekat dengan buffer 1.5 poin (~292 pips).\n• Target Profit: TP dipasang di 4514.03 menyasar zona likuiditas ekspansi atas dengan rasio Risk:Reward 1:2.0.\n• Alokasi Risiko: Mengalokasikan risiko 2.0% dari modal $1000 ($20) dengan ukuran lot 0.01 demi disiplin modal."
}}

Aturan Wajib Bahasa & Format Reasoning:
- Kolom "reasoning" WAJIB ditulis dalam BAHASA INDONESIA yang jelas, lengkap, dan profesional tanpa tanda titik-titik (...) atau teks kosong.
- Tuliskan persis 4 poin bullet (•) dengan baris baru (\n) yang memuat kalimat analisa lengkap:
  • Arah & Struktur: Nyatakan konfirmasi arah tren, event struktur M15 (apakah CHOCH Siklus #0 atau BOS dengan nomor urutannya), dan evaluasi regangan harga terhadap EMA200.
  • Stop Loss & Invalidasi: Nyatakan level harga SL, alasan teknis penempatan pada swing level/buffer ATR, dan jarak risiko pips dari titik entry.
  • Target Profit: Nyatakan level harga TP, target area likuiditas atau Supply/Demand yang dituju, serta rasio Risk:Reward (R:R).
  • Alokasi Risiko: Nyatakan persentase risiko modal yang dialokasikan dan ukuran lot posisi yang dihitung secara disiplin.
- Format pilihan cycle_stage wajib menyesuaikan konteks: jika overextended gunakan format "🔴 OVEREXTENDED (BOS #{bos_cycle}, Stretch {ema_stretch_str})", jika siklus awal gunakan "🟢 FRESH_CYCLE (BOS #{bos_cycle})" atau "🟣 REVERSAL_SHIFT (CHOCH)", jika pertengahan gunakan "🟡 MID_CYCLE (BOS #{bos_cycle})".

Confidence & Directional Conviction Rubric:
- High Conviction (Confidence 0.80 - 0.95):
  * M15 structure is verified. If H1/H4 data is available, it aligns with trend. Breakout candle is strong.
  * Allocate 2.0% - 3.0% dynamic risk.
- Moderate Conviction (Confidence 0.65 - 0.79):
  * Valid M15 structure (CHoCH/BOS). If H1/H4 data is "n/a" or filter is OFF, proceed confidently based on M15 market structure and local price action!
  * Allocate 1.0% - 2.0% dynamic risk.
- Invalidation & HOLD Rule (Confidence < 0.60):
  * Signal HOLD ONLY when there is an explicit structural failure (e.g. price is confirmed opposite to trend while filter is ON, or extreme excessive risk).
  * CRITICAL RULE: Do NOT signal HOLD simply because H1/H4 or session data is "n/a"! If higher-timeframe data is "n/a", treat M15 structure as primary and execute the trade setup.

SL Determination Workflow (Check Last Structure Level First -> Evaluate Threshold):
1. First, inspect the distance from Entry Price to the nearest structural Swing Low (LL) for BUY or Swing High (HH) for SELL.
2. Tier 1 - Reasonable Structure (Distance is between 1.5x and 4.0x ATR / approx 150 - 400 Pips / $15 - $40):
   * Place SL safely BEYOND the actual Swing Structure level (LL/HH) with a small buffer (e.g. 1.0 - 2.0 points beyond).
   * Size lot down (e.g. 0.01 lot) so total risk remains controlled (~1.5% to 3.5% of ${balance}).
3. Tier 2 - Extreme Macro Distance (Distance > 4.0x ATR / > 400 Pips / > $40 - $60, e.g. multi-hour macro extreme):
   * Do NOT anchor SL to extreme macro lows/highs! Instead, use the Local Pullback Base / 1.5x - 2.0x ATR buffer (approx 150 - 250 Pips / $15 - $25) to maintain trade viability.
4. Tier 3 - Too Cramped (< 1.0x ATR / < 100 Pips / < $10):
   * Add a buffer so SL is never tighter than 1.2x ATR to prevent wick noise stops.

TP Placement (Strict Minimum 1:1.5 to 1:2.5 Risk-to-Reward):
* TP Distance MUST be at least 1.5x to 2.5x greater than SL Distance (NEVER place TP closer than SL!).
* Target realistic liquidity expansion zones.

Lot Size Formula: lot_size = (balance * (risk_pct / 100)) / (abs(entry_price - sl_price) * 100), rounded to 2 decimals (minimum 0.01).
"""

    # ── JSON parsing & Sanitizer ───────────────────────────────────────────

    def _robust_json_parse(self, content: str) -> Dict[str, Any]:
        """Robustly clean and parse JSON from LLM responses."""
        if not content:
            raise ValueError("Empty response content from LLM")

        cleaned = content.strip()
        # Strip <think>...</think> tags if model produces reasoning thoughts
        cleaned = re.sub(r"<think>[\s\S]*?</think>", "", cleaned).strip()

        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
        if match:
            cleaned = match.group(1).strip()
        else:
            brace_match = re.search(r"(\{[\s\S]*\})", cleaned)
            if brace_match:
                cleaned = brace_match.group(1).strip()
            else:
                idx = cleaned.find("{")
                if idx != -1:
                    cleaned = cleaned[idx:]

        data: Dict[str, Any] = {}
        try:
            data = json.loads(cleaned, strict=False)
        except Exception:
            # Auto-repair truncated JSON
            repaired = cleaned.strip()
            unescaped_quotes = len(re.findall(r'(?<!\\)"', repaired))
            if unescaped_quotes % 2 != 0:
                repaired += '"'
            open_braces = repaired.count("{")
            close_braces = repaired.count("}")
            if open_braces > close_braces:
                repaired += "}" * (open_braces - close_braces)
            try:
                data = json.loads(repaired, strict=False)
            except Exception:
                raise ValueError(f"Failed to parse JSON: {content}")

        # Normalize reasoning key and format so frontend always receives valid reasoning string
        if "reason" in data and "reasoning" not in data:
            data["reasoning"] = data["reason"]
        elif "analysis" in data and "reasoning" not in data:
            data["reasoning"] = data["analysis"]
        elif "explanation" in data and "reasoning" not in data:
            data["reasoning"] = data["explanation"]
        elif "alasan" in data and "reasoning" not in data:
            data["reasoning"] = data["alasan"]

        if isinstance(data.get("reasoning"), list):
            data["reasoning"] = "\n".join(str(item) for item in data["reasoning"])
        elif isinstance(data.get("reasoning"), dict):
            data["reasoning"] = "\n".join(f"• {k}: {v}" for k, v in data["reasoning"].items())

        return data

    def _sanitize_trade_setup(self, data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and enrich LLM response with robust fallback for cycle stage and reasoning."""
        market_context = context.get("market_context") or {}
        exhaustion_stage = market_context.get("exhaustion_stage")
        bos_cycle = market_context.get("bos_cycle_count", 1)
        ema_stretch = market_context.get("ema_stretch_ratio")
        ema_stretch_str = f"{ema_stretch:.2f}x ATR" if ema_stretch is not None else "n/a"
        structure = context.get("structure", "Market Structure")
        signal = str(data.get("signal", "HOLD")).upper()
        entry_price = float(context.get("entry_price") or data.get("entry_price") or 0.0)
        sl_price = float(data.get("sl_price") or 0.0)
        tp_price = float(data.get("tp_price") or 0.0)
        risk_pct = float(data.get("risk_pct") or 1.0)
        lot_size = float(data.get("lot_size") or 0.01)
        balance = float(context.get("balance") or 1000.0)

        # 1. Sanitize cycle_stage: ensure dynamic accuracy
        current_stage = str(data.get("cycle_stage") or "").strip()
        if not current_stage or ("BOS #4+" in current_stage and int(bos_cycle or 1) < 4):
            if exhaustion_stage:
                prefix = "🔴 " if "OVEREXTENDED" in exhaustion_stage else ("🟣 " if ("REVERSAL" in exhaustion_stage or "CHOCH" in exhaustion_stage) else ("🟡 " if "MID_CYCLE" in exhaustion_stage else "🟢 "))
                data["cycle_stage"] = f"{prefix}{exhaustion_stage}"
            else:
                data["cycle_stage"] = f"🟢 FRESH_CYCLE (BOS #{bos_cycle})"
        elif exhaustion_stage and ("OVEREXTENDED" in current_stage or "OVEREXTENDED" in exhaustion_stage):
            prefix = "🔴 " if not current_stage.startswith("🔴") else ""
            data["cycle_stage"] = f"{prefix}{exhaustion_stage}" if not current_stage or "..." in current_stage or ("BOS #4+" in current_stage and int(bos_cycle or 1) < 4) else current_stage

        # 2. Sanitize reasoning: detect lazy placeholder dots, truncation, or missing bullets
        reasoning = str(data.get("reasoning") or "").strip()
        required_bullets = ["• Arah & Struktur:", "• Stop Loss & Invalidasi:", "• Target Profit:", "• Alokasi Risiko:"]
        missing_bullets = [b for b in required_bullets if b not in reasoning]
        has_lazy_dots = bool(re.search(r"•\s*[^:\n]+:\s*\.{2,}", reasoning)) or reasoning.count("...") >= 2 or len(reasoning.replace(".", "").strip()) < 60
        is_incomplete = bool(missing_bullets) or has_lazy_dots or not reasoning

        if is_incomplete:
            # Build high-quality dynamic Indonesian reasoning
            sl_pips = abs(entry_price - sl_price) * 10.0 if entry_price and sl_price else 0.0
            tp_pips = abs(tp_price - entry_price) * 10.0 if entry_price and tp_price else 0.0
            sl_diff = abs(entry_price - sl_price)
            rr_ratio = (abs(tp_price - entry_price) / sl_diff) if sl_diff > 0.001 else 2.0
            risk_usd = balance * (risk_pct / 100.0)

            # Structure line
            is_choch = "CHOCH" in structure.upper() or market_context.get("is_choch_reversal")
            if is_choch:
                arah_line = f"Struktur M15 mengonfirmasi {structure} valid sebagai awal pembalikan arah tren (Siklus #0)."
            elif "OVEREXTENDED" in str(data.get("cycle_stage", "")):
                arah_line = f"Struktur M15 membentuk {structure} (Siklus BOS #{bos_cycle}), namun pergerakan harga terdeteksi overextended dengan regangan EMA200 sebesar {ema_stretch_str}."
            else:
                arah_line = f"Struktur M15 mengonfirmasi kelanjutan tren {structure} (Siklus BOS #{bos_cycle}) dengan momentum yang sehat."

            # SL line
            if sl_price > 0:
                sl_line = f"SL dipasang di {sl_price:.2f} di luar level swing terdekat ({sl_pips:.1f} pips / ${abs(entry_price - sl_price):.2f}) sebagai batas invalidasi teknis."
            else:
                sl_line = "SL diposisikan di luar batas swing terdekat untuk melindungi modal dari fluktuasi harga."

            # TP line
            nearest_supply = market_context.get("nearest_supply_zone")
            nearest_demand = market_context.get("nearest_demand_zone")
            if signal == "BUY" and nearest_supply:
                target_desc = f"zona Supply resistance ${nearest_supply.get('bottom', 0):.2f}"
            elif signal == "SELL" and nearest_demand:
                target_desc = f"zona Demand support ${nearest_demand.get('top', 0):.2f}"
            else:
                target_desc = "target ekspansi likuiditas pasar"

            if tp_price > 0:
                tp_line = f"TP dipasang di {tp_price:.2f} ({tp_pips:.1f} pips) menyasar {target_desc} dengan rasio Risk:Reward 1:{rr_ratio:.1f}."
            else:
                tp_line = f"TP ditargetkan pada rasio Risk:Reward minimal 1:{rr_ratio:.1f} menuju likuiditas pasar."

            # Risk line
            risk_line = f"Mengalokasikan risiko {risk_pct:.1f}% dari modal ${balance:.0f} (~${risk_usd:.2f}) dengan ukuran lot {lot_size:.2f} demi disiplin modal."

            data["reasoning"] = (
                f"• Arah & Struktur: {arah_line}\n"
                f"• Stop Loss & Invalidasi: {sl_line}\n"
                f"• Target Profit: {tp_line}\n"
                f"• Alokasi Risiko: {risk_line}"
            )

        return data

    # ── Single model call ───────────────────────────────────────────────────

    def _call_model(self, name: str, model, prompt: str) -> Dict[str, Any]:
        """Run one model and parse its JSON response."""
        from agno.agent import Agent

        agent = Agent(
            model=model,
            description=(
                "You are an expert quantitative XAUUSD trade setup engine. "
                "You MUST ALWAYS respond with valid raw JSON only. "
                "CRITICAL: Do NOT output any <think> tags, preamble, monologue, thoughts, or text outside the JSON object. "
                "Start your response immediately with '{' and end with '}'."
            ),
        )
        response = agent.run(prompt)
        if not response or not response.content:
            raise ValueError(f"Empty response from {name}")
        content = response.content.strip()
        data = self._robust_json_parse(content)
        logger.info(f"✅ Trade setup via {name}")
        return data

    # ── Main analyze with fallback chain ────────────────────────────────────

    def analyze(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Decide trade setup via LLM with ultra-fast sequential fallback."""
        from agno.models.openai import OpenAILike

        prompt = self._build_prompt(context)
        last_err: Optional[Exception] = None

        # 1. Tier 1: Groq Ultra-Fast (Qwen 3.6 27B)
        try:
            model = OpenAILike(
                id=self.groq_model_id or "qwen/qwen3.6-27b",
                api_key=self.groq_api_key,
                base_url=self.groq_base_url,
                temperature=0.6,
                max_tokens=4096,
                timeout=15.0,
                max_retries=0,
            )
            raw = self._call_model("Groq Qwen 3.6 27b", model, prompt)
            return self._sanitize_trade_setup(raw, context)
        except Exception as e:
            last_err = e
            logger.warning(f"Groq Qwen failed, trying Tier 2 (9inference DeepSeek): {e}")

        # 2. Tier 2: 9inference DeepSeek V4 Flash (Short timeout)
        try:
            model = OpenAILike(
                id=self.nineinference_model_id,
                api_key=self.nineinference_api_key,
                base_url=self.nineinference_base_url,
                temperature=0.6,
                top_p=0.95,
                max_tokens=4096,
                timeout=12.0,
                max_retries=0,
            )
            raw = self._call_model("9inference DeepSeek V4 Flash", model, prompt)
            return self._sanitize_trade_setup(raw, context)
        except Exception as e:
            last_err = e
            logger.warning(f"DeepSeek failed, trying Tier 3 (Gemini): {e}")

        # 3. Tier 3: Gemini 2.5 Flash Fallback
        try:
            from agno.models.google import Gemini
            google_api_key = os.getenv("GOOGLE_API_KEY")
            if google_api_key:
                model = Gemini(id="gemini-2.5-flash", api_key=google_api_key)
                raw = self._call_model("Gemini 2.5 Flash", model, prompt)
                return self._sanitize_trade_setup(raw, context)
        except Exception as e:
            last_err = e
            logger.warning(f"Gemini failed, trying Tier 4 (NVIDIA): {e}")

        # 4. Tier 4: NVIDIA Models (Optimized 15s timeout per model)
        for name, api_key, model_id in self.nvidia_models:
            try:
                model = OpenAILike(
                    id=model_id,
                    api_key=api_key,
                    base_url=self.nvidia_base_url,
                    temperature=0.6,
                    max_tokens=4096,
                    timeout=15.0,
                    max_retries=0,
                )
                raw = self._call_model(name, model, prompt)
                return self._sanitize_trade_setup(raw, context)
            except Exception as e:
                last_err = e
                logger.warning(f"{name} failed: {e}")

        fallback_result = {
            "signal": "HOLD",
            "confidence": 0.0,
            "risk_pct": 0.0,
            "sl_price": 0,
            "tp_price": 0,
            "lot_size": 0,
            "reasoning": f"All LLM providers failed: {last_err}",
            "error": str(last_err),
        }
        return self._sanitize_trade_setup(fallback_result, context)


# Module-level singleton (lazy init)
_llm_trade_setup: Optional[LLMTradeSetup] = None


def get_llm_trade_setup() -> LLMTradeSetup:
    """Return a shared LLMTradeSetup instance."""
    global _llm_trade_setup
    if _llm_trade_setup is None:
        _llm_trade_setup = LLMTradeSetup()
    return _llm_trade_setup
