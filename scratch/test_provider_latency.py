import sys
import os
import time

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

backend_path = r"B:\Project MT5\ValueCell_MT5\backend"
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from agno.models.openai import OpenAILike
from app.services.llm_trade_setup import LLMTradeSetup

service = LLMTradeSetup()

providers = [
    ("Tier 1: Groq Qwen", OpenAILike(id=service.groq_model_id or "qwen/qwen3.6-27b", api_key=service.groq_api_key, base_url=service.groq_base_url, timeout=10.0, max_retries=0)),
    ("Tier 2: 9inference DeepSeek", OpenAILike(id=service.nineinference_model_id, api_key=service.nineinference_api_key, base_url=service.nineinference_base_url, timeout=12.0, max_retries=0)),
]

google_key = os.getenv("GOOGLE_API_KEY")
if google_key:
    from agno.models.google import Gemini
    providers.append(("Tier 3: Gemini 2.5 Flash", Gemini(id="gemini-2.5-flash", api_key=google_key)))

nv_key = os.getenv("NVIDIA_MINIMAX_API_KEY", os.getenv("NVIDIA_API_KEY", ""))
if nv_key:
    providers.append(
        ("Tier 4: NVIDIA MiniMax M3", OpenAILike(id="minimaxai/minimax-m3", api_key=nv_key, base_url=service.nvidia_base_url, timeout=12.0, max_retries=0))
    )

prompt = "Return raw JSON ONLY: {\"status\": \"ok\"}"

for name, model in providers:
    t0 = time.time()
    try:
        data = service._call_model(name, model, prompt)
        elapsed = time.time() - t0
        print(f"✅ {name}: Success in {elapsed:.2f}s -> {data}")
    except Exception as e:
        elapsed = time.time() - t0
        print(f"❌ {name}: Failed after {elapsed:.2f}s -> {e}")
