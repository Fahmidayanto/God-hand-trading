
import os

BASE = r"d:\Project\Project MT5"
md_path = os.path.join(BASE, "Dokumen", "2023.md")

with open(md_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "WIN (Executed)" in line:
        print(f"Line {i+1}: {repr(line)}")
