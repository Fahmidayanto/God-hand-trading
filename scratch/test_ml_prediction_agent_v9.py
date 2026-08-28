import sys
from pathlib import Path
import pandas as pd
from loguru import logger

sys.path.insert(0, 'ValueCell_MT5/python')
from valuecell.agents.ml_prediction_agent import MLPredictionAgent

logger.info("Testing MLPredictionAgent with Model v9...")
agent = MLPredictionAgent()
logger.info(f"Loaded Agent Model Type: {agent.model_type}")

# Create mock market data
market_data_safe = {
    "current_bar": {
        "time": "2026-01-28T12:00:00Z",  # Safe time (hours before FOMC)
        "close": 2750.0,
        "open": 2748.0,
        "high": 2755.0,
        "low": 2745.0,
        "spread": 15
    },
    "session": "London",
    "structure_events": [
        {"type": "BoS", "price": 2740.0, "time": "2026-01-28T11:45:00Z"}
    ]
}

res_safe = agent.analyze(market_data_safe, structure_signal="BUY")
logger.info(f"Safe time result: Signal={res_safe['signal']}, R:R={res_safe.get('expected_rr', 0.0):.2f}, Reason={res_safe.get('reasoning')}")

# Test during blackout (15 mins before FOMC)
market_data_blackout = {
    "current_bar": {
        "time": "2026-01-28T18:45:00Z",  # 15 mins before FOMC
        "close": 2750.0,
        "open": 2748.0,
        "high": 2755.0,
        "low": 2745.0,
        "spread": 15
    },
    "session": "NY",
    "structure_events": [
        {"type": "BoS", "price": 2740.0, "time": "2026-01-28T18:30:00Z"}
    ]
}

res_blackout = agent.analyze(market_data_blackout, structure_signal="BUY")
logger.info(f"Blackout time result: Signal={res_blackout['signal']}, Reason={res_blackout.get('reasoning')}")
