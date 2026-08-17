import sys
import os
import json

# Add backend directory to sys.path
sys.path.insert(0, r"b:\Project MT5\ValueCell_MT5\backend")

from app.services.llm_trade_setup import LLMTradeSetup

# Test Case: CHOCH Reversal Setup
payload_choch = {
    "structure": "CHOCH (BULLISH)",
    "entry_price": 4380.50,
    "atr": 12.00,
    "balance": 1000.0,
    "news": "no news",
    "timeframe": "M15",
    "candles_summary": "recent 10-bar local pullback: high=4380.50, low=4360.00 | 30-bar range: swingHigh=4420.00, swingLow=4360.00",
    "market_context": {
        "m15_ema200": 4390.00,
        "m15_trend": "NEUTRAL",
        "h1_ema200": 4370.10,
        "h1_trend": "BULLISH (Close $4380.50 > EMA $4370.10)",
        "h4_ema200": 4320.14,
        "h4_trend": "BULLISH (Close $4380.50 > EMA $4320.14)",
        "candle_body_ratio_pct": 70,
        "candle_quality": "STRONG IMPULSE (70% Body)",
        "session_name": "London Session (07:00 - 12:00 UTC)",
        "utc_hour": 9,
        "is_choch_reversal": True,
        "bos_cycle_count": 0,
        "ema_stretch_ratio": 0.79,
        "exhaustion_stage": "REVERSAL_SHIFT (CHOCH - Awal Pembalikan Arah / Siklus #0)",
        "nearest_supply_zone": {
            "bottom": 4440.00,
            "top": 4448.00,
            "label": "SUPPLY [4440.0 - 4448.0]"
        },
        "nearest_demand_zone": {
            "bottom": 4360.00,
            "top": 4368.00,
            "label": "DEMAND [4360.0 - 4368.0]"
        }
    },
    "ea_filters": {
        "h1_ema200": True,
        "h4_ema": True,
        "ema_slope": True,
        "body_ratio": True,
        "session": True,
        "ema_stretch_filter": True,
        "bos_cycle_filter": True
    }
}

service = LLMTradeSetup()
print("Starting CHOCH Reversal Analysis test...")
result = service.analyze(payload_choch)
with open(r"b:\Project MT5\scratch\choch_result.json", "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2, ensure_ascii=False)
print("Saved result to scratch/choch_result.json")
