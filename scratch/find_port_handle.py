with open(r'b:\Project MT5\Other\Dokumen\diagram_arsitektur.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'port-handle' in line or 'port_handle' in line:
        print(f"Line {i+1}: {line.strip()}")
