"""
Reset & Re-import DB Script
============================
1. TRUNCATE + RESTART IDENTITY semua tabel CSV di Neon PostgreSQL
2. ALTER TABLE backtest_results_xauusd - tambah kolom baru (entry_structure, close_type)
3. Clear csv_load_log (reset tracking watcher)
4. Clear LanceDB (5 koleksi)

Setelah script ini selesai:
  -> Restart backend -> watcher otomatis re-import semua CSV

Usage:
    cd B:\\Project MT5\\ValueCell_MT5
    .\\venv\\Scripts\\python.exe ..\\scratch\\reset_and_reimport_db.py
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

CSV_TABLES = [
    "backtest_results_xauusd",
    "llhhbosdata_xauusd",
    "marketdata_xauusd_m15",
    "marketdata_xauusd_h1",
    "marketdata_xauusd_h4",
    "sessionzone_xauusd",
    "csv_load_log",
]

ALTER_STATEMENTS = [
    "ALTER TABLE backtest_results_xauusd ADD COLUMN IF NOT EXISTS entry_structure VARCHAR(50)",
    "ALTER TABLE backtest_results_xauusd ADD COLUMN IF NOT EXISTS close_type VARCHAR(50)",
]

LANCEDB_TABLES = [
    "historical_structures",
    "market_conditions",
    "news_sentiment_cache",
    "session_patterns",
    "trade_outcomes",
]


def get_conn():
    return psycopg2.connect(
        host=os.getenv("PGHOST"),
        dbname=os.getenv("PGDATABASE"),
        user=os.getenv("PGUSER"),
        password=os.getenv("PGPASSWORD"),
        sslmode=os.getenv("PGSSLMODE", "require"),
        connect_timeout=15,
    )


def truncate_neon(conn):
    print("\n[1/3] Truncate tabel Neon PostgreSQL...")
    with conn.cursor() as cur:
        for table in CSV_TABLES:
            try:
                cur.execute(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE")
                conn.commit()
                print(f"  OK TRUNCATE {table}")
            except psycopg2.errors.UndefinedTable:
                print(f"  SKIP tabel {table} belum ada")
                conn.rollback()
            except Exception as e:
                print(f"  ERR TRUNCATE {table}: {e}")
                conn.rollback()
    print("  -> Selesai truncate.")


def alter_columns(conn):
    print("\n[2/3] ALTER TABLE tambah kolom baru...")
    with conn.cursor() as cur:
        for stmt in ALTER_STATEMENTS:
            try:
                cur.execute(stmt)
                conn.commit()
                col = stmt.split("IF NOT EXISTS")[-1].strip().split()[0]
                print(f"  OK ADD COLUMN {col}")
            except Exception as e:
                print(f"  ERR ALTER: {e}")
                conn.rollback()
    print("  -> ALTER selesai.")


def clear_lancedb():
    print("\n[3/3] Clear LanceDB...")
    if not LANCEDB_PATH.exists():
        print(f"  SKIP LanceDB path tidak ada: {LANCEDB_PATH}")
        return
    try:
        import lancedb
        db = lancedb.connect(str(LANCEDB_PATH))
        existing = db.table_names()
        for tbl in LANCEDB_TABLES:
            if tbl in existing:
                try:
                    db.drop_table(tbl)
                    print(f"  OK Drop LanceDB: {tbl}")
                except Exception as e:
                    print(f"  ERR drop {tbl}: {e}")
            else:
                print(f"  SKIP {tbl} tidak ada")
        print("  -> LanceDB bersih.")
    except ImportError:
        print("  SKIP lancedb tidak terinstall")
    except Exception as e:
        print(f"  ERR LanceDB: {e}")


def main():
    print("=" * 58)
    print("  RESET & RE-IMPORT DB - Project MT5")
    print("=" * 58)
    print(f"  Neon DB: {os.getenv('PGHOST', '(tidak ada)')}")
    print(f"  LanceDB: {LANCEDB_PATH}")
    print()
    print("  PERINGATAN: Semua data CSV di Neon akan DIHAPUS!")
    confirm = input("  Ketik 'ya' untuk lanjut: ").strip().lower()
    if confirm != "ya":
        print("  Dibatalkan.")
        return

    try:
        conn = get_conn()
        print(f"\n  OK Terhubung ke Neon PostgreSQL")
    except Exception as e:
        print(f"\n  ERR Gagal connect Neon: {e}")
        return

    try:
        truncate_neon(conn)
        alter_columns(conn)
    finally:
        conn.close()

    clear_lancedb()

    print("\n" + "=" * 58)
    print("  SELESAI! Langkah selanjutnya:")
    print("  1. Jalankan: .\\start_backend.bat")
    print("  2. Watcher otomatis re-import semua CSV")
    print("  3. Pantau log backend untuk progress sync")
    print("=" * 58)


if __name__ == "__main__":
    main()
