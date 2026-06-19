
import os

BASE = r"d:\Project\Project MT5"
md_path = os.path.join(BASE, "Dokumen", "2023.md")

with open(md_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix target string for WIN (Executed)
old_str = "| WIN (Executed) | 29 | 25 | 23 | 18 | 19 |"
new_str = "| WIN (Executed) | 29 | 25 | 23 | 18 | 24 |"

if old_str in content:
    content = content.replace(old_str, new_str)
    print("WIN (Executed) successfully updated.")
else:
    print("WARNING: WIN (Executed) line not found!")

with open(md_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("2023.md successfully updated!")
