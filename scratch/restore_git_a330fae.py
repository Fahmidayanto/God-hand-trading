import subprocess
from pathlib import Path

content = subprocess.check_output(['git', 'show', 'a330fae:Other/Dokumen/diagram_arsitektur.html'], encoding='utf-8')
target = Path(r"b:\Project MT5\Other\Dokumen\diagram_arsitektur.html")
target.write_text(content, encoding="utf-8")
print(f"Restored {target.name} exactly to commit a330fae (length: {len(content)}, lines: {len(content.splitlines())})")
