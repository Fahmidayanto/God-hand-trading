import re

html_path = r"b:\Project MT5\Other\Dokumen\diagram_arsitektur.html"

with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

# 1. Find all selectNode('...') in HTML
onclick_types = set(re.findall(r'selectNode\([\'"]([^\'"]+)[\'"]\)', html))
print(f"Total selectNode calls found in HTML: {len(onclick_types)}")

# 2. Extract cardMap in selectNode
cardmap_match = re.search(r'const cardMap = \{([\s\S]*?)\};', html)
cardmap_keys = set()
if cardmap_match:
    cardmap_keys = set(re.findall(r'[\'"]([^\'"]+)[\'"]\s*:', cardmap_match.group(1)))
print(f"Total cardMap keys found in JS: {len(cardmap_keys)}")

# 3. Find all panel IDs in HTML
panel_ids = set(re.findall(r'id=[\'"](panel-[^\'"]+)[\'"]', html))
print(f"Total panel IDs found in HTML: {len(panel_ids)}")

# 4. Check missing keys
missing_in_cardmap = onclick_types - cardmap_keys
print(f"Missing in cardMap: {missing_in_cardmap}")

# 5. Check if cardMap panelIds exist in DOM
for k in cardmap_keys:
    # check panelId
    p_match = re.search(rf'[\'"]{re.escape(k)}[\'"]\s*:\s*\{{[^}}]*panelId\s*:\s*[\'"]([^\'"]+)[\'"]', html)
    if p_match:
        pid = p_match.group(1)
        if pid not in panel_ids:
            print(f"Warning: Panel ID {pid} for key '{k}' NOT in HTML!")
