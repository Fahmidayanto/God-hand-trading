import pandas as pd
import os
from datetime import datetime

# Load all CSV files
base_path = r"d:\Project\Project MT5"
v7_df = pd.read_csv(os.path.join(base_path, "backtest_v7", "Backtest_Results_XAUUSD_2023-12-29.csv"))
v8_df = pd.read_csv(os.path.join(base_path, "backtest_v8", "Backtest_Results_XAUUSD_2023-12-29.csv"))
v9_df = pd.read_csv(os.path.join(base_path, "backtest_v9", "Backtest_Results_XAUUSD_2023-12-29.csv"))
v10_df = pd.read_csv(os.path.join(base_path, "backtest_v10", "Backtest_Results_XAUUSD_2023-12-29.csv"))

# Create unified signal dictionary
all_signals = {}

def process_df(df, version):
    """Process dataframe and add to all_signals dictionary"""
    for idx, row in df.iterrows():
        entry_time = row['EntryTime']
        entry_price = row['EntryPrice']
        trade_type = row['Type']
        
        # Create unique key
        key = f"{entry_time}_{trade_type}_{entry_price}"
        
        if key not in all_signals:
            all_signals[key] = {
                'EntryTime': entry_time,
                'Type': trade_type,
                'EntryPrice': entry_price,
                'ExitPrice': row['ExitPrice'],
                'SL': row['SL'],
                'TP': row['TP'],
                'Session': row['Session'],
                'Status': row['Status'],
                'Net_Profit': row['Net_Profit'],
                'Swap': row['Swap'],
                'ExitTime': row['ExitTime'],
                'Reject_Reason': row['Reject_Reason'],
                'v7': None,
                'v8': None,
                'v9': None,
                'v10': None
            }
        
        # Add version specific data
        all_signals[key][f'v{version}'] = {
            'Status': row['Status'],
            'Net_Profit': row['Net_Profit'],
            'Reject_Reason': row['Reject_Reason']
        }

# Process all versions
process_df(v7_df, 7)
process_df(v8_df, 8)
process_df(v9_df, 9)
process_df(v10_df, 10)

# Sort signals by EntryTime
sorted_signals = sorted(all_signals.items(), key=lambda x: x[1]['EntryTime'])

# Generate markdown table rows
print("| # | Entry Time | Type | Entry | Session | V7 | V8 | V9 | V10 | Profit | Catatan | Analisa |")
print("|---|-----------|------|-------|---------|----|----|----|-----|--------|---------|---------|")

signal_num = 1
for key, signal in sorted_signals:
    entry_time = signal['EntryTime']
    trade_type = signal['Type']
    entry_price = signal['EntryPrice']
    session = signal['Session']
    
    # Determine status for each version
    v7_status = "—"
    v8_status = "—"
    v9_status = "—"
    v10_status = "—"
    profit = "—"
    catatan = ""
    
    if signal['v7']:
        if signal['v7']['Status'] == 'EXECUTED':
            net = signal['v7']['Net_Profit']
            v7_status = "✅" if net > 0 else "❌"
            profit = f"${net:+.2f}" if profit == "—" else profit
        elif signal['v7']['Status'] == 'REJECTED':
            v7_status = f"🚫 {signal['v7']['Reject_Reason'].replace(' Filter', '')}"
    
    if signal['v8']:
        if signal['v8']['Status'] == 'EXECUTED':
            net = signal['v8']['Net_Profit']
            v8_status = "✅" if net > 0 else "❌"
            profit = f"${net:+.2f}" if profit == "—" else profit
        elif signal['v8']['Status'] == 'REJECTED':
            reason = signal['v8']['Reject_Reason'].replace(' Filter', '').replace('H1 EMA200', 'H1').replace('Body Ratio', 'BR')
            v8_status = f"🚫 {reason}"
    
    if signal['v9']:
        if signal['v9']['Status'] == 'EXECUTED':
            net = signal['v9']['Net_Profit']
            v9_status = "✅" if net > 0 else "❌"
            profit = f"${net:+.2f}" if profit == "—" else profit
        elif signal['v9']['Status'] == 'REJECTED':
            reason = signal['v9']['Reject_Reason'].replace(' Filter', '').replace('H1 EMA200', 'H1').replace('H4 EMA', 'H4')
            v9_status = f"🚫 {reason}"
    
    if signal['v10']:
        if signal['v10']['Status'] == 'EXECUTED':
            net = signal['v10']['Net_Profit']
            v10_status = "✅" if net > 0 else "❌"
            profit = f"${net:+.2f}" if profit == "—" else profit
        elif signal['v10']['Status'] == 'REJECTED':
            reason = signal['v10']['Reject_Reason'].replace(' Filter', '').replace('H1 EMA200', 'H1').replace('H4 EMA', 'H4').replace('Body Ratio', 'BR')
            v10_status = f"🚫 {reason}"
    
    # Generate catatan based on pattern
    executed = []
    if signal['v7'] and signal['v7']['Status'] == 'EXECUTED':
        executed.append('V7')
    if signal['v8'] and signal['v8']['Status'] == 'EXECUTED':
        executed.append('V8')
    if signal['v9'] and signal['v9']['Status'] == 'EXECUTED':
        executed.append('V9')
    if signal['v10'] and signal['v10']['Status'] == 'EXECUTED':
        executed.append('V10')
    
    if len(executed) == 4:
        if profit and profit != "—" and float(profit.replace('$', '').replace('+', '')) > 0:
            catatan = "WIN semua"
        else:
            catatan = "LOSS semua"
    elif len(executed) == 0:
        catatan = "REJECTED semua"
    else:
        catatan = f"{'+'.join(executed)}"
    
    # Generate basic analysis placeholder
    analisa = f"**PLACEHOLDER**: {trade_type} ${entry_price} di {session}"
    
    print(f"| {signal_num} | {entry_time} | {trade_type} | {entry_price} | {session} | {v7_status} | {v8_status} | {v9_status} | {v10_status} | {profit} | {catatan} | {analisa} |")
    signal_num += 1

print(f"\n\nTotal Signals: {len(sorted_signals)}")

# Generate statistics
print("\n### Statistics Summary:")
for version in [7, 8, 9, 10]:
    executed = sum(1 for s in all_signals.values() if s[f'v{version}'] and s[f'v{version}']['Status'] == 'EXECUTED')
    rejected = sum(1 for s in all_signals.values() if s[f'v{version}'] and s[f'v{version}']['Status'] == 'REJECTED')
    wins = sum(1 for s in all_signals.values() if s[f'v{version}'] and s[f'v{version}']['Status'] == 'EXECUTED' and s[f'v{version}']['Net_Profit'] > 0)
    losses = sum(1 for s in all_signals.values() if s[f'v{version}'] and s[f'v{version}']['Status'] == 'EXECUTED' and s[f'v{version}']['Net_Profit'] < 0)
    total_profit = sum(s[f'v{version}']['Net_Profit'] for s in all_signals.values() if s[f'v{version}'] and s[f'v{version}']['Status'] == 'EXECUTED')
    win_rate = (wins / executed * 100) if executed > 0 else 0
    
    print(f"\nV{version}:")
    print(f"  Total Signals: {executed + rejected}")
    print(f"  Executed: {executed}")
    print(f"  Rejected: {rejected}")
    print(f"  Wins: {wins}")
    print(f"  Losses: {losses}")
    print(f"  Win Rate: {win_rate:.2f}%")
    print(f"  Total Net Profit: ${total_profit:.2f}")
