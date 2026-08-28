import sys
from pathlib import Path
from loguru import logger

sys.path.insert(0, 'ValueCell_MT5/python')
from valuecell.agents.ml_prediction_agent import MLPredictionAgent

agent = MLPredictionAgent()

# 1. Test Friday Late Entry (Friday 19:30 UTC)
market_data_friday = {
    "current_bar": {
        "time": "2026-01-30T19:30:00Z",  # Friday 19:30 UTC
        "close": 2750.0,
        "open": 2748.0,
        "high": 2755.0,
        "low": 2745.0,
        "spread": 15
    },
    "session": "NY",
    "structure_events": [{"type": "BoS", "price": 2740.0, "time": "2026-01-30T19:15:00Z"}]
}
res_fri = agent.analyze(market_data_friday, structure_signal="BUY")
logger.info(f"Friday Late Entry Result: Signal={res_fri['signal']}, Reason={res_fri.get('reasoning')}")

# 2. Test Monday Open Blackout (Sunday 23:15 UTC / Monday open)
market_data_monday = {
    "current_bar": {
        "time": "2026-02-01T23:15:00Z",  # Sunday 23:15 UTC (Market Open)
        "close": 2755.0,
        "open": 2750.0,
        "high": 2760.0,
        "low": 2748.0,
        "spread": 45  # Wide spread
    },
    "session": "Asia",
    "structure_events": [{"type": "BoS", "price": 2745.0, "time": "2026-02-01T23:00:00Z"}]
}
res_mon = agent.analyze(market_data_monday, structure_signal="BUY")
logger.info(f"Monday Open Result: Signal={res_mon['signal']}, Reason={res_mon.get('reasoning')}")
