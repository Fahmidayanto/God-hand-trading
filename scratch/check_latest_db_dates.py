import sys
import os
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

backend_dir = Path(__file__).resolve().parent.parent / "ValueCell_MT5" / "backend"
python_dir = Path(__file__).resolve().parent.parent / "ValueCell_MT5" / "python"

from dotenv import load_dotenv
for env_path in [backend_dir / ".env", backend_dir.parent / ".env"]:
    if env_path.exists():
        load_dotenv(env_path, override=True)

import psycopg2
import lancedb
import pandas as pd

conn = psycopg2.connect(
    host=os.getenv("PGHOST"),
    database=os.getenv("PGDATABASE"),
    user=os.getenv("PGUSER"),
    password=os.getenv("PGPASSWORD"),
    sslmode="require"
)

tables_config = [
    ("backtest_results_xauusd", "entry_time"),
    ("llhhbosdata_xauusd", "time"),
    ("marketdata_xauusd_m15", "time"),
    ("marketdata_xauusd_h1", "time"),
    ("marketdata_xauusd_h4", "time"),
    ("sessionzone_xauusd", "start_time"),
]

print("=== NEON POSTGRESQL LATEST RECORD STATUS ===")
try:
    with conn.cursor() as cur:
        for t, col in tables_config:
            cur.execute(f"SELECT COUNT(*), MIN({col}), MAX({col}) FROM {t}")
            count, min_t, max_t = cur.fetchone()
            
            cur.execute(f"SELECT COUNT(*) FROM {t} WHERE {col} >= '2026-08-01'")
            count_aug_sep = cur.fetchone()[0]
            
            print(f"Table {t:25}: Total={count:<6} | Latest={str(max_t):<20} | Aug-Sep 2026 Rows={count_aug_sep}")
        
        cur.execute("SELECT filename, rows_loaded, loaded_at FROM csv_load_log ORDER BY loaded_at DESC LIMIT 5")
        rows = cur.fetchall()
        print("\nLast 5 CSV Load Logs:")
        for r in rows:
            print(f"  - {r[0]}: rows={r[1]}, loaded_at={r[2]}")
finally:
    conn.close()

print("\n=== LANCEDB LATEST RECORD STATUS ===")
ldb_path = python_dir / "valuecell" / "data" / "lancedb"
if ldb_path.exists():
    db = lancedb.connect(str(ldb_path))
    raw_tables = db.list_tables()
    table_names = raw_tables if isinstance(raw_tables, list) else getattr(raw_tables, "tables", list(raw_tables))
    for t in table_names:
        tbl = db.open_table(t)
        count = tbl.count_rows()
        df = tbl.to_arrow().to_pandas()
        date_cols = [c for c in df.columns if any(k in c.lower() for k in ["timestamp", "time", "date", "created", "entry_time", "start_time"])]
        latest_val = "N/A"
        aug_sep_count = 0
        if date_cols:
            latest_val = str(df[date_cols[0]].max())
            for col in date_cols:
                str_col = df[col].astype(str)
                aug_sep_count += str_col.str.contains(r"2026[-.]0[89]", regex=True).sum()
        print(f"Collection {t:26}: Total={count:<6} | Latest={latest_val:<25} | Aug-Sep 2026 Records={aug_sep_count}")

