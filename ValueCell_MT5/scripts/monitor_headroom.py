import time
import requests
import sys
from datetime import datetime

PROXY_STATS_URL = "http://127.0.0.1:8787/stats"

def main():
    print("=" * 65)
    print("   Headroom Real-time Token & Cost Savings Monitor")
    print("============================================================")
    print("Listening for incoming requests from Claude / MT5 Agent...\n")

    seen_requests = set()
    first_run = True

    while True:
        try:
            resp = requests.get(PROXY_STATS_URL, timeout=3.0)
            if resp.status_code == 200:
                data = resp.json()
                recent_requests = data.get("recent_requests", [])
                request_logs = data.get("request_logs", [])
                
                all_reqs = request_logs + recent_requests
                
                summary = data.get("summary", {})
                cost_info = summary.get("cost", {})
                total_saved_usd = cost_info.get("total_saved_usd", 0.0)
                cache_savings_usd = cost_info.get("breakdown", {}).get("cache_savings_usd", 0.0)

                for req in all_reqs:
                    req_id = req.get("request_id")
                    if not req_id or req_id in seen_requests:
                        continue

                    seen_requests.add(req_id)

                    if first_run:
                        continue

                    timestamp = req.get("timestamp", "").split(".")[0].replace("T", " ")
                    if not timestamp:
                        timestamp = datetime.now().strftime("%H:%M:%S")

                    client = req.get("tags", {}).get("client", req.get("provider", "LLM"))
                    model = req.get("model", "unknown-model")
                    
                    orig_tokens = req.get("input_tokens_original", 0)
                    opt_tokens = req.get("input_tokens_optimized", 0)
                    saved_text = req.get("tokens_saved", 0)

                    deferred_saved = 0
                    transforms_list = req.get("transforms_applied", [])
                    for tr in transforms_list:
                        if "tok" in tr and ":" in tr:
                            try:
                                tok_part = tr.split(":")[-1].replace("tok", "")
                                deferred_saved = max(deferred_saved, int(tok_part))
                            except Exception:
                                pass

                    total_real_saved = saved_text + deferred_saved
                    transforms = ", ".join(transforms_list)

                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 Request Detected ({client} | {model})")
                    if orig_tokens > 0:
                        print(f"   -> Prompt Tokens : {orig_tokens:,} orig --> {opt_tokens:,} optimized")
                    
                    print(f"   -> Text Savings   : {saved_text:,} TOKENS (Dynamic prompt text compression)")
                    if deferred_saved > 0:
                        print(f"   -> Tool Savings   : {deferred_saved:,} TOKENS (Deferred tool schemas)")
                    print(f"   -> TOTAL SAVED    : {total_real_saved:,} TOKENS REAL SAVINGS!")
                    
                    if transforms:
                        print(f"   -> Optimizations  : {transforms}")
                    print(f"   -> Cost Savings   : ${total_saved_usd:.4f} USD (${cache_savings_usd:.4f} USD Cache Savings)")
                    print("-" * 65)

                first_run = False
        except Exception:
            pass

        time.sleep(1.0)

if __name__ == "__main__":
    main()
