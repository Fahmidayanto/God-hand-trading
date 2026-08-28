import re

html = open(r"b:\Project MT5\Other\Dokumen\diagram_arsitektur.html", encoding="utf-8").read()
cards = re.findall(r'id="(node-[^"]+)"', html)
print(f"Total cards found in HTML: {len(cards)}")
for c in cards:
    print(" -", c)
