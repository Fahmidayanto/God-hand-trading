"""
Truncate 2026 Data from Neon DB (PostgreSQL) and LanceDB
"""

import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Force UTF-8 stdout encoding for Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# Setup paths
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
PYTHON_DIR = PROJECT_ROOT / "python"

if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("truncate_2026_data")

# Load environment
for env_candidate in [PROJECT_ROOT / ".env", PYTHON_DIR / "valuecell" / ".env"]:
    if env_candidate.exists():
        load_dotenv(env_candidate)

import psycopg2
import lancedb
import pandas as pd

def get_neon_conn():
    host = os.getenv("PGHOST")
    dbname = os.getenv("PGDATABASE")
    user = os.getenv("PGUSER")
    password = os.getenv("PGPASSWORD")
    sslmode = os.getenv("PGSSLMODE", "require")

    if not host or not dbname or not user:
        raise ValueError("Neon DB credentials not fully configured in environment")

    return psycopg2.connect(
        host=host,
        database=dbname,
        user=user,
        password=password,
        sslmode=sslmode
    )

def truncate_neon_2026():
    logger.info("==================================================")
    logger.info("STARTING NEON DB 2026 TRUNCATION/DELETION")
    logger.info("==================================================")

    tables_config = [
        ("llhhbosdata_xauusd", "time", "time >= '2026-01-01' AND time < '2027-01-01'"),
        ("backtest_results_xauusd", "entry_time", "entry_time >= '2026-01-01' AND entry_time < '2027-01-01'"),
        ("marketdata_xauusd_m15", "time", "time >= '2026-01-01' AND time < '2027-01-01'"),
        ("marketdata_xauusd_h1", "time", "time >= '2026-01-01' AND time < '2027-01-01'"),
        ("marketdata_xauusd_h4", "time", "time >= '2026-01-01' AND time < '2027-01-01'"),
        ("sessionzone_xauusd", "start_time", "start_time >= '2026-01-01' AND start_time < '2027-01-01'"),
        ("csv_load_log", "filename / loaded_at", "filename LIKE '%_2026-%' OR loaded_at >= '2026-01-01'")
    ]

    total_deleted_neon = 0

    try:
        conn = get_neon_conn()
        cur = conn.cursor()

        for table_name, time_col, where_clause in tables_config:
            count_sql = f"SELECT COUNT(*) FROM {table_name} WHERE {where_clause};"
            delete_sql = f"DELETE FROM {table_name} WHERE {where_clause};"

            try:
                cur.execute(count_sql)
                count_before = cur.fetchone()[0]
                logger.info(f"Neon [{table_name}]: Found {count_before:,} rows for year 2026")

                if count_before > 0:
                    cur.execute(delete_sql)
                    deleted_count = cur.rowcount
                    conn.commit()
                    logger.info(f"Neon [{table_name}]: Successfully deleted {deleted_count:,} rows")
                    total_deleted_neon += deleted_count
                else:
                    logger.info(f"Neon [{table_name}]: No 2026 rows to delete")
            except Exception as e:
                conn.rollback()
                logger.error(f"Error truncating Neon table {table_name}: {e}")

        cur.close()
        conn.close()
        logger.info(f"TOTAL NEON DB 2026 ROWS DELETED: {total_deleted_neon:,}")
    except Exception as e:
        logger.error(f"Connection to Neon DB failed: {e}")

def truncate_lancedb_2026():
    logger.info("==================================================")
    logger.info("STARTING LANCEDB 2026 TRUNCATION/DELETION")
    logger.info("==================================================")

    possible_paths = [
        PYTHON_DIR / "valuecell" / "data" / "lancedb",
        PROJECT_ROOT / "lancedb",
        Path(os.environ.get("USERPROFILE", "")) / ".valuecell" / "lancedb" if os.environ.get("USERPROFILE") else None
    ]

    valid_paths = [p for p in possible_paths if p and p.exists()]
    if not valid_paths:
        logger.warning("No valid LanceDB directory found. Skipping LanceDB truncation.")
        return

    total_deleted_lance = 0

    for db_path in valid_paths:
        logger.info(f"Opening LanceDB at: {db_path}")
        try:
            db = lancedb.connect(str(db_path))
            tables = db.list_tables()
            table_names = tables if isinstance(tables, list) else getattr(tables, "tables", list(tables))

            logger.info(f"Found LanceDB tables: {table_names}")

            for tbl_name in table_names:
                try:
                    table = db.open_table(tbl_name)
                    # Use to_arrow().to_pandas() for compatibility
                    df = table.to_arrow().to_pandas()

                    if df.empty:
                        logger.info(f"LanceDB [{tbl_name}]: Table is empty")
                        continue

                    total_rows = len(df)
                    date_cols = [c for c in df.columns if any(k in c.lower() for k in ["time", "date", "created"])]

                    is_2026_mask = pd.Series([False] * total_rows, index=df.index)

                    for col in date_cols:
                        str_col = df[col].astype(str)
                        is_2026_mask |= str_col.str.contains("2026")

                    count_2026 = is_2026_mask.sum()
                    logger.info(f"LanceDB [{tbl_name}]: Found {count_2026:,} rows for year 2026 out of {total_rows:,} total rows")

                    if count_2026 > 0:
                        df_clean = df[~is_2026_mask].reset_index(drop=True)
                        if df_clean.empty:
                            db.drop_table(tbl_name)
                            db.create_table(tbl_name, df.head(0))
                        else:
                            db.drop_table(tbl_name)
                            db.create_table(tbl_name, df_clean)

                        logger.info(f"LanceDB [{tbl_name}]: Successfully removed {count_2026:,} 2026 entries")
                        total_deleted_lance += count_2026
                    else:
                        logger.info(f"LanceDB [{tbl_name}]: No 2026 entries found")

                except Exception as e:
                    logger.error(f"Error cleaning LanceDB table {tbl_name}: {e}")

        except Exception as e:
            logger.error(f"Error connecting to LanceDB at {db_path}: {e}")

    logger.info(f"TOTAL LANCEDB 2026 ENTRIES DELETED: {total_deleted_lance:,}")

if __name__ == "__main__":
    truncate_neon_2026()
    truncate_lancedb_2026()
