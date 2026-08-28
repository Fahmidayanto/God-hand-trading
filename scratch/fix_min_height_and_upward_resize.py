import json, re

html_path = r"b:\Project MT5\Other\Dokumen\diagram_arsitektur.html"
json_path = r"b:\Project MT5\Other\Dokumen\diagram_layout.json"

with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

# 1. Update CSS for .node-card and .agent-card min-height
html = re.sub(
    r'\.node-card\s*\{([^}]*?)min-height:\s*100px;',
    r'.node-card {\1min-height: 36px;',
    html
)
html = re.sub(
    r'\.agent-card\s*\{([^}]*?)min-height:\s*[^;]+;',
    r'.agent-card {\1min-height: 36px;',
    html
)

# 2. Update handleCardEdgeResizeStart in JavaScript
old_resize_js = """                // Measure true minimum content height by temporarily testing auto height
                const curInlineH = card.style.height;
                card.style.height = 'auto';
                const naturalAutoH = card.offsetHeight;
                card.style.height = curInlineH || `${startCardHeight}px`;
                const minH = card.classList.contains('agent-card') ? 70 : 90;
                startMinContentH = Math.max(minH, naturalAutoH);"""

new_resize_js = """                // Measure true minimum content height by temporarily testing auto height with zero minHeight
                const curInlineH = card.style.height;
                card.style.height = 'auto';
                card.style.minHeight = '0px';
                const naturalAutoH = card.offsetHeight;
                card.style.height = curInlineH || `${startCardHeight}px`;
                card.style.minHeight = '';
                const minH = 36;
                startMinContentH = Math.max(minH, naturalAutoH);"""

if old_resize_js in html:
    html = html.replace(old_resize_js, new_resize_js, 1)
    print("handleCardEdgeResizeStart header replaced!")
else:
    print("Trying regex for handleCardEdgeResizeStart...")
    html = re.sub(
        r'// Measure true minimum content height[\s\S]*?startMinContentH = Math\.max\(minH, naturalAutoH\);',
        new_resize_js,
        html
    )

# 3. Remove activeResizeCard.style.minHeight = ... from onResizeMove
html = re.sub(
    r'activeResizeCard\.style\.minHeight\s*=\s*`\$\{curH\}px`;\s*',
    '',
    html
)

# 4. Clean up any minW settings to 120
html = re.sub(
    r'const minW = activeResizeCard\.classList\.contains\(\'agent-card\'\) \? 180 : 220;',
    r'const minW = 120;',
    html
)

# 5. Fix node-watcher-trigger in HTML
html = re.sub(
    r'(id="node-watcher-trigger"[^>]*?)data-w="[^"]*"\s*data-h="[^"]*"\s*style="([^"]*?)width:\s*[^;]+;\s*height:\s*[^;]+;"',
    r'\1data-w="280" data-h="56" style="\2width: 280px; height: 56px;"',
    html
)

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)
print("HTML saved successfully!")

# 6. Fix node-watcher-trigger in diagram_layout.json
try:
    with open(json_path, "r", encoding="utf-8") as f:
        layout = json.load(f)
    if "nodes" in layout and "node-watcher-trigger" in layout["nodes"]:
        layout["nodes"]["node-watcher-trigger"]["w"] = 280
        layout["nodes"]["node-watcher-trigger"]["h"] = 56
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(layout, f, indent=2)
        print("diagram_layout.json updated with compact watcher dimensions!")
except Exception as e:
    print("JSON notice:", e)
