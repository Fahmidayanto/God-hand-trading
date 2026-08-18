import requests
import json

payload = {
    "symbol": "XAUUSD",
    "anchor_timestamp": "2026-03-02T10:00:00Z",
    "engine": "llm",
    "ohlc": {
        "M15": [
            {"time": "2026-03-02T09:30:00Z", "open": 2040.0, "high": 2045.0, "low": 2038.0, "close": 2042.0},
            {"time": "2026-03-02T09:45:00Z", "open": 2042.0, "high": 2048.0, "low": 2041.0, "close": 2047.0},
            {"time": "2026-03-02T10:00:00Z", "open": 2047.0, "high": 2050.0, "low": 2045.0, "close": 2049.0},
        ],
        "H1": [
            {"time": "2026-03-02T09:00:00Z", "open": 2035.0, "high": 2050.0, "low": 2034.0, "close": 2049.0},
        ],
        "H4": [
            {"time": "2026-03-02T08:00:00Z", "open": 2030.0, "high": 2055.0, "low": 2028.0, "close": 2049.0},
        ]
    },
    "balance": 1000.0,
    "risk_pct": 1.0,
    "min_rr": 2.0
}

try:
    res = requests.post("http://localhost:8000/api/v1/replay/decision", json=payload, timeout=30)
    print("Status:", res.status_code)
    print("Response:", json.dumps(res.json(), indent=2))
except Exception as e:
    print("Error:", e)
