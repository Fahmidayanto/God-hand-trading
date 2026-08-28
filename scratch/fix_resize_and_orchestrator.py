import json, re

html_path = r"b:\Project MT5\Other\Dokumen\diagram_arsitektur.html"
json_path = r"b:\Project MT5\Other\Dokumen\diagram_layout.json"

with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

# 1. Update CSS for .node-card, .agent-card, and .card-resizer
old_card_css = """.node-card {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 1.5rem;
            width: 500px;
            min-width: 260px;
            min-height: 100px;
            position: relative;
            z-index: 10;
            cursor: pointer;
            transition: box-shadow 0.3s ease, border-color 0.3s ease, background 0.3s ease;
            backdrop-filter: blur(8px);
            box-shadow: 0 4px 30px rgba(0, 0, 0, 0.4);
            pointer-events: auto;
        }"""

new_card_css = """.node-card {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 1.25rem 1.5rem;
            width: 500px;
            min-width: 260px;
            min-height: 100px;
            position: relative;
            z-index: 10;
            cursor: pointer;
            transition: box-shadow 0.3s ease, border-color 0.3s ease, background 0.3s ease;
            backdrop-filter: blur(8px);
            box-shadow: 0 4px 30px rgba(0, 0, 0, 0.4);
            pointer-events: auto;
            display: flex;
            flex-direction: column;
            box-sizing: border-box;
        }"""

if old_card_css in html:
    html = html.replace(old_card_css, new_card_css, 1)

old_resizer_css = """        /* Card Resizer Handle on bottom-right corner */
        .card-resizer {
            position: absolute;
            right: 4px;
            bottom: 4px;
            width: 18px;
            height: 18px;
            cursor: se-resize;
            opacity: 0.25;
            transition: opacity 0.2s ease, transform 0.2s ease;
            z-index: 35;
            pointer-events: auto;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .node-card:hover .card-resizer,
        .agent-card:hover .card-resizer,
        .card-resizer.resizing {
            opacity: 0.95;
            transform: scale(1.1);
        }

        .card-resizer::after {
            content: '';
            position: absolute;
            right: 4px;
            bottom: 4px;
            width: 8px;
            height: 8px;
            border-right: 2px solid var(--text-secondary);
            border-bottom: 2px solid var(--text-secondary);
            border-bottom-right-radius: 2px;
        }"""

new_resizer_css = """        /* Card Resizer Handle on bottom-right corner */
        .card-resizer {
            position: absolute;
            right: 2px;
            bottom: 2px;
            width: 24px;
            height: 24px;
            cursor: nwse-resize;
            opacity: 0.35;
            transition: opacity 0.2s ease, transform 0.2s ease;
            z-index: 50;
            pointer-events: auto;
            display: flex;
            align-items: flex-end;
            justify-content: flex-end;
            padding: 3px;
        }

        .node-card:hover .card-resizer,
        .agent-card:hover .card-resizer,
        .card-resizer.resizing {
            opacity: 1;
            transform: scale(1.2);
        }

        .card-resizer::after {
            content: '';
            width: 10px;
            height: 10px;
            border-right: 2.5px solid var(--theme-color, #00e5ff);
            border-bottom: 2.5px solid var(--theme-color, #00e5ff);
            border-bottom-right-radius: 3px;
        }"""

if old_resizer_css in html:
    html = html.replace(old_resizer_css, new_resizer_css, 1)
else:
    html = re.sub(
        r'/\*\s*Card Resizer Handle on bottom-right corner\s*\*\/[\s\S]*?border-bottom-right-radius:\s*2px;\s*\}',
        new_resizer_css,
        html
    )

# 2. Update handleCardResizeStart in JavaScript
old_resize_fn = """                const onResizeMove = (moveEvent) => {
                    if (!activeResizeCard) return;
                    const curX = moveEvent.type === 'touchmove' ? moveEvent.touches[0].clientX : moveEvent.clientX;
                    const curY = moveEvent.type === 'touchmove' ? moveEvent.touches[0].clientY : moveEvent.clientY;

                    const deltaX = (curX - resizeStartX) / zoomScale;
                    const deltaY = (curY - resizeStartY) / zoomScale;

                    const minW = activeResizeCard.classList.contains('agent-card') ? 180 : 240;
                    const minH = activeResizeCard.classList.contains('agent-card') ? 80 : 100;

                    const newW = Math.max(minW, Math.round(startCardWidth + deltaX));
                    const newH = Math.max(minH, Math.round(startCardHeight + deltaY));

                    activeResizeCard.style.width = `${newW}px`;
                    activeResizeCard.style.height = `${newH}px`;
                    activeResizeCard.setAttribute('data-w', newW);
                    activeResizeCard.setAttribute('data-h', newH);

                    drawLines();

                    if (moveEvent.type === 'touchmove') moveEvent.preventDefault();
                };"""

new_resize_fn = """                const onResizeMove = (moveEvent) => {
                    if (!activeResizeCard) return;
                    const curX = moveEvent.type === 'touchmove' ? moveEvent.touches[0].clientX : moveEvent.clientX;
                    const curY = moveEvent.type === 'touchmove' ? moveEvent.touches[0].clientY : moveEvent.clientY;

                    const deltaX = (curX - resizeStartX) / zoomScale;
                    const deltaY = (curY - resizeStartY) / zoomScale;

                    const minW = activeResizeCard.classList.contains('agent-card') ? 180 : 240;
                    const minH = activeResizeCard.classList.contains('agent-card') ? 70 : 90;

                    const targetW = Math.max(minW, Math.round(startCardWidth + deltaX));
                    activeResizeCard.style.width = `${targetW}px`;
                    activeResizeCard.setAttribute('data-w', targetW);

                    // Ensure height fits content and allows vertical expansion
                    const naturalH = activeResizeCard.scrollHeight;
                    const targetH = Math.max(minH, Math.round(startCardHeight + deltaY));
                    const finalH = Math.max(targetH, naturalH);

                    activeResizeCard.style.height = `${finalH}px`;
                    activeResizeCard.setAttribute('data-h', finalH);

                    drawLines();

                    if (moveEvent.type === 'touchmove') moveEvent.preventDefault();
                };"""

if old_resize_fn in html:
    html = html.replace(old_resize_fn, new_resize_fn, 1)
    print("Resize function updated successfully!")
else:
    print("Old resize function not exact match, using regex...")
    html = re.sub(
        r'const onResizeMove = \(moveEvent\) => \{[\s\S]*?if \(moveEvent\.type === \'touchmove\'\) moveEvent\.preventDefault\(\);\s*\};',
        new_resize_fn,
        html
    )
    print("Resize function updated via regex!")

# 3. Update node-orchestrator in HTML with proper dimensions (w: 360, h: 195)
orch_pattern = re.compile(r'<!-- Node 5: Orchestrator Agent -->\s*<div class="node-card" id="node-orchestrator"[^>]*>[\s\S]*?</div>\s*</div>', re.MULTILINE)

new_orch_card = """<!-- Node 5: Orchestrator Agent -->
                <div class="node-card" id="node-orchestrator" onclick="selectNode('orchestrator')" data-dx="1034.6670129796428" data-dy="-419.96460295289927" data-w="360" data-h="195" style="transform: translate(1034.6670129796428px, -419.96460295289927px); width: 360px; height: 195px;">
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
    print("Orchestrator card updated in HTML!")

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)
print("HTML saved successfully!")

# 4. Update diagram_layout.json for node-orchestrator
try:
    with open(json_path, "r", encoding="utf-8") as f:
        layout = json.load(f)
    if "nodes" in layout and "node-orchestrator" in layout["nodes"]:
        layout["nodes"]["node-orchestrator"]["w"] = 360
        layout["nodes"]["node-orchestrator"]["h"] = 195
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(layout, f, indent=2)
        print("diagram_layout.json updated successfully!")
except Exception as e:
    print("JSON update warning:", e)
