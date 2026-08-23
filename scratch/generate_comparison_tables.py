import csv
from datetime import datetime

ea_csv_path = r"C:\Users\fahmi\AppData\Roaming\MetaQuotes\Tester\D0E8209F77C8CF37AD8BF550E51FF075\Agent-127.0.0.1-3000\MQL5\Files\Backtest_Results_XAUUSD_2026-08-20.csv"
replay_csv_path = r"C:\Users\fahmi\Downloads\Backtest_Results_XAUUSD_2026-08-21.csv"

def parse_dt(s):
    if not s: return None
    s = s.replace("-", ".").strip()
    try: return datetime.strptime(s, "%Y.%m.%d %H:%M:%S")
    except:
        try: return datetime.strptime(s, "%Y.%m.%d %H:%M")
        except: return None

with open(ea_csv_path, "r", encoding="utf-8", errors="ignore") as f:
    ea_rows = list(csv.DictReader(f))
with open(replay_csv_path, "r", encoding="utf-8", errors="ignore") as f:
    replay_rows = list(csv.DictReader(f))

ea_trades = [r for r in ea_rows if r.get("Status", "").upper() != "REJECTED"]
replay_trades = [r for r in replay_rows if r.get("Status", "").upper() != "REJECTED"]

for r in ea_trades: r["_dt"] = parse_dt(r.get("EntryTime"))
for r in replay_trades: r["_dt"] = parse_dt(r.get("EntryTime"))

matched_pairs = []
unmatched_ea = []
used_replay = set()

for e in ea_trades:
    e_dt = e["_dt"]
    best_r = None
    best_diff = 999999
    best_idx = None
    for idx, r in enumerate(replay_trades):
        if idx in used_replay: continue
        if e.get("Type") != r.get("Type"): continue
        diff_s = abs((e_dt - r["_dt"]).total_seconds())
        if diff_s <= 1800 and diff_s < best_diff:
            best_diff = diff_s
            best_r = r
            best_idx = idx
    if best_r is not None:
        used_replay.add(best_idx)
        matched_pairs.append((e, best_r))
    else:
        unmatched_ea.append(e)

unmatched_replay = [r for idx, r in enumerate(replay_trades) if idx not in used_replay]

# Classify into 4 Groups
# Kelompok 1: Perbedaan Waktu & Harga Eksekusi 24H_FORCE
# Kelompok 2: Trade Ekstra di EA MT5 (12 Trade) & Replay Only (4 Trade)
# Kelompok 3: Spread Realistis & Slippage di MT5 (Hit SL)
# Kelompok 4: Noise Pullback Menyentuh SL Lebih Awal / Perbedaan Exit CloseType

group1 = [] # 24H Force diffs
group2_ea = sorted(unmatched_ea, key=lambda x: x["_dt"]) # EA only
group2_replay = sorted(unmatched_replay, key=lambda x: x["_dt"]) # Replay only
group3 = [] # Spread / SL diffs
group4 = [] # Different CloseType (SL in EA vs TP/24H in Replay)

for e, r in matched_pairs:
    e_p = float(e.get("Net_Profit", 0) or 0)
    r_p = float(r.get("Net_Profit", 0) or 0)
    diff = r_p - e_p
    e_close = e.get("CloseType")
    r_close = r.get("CloseType")
    
    if e_close != r_close:
        group4.append((e, r, diff))
    elif "24H" in str(e_close) and "24H" in str(r_close):
        group1.append((e, r, diff))
    else:
        group3.append((e, r, diff))

# Sort groups chronologically
group1 = sorted(group1, key=lambda x: x[0]["_dt"])
group3 = sorted(group3, key=lambda x: x[0]["_dt"])
group4 = sorted(group4, key=lambda x: x[0]["_dt"])

def fmt_row(e, r):
    time_str = e.get("EntryTime", "")
    t_type = e.get("Type", "")
    ea_entry = f"{float(e.get('EntryPrice',0)):.2f}"
    rp_entry = f"{float(r.get('EntryPrice',0)):.2f}"
    ea_sl = f"{float(e.get('FinalSL',0)):.2f}"
    rp_sl = f"{float(r.get('FinalSL',0)):.2f}"
    ea_tp = f"{float(e.get('FinalTP',0)):.2f}"
    rp_tp = f"{float(r.get('FinalTP',0)):.2f}"
    ea_exit = f"{float(e.get('ExitPrice',0)):.2f} ({e.get('CloseType')})"
    rp_exit = f"{float(r.get('ExitPrice',0)):.2f} ({r.get('CloseType')})"
    ea_pnl = f"{float(e.get('Net_Profit',0)):+.2f}"
    rp_pnl = f"{float(r.get('Net_Profit',0)):+.2f}"
    diff = f"{float(r.get('Net_Profit',0)) - float(e.get('Net_Profit',0)):+.2f}"
    return f"| {time_str} | {t_type} | {ea_entry} / {rp_entry} | {ea_sl} / {rp_sl} | {ea_tp} / {rp_tp} | {ea_exit} | {rp_exit} | {ea_pnl} | {rp_pnl} | {diff} |"

print(f"Group 1 Count: {len(group1)}")
print(f"Group 2 EA Count: {len(group2_ea)}, Replay Count: {len(group2_replay)}")
print(f"Group 3 Count: {len(group3)}")
print(f"Group 4 Count: {len(group4)}")

with open(r"b:\Project MT5\scratch\table_output.txt", "w", encoding="utf-8") as out:
    out.write("### KELOMPOK 1: Perbedaan Waktu & Harga Eksekusi 24H_FORCE (28 Trade)\n")
    out.write("| Waktu Entry | Tipe | Entry (EA/Replay) | SL (EA/Replay) | TP (EA/Replay) | Exit EA (Tipe) | Exit Replay (Tipe) | Profit EA (USD) | Profit Replay (USD) | Selisih (USD) |\n")
    out.write("|---|---|---|---|---|---|---|---|---|---|\n")
    for e, r, d in group1:
        out.write(fmt_row(e, r) + "\n")

    out.write("\n### KELOMPOK 2: Trade yang Hanya Muncul di EA atau Hanya di Replay\n")
    out.write("#### 2A. Trade Hanya Muncul di EA MT5 (12 Trade - Rata-rata Filtered di Replay)\n")
    out.write("| Waktu Entry | Tipe | Struktur | Entry Price | SL | TP | Exit Price | Close Type | Net Profit (USD) | Status / Alasan Filter Replay |\n")
    out.write("|---|---|---|---|---|---|---|---|---|---|\n")
    for e in group2_ea:
        out.write(f"| {e.get('EntryTime')} | {e.get('Type')} | {e.get('EntryStructure')} | {float(e.get('EntryPrice',0)):.2f} | {float(e.get('FinalSL',0)):.2f} | {float(e.get('FinalTP',0)):.2f} | {float(e.get('ExitPrice',0)):.2f} | {e.get('CloseType')} | {float(e.get('Net_Profit',0)):+.2f} | Filtered di Replay |\n")

    out.write("\n#### 2B. Trade Hanya Muncul di Replay Trades (4 Trade)\n")
    out.write("| Waktu Entry | Tipe | Struktur | Entry Price | SL | TP | Exit Price | Close Type | Net Profit (USD) | Catatan |\n")
    out.write("|---|---|---|---|---|---|---|---|---|---|\n")
    for r in group2_replay:
        out.write(f"| {r.get('EntryTime')} | {r.get('Type')} | {r.get('EntryStructure')} | {float(r.get('EntryPrice',0)):.2f} | {float(r.get('FinalSL',0)):.2f} | {float(r.get('FinalTP',0)):.2f} | {float(r.get('ExitPrice',0)):.2f} | {r.get('CloseType')} | {float(r.get('Net_Profit',0)):+.2f} | {r.get('Status')} |\n")

    out.write("\n### KELOMPOK 3: Spread Realistis & Slippage di MT5 (Hit SL / Normal Exits - 28 Trade)\n")
    out.write("| Waktu Entry | Tipe | Entry (EA/Replay) | SL (EA/Replay) | TP (EA/Replay) | Exit EA (Tipe) | Exit Replay (Tipe) | Profit EA (USD) | Profit Replay (USD) | Selisih (USD) |\n")
    out.write("|---|---|---|---|---|---|---|---|---|---|\n")
    for e, r, d in group3:
        out.write(fmt_row(e, r) + "\n")

    out.write("\n### KELOMPOK 4: Noise Pullback / Perbedaan CloseType (5 Trade)\n")
    out.write("| Waktu Entry | Tipe | Entry (EA/Replay) | SL (EA/Replay) | TP (EA/Replay) | Exit EA (Tipe) | Exit Replay (Tipe) | Profit EA (USD) | Profit Replay (USD) | Selisih (USD) |\n")
    out.write("|---|---|---|---|---|---|---|---|---|---|\n")
    for e, r, d in group4:
        out.write(fmt_row(e, r) + "\n")

print("Output written to scratch/table_output.txt")
