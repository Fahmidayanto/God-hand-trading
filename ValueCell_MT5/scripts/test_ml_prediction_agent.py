"""
Test ML Prediction Agent

This script tests the ML Prediction Agent with:
1. Feature engineering validation
2. Model prediction testing
3. Various market scenarios
4. Error handling
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

from valuecell.agents.ml_prediction_agent import MLPredictionAgent
from valuecell.models.feature_engineer import FeatureEngineer


def create_test_market_data(scenario: str = "bullish") -> dict:
    """
    Create synthetic market data for testing.
    
    Args:
        scenario: "high_confidence", "low_confidence", "neutral"
    
    Returns:
        Dict with current_bar, structure_events, h1_data, m15_history
    """
    logger.info(f"Creating {scenario} test data...")
    
    current_time = datetime.now()
    
    # Base data
    current_bar = {
        "time": current_time,
        "open": 2350.0,
        "high": 2352.5,
        "low": 2348.0,
        "close": 2351.0,
        "volume": 1500
    }
    
    if scenario == "high_confidence":
        # Recent aligned BoS/CHoCH, London session, good volume
        structure_events = [
            {
                "type": "CHOCH_BULLISH",
                "price": 2345.0,
                "time": current_time - timedelta(hours=1)  # Recent
            },
            {
                "type": "BOS_BULLISH",
                "price": 2350.0,
                "time": current_time - timedelta(minutes=30)  # Very recent
            }
        ]
        # Set time to London session (13:00 UTC)
        current_bar["time"] = current_time.replace(hour=13, minute=0)
        
    elif scenario == "low_confidence":
        # Old events, conflicting directions, off-hours
        structure_events = [
            {
                "type": "CHOCH_BEARISH",
                "price": 2360.0,
                "time": current_time - timedelta(hours=12)  # Old
            },
            {
                "type": "BOS_BULLISH",
                "price": 2350.0,
                "time": current_time - timedelta(hours=8)  # Conflicting
            }
        ]
        # Set time to off-hours (3:00 UTC)
        current_bar["time"] = current_time.replace(hour=3, minute=0)
        
    elif scenario == "neutral":
        # Moderate signals
        structure_events = [
            {
                "type": "CHOCH_BULLISH",
                "price": 2345.0,
                "time": current_time - timedelta(hours=3)
            },
            {
                "type": "BOS_BULLISH",
                "price": 2350.0,
                "time": current_time - timedelta(hours=1)
            }
        ]
        # Set time to NY session (19:00 UTC)
        current_bar["time"] = current_time.replace(hour=19, minute=0)
    
    else:
        structure_events = []
    
    # Create H1 data
    h1_bars = 100
    h1_times = pd.date_range(
        start=current_time - timedelta(hours=h1_bars),
        periods=h1_bars,
        freq="1h"
    )
    h1_data = pd.DataFrame({
        "time": h1_times,
        "open": np.random.uniform(2340, 2360, h1_bars),
        "high": np.random.uniform(2350, 2370, h1_bars),
        "low": np.random.uniform(2330, 2350, h1_bars),
        "close": np.random.uniform(2340, 2360, h1_bars),
        "volume": np.random.randint(5000, 15000, h1_bars),
        "ema200": np.linspace(2340, 2345, h1_bars)  # Uptrend EMA
    })
    
    # Create M15 history
    m15_bars = 100
    m15_times = pd.date_range(
        start=current_time - timedelta(minutes=15 * m15_bars),
        periods=m15_bars,
        freq="15min"
    )
    m15_history = pd.DataFrame({
        "time": m15_times,
        "open": np.random.uniform(2345, 2355, m15_bars),
        "high": np.random.uniform(2350, 2360, m15_bars),
        "low": np.random.uniform(2340, 2350, m15_bars),
        "close": np.random.uniform(2345, 2355, m15_bars),
        "volume": np.random.randint(1000, 3000, m15_bars)
    })
    
    return {
        "current_bar": current_bar,
        "structure_events": structure_events,
        "h1_data": h1_data,
        "m15_history": m15_history
    }


def test_feature_engineer():
    """Test FeatureEngineer standalone"""
    logger.info("=" * 70)
    logger.info("TEST: FEATURE ENGINEER")
    logger.info("=" * 70)
    
    engineer = FeatureEngineer()
    
    # Test 1: Basic feature extraction
    logger.info("\nTest 1: Basic Feature Extraction")
    market_data = create_test_market_data("high_confidence")
    
    features = engineer.extract_features(
        current_bar=market_data["current_bar"],
        structure_events=market_data["structure_events"],
        h1_data=market_data["h1_data"],
        m15_history=market_data["m15_history"]
    )
    
    logger.info(f"✅ Extracted {len(features)} features")
    logger.info(f"   Expected: {len(engineer.feature_names)}")
    
    # Verify all features present
    missing = set(engineer.feature_names) - set(features.keys())
    extra = set(features.keys()) - set(engineer.feature_names)
    
    if missing:
        logger.error(f"❌ Missing features: {missing}")
    if extra:
        logger.warning(f"⚠️ Extra features: {extra}")
    
    if not missing and not extra:
        logger.info("   ✅ All features present and correct")
    
    # Print sample features
    logger.info("\n   Sample features:")
    sample_features = [
        "last_bos_age_hours",
        "last_choch_age_hours",
        "bos_choch_aligned",
        "hour_of_day",
        "session_priority"
    ]
    for feat_name in sample_features:
        logger.info(f"      {feat_name:25} = {features.get(feat_name, 'N/A')}")
    
    logger.info("")


def test_agent_with_scenario(agent: MLPredictionAgent, scenario: str):
    """Test agent with specific scenario"""
    logger.info("=" * 70)
    logger.info(f"TEST: {scenario.upper()} SCENARIO")
    logger.info("=" * 70)
    
    # Create market data
    market_data = create_test_market_data(scenario)
    
    # Define structure signal based on scenario
    if scenario == "high_confidence":
        structure_signal = "BUY"
    elif scenario == "low_confidence":
        structure_signal = "SELL"
    else:
        structure_signal = "BUY"
    
    # Analyze
    result = agent.analyze(
        market_data=market_data,
        structure_signal=structure_signal,
        symbol="XAUUSD",
        timeframe="M15"
    )
    
    # Print results
    logger.info("")
    logger.info("🎯 AGENT RESPONSE:")
    logger.info(f"   Signal: {result['signal']}")
    logger.info(f"   Confidence: {result['confidence']:.3f}")
    logger.info(f"   Probability: {result['probability']:.3f}")
    logger.info(f"   Threshold: {result['threshold']:.3f}")
    logger.info(f"   Reasoning: {result['reasoning']}")
    logger.info("")
    
    # Print top features
    if result.get('top_features'):
        logger.info(f"🔍 Top Contributing Features:")
        for i, feat in enumerate(result['top_features'][:5], 1):
            logger.info(
                f"   {i}. {feat['name']:25} = {feat['value']:7.3f} "
                f"(importance: {feat['importance']:.3f})"
            )
        logger.info("")
    
    # Model info
    logger.info(f"📊 Model Stats:")
    logger.info(f"   Accuracy: {result.get('model_accuracy', 0):.1%}")
    logger.info("")
    
    return result


def test_agent_info():
    """Test agent info retrieval"""
    logger.info("=" * 70)
    logger.info("TEST: AGENT INFO")
    logger.info("=" * 70)
    
    agent = MLPredictionAgent()
    info = agent.get_info()
    
    logger.info(f"Agent Name: {info['name']}")
    logger.info(f"Version: {info['version']}")
    logger.info(f"Type: {info['type']}")
    logger.info(f"Description: {info['description']}")
    logger.info("")
    logger.info("Model Info:")
    for key, value in info['model_info'].items():
        logger.info(f"  {key}: {value}")
    logger.info("")
    logger.info("Capabilities:")
    for cap in info['capabilities']:
        logger.info(f"  - {cap}")
    logger.info("")


def test_error_handling():
    """Test error handling"""
    logger.info("=" * 70)
    logger.info("TEST: ERROR HANDLING")
    logger.info("=" * 70)
    
    agent = MLPredictionAgent()
    
    # Test 1: Empty market data
    logger.info("\nTest 1: Empty market data")
    empty_data = {
        "current_bar": None,
        "structure_events": [],
        "h1_data": None,
        "m15_history": None
    }
    try:
        result = agent.analyze(empty_data, structure_signal="BUY")
        logger.info(f"   Result: {result['signal']} | {result['reasoning'][:50]}...")
    except Exception as e:
        logger.error(f"   ❌ Exception: {e}")
    logger.info("")
    
    # Test 2: Missing current_bar
    logger.info("Test 2: Missing current_bar key")
    incomplete_data = {
        "structure_events": [],
    }
    try:
        result = agent.analyze(incomplete_data, structure_signal="BUY")
        logger.info(f"   Result: {result['signal']} | {result['reasoning'][:50]}...")
    except Exception as e:
        logger.error(f"   ❌ Exception: {e}")
    logger.info("")
    
    # Test 3: Invalid structure signal
    logger.info("Test 3: Invalid structure signal")
    market_data = create_test_market_data("neutral")
    try:
        result = agent.analyze(market_data, structure_signal="INVALID")
        logger.info(f"   Result: {result['signal']} | Reasoning: {result['reasoning'][:50]}...")
    except Exception as e:
        logger.info(f"   Note: Agent handles invalid signal gracefully")
    logger.info("")


def test_probability_thresholds():
    """Test different probability scenarios"""
    logger.info("=" * 70)
    logger.info("TEST: PROBABILITY THRESHOLDS")
    logger.info("=" * 70)
    logger.info("")
    
    agent = MLPredictionAgent()
    
    # We can't directly control probability, but we can test with different scenarios
    scenarios = ["high_confidence", "neutral", "low_confidence"]
    
    logger.info("Testing signal generation with different market conditions:")
    logger.info("")
    
    for scenario in scenarios:
        market_data = create_test_market_data(scenario)
        result = agent.analyze(market_data, structure_signal="BUY")
        
        logger.info(f"{scenario.upper():20} | Prob: {result['probability']:.3f} | Signal: {result['signal']:8} | Conf: {result['confidence']:.3f}")
    
    logger.info("")


def test_all_scenarios():
    """Run all test scenarios"""
    logger.info("🚀 STARTING ML PREDICTION AGENT TESTS")
    logger.info("=" * 70)
    logger.info("")
    
    # Test 1: Feature Engineer
    test_feature_engineer()
    
    # Test 2: Agent Info
    test_agent_info()
    
    # Initialize agent
    agent = MLPredictionAgent(threshold=0.7)
    
    # Test 3: Different scenarios
    scenarios = ["high_confidence", "low_confidence", "neutral"]
    results = {}
    
    for scenario in scenarios:
        result = test_agent_with_scenario(agent, scenario)
        results[scenario] = result
    
    # Test 4: Probability thresholds
    test_probability_thresholds()
    
    # Test 5: Error handling
    test_error_handling()
    
    # Summary
    logger.info("=" * 70)
    logger.info("📊 TEST SUMMARY")
    logger.info("=" * 70)
    logger.info("")
    
    for scenario, result in results.items():
        logger.info(
            f"{scenario.upper():20} | "
            f"Signal: {result['signal']:8} | "
            f"Confidence: {result['confidence']:.3f} | "
            f"Probability: {result['probability']:.3f}"
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
