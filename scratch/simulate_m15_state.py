import csv
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path

csv_path = Path("B:/Project MT5/Backtest_result/LLHHBOSData_XAUUSD_2026-09-04.csv")

events = []
with open(csv_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()
    header_idx = -1
    for i, line in enumerate(lines):
        if line.startswith("Type,Direction"):
            header_idx = i
            break
    
    reader = csv.DictReader(lines[header_idx:])
    for row_idx, row in enumerate(reader):
        t = row.get("Type", "").strip()
        d = row.get("Direction/Action", "").strip()
        p = row.get("Price", "").strip()
        tm = row.get("Time", "").strip()
        tf = row.get("Timeframe", "").strip()
        st = row.get("Status", "").strip()
        prev_p = row.get("PreviousPrice", "").strip()
        prev_tm = row.get("PreviousTime", "").strip()
        
        if not t or not tm:
            continue
        events.append({
            "idx": row_idx + 3,
            "type": t,
            "direction": d,
            "price": float(p) if p else 0.0,
            "time": tm,
            "timeframe": tf,
            "status": st,
            "prev_price": float(prev_p) if prev_p else 0.0,
            "prev_time": prev_tm
        })

# Sort events chronologically
events_sorted = sorted(events, key=lambda x: x["time"])

# Initialize state variables
m15_lastAcceptedHH = 0.0
m15_lastTimeHH = "1970.01.01 00:00:00"
m15_lastAcceptedLL = 0.0
m15_lastTimeLL = "1970.01.01 00:00:00"

m15_chochBullishConfirmed = False
m15_time_choch_bullish = "1970.01.01 00:00:00"
m15_chochBearishConfirmed = False
m15_time_choch_bearish = "1970.01.01 00:00:00"

m15_chochBullish = False
m15_chochBearish = False

m15_bosBullishConfirmed = False
m15_timeBoSBullish = "1970.01.01 00:00:00"
m15_bosBearishConfirmed = False
m15_timeBoSBearish = "1970.01.01 00:00:00"

m15_isInTrendBullish = False
m15_isInTrendBearish = False

m15_hhAfterChoch = False
m15_llAfterChoch = False
m15_hhAfterBos = False
m15_llAfterBos = False

m15_postChoCH_HH = -1.00
m15_time_postChoCH_HH = "1970.01.01 00:00:00"
m15_absoluteHighestHH = -1.00
m15_timeAbsoluteHighestHH = "1970.01.01 00:00:00"
m15_postChoCH_LL = -1.00
m15_time_postChoCH_LL = "1970.01.01 00:00:00"

m15_entryCountBuy = 0
m15_entryCountSell = 0
m15_bosCycleBuy = 0
m15_bosCycleSell = 0

# Last entry time from Backtest_Results_XAUUSD_2026-09-04.csv was 2026.08.25 18:45:00
m15_lastEntryTime = "2026.08.25 18:45:00"
m15_lastBarTime = "2026.09.04 22:45:00"

for ev in events_sorted:
    t = ev["type"]
    d = ev["direction"]
    p = ev["price"]
    tm = ev["time"]
    st = ev["status"]
    
    if t == "HH" and st == "Accepted":
        m15_lastAcceptedHH = p
        m15_lastTimeHH = tm
        if m15_chochBullish or m15_chochBullishConfirmed:
            m15_hhAfterChoch = True
            if p > m15_postChoCH_HH:
                m15_postChoCH_HH = p
                m15_time_postChoCH_HH = tm
        if m15_bosBullishConfirmed:
            m15_hhAfterBos = True
        if p > m15_absoluteHighestHH:
            m15_absoluteHighestHH = p
            m15_timeAbsoluteHighestHH = tm

    elif t == "LL" and st == "Accepted":
        m15_lastAcceptedLL = p
        m15_lastTimeLL = tm
        if m15_chochBullish or m15_chochBullishConfirmed:
            m15_llAfterChoch = True
            if m15_postChoCH_LL == -1.00 or p < m15_postChoCH_LL:
                m15_postChoCH_LL = p
                m15_time_postChoCH_LL = tm
        if m15_bosBullishConfirmed:
            m15_llAfterBos = True

    elif t == "CHoCH" and d == "Bullish" and st == "Confirmed":
        m15_chochBullishConfirmed = True
        m15_time_choch_bullish = tm
        m15_chochBullish = True
        m15_chochBearish = False
        m15_chochBearishConfirmed = False
        m15_bosBullishConfirmed = False
        m15_isInTrendBullish = False
        m15_isInTrendBearish = False
        m15_hhAfterChoch = False
        m15_llAfterChoch = False
        m15_hhAfterBos = False
        m15_llAfterBos = False
        m15_postChoCH_HH = p
        m15_time_postChoCH_HH = tm
        m15_postChoCH_LL = -1.00
        m15_time_postChoCH_LL = "1970.01.01 00:00:00"
        m15_bosCycleBuy = 0
        m15_bosCycleSell = 0
        m15_entryCountBuy = 0

    elif t == "CHoCH" and d == "Bearish" and st == "Confirmed":
        m15_chochBearishConfirmed = True
        m15_time_choch_bearish = tm
        m15_chochBearish = True
        m15_chochBullish = False
        m15_chochBullishConfirmed = False
        m15_bosBearishConfirmed = False
        m15_isInTrendBullish = False
        m15_isInTrendBearish = False
        m15_hhAfterChoch = False
        m15_llAfterChoch = False
        m15_hhAfterBos = False
        m15_llAfterBos = False
        m15_postChoCH_LL = p
        m15_time_postChoCH_LL = tm
        m15_bosCycleBuy = 0
        m15_bosCycleSell = 0
        m15_entryCountSell = 0

    elif t == "BoS" and d == "Bullish" and st == "Confirmed":
        m15_bosBullishConfirmed = True
        m15_timeBoSBullish = tm
        m15_isInTrendBullish = True
        m15_isInTrendBearish = False
        m15_hhAfterBos = False
        m15_llAfterBos = False
        m15_bosCycleBuy += 1

    elif t == "BoS" and d == "Bearish" and st == "Confirmed":
        m15_bosBearishConfirmed = True
        m15_timeBoSBearish = tm
        m15_isInTrendBearish = True
        m15_isInTrendBullish = False
        m15_hhAfterBos = False
        m15_llAfterBos = False
        m15_bosCycleSell += 1

print("--- SIMULATION RESULT AT END OF DATA (2026.09.04 22:45:00) ---")
res = {
    "M15_lastAcceptedHH": f"{m15_lastAcceptedHH:.2f}",
    "M15_lastTimeHH": m15_lastTimeHH,
    "M15_lastAcceptedLL": f"{m15_lastAcceptedLL:.2f}",
    "M15_lastTimeLL": m15_lastTimeLL,
    "M15_chochBullishConfirmed": "true" if m15_chochBullishConfirmed else "false",
    "M15_time_choch_bullish": m15_time_choch_bullish,
    "M15_chochBearishConfirmed": "true" if m15_chochBearishConfirmed else "false",
    "M15_time_choch_bearish": m15_time_choch_bearish,
    "M15_chochBullish": "true" if m15_chochBullish else "false",
    "M15_chochBearish": "true" if m15_chochBearish else "false",
    "M15_bosBullishConfirmed": "true" if m15_bosBullishConfirmed else "false",
    "M15_timeBoSBullish": m15_timeBoSBullish,
    "M15_bosBearishConfirmed": "true" if m15_bosBearishConfirmed else "false",
    "M15_timeBoSBearish": m15_timeBoSBearish,
    "M15_isInTrendBullish": "true" if m15_isInTrendBullish else "false",
    "M15_isInTrendBearish": "true" if m15_isInTrendBearish else "false",
    "M15_hhAfterChoch": "true" if m15_hhAfterChoch else "false",
    "M15_llAfterChoch": "true" if m15_llAfterChoch else "false",
    "M15_hhAfterBos": "true" if m15_hhAfterBos else "false",
    "M15_llAfterBos": "true" if m15_llAfterBos else "false",
    "M15_postChoCH_HH": f"{m15_postChoCH_HH:.2f}",
    "M15_time_postChoCH_HH": m15_time_postChoCH_HH,
    "M15_absoluteHighestHH": f"{m15_absoluteHighestHH:.2f}",
    "M15_timeAbsoluteHighestHH": m15_timeAbsoluteHighestHH,
    "M15_postChoCH_LL": f"{m15_postChoCH_LL:.2f}",
    "M15_time_postChoCH_LL": m15_time_postChoCH_LL,
    "M15_entryCountBuy": str(m15_entryCountBuy),
    "M15_entryCountSell": str(m15_entryCountSell),
    "M15_bosCycleBuy": str(m15_bosCycleBuy),
    "M15_bosCycleSell": str(m15_bosCycleSell),
    "M15_lastEntryTime": m15_lastEntryTime,
    "M15_lastBarTime": m15_lastBarTime,
}

for k, v in res.items():
    print(f"{k}={v}")

