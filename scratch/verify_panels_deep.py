import re

html_path = r"b:\Project MT5\Other\Dokumen\diagram_arsitektur.html"

with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

# Check cardMap content
cardmap_match = re.search(r'const cardMap = \{([\s\S]*?)\};', html)
if cardmap_match:
    lines = cardmap_match.group(1).strip().split('\n')
    print(f"cardMap has {len(lines)} entries:")
    for l in lines[:10]:
        print("  ", l.strip())

# Check onclicks
onclicks = set(re.findall(r'onclick=[\'"]selectNode\([\'"]([^\'"]+)[\'"]\)', html))
print(f"\nFound {len(onclicks)} unique onclick=selectNode(...) targets:")
print(sorted(list(onclicks)))

# Check all panel IDs in DOM
panel_ids = set(re.findall(r'id=[\'"](panel-[^\'"]+)[\'"]', html))
print(f"\nFound {len(panel_ids)} panel IDs in HTML:")
print(sorted(list(panel_ids)))

# Check if each onclick has a corresponding cardMap entry and panel ID
for oc in sorted(list(onclicks)):
    # Look for key in cardMap
    k_match = re.search(rf'[\'"]{re.escape(oc)}[\'"]\s*:\s*\{{\s*cardId:\s*[\'"]([^\'"]+)[\'"],\s*panelId:\s*[\'"]([^\'"]+)[\'"]', html)
    if not k_match:
        print(f"ERROR: onclick '{oc}' NOT found in cardMap!")
    else:
        cid, pid = k_match.group(1), k_match.group(2)
        if pid not in panel_ids:
            print(f"ERROR: panelId '{pid}' for onclick '{oc}' NOT in DOM!")
        else:
            # Check if panel div has text content
            pdiv = re.search(rf'<div[^>]*id=[\'"]{re.escape(pid)}[\'"][^>]*>([\s\S]*?)</div>', html)
            if not pdiv or len(pdiv.group(1).strip()) < 10:
                print(f"WARNING: panel '{pid}' has empty or very short content!")

print("\nAudit complete!")
