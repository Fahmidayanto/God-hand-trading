import sys
import os
from pathlib import Path
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

backend_dir = Path(__file__).resolve().parent.parent / "ValueCell_MT5" / "backend"
python_dir = Path(__file__).resolve().parent.parent / "ValueCell_MT5" / "python"

from dotenv import load_dotenv
# Load .env candidates
for env_path in [backend_dir / ".env", backend_dir.parent / ".env"]:
    if env_path.exists():
        load_dotenv(env_path, override=True)

# Set DEBUG to false to prevent pydantic error if imported
os.environ["DEBUG"] = "False"

sys.path.insert(0, str(backend_dir))
sys.path.insert(0, str(python_dir))

import psycopg2
from valuecell.knowledge.lance_db import LanceDBManager
import lancedb
import pandas as pd

def get_pg_connection():
    return psycopg2.connect(
        host=os.getenv("PGHOST"),
        database=os.getenv("PGDATABASE"),
        user=os.getenv("PGUSER"),
        password=os.getenv("PGPASSWORD"),
        sslmode="require"
    )

def main():
    print("================================================================")
    print("RESET DATA DATABASE (NEON PG) & LANCEDB (AGUSTUS - SEPTEMBER 2026)")
    print("================================================================")

    tables_config = [
        ("backtest_results_xauusd", "entry_time"),
        ("llhhbosdata_xauusd", "time"),
        ("marketdata_xauusd_m15", "time"),
        ("marketdata_xauusd_h1", "time"),
        ("marketdata_xauusd_h4", "time"),
        ("sessionzone_xauusd", "start_time"),
    ]

    # 1. NEON POSTGRESQL INSPECTION & DELETION
    print("\n--- 1. NEON POSTGRESQL ---")
    total_deleted_pg = 0
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            for t, col in tables_config:
                cur.execute(f"SELECT COUNT(*) FROM {t} WHERE {col} >= '2026-08-01'")
                count_before = cur.fetchone()[0]
                
                cur.execute(f"DELETE FROM {t} WHERE {col} >= '2026-08-01'")
                deleted = cur.rowcount
                total_deleted_pg += deleted
                print(f"  [PG] {t}: {deleted} baris dihapus (sebelumnya ada {count_before} baris >= 2026-08-01)")

            # Reset csv_load_log checkpoint
            cur.execute("DELETE FROM csv_load_log WHERE filename LIKE '%2026-09-04%' OR filename LIKE '%2026-08%' OR loaded_at >= '2026-08-01'")
            deleted_log = cur.rowcount
            print(f"  [PG] csv_load_log: {deleted_log} log checkpoint direset")
        conn.commit()
    finally:
        conn.close()

    print(f"  >> Total baris terhapus di Neon PostgreSQL: {total_deleted_pg}")

    # 2. LANCEDB DELETION
    print("\n--- 2. LANCEDB VECTOR DATABASE ---")
    lancedb_paths = [
        python_dir / "valuecell" / "data" / "lancedb",
        backend_dir.parent / "knowledge" / "lancedb"
    ]

    total_deleted_lance = 0
    for ldb_path in lancedb_paths:
        if not ldb_path.exists():
            continue
        print(f"\n  Memeriksa direktori LanceDB: {ldb_path}")
        try:
            db = lancedb.connect(str(ldb_path))
            raw_tables = db.list_tables()
            table_names = raw_tables if isinstance(raw_tables, list) else getattr(raw_tables, "tables", list(raw_tables))
            
            for tbl_name in table_names:
                try:
                    table = db.open_table(tbl_name)
                    df = table.to_arrow().to_pandas()
                    if df.empty:
                        print(f"    - {tbl_name}: kosong")
                        continue
                    
                    total_rows = len(df)
                    date_cols = [c for c in df.columns if any(k in c.lower() for k in ["timestamp", "time", "date", "created", "entry_time", "start_time"])]
                    
                    if not date_cols:
                        print(f"    - {tbl_name}: {total_rows} total rows (tidak ada kolom waktu)")
                        continue
                        
                    is_target_mask = pd.Series([False] * total_rows, index=df.index)
                    for col in date_cols:
                        str_col = df[col].astype(str)
                        # Match '2026-08', '2026-09', '2026.08', '2026.09'
                        is_target_mask |= str_col.str.contains(r"2026[-.]0[89]", regex=True)
                        # Also match iso dates >= '2026-08-01'
                        is_target_mask |= (str_col >= "2026-08-01") & (str_col < "2026-10-01")
                    
                    count_target = is_target_mask.sum()
                    print(f"    - {tbl_name}: Ditemukan {count_target} baris Agustus-September 2026 (total: {total_rows})")
                    
                    if count_target > 0:
                        df_clean = df[~is_target_mask].reset_index(drop=True)
                        db.drop_table(tbl_name)
                        if df_clean.empty:
                            db.create_table(tbl_name, df.head(0))
                        else:
                            db.create_table(tbl_name, df_clean)
                        print(f"      -> Berhasil menghapus {count_target} baris dari {tbl_name}")
                        total_deleted_lance += count_target
                except Exception as e:
                    print(f"      [Error] {tbl_name}: {e}")
        except Exception as e:
            print(f"    [Error connecting to LanceDB]: {e}")

    print(f"\n  >> Total baris terhapus di LanceDB: {total_deleted_lance}")

    # 3. VERIFIKASI AKHIR
    print("\n--- 3. VERIFIKASI PASCA-RESET (STATUS >= 2026-08-01) ---")
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            for t, col in tables_config:
                cur.execute(f"SELECT COUNT(*) FROM {t} WHERE {col} >= '2026-08-01'")
                remaining = cur.fetchone()[0]
                status_icon = "✅" if remaining == 0 else "❌"
                print(f"  {status_icon} Neon {t}: {remaining} sisa baris >= 2026-08-01")
    finally:
        conn.close()

    mgr = LanceDBManager(str(python_dir / "valuecell" / "data" / "lancedb"))
    for col_name in ["historical_structures", "trade_outcomes"]:
        try:
            tbl = mgr.db.open_table(col_name)
            df = tbl.to_arrow().to_pandas()
            date_cols = [c for c in df.columns if "timestamp" in c.lower() or "time" in c.lower()]
            found = 0
            for col in date_cols:
                str_col = df[col].astype(str)
                found += str_col.str.contains(r"2026[-.]0[89]", regex=True).sum()
            status_icon = "✅" if found == 0 else "❌"
            print(f"  {status_icon} LanceDB {col_name}: {found} sisa baris Agustus-September 2026 (total tabel: {len(df)})")
        except Exception as e:
            print(f"  ⚠️ LanceDB {col_name}: {e}")

    print("\n[SELESAI] Reset Database & LanceDB untuk data Agustus - September 2026 berhasil.")

if __name__ == "__main__":
    main()

