import re

def sort_tables_by_hour():
    filepath = r"d:\Project\Project MT5\Dokumen\2023.md"
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Split the content to locate Section 12.3b
    section_start_str = "### 12.3b Rincian Detail Setiap Transaksi Executed Berdasarkan Sesi (V11 — TAHUN 2023)"
    section_end_str = "### 12.4"
    
    parts = content.split(section_start_str)
    if len(parts) < 2:
        print("Could not find section start!")
        return
        
    before_section = parts[0]
    section_and_after = parts[1]
    
    subparts = section_and_after.split(section_end_str, 1)
    if len(subparts) < 2:
        print("Could not find section end!")
        return
        
    section_content = subparts[0]
    after_section = subparts[1]
    
    # We want to parse each session table in section_content
    # Session tables look like:
    # #### Sesi: <SessionName> (<Count> Transaksi)
    # | # | Waktu Entri | ...
    # |---|-------------|...
    # | ... rows ...
    
    session_blocks = re.split(r"(#### Sesi: [^\n]+)", section_content)
    
    new_section_content = session_blocks[0] # Header text
    
    # Iterate through blocks
    for i in range(1, len(session_blocks), 2):
        session_header = session_blocks[i]
        session_table = session_blocks[i+1]
        
        # Parse the rows of the table
        lines = session_table.strip().split("\n")
        if len(lines) < 3:
            new_section_content += session_header + session_table
            continue
            
        header = lines[0]
        separator = lines[1]
        data_lines = lines[2:]
        
        parsed_rows = []
        for line in data_lines:
            if not line.strip() or line.strip().startswith("---"):
                continue
            cols = [c.strip() for c in line.split("|")]
            # cols will be ['', '#', 'Waktu Entri', 'Tipe', 'Entry', 'SL', 'TP', 'Jam', 'BR (%)', 'Outcome', 'Profit ($)', 'Exit Type', '']
            if len(cols) >= 12:
                # Column index 7 is Jam
                jam_val = int(cols[7])
                parsed_rows.append((jam_val, cols[2], line)) # Sort by Jam first, then by EntryTime (Waktu Entri) as a secondary key
                
        # Sort rows: first by Jam (hour), then chronologically by Waktu Entri
        parsed_rows.sort(key=lambda x: (x[0], x[1]))
        
        # Re-number local index '#' from 1 to N inside each table
        new_table_rows = []
        for index, (jam_val, waktu_entri, original_line) in enumerate(parsed_rows, 1):
            cols = [c.strip() for c in original_line.split("|")]
            cols[1] = str(index) # Re-index # locally within the sorted table
            new_line = " | ".join(cols[1:-1])
            new_table_rows.append(f"| {new_line} |")
            
        # Reassemble the session table block
        sorted_table = f"\n{header}\n{separator}\n" + "\n".join(new_table_rows) + "\n\n"
        new_section_content += session_header + sorted_table
        
    # Reassemble the entire file content
    new_content = before_section + section_start_str + new_section_content + "### 12.4" + after_section
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Successfully sorted and reindexed all session tables by Jam!")

if __name__ == "__main__":
    sort_tables_by_hour()
