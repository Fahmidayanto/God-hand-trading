import json, re

html_path = r"b:\Project MT5\Other\Dokumen\diagram_arsitektur.html"
json_path = r"b:\Project MT5\Other\Dokumen\diagram_layout.json"

with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

# 1. Update applyLayoutState in JavaScript to auto-heal any crushed card heights
old_apply_layout = """                            if (node.w) {
                                card.style.width = `${node.w}px`;
                                card.setAttribute('data-w', node.w);
                            }
                            if (node.h) {
                                card.style.height = `${node.h}px`;
                                card.setAttribute('data-h', node.h);
                            }"""

new_apply_layout = """                            if (node.w) {
                                card.style.width = `${node.w}px`;
                                card.setAttribute('data-w', node.w);
                            }
                            if (node.h) {
                                card.style.height = `${node.h}px`;
                                card.setAttribute('data-h', node.h);
                            }
                            // Auto-fit protection: Ensure card height always fully accommodates its content
                            card.style.height = 'auto';
                            const naturalContentH = card.offsetHeight;
                            const finalH = node.h ? Math.max(node.h, naturalContentH) : naturalContentH;
                            card.style.height = `${finalH}px`;
                            card.setAttribute('data-h', finalH);"""

if old_apply_layout in html:
    html = html.replace(old_apply_layout, new_apply_layout, 1)
    print("applyLayoutState updated with auto-fit protection!")
else:
    print("Old applyLayoutState snippet not exact, trying regex...")
    html = re.sub(
        r'if \(node\.w\) \{[\s\S]*?if \(node\.h\) \{[\s\S]*?card\.setAttribute\(\'data-h\', node\.h\);\s*\}',
        new_apply_layout,
        html
    )

# 2. Update onResizeMove to dynamically handle horizontal re-wrapping
old_calc = """                    } else {
                        // For pure horizontal resizing, ensure height still accommodates wrapped text
                        curH = Math.max(startCardHeight, activeResizeCard.scrollHeight);
                    }"""

new_calc = """                    } else {
                        // For pure horizontal resizing, re-measure auto content height as text wraps/unwraps
                        activeResizeCard.style.height = 'auto';
                        const rewrappedH = activeResizeCard.offsetHeight;
                        curH = Math.max(startCardHeight, rewrappedH);
                    }"""

if old_calc in html:
    html = html.replace(old_calc, new_calc, 1)
    print("onResizeMove horizontal rewrapping updated!")

# 3. Add dblclick on resizers to snap to fit-content
old_resizer_create = """                    resizeDirs.forEach(({ dir, title }) => {
                        const edgeResizer = document.createElement('div');
                        edgeResizer.className = `card-edge-resizer edge-${dir}`;
                        edgeResizer.title = title;
                        edgeResizer.addEventListener('mousedown', (e) => handleCardEdgeResizeStart(e, card, dir));
                        edgeResizer.addEventListener('touchstart', (e) => handleCardEdgeResizeStart(e, card, dir), { passive: false });
                        card.appendChild(edgeResizer);
                    });"""

new_resizer_create = """                    resizeDirs.forEach(({ dir, title }) => {
                        const edgeResizer = document.createElement('div');
                        edgeResizer.className = `card-edge-resizer edge-${dir}`;
                        edgeResizer.title = title + ' (Klik ganda untuk Auto-Fit)';
                        edgeResizer.addEventListener('mousedown', (e) => handleCardEdgeResizeStart(e, card, dir));
                        edgeResizer.addEventListener('touchstart', (e) => handleCardEdgeResizeStart(e, card, dir), { passive: false });
                        edgeResizer.addEventListener('dblclick', (e) => {
                            e.stopPropagation();
                            e.preventDefault();
                            card.style.height = 'auto';
                            const fitH = card.offsetHeight;
                            card.style.height = `${fitH}px`;
                            card.setAttribute('data-h', fitH);
                            drawLines();
                            saveLayoutState();
                        });
                        card.appendChild(edgeResizer);
                    });"""

if old_resizer_create in html:
    html = html.replace(old_resizer_create, new_resizer_create, 1)
    print("Double-click auto-fit added to edge resizers!")

# 4. Update node-neondb-mapping and node-lancedb in HTML
html = re.sub(
    r'(id="node-neondb-mapping"[^>]*?)data-w="[^"]*"\s*data-h="[^"]*"\s*style="([^"]*?)width:\s*[^;]+;\s*height:\s*[^;]+;"',
    r'\1data-w="480" data-h="220" style="\2width: 480px; height: 220px;"',
    html
)

html = re.sub(
    r'(id="node-lancedb"[^>]*?)style="([^"]*?)"',
    r'\1data-w="480" data-h="240" style="\2 width: 480px; height: 240px;"',
    html
)

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)
print("HTML saved successfully!")

# 5. Update diagram_layout.json with generous dimensions
try:
    with open(json_path, "r", encoding="utf-8") as f:
        layout = json.load(f)
    if "nodes" in layout:
        if "node-neondb-mapping" in layout["nodes"]:
            layout["nodes"]["node-neondb-mapping"]["w"] = 480
            layout["nodes"]["node-neondb-mapping"]["h"] = 220
        if "node-lancedb" in layout["nodes"]:
            layout["nodes"]["node-lancedb"]["w"] = 480
            layout["nodes"]["node-lancedb"]["h"] = 240
        if "node-orchestrator" in layout["nodes"]:
            layout["nodes"]["node-orchestrator"]["w"] = 360
            layout["nodes"]["node-orchestrator"]["h"] = 195
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(layout, f, indent=2)
        print("diagram_layout.json updated successfully!")
except Exception as e:
    print("JSON update notice:", e)
