import json, re

html_path = r"b:\Project MT5\Other\Dokumen\diagram_arsitektur.html"
json_path = r"b:\Project MT5\Other\Dokumen\diagram_layout.json"

with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

# 1. Update CSS for #pan-container to be an absolute infinite canvas without flex shifting
old_pan_css = """        #pan-container {
            position: absolute;
            top: 0;
            left: 0;
            width: 3500px;
            height: 3500px;
            display: flex;
            flex-direction: column;
            align-items: flex-start;
            justify-content: flex-start;
            gap: 3.5rem;
            padding: 80px 0 0 10%;
            transform-origin: 0 0;
        }"""

new_pan_css = """        #pan-container {
            position: absolute;
            top: 0;
            left: 0;
            width: 4500px;
            height: 4500px;
            transform-origin: 0 0;
            pointer-events: none;
        }"""

if old_pan_css in html:
    html = html.replace(old_pan_css, new_pan_css, 1)
else:
    html = re.sub(
        r'#pan-container\s*\{[\s\S]*?transform-origin:\s*0\s*0;\s*\}',
        new_pan_css,
        html
    )

# 2. Update .node-card CSS to be position: absolute; top: 0; left: 0;
html = re.sub(
    r'\.node-card\s*\{([^}]*?)position:\s*relative;',
    r'.node-card {\1position: absolute; top: 0; left: 0;',
    html
)

# 3. Update top-level agent-card info boxes that are direct children of pan-container to position: absolute; top: 0; left: 0;
top_info_cards_css = """        /* Top-Level Info & Condition Cards in Pan Container */
        #node-fe-to-orch-info,
        #node-orch-to-msa-info,
        #node-msa-to-orch-info,
        #node-orch-cond1,
        #node-orch-cond2,
        #node-orch-cond3 {
            position: absolute;
            top: 0;
            left: 0;
        }

        .agents-row {
            position: absolute;
            top: 1050px;
            left: 60px;
            display: flex;
            gap: 1.5rem;
            z-index: 10;
            pointer-events: none;
            align-items: flex-start;
        }"""

if "#node-fe-to-orch-info" not in html:
    html = html.replace(".agents-row {", top_info_cards_css + "\n\n        .old-agents-row {")
    html = re.sub(r'\.old-agents-row\s*\{[\s\S]*?align-items:\s*flex-start;\s*\}', '', html)

# 4. Define clean absolute coordinates for Stage 1 & 2 cards
initial_coords = {
    "node-mt5": {"dx": 750, "dy": 80, "w": 500, "h": 240},
    "node-watcher-trigger": {"dx": 860, "dy": 370, "w": 280, "h": 56},
    "node-neondb-mapping": {"dx": 500, "dy": 470, "w": 480, "h": 220},
    "node-lancedb": {"dx": 60, "dy": 740, "w": 480, "h": 240},
    "node-orchestrator": {"dx": 1040, "dy": 740, "w": 360, "h": 185},
    "node-fe-to-orch-info": {"dx": 1600, "dy": 80, "w": 415, "h": 311},
    "node-orch-to-msa-info": {"dx": 1600, "dy": 430, "w": 493, "h": 185},
    "node-msa-to-orch-info": {"dx": 1600, "dy": 660, "w": 496, "h": 298},
    "node-orch-cond1": {"dx": 2150, "dy": 80, "w": 620, "h": 183},
    "node-orch-cond2": {"dx": 2150, "dy": 310, "w": 434, "h": 306},
    "node-orch-cond3": {"dx": 2150, "dy": 660, "w": 530, "h": 324}
}

for node_id, data in initial_coords.items():
    dx, dy, w, h = data["dx"], data["dy"], data["w"], data["h"]
    pattern = re.compile(rf'(id="{node_id}"[^>]*?)data-dx="[^"]*"\s*data-dy="[^"]*"\s*(?:data-w="[^"]*"\s*data-h="[^"]*"\s*)?style="[^"]*"')
    if pattern.search(html):
        html = pattern.sub(rf'\1data-dx="{dx}" data-dy="{dy}" data-w="{w}" data-h="{h}" style="transform: translate({dx}px, {dy}px); width: {w}px; height: {h}px;"', html)
    else:
        pattern2 = re.compile(rf'(id="{node_id}"[^>]*)style="[^"]*"')
        html = pattern2.sub(rf'\1data-dx="{dx}" data-dy="{dy}" data-w="{w}" data-h="{h}" style="transform: translate({dx}px, {dy}px); width: {w}px; height: {h}px;"', html)

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)
print("HTML updated with absolute decoupled positioning!")

# 5. Update diagram_layout.json with the absolute decoupled coordinates
try:
    with open(json_path, "r", encoding="utf-8") as f:
        layout = json.load(f)
    if "nodes" not in layout:
        layout["nodes"] = {}
    for node_id, data in initial_coords.items():
        layout["nodes"][node_id] = data
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(layout, f, indent=2)
    print("diagram_layout.json updated with absolute decoupled coordinates!")
except Exception as e:
    print("JSON update notice:", e)
