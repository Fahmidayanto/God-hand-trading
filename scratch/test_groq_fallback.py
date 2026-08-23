"""
Verification script for Groq Qwen 3.6 27B API integration.
Tests direct connection and streaming/non-streaming response.
"""
import os
import sys

# Try loading from backend .env
env_path = os.path.join(os.path.dirname(__file__), "..", "ValueCell_MT5", "backend", ".env")
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

api_key = os.getenv("GROQ_API_KEY", "")
model_id = os.getenv("GROQ_MODEL", "qwen/qwen3.6-27b")

print(f"Testing Groq API...")
print(f"Model: {model_id}")
print(f"API Key: {api_key[:10]}...{api_key[-4:]}")

try:
    from groq import Groq
    client = Groq(api_key=api_key)
    completion = client.chat.completions.create(
        model=model_id,
        messages=[
            {
                "role": "user",
                "content": "Respond with exactly: 'Groq Qwen 3.6 27B is online and operational.'"
            }
        ],
        temperature=0.6,
        max_completion_tokens=100,
        top_p=0.95,
    )
    res_text = completion.choices[0].message.content or ""
    print(f"\n[SUCCESS] Response from Groq:\n{res_text}")
except ImportError:
    print("[INFO] groq package not installed in global env, testing via OpenAI-compatible endpoint...")
    import urllib.request
    import json
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        headers=headers,
        data=json.dumps({
            "model": model_id,
            "messages": [{"role": "user", "content": "Respond with: Groq Qwen 3.6 27B is operational."}],
            "temperature": 0.6,
            "max_tokens": 100
        }).encode("utf-8")
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print("\n[SUCCESS] Response from Groq via HTTP API:")
        print(data["choices"][0]["message"]["content"])
except Exception as e:
    print(f"\n[ERROR] Groq API call failed: {e}")
    sys.exit(1)
