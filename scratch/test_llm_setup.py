import requests
import json
import sys

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

url = "http://localhost:8000/api/v1/trading/llm-setup"

payload = {
    "structure": "BOS (BULLISH)",
    "entry_price": 4455.65,
    "atr": 12.95,
    "balance": 1000.0,
    "news": "no news",
    "timeframe": "M15",
    "candles_summary": "recent 10-bar local pullback: high=4450.00, low=4427.96 | 30-bar range: swingHigh=4455.65, swingLow=4427.96, lastClose=4455.65",
    "market_context": {
        "m15_ema200": 4380.20,
        "m15_trend": "BULLISH (Price above M15 EMA200 $4380.20)",
        "h1_ema200": 4385.10,
        "h1_trend": "BULLISH (Close $4455.65 > EMA $4385.10)",
        "h4_ema200": 4267.14,
        "h4_trend": "BULLISH (Close $4455.65 > EMA $4267.14)",
        "candle_body_ratio_pct": 78,
        "candle_quality": "STRONG IMPULSE (78% Body)",
        "session_name": "London Session (07:00 - 12:00 UTC)",
        "utc_hour": 8,
        "nearest_supply_zone": {
            "bottom": 4482.00,
            "top": 4488.50,
            "label": "MAJOR SUPPLY [4482.0 - 4488.5]"
        },
        "nearest_demand_zone": {
            "bottom": 4421.20,
            "top": 4428.50,
            "label": "DEMAND [4421.2 - 4428.5]"
        },
        "nearest_bsl_target": {
            "price": 4480.50,
            "label": "🎯 BSL [4480.50]"
        },
        "bos_cycle_count": 1,
        "ema_stretch_ratio": 5.83,
        "exhaustion_stage": "OVEREXTENDED (BOS #1, Regangan EMA 5.83x ATR - Risiko Kelelahan Tinggi)"
    },
    "ea_filters": {
        "h1_ema200": True,
        "h4_ema": True,
        "ema_slope": True,
        "body_ratio": True,
        "session": True
    }
}

try:
    resp = requests.post(url, json=payload, timeout=60)
    print("Status Code:", resp.status_code)
    data = resp.json()
    print("Response JSON:")
    print(json.dumps(data, indent=2, ensure_ascii=False))
except Exception as e:
    print("Error calling endpoint:", e)
