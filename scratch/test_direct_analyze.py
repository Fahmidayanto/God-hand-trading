import sys
import os
import json

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
        "m15_trend": "BULLISH (Price above M15 EMA200 $4380.20)",
        "h1_ema200": 4385.10,
        "h1_trend": "BULLISH (Close $4455.65 > EMA $4385.10)",
        "h4_ema200": 4267.14,
        "h4_trend": "BULLISH (Close $4455.65 > EMA $4267.14)",
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

print("Running analyze()...")
result = service.analyze(context)
print("Result JSON:")
print(json.dumps(result, indent=2, ensure_ascii=False))
