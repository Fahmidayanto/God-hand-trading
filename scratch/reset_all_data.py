"""
Reset All Database & LanceDB Data
"""
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
BACKEND_DIR = PROJECT_ROOT / "ValueCell_MT5" / "backend"
PYTHON_DIR = PROJECT_ROOT / "ValueCell_MT5" / "python"
LANCEDB_PATH = PYTHON_DIR / "valuecell" / "data" / "lancedb"

sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(PYTHON_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

import psycopg2

ALL_TABLES = [
    "backtest_results_xauusd",
    "llhhbosdata_xauusd",
    "marketdata_xauusd_m15",
    "marketdata_xauusd_h1",
    "marketdata_xauusd_h4",
    "sessionzone_xauusd",
    "csv_load_log",
    "realtime_ohlcv",
    "realtime_structures",
    "trades",
    "agent_decisions",
    "state_machine",
    "agent_performance",
    "agent_sentiment_logs",
    "cross_validation"
]

LANCEDB_TABLES = [
    "historical_structures",
    "market_conditions",
    "news_sentiment_cache",
    "session_patterns",
    "trade_outcomes",
]

def reset_neon():
    print("[1/2] Mengosongkan tabel di Neon PostgreSQL...")
    conn = psycopg2.connect(
        host=os.getenv("PGHOST"),
        dbname=os.getenv("PGDATABASE"),
        user=os.getenv("PGUSER"),
        password=os.getenv("PGPASSWORD"),
        sslmode=os.getenv("PGSSLMODE", "require"),
        connect_timeout=15,
    )
    with conn.cursor() as cur:
        for t in ALL_TABLES:
            try:
                cur.execute(f"TRUNCATE TABLE {t} RESTART IDENTITY CASCADE")
                conn.commit()
                print(f"  OK TRUNCATE {t}")
            except psycopg2.errors.UndefinedTable:
                conn.rollback()
                print(f"  SKIP {t} (tabel belum ada)")
            except Exception as e:
                conn.rollback()
                print(f"  ERR TRUNCATE {t}: {e}")
    conn.close()
    print("  -> Neon PostgreSQL bersih.")

def reset_lancedb():
    print("\n[2/2] Mengosongkan LanceDB...")
    if not LANCEDB_PATH.exists():
        print("  SKIP LanceDB direktori belum ada")
        return
    try:
        import lancedb
        db = lancedb.connect(str(LANCEDB_PATH))
        tables = db.table_names() if hasattr(db, "table_names") else db.list_tables()
        for tbl in LANCEDB_TABLES:
            if tbl in tables:
                try:
                    db.drop_table(tbl)
                    print(f"  OK Drop LanceDB: {tbl}")
                except Exception as e:
                    print(f"  ERR drop {tbl}: {e}")
            else:
                print(f"  SKIP {tbl} (belum ada)")
        print("  -> LanceDB bersih.")
    except Exception as e:
        print(f"  ERR LanceDB: {e}")

if __name__ == "__main__":
    reset_neon()
    reset_lancedb()
    print("\n=== SEMUA DATA DATABASE & LANCE DB TELAH BERHASIL DI-RESET ===")
