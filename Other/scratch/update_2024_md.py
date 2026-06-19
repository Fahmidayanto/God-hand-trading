
import os

BASE = r"d:\Project\Project MT5"
md_path = os.path.join(BASE, "Dokumen", "2024.md")
new_sessions_path = os.path.join(BASE, "scratch", "new_sessions_2024.md")

with open(md_path, 'r', encoding='utf-8') as f:
    orig_lines = f.readlines()

with open(new_sessions_path, 'r', encoding='utf-8') as f:
    new_content = f.read()

# 1-based lines 180 to 395 correspond to index 179 to 394 in orig_lines
# Perform replacement
updated_lines = orig_lines[:179] + [new_content]

with open(md_path, 'w', encoding='utf-8') as f:
    f.writelines(updated_lines)

print("2024.md successfully updated!")
