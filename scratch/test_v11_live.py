import sys
from pathlib import Path
from loguru import logger

sys.path.insert(0, 'ValueCell_MT5/python')
from valuecell.agents.ml_prediction_agent import MLPredictionAgent

agent = MLPredictionAgent()
logger.info(f"Agent Active: {agent.name}, Model Type: {agent.model_type}")

# Test active session London entry (Wednesday 10:00 UTC)
market_data = {
    "current_bar": {
        "time": "2026-03-11T10:00:00Z",  # Wednesday London session
        "close": 2750.0,
        "open": 2745.0,
        "high": 2755.0,
        "low": 2742.0,
        "spread": 15
    },
    "session": "London",
    "structure_events": [{"type": "BoS", "price": 2740.0, "time": "2026-03-11T09:45:00Z"}],
    "planned_rr": 2.0,
    "init_risk_points": 3000.0,
    "init_reward_points": 6000.0
}

res = agent.analyze(market_data, structure_signal="BUY")
logger.info(f"✅ Live v11 Inference Result: Signal={res['signal']}, Predicted_MFE={res.get('predicted_mfe', 0):.2f}, Predicted_MAE={res.get('predicted_mae', 0):.2f}, Expected_RR={res.get('expected_rr', 0):.2f}, Confidence={res.get('confidence', 0):.2f}")
