"""
Focused High-Performance Target Optimizer for 2019 XAUUSD Replay Trades.
Targets 1000++ Net PnL (Saldo 2000++ USD) across ~61,440 high-probability combinations.
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime
import itertools
import time
from multiprocessing import Pool, cpu_count

BASE_DIR = r"B:\Project MT5\Backtest_result"
CSV_TRADES = os.path.join(BASE_DIR, "Backtest_Results_XAUUSD_2019-12-30.csv")
CSV_M15 = os.path.join(BASE_DIR, "MarketData_XAUUSD_M15_2019-12-30.csv")
CSV_BOS = os.path.join(BASE_DIR, "LLHHBOSData_XAUUSD_2019-12-30.csv")

def parse_time(ts_str):
    for fmt in ("%Y.%m.%d %H:%M:%S", "%Y.%m.%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(str(ts_str).strip(), fmt)
        except Exception:
            pass
    return None

def load_and_preprocess():
    print("[INFO] Loading datasets from Backtest_result...", flush=True)
    df_m15 = pd.read_csv(CSV_M15)
    df_m15['dt'] = df_m15['Time'].apply(parse_time)
    df_m15 = df_m15.dropna(subset=['dt']).sort_values('dt').reset_index(drop=True)
    df_m15['epoch'] = df_m15['dt'].apply(lambda x: int(x.timestamp()))
    
    m15_epochs = df_m15['epoch'].values
    m15_opens = df_m15['Open'].values
    m15_highs = df_m15['High'].values
    m15_lows = df_m15['Low'].values
    m15_closes = df_m15['Close'].values
    n_candles = len(m15_epochs)
    
    df_bos = pd.read_csv(CSV_BOS, skiprows=1)
    df_bos['dt'] = df_bos['Time'].apply(parse_time)
    df_bos = df_bos.dropna(subset=['dt']).sort_values('dt').reset_index(drop=True)
    df_bos['epoch'] = df_bos['dt'].apply(lambda x: int(x.timestamp()))
    
    dir_col = 'Direction/Action' if 'Direction/Action' in df_bos.columns else ('Direction' if 'Direction' in df_bos.columns else 'Type')
    structures = []
    for _, row in df_bos.iterrows():
        structures.append({
            'epoch': row['epoch'],
            'type': str(row['Type']).strip().upper(),
            'price': float(row['Price'])
        })
    structures.sort(key=lambda x: x['epoch'])
    
    df_trades = pd.read_csv(CSV_TRADES)
    executed = df_trades[df_trades['Status'] == 'EXECUTED'].copy()
    executed['entry_dt'] = executed['EntryTime'].apply(parse_time)
    executed = executed.dropna(subset=['entry_dt']).sort_values('entry_dt').reset_index(drop=True)
    executed['entry_epoch'] = executed['entry_dt'].apply(lambda x: int(x.timestamp()))
    
    prepared_trades = []
    for _, row in executed.iterrows():
        entry_epoch = int(row['entry_epoch'])
        entry_price = float(row['EntryPrice'])
        is_buy = (str(row['Type']).strip().upper() == 'BUY')
        actual_lot = float(row.get('LotSize', 0.05))
        spread_cost = float(row.get('Spread_Cost', 0.0))
        commission = float(row.get('Commission', 0.0))
        swap = float(row.get('Swap', 0.0))
        
        struct_sl = None
        if is_buy:
            for s in structures:
                if s['epoch'] < entry_epoch:
                    if 'LL' in s['type'] or 'LOW' in s['type']:
                        struct_sl = s['price']
                else:
                    break
        else:
            for s in structures:
                if s['epoch'] < entry_epoch:
                    if 'HH' in s['type'] or 'HIGH' in s['type']:
                        struct_sl = s['price']
                else:
                    break
                    
        start_idx = np.searchsorted(m15_epochs, entry_epoch, side='left')
        if start_idx >= n_candles:
            continue
            
        end_idx = min(n_candles, start_idx + 105)
        
        prepared_trades.append({
            'ticket': int(row['Ticket']),
            'is_buy': is_buy,
            'entry_price': entry_price,
            'entry_epoch': entry_epoch,
            'struct_sl': struct_sl,
            'actual_lot': actual_lot,
            'base_fees': (spread_cost + commission + abs(swap)),
            'c_epochs': m15_epochs[start_idx:end_idx].tolist(),
            'c_opens': m15_opens[start_idx:end_idx].tolist(),
            'c_highs': m15_highs[start_idx:end_idx].tolist(),
            'c_lows': m15_lows[start_idx:end_idx].tolist(),
            'c_closes': m15_closes[start_idx:end_idx].tolist(),
            'n_sub_candles': len(m15_epochs[start_idx:end_idx])
        })
        
    print(f"[INFO] Successfully preprocessed {len(prepared_trades)} active trades for target search.", flush=True)
    return prepared_trades

G_TRADES = []

def init_worker(trades):
    global G_TRADES
    G_TRADES = trades

def worker_evaluate_chunk(chunk):
    results = []
    trades = G_TRADES
    
    for item in chunk:
        b_ref, base_lot, is_compound, tr, i_tp, m_sl, buf, be_trig, pt_exit = item
        
        balance = 1000.0
        peak = balance
        max_dd_usd = 0.0
        max_dd_pct = 0.0
        
        pnl_list = []
        wins = 0
        total_gain = 0.0
        total_loss = 0.0
        
        for t in trades:
            entry_price = t['entry_price']
            entry_epoch = t['entry_epoch']
            is_buy = t['is_buy']
            
            if is_compound:
                current_base_lot = max(0.01, round((max(200.0, balance) / 1000.0) * base_lot, 2))
            else:
                current_base_lot = base_lot
                
            if b_ref > 0 and entry_price > 0:
                ratio = entry_price / b_ref
                trade_lot = max(0.01, round(current_base_lot / ratio, 2))
            else:
                ratio = 1.0
                trade_lot = current_base_lot
                
            eff_trailing = tr * ratio
            eff_initial_tp = i_tp * ratio
            eff_buffer = buf * ratio
            eff_min_sl = m_sl * ratio
            eff_max_sl = eff_trailing * 1.5
            eff_be_trigger = (be_trig * ratio) if be_trig > 0 else 0.0
            
            raw_struct = t['struct_sl']
            if is_buy:
                struct_sl = raw_struct if raw_struct is not None else (entry_price - eff_trailing)
                buffered_sl = struct_sl - eff_buffer
                sl_distance = max(eff_min_sl, min(eff_max_sl, abs(entry_price - buffered_sl)))
                current_sl = entry_price - sl_distance
                current_tp = (entry_price + eff_initial_tp) if eff_initial_tp > 0 else (entry_price + 30.0 * ratio)
            else:
                struct_sl = raw_struct if raw_struct is not None else (entry_price + eff_trailing)
                buffered_sl = struct_sl + eff_buffer
                sl_distance = max(eff_min_sl, min(eff_max_sl, abs(entry_price - buffered_sl)))
                current_sl = entry_price + sl_distance
                current_tp = (entry_price - eff_initial_tp) if eff_initial_tp > 0 else (entry_price - 30.0 * ratio)
                
            exit_price = None
            c_epochs = t['c_epochs']
            c_opens = t['c_opens']
            c_highs = t['c_highs']
            c_lows = t['c_lows']
            c_closes = t['c_closes']
            n_c = t['n_sub_candles']
            
            be_triggered = False
            
            for i in range(n_c):
                if (c_epochs[i] - entry_epoch) >= 86400:
                    exit_price = c_opens[i]
                    break
                    
                if pt_exit > 0:
                    if is_buy:
                        floating_gain = (c_highs[i] - entry_price) * trade_lot * 100.0
                        if floating_gain >= pt_exit:
                            exit_price = entry_price + (pt_exit / (trade_lot * 100.0))
                            break
                    else:
                        floating_gain = (entry_price - c_lows[i]) * trade_lot * 100.0
                        if floating_gain >= pt_exit:
                            exit_price = entry_price - (pt_exit / (trade_lot * 100.0))
                            break
                            
                if is_buy:
                    if c_lows[i] <= current_sl:
                        exit_price = current_sl
                        break
                    if current_tp is not None and c_highs[i] >= current_tp:
                        exit_price = current_tp
                        break
                    if eff_be_trigger > 0 and (c_highs[i] - entry_price) >= eff_be_trigger:
                        be_triggered = True
                    target_sl = c_closes[i] - eff_trailing
                    min_sl = entry_price - eff_trailing
                    max_sl = c_closes[i] - 1.50
                    new_sl = max(min_sl, min(max_sl, target_sl))
                    if be_triggered:
                        new_sl = max(new_sl, entry_price + 1.0 * ratio)
                    if new_sl > current_sl:
                        current_sl = new_sl
                else:
                    if c_highs[i] >= current_sl:
                        exit_price = current_sl
                        break
                    if current_tp is not None and c_lows[i] <= current_tp:
                        exit_price = current_tp
                        break
                    if eff_be_trigger > 0 and (entry_price - c_lows[i]) >= eff_be_trigger:
                        be_triggered = True
                    target_sl = c_closes[i] + eff_trailing
                    min_sl = entry_price + eff_trailing
                    max_sl = c_closes[i] + 1.50
                    new_sl = min(min_sl, max(max_sl, target_sl))
                    if be_triggered:
                        new_sl = min(new_sl, entry_price - 1.0 * ratio)
                    if new_sl < current_sl:
                        current_sl = new_sl
                        
            if exit_price is None:
                exit_price = c_closes[-1]
                
            if is_buy:
                gross_pnl = (exit_price - entry_price) * trade_lot * 100.0
            else:
                gross_pnl = (entry_price - exit_price) * trade_lot * 100.0
                
            lot_ratio = trade_lot / t['actual_lot'] if t['actual_lot'] > 0 else 1.0
            net_profit = gross_pnl - (t['base_fees'] * lot_ratio)
            
            pnl_list.append(net_profit)
            balance += net_profit
            
            if balance > peak:
                peak = balance
            dd_usd = peak - balance
            dd_pct = (dd_usd / peak) * 100.0 if peak > 0 else 0.0
            if dd_usd > max_dd_usd:
                max_dd_usd = dd_usd
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct
                
            if net_profit > 0:
                wins += 1
                total_gain += net_profit
            elif net_profit < 0:
                total_loss += abs(net_profit)
                
        total_trades = len(pnl_list)
        if total_trades == 0:
            continue
            
        total_net_pnl = balance - 1000.0
        win_rate = (wins / total_trades) * 100.0 if total_trades > 0 else 0.0
        profit_factor = (total_gain / total_loss) if total_loss > 0 else (999.0 if total_gain > 0 else 0.0)
        
        # Keep all results that made positive profit
        if total_net_pnl > 0:
            results.append({
                'base_ref': b_ref,
                'base_lot': base_lot,
                'is_compound': is_compound,
                'trailing_dist': tr,
                'initial_tp_dist': i_tp,
                'min_sl_dist': m_sl,
                'sl_safety_buffer': buf,
                'be_trigger': be_trig,
                'pt_exit': pt_exit,
                'total_trades': total_trades,
                'wins': wins,
                'losses': total_trades - wins,
                'win_rate': round(win_rate, 2),
                'total_net_pnl': round(total_net_pnl, 2),
                'final_balance': round(balance, 2),
                'max_dd_usd': round(max_dd_usd, 2),
                'max_dd_pct': round(max_dd_pct, 2),
                'profit_factor': round(profit_factor, 2)
            })
            
    return results

if __name__ == "__main__":
    start_t = time.time()
    trades = load_and_preprocess()
    
    # Focused parameter space
    base_refs = [1500.0, 2000.0, 2500.0, 3000.0, 4500.0]
    base_lots = [0.10, 0.15, 0.20, 0.25, 0.30]
    compounds = [False, True]
    trailings = [12.0, 15.0, 18.0, 20.0, 25.0]
    initial_tps = [20.0, 25.0, 30.0, 35.0, 40.0]
    min_sls = [10.0, 12.0]
    buffers = [2.0, 3.0]
    be_triggers = [0.0, 8.0, 10.0, 12.0]
    pt_exits = [0.0, 150.0, 250.0, 350.0]
    
    grid = list(itertools.product(base_refs, base_lots, compounds, trailings, initial_tps, min_sls, buffers, be_triggers, pt_exits))
    total_combos = len(grid)
    n_workers = min(12, cpu_count())
    chunk_size = 500
    
    chunks = [grid[i:i + chunk_size] for i in range(0, total_combos, chunk_size)]
    print(f"[INFO] Launching Focused Pool for {total_combos} combinations on {n_workers} CPU cores...", flush=True)
    
    all_results = []
    with Pool(processes=n_workers, initializer=init_worker, initargs=(trades,)) as pool:
        for chunk_res in pool.imap_unordered(worker_evaluate_chunk, chunks):
            all_results.extend(chunk_res)
            
    elapsed = time.time() - start_t
    print(f"[SUCCESS] Evaluated {total_combos} combinations in {elapsed:.2f} seconds!", flush=True)
    print(f"[INFO] Total profitable configurations found: {len(all_results)}", flush=True)
    
    df_res = pd.DataFrame(all_results)
    
    # Sort by Final Balance desc, Max DD pct asc
    df_sorted = df_res.sort_values(by=['final_balance', 'max_dd_pct'], ascending=[False, True]).reset_index(drop=True)
    
    print("\n" + "="*95, flush=True)
    print("TOP 10 BEST CONFIGURATIONS REACHING TARGET SALDO 1900 - 2000++ USD", flush=True)
    print("="*95, flush=True)
    
    top10 = df_sorted.head(10)
    for idx, row in top10.iterrows():
        comp_str = "Compounding (Reinvest)" if row['is_compound'] else "Fixed Lot"
        be_str = f"BE: {row['be_trigger']} USD" if row['be_trigger'] > 0 else "BE: OFF"
        pt_str = f"PT: {row['pt_exit']} USD" if row['pt_exit'] > 0 else "PT: OFF"
        print(f"Rank #{idx+1}: BaseRef={row['base_ref']} USD | Lot={row['base_lot']} ({comp_str}) | TP={row['initial_tp_dist']} | Trailing={row['trailing_dist']} | MinSL={row['min_sl_dist']} | {be_str} | {pt_str}", flush=True)
        print(f"         Net PnL: +{row['total_net_pnl']} USD | Final Balance: {row['final_balance']} USD | Max DD: {row['max_dd_pct']}% ({row['max_dd_usd']} USD) | PF: {row['profit_factor']} | WR: {row['win_rate']}% ({row['wins']}/{row['total_trades']})", flush=True)
        print("-" * 95, flush=True)
        
    df_sorted.to_csv(os.path.join(r"B:\Project MT5\scratch", "top_target_2000_2019.csv"), index=False)
    print(f"\n[INFO] Full results saved to B:\\Project MT5\\scratch\\top_target_2000_2019.csv", flush=True)
