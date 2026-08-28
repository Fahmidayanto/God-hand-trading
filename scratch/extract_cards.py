import json
import re

transcript_path = r"C:\Users\fahmi\.gemini\antigravity-ide\brain\703a8563-7e8a-48ff-946d-a3e0c964fb96\.system_generated\logs\transcript_full.jsonl"

with open(transcript_path, "r", encoding="utf-8") as f:
    for line_idx, line in enumerate(f):
        if 'id=\\"node-llm-msa\\"' in line or 'id="node-llm-msa"' in line:
            obj = json.loads(line)
            # Check content or tool calls
            s = json.dumps(obj)
            print(f"Match at line {line_idx}, size {len(s)}")
            # Extract div block
            matches = re.findall(r'(<!-- (?:Optional LLM Council Layer|Orchestrator Decision Branches|Data Transfer)[^>]*-->[\s\S]*?)(?=<script>|<div class="detail-panel"|$)', s)
            for m in matches:
                # unescape
                clean = m.replace(r'\"', '"').replace(r'\n', '\n').replace(r'\r', '')
                print("Extracted length:", len(clean))
                with open(rf"b:\Project MT5\scratch\cards_found_{line_idx}.html", "w", encoding="utf-8") as out:
                    out.write(clean)
                print(f"Wrote to scratch/cards_found_{line_idx}.html")
