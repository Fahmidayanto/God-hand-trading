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
groq_key = service.groq_api_key

models_to_test = [
    ("Groq Qwen 2.5 32B", OpenAILike(id="qwen-2.5-32b", api_key=groq_key, base_url=service.groq_base_url, timeout=10.0, max_retries=0)),
    ("Groq Llama 3.3 70B", OpenAILike(id="llama-3.3-70b-versatile", api_key=groq_key, base_url=service.groq_base_url, timeout=10.0, max_retries=0)),
    ("Groq Llama 3.1 8B", OpenAILike(id="llama-3.1-8b-instant", api_key=groq_key, base_url=service.groq_base_url, timeout=10.0, max_retries=0)),
    ("Groq Qwen 3.6 27b", OpenAILike(id="qwen/qwen3.6-27b", api_key=groq_key, base_url=service.groq_base_url, timeout=10.0, max_retries=0)),
]

# Check Gemini
google_key = os.getenv("GOOGLE_API_KEY")
if google_key:
    from agno.models.google import Gemini
    models_to_test.append(("Gemini 2.5 Flash", Gemini(id="gemini-2.5-flash", api_key=google_key)))

prompt = "Return raw JSON ONLY: {\"status\": \"ok\", \"ping\": \"pong\"}"

for name, model in models_to_test:
    t0 = time.time()
    try:
        data = service._call_model(name, model, prompt)
        elapsed = time.time() - t0
        print(f"✅ {name}: Success in {elapsed:.2f}s -> {data}")
    except Exception as e:
        elapsed = time.time() - t0
        print(f"❌ {name}: Failed after {elapsed:.2f}s -> {e}")
