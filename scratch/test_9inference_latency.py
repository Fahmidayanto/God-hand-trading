"""
Test completions with various models and timeout settings on 9inference
"""
import urllib.request
import json
import time
import os

api_key = os.getenv("NINEINFERENCE_API_KEY", "")
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0"
}

models = ["deepseek-v4-flash", "deepseek-v4-flash-0731", "deepseek-v4-pro-0813", "glm-5.2"]

for m in models:
    url = "https://9inference.cloud/v1/package/chat/completions"
    payload = {
        "model": m,
        "messages": [{"role": "user", "content": "Hi"}],
        "max_tokens": 10
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    print(f"\nTesting model: {m}...")
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            elapsed = time.time() - start
            body = json.loads(resp.read().decode("utf-8"))
            content = body.get("choices", [{}])[0].get("message", {}).get("content", "")
            print(f" -> SUCCESS in {elapsed:.2f}s: {content.strip()}")
    except Exception as e:
        elapsed = time.time() - start
        print(f" -> FAILED in {elapsed:.2f}s: {e}")
