import json
from pathlib import Path
import re

json_path = Path(r"b:\Project MT5\Other\Dokumen\diagram_layout.json")
html_path = Path(r"b:\Project MT5\Other\Dokumen\diagram_arsitektur.html")

layout = json.loads(json_path.read_text(encoding="utf-8"))
html = html_path.read_text(encoding="utf-8")

nodes = layout.get("nodes", {})
for node_id, pos in nodes.items():
    dx = pos.get("dx", 0)
    dy = pos.get("dy", 0)
    w = pos.get("w")
    h = pos.get("h")
    
    # Match card tag with id="node_id"
    pattern = rf'(<div[^>]*id="{node_id}"[^>]*>)'
    match = re.search(pattern, html)
    if match:
        tag = match.group(1)
        # Clean existing dx, dy, w, h, style
        clean_tag = re.sub(r'\s*data-dx="[^"]*"', '', tag)
        clean_tag = re.sub(r'\s*data-dy="[^"]*"', '', clean_tag)
        clean_tag = re.sub(r'\s*data-w="[^"]*"', '', clean_tag)
        clean_tag = re.sub(r'\s*data-h="[^"]*"', '', clean_tag)
        clean_tag = re.sub(r'\s*style="[^"]*"', '', clean_tag)
        
        # Build new attrs & style
        style_parts = [f"transform: translate({dx}px, {dy}px);"]
        attrs_parts = [f'data-dx="{dx}"', f'data-dy="{dy}"']
        if w is not None:
            style_parts.append(f"width: {w}px;")
            attrs_parts.append(f'data-w="{w}"')
        if h is not None:
            style_parts.append(f"height: {h}px;")
            attrs_parts.append(f'data-h="{h}"')
            
        style_str = " ".join(style_parts)
        attrs_str = " ".join(attrs_parts)
        
        new_tag = clean_tag[:-1] + f' {attrs_str} style="{style_str}">'
        html = html.replace(tag, new_tag)

html_path.write_text(html, encoding="utf-8")
print(f"Successfully baked {len(nodes)} node positions into {html_path.name}!")
