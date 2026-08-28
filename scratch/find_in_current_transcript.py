import json

transcript_path = r"C:\Users\fahmi\.gemini\antigravity-ide\brain\703a8563-7e8a-48ff-946d-a3e0c964fb96\.system_generated\logs\transcript_full.jsonl"

with open(transcript_path, "r", encoding="utf-8") as f:
    for line_num, line in enumerate(f):
        if "node-llm-msa" in line:
            obj = json.loads(line)
            content = str(obj.get("content", "")) + str(obj.get("tool_calls", ""))
            idx = content.find("node-llm-msa")
            print(f"Line {line_num} in transcript_full has node-llm-msa!")
            snippet = content[max(0, idx - 150): min(len(content), idx + 1000)]
            print(snippet)
            print("-" * 50)
