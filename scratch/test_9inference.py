"""
Diagnostic script for 9inference DeepSeek endpoint.
Tests network reachability, API key validity, latency, and models list.
"""
import urllib.request
import urllib.error
import json
import time

api_key = "sk_live_66f741e252367899a56bef4608f5acf27003944a9e3b535f"
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

endpoints_to_test = [
    ("https://9inference.cloud/v1/models", "GET", None),
    ("https://9inference.cloud/v1/package/models", "GET", None),
    ("https://9inference.cloud/v1/chat/completions", "POST", {
        "model": "deepseek-v4-flash-0731",
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 10
    }),
    ("https://9inference.cloud/v1/package/chat/completions", "POST", {
        "model": "deepseek-v4-flash-0731",
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 10
    })
]

for url, method, payload in endpoints_to_test:
    print(f"\n--- Testing {method} {url} ---")
    data = json.dumps(payload).encode("utf-8") if payload else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    
    start_time = time.time()
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            elapsed = time.time() - start_time
            body = resp.read().decode("utf-8", errors="replace")
            print(f"Status: {resp.status} (took {elapsed:.2f}s)")
            print(f"Response: {body[:300]}")
    except urllib.error.HTTPError as e:
        elapsed = time.time() - start_time
        body = e.read().decode("utf-8", errors="replace")
        print(f"HTTPError: {e.code} {e.reason} (took {elapsed:.2f}s)")
        print(f"Response Body: {body[:300]}")
    except urllib.error.URLError as e:
        elapsed = time.time() - start_time
        print(f"URLError (Network/Timeout/DNS): {e.reason} (took {elapsed:.2f}s)")
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"Exception: {e} (took {elapsed:.2f}s)")
