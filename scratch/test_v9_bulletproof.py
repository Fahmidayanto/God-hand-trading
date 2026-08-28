import sys
from pathlib import Path
from loguru import logger

sys.path.insert(0, 'ValueCell_MT5/python')
from valuecell.agents.ml_prediction_agent import MLPredictionAgent

agent = MLPredictionAgent()
logger.info(f"Active Agent: {agent.name}, Production Model: {agent.model_type}")

# Test 1: Normal Live Bar with ISO String time (Wednesday London 10:00 UTC, normal spread 15 pts)
market_data_normal = {
    "current_bar": {
        "time": "2026-03-11T10:00:00Z",  # ISO string format
        "close": 2750.0,
        "open": 2745.0,
        "high": 2755.0,
        "low": 2742.0,
        "spread": 15
    },
    "spread": 15,
    "session": "London",
    "structure_events": [{"type": "BoS", "price": 2740.0, "time": "2026-03-11T09:45:00Z"}],
    "planned_rr": 2.0,
    "init_risk_points": 3000.0,
    "init_reward_points": 6000.0
}

res_normal = agent.analyze(market_data_normal, structure_signal="BUY")
logger.info(f"✅ Test 1 (Normal Bar): Signal={res_normal['signal']}, Net_RR={res_normal.get('expected_rr', 0):.2f}, Pred_MFE={res_normal.get('predicted_mfe', 0):.1f}, Pred_MAE={res_normal.get('predicted_mae', 0):.1f}")
assert res_normal['signal'] == "BUY", "Normal setup should pass"

# Test 2: High Spread Bar (Spread = 45 points / $0.45 USD during low liquidity)
market_data_high_spread = {
    "current_bar": {
        "time": "2026-03-11T23:15:00Z",  # Asian rollover
        "close": 4500.0,
        "open": 4498.0,
        "high": 4502.0,
        "low": 4497.0,
        "spread": 45
    },
    "spread": 45,
    "session": "Asia",
    "structure_events": [{"type": "BoS_BULLISH", "price": 4480.0, "time": "2026-03-11T23:00:00Z"}]
}

res_high_spread = agent.analyze(market_data_high_spread, structure_signal="BUY")
logger.info(f"✅ Test 2 (High Spread 45 pts): Signal={res_high_spread['signal']}, Reasoning={res_high_spread.get('reasoning')}")
assert res_high_spread['signal'] == "HOLD", "High spread must be VETOED"

# Test 3: Friday Late Entry (Friday 19:30 UTC)
market_data_friday = {
    "current_bar": {
        "time": "2026-03-13T19:30:00Z",  # Friday evening
        "close": 4500.0,
        "open": 4495.0,
        "high": 4505.0,
        "low": 4490.0,
        "spread": 15
    },
    "spread": 15,
    "session": "NewYork",
    "structure_events": [{"type": "BoS_BULLISH", "price": 4480.0, "time": "2026-03-13T19:15:00Z"}]
}

res_friday = agent.analyze(market_data_friday, structure_signal="BUY")
logger.info(f"✅ Test 3 (Friday Late Entry): Signal={res_friday['signal']}, Reasoning={res_friday.get('reasoning')}")
assert res_friday['signal'] == "HOLD", "Friday late entry must be VETOED"

logger.info("🎉 ALL TESTS PASSED: Model v9 Bulletproof successfully verified!")
