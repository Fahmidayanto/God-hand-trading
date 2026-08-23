import requests

url = "http://localhost:8000/trading/replay?year_from=2020&month_from=1&year_to=2020&month_to=1&timeframe=M15"
res = requests.get(url)
data = res.json()

print(f"Total executed trades returned by API: {len(data.get('trades', []))}")
print(f"Total rejected trades returned by API: {len(data.get('rejected_trades', []))}")

print("\n--- ALL EXECUTED TRADES IN JAN 2020 ---")
for t in data.get('trades', []):
    print(f"Ticket: {t.get('ticket')}, Type: {t.get('type')}, EntryTime: {t.get('entry_time')}, EntryPrice: {t.get('entry_price')}, Structure: {t.get('structure_type') or t.get('entry_structure')}")

