"""
Verification script for SentimentAgent and LLMTradeSetup with 9inference DeepSeek V4 Flash.
"""
import os
import sys

backend_dir = os.path.join(os.path.dirname(__file__), "..", "ValueCell_MT5", "backend")
python_dir = os.path.join(os.path.dirname(__file__), "..", "ValueCell_MT5", "python")
sys.path.insert(0, backend_dir)
sys.path.insert(0, python_dir)

from datetime import datetime, timezone
from valuecell.agents.sentiment_agent import SentimentAgent
from app.services.llm_trade_setup import LLMTradeSetup

print("=== 1. Testing SentimentAgent with 9inference DeepSeek ===")
try:
    agent = SentimentAgent(use_llm=True)
    print(f"SentimentAgent base_url: {agent.nineinference_base_url}")
    print(f"SentimentAgent model: {agent.nineinference_model_id}")
    
    # Test sentiment analysis with sample headline dict
    kept_headlines = [
        {"text": "US Inflation cools down, Fed signals rate cuts ahead boosting Gold rally", "timestamp": datetime.now(timezone.utc)}
    ]
    res = agent._analyze_news_sentiment_llm(kept_headlines, current_time=datetime.now(timezone.utc))
    print(f"[SUCCESS] SentimentAgent result:\n{res}")
except Exception as e:
    print(f"[FAIL] SentimentAgent test error: {e}")

print("\n=== 2. Testing LLMTradeSetup with 9inference DeepSeek ===")
try:
    setup = LLMTradeSetup()
    print(f"LLMTradeSetup base_url: {setup.nineinference_base_url}")
    context = {
        "structure": "BULLISH_CONTINUATION",
        "atr": 4.5,
        "balance": 10000.0,
        "risk_pct": 1.5,
        "entry_price": 2850.50,
        "news": "Bullish US Fed rate cut signals"
    }
    trade_res = setup.analyze(context)
    print(f"[SUCCESS] LLMTradeSetup result:\n{trade_res}")
except Exception as e:
    print(f"[FAIL] LLMTradeSetup test error: {e}")
