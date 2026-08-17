"""
Get full list of models on 9inference /v1/package/models
"""
import urllib.request
import json

api_key = "sk_live_66f741e252367899a56bef4608f5acf27003944a9e3b535f"
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0"
}

req = urllib.request.Request("https://9inference.cloud/v1/package/models", headers=headers)
try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print("Available models in 9inference package:")
        for m in data.get("data", []):
            print(f" - {m.get('id')} ({m.get('owned_by', '')})")
except Exception as e:
    print(f"Error: {e}")
