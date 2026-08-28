import re

html_path = r"b:\Project MT5\Other\Dokumen\diagram_arsitektur.html"

with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

print("HTML Length:", len(html))
print("Contains 'selectNode':", "selectNode" in html)
print("Contains 'side-panel':", "side-panel" in html)
print("Contains 'detail-panel':", "detail-panel" in html)

matches = re.findall(r'function \w+', html)
print("First 20 functions found:", matches[:20])
