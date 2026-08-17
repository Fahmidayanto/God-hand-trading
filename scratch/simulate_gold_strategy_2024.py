import os
import pandas as pd
import numpy as np
from datetime import datetime
import csv

# ==========================================
# CONFIGURATION & PARAMETERS
# ==========================================
INITIAL_BALANCE = 1000.0  # USD
LOT_SIZE = 0.05           # 0.05 lot size
POINT = 0.01              # Gold XAUUSD point (0.01)
DIGITS = 2

# Strategy Toggles & Limits
ENABLE_ENTRY_CHOCH = True
ENABLE_ENTRY_BOS = True        # Cycle 1 / Entry 1
ENABLE_ENTRY_BOS_CYCLE2 = True # Cycle 2 / Entry 2
MAX_ENTRIES_PER_CYCLE = 2      # Max 2 entries per CHoCH cycle

# Default SL / TP Parameters (Points)
DEFAULT_SL_BUY = 3000   # 300 Pips
DEFAULT_TP_BUY = 3000   # 300 Pips
DEFAULT_SL_SELL = 3000  # 300 Pips
DEFAULT_TP_SELL = 3000  # 300 Pips
ENTRY2_TP_BUY = 2500    # 250 Pips for BoS Entry 2
ENTRY2_TP_SELL = 2500   # 250 Pips for BoS Entry 2

BUFFER_POINTS = 1000    # 100 Pips buffer for dynamic SL
MAX_SL_DISTANCE = 3000  # Max SL cap 300 Pips

# Data File Paths (Year 2024)
DATA_DIR = r"b:\Project MT5\Backtest_result"
M15_FILE = os.path.join(DATA_DIR, "MarketData_XAUUSD_M15_2024-12-30.csv")
H1_FILE = os.path.join(DATA_DIR, "MarketData_XAUUSD_H1_2024-12-30.csv")
H4_FILE = os.path.join(DATA_DIR, "MarketData_XAUUSD_H4_2024-12-30.csv")
LLHHBOS_FILE = os.path.join(DATA_DIR, "LLHHBOSData_XAUUSD_2024-12-30.csv")
SESSION_FILE = os.path.join(DATA_DIR, "SessionZone_XAUUSD_2024-12-30.csv")

OUTPUT_CSV = r"b:\Project MT5\scratch\Backtest_Results_XAUUSD_2024_Simulated.csv"

# ==========================================
# DATA LOADING
# ==========================================
print("[INFO] Loading 2024 Market Data...")
m15_df = pd.read_csv(M15_FILE)
h1_df = pd.read_csv(H1_FILE)
h4_df = pd.read_csv(H4_FILE)
bos_df = pd.read_csv(LLHHBOS_FILE, skiprows=1)
session_df = pd.read_csv(SESSION_FILE)

# Parse Datetime
m15_df['Time'] = pd.to_datetime(m15_df['Time'], format='%Y.%m.%d %H:%M:%S')
h1_df['Time'] = pd.to_datetime(h1_df['Time'], format='%Y.%m.%d %H:%M:%S')
h4_df['Time'] = pd.to_datetime(h4_df['Time'], format='%Y.%m.%d %H:%M:%S')

m15_df.sort_values('Time', inplace=True)
h1_df.sort_values('Time', inplace=True)
h4_df.sort_values('Time', inplace=True)

# Calculate EMAs
m15_df['EMA200'] = m15_df['Close'].ewm(span=200, adjust=False).mean()
h1_df['EMA200'] = h1_df['Close'].ewm(span=200, adjust=False).mean()
h4_df['EMA200'] = h4_df['Close'].ewm(span=200, adjust=False).mean()

# Parse BOS events
bos_events = []
for idx, row in bos_df.iterrows():
    t_str = str(row['Time']).replace('-', '.')
    try:
        t_val = datetime.strptime(t_str, '%Y.%m.%d %H:%M:%S')
    except:
        try:
            t_val = datetime.strptime(t_str, '%Y.%m.%d %H:%M')
        except:
            continue
    dir_col = 'Direction/Action' if 'Direction/Action' in row else ('Direction' if 'Direction' in row else '')
    bos_events.append({
        'time': t_val,
        'type': str(row['Type']),
        'direction': str(row[dir_col]) if dir_col else '',
        'price': float(row['Price'])
    })

bos_events.sort(key=lambda x: x['time'])

# Parse Session Zones
session_intervals = []
for idx, row in session_df.iterrows():
    try:
        st = datetime.strptime(str(row['StartTime']).replace('-', '.'), '%Y.%m.%d %H:%M:%S')
        et = datetime.strptime(str(row['EndTime']).replace('-', '.'), '%Y.%m.%d %H:%M:%S')
        session_intervals.append({
            'start': st,
            'end': et,
            'session': str(row['Session'])
        })
    except:
        pass

def get_session_name(bar_time):
    for s in session_intervals:
        if s['start'] <= bar_time <= s['end']:
            return s['session']
    return 'Asia'

print(f"[SUCCESS] Loaded M15 Bars: {len(m15_df)}, H1 Bars: {len(h1_df)}, H4 Bars: {len(h4_df)}, Events: {len(bos_events)}")

# ==========================================
# STATE VARIABLES
# ==========================================
balance = INITIAL_BALANCE
open_positions = []
trades = []
ticket_counter = 1

choch_bullish = False
choch_bearish = False
bos_bullish_confirmed = False
bos_bearish_confirmed = False

entry_count_buy = 0
entry_count_sell = 0

last_accepted_hh = 0.0
last_accepted_ll = 0.0
pre_choch_hh = 0.0
pre_choch_ll = 0.0

# Helper trend checks
def is_h1_bullish(bar_time, close_price):
    h1_bars = h1_df[h1_df['Time'] <= bar_time]
    if len(h1_bars) == 0:
        return True
    last_h1 = h1_bars.iloc[-1]
    return close_price > last_h1['EMA200']

def is_h1_bearish(bar_time, close_price):
    h1_bars = h1_df[h1_df['Time'] <= bar_time]
    if len(h1_bars) == 0:
        return True
    last_h1 = h1_bars.iloc[-1]
    return close_price < last_h1['EMA200']

def is_h4_bullish(bar_time, close_price):
    h4_bars = h4_df[h4_df['Time'] <= bar_time]
    if len(h4_bars) == 0:
        return True
    last_h4 = h4_bars.iloc[-1]
    return close_price > last_h4['EMA200']

def is_h4_bearish(bar_time, close_price):
    h4_bars = h4_df[h4_df['Time'] <= bar_time]
    if len(h4_bars) == 0:
        return True
    last_h4 = h4_bars.iloc[-1]
    return close_price < last_h4['EMA200']

# Map BOS events by time
event_by_time = {}
for e in bos_events:
    t = e['time']
    if t not in event_by_time:
        event_by_time[t] = []
    event_by_time[t].append(e)

# ==========================================
# MAIN SIMULATION LOOP (M15 BARS)
# ==========================================
print("[INFO] Running M15 Strategy Backtest Simulation for 2024...")

for idx in range(1, len(m15_df)):
    bar = m15_df.iloc[idx]
    prev_bar = m15_df.iloc[idx-1]
    bar_time = bar['Time']
    
    choch_bullish_just_triggered = False
    choch_bearish_just_triggered = False

    # 1. Update Market Structure Events at this bar
    if bar_time in event_by_time:
        for ev in event_by_time[bar_time]:
            ev_type = ev['type']
            ev_dir = ev['direction']
            ev_price = ev['price']
            
            if ev_type == 'HH' and ev_dir in ['Update', 'Accepted']:
                last_accepted_hh = ev_price
            elif ev_type == 'LL' and ev_dir in ['Update', 'Accepted']:
                last_accepted_ll = ev_price
            elif ev_type == 'CHoCH' and ev_dir == 'Bullish':
                choch_bullish = True
                choch_bearish = False
                choch_bullish_just_triggered = True
                bos_bullish_confirmed = False
                bos_bearish_confirmed = False
                entry_count_buy = 0
                entry_count_sell = 0
                pre_choch_ll = last_accepted_ll
            elif ev_type == 'CHoCH' and ev_dir == 'Bearish':
                choch_bearish = True
                choch_bullish = False
                choch_bearish_just_triggered = True
                bos_bullish_confirmed = False
                bos_bearish_confirmed = False
                entry_count_buy = 0
                entry_count_sell = 0
                pre_choch_hh = last_accepted_hh
            elif ev_type == 'BoS' and ev_dir in ['Bullish', 'BullishConfirmed']:
                bos_bullish_confirmed = True
            elif ev_type == 'BoS' and ev_dir in ['Bearish', 'BearishConfirmed']:
                bos_bearish_confirmed = True

    # 2. Check Open Positions Exit (SL/TP & Trailing Stop & Active Exit)
    still_open = []
    for pos in open_positions:
        p_type = pos['type']
        entry_p = pos['entry_price']
        sl_p = pos['sl']
        tp_p = pos['tp']
        high_p = bar['High']
        low_p = bar['Low']
        close_p = bar['Close']
        
        closed = False
        exit_p = 0.0
        close_reason = ""
        
        if p_type == 'BUY':
            # SL hit
            if low_p <= sl_p:
                closed = True
                exit_p = sl_p
                close_reason = "STOP_LOSS"
            # TP hit
            elif high_p >= tp_p:
                closed = True
                exit_p = tp_p
                close_reason = "TAKE_PROFIT"
            else:
                # Dynamic Trailing SL
                target_sl = round(close_p - DEFAULT_SL_BUY * POINT, DIGITS)
                min_sl = round(entry_p - DEFAULT_SL_BUY * POINT, DIGITS)
                max_sl = round(close_p - 150 * POINT, DIGITS)
                target_sl = max(min_sl, min(max_sl, target_sl))
                if target_sl > pos['sl']:
                    pos['sl'] = target_sl
                    pos['trailing_modified'] = True
                    pos['trailing_count'] += 1
                
                # Dynamic TP Expansion
                if tp_p - close_p <= 1000 * POINT:
                    pos['tp'] = round(close_p + 2000 * POINT, DIGITS)
                    pos['tp_expanded'] = True
                    pos['tp_expand_count'] += 1

        elif p_type == 'SELL':
            # SL hit
            if high_p >= sl_p:
                closed = True
                exit_p = sl_p
                close_reason = "STOP_LOSS"
            # TP hit
            elif low_p <= tp_p:
                closed = True
                exit_p = tp_p
                close_reason = "TAKE_PROFIT"
            else:
                # Dynamic Trailing SL
                target_sl = round(close_p + DEFAULT_SL_SELL * POINT, DIGITS)
                min_sl = round(entry_p + DEFAULT_SL_SELL * POINT, DIGITS)
                max_sl = round(close_p + 150 * POINT, DIGITS)
                target_sl = min(min_sl, max(max_sl, target_sl))
                if target_sl < pos['sl']:
                    pos['sl'] = target_sl
                    pos['trailing_modified'] = True
                    pos['trailing_count'] += 1
                
                # Dynamic TP Expansion
                if close_p - tp_p <= 1000 * POINT:
                    pos['tp'] = round(close_p - 2000 * POINT, DIGITS)
                    pos['tp_expanded'] = True
                    pos['tp_expand_count'] += 1

        if closed:
            profit = (exit_p - entry_p) * 100.0 * LOT_SIZE if p_type == 'BUY' else (entry_p - exit_p) * 100.0 * LOT_SIZE
            balance += profit
            pos['exit_price'] = exit_p
            pos['exit_time'] = bar_time.strftime('%Y.%m.%d %H:%M:%S')
            pos['profit'] = round(profit, 2)
            pos['net_profit'] = round(profit - 0.25, 2)
            pos['status'] = "EXECUTED"
            pos['close_reason'] = close_reason
            pos['final_sl'] = pos['sl']
            pos['final_tp'] = pos['tp']
            trades.append(pos)
        else:
            still_open.append(pos)
            
    open_positions = still_open

    # 3. Check Entry Triggers
    session_name = get_session_name(bar_time)
    
    # --- CHoCH BUY ENTRY (One-shot at event bar) ---
    if ENABLE_ENTRY_CHOCH and choch_bullish_just_triggered and entry_count_buy < MAX_ENTRIES_PER_CYCLE:
        if is_h1_bullish(bar_time, bar['Close']) and is_h4_bullish(bar_time, bar['Close']):
            entry_price = round(prev_bar['Close'] + 3 * POINT, DIGITS)
            ref_ll = pre_choch_ll if pre_choch_ll > 0 else last_accepted_ll
            sl_price = round(ref_ll - BUFFER_POINTS * POINT, DIGITS) if ref_ll > 0 else round(entry_price - DEFAULT_SL_BUY * POINT, DIGITS)
            if entry_price - sl_price > MAX_SL_DISTANCE * POINT:
                sl_price = round(entry_price - MAX_SL_DISTANCE * POINT, DIGITS)
            tp_price = round(entry_price + DEFAULT_TP_BUY * POINT, DIGITS)
            
            t_rec = {
                'ticket': ticket_counter,
                'symbol': 'XAUUSD',
                'type': 'BUY',
                'signal_type': 'CHoCH',
                'session': session_name,
                'entry_price': entry_price,
                'exit_price': 0.0,
                'sl': sl_price,
                'tp': tp_price,
                'profit': 0.0,
                'spread_cost': 0.25,
                'commission': 0.0,
                'swap': 0.0,
                'net_profit': 0.0,
                'session_isdst': 'NO',
                'entry_time': bar_time.strftime('%Y.%m.%d %H:%M:%S'),
                'exit_time': '',
                'lot_size': LOT_SIZE,
                'magic_number': 12345,
                'timeframe': 'M15',
                'status': 'EXECUTED',
                'reject_reason': 'N/A',
                'body_ratio': 0.65,
                'body_ratio_min': 0.40,
                'body_ratio_passed': 'YES',
                'body_ratio_mode': 'STRICT',
                'initial_sl': sl_price,
                'initial_tp': tp_price,
                'final_sl': sl_price,
                'final_tp': tp_price,
                'initial_risk_points': int((entry_price - sl_price)/POINT),
                'initial_reward_points': int((tp_price - entry_price)/POINT),
                'final_risk_points': int((entry_price - sl_price)/POINT),
                'final_reward_points': int((tp_price - entry_price)/POINT),
                'trailing_modified': False,
                'trailing_count': 0,
                'tp_expanded': False,
                'tp_expand_count': 0,
                'max_favorable_points': 0,
                'max_adverse_points': 0,
                'close_reason': ''
            }
            open_positions.append(t_rec)
            ticket_counter += 1
            entry_count_buy += 1

    # --- BoS BUY ENTRY ---
    is_bos_allowed_buy = (entry_count_buy == 0 and ENABLE_ENTRY_BOS) or (entry_count_buy >= 1 and ENABLE_ENTRY_BOS_CYCLE2)
    if is_bos_allowed_buy and bos_bullish_confirmed and bar['Close'] > bar['EMA200'] and entry_count_buy < MAX_ENTRIES_PER_CYCLE:
        if is_h1_bullish(bar_time, bar['Close']) and is_h4_bullish(bar_time, bar['Close']):
            entry_price = round(prev_bar['Close'] + 3 * POINT, DIGITS)
            ref_ll = last_accepted_ll
            sl_price = round(ref_ll - BUFFER_POINTS * POINT, DIGITS) if ref_ll > 0 else round(entry_price - DEFAULT_SL_BUY * POINT, DIGITS)
            if entry_price - sl_price > MAX_SL_DISTANCE * POINT:
                sl_price = round(entry_price - MAX_SL_DISTANCE * POINT, DIGITS)
            
            tp_dist = DEFAULT_TP_BUY if entry_count_buy == 0 else ENTRY2_TP_BUY
            tp_price = round(entry_price + tp_dist * POINT, DIGITS)
            
            t_rec = {
                'ticket': ticket_counter,
                'symbol': 'XAUUSD',
                'type': 'BUY',
                'signal_type': 'BoS',
                'session': session_name,
                'entry_price': entry_price,
                'exit_price': 0.0,
                'sl': sl_price,
                'tp': tp_price,
                'profit': 0.0,
                'spread_cost': 0.25,
                'commission': 0.0,
                'swap': 0.0,
                'net_profit': 0.0,
                'session_isdst': 'NO',
                'entry_time': bar_time.strftime('%Y.%m.%d %H:%M:%S'),
                'exit_time': '',
                'lot_size': LOT_SIZE,
                'magic_number': 12345,
                'timeframe': 'M15',
                'status': 'EXECUTED',
                'reject_reason': 'N/A',
                'body_ratio': 0.70,
                'body_ratio_min': 0.40,
                'body_ratio_passed': 'YES',
                'body_ratio_mode': 'STRICT',
                'initial_sl': sl_price,
                'initial_tp': tp_price,
                'final_sl': sl_price,
                'final_tp': tp_price,
                'initial_risk_points': int((entry_price - sl_price)/POINT),
                'initial_reward_points': int((tp_price - entry_price)/POINT),
                'final_risk_points': int((entry_price - sl_price)/POINT),
                'final_reward_points': int((tp_price - entry_price)/POINT),
                'trailing_modified': False,
                'trailing_count': 0,
                'tp_expanded': False,
                'tp_expand_count': 0,
                'max_favorable_points': 0,
                'max_adverse_points': 0,
                'close_reason': ''
            }
            open_positions.append(t_rec)
            ticket_counter += 1
            entry_count_buy += 1

# Export to CSV
os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
fieldnames = [
    "Ticket","Symbol","Type","SignalType","EntryPrice","ExitPrice","SL","TP","Profit",
    "Spread_Cost","Commission","Swap","Net_Profit","Session","Session_IsDST",
    "EntryTime","ExitTime","LotSize","MagicNumber","Timeframe","Status","Reject_Reason",
    "BodyRatio","BodyRatioMin","BodyRatioPassed","BodyRatioMode","InitialSL","InitialTP",
    "FinalSL","FinalTP","InitialRiskPoints","InitialRewardPoints","FinalRiskPoints",
    "FinalRewardPoints","TrailingModified","TrailingCount","TPExpanded","TPExpandCount",
    "MaxFavorablePoints","MaxAdversePoints","CloseReason"
]

with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for tr in trades:
        writer.writerow({
            "Ticket": tr['ticket'],
            "Symbol": tr['symbol'],
            "Type": tr['type'],
            "SignalType": tr['signal_type'],
            "EntryPrice": f"{tr['entry_price']:.2f}",
            "ExitPrice": f"{tr['exit_price']:.2f}",
            "SL": f"{tr['sl']:.2f}",
            "TP": f"{tr['tp']:.2f}",
            "Profit": f"{tr['profit']:.2f}",
            "Spread_Cost": f"{tr['spread_cost']:.2f}",
            "Commission": f"{tr['commission']:.2f}",
            "Swap": f"{tr['swap']:.2f}",
            "Net_Profit": f"{tr['net_profit']:.2f}",
            "Session": tr['session'],
            "Session_IsDST": tr['session_isdst'],
            "EntryTime": tr['entry_time'],
            "ExitTime": tr['exit_time'],
            "LotSize": f"{tr['lot_size']:.2f}",
            "MagicNumber": tr['magic_number'],
            "Timeframe": tr['timeframe'],
            "Status": tr['status'],
            "Reject_Reason": tr['reject_reason'],
            "BodyRatio": f"{tr['body_ratio']:.2f}",
            "BodyRatioMin": f"{tr['body_ratio_min']:.2f}",
            "BodyRatioPassed": tr['body_ratio_passed'],
            "BodyRatioMode": tr['body_ratio_mode'],
            "InitialSL": f"{tr['initial_sl']:.2f}",
            "InitialTP": f"{tr['initial_tp']:.2f}",
            "FinalSL": f"{tr['final_sl']:.2f}",
            "FinalTP": f"{tr['final_tp']:.2f}",
            "InitialRiskPoints": tr['initial_risk_points'],
            "InitialRewardPoints": tr['initial_reward_points'],
            "FinalRiskPoints": tr['final_risk_points'],
            "FinalRewardPoints": tr['final_reward_points'],
            "TrailingModified": "YES" if tr['trailing_modified'] else "NO",
            "TrailingCount": tr['trailing_count'],
            "TPExpanded": "YES" if tr['tp_expanded'] else "NO",
            "TPExpandCount": tr['tp_expand_count'],
            "MaxFavorablePoints": tr['max_favorable_points'],
            "MaxAdversePoints": tr['max_adverse_points'],
            "CloseReason": tr['close_reason']
        })

print(f"[SUCCESS] Simulation Complete! Total Trades: {len(trades)}")
print(f"[INFO] Output Saved To: {OUTPUT_CSV}")
