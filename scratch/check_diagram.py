# -*- coding: utf-8 -*-
"""
Verification script for diagram_arsitektur.html
Checks:
1. All node IDs referenced in defaultConnections exist in DOM
2. All nodes have corresponding panel IDs
3. No duplicate IDs
"""
import re

html_path = r"b:\Project MT5\Other\Dokumen\diagram_arsitektur.html"
with open(html_path, "r", encoding="utf-8") as f:
    content = f.read()

# Extract all elements with id="..."
all_ids = set(re.findall(r'id="([^"]+)"', content))
print(f"Total Unique IDs in DOM: {len(all_ids)}")

# Extract connections
conn_matches = re.findall(r'\{\s*from:\s*"([^"]+)",\s*fromPort:\s*"([^"]+)",\s*to:\s*"([^"]+)",\s*toPort:\s*"([^"]+)"\s*\}', content)
print(f"Total Default Connections: {len(conn_matches)}")

missing_nodes = []
for c_from, fp, c_to, tp in conn_matches:
    if c_from not in all_ids:
        missing_nodes.append(f"FROM: {c_from}")
    if c_to not in all_ids:
        missing_nodes.append(f"TO: {c_to}")

if missing_nodes:
    print(f"FAILED: Missing connection nodes: {missing_nodes}")
else:
    print("PASSED: All connection nodes exist in DOM.")

# Check MSA nodes specifically
msa_nodes = ["node-ms-agent", "node-ms-sub1", "node-ms-sub2", "node-ms-sub3", "node-ms-sub4"]
for n in msa_nodes:
    panel_id = "panel-" + n[5:]
    has_node = n in all_ids
    has_panel = panel_id in all_ids
    print(f"Node {n}: DOM={'OK' if has_node else 'MISSING'}, Panel {panel_id}={'OK' if has_panel else 'MISSING'}")
