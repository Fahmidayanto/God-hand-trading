import csv
from datetime import datetime

ea_file = r"b:\Project MT5\Backtest_result_v1\Backtest_Results_XAUUSD_2026-08-20.csv"
replay_file = r"b:\Project MT5\Backtest_result_v1\Backtest_Results_XAUUSD_2026-08-21.csv"

def load_csv(filepath):
    trades = []
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for row in reader:
            clean_row = {k.strip(): v.strip() for k, v in row.items() if k}
            trades.append(clean_row)
    return trades

ea_trades = load_csv(ea_file)
replay_trades = load_csv(replay_file)

# Executed trades: Status != REJECTED
ea_exec = [t for t in ea_trades if t.get("Status", "").upper() not in ("REJECTED", "FILTERED")]
replay_exec = [t for t in replay_trades if t.get("Status", "").upper() not in ("REJECTED", "FILTERED")]

print("=" * 80)
print("             RINGKASAN PERBANDINGAN DATA BACKTEST EA VS REPLAY")
print("=" * 80)
print(f"File EA (2026-08-20)     : {len(ea_trades)} total baris ({len(ea_exec)} dieksekusi, {len(ea_trades) - len(ea_exec)} ditolak)")
print(f"File Replay (2026-08-21) : {len(replay_trades)} total baris ({len(replay_exec)} dieksekusi, {len(replay_trades) - len(replay_exec)} ditolak)")

def parse_time(ts_str):
    if not ts_str or ts_str in ("0", "N/A", ""):
        return None
    for fmt in ("%Y.%m.%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y.%m.%d %H:%M", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(ts_str, fmt)
        except ValueError:
            pass
    return None

def calc_stats(trades):
    pnl_list = [float(t.get("Net_Profit", 0) or 0) for t in trades]
    spread_cost_list = [float(t.get("Spread_Cost", 0) or 0) for t in trades]
    wins = [p for p in pnl_list if p > 0]
    losses = [p for p in pnl_list if p <= 0]
    tot_pnl = sum(pnl_list)
    tot_spread = sum(spread_cost_list)
    wr = (len(wins) / len(pnl_list) * 100) if pnl_list else 0.0
    return {
        "count": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": wr,
        "total_pnl": tot_pnl,
        "total_spread_cost": tot_spread
    }

ea_stats = calc_stats(ea_exec)
rep_stats = calc_stats(replay_exec)

print(f"\nPerforma EA MT5     : {ea_stats['count']} Trade | Win Rate: {ea_stats['win_rate']:.1f}% ({ea_stats['wins']}W / {ea_stats['losses']}L) | Net Profit: {ea_stats['total_pnl']:+,.2f} USD | Spread Cost: {ea_stats['total_spread_cost']:.2f} USD")
print(f"Performa Replay Web : {rep_stats['count']} Trade | Win Rate: {rep_stats['win_rate']:.1f}% ({rep_stats['wins']}W / {rep_stats['losses']}L) | Net Profit: {rep_stats['total_pnl']:+,.2f} USD | Spread Cost: {rep_stats['total_spread_cost']:.2f} USD")
print(f"Selisih Bersih      : {rep_stats['count'] - ea_stats['count']} Trade | Win Rate Diff: {rep_stats['win_rate'] - ea_stats['win_rate']:+.1f}% | Net Profit Diff: {rep_stats['total_pnl'] - ea_stats['total_pnl']:+,.2f} USD")

# Matching trades by entry time proximity (within 30 mins) and direction
matched_pairs = []
unmatched_ea = []
unmatched_replay = list(replay_exec)

for eat in ea_exec:
    ea_t = parse_time(eat.get("EntryTime"))
    ea_type = eat.get("Type", "").upper()
    found = None
    for rept in unmatched_replay:
        rep_t = parse_time(rept.get("EntryTime"))
        rep_type = rept.get("Type", "").upper()
        if ea_t and rep_t and ea_type == rep_type:
            diff_sec = abs((ea_t - rep_t).total_seconds())
            if diff_sec <= 1800: # within 30 minutes
                found = rept
                break
    if found:
        matched_pairs.append((eat, found))
        unmatched_replay.remove(found)
    else:
        unmatched_ea.append(eat)

print("\n" + "=" * 80)
print(f"               HASIL PENCOCOKAN TRANSAKSI (MATCHING)")
print("=" * 80)
print(f"Total Trade Berpasangan (Matched) : {len(matched_pairs)} trade")
print(f"Trade HANYA di EA MT5            : {len(unmatched_ea)} trade (Ditolak/Filtered di Replay)")
print(f"Trade HANYA di Replay Trades     : {len(unmatched_replay)} trade (Ditolak/Filtered di EA atau tgl 21)")

# Kelompokkan Matched Pairs ke dalam 4 Kelompok
group1_24h = []
group3_sl = []
group4_trailing = []
group_perfect = []

for eat, rept in matched_pairs:
    ea_pnl = float(eat.get("Net_Profit", 0) or 0)
    rep_pnl = float(rept.get("Net_Profit", 0) or 0)
    pnl_diff = rep_pnl - ea_pnl
    close_type_ea = eat.get("CloseType", "")
    close_type_rep = rept.get("CloseType", "")
    
    entry_ea = float(eat.get("EntryPrice", 0) or 0)
    entry_rep = float(rept.get("EntryPrice", 0) or 0)
    
    exit_ea = float(eat.get("ExitPrice", 0) or 0)
    exit_rep = float(rept.get("ExitPrice", 0) or 0)
    
    pair_info = {
        "entry_time_ea": eat.get("EntryTime"),
        "entry_time_rep": rept.get("EntryTime"),
        "type": eat.get("Type"),
        "struct": eat.get("EntryStructure"),
        "close_ea": close_type_ea,
        "close_rep": close_type_rep,
        "entry_ea": entry_ea,
        "entry_rep": entry_rep,
        "exit_ea": exit_ea,
        "exit_rep": exit_rep,
        "pnl_ea": ea_pnl,
        "pnl_rep": rep_pnl,
        "diff": pnl_diff
    }
    
    if "24H" in close_type_ea or "24H" in close_type_rep:
        group1_24h.append(pair_info)
    elif "SL" in close_type_ea and "SL" in close_type_rep:
        group3_sl.append(pair_info)
    elif abs(pnl_diff) > 5.0:
        group4_trailing.append(pair_info)
    else:
        group_perfect.append(pair_info)

print("\n" + "=" * 80)
print(f"             BREAKDOWN 4 KELOMPOK PERBEDAAN (DARI FILE CSV)")
print("=" * 80)
print(f"KELOMPOK 1: 24H_FORCE Exit   -> {len(group1_24h)} trade | Net Diff: {sum(x['diff'] for x in group1_24h):+,.2f} USD")
print(f"KELOMPOK 2: Unmatched Trades -> {len(unmatched_ea)} EA-only ({sum(float(x.get('Net_Profit',0)) for x in unmatched_ea):+,.2f} USD) | {len(unmatched_replay)} Replay-only ({sum(float(x.get('Net_Profit',0)) for x in unmatched_replay):+,.2f} USD)")
print(f"KELOMPOK 3: Sama-sama Hit SL -> {len(group3_sl)} trade | Net Diff: {sum(x['diff'] for x in group3_sl):+,.2f} USD")
print(f"KELOMPOK 4: Trailing / Noise -> {len(group4_trailing)} trade | Net Diff: {sum(x['diff'] for x in group4_trailing):+,.2f} USD")
print(f"IDENTIK / SANGAT DEKAT       -> {len(group_perfect)} trade | Net Diff: {sum(x['diff'] for x in group_perfect):+,.2f} USD")
