import os
import re

BASE = r"d:\Project\Project MT5"
md_path = os.path.join(BASE, "Dokumen", "2025.md")

with open(md_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

log_started = False
parsed_signals = {}

for line in lines:
    line_str = line.strip()
    if 'Signal Log Lengkap' in line_str:
        log_started = True
        continue
    if log_started and line_str.startswith('|'):
        parts = [p.strip() for p in line_str.split('|')]
        # Skip header and separator
        if len(parts) < 12 or parts[1] == '#' or parts[1].startswith('---'):
            continue
        
        idx = parts[1]
        entry_time = parts[2]
        trade_type = parts[3]
        catatan = parts[10]
        analisa = parts[11]
        
        key = (entry_time, trade_type)
        parsed_signals[key] = {
            'catatan': catatan,
            'analisa': analisa
        }

print(f"Parsed {len(parsed_signals)} signals from 2025.md")
# Print a few examples to verify
sample_keys = list(parsed_signals.keys())[:5]
for k in sample_keys:
    print(f"Key: {k} -> Catatan: {parsed_signals[k]['catatan']} | Analisa: {parsed_signals[k]['analisa'][:60]}...")
