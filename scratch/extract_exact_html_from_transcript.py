import json
import re

transcript_path = r"C:\Users\fahmi\.gemini\antigravity-ide\brain\703a8563-7e8a-48ff-946d-a3e0c964fb96\.system_generated\logs\transcript_full.jsonl"

with open(transcript_path, "r", encoding="utf-8") as f:
    for line_idx, line in enumerate(f):
        if "node-llm-msa" in line:
            obj = json.loads(line)
            tool_calls = obj.get("tool_calls", [])
            for call in tool_calls:
                args = call.get("args", {})
                content = args.get("CodeContent") or args.get("ReplacementContent") or ""
                if "node-llm-msa" in content:
                    print(f"Found in tool call line {line_idx}, content length: {len(content)}")
                    with open(rf"b:\Project MT5\scratch\extracted_block_{line_idx}.html", "w", encoding="utf-8") as out:
                        out.write(content)
                    print(f"Saved to scratch/extracted_block_{line_idx}.html")
