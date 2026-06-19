import os
import csv
from datetime import datetime

def get_session(time_str):
    # Parse hour to estimate session
    # Sydney: 22:00 - 06:00 GMT (roughly)
    # Asia (Tokyo): 00:00 - 08:00 GMT
    # London: 08:00 - 16:00 GMT
    # New York: 13:00 - 21:00 GMT
    try:
        dt = datetime.strptime(time_str, "%Y.%m.%d %H:%M:%S")
    except Exception:
        dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
        
    h = dt.hour
    
    # Let's align with the session naming in the MQL5 code:
    # Asia (00-08 GMT), London (08-16 GMT), NY (13-21 GMT)
    if 8 <= h < 12:
        return "London (London Open)"
    elif 12 <= h < 13:
        return "London"
    elif 13 <= h < 17:
        return "London_NewYork_Overlap"
    elif 17 <= h < 22:
        return "NewYork"
    elif 22 <= h or h < 1:
        return "Sydney"
    elif 1 <= h < 8:
        return "Asia / Sydney_Tokyo_Overlap"
    else:
        return "Unknown"

def analyze_periods(csv_path):
    print(f"Analyzing: {csv_path}")
    if not os.path.exists(csv_path):
        print("File not found")
        return
        
    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader) # Skip title or metadata
        header2 = next(reader) # Columns
        
        events = []
        for row in reader:
            if not row or len(row) < 5:
                continue
            type_val = row[0]
            direction = row[1]
            price = row[2]
            time_str = row[3]
            tf = row[4]
            status = row[5] if len(row) > 5 else ""
            
            if type_val in ["CHoCH", "BoS"]:
                try:
                    dt = datetime.strptime(time_str, "%Y.%m.%d %H:%M:%S")
                    events.append((dt, type_val, direction, price, time_str, tf, status))
                except Exception:
                    try:
                        dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
                        events.append((dt, type_val, direction, price, time_str, tf, status))
                    except Exception:
                        continue
                        
        # Sort by time
        events.sort(key=lambda x: x[0])
        
        print("\n--- Period 1: 2024.05.28 to 2024.06.01 ---")
        for ev in events:
            dt, type_val, direction, price, time_str, tf, status = ev
            if datetime(2024, 5, 28) <= dt <= datetime(2024, 6, 1):
                session = get_session(time_str)
                print(f"{time_str} | {type_val} {direction} | Price: {price} | TF: {tf} | Session: {session}")
                
        print("\n--- Period 2: 2024.08.18 to 2024.08.29 ---")
        for ev in events:
            dt, type_val, direction, price, time_str, tf, status = ev
            if datetime(2024, 8, 18) <= dt <= datetime(2024, 8, 29):
                session = get_session(time_str)
                print(f"{time_str} | {type_val} {direction} | Price: {price} | TF: {tf} | Session: {session}")

def main():
    csv_path = r"D:\Project\Project MT5\backtest_v11\LLHHBOSData_XAUUSD_2024-12-30.csv"
    analyze_periods(csv_path)

if __name__ == "__main__":
    main()
