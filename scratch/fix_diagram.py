import re
import json

HTML_FILE = r"b:\Project MT5\Other\Dokumen\diagram_arsitektur.html"
LAYOUT_FILE = r"b:\Project MT5\Other\Dokumen\diagram_layout.json"

with open(HTML_FILE, "r", encoding="utf-8") as f:
    content = f.read()

with open(LAYOUT_FILE, "r", encoding="utf-8") as f:
    layout_data = json.load(f)

layout_json_str = json.dumps(layout_data, indent=4)

# 1. Ensure defaultLayoutState is exactly equal to layout_data
layout_replacement = f"const defaultLayoutState = {layout_json_str};"
content = re.sub(r"const defaultLayoutState = [\s\S]*?;\s*(?=\n\s*// Selection & Hover)", layout_replacement + "\n\n", content)

print("defaultLayoutState check done")
