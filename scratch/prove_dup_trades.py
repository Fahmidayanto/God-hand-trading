# Time in DB trade: 2020.01.16 02:15:01
db_entry_time = 1579140901 # 2020.01.16 02:15:01 UTC
event_time = 1579140000    # 2020.01.16 02:00:00 UTC
local_entry_time = event_time + 900 # 1579140900 (02:15:00 UTC)

diff_to_event = abs(db_entry_time - event_time)
print(f"diff_to_event: {diff_to_event} seconds (Threshold was <= 900, so {diff_to_event} <= 900 is {diff_to_event <= 900})")

# In dedup seenKeys:
key_db = f"BUY_{db_entry_time}"
key_local = f"BUY_{local_entry_time}"
print(f"key_db: {key_db}, key_local: {key_local}, equal? {key_db == key_local}")
