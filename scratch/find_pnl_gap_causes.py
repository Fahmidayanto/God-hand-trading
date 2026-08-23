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

ea_exec = [t for t in ea_trades if t.get("Status", "").upper() not in ("REJECTED", "FILTERED")]
replay_exec = [t for t in replay_trades if t.get("Status", "").upper() not in ("REJECTED", "FILTERED")]

def parse_time(ts_str):
    if not ts_str or ts_str in ("0", "N/A", ""):
        return None
    for fmt in ("%Y.%m.%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y.%m.%d %H:%M", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(ts_str, fmt)
        except ValueError:
            pass
    return None

# Match trades
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
            if diff_sec <= 1800:
                found = rept
                break
    if found:
        matched_pairs.append((eat, found))
        unmatched_replay.remove(found)
    else:
        unmatched_ea.append(eat)

diff_items = []

for eat, rept in matched_pairs:
    ea_pnl = float(eat.get("Net_Profit", 0) or 0)
    rep_pnl = float(rept.get("Net_Profit", 0) or 0)
    diff = rep_pnl - ea_pnl
    diff_items.append({
        "time": eat.get("EntryTime"),
        "type": eat.get("Type"),
        "struct": eat.get("EntryStructure"),
        "ea_close": eat.get("CloseType"),
        "rep_close": rept.get("CloseType"),
        "ea_pnl": ea_pnl,
        "rep_pnl": rep_pnl,
        "diff": diff,
        "reason": f"Matched trade: {eat.get('CloseType')} vs {rept.get('CloseType')}"
    })

# Unmatched EA trades: EA had it, Replay didn't -> EA PnL exists, Replay = 0, diff = -EA PnL
for eat in unmatched_ea:
    ea_pnl = float(eat.get("Net_Profit", 0) or 0)
    diff_items.append({
        "time": eat.get("EntryTime"),
        "type": eat.get("Type"),
        "struct": eat.get("EntryStructure"),
        "ea_close": eat.get("CloseType"),
        "rep_close": "DITOLAK_REPLAY",
        "ea_pnl": ea_pnl,
        "rep_pnl": 0.0,
        "diff": -ea_pnl, # Replay didn't take it
        "reason": "Trade HANYA ada di EA (Ditolak di Replay)"
    })

# Unmatched Replay trades: Replay had it, EA didn't -> Replay PnL exists, EA = 0, diff = +Replay PnL
for rept in unmatched_replay:
    rep_pnl = float(rept.get("Net_Profit", 0) or 0)
    diff_items.append({
        "time": rept.get("EntryTime"),
        "type": rept.get("Type"),
        "struct": rept.get("EntryStructure"),
        "ea_close": "DITOLAK_EA",
        "rep_close": rept.get("CloseType"),
        "ea_pnl": 0.0,
        "rep_pnl": rep_pnl,
        "diff": rep_pnl, # Replay took it
        "reason": "Trade HANYA ada di Replay (Ditolak di EA)"
    })

diff_items.sort(key=lambda x: abs(x["diff"]), reverse=True)

print("=" * 90)
print("       TOP 20 PERBEDAAN TERBESAR YANG MEMBUAT PNL REPLAY LEBIH TINGGI")
print("=" * 90)
print(f"{'Waktu':<20} | {'Tipe':<4} | {'Struktur':<7} | {'EA PnL':>9} | {'Replay PnL':>11} | {'Selisih':>10} | Alasan")
print("-" * 90)
for item in diff_items[:20]:
    print(f"{item['time']:<20} | {item['type']:<4} | {item['struct']:<7} | {item['ea_pnl']:>8.2f}$ | {item['rep_pnl']:>10.2f}$ | {item['diff']:>+9.2f}$ | {item['reason']}")

print("\n" + "=" * 90)
print("                   AKUMULASI SUMBER SELISIH PROFIT")
print("=" * 90)
total_diff = sum(x["diff"] for x in diff_items)
print(f"Total Selisih Keseluruhan: {total_diff:+,.2f} USD")

# Breakdown penyebab utama:
ea_losses_saved = sum(x["diff"] for x in diff_items if x["rep_close"] == "DITOLAK_REPLAY" and x["ea_pnl"] < 0)
ea_wins_missed = sum(x["diff"] for x in diff_items if x["rep_close"] == "DITOLAK_REPLAY" and x["ea_pnl"] > 0)
replay_extra_wins = sum(x["diff"] for x in diff_items if x["ea_close"] == "DITOLAK_EA")
exit_24h_diff = sum(x["diff"] for x in diff_items if "24H" in x["ea_close"] or "24H" in x["rep_close"])
sl_diff = sum(x["diff"] for x in diff_items if "SL" in x["ea_close"] and "SL" in x["rep_close"])

print(f"1. Kerugian EA yang Berhasil Ditolak oleh Replay (Untung untuk Replay) : {ea_losses_saved:+,.2f} USD")
print(f"2. Keuntungan EA yang Ditolak oleh Replay (Rugi untuk Replay)          : {ea_wins_missed:+,.2f} USD")
print(f"3. Transaksi Ekstra yang Hanya Ada di Replay                          : {replay_extra_wins:+,.2f} USD")
print(f"4. Perbedaan Harga Penutupan 24 Jam (24H_FORCE Exit)                  : {exit_24h_diff:+,.2f} USD")
print(f"5. Perbedaan Spread saat Kena Stop Loss (SL)                          : {sl_diff:+,.2f} USD")
