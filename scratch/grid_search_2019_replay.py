"""
Parallel High-Performance Grid Search Optimizer for 2019 XAUUSD Replay Trades.
Uses multiprocessing to distribute 40,320 combinations across all CPU cores.
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime
import itertools
import time
from multiprocessing import Pool, cpu_count

# Paths
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
    
    # 1. Load M15 Candles
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
    
    # 2. Load BOS / Structures
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
    
    # 3. Load Executed Trades
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
        
        # Precompute structural SL
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
                    
        # Find candle slice for trade (up to 24h = 96 candles + 5 margin)
        start_idx = np.searchsorted(m15_epochs, entry_epoch, side='left')
        if start_idx >= n_candles:
            continue
            
        end_idx = min(n_candles, start_idx + 105)
        
        # Slice arrays for this trade
        c_epochs = m15_epochs[start_idx:end_idx].tolist()
        c_opens = m15_opens[start_idx:end_idx].tolist()
        c_highs = m15_highs[start_idx:end_idx].tolist()
        c_lows = m15_lows[start_idx:end_idx].tolist()
        c_closes = m15_closes[start_idx:end_idx].tolist()
        
        prepared_trades.append({
            'ticket': int(row['Ticket']),
            'is_buy': is_buy,
            'entry_price': entry_price,
            'entry_epoch': entry_epoch,
            'struct_sl': struct_sl,
            'actual_lot': actual_lot,
            'base_fees': (spread_cost + commission + abs(swap)),
            'c_epochs': c_epochs,
            'c_opens': c_opens,
            'c_highs': c_highs,
            'c_lows': c_lows,
            'c_closes': c_closes,
            'n_sub_candles': len(c_epochs)
        })
        
    print(f"[INFO] Successfully preprocessed {len(prepared_trades)} active trades for parallel simulation.", flush=True)
    return prepared_trades

# Global worker trade storage
G_TRADES = []

def init_worker(trades):
    global G_TRADES
    G_TRADES = trades

def worker_evaluate_chunk(chunk):
    results = []
    trades = G_TRADES
    
    for item in chunk:
        b_ref, i_tp, tr, m_sl, buf, t_trig, t_exp = item
        base_lot = 0.05
        use_scaling = True
        
        pnl_list = []
        wins = 0
        total_gain = 0.0
        total_loss = 0.0
        
        for t in trades:
            entry_price = t['entry_price']
            entry_epoch = t['entry_epoch']
            is_buy = t['is_buy']
            
            if use_scaling and b_ref > 0 and entry_price > 0:
                ratio = entry_price / b_ref
                trade_lot = max(0.01, round(base_lot / ratio, 2))
            else:
                ratio = 1.0
                trade_lot = base_lot
                
            eff_trailing = tr * ratio
            eff_tp_trigger = t_trig * ratio
            eff_tp_ekspansi = t_exp * ratio
            eff_initial_tp = i_tp * ratio
            eff_buffer = buf * ratio
            eff_min_sl = m_sl * ratio
            eff_max_sl = eff_trailing * 1.5
            
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
            
            for i in range(n_c):
                # 1. 24h force close
                if (c_epochs[i] - entry_epoch) >= 86400:
                    exit_price = c_opens[i]
                    break
                    
                # 2. Dynamic TP Expansion
                if is_buy:
                    if current_tp is not None and (current_tp - c_opens[i]) <= eff_tp_trigger:
                        expanded_tp = c_opens[i] + eff_tp_ekspansi
                        if expanded_tp > current_tp:
                            current_tp = expanded_tp
                    # 3. Intra-Bar check
                    if c_lows[i] <= current_sl:
                        exit_price = current_sl
                        break
                    if current_tp is not None and c_highs[i] >= current_tp:
                        exit_price = current_tp
                        break
                    # Trailing SL
                    target_sl = c_closes[i] - eff_trailing
                    min_sl = entry_price - eff_trailing
                    max_sl = c_closes[i] - 1.50
                    new_sl = max(min_sl, min(max_sl, target_sl))
                    if new_sl > current_sl:
                        current_sl = new_sl
                else:
                    if current_tp is not None and (c_opens[i] - current_tp) <= eff_tp_trigger:
                        expanded_tp = c_opens[i] - eff_tp_ekspansi
                        if expanded_tp < current_tp:
                            current_tp = expanded_tp
                    # 3. Intra-Bar check
                    if c_highs[i] >= current_sl:
                        exit_price = current_sl
                        break
                    if current_tp is not None and c_lows[i] <= current_tp:
                        exit_price = current_tp
                        break
                    # Trailing SL
                    target_sl = c_closes[i] + eff_trailing
                    min_sl = entry_price + eff_trailing
                    max_sl = c_closes[i] + 1.50
                    new_sl = min(min_sl, max(max_sl, target_sl))
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
            if net_profit > 0:
                wins += 1
                total_gain += net_profit
            elif net_profit < 0:
                total_loss += abs(net_profit)
                
        total_trades = len(pnl_list)
        if total_trades == 0:
            continue
            
        balance = 1000.0
        peak = balance
        max_dd_usd = 0.0
        max_dd_pct = 0.0
        
        for p in pnl_list:
            balance += p
            if balance > peak:
                peak = balance
            dd_usd = peak - balance
            dd_pct = (dd_usd / peak) * 100.0 if peak > 0 else 0.0
            if dd_usd > max_dd_usd:
                max_dd_usd = dd_usd
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct
                
        total_net_pnl = balance - 1000.0
        win_rate = (wins / total_trades) * 100.0 if total_trades > 0 else 0.0
        profit_factor = (total_gain / total_loss) if total_loss > 0 else (999.0 if total_gain > 0 else 0.0)
        
        # Only keep profitable results to save memory
        if total_net_pnl > 0:
            results.append({
                'base_ref': b_ref,
                'use_scaling': True,
                'trailing_dist': tr,
                'initial_tp_dist': i_tp,
                'min_sl_dist': m_sl,
                'sl_safety_buffer': buf,
                'tp_trigger': t_trig,
                'tp_ekspansi': t_exp,
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

def evaluate_single(trades, base_ref, use_scaling, base_lot, tr, i_tp, m_sl, buf, t_trig, t_exp):
    pnl_list = []
    wins = 0
    total_gain = 0.0
    total_loss = 0.0
    
    for t in trades:
        entry_price = t['entry_price']
        entry_epoch = t['entry_epoch']
        is_buy = t['is_buy']
        
        if use_scaling and base_ref > 0 and entry_price > 0:
            ratio = entry_price / base_ref
            trade_lot = max(0.01, round(base_lot / ratio, 2))
        else:
            ratio = 1.0
            trade_lot = base_lot
            
        eff_trailing = tr * ratio
        eff_tp_trigger = t_trig * ratio
        eff_tp_ekspansi = t_exp * ratio
        eff_initial_tp = i_tp * ratio
        eff_buffer = buf * ratio
        eff_min_sl = m_sl * ratio
        eff_max_sl = eff_trailing * 1.5
        
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
        
        for i in range(n_c):
            if (c_epochs[i] - entry_epoch) >= 86400:
                exit_price = c_opens[i]
                break
            if is_buy:
                if current_tp is not None and (current_tp - c_opens[i]) <= eff_tp_trigger:
                    expanded_tp = c_opens[i] + eff_tp_ekspansi
                    if expanded_tp > current_tp:
                        current_tp = expanded_tp
                if c_lows[i] <= current_sl:
                    exit_price = current_sl
                    break
                if current_tp is not None and c_highs[i] >= current_tp:
                    exit_price = current_tp
                    break
                target_sl = c_closes[i] - eff_trailing
                min_sl = entry_price - eff_trailing
                max_sl = c_closes[i] - 1.50
                new_sl = max(min_sl, min(max_sl, target_sl))
                if new_sl > current_sl:
                    current_sl = new_sl
            else:
                if current_tp is not None and (c_opens[i] - current_tp) <= eff_tp_trigger:
                    expanded_tp = c_opens[i] - eff_tp_ekspansi
                    if expanded_tp < current_tp:
                        current_tp = expanded_tp
                if c_highs[i] >= current_sl:
                    exit_price = current_sl
                    break
                if current_tp is not None and c_lows[i] <= current_tp:
                    exit_price = current_tp
                    break
                target_sl = c_closes[i] + eff_trailing
                min_sl = entry_price + eff_trailing
                max_sl = c_closes[i] + 1.50
                new_sl = min(min_sl, max(max_sl, target_sl))
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
        if net_profit > 0:
            wins += 1
            total_gain += net_profit
        elif net_profit < 0:
            total_loss += abs(net_profit)
            
    total_trades = len(pnl_list)
    balance = 1000.0
    peak = balance
    max_dd_usd = 0.0
    max_dd_pct = 0.0
    
    for p in pnl_list:
        balance += p
        if balance > peak:
            peak = balance
        dd_usd = peak - balance
        dd_pct = (dd_usd / peak) * 100.0 if peak > 0 else 0.0
        if dd_usd > max_dd_usd:
            max_dd_usd = dd_usd
        if dd_pct > max_dd_pct:
            max_dd_pct = dd_pct
            
    total_net_pnl = balance - 1000.0
    win_rate = (wins / total_trades) * 100.0 if total_trades > 0 else 0.0
    profit_factor = (total_gain / total_loss) if total_loss > 0 else (999.0 if total_gain > 0 else 0.0)
    
    return {
        'total_trades': total_trades,
        'wins': wins,
        'losses': total_trades - wins,
        'win_rate': round(win_rate, 2),
        'total_net_pnl': round(total_net_pnl, 2),
        'final_balance': round(balance, 2),
        'max_dd_usd': round(max_dd_usd, 2),
        'max_dd_pct': round(max_dd_pct, 2),
        'profit_factor': round(profit_factor, 2)
    }

if __name__ == "__main__":
    start_t = time.time()
    trades = load_and_preprocess()
    
    # Benchmarks
    unscaled_res = evaluate_single(trades, 2000.0, False, 0.05, 30.0, 30.0, 15.0, 10.0, 10.0, 20.0)
    unscaled_res['label'] = 'Tanpa Scaling (Fixed Default: TP 30, Trailing 30, MinSL 15)'
    
    base4500_res = evaluate_single(trades, 4500.0, True, 0.05, 60.0, 60.0, 20.0, 10.0, 15.0, 30.0)
    base4500_res['label'] = 'Base 4500 Default (TP 60, Trailing 60, MinSL 20)'
    
    base1500_res = evaluate_single(trades, 1500.0, True, 0.05, 25.0, 25.0, 12.0, 5.0, 10.0, 20.0)
    base1500_res['label'] = 'Base 1500 Standard (TP 25, Trailing 25, MinSL 12)'
    
    # Parameter Grid
    base_refs = [1200.0, 1300.0, 1400.0, 1500.0, 1800.0, 2000.0, 2500.0, 3000.0, 4500.0]
    initial_tps = [15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 50.0, 60.0]
    trailings = [15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 50.0]
    min_sls = [10.0, 12.0, 15.0, 20.0]
    buffers = [2.0, 3.0, 5.0, 8.0, 10.0]
    tp_triggers = [10.0, 15.0]
    tp_ekspansis = [20.0, 30.0]
    
    grid = list(itertools.product(base_refs, initial_tps, trailings, min_sls, buffers, tp_triggers, tp_ekspansis))
    total_combos = len(grid)
    n_workers = min(16, cpu_count())
    chunk_size = 500
    
    chunks = [grid[i:i + chunk_size] for i in range(0, total_combos, chunk_size)]
    print(f"[INFO] Launching Pool with {n_workers} CPU cores for {total_combos} combinations in {len(chunks)} chunks...", flush=True)
    
    all_results = []
    with Pool(processes=n_workers, initializer=init_worker, initargs=(trades,)) as pool:
        for chunk_res in pool.imap_unordered(worker_evaluate_chunk, chunks):
            all_results.extend(chunk_res)
            
    elapsed = time.time() - start_t
    print(f"[SUCCESS] Parallel Grid Search evaluated {total_combos} combinations in {elapsed:.2f} seconds!", flush=True)
    print(f"[INFO] Found {len(all_results)} profitable configurations.", flush=True)
    
    df_res = pd.DataFrame(all_results)
    
    df_filtered = df_res[df_res['profit_factor'] >= 1.5].copy()
    if len(df_filtered) == 0:
        df_filtered = df_res.copy()
        
    df_sorted = df_filtered.sort_values(by=['total_net_pnl', 'max_dd_pct', 'profit_factor'], ascending=[False, True, False]).reset_index(drop=True)
    
    print("\n" + "="*85, flush=True)
    print("TOP 5 BEST PARAMETER COMBINATIONS FOR 2019 (RANKED BY NET PNL & DRAWDOWN)", flush=True)
    print("="*85, flush=True)
    top5 = df_sorted.head(5)
    for idx, row in top5.iterrows():
        print(f"Rank #{idx+1}: BaseRef={row['base_ref']} USD | TP={row['initial_tp_dist']} | Trailing={row['trailing_dist']} | MinSL={row['min_sl_dist']} | Buffer={row['sl_safety_buffer']} | Trig={row['tp_trigger']} | Exp={row['tp_ekspansi']}", flush=True)
        print(f"         Net PnL: +{row['total_net_pnl']} USD | Final Balance: {row['final_balance']} USD | Max DD: {row['max_dd_pct']}% ({row['max_dd_usd']} USD) | PF: {row['profit_factor']} | WR: {row['win_rate']}% ({row['wins']}/{row['total_trades']})", flush=True)
        print("-" * 85, flush=True)
        
    print("\n" + "="*85, flush=True)
    print("BENCHMARK COMPARISON TABLE", flush=True)
    print("="*85, flush=True)
    benchmarks = [unscaled_res, base4500_res, base1500_res]
    for b in benchmarks:
        print(f"{b['label']}:", flush=True)
        print(f"   Net PnL: {b['total_net_pnl']} USD | Final Balance: {b['final_balance']} USD | Max DD: {b['max_dd_pct']}% ({b['max_dd_usd']} USD) | PF: {b['profit_factor']} | WR: {b['win_rate']}%", flush=True)
        print("-" * 85, flush=True)
        
    df_sorted.head(100).to_csv(os.path.join(r"B:\Project MT5\scratch", "top100_grid_search_2019.csv"), index=False)
    print(f"\n[INFO] Full Top 100 results saved to B:\\Project MT5\\scratch\\top100_grid_search_2019.csv", flush=True)
