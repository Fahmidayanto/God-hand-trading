from pathlib import Path
import re

html = Path(r"b:\Project MT5\Other\Dokumen\diagram_arsitektur.html").read_text(encoding="utf-8")

matches = re.findall(r"LAYOUT_VERSION\s*=\s*\d+", html)
panels = re.findall(r'id="panel-', html)
scripts = re.findall(r'<script>', html)
closings = re.findall(r'</script>', html)

print("Total lines:", len(html.splitlines()))
print("LAYOUT_VERSION matches:", matches)
print("Script tag count:", len(scripts))
print("Closing script tag count:", len(closings))
print("Panel count:", len(panels))
print("defaultConnections presence:", 'const defaultConnections =' in html)
print("defaultLayoutState presence:", 'const defaultLayoutState =' in html)
