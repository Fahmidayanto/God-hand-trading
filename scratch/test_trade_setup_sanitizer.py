import sys
import os

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# Add backend to path
backend_path = r"B:\Project MT5\ValueCell_MT5\backend"
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.services.llm_trade_setup import LLMTradeSetup

service = LLMTradeSetup()

context = {
    "structure": "BOS (BULLISH)",
    "entry_price": 4455.65,
    "atr": 12.95,
    "balance": 1000.0,
    "news": "no news",
    "timeframe": "M15",
    "candles_summary": "recent pullback",
    "market_context": {
        "m15_ema200": 4380.20,
        "m15_trend": "BULLISH",
        "h1_ema200": 4385.10,
        "h1_trend": "BULLISH",
        "h4_ema200": 4267.14,
        "h4_trend": "BULLISH",
        "candle_body_ratio_pct": 78,
        "candle_quality": "STRONG IMPULSE (78% Body)",
        "session_name": "London Session",
        "utc_hour": 8,
        "nearest_supply_zone": {"bottom": 4482.00, "top": 4488.50},
        "nearest_demand_zone": {"bottom": 4421.20, "top": 4428.50},
        "nearest_bsl_target": {"price": 4480.50},
        "bos_cycle_count": 1,
        "ema_stretch_ratio": 5.83,
        "exhaustion_stage": "OVEREXTENDED (BOS #1, Regangan EMA 5.83x ATR - Risiko Kelelahan Tinggi)"
    },
    "ea_filters": {
        "h1_ema200": True,
        "h4_ema": True
    }
}

# Test 1: Sanitizer with empty/placeholder dots reasoning
raw_mock_dots = {
    "signal": "BUY",
    "confidence": 0.75,
    "risk_pct": 1.0,
    "sl_price": 4425.00,
    "tp_price": 4516.95,
    "lot_size": 0.01,
    "cycle_stage": "🔴 OVEREXTENDED (BOS #4+ / Stretch >3.5x ATR)",
    "reasoning": "• Arah & Struktur: ...\n• Stop Loss & Invalidasi: ...\n• Target Profit: ...\n• Alokasi Risiko: ..."
}

sanitized = service._sanitize_trade_setup(raw_mock_dots, context)
print("=== TEST 1: Sanitizer with Placeholder Dots ===")
print("Cycle Stage:", sanitized.get("cycle_stage"))
print("Reasoning:\n", sanitized.get("reasoning"))

assert "BOS #4+" not in sanitized.get("cycle_stage"), "Should replace static BOS #4+ with dynamic stage!"
assert "..." not in sanitized.get("reasoning"), "Should replace dots with full sentences!"
assert "4425.00" in sanitized.get("reasoning"), "Should include SL price in reasoning!"
assert "4516.95" in sanitized.get("reasoning"), "Should include TP price in reasoning!"

print("\n✅ All assertions passed!")
