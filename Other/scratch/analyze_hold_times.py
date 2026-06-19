import os
import csv
from datetime import datetime, timedelta

def calculate_trading_days(start_time, end_time):
    if start_time >= end_time:
        return 0
        
    # Normalize to midnight
    start_date = start_time.date()
    end_date = end_time.date()
    
    days = 0
    t = start_date
    while t < end_date:
        t += timedelta(days=1)
        if t.weekday() < 5:  # Monday to Friday (0 to 4)
            days += 1
    return days

def analyze_csv(file_path):
    results = []
    if not os.path.exists(file_path):
        return results
        
    with open(file_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('Status') != 'EXECUTED':
                continue
                
            entry_time_str = row.get('EntryTime')
            exit_time_str = row.get('ExitTime')
            
            if not entry_time_str or not exit_time_str:
                continue
                
            # Parse times
            # Expected format: "2024.12.30 15:45:00" or similar
            try:
                entry_time = datetime.strptime(entry_time_str, "%Y.%m.%d %H:%M:%S")
                exit_time = datetime.strptime(exit_time_str, "%Y.%m.%d %H:%M:%S")
            except Exception as e:
                try:
                    entry_time = datetime.strptime(entry_time_str, "%Y-%m-%d %H:%M:%S")
                    exit_time = datetime.strptime(exit_time_str, "%Y-%m-%d %H:%M:%S")
                except Exception:
                    continue
            
            trading_days = calculate_trading_days(entry_time, exit_time)
            calendar_days = (exit_time - entry_time).days
            
            if 8 <= trading_days <= 10:
                results.append({
                    'Ticket': row.get('Ticket'),
                    'Type': row.get('Type'),
                    'EntryTime': entry_time_str,
                    'ExitTime': exit_time_str,
                    'TradingDays': trading_days,
                    'CalendarDays': calendar_days,
                    'Profit': row.get('Profit'),
                    'NetProfit': row.get('Net_Profit'),
                    'ExitType': row.get('ExitType', 'N/A')
                })
    return results

def main():
    base_dir = r"D:\Project\Project MT5"
    versions = ["backtest_v7", "backtest_v8", "backtest_v9", "backtest_v10", "backtest_v11"]
    
    print("=== ANALISIS TRADE HOLD TIME 8-10 HARI TRADING (TAHUN 2024) ===")
    
    for version in versions:
        version_dir = os.path.join(base_dir, version)
        if not os.path.isdir(version_dir):
            continue
            
        print(f"\nChecking directory: {version}")
        
        # Look for 2024 backtest files
        for file_name in os.listdir(version_dir):
            if file_name.startswith("Backtest_Results_") and "2024" in file_name and file_name.endswith(".csv"):
                file_path = os.path.join(version_dir, file_name)
                trades = analyze_csv(file_path)
                
                if trades:
                    print(f"  File: {file_name} -> Found {len(trades)} matches:")
                    for t in trades:
                        print(f"    - Ticket: {t['Ticket']} | Type: {t['Type']} | Net Profit: ${t['NetProfit']}")
                        print(f"      Entry: {t['EntryTime']} -> Exit: {t['ExitTime']}")
                        print(f"      Hold: {t['TradingDays']} Trading Days ({t['CalendarDays']} Calendar Days) | Exit Type: {t['ExitType']}")
                else:
                    print(f"  File: {file_name} -> No trades held for 8-10 trading days.")

if __name__ == "__main__":
    main()
