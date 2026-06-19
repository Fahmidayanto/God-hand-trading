"""
Test Market Structure Agent

This script tests the Market Structure Agent with:
1. Sample synthetic data
2. Real historical data (if available)
3. Various market scenarios (bullish, bearish, neutral)
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from loguru import logger

from python.valuecell.agents.market_structure_agent import MarketStructureAgent


def create_test_data(scenario: str = "bullish", bars: int = 150) -> pd.DataFrame:
    """
    Create synthetic test data for different scenarios.
    
    Args:
        scenario: "bullish", "bearish", "neutral", "volatile"
        bars: Number of bars to generate
    
    Returns:
        DataFrame with OHLCV + ema200
    """
    logger.info(f"Creating {scenario} test data ({bars} bars)...")
    
    dates = pd.date_range(start="2024-01-01", periods=bars, freq="15min")
    base_price = 2300.0
    
    if scenario == "bullish":
        # Strong uptrend
        trend = np.linspace(0, 60, bars)  # +60 pips
        noise = np.random.normal(0, 3, bars)
        
    elif scenario == "bearish":
        # Strong downtrend
        trend = np.linspace(0, -60, bars)  # -60 pips
        noise = np.random.normal(0, 3, bars)
        
    elif scenario == "neutral":
        # Ranging market
        trend = np.sin(np.linspace(0, 4 * np.pi, bars)) * 20  # Oscillating
        noise = np.random.normal(0, 5, bars)
        
    elif scenario == "volatile":
        # High volatility
        trend = np.cumsum(np.random.normal(0, 2, bars))
        noise = np.random.normal(0, 8, bars)
    
    else:
        trend = np.zeros(bars)
        noise = np.random.normal(0, 3, bars)
    
    close_prices = base_price + trend + noise
    
    # Generate OHLC
    opens = close_prices - np.random.uniform(1, 3, bars)
    highs = np.maximum(close_prices, opens) + np.random.uniform(1, 4, bars)
    lows = np.minimum(close_prices, opens) - np.random.uniform(1, 4, bars)
    
    df = pd.DataFrame({
        "time": dates,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": close_prices,
        "volume": np.random.randint(1000, 5000, bars),
        "ema200": base_price + trend * 0.7  # EMA follows slower
    })
    
    logger.info(
        f"✅ Data created | "
        f"Price range: {df['low'].min():.2f} - {df['high'].max():.2f} | "
        f"Total change: {df['close'].iloc[-1] - df['close'].iloc[0]:.2f} pips"
    )
    
    return df


def test_agent_with_scenario(agent: MarketStructureAgent, scenario: str):
    """Test agent with specific market scenario"""
    logger.info("=" * 70)
    logger.info(f"TEST: {scenario.upper()} MARKET SCENARIO")
    logger.info("=" * 70)
    
    # Create data
    df = create_test_data(scenario=scenario, bars=150)
    
    # Analyze
    result = agent.analyze(
        df=df,
        symbol="XAUUSD",
        timeframe="M15",
        session="London"
    )
    
    # Print results
    logger.info("")
    logger.info("🎯 AGENT RESPONSE:")
    logger.info(f"   Signal: {result['signal']}")
    logger.info(f"   Confidence: {result['confidence']:.3f}")
    logger.info(f"   Reasoning: {result['reasoning']}")
    logger.info("")
    
    if result['structure_events']:
        logger.info(f"📊 Structure Events ({len(result['structure_events'])}):")
        for i, event in enumerate(result['structure_events'][-3:], 1):
            logger.info(
                f"   {i}. {event['type']} @ "
                f"{event['price']:.2f} ({event['status']})"
            )
        logger.info("")
    
    if result['pattern_analysis']:
        pa = result['pattern_analysis']
        logger.info(f"🔍 Pattern Analysis:")
        logger.info(f"   Similar patterns: {pa['total_count']}")
        logger.info(f"   Win rate: {pa['win_rate']:.1%}")
        logger.info(f"   Avg profit: {pa['avg_profit']:.1f} pips")
        logger.info(f"   Recommendation: {pa['recommendation']}")
        logger.info("")
    
    metadata = result.get('metadata', {})
    if metadata:
        logger.info(f"📈 Market State:")
        logger.info(f"   Current price: {metadata.get('current_price', 0):.2f}")
        logger.info(f"   EMA200: {metadata.get('ema200', 0):.2f}")
        logger.info(f"   Price vs EMA: {metadata.get('price_vs_ema', 'N/A')}")
        logger.info(f"   Distance: {metadata.get('ema_distance', 0):.2f} pips")
        logger.info("")
    
    return result


def test_agent_info():
    """Test agent info retrieval"""
    logger.info("=" * 70)
    logger.info("TEST: AGENT INFO")
    logger.info("=" * 70)
    
    agent = MarketStructureAgent()
    info = agent.get_info()
    
    logger.info(f"Agent Name: {info['name']}")
    logger.info(f"Version: {info['version']}")
    logger.info(f"Type: {info['type']}")
    logger.info(f"Description: {info['description']}")
    logger.info("")
    logger.info("Capabilities:")
    for cap in info['capabilities']:
        logger.info(f"  - {cap}")
    logger.info("")
    logger.info(f"Config: {info['config']}")
    logger.info("")


def test_error_handling():
    """Test error handling"""
    logger.info("=" * 70)
    logger.info("TEST: ERROR HANDLING")
    logger.info("=" * 70)
    
    agent = MarketStructureAgent()
    
    # Test 1: Empty DataFrame
    logger.info("Test 1: Empty DataFrame")
    df_empty = pd.DataFrame()
    result = agent.analyze(df_empty)
    logger.info(f"   Result: {result['signal']} | Reasoning: {result['reasoning']}")
    logger.info("")
    
    # Test 2: Insufficient data
    logger.info("Test 2: Insufficient data (5 bars, need at least 11)")
    df_small = create_test_data(bars=5)
    result = agent.analyze(df_small)
    logger.info(f"   Result: {result['signal']} | Reasoning: {result['reasoning']}")
    logger.info("")
    
    # Test 3: Missing columns
    logger.info("Test 3: Missing required columns")
    df_incomplete = pd.DataFrame({
        "time": pd.date_range(start="2024-01-01", periods=150, freq="15min"),
        "close": np.random.uniform(2300, 2350, 150)
        # Missing: open, high, low, volume
    })
    result = agent.analyze(df_incomplete)
    logger.info(f"   Result: {result['signal']} | Reasoning: {result['reasoning']}")
    logger.info("")


def test_all_scenarios():
    """Run all test scenarios"""
    logger.info("🚀 STARTING MARKET STRUCTURE AGENT TESTS")
    logger.info("=" * 70)
    logger.info("")
    
    # Test agent info
    test_agent_info()
    
    # Initialize agent
    agent = MarketStructureAgent(
        swing_length=5,
        timeframe="M15",
        use_patterns=True
    )
    
    # Test different scenarios
    scenarios = ["bullish", "bearish", "neutral", "volatile"]
    results = {}
    
    for scenario in scenarios:
        result = test_agent_with_scenario(agent, scenario)
        results[scenario] = result
    
    # Test error handling
    test_error_handling()
    
    # Summary
    logger.info("=" * 70)
    logger.info("📊 TEST SUMMARY")
    logger.info("=" * 70)
    logger.info("")
    
    for scenario, result in results.items():
        logger.info(
            f"{scenario.upper():12} | "
            f"Signal: {result['signal']:4} | "
            f"Confidence: {result['confidence']:.3f} | "
            f"Events: {len(result['structure_events'])}"
        )
    
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
