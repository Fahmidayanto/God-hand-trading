import re

with open(r"b:\Project MT5\Other\Strategy_all\Dev_Bot_v11_Gold.cs", "r", encoding="utf-8", errors="ignore") as f:
    content = f.read()

print("File length:", len(content))
matches = re.findall(r"(?:chochBearishConfirmedFlag_M15|postChoCH_LL_M15|lastAcceptedHH_M15|lastAcceptedLL_M15)\s*=[^;]+;", content)
for m in matches[:20]:
    print(m)
