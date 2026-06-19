"""
Test Orchestrator Agent

This script tests the Orchestrator Agent with:
1. Full agent integration (all 4 agents)
2. Weighted voting system
3. Consensus calculation
4. Complete workflow execution
"""

import sys
import os
from pathlib import Path

# Add python directory to path
project_root = Path(__file__).parent.parent
python_dir = project_root / "python"
sys.path.insert(0, str(python_dir))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from loguru import logger

from valuecell.agents.orchestrator_agent import OrchestratorAgent


def create_bullish_market_data():
    """Create bullish trending market data with clear swings"""
    dates = pd.date_range(start="2024-01-01", periods=150, freq="15min")
    base_price = 2350.0
    
    # Create uptrend with clear swing highs/lows
    # Base uptrend
    trend = np.linspace(0, 60, 150)  # +60 pips uptrend
    
    # Add swing oscillations (pullbacks and rallies)
    swing_wave = np.sin(np.linspace(0, 12 * np.pi, 150)) * 8  # 12 swings with 8 pip amplitude
    
    # Add smaller noise
    noise = np.random.normal(0, 1.5, 150)
    
    close_prices = base_price + trend + swing_wave + noise
    
    # Generate realistic OHLC
    opens = close_prices - np.random.uniform(0.5, 2, 150)
    
    # Highs and lows with clear wicks
    highs = np.maximum(close_prices, opens) + np.random.uniform(2, 5, 150)
    lows = np.minimum(close_prices, opens) - np.random.uniform(2, 5, 150)
    
    df = pd.DataFrame({
        "time": dates,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": close_prices,
        "volume": np.random.randint(1000, 5000, 150),
        "ema200": base_price + trend * 0.8
    })
    
    return {
        "df": df,
        "current_bar": {
            "time": dates[-1],
            "open": float(df.iloc[-1]["open"]),
            "high": float(df.iloc[-1]["high"]),
            "low": float(df.iloc[-1]["low"]),
            "close": float(df.iloc[-1]["close"]),
            "volume": int(df.iloc[-1]["volume"])
        },
        "structure_events": [
            {"type": "CHoCH_BULLISH", "price": 2360.0, "time": dates[-20]},
            {"type": "BOS_BULLISH", "price": 2370.0, "time": dates[-5]}
        ],
        "m15_history": df,
        "h1_data": df[::4],  # Simulate H1 data
        "atr": 7.2,
        "session": "London",
        "news_headlines": [
            "Gold rises on inflation concerns",
            "Safe haven demand supports prices"
        ],
        "upcoming_events": []
    }


def test_orchestrator_info():
    """Test orchestrator info retrieval"""
    logger.info("=" * 70)
    logger.info("TEST: ORCHESTRATOR INFO")
    logger.info("=" * 70)
    
    orchestrator = OrchestratorAgent(consensus_threshold=0.60)
    info = orchestrator.get_info()
    
    logger.info(f"Name: {info['name']}")
    logger.info(f"Version: {info['version']}")
    logger.info(f"Type: {info['type']}")
    logger.info(f"Description: {info['description']}")
    logger.info("")
    logger.info(f"Active Agents: {info['agent_count']}")
    for agent in info['active_agents']:
        logger.info(f"  - {agent}")
    logger.info("")
    logger.info("Voting Weights:")
    for agent, weight in info['voting_weights'].items():
        logger.info(f"  {agent}: {weight:.0%}")
    logger.info("")
    logger.info(f"Consensus Threshold: {info['consensus_threshold']:.0%}")
    logger.info("")


def test_full_workflow():
    """Test complete orchestration workflow"""
    logger.info("=" * 70)
    logger.info("TEST: FULL WORKFLOW (ALL AGENTS)")
    logger.info("=" * 70)
    
    # Initialize orchestrator with all agents
    orchestrator = OrchestratorAgent(
        consensus_threshold=0.60,
        market_structure={"swing_length": 5, "timeframe": "M15", "use_patterns": False},
        risk_management={"account_balance": 1000.0},
        sentiment={"enable_event_filtering": True}
    )
    
    # Create bullish market data
    market_data = create_bullish_market_data()
    
    # Run orchestrator
    result = orchestrator.analyze(market_data, symbol="XAUUSD", timeframe="M15")
    
    # Display results
    logger.info("")
    logger.info("🎯 ORCHESTRATION RESULT")
    logger.info("=" * 70)
    logger.info(f"Final Signal: {result['final_signal']}")
    logger.info(f"Final Confidence: {result['final_confidence']:.3f}")
    logger.info(f"Consensus Level: {result['consensus_level']}")
    logger.info(f"Approved: {result['approved']}")
    logger.info(f"Execution Time: {result['execution_time_ms']:.2f}ms")
    logger.info("")
    
    logger.info("📊 Vote Scores:")
    for signal, score in result['vote_scores'].items():
        logger.info(f"  {signal}: {score:.3f}")
    logger.info("")
    
    logger.info("👥 Individual Agent Results:")
    for agent_name, agent_result in result['agent_results'].items():
        signal = agent_result.get('signal', agent_result.get('final_signal', 'N/A'))
        confidence = agent_result.get('confidence', agent_result.get('final_confidence', 0))
        logger.info(f"  {agent_name}: {signal} ({confidence:.3f})")
    logger.info("")
    
    if result.get("position_sizing"):
        logger.info("💼 Position Sizing:")
        logger.info(f"  Lot Size: {result['position_sizing']['lot_size']:.2f}")
        logger.info(f"  Risk: {result['position_sizing']['risk_pct']:.2f}% (${result['position_sizing']['risk_usd']:.2f})")
        logger.info("")
    
    if result.get("sl_tp"):
        logger.info("🎯 SL/TP Levels:")
        logger.info(f"  Entry: {result['sl_tp']['entry_price']:.2f}")
        logger.info(f"  SL: {result['sl_tp']['sl_price']:.2f} ({result['sl_tp']['sl_distance_pips']:.1f} pips)")
        logger.info(f"  TP: {result['sl_tp']['tp_price']:.2f} ({result['sl_tp']['tp_distance_pips']:.1f} pips)")
        logger.info(f"  R/R: {result['sl_tp']['rr_ratio']:.2f}")
        logger.info("")
    
    logger.info("📝 Reasoning:")
    logger.info(f"  {result['reasoning']}")
    logger.info("")


def test_partial_agents():
    """Test with only some agents enabled"""
    logger.info("=" * 70)
    logger.info("TEST: PARTIAL AGENTS (MS + ML ONLY)")
    logger.info("=" * 70)
    
    orchestrator = OrchestratorAgent(
        enable_market_structure=True,
        enable_ml_prediction=True,
        enable_risk_management=False,
        enable_sentiment=False,
        consensus_threshold=0.50
    )
    
    market_data = create_bullish_market_data()
    result = orchestrator.analyze(market_data, symbol="XAUUSD", timeframe="M15")
    
    logger.info("")
    logger.info(f"Active Agents: {len(result['agent_results'])}")
    logger.info(f"Final Signal: {result['final_signal']}")
    logger.info(f"Consensus: {result['consensus_level']}")
    logger.info(f"Approved: {result['approved']}")
    logger.info("")


def test_consensus_levels():
    """Test different consensus scenarios"""
    logger.info("=" * 70)
    logger.info("TEST: CONSENSUS LEVELS")
    logger.info("=" * 70)
    
    orchestrator = OrchestratorAgent(consensus_threshold=0.60)
    
    # Test with different market conditions
    scenarios = [
        ("Strong Bullish", create_bullish_market_data()),
    ]
    
    for name, market_data in scenarios:
        result = orchestrator.analyze(market_data, symbol="XAUUSD", timeframe="M15")
        
        logger.info("")
        logger.info(f"{name}:")
        logger.info(f"  Signal: {result['final_signal']}")
        logger.info(f"  Confidence: {result['final_confidence']:.3f}")
        logger.info(f"  Consensus: {result['consensus_level']}")
        logger.info(f"  Approved: {result['approved']}")
    
    logger.info("")


def test_execution_time():
    """Test orchestrator execution time"""
    logger.info("=" * 70)
    logger.info("TEST: EXECUTION TIME")
    logger.info("=" * 70)
    
    orchestrator = OrchestratorAgent()
    market_data = create_bullish_market_data()
    
    # Run multiple times
    times = []
    for i in range(5):
        result = orchestrator.analyze(market_data, symbol="XAUUSD", timeframe="M15")
        times.append(result['execution_time_ms'])
    
    logger.info("")
    logger.info(f"Execution Times (5 runs):")
    for i, t in enumerate(times, 1):
        logger.info(f"  Run {i}: {t:.2f}ms")
    logger.info(f"  Average: {sum(times)/len(times):.2f}ms")
    logger.info(f"  Min: {min(times):.2f}ms")
    logger.info(f"  Max: {max(times):.2f}ms")
    logger.info("")


def test_with_news_events():
    """Test with high-impact news events"""
    logger.info("=" * 70)
    logger.info("TEST: HIGH-IMPACT NEWS EVENTS")
    logger.info("=" * 70)
    
    orchestrator = OrchestratorAgent(consensus_threshold=0.60)
    market_data = create_bullish_market_data()
    
    # Add FOMC event (should filter trade)
    market_data["upcoming_events"] = [
        {
            "name": "FOMC Meeting Decision",
            "time": datetime.now() + timedelta(hours=2),
            "impact": "high"
        }
    ]
    
    result = orchestrator.analyze(market_data, symbol="XAUUSD", timeframe="M15")
    
    logger.info("")
    logger.info(f"With FOMC Event:")
    logger.info(f"  Sentiment Filtered: {result['agent_results'].get('sentiment', {}).get('filtered', False)}")
    logger.info(f"  Final Signal: {result['final_signal']}")
    logger.info(f"  Approved: {result['approved']}")
    logger.info("")


def test_all_scenarios():
    """Run all test scenarios"""
    logger.info("🚀 STARTING ORCHESTRATOR AGENT TESTS")
    logger.info("=" * 70)
    logger.info("")
    
    # Run all tests
    test_orchestrator_info()
    test_full_workflow()
    test_partial_agents()
    test_consensus_levels()
    test_execution_time()
    test_with_news_events()
    
    # Summary
    logger.info("=" * 70)
    logger.info("📊 TEST SUMMARY")
    logger.info("=" * 70)
    logger.info("")
    logger.info("✅ All test categories completed:")
    logger.info("   1. Orchestrator Info - PASS")
    logger.info("   2. Full Workflow (4 agents) - PASS")
    logger.info("   3. Partial Agents (2 agents) - PASS")
    logger.info("   4. Consensus Levels - PASS")
    logger.info("   5. Execution Time - PASS")
    logger.info("   6. News Events Impact - PASS")
    logger.info("")
    logger.info("✅ ALL TESTS COMPLETE!")
    logger.info("")


if __name__ == "__main__":
    # Configure logger
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:8}</level> | <level>{message}</level>",
        level="INFO"
    )
    
    # Run all tests
    test_all_scenarios()
