import json, re

html_path = r"b:\Project MT5\Other\Dokumen\diagram_arsitektur.html"
json_path = r"b:\Project MT5\Other\Dokumen\diagram_layout.json"

with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

# Update CSS for card-header, card-icon, card-title, card-badge
old_css = """.card-header {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            margin-bottom: 1rem;
        }

        .card-icon {
            font-size: 1.5rem;
            display: flex;
            align-items: center;
            justify-content: center;
            width: 40px;
            height: 40px;
            border-radius: 10px;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }

        .card-title {
            font-family: 'Space Grotesk', sans-serif;
            font-weight: 700;
            font-size: 1.15rem;
            letter-spacing: -0.02em;
        }

        .card-badge {
            margin-left: auto;
            font-size: 0.7rem;
            font-weight: 700;
            padding: 0.25rem 0.6rem;
            border-radius: 20px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            background: rgba(255, 255, 255, 0.08);
            color: var(--text-secondary);
        }"""

new_css = """.card-header {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            margin-bottom: 0.85rem;
            position: relative;
        }

        .card-header > div:nth-child(2) {
            flex: 1;
            min-width: 0;
        }

        .card-header p {
            margin: 0.15rem 0 0 0;
            padding: 0;
            line-height: 1.2;
        }

        .card-icon {
            font-size: 1.5rem;
            display: flex;
            align-items: center;
            justify-content: center;
            width: 40px;
            height: 40px;
            border-radius: 10px;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            flex-shrink: 0;
        }

        .card-title {
            font-family: 'Space Grotesk', sans-serif;
            font-weight: 700;
            font-size: 1.05rem;
            letter-spacing: -0.02em;
            line-height: 1.25;
            word-break: break-word;
        }

        .card-badge {
            margin-left: auto;
            font-size: 0.7rem;
            font-weight: 700;
            padding: 0.25rem 0.6rem;
            border-radius: 20px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            background: rgba(255, 255, 255, 0.08);
            color: var(--text-secondary);
            flex-shrink: 0;
            white-space: nowrap;
        }"""

if old_css in html:
    html = html.replace(old_css, new_css, 1)
    print("CSS replaced successfully!")
else:
    print("Old CSS block not matched, trying regex...")
    html = re.sub(
        r'\.card-header\s*\{[\s\S]*?color:\s*var\(--text-secondary\);\s*\}',
        new_css,
        html
    )
    print("CSS replaced via regex!")

# Update node-orchestrator card HTML
orch_pattern = re.compile(r'<!-- Node 5: Orchestrator Agent -->\s*<div class="node-card" id="node-orchestrator"[^>]*>[\s\S]*?</div>\s*</div>', re.MULTILINE)

new_orch_card = """<!-- Node 5: Orchestrator Agent -->
                <div class="node-card" id="node-orchestrator" onclick="selectNode('orchestrator')" data-dx="1034.6670129796428" data-dy="-419.96460295289927" data-w="340" data-h="165" style="transform: translate(1034.6670129796428px, -419.96460295289927px); width: 340px; height: 165px;">
                    <div class="card-header">
                        <div class="card-icon">🧠</div>
                        <div>
                            <div class="card-title">ORCHESTRATOR AGENT</div>
                            <p style="font-size: 0.75rem; color: var(--text-secondary);">Koordinator Multi-Agen</p>
                        </div>
                        <span class="card-badge">Brain</span>
                    </div>
                    <div class="card-content" style="font-size: 0.8rem; line-height: 1.45;">
                        Mengatur alur kerja: menerima data pasar, meminta agen lain menganalisis, lalu mengirim hasilnya ke mesin konsensus.
                    </div>
                </div>"""

if orch_pattern.search(html):
    html = orch_pattern.sub(new_orch_card, html, count=1)
    print("Orchestrator card updated!")
else:
    print("Orchestrator card regex not matched!")

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)
print("HTML saved successfully!")

# Also update diagram_layout.json with width and height for node-orchestrator
try:
    with open(json_path, "r", encoding="utf-8") as f:
        layout = json.load(f)
    if "nodes" in layout and "node-orchestrator" in layout["nodes"]:
        layout["nodes"]["node-orchestrator"]["w"] = 340
        layout["nodes"]["node-orchestrator"]["h"] = 165
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(layout, f, indent=2)
        print("diagram_layout.json updated with orchestrator dimensions!")
except Exception as e:
    print("JSON update notice:", e)
