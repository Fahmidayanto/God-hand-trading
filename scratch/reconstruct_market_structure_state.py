"""
Reconstruct Market Structure State file from LLHHBOSData CSV.
Matches MT5 Dev_Bot_v12 state format exactly.
"""
import csv
from pathlib import Path
from datetime import datetime

def reconstruct_state(csv_path: str, template_state_path: str, output_path: str):
    # Read LLHHBOSData CSV events
    events = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        header_idx = -1
        for i, line in enumerate(lines):
            if line.startswith("Type,Direction"):
                header_idx = i
                break
        if header_idx == -1:
            print("Header not found")
            return
            
        reader = csv.DictReader(lines[header_idx:])
        for row in reader:
            event_type = row.get("Type", "").strip()
            direction = row.get("Direction/Action", "").strip()
            price_str = row.get("Price", "0")
            time_str = row.get("Time", "").strip()
            timeframe = row.get("Timeframe", "M15").strip()
            status = row.get("Status", "").strip()
            prev_price_str = row.get("PreviousPrice", "").strip()
            
            if not event_type or not time_str:
                continue
            if status not in ("Accepted", "Confirmed"):
                continue
                
            try:
                price = float(price_str)
            except ValueError:
                continue
                
            events.append({
                "type": event_type,
                "direction": direction,
                "price": price,
                "time_str": time_str,
                "timeframe": timeframe,
                "status": status,
                "prev_price": float(prev_price_str) if prev_price_str else 0.0
            })

    print(f"Loaded {len(events)} valid events from {csv_path}")

    # Track state variables for M15
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

    # Process events sequentially
    for ev in events:
        tf = ev["timeframe"]
        t = ev["type"]
        d = ev["direction"]
        p = ev["price"]
        tm = ev["time_str"]
        
        if tf == "M15":
            if t == "HH" and ev["status"] == "Accepted":
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

            elif t == "LL" and ev["status"] == "Accepted":
                m15_lastAcceptedLL = p
                m15_lastTimeLL = tm
                if m15_chochBullish or m15_chochBullishConfirmed:
                    m15_llAfterChoch = True
                    if m15_postChoCH_LL == -1.00 or p < m15_postChoCH_LL:
                        m15_postChoCH_LL = p
                        m15_time_postChoCH_LL = tm
                if m15_bosBullishConfirmed:
                    m15_llAfterBos = True

            elif t == "CHoCH" and d == "Bullish":
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

            elif t == "CHoCH" and d == "Bearish":
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

            elif t == "BoS" and d == "Bullish":
                m15_bosBullishConfirmed = True
                m15_timeBoSBullish = tm
                m15_isInTrendBullish = True
                m15_isInTrendBearish = False
                m15_hhAfterBos = False
                m15_llAfterBos = False

            elif t == "BoS" and d == "Bearish":
                m15_bosBearishConfirmed = True
                m15_timeBoSBearish = tm
                m15_isInTrendBearish = True
                m15_isInTrendBullish = False
                m15_hhAfterBos = False
                m15_llAfterBos = False

    # Build updated text content matching template exactly
    state_lines = [
        f"M15_lastAcceptedHH={m15_lastAcceptedHH:.2f}",
        f"M15_lastTimeHH={m15_lastTimeHH}",
        f"M15_lastAcceptedLL={m15_lastAcceptedLL:.2f}",
        f"M15_lastTimeLL={m15_lastTimeLL}",
        f"M15_chochBullishConfirmed={'true' if m15_chochBullishConfirmed else 'false'}",
        f"M15_time_choch_bullish={m15_time_choch_bullish}",
        f"M15_chochBearishConfirmed={'true' if m15_chochBearishConfirmed else 'false'}",
        f"M15_time_choch_bearish={m15_time_choch_bearish}",
        f"M15_chochBullish={'true' if m15_chochBullish else 'false'}",
        f"M15_chochBearish={'true' if m15_chochBearish else 'false'}",
        f"M15_bosBullishConfirmed={'true' if m15_bosBullishConfirmed else 'false'}",
        f"M15_timeBoSBullish={m15_timeBoSBullish}",
        f"M15_bosBearishConfirmed={'true' if m15_bosBearishConfirmed else 'false'}",
        f"M15_timeBoSBearish={m15_timeBoSBearish}",
        f"M15_isInTrendBullish={'true' if m15_isInTrendBullish else 'false'}",
        f"M15_isInTrendBearish={'true' if m15_isInTrendBearish else 'false'}",
        f"M15_hhAfterChoch={'true' if m15_hhAfterChoch else 'false'}",
        f"M15_llAfterChoch={'true' if m15_llAfterChoch else 'false'}",
        f"M15_hhAfterBos={'true' if m15_hhAfterBos else 'false'}",
        f"M15_llAfterBos={'true' if m15_llAfterBos else 'false'}",
        f"M15_postChoCH_HH={m15_postChoCH_HH:.2f}",
        f"M15_time_postChoCH_HH={m15_time_postChoCH_HH}",
        f"M15_absoluteHighestHH={m15_absoluteHighestHH:.2f}",
        f"M15_timeAbsoluteHighestHH={m15_timeAbsoluteHighestHH}",
        f"M15_postChoCH_LL={m15_postChoCH_LL:.2f}",
        f"M15_time_postChoCH_LL={m15_time_postChoCH_LL}",
        f"M15_entryCountBuy=0",
        f"M15_entryCountSell=0",
        f"M15_lastEntryTime=1970.01.01 00:00:00",
        f"M15_lastBarTime=2026.08.12 13:00:00",
        f"H1_lastAcceptedHH=-1.00",
        f"H1_lastTimeHH=1970.01.01 00:00:00",
        f"H1_lastAcceptedLL=-1.00",
        f"H1_lastTimeLL=1970.01.01 00:00:00",
        f"H1_chochBullishConfirmed=false",
        f"H1_chochBearishConfirmed=false",
        f"H1_chochBullish=false",
        f"H1_chochBearish=false",
        f"H1_bosBullishConfirmed=false",
        f"H1_bosBearishConfirmed=false",
        f"H1_isInTrendBullish=false",
        f"H1_isInTrendBearish=false",
        f"H1_hhAfterChoch=false",
        f"H1_llAfterChoch=false",
        f"H1_hhAfterBos=false",
        f"H1_llAfterBos=false",
        f"H1_postChoCH_HH=-1.00",
        f"H1_time_postChoCH_HH=1970.01.01 00:00:00",
        f"H1_absoluteHighestHH=-1.00",
        f"H1_timeAbsoluteHighestHH=1970.01.01 00:00:00",
        f"H1_postChoCH_LL=-1.00",
        f"H1_time_postChoCH_LL=1970.01.01 00:00:00",
        f"H1_lastBarTime=1970.01.01 00:00:00"
    ]
    
    out_content = "\n".join(state_lines) + "\n"
    print("=== RECONSTRUCTED STATE ===")
    print(out_content)
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(out_content)
    print(f"Wrote reconstructed state to {output_path}")

if __name__ == "__main__":
    csv_file = r"b:\Project MT5\Backtest_result\LLHHBOSData_XAUUSD_2026-08-11.csv"
    template_file = r"b:\Project MT5\Backtest_result\MarketStructure_State_XAUUSD_2026-08-12.txt"
    out_file = r"b:\Project MT5\scratch\MarketStructure_State_XAUUSD_2026-08-12_reconstructed.txt"
    reconstruct_state(csv_file, template_file, out_file)
