"""
Inspect full JSON response structure from deepseek-v4-flash-0731 on 9inference
"""
import urllib.request
import json
import os

api_key = os.getenv("NINEINFERENCE_API_KEY", "")
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0"
}

url = "https://9inference.cloud/v1/package/chat/completions"
payload = {
    "model": "deepseek-v4-flash-0731",
    "messages": [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, please give me a 1 sentence answer."}
    ],
    "temperature": 0.6,
    "max_tokens": 100
}

req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        body_text = resp.read().decode("utf-8")
        data = json.loads(body_text)
        print("Full JSON Response from 9inference:")
        print(json.dumps(data, indent=2))
except Exception as e:
    print(f"Error: {e}")
