"""
Cross-Validation: Bandingkan data CSV langsung vs data di Neon Database
"""
import os
import sys
import csv
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
BACKEND_DIR = PROJECT_ROOT / "ValueCell_MT5" / "backend"
BACKTEST_DIR = PROJECT_ROOT / "Backtest_result"

sys.path.insert(0, str(BACKEND_DIR))
from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

import psycopg2

conn = psycopg2.connect(
    host=os.getenv("PGHOST"), dbname=os.getenv("PGDATABASE"),
    user=os.getenv("PGUSER"), password=os.getenv("PGPASSWORD"),
    sslmode=os.getenv("PGSSLMODE", "require"), connect_timeout=15
)
cur = conn.cursor()

years = ["2024", "2025", "2026"]

print("=== 1. VALIDASI JUMLAH BARIS CSV vs DATABASE ===")
for y in years:
    # Backtest Results
    bf = list(BACKTEST_DIR.glob(f"Backtest_Results_XAUUSD_*{y}*.csv"))[0]
    with open(bf, "r", encoding="utf-8", errors="ignore") as f:
        csv_trades = sum(1 for line in f if line.strip()) - 1  # minus header
    
    cur.execute("SELECT COUNT(*) FROM backtest_results_xauusd WHERE csv_filename = %s", (bf.name,))
    db_trades = cur.fetchone()[0]
    
    # LLHHBOSData
    lf = list(BACKTEST_DIR.glob(f"LLHHBOSData_XAUUSD_*{y}*.csv"))[0]
    with open(lf, "r", encoding="utf-8", errors="ignore") as f:
        csv_structs = sum(1 for line in f if line.strip()) - 2  # minus title & header
        
    cur.execute("SELECT COUNT(*) FROM llhhbosdata_xauusd WHERE csv_filename = %s", (lf.name,))
    db_structs = cur.fetchone()[0]
    
    # MarketData M15
    mf = list(BACKTEST_DIR.glob(f"MarketData_XAUUSD_M15_*{y}*.csv"))[0]
    with open(mf, "r", encoding="utf-8", errors="ignore") as f:
        csv_m15 = sum(1 for line in f if line.strip()) - 1
        
    cur.execute("SELECT COUNT(*) FROM marketdata_xauusd_m15 WHERE csv_filename = %s", (mf.name,))
    db_m15 = cur.fetchone()[0]
    
    status_trade = "VALID MATCH" if csv_trades == db_trades else f"MISMATCH ({csv_trades} vs {db_trades})"
    status_struct = "VALID MATCH" if csv_structs == db_structs else f"MISMATCH ({csv_structs} vs {db_structs})"
    status_m15 = "VALID MATCH" if csv_m15 == db_m15 else f"MISMATCH ({csv_m15} vs {db_m15})"
    
    print(f"Tahun {y}:")
    print(f"  - Backtest Trades : CSV={csv_trades:>5} | DB={db_trades:>5} -> {status_trade}")
    print(f"  - LLHHBoS Events  : CSV={csv_structs:>5} | DB={db_structs:>5} -> {status_struct}")
    print(f"  - MarketData M15  : CSV={csv_m15:>5} | DB={db_m15:>5} -> {status_m15}")

print("\n=== 2. VALIDASI SAMPEL FIELD (CSV vs DB) ===")
# Ambil 3 baris dari Backtest_Results_2024
b2024 = list(BACKTEST_DIR.glob(f"Backtest_Results_XAUUSD_*2024*.csv"))[0]
with open(b2024, "r", encoding="utf-8", errors="ignore") as f:
    reader = csv.DictReader(f)
    samples = [next(reader) for _ in range(3)]

for s in samples:
    ticket = int(s["Ticket"])
    t_type = s["Type"]
    net_p = float(s["Net_Profit"])
    struct = s.get("EntryStructure", "")
    c_type = s.get("CloseType", "")
    
    cur.execute("""
        SELECT ticket, type, entry_structure, close_type, net_profit, entry_time 
        FROM backtest_results_xauusd 
        WHERE ticket = %s AND type = %s AND csv_filename = %s
    """, (ticket, t_type, b2024.name))
    db_r = cur.fetchone()
    
    if db_r:
        print(f"Ticket #{ticket} ({t_type}):")
        print(f"  CSV : NetProfit={net_p:>8.2f} | Structure={struct:<8} | CloseType={c_type}")
        print(f"  DB  : NetProfit={float(db_r[4]):>8.2f} | Structure={db_r[2]:<8} | CloseType={db_r[3]}")
        match = (abs(net_p - float(db_r[4])) < 0.01 and struct == db_r[2] and c_type == db_r[3])
        print(f"  STATUS: {'100% PERSIS IDENTIK' if match else 'BEDA!'}")

cur.close()
conn.close()
