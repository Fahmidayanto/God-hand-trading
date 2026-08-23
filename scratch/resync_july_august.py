import sys
import os
from pathlib import Path
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

backend_dir = Path("b:/Project MT5/ValueCell_MT5/backend")
python_dir = Path("b:/Project MT5/ValueCell_MT5/python")

from dotenv import load_dotenv
load_dotenv(backend_dir / ".env")

sys.path.insert(0, str(backend_dir))
sys.path.insert(0, str(python_dir))

from app.core.database import get_db_conn, init_db_pool
from valuecell.knowledge.lance_db import LanceDBManager
from app.services.csv_watcher_service import CSVWatcherService

def main():
    print("=== PROSES HAPUS & INSERT ULANG DATA JULI - AGUSTUS 2026 ===")
    init_db_pool()

    # 1. Hapus dari Neon PostgreSQL
    print("\n[1/3] Menghapus data Juli - Agustus 2026 dari Neon Database...")
    tables_to_clean = [
        ("backtest_results_xauusd", "entry_time"),
        ("llhhbosdata_xauusd", "time"),
        ("marketdata_xauusd_m15", "time"),
        ("marketdata_xauusd_h1", "time"),
        ("marketdata_xauusd_h4", "time"),
        ("sessionzone_xauusd", "start_time"),
    ]

    with get_db_conn() as conn:
        with conn.cursor() as cur:
            for t, col in tables_to_clean:
                cur.execute(f"DELETE FROM {t} WHERE {col} >= '2026-07-01'")
                print(f"  - {t}: {cur.rowcount} baris dihapus")
            
            # Reset checkpoint log untuk file 2026-08-19
            cur.execute("DELETE FROM csv_load_log WHERE filename LIKE '%2026-08-19%'")
            print(f"  - csv_load_log: {cur.rowcount} log checkpoint direset")
        conn.commit()
    print("✅ Selesai menghapus dari Neon Database.")

    # 2. Hapus dari LanceDB
    print("\n[2/3] Menghapus data Juli - Agustus 2026 dari LanceDB...")
    lancedb_path = python_dir / "valuecell" / "data" / "lancedb"
    mgr = LanceDBManager(str(lancedb_path))
    
    # Clean historical_structures
    try:
        tbl_hs = mgr.db.open_table("historical_structures")
        before_hs = tbl_hs.count_rows()
        tbl_hs.delete("timestamp >= '2026-07-01'")
        after_hs = tbl_hs.count_rows()
        print(f"  - historical_structures: {before_hs - after_hs} baris dihapus (sisa: {after_hs})")
    except Exception as e:
        print(f"  - historical_structures delete warning: {e}")

    # Clean trade_outcomes
    try:
        tbl_to = mgr.db.open_table("trade_outcomes")
        before_to = tbl_to.count_rows()
        tbl_to.delete("timestamp >= '2026-07-01'")
        after_to = tbl_to.count_rows()
        print(f"  - trade_outcomes: {before_to - after_to} baris dihapus (sisa: {after_to})")
    except Exception as e:
        print(f"  - trade_outcomes delete warning: {e}")
    print("✅ Selesai menghapus dari LanceDB.")

    # 3. Insert Ulang via CSVWatcherService
    print("\n[3/3] Membaca & Memasukkan Ulang CSV ke Neon DB & LanceDB...")
    watcher = CSVWatcherService()
    watcher.lancedb = mgr
    watcher._scan_and_load_all()
    print("✅ Selesai Sinkronisasi & Insert Ulang.")

    # 4. Verifikasi Akhir
    print("\n=== VERIFIKASI HASIL AKHIR ===")
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            for t, col in tables_to_clean:
                cur.execute(f"SELECT COUNT(*), MIN({col}), MAX({col}) FROM {t} WHERE {col} >= '2026-07-01'")
                r = cur.fetchone()
                print(f"  - Neon {t} (Juli-Agustus 2026): {r[0]} baris (Range: {r[1]} s/d {r[2]})")

    for col_name in ["historical_structures", "trade_outcomes"]:
        tbl = mgr.db.open_table(col_name)
        print(f"  - LanceDB {col_name}: Total {tbl.count_rows()} records")

if __name__ == "__main__":
    main()
