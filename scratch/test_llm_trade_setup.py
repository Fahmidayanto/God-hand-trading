"""
Test LLMTradeSetup fallback initialization.
"""
import os
import sys

backend_dir = os.path.join(os.path.dirname(__file__), "..", "ValueCell_MT5", "backend")
sys.path.insert(0, backend_dir)

from app.services.llm_trade_setup import LLMTradeSetup

setup = LLMTradeSetup()
print(f"LLMTradeSetup initialized successfully!")
print(f"Groq API Key: {setup.groq_api_key[:8]}...{setup.groq_api_key[-4:]}")
print(f"Groq Model ID: {setup.groq_model_id}")
print(f"NVIDIA Models remaining: {len(setup.nvidia_models)}")
for name, _, model_id in setup.nvidia_models:
    print(f"  - {name}: {model_id}")
