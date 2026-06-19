import os

BASE = r"d:\Project\Project MT5"
versions = [7, 8, 9, 10, 11]

SESSION_MAPPING = {
    'Sydney_Tokyo_Overlap': 'Sydney_Tokyo_Overlap',
    'Sydney': 'Sydney_Tokyo_Overlap',
    'NoSession': 'Sydney_Tokyo_Overlap',
    'Tokyo_London_Overlap': 'Tokyo_London_Overlap',
    'London': 'London',
    'London_NewYork_Overlap': 'London_NewYork_Overlap',
    'NewYork': 'NewYork',
    'Asia': 'Asia'
}

SESSIONS_6 = [
    'Sydney_Tokyo_Overlap',
    'Tokyo_London_Overlap',
    'London',
    'London_NewYork_Overlap',
    'NewYork',
    'Asia'
]

def parse_csv(filepath, version):
    if not os.path.exists(filepath):
        return []
    trades = []
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read().strip().splitlines()
    if not content:
        return []
    header = content[0].split(',')
    is_v11 = len(header) > 20
    for line in content[1:]:
        if not line.strip():
            continue
        parts = line.split(',')
        session_raw = parts[12].strip()
        session = SESSION_MAPPING.get(session_raw, session_raw)
        if is_v11:
            entry_time = parts[14].strip()[:16]
            status = parts[19].strip()
            reject_reason = parts[20].strip()
            exit_type = parts[21].strip()
        else:
            entry_time = parts[13].strip()[:16]
            status = parts[18].strip()
            reject_reason = parts[19].strip()
            exit_type = 'N/A'
        try: net_profit = float(parts[11])
        except: net_profit = 0.0
        try: entry_price = float(parts[3])
        except: entry_price = 0.0
        try: sl = float(parts[5])
        except: sl = 0.0
        try: tp = float(parts[6])
        except: tp = 0.0
        trade_type = parts[2].strip()
        trades.append({
            'type': trade_type, 'entry_price': entry_price, 'sl': sl, 'tp': tp,
            'net_profit': net_profit, 'session': session, 'session_raw': session_raw,
            'entry_time': entry_time, 'status': status,
            'reject_reason': reject_reason, 'exit_type': exit_type,
        })
    return trades

def get_summary(version):
    f = os.path.join(BASE, f"backtest_v{version}", "Backtest_Summary_XAUUSD_2025-12-30.csv")
    if os.path.exists(f):
        with open(f, 'r', encoding='utf-8') as fh:
            lines = fh.read().strip().splitlines()
        if len(lines) > 1:
            p = lines[1].split(',')
            return float(p[6]), float(p[7])
    return 0.0, 0.0

def parse_old_analisa():
    analisa_map = {}
    md_path = os.path.join(BASE, "Dokumen", "2025.md")
    with open(md_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    in_log = False
    for line in lines:
        ls = line.strip()
        if '11.0b Signal Log' in ls:
            in_log = True
            continue
        if in_log and '11.0c' in ls:
            break
        if in_log and ls.startswith('|'):
            parts = [p.strip() for p in ls.split('|')]
            if not parts[1] or parts[1] == '#' or '---' in parts[1]:
                continue
            try: int(parts[1])
            except: continue
            entry_time = parts[2]
            trade_type = parts[3]
            catatan = parts[10] if len(parts) > 10 else ''
            analisa = parts[11] if len(parts) > 11 else ''
            analisa_map[(entry_time, trade_type)] = {'catatan': catatan, 'analisa': analisa}
    return analisa_map

# ---- Load data ----
trades_by_v = {v: parse_csv(os.path.join(BASE, f"backtest_v{v}", "Backtest_Results_XAUUSD_2025-12-30.csv"), v) for v in versions}
summaries = {v: get_summary(v) for v in versions}
old_analisa = parse_old_analisa()

all_keys = set()
for v in versions:
    for t in trades_by_v[v]:
        all_keys.add((t['entry_time'], t['type']))
sorted_keys = sorted(list(all_keys))

lookup = {}
for v in versions:
    lookup[v] = {}
    for t in trades_by_v[v]:
        k = (t['entry_time'], t['type'])
        lookup[v].setdefault(k, t)

signal_sessions = {}
for k in sorted_keys:
    for v in reversed(versions):
        if k in lookup[v]:
            signal_sessions[k] = lookup[v][k]['session']
            break

def get_entry_info(k):
    for v in versions:
        if k in lookup[v] and lookup[v][k]['status'] == 'EXECUTED':
            t = lookup[v][k]
            return t['entry_price'], t['sl'], t['tp']
    for v in versions:
        if k in lookup[v]:
            t = lookup[v][k]
            return t['entry_price'], t['sl'], t['tp']
    return 0.0, 0.0, 0.0

def get_v_status(v, k):
    if k not in lookup[v]:
        return '—', 0.0
    t = lookup[v][k]
    if t['status'] == 'EXECUTED':
        np = t['net_profit']
        sym = '✅' if np > 0 else '❌'
        return sym, np
    rr = t['reject_reason']
    if 'H1' in rr: return '🚫 H1', 0.0
    if 'H4' in rr: return '🚫 H4', 0.0
    if 'Body Ratio' in rr or 'BR' in rr: return '🚫 BR', 0.0
    if 'Session' in rr: return '🚫 Session', 0.0
    return f'🚫', 0.0

def session_display(sess):
    return {
        'Sydney_Tokyo_Overlap': 'Sydney_Tokyo',
        'Tokyo_London_Overlap': 'Tokyo_London',
        'London': 'London',
        'London_NewYork_Overlap': 'Overlap',
        'NewYork': 'NewYork',
        'Asia': 'Asia'
    }.get(sess, sess)

# ---- Overall metrics ----
metrics = {}
for v in versions:
    trades = trades_by_v[v]
    executed = [t for t in trades if t['status'] == 'EXECUTED']
    rejected = [t for t in trades if t['status'] != 'EXECUTED']
    wins = [t for t in executed if t['net_profit'] > 0]
    losses = [t for t in executed if t['net_profit'] <= 0]
    win_rate = len(wins) / len(executed) * 100 if executed else 0.0
    net_profit = sum(t['net_profit'] for t in executed)
    max_dd, pf = summaries[v]
    prof_per_trade = net_profit / len(executed) if executed else 0.0
    metrics[v] = {
        'total': len(trades), 'exec': len(executed), 'rej': len(rejected),
        'wins': len(wins), 'losses': len(losses), 'win_rate': win_rate,
        'net_profit': net_profit, 'max_dd': max_dd, 'pf': pf, 'prof_per_trade': prof_per_trade
    }

# ---- Rejection breakdown ----
reject_breakdown = {}
for v in versions:
    bd = {}
    for t in trades_by_v[v]:
        if t['status'] != 'EXECUTED':
            rr = t['reject_reason']
            bd[rr] = bd.get(rr, 0) + 1
    reject_breakdown[v] = bd

# ---- Session stats ----
session_stats = {}
for sess in SESSIONS_6:
    session_stats[sess] = {}
    for v in versions:
        v_exec = [t for t in trades_by_v[v] if t['session'] == sess and t['status'] == 'EXECUTED']
        wins = [t for t in v_exec if t['net_profit'] > 0]
        losses = [t for t in v_exec if t['net_profit'] <= 0]
        win_rate = len(wins) / len(v_exec) * 100 if v_exec else 0.0
        net_profit = sum(t['net_profit'] for t in v_exec)
        session_stats[sess][v] = {
            'exec': len(v_exec), 'wins': len(wins), 'losses': len(losses),
            'win_rate': win_rate, 'net_profit': net_profit
        }

# ---- V11-specific exit types ----
v11_exit_notes = {}  # key -> short exit note
for t in trades_by_v[11]:
    k = (t['entry_time'], t['type'])
    if t['status'] == 'EXECUTED':
        et = t['exit_type']
        np = t['net_profit']
        v11_exit_notes[k] = f"{et} (+${np:.2f})" if np > 0 else f"{et} (-${abs(np):.2f})"

# ---- Build analisa texts for new entries (V7/V11 specifics) ----
def make_catatan(k):
    statuses = []
    for v in versions:
        s, np = get_v_status(v, k)
        statuses.append((v, s, np))
    # Summarize
    wins_v = [v for v, s, np in statuses if s == '✅']
    losses_v = [v for v, s, np in statuses if s == '❌']
    missing_v = [v for v, s, np in statuses if s == '—']
    filtered_v = [v for v, s, np in statuses if '🚫' in s]
    
    if filtered_v and not wins_v and not losses_v and not missing_v:
        return "REJECTED semua"
    if not filtered_v and not missing_v:
        if wins_v and not losses_v:
            return "WIN semua"
        if losses_v and not wins_v:
            return "LOSS semua"
    
    parts = []
    if wins_v:
        parts.append(f"V{'V'.join(str(v) for v in wins_v)} WIN")
    if losses_v:
        parts.append(f"V{'V'.join(str(v) for v in losses_v)} LOSS")
    if filtered_v:
        # Get filter type
        fs = get_v_status(filtered_v[0], k)[0]
        ftype = fs.replace('🚫 ', '')
        parts.append(f"V{'V'.join(str(v) for v in filtered_v)} {ftype} blokir")
    if missing_v:
        parts.append(f"V{'V'.join(str(v) for v in missing_v)} tidak ada")
    return ", ".join(parts)

def make_analisa(k, old_a):
    # Preserve old analisa if available, but we need to update it for V7/V11 context
    # Old analisa was for V8/V9/V10 — we'll keep the core and add V7/V11 notes
    entry_time, trade_type = k
    
    # Get V7 status
    v7s, v7np = get_v_status(7, k)
    v11s, v11np = get_v_status(11, k)
    v8s, v8np = get_v_status(8, k)
    v9s, v9np = get_v_status(9, k)
    v10s, v10np = get_v_status(10, k)
    
    # Use old analisa as base if available
    if old_a:
        base = old_a.get('analisa', '')
        if not base:
            return ''
        
        # Add V7 note if interesting
        v7_note = ''
        if v7s not in ('🚫 H1', '🚫 H4', '🚫 BR', '🚫 Session', '—'):
            if v7s == '✅' and v8s != '✅':
                v7_note = f" **V7 WIN ${v7np:.2f}** (tanpa filter H4/BR). "
            elif v7s == '❌' and v8s not in ('❌', '—'):
                v7_note = f" **V7 LOSS ${v7np:.2f}** (tanpa filter H4/BR). "
        
        # Add V11 note
        v11_note = ''
        if v11s == '✅':
            et = v11_exit_notes.get(k, '')
            if v10s != '✅':
                v11_note = f" **V11 WIN** via {et}."
            else:
                et_short = et[:30] if et else ''
                v11_note = f" V11 exit: {et_short}."
        elif v11s == '❌':
            et = v11_exit_notes.get(k, '')
            v11_note = f" **V11 LOSS** ${v11np:.2f}."
        
        result = base
        if v11_note:
            result = result.rstrip() + v11_note
        return result
    
    return ''

# ---- Generate the Markdown ----
lines_out = []

def add(s):
    lines_out.append(s)

# Header
add("# 📊 RINGKASAN KOMPARATIF EA MT5 — v7 s/d v11 (2025)")
add("**Instrumen:** XAUUSD | **Timeframe Entry:** M15 | **Konfirmasi:** H1 EMA")
add("**Lot Size:** 0.01 fixed | **Periode Backtest:** 2025 (Jan–Des)")
add("")
add("---")
add("")

# Feature Matrix
add("## 1. Matriks Fitur (Referensi)")
add("")
add("| Fitur / Versi            | v7 | v8 | v9 | v10 | v11 |")
add("|--------------------------|:--:|:--:|:--:|:---:|:---:|")
add("| Dynamic SL (last LL)     | ✅ | ✅ | ✅ | ✅  | ✅  |")
add("| Hybrid SL Cap (max SL)   | ✅ | ✅ | ✅ | ✅  | ✅  |")
add("| Filter H1 EMA            | ✅ | ✅ | ✅ | ✅  | ✅  |")
add("| Filter H4 EMA            | ❌ | ❌ | ✅ | ✅  | ✅  |")
add("| Filter Body Ratio Candle | ❌ | ✅ | ❌ | ✅  | ✅  |")
add("| Trailing Stop M15        | ❌ | ❌ | ❌ | ❌  | ✅  |")
add("| Stretch-Aware BR Override| ❌ | ❌ | ❌ | ❌  | ✅  |")
add("")
add("---")
add("")

# Performance Summary
add("## 2A. Ringkasan Performa 2025")
add("")
m = metrics

header_row = "| Metrik | V7 | V8 | V9 | V10 | V11 |"
sep_row = "|--------|:--:|:--:|:--:|:---:|:---:|"
add(header_row)
add(sep_row)
add(f"| **Total Signals** | **{m[7]['total']}** | **{m[8]['total']}** | **{m[9]['total']}** | **{m[10]['total']}** | **{m[11]['total']}** |")
add(f"| **EXECUTED Trades** | **{m[7]['exec']}** | **{m[8]['exec']}** | **{m[9]['exec']}** | **{m[10]['exec']}** | **{m[11]['exec']}** |")
add(f"| **REJECTED Signals** | **{m[7]['rej']}** | **{m[8]['rej']}** | **{m[9]['rej']}** | **{m[10]['rej']}** | **{m[11]['rej']}** |")
add(f"| WIN (Executed) | {m[7]['wins']} | {m[8]['wins']} | {m[9]['wins']} | {m[10]['wins']} | {m[11]['wins']} |")
add(f"| LOSS (Executed) | {m[7]['losses']} | {m[8]['losses']} | {m[9]['losses']} | {m[10]['losses']} | {m[11]['losses']} |")
add(f"| Win Rate | **{m[7]['win_rate']:.2f}%** | **{m[8]['win_rate']:.2f}%** | **{m[9]['win_rate']:.2f}%** | **{m[10]['win_rate']:.2f}%** | **{m[11]['win_rate']:.2f}%** |")
add(f"| Total Net Profit | **${m[7]['net_profit']:,.2f}** | **${m[8]['net_profit']:,.2f}** | **${m[9]['net_profit']:,.2f}** | **${m[10]['net_profit']:,.2f}** | **${m[11]['net_profit']:,.2f}** |")
add(f"| Profit per Executed Trade | ${m[7]['prof_per_trade']:.2f} | ${m[8]['prof_per_trade']:.2f} | ${m[9]['prof_per_trade']:.2f} | ${m[10]['prof_per_trade']:.2f} | ${m[11]['prof_per_trade']:.2f} |")
add(f"| Max Drawdown | ${m[7]['max_dd']:,.2f} | ${m[8]['max_dd']:,.2f} | ${m[9]['max_dd']:,.2f} | ${m[10]['max_dd']:,.2f} | ${m[11]['max_dd']:,.2f} |")
add(f"| Profit Factor | {m[7]['pf']:.2f} | {m[8]['pf']:.2f} | {m[9]['pf']:.2f} | {m[10]['pf']:.2f} | {m[11]['pf']:.2f} |")
add("")

add("> ⚠️ **Rejection Breakdown:**")
for v in versions:
    bd = reject_breakdown[v]
    total_rej = sum(bd.values())
    if total_rej == 0:
        add(f"> - **V{v}**: 0 signals REJECTED")
        continue
    parts = []
    for rr, cnt in bd.items():
        pct = cnt / m[v]['total'] * 100
        if 'H1' in rr: label = f"{cnt}x H1 EMA200 Filter"
        elif 'H4' in rr: label = f"{cnt}x H4 EMA Filter"
        elif 'Body Ratio' in rr: label = f"{cnt}x Body Ratio Filter"
        elif 'Session' in rr: label = f"{cnt}x Session Filter"
        else: label = f"{cnt}x {rr}"
        parts.append(label)
    add(f"> - **V{v}**: {total_rej} signals REJECTED — {', '.join(parts)}")
add("")
add("---")
add("")

# Market Context
add("## 2B. Konteks Market 2025 — XAUUSD")
add("")
add("> - **Q1**: $2,630 → $3,100 (rally kuat — Fed dovish expectation, tariff war Trump, safe-haven demand. ATH baru Maret $3,100+)")
add("> - **Q2**: $3,100 → $3,500 (konsolidasi lalu breakout — geopolitical tension, dollar lemah, ATH baru $3,500 April)")
add("> - **Q3**: $3,500 → $3,800 (koreksi volatile Juli, recovery kuat Agustus-September. ATH baru $3,800+ September)")
add("> - **Q4**: $3,800 → $4,300 (rally year-end — Fed rate cut, dollar lemah, gold ATH $4,300 Desember)")
add("")
add("---")
add("")

# Ranking Total Profit
add("## 3. Ranking Total Profit 2025")
add("")
add("| Rank | Versi | Total Profit | Win Rate | Catatan |")
add("|:----:|:-----:|:------------:|:--------:|:--------|")
ranked = sorted(versions, key=lambda v: m[v]['net_profit'], reverse=True)
rank_emojis = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
rank_notes = {
    11: "Trailing stop + stretch-aware BR — profit/trade tertinggi ($80.44) berkat exit ACTIVE_3_BOS di trending kuat",
    10: "Double filter H4+BR — WR tertinggi (73.53%), profit terbesar kedua, MaxDD terkecil ($612.55)",
    9: "H4 filter — WR solid (64.29%), profit moderat. Tidak ada Body Ratio sehingga tangkap lebih banyak signal",
    7: "Baseline lengkap — hanya H1 filter. Profit lebih tinggi dari V8 karena tidak ada Body Ratio filter",
    8: "Body Ratio filter ketat — banyak false rejection di trending market 2025. Profit terendah",
}
for i, v in enumerate(ranked):
    add(f"| {rank_emojis[i]} | **V{v}** | **${m[v]['net_profit']:,.2f}** | **{m[v]['win_rate']:.2f}%** | {rank_notes.get(v, '')} |")
add("")
add("---")
add("")

# Signal Log Section
add("## BAGIAN 11 — COMPARISON DETAIL: TRADE UNIK PER VERSI (V7 vs V8 vs V9 vs V10 vs V11) — TAHUN 2025")
add("")
add("> **Sumber Data**: CSV Aktual — `backtest_v7/`, `backtest_v8/`, `backtest_v9/`, `backtest_v10/`, `backtest_v11/` → file `Backtest_Results_XAUUSD_2025-12-30.csv`")
add("> **Metodologi**: Setiap trade diidentifikasi berdasarkan kombinasi `EntryTime + Type`. Trade dikategorikan berdasarkan kehadiran di masing-masing versi.")
add("> **Legenda**: ✅ WIN | ❌ LOSS | 🚫 FILTER = REJECTED | — Tidak ada di versi ini | **Bold** = trade unik")
add("")
add("> **Konteks Market 2025** — XAUUSD bull run sepanjang tahun:")
add("> - Q1: $2,630 → $3,100 (Fed dovish + tariff war Trump, ATH Maret)")
add("> - Q2: $3,100 → $3,500 (geopolitical + ATH baru April)")
add("> - Q3: $3,500 → $3,800 (volatile Juli, recovery Aug-Sep, ATH baru Sep)")
add("> - Q4: $3,800 → $4,300 (Fed rate cut, year-end rally, ATH $4,300 Des)")
add("")
add("")
add("**Ringkasan 2025 (Aktual dari CSV):**")
add("")
add("| Metrik | V7 | V8 | V9 | V10 | V11 |")
add("|--------|:--:|:--:|:--:|:---:|:---:|")
add(f"| **Total Signals** | **{m[7]['total']}** | **{m[8]['total']}** | **{m[9]['total']}** | **{m[10]['total']}** | **{m[11]['total']}** |")
add(f"| **EXECUTED Trades** | **{m[7]['exec']}** | **{m[8]['exec']}** | **{m[9]['exec']}** | **{m[10]['exec']}** | **{m[11]['exec']}** |")
add(f"| **REJECTED Signals** | **{m[7]['rej']}** | **{m[8]['rej']}** | **{m[9]['rej']}** | **{m[10]['rej']}** | **{m[11]['rej']}** |")
add(f"| WIN (Executed) | {m[7]['wins']} | {m[8]['wins']} | {m[9]['wins']} | {m[10]['wins']} | {m[11]['wins']} |")
add(f"| LOSS (Executed) | {m[7]['losses']} | {m[8]['losses']} | {m[9]['losses']} | {m[10]['losses']} | {m[11]['losses']} |")
add(f"| Win Rate | **{m[7]['win_rate']:.2f}%** | **{m[8]['win_rate']:.2f}%** | **{m[9]['win_rate']:.2f}%** | **{m[10]['win_rate']:.2f}%** | **{m[11]['win_rate']:.2f}%** |")
add(f"| Total Net Profit | **${m[7]['net_profit']:,.2f}** | **${m[8]['net_profit']:,.2f}** | **${m[9]['net_profit']:,.2f}** | **${m[10]['net_profit']:,.2f}** | **${m[11]['net_profit']:,.2f}** |")
add(f"| Profit per Executed Trade | ${m[7]['prof_per_trade']:.2f} | ${m[8]['prof_per_trade']:.2f} | ${m[9]['prof_per_trade']:.2f} | ${m[10]['prof_per_trade']:.2f} | ${m[11]['prof_per_trade']:.2f} |")
add("")
add("---")
add("")

# Signal Log Table
add("### 11.0b Signal Log Lengkap (EXECUTED + REJECTED) — V7 vs V8 vs V9 vs V10 vs V11")
add("")
add("> **Format**: EntryTime | Type | Entry | Session → V7 Status | V8 Status | V9 Status | V10 Status | V11 Status | Profit V7-V10 | Profit V11 | Catatan | Analisa")
add("> **Legenda**: ✅ WIN | ❌ LOSS | 🚫 FILTER = REJECTED | — Tidak ada di versi ini")
add("")
add("#### SIGNAL LOG (Sorted by Entry Time — All 5 Versions)")
add("")
add("| # | Entry Time | Type | Entry | SL | TP | V7 | V8 | V9 | V10 | V11 | Profit V7-V10 | Profit V11 | Catatan | Analisa |")
add("|---|-----------|------|-------|-----|-----|----|----|----|-----|-----|--------------|------------|---------|---------|")

for idx, k in enumerate(sorted_keys, 1):
    entry_time, trade_type = k
    ep, sl, tp = get_entry_info(k)
    sess = session_sessions = signal_sessions[k]

    v7s, v7np = get_v_status(7, k)
    v8s, v8np = get_v_status(8, k)
    v9s, v9np = get_v_status(9, k)
    v10s, v10np = get_v_status(10, k)
    v11s, v11np = get_v_status(11, k)

    # Profit V7-V10: use highest absolute profit from V7-V10 for executed
    exec_profs = [(v, np) for (v, s, np) in [(7,v7s,v7np),(8,v8s,v8np),(9,v9s,v9np),(10,v10s,v10np)] if s in ('✅','❌')]
    if exec_profs:
        # Use V10 if available, else V9, else V8, else V7
        prof_ref = None
        for vx in [10, 9, 8, 7]:
            for vv, np in exec_profs:
                if vv == vx:
                    prof_ref = np
                    break
            if prof_ref is not None:
                break
        profit_v7v10_str = f"${prof_ref:+.2f}" if prof_ref is not None else "—"
    else:
        profit_v7v10_str = "—"

    # Profit V11
    if v11s in ('✅', '❌'):
        profit_v11_str = f"${v11np:+.2f}"
    else:
        profit_v11_str = "—"

    # Get old analisa
    old_a = old_analisa.get(k, None)
    if old_a:
        catatan = old_a['catatan']
        analisa = old_a['analisa']
        # Append V7/V11 context
        if v11s != '—':
            if v11s == '✅':
                et = v11_exit_notes.get(k, '')
                if v10s != '✅' or v9s != '✅':
                    v11_add = f" **V11 WIN ${v11np:.2f}** ({et})."
                else:
                    v11_add = f" V11 exit: {et}."
            else:
                v11_add = f" **V11 LOSS ${v11np:.2f}**."
            if v11_add and v11_add not in analisa:
                analisa = analisa.rstrip() + v11_add
        if v7s not in ('—',) and '🚫' not in v7s:
            v7_add = ''
            if v7s == '✅' and v8s not in ('✅',) and '🚫' not in v8s:
                v7_add = f" **V7 WIN ${v7np:.2f}** (no H4/BR filter)."
            elif v7s == '❌' and v8s == '—':
                v7_add = f" V7 LOSS ${v7np:.2f} (no H4/BR filter)."
            if v7_add and v7_add not in analisa:
                analisa = analisa.rstrip() + v7_add
    else:
        # Generate new catatan/analisa
        catatan = make_catatan(k)
        # Generate analisa based on signal characteristics
        sess_label = {
            'Sydney_Tokyo_Overlap': 'Sydney-Tokyo Overlap',
            'Tokyo_London_Overlap': 'Tokyo-London Overlap',
            'London': 'London',
            'London_NewYork_Overlap': 'Overlap (LN)',
            'NewYork': 'NewYork',
            'Asia': 'Asia'
        }.get(sess, sess)
        
        statuses_str = []
        for vs, s, np in [(7,v7s,v7np),(8,v8s,v8np),(9,v9s,v9np),(10,v10s,v10np),(11,v11s,v11np)]:
            statuses_str.append(f"V{vs}:{s}")
        
        # Determine outcome summary
        if all(s in ('🚫 H1','🚫 H4','🚫 BR','🚫 Session') for _,s,_ in [(7,v7s,0),(8,v8s,0),(9,v9s,0),(10,v10s,0),(11,v11s,0)] if s != '—'):
            analisa = f"**REJECTED**: {trade_type} {sess_label} oleh semua versi."
        elif v7s == '✅' and v8s == '—' and v9s == '—' and v10s == '—' and v11s == '—':
            analisa = f"**V7 ONLY WIN**: {trade_type} {ep:.2f} {sess_label}, profit ${v7np:.2f}. V7 generate signal unik karena tanpa H4/BR filter."
        elif v11s == '✅' and all(s == '—' for s in [v7s,v8s,v9s,v10s]):
            analisa = f"**V11 ONLY WIN**: {trade_type} {ep:.2f} {sess_label}. V11 generate signal unik dari {lookup[11][k]['session_raw']} session."
        else:
            analisa = f"{trade_type} {ep:.2f} {sess_label}. {catatan}."

    sl_str = f"{sl:.2f}" if sl > 0 else "—"
    tp_str = f"{tp:.2f}" if tp > 0 else "—"

    add(f"| {idx} | {entry_time} | {trade_type} | {ep:.2f} | {sl_str} | {tp_str} | {v7s} | {v8s} | {v9s} | {v10s} | {v11s} | {profit_v7v10_str} | {profit_v11_str} | {catatan} | {analisa} |")

add("")
add("")
add("---")
add("")

# Rejection Pattern Analysis
add("### 11.0c Rejection Pattern Analysis 2025")
add("")
add("| Filter | V7 Rejections | V8 Rejections | V9 Rejections | V10 Rejections | V11 Rejections |")
add("|--------|--------------|---------------|---------------|----------------|----------------|")

total_sigs = {v: m[v]['total'] for v in versions}
h1_rej = {v: reject_breakdown[v].get('H1 EMA200 Filter', 0) for v in versions}
h4_rej = {v: reject_breakdown[v].get('H4 EMA Filter', 0) for v in versions}
br_rej = {v: reject_breakdown[v].get('Body Ratio Filter', 0) for v in versions}
sess_rej = {v: reject_breakdown[v].get('Session Filter', 0) for v in versions}
total_rej = {v: m[v]['rej'] for v in versions}

def fmt_rej(v, cnt):
    if cnt == 0:
        return f"N/A"
    pct = cnt / total_sigs[v] * 100
    return f"{cnt} ({pct:.1f}%)"

add(f"| **H1 EMA200** | {fmt_rej(7,h1_rej[7])} | {fmt_rej(8,h1_rej[8])} | {fmt_rej(9,h1_rej[9])} | {fmt_rej(10,h1_rej[10])} | {fmt_rej(11,h1_rej[11])} |")
add(f"| **H4 EMA** | N/A | N/A | {fmt_rej(9,h4_rej[9])} | {fmt_rej(10,h4_rej[10])} | {fmt_rej(11,h4_rej[11])} |")
add(f"| **Body Ratio** | N/A | {fmt_rej(8,br_rej[8])} | N/A | {fmt_rej(10,br_rej[10])} | {fmt_rej(11,br_rej[11])} |")
add(f"| **Session Filter** | N/A | N/A | N/A | {fmt_rej(10,sess_rej[10])} | N/A |")
add(f"| **Total Rejected** | **{total_rej[7]} ({total_rej[7]/total_sigs[7]*100:.1f}%)** | **{total_rej[8]} ({total_rej[8]/total_sigs[8]*100:.1f}%)** | **{total_rej[9]} ({total_rej[9]/total_sigs[9]*100:.1f}%)** | **{total_rej[10]} ({total_rej[10]/total_sigs[10]*100:.1f}%)** | **{total_rej[11]} ({total_rej[11]/total_sigs[11]*100:.1f}%)** |")
add("")
add("> **Key Insight**: V7 paling toleran (H1 filter saja — 14 rejections dari 63 signals). V8 tambah Body Ratio tapi justru membuat lebih ketat dari V7 tanpa H4 benefit. V9 tambah H4 filter — WR naik signifikan (64.29%). V10 double filter = strictest V7-V10 (55.8% rejected) tapi WR tertinggi (73.53%). V11 mirip V10 + trailing stop + Stretch-Aware BR Override — profit tertinggi $3,056 karena exit strategy ACTIVE_3_BOS melipatgandakan profit di trending market 2025.")
add("")
add("---")
add("")

# Session subsections
session_icons = {
    'Sydney_Tokyo_Overlap': '🌐 SYDNEY–TOKYO OVERLAP SESSION',
    'Tokyo_London_Overlap': '🌅 TOKYO–LONDON OVERLAP SESSION',
    'London': '🇬🇧 LONDON SESSION',
    'London_NewYork_Overlap': '🔀 LONDON–NEWYORK OVERLAP SESSION',
    'NewYork': '🗽 NEWYORK SESSION',
    'Asia': '🌏 ASIA SESSION'
}

for sess in SESSIONS_6:
    sess_keys = [k for k in sorted_keys if signal_sessions[k] == sess]
    icon = session_icons[sess]
    add(f"#### {icon} — 2025")
    add("")
    add("| # | Entry Time | Type | Entry | SL | TP | V7 | V8 | V9 | V10 | V11 | Analisa & Alasan |")
    add("|---|-----------|------|-------|-----|-----|----|----|----|-----|-----|------------------|")
    
    for ridx, k in enumerate(sess_keys, 1):
        entry_time, trade_type = k
        ep, sl, tp = get_entry_info(k)
        v7s, v7np = get_v_status(7, k)
        v8s, v8np = get_v_status(8, k)
        v9s, v9np = get_v_status(9, k)
        v10s, v10np = get_v_status(10, k)
        v11s, v11np = get_v_status(11, k)
        
        # Format profit amounts in status
        def fmt_s(s, np):
            if s == '✅': return f"✅ +${np:.2f}"
            if s == '❌': return f"❌ -${abs(np):.2f}"
            return s
        
        v7_disp = fmt_s(v7s, v7np)
        v8_disp = fmt_s(v8s, v8np)
        v9_disp = fmt_s(v9s, v9np)
        v10_disp = fmt_s(v10s, v10np)
        v11_disp = fmt_s(v11s, v11np)
        
        # V11 exit type
        if v11s in ('✅', '❌'):
            et = v11_exit_notes.get(k, '')
            if et:
                v11_disp += f" [{et.split('(')[0].strip()}]"
        
        old_a = old_analisa.get(k, None)
        if old_a and old_a.get('catatan'):
            analisa_text = old_a['catatan']
            # Add V7/V11 notes
            if v7s == '✅' and v8s != '✅' and '🚫' not in v8s:
                analisa_text += f" V7 WIN ${v7np:.2f} (no H4/BR filter)."
            elif v7s == '❌' and v8s == '—':
                analisa_text += f" V7 LOSS ${v7np:.2f}."
            if v11s == '✅' and v10s != '✅':
                analisa_text += f" V11 WIN ${v11np:.2f} via trailing."
            elif v11s == '❌':
                analisa_text += f" V11 LOSS ${v11np:.2f}."
        else:
            analisa_text = make_catatan(k)
            if v11s == '✅':
                et = v11_exit_notes.get(k, '')
                analisa_text += f" V11 WIN via {et}."
        
        sl_str = f"{sl:.2f}" if sl > 0 else "—"
        tp_str = f"{tp:.2f}" if tp > 0 else "—"
        
        add(f"| {ridx} | {entry_time} | {trade_type} | {ep:.2f} | {sl_str} | {tp_str} | {v7_disp} | {v8_disp} | {v9_disp} | {v10_disp} | {v11_disp} | {analisa_text} |")
    
    add("")
    add(f"**Statistik {sess} Session 2025 (dari CSV aktual):**")
    add("")
    add("| Metrik | V7 | V8 | V9 | V10 | V11 |")
    add("|--------|----|----|----|-----|-----|")
    ss = session_stats[sess]
    add(f"| Executed | **{ss[7]['exec']}** | **{ss[8]['exec']}** | **{ss[9]['exec']}** | **{ss[10]['exec']}** | **{ss[11]['exec']}** |")
    add(f"| WIN | **{ss[7]['wins']}** | **{ss[8]['wins']}** | **{ss[9]['wins']}** | **{ss[10]['wins']}** | **{ss[11]['wins']}** |")
    add(f"| LOSS | **{ss[7]['losses']}** | **{ss[8]['losses']}** | **{ss[9]['losses']}** | **{ss[10]['losses']}** | **{ss[11]['losses']}** |")
    
    def wr_fmt(v):
        return f"**{ss[v]['win_rate']:.1f}%**" if ss[v]['exec'] > 0 else "**—**"
    def net_fmt(v):
        return f"**${ss[v]['net_profit']:+,.2f}**"
    add(f"| Win Rate | {wr_fmt(7)} | {wr_fmt(8)} | {wr_fmt(9)} | {wr_fmt(10)} | {wr_fmt(11)} |")
    add(f"| Net Profit | {net_fmt(7)} | {net_fmt(8)} | {net_fmt(9)} | {net_fmt(10)} | {net_fmt(11)} |")
    add("")
    
    # Session insight
    insights = {
        'Sydney_Tokyo_Overlap': "> Sydney_Tokyo_Overlap Insight 2025: Sesi pre-London (00:00–08:00) hanya dikenali oleh V11 yang memiliki granular session classifier. V7-V10 tidak merekam session ini secara terpisah — sinyal-sinyalnya masuk ke NoSession/Asia di versi lain. V11 mencatat 11 exec (WR 45.5%, +$257.43) — moderat karena mix signal pagi yang masih choppy sebelum London open.",
        'Tokyo_London_Overlap': "> Tokyo_London_Overlap Insight 2025: Sesi transisi (08:00–10:00) hanya dikenali oleh V11. Hanya 2 exec — volume rendah, hanya signal yang sangat kuat yang lolos filter. WR 50% (+$51.42) — netral.",
        'London': "> London Session Insight 2025: V7 dominan profit (+$296.61, WR 58.3%) karena mengeksekusi 12 trade vs V8 hanya 10. V8 nyaris break-even (-$3.26) — Body Ratio filter terlalu restriktif di jam London 2025. V11 hanya 4 exec dan net negatif (-$66.95) karena trailing stop terpotong volatilitas London.",
        'London_NewYork_Overlap': "> London_NewYork_Overlap Insight 2025: Sesi terbaik 2025 untuk SEMUA versi. V10 luar biasa (WR 90.9%, +$1,337.57) dengan hanya 11 exec berkualitas tinggi. V11 mendominasi profit absolut (+$2,494.91) berkat trailing stop ACTIVE_3_BOS yang melipatgandakan profit di trending Overlap session. V7 dan V8 hampir identik (~$585-586, WR 66.7%).",
        'NewYork': "> NewYork Session Insight 2025: V7 dan V8 identik (WR 66.7%, +$580.96 masing-masing) — tanpa H4 filter mereka tangkap lebih banyak NY signal. V9 dan V10 solid (WR 66.7-75%). V11 justru terburuk di NY (-$93.53, WR 40%) — trailing stop dipotong oleh NY volatilitas sebelum TP tercapai.",
        'Asia': "> Asia Session Insight 2025: V11 perfek (WR 100%, +$413.41) dengan hanya 2 exec berkualitas — filter strict V11 hanya izinkan signal terbaik. V7-V8 mengeksekusi 13 trade tapi WR rendah (46.2%, ~-$161) — banyak false signal Asia tanpa H4 filter. V10 terbaik di V7-V10 (WR 66.7%, +$436.07) berkat double filter."
    }
    if sess in insights:
        add(insights[sess])
    add("")
    add("")
    add("---")
    add("")

# Cross-session summary
add("#### 📊 RINGKASAN KOMPARATIF ANTAR SESSION — V7 s/d V11 (2025)")
add("")
add("| Session | V7 Exec | V7 WR | V7 Net | V8 Exec | V8 WR | V8 Net | V9 Exec | V9 WR | V9 Net | V10 Exec | V10 WR | V10 Net | V11 Exec | V11 WR | V11 Net |")
add("|---------|---------|-------|--------|---------|-------|--------|---------|-------|--------|----------|--------|---------|----------|--------|---------|")

for sess in SESSIONS_6:
    ss = session_stats[sess]
    sess_name = {
        'Sydney_Tokyo_Overlap': '**Sydney_Tokyo_Overlap**',
        'Tokyo_London_Overlap': '**Tokyo_London_Overlap**',
        'London': '**London**',
        'London_NewYork_Overlap': '**London_NewYork_Overlap**',
        'NewYork': '**NewYork**',
        'Asia': '**Asia**'
    }.get(sess, sess)
    
    def wr_str(v): return f"{ss[v]['win_rate']:.1f}%" if ss[v]['exec'] > 0 else "—"
    def net_str(v): return f"${ss[v]['net_profit']:+,.2f}"
    
    add(f"| {sess_name} | {ss[7]['exec']} | {wr_str(7)} | {net_str(7)} | {ss[8]['exec']} | {wr_str(8)} | {net_str(8)} | {ss[9]['exec']} | {wr_str(9)} | {net_str(9)} | {ss[10]['exec']} | {wr_str(10)} | {net_str(10)} | {ss[11]['exec']} | {wr_str(11)} | {net_str(11)} |")

# Total row
add("| **TOTAL** | " + " | ".join([f"**{m[v]['exec']}** | **{m[v]['win_rate']:.1f}%** | **${m[v]['net_profit']:+,.2f}**" for v in versions]) + " |")

add("")
add("Ranking Session Performance 2025 (6 sesi):")
add("1. 🥇 **London_NewYork_Overlap** — WR tertinggi di semua versi (66-91%). Profit terbesar. V11 dominan ($+2,494.91) via trailing stop ACTIVE_3_BOS.")
add("2. 🥈 **NewYork** — V7-V10 WR solid (66-75%), profit positif. V11 menjadi pengecualian (-$93 karena trailing stop dipotong volatilitas NY).")
add("3. 🥉 **Asia** — V11 flawless (WR 100%). V10 terbaik di V7-V10 (WR 66.7%). V7-V8 terburuk (WR 46%, net negatif).")
add("4. 📊 **Sydney_Tokyo_Overlap** — Hanya V11 yang merekam session ini (11 exec, WR 45.5%, +$257.43).")
add("5. 📊 **Tokyo_London_Overlap** — Hanya V11, 2 exec saja. WR 50%, break-even (+$51.42).")
add("6. ⚠️ **London** — Moderat. V7 paling baik (+$296.61). V8/V10/V11 hampir break-even atau sedikit negatif.")
add("")
add("> ⚠️ **PERBANDINGAN DENGAN 2024**: Di 2024, Asia adalah sesi terbaik (WR 100% semua versi) dan London_NewYork_Overlap terbaik kedua. Di 2025, Overlap tetap dominan dan Asia semakin terbagi — V11 perfect tapi V7-V8 merugi di Asia karena tanpa H4 filter banyak false signal di ATH zone. V11 menjadi pemenang jelas 2025 (+$3,056) berkat trailing stop yang bekerja optimal di trending market 2025.")
add("")
add("---")
add("")

# Insight Section
add("#### 📊 INSIGHT KUNCI: PERBANDINGAN KOMPARATIF DI TAHUN 2025")
add("")
add(f"**Mengapa V11 Profit Tertinggi (${m[11]['net_profit']:,.2f})?**")
add("> - Trailing Stop M15 (ACTIVE_3_BOS + ACTIVE_300_USD) bekerja sempurna di trending market 2025 — gold rally dari $2,630 ke $4,300.")
add("> - Profit/trade tertinggi ($80.44) karena trailing stop melipatgandakan profit di Overlap session.")
add(f"> - WR 60.53% (lebih rendah dari V10) tapi net profit jauh lebih tinggi karena asymmetric risk/reward.")
add("> - London_NewYork_Overlap menjadi goldmine: 14 exec, WR 78.6%, +$2,494.91.")
add("")
add(f"**Mengapa V10 Menjadi Alternatif Terbaik (${m[10]['net_profit']:,.2f})?**")
add("> - WR tertinggi (73.53%) berkat double filter H4+Body Ratio.")
add("> - MaxDD terkecil ($612.55) — paling aman dari semua versi.")
add("> - Overlap dominan (WR 90.9%!) — hanya 11 exec berkualitas sangat tinggi.")
add("> - Sangat konsisten tanpa risiko trailing stop yang kompleks.")
add("")
add(f"**Mengapa V7 Lebih Baik dari V8 (${m[7]['net_profit']:,.2f} vs ${m[8]['net_profit']:,.2f})?**")
add("> - V7 tidak memiliki Body Ratio filter — di market 2025 yang trending kuat, banyak candle dengan body < 40% yang sebenarnya valid entry.")
add("> - V7 execute 49 trade (+2 dari V8), kelebihan ini memberikan additional WIN yang menutupi perbedaan profit.")
add("> - V8 Body Ratio filter menjadi 'false rejection' di trending market 2025 — sama seperti V9 di 2024.")
add("")
add(f"**Pola Kunci 2025 (Berdasarkan 6 Session):**")
add("> - **London_NewYork_Overlap Dominan:** Trending market 2025 membuat Overlap jam 14:00-18:00 sangat profitable di semua versi.")
add("> - **Asia Session Terbagi:** V11+V10 unggul (filter ketat), V7-V8 merugi (tanpa H4 filter tangkap false signal di ATH zone).")
add("> - **V11 LN_Overlap Windfall:** 14 exec, WR 78.6%, +$2,494.91 — trailing stop ACTIVE_3_BOS catch besar-besaran di trending 2025.")
add("> - **V7-V8 NY Identical:** Tanpa H4 filter, V7 dan V8 menghasilkan profit identik di NY session (+$580.96).")
add("")
add("---")
add("")
add(f"*Diekstrak dari CSV aktual: `backtest_v7/Backtest_Results_XAUUSD_2025-12-30.csv`, `backtest_v8/Backtest_Results_XAUUSD_2025-12-30.csv`, `backtest_v9/Backtest_Results_XAUUSD_2025-12-30.csv`, `backtest_v10/Backtest_Results_XAUUSD_2025-12-30.csv`, `backtest_v11/Backtest_Results_XAUUSD_2025-12-30.csv`*")
add("*Instrumen: XAUUSD | Backtest Independen 2025*")

# Write output
out_path = os.path.join(BASE, "Dokumen", "2025.md")
with open(out_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines_out))

print(f"Written {len(lines_out)} lines to {out_path}")
