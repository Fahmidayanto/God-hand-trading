import glob
import re

logs = glob.glob(r"C:\Users\fahmi\.gemini\antigravity-ide\brain\*\.system_generated\logs\*.jsonl")
print(f"Searching {len(logs)} log files...")

for log in logs:
    try:
        with open(log, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            if "node-llm-msa" in content:
                print(f"Found 'node-llm-msa' in {log} (size: {len(content)})")
                # Extract HTML block around node-llm-msa
                idx = content.find('id=\\"node-llm-msa\\"')
                if idx == -1:
                    idx = content.find('id="node-llm-msa"')
                if idx != -1:
                    snippet = content[max(0, idx - 200): min(len(content), idx + 2000)]
                    print("Snippet:")
                    print(snippet)
                    print("="*60)
    except Exception as e:
        print(f"Error reading {log}: {e}")
