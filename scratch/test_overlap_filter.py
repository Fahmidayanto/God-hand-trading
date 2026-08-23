# Simulate the two lines:
# Line 1: HH [M15] 4468.29, startTime: 2026.01.07 18:45, endTime: 2026.01.08 07:30
# Line 2: HH [M15] 4466.37, startTime: 2026.01.08 02:15, endTime: 2026.01.08 07:30

lines = [
    {
        'label': 'HH [M15] 4468.29',
        'price': 4468.29,
        'startTime': 1767811500, # 2026.01.07 18:45
        'endTime': 1767857400,   # 2026.01.08 07:30
    },
    {
        'label': 'HH [M15] 4466.37',
        'price': 4466.37,
        'startTime': 1767838500, # 2026.01.08 02:15
        'endTime': 1767857400,   # 2026.01.08 07:30
    }
]

filtered = []
for line in lines:
    isHh = line['label'].startswith('HH') or line['label'].startswith('LH')
    if isHh:
        overlappingHh = next((ex for ex in filtered if (ex['label'].startswith('HH') or ex['label'].startswith('LH')) and 
                              (line['startTime'] <= ex['endTime'] and line['endTime'] >= ex['startTime'])), None)
        if overlappingHh:
            if line['price'] <= overlappingHh['price']:
                print(f"-> Discarded lower HH {line['price']} because active HH {overlappingHh['price']} is higher!")
                continue
            else:
                idx = filtered.index(overlappingHh)
                filtered[idx] = line
                print(f"-> Replaced older HH {overlappingHh['price']} with higher HH {line['price']}")
                continue
    filtered.append(line)

print("\nFinal Filtered Lines:", [f['label'] for f in filtered])
