path = "Other/Strategy_all/Dev_Bot_v11.cs"

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

matches = []
for idx, line in enumerate(content.splitlines()):
    if "positionmodify" in line.lower() or "ordermodify" in line.lower():
        matches.append((idx + 1, line.strip()))

print(f"Total occurrences of Modify calls: {len(matches)}")
for num, line in matches:
    print(f"Line {num}: {line}")
