import os
import logging
import csv
import io
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Query, HTTPException, Request
from pydantic import BaseModel
from app.core.database import get_db_conn
from app.config import get_settings
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter()

def parse_dt(val):
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    val_str = str(val).replace("T", " ").replace("Z", "")
    if "-" in val_str and "." in val_str:
        val_str = val_str.split(".")[0]
    try:
        return datetime.strptime(val_str, "%Y-%m-%d %H:%M:%S")
    except Exception:
        try:
            return datetime.strptime(val_str, "%Y.%m.%d %H:%M:%S")
        except Exception:
            try:
                return datetime.strptime(val_str, "%Y-%m-%d")
            except Exception:
                return val

def parse_float(val):
    if val is None:
        return None
    try:
        return round(float(val), 2)
    except Exception:
        return val

def parse_int(val):
    if val is None:
        return None
    try:
        return int(val)
    except Exception:
        return val

def check_last_row_exists(fp: Path, table_name: str) -> bool:
    try:
        with open(fp, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            if len(lines) <= 1:
                return True  # Empty or just header
            last_line = lines[-1].strip()
            header_line = lines[0].strip()
            
        import csv
        import io
        cols = next(csv.reader(io.StringIO(header_line)))
        vals = next(csv.reader(io.StringIO(last_line)))
        
        row_dict = dict(zip(cols, vals))
        
        conditions = []
        params = []
        
        if table_name == "llhhbosdata_xauusd":
            conditions = ["time = %s", "timeframe = %s", "type = %s", "price = %s"]
            params = [parse_dt(row_dict.get("time")), row_dict.get("timeframe"), row_dict.get("type"), parse_float(row_dict.get("price"))]
        elif table_name == "backtest_results_xauusd":
            conditions = ["entry_time = %s", "ticket = %s", "type = %s"]
            params = [parse_dt(row_dict.get("entry_time")), parse_int(row_dict.get("ticket")), row_dict.get("type")]
        elif table_name in ("marketdata_xauusd_m15", "marketdata_xauusd_h1", "marketdata_xauusd_h4"):
            conditions = ["time = %s"]
            params = [parse_dt(row_dict.get("time"))]
        elif table_name == "sessionzone_xauusd":
            conditions = ["start_time = %s", "session = %s"]
            params = [parse_dt(row_dict.get("start_time")), row_dict.get("session")]
            
        if not conditions:
            return True
            
        query = f"SELECT EXISTS(SELECT 1 FROM {table_name} WHERE {' AND '.join(conditions)});"
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.fetchone()[0]
    except Exception as e:
        logger.error(f"Error checking last row for {fp.name}: {e}")
        return False

def get_csv_watch_path() -> Optional[Path]:
    settings = get_settings()
    candidates = []
    if settings.CSV_WATCH_PATH:
        candidates.append(Path(settings.CSV_WATCH_PATH))

    here = Path(__file__).resolve()
    candidates.extend([
        here.parents[5] / "Backtest_result",  # repo root when file is backend/app/api/v1/database.py
        Path.cwd() / "Backtest_result",
    ])

    for path in candidates:
        if path.exists():
            return path
    return candidates[0] if candidates else None

def map_filename_to_table(filename: str) -> Optional[str]:
    fn_lower = filename.lower()
    if fn_lower.startswith("llhhbosdata_xauusd"):
        return "llhhbosdata_xauusd"
    if fn_lower.startswith("backtest_results_xauusd"):
        return "backtest_results_xauusd"
    if fn_lower.startswith("marketdata_xauusd_m15"):
        return "marketdata_xauusd_m15"
    if fn_lower.startswith("marketdata_xauusd_h1"):
        return "marketdata_xauusd_h1"
    if fn_lower.startswith("marketdata_xauusd_h4"):
        return "marketdata_xauusd_h4"
    if fn_lower.startswith("sessionzone_xauusd"):
        return "sessionzone_xauusd"
    return None

def row_get(row: Dict[str, Any], key: str):
    if key in row:
        return row[key]
    key_lower = key.lower()
    key_compact = re.sub(r"[^a-z0-9]", "", key_lower)
    for row_key, value in row.items():
        if row_key is None:
            continue
        row_key_lower = row_key.lower()
        row_key_compact = re.sub(r"[^a-z0-9]", "", row_key_lower)
        if row_key_lower == key_lower or row_key_compact == key_compact:
            return value
    return None

def filename_year(filename: str) -> Optional[int]:
    match = re.search(r"_(\d{4})-\d{2}-\d{2}\.csv$", filename)
    return int(match.group(1)) if match else None

def unique_cols_for_table(table_name: str) -> List[str]:
    if table_name == "llhhbosdata_xauusd":
        return ["time", "timeframe", "type", "price"]
    if table_name == "backtest_results_xauusd":
        return ["entry_time", "ticket", "type"]
    if table_name in ("marketdata_xauusd_m15", "marketdata_xauusd_h1", "marketdata_xauusd_h4"):
        return ["time"]
    if table_name == "sessionzone_xauusd":
        return ["start_time", "session"]
    return []

def key_tuple_for_row(row_dict: Dict[str, Any], unique_cols: List[str]):
    vals = []
    for col in unique_cols:
        v = row_get(row_dict, col)
        if col in ("time", "entry_time", "start_time"):
            vals.append(parse_dt(v))
        elif col in ("price", "entry_price", "exit_price", "sl", "tp"):
            vals.append(parse_float(v))
        elif col in ("ticket", "magic_number"):
            vals.append(parse_int(v))
        else:
            vals.append(v)
    return tuple(vals)

def count_existing_keys(table_name: str, rows: List[Dict[str, Any]]) -> int:
    unique_cols = unique_cols_for_table(table_name)
    if not unique_cols or not rows:
        return 0

    keys = [key_tuple_for_row(row, unique_cols) for row in rows]
    existing_keys = set()
    cols_str = ", ".join(unique_cols)
    placeholders = ", ".join(["%s"] * len(unique_cols))

    with get_db_conn() as conn:
        with conn.cursor() as cur:
            for i in range(0, len(keys), 1000):
                batch = keys[i:i + 1000]
                if len(unique_cols) == 1:
                    query_placeholders = ", ".join(["%s"] * len(batch))
                    query = f"SELECT {cols_str} FROM {table_name} WHERE {cols_str} IN ({query_placeholders});"
                    params = [key[0] for key in batch]
                else:
                    query_placeholders = ", ".join([f"({placeholders})" for _ in batch])
                    query = f"SELECT {cols_str} FROM {table_name} WHERE ({cols_str}) IN ({query_placeholders});"
                    params = []
                    for key in batch:
                        params.extend(key)
                cur.execute(query, params)
                for db_row in cur.fetchall():
                    existing_keys.add(
                        tuple(
                            parse_dt(val) if isinstance(val, datetime)
                            else parse_float(val) if hasattr(val, "as_tuple")
                            else val
                            for val in db_row
                        )
                    )
    return sum(1 for key in keys if key in existing_keys)

def read_csv_data_rows(fp: Path, table_name: str) -> List[Dict[str, Any]]:
    header_idx = 1 if table_name == "llhhbosdata_xauusd" else 0
    with open(fp, "r", encoding="utf-8", errors="ignore") as f:
        lines = [line for line in f.readlines() if line.strip()]
    if len(lines) <= header_idx + 1:
        return []
    csv_data = "".join(lines[header_idx:])
    return [row for row in csv.DictReader(io.StringIO(csv_data))]

def csv_data_info(fp: Path, table_name: str):
    header_idx = 1 if table_name == "llhhbosdata_xauusd" else 0
    time_col = "time"
    if table_name == "backtest_results_xauusd":
        time_col = "entry_time"
    elif table_name == "sessionzone_xauusd":
        time_col = "start_time"

    with open(fp, "r", encoding="utf-8", errors="ignore") as f:
        lines = [line for line in f.readlines() if line.strip()]

    if len(lines) <= header_idx + 1:
        return 0, None, None

    headers = next(csv.reader(io.StringIO(lines[header_idx])))
    data_lines = lines[header_idx + 1:]
    first_row = dict(zip(headers, next(csv.reader(io.StringIO(data_lines[0])))))
    last_row = dict(zip(headers, next(csv.reader(io.StringIO(data_lines[-1])))))
    return len(data_lines), parse_dt(row_get(first_row, time_col)), parse_dt(row_get(last_row, time_col))

# List of allowed table names to prevent SQL Injection
ALLOWED_TABLES = [
    "llhhbosdata_xauusd",
    "backtest_results_xauusd",
    "marketdata_xauusd_m15",
    "marketdata_xauusd_h1",
    "marketdata_xauusd_h4",
    "sessionzone_xauusd",
    "csv_load_log"
]

class NeonStats(BaseModel):
    llhhbosdata_xauusd: int = 0
    backtest_results_xauusd: int = 0
    csv_load_log: int = 0
    marketdata_xauusd_m15: int = 0
    marketdata_xauusd_h1: int = 0
    marketdata_xauusd_h4: int = 0
    sessionzone_xauusd: int = 0

class LanceDBCollectionStats(BaseModel):
    name: str
    count: int

class DBStatsResponse(BaseModel):
    neon_stats: NeonStats
    lancedb_active: bool
    lancedb_collections: List[LanceDBCollectionStats]

class TablePreviewResponse(BaseModel):
    table: str
    columns: List[str]
    rows: List[Dict[str, Any]]

class LancePreviewResponse(BaseModel):
    collection: str
    columns: List[str]
    rows: List[Dict[str, Any]]

ALLOWED_LANCE_COLLECTIONS = [
    "historical_structures",
    "market_conditions",
    "session_patterns",
    "trade_outcomes",
    "news_sentiment_cache",
]

class CsvSyncStatusItem(BaseModel):
    filename: str
    table_name: str
    local_rows: int
    db_rows: int
    status: str
    loaded_at: Optional[str] = None
    is_up_to_date: bool

class SyncDiffResponse(BaseModel):
    type: str  # "csv_extra" | "db_extra" | "synced"
    count: int
    columns: List[str]
    rows: List[Dict[str, Any]]

@router.get("/stats", response_model=DBStatsResponse)
def get_database_stats():
    neon_counts = {}
    
    # 1. Fetch NeonDB Row Counts
    try:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                for table in ALLOWED_TABLES:
                    cur.execute(f"SELECT COUNT(*) FROM {table};")
                    count = cur.fetchone()[0]
                    neon_counts[table] = count
    except Exception as exc:
        logger.error(f"[DB] Error fetching NeonDB row counts: {exc}")
        # Fallback default values
        for table in ALLOWED_TABLES:
            neon_counts[table] = 0

    # 2. Check LanceDB status
    lancedb_active = False
    lancedb_collections = []
    
    try:
        # LanceDB path: this file lives at .../ValueCell_MT5/backend/app/api/v1/database.py
        # Walk 5 levels up to reach the ValueCell_MT5 root, then into python/valuecell/data/lancedb.
        base_dir = Path(__file__).parents[4]
        lancedb_path = base_dir / "python" / "valuecell" / "data" / "lancedb"
        
        if lancedb_path.exists() and (lancedb_path / "historical_structures.lance").exists():
            import lancedb
            db = lancedb.connect(str(lancedb_path))
            lancedb_active = True
            for table_name in db.list_tables():
                tbl = db.open_table(table_name)
                count = tbl.count_rows()
                lancedb_collections.append(
                    LanceDBCollectionStats(name=table_name, count=count)
                )
    except Exception as exc:
        logger.warning(f"[DB] LanceDB is offline or not found: {exc}")
        lancedb_active = False
        lancedb_collections = []

    return DBStatsResponse(
        neon_stats=NeonStats(**neon_counts),
        lancedb_active=lancedb_active,
        lancedb_collections=lancedb_collections
    )

@router.get("/neon/preview", response_model=TablePreviewResponse)
def preview_table(
    table: str = Query(..., description="Name of the table to preview"),
    limit: int = Query(50, ge=1, le=100, description="Max rows to return")
):
    if table not in ALLOWED_TABLES:
        raise HTTPException(status_code=400, detail="Invalid table name")

    try:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                # Fetch latest 50 rows based on timestamp/time or loaded_at column
                sort_col = "id"
                if table == "csv_load_log":
                    sort_col = "id"
                elif table in ("llhhbosdata_xauusd", "sessionzone_xauusd", "marketdata_xauusd_m15", "marketdata_xauusd_h1", "marketdata_xauusd_h4"):
                    sort_col = "time"
                elif table == "backtest_results_xauusd":
                    sort_col = "entry_time"
                    
                cur.execute(f"SELECT * FROM {table} ORDER BY {sort_col} DESC LIMIT %s;", (limit,))
                rows = cur.fetchall()
                colnames = [desc[0] for desc in cur.description]
                
                formatted_rows = []
                for row in rows:
                    row_dict = {}
                    for col, val in zip(colnames, row):
                        # Format datetime values for JSON serialization
                        if hasattr(val, "isoformat"):
                            row_dict[col] = val.isoformat()
                        else:
                            row_dict[col] = val
                    formatted_rows.append(row_dict)
                    
                return TablePreviewResponse(
                    table=table,
                    columns=colnames,
                    rows=formatted_rows
                )
    except Exception as exc:
        logger.error(f"[DB] Error previewing table {table}: {exc}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(exc)}")


@router.get("/lancedb/preview", response_model=LancePreviewResponse)
def preview_lancedb_collection(
    collection: str = Query(..., description="Name of the LanceDB collection to preview"),
    limit: int = Query(30, ge=1, le=500, description="Max rows to return"),
):
    """Return up to `limit` rows from a LanceDB collection with full vector payload."""
    if collection not in ALLOWED_LANCE_COLLECTIONS:
        raise HTTPException(status_code=400, detail="Invalid collection name")

    base_dir = Path(__file__).parents[4]
    lancedb_path = base_dir / "python" / "valuecell" / "data" / "lancedb"

    if not lancedb_path.exists():
        raise HTTPException(status_code=503, detail="LanceDB folder not found on server")

    try:
        import lancedb
        import pandas as pd  # noqa: F401  (lancedb returns pandas frames)

        db = lancedb.connect(str(lancedb_path))

        if collection not in db.list_tables():
            raise HTTPException(
                status_code=404,
                detail=f"Collection '{collection}' not found in LanceDB",
            )

        tbl = db.open_table(collection)
        # NOTE: lancedb 0.33 calls LanceDataset.to_pandas() which was removed in
        # newer pylance. Use search().limit() path which works across versions.
        df = tbl.search().limit(limit).to_pandas()
        # Vector payload not needed in inspector view — drop to keep payload small.
        if "vector" in df.columns:
            df = df.drop(columns=["vector"])

        # Serialize: numpy arrays (vector), datetime, numpy scalars → JSON-safe types
        formatted_rows: List[Dict[str, Any]] = []
        for _, row in df.iterrows():
            row_dict: Dict[str, Any] = {}
            for col in df.columns:
                val = row[col]
                if hasattr(val, "tolist"):
                    row_dict[col] = val.tolist()
                elif hasattr(val, "isoformat"):
                    row_dict[col] = val.isoformat()
                else:
                    # pandas may yield numpy scalars; bool/int/float pass through fine
                    row_dict[col] = val.item() if hasattr(val, "item") else val
            formatted_rows.append(row_dict)

        return LancePreviewResponse(
            collection=collection,
            columns=list(df.columns),
            rows=formatted_rows,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"[DB] Error previewing LanceDB collection {collection}: {exc}")
        raise HTTPException(status_code=500, detail=f"LanceDB error: {str(exc)}")


@router.get("/sync-status", response_model=List[CsvSyncStatusItem])
def get_sync_status():
    """Compares CSV files in the watch path with imported rows in Neon DB."""
    watch_path = get_csv_watch_path()
        
    if not watch_path or not watch_path.exists():
        logger.warning(f"[DB] Watch path does not exist: {watch_path}")
        return []
        
    # Get all csv files
    csv_files = sorted(watch_path.glob("*.csv"))
    
    # Get all load log history from Neon DB
    db_logs = {}
    try:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT filename, rows_loaded, status, loaded_at FROM csv_load_log;")
                rows = cur.fetchall()
                for row in rows:
                    filename, rows_loaded, status, loaded_at = row
                    db_logs[filename] = {
                        "rows_loaded": rows_loaded,
                        "status": status,
                        "loaded_at": loaded_at.isoformat() if loaded_at else None
                    }
    except Exception as exc:
        logger.error(f"[DB] Error fetching csv_load_log: {exc}")
        pass
        
    file_infos = []
    for fp in csv_files:
        filename = fp.name
        # Skip summary files
        if "summary" in filename.lower():
            continue
            
        table_name = map_filename_to_table(filename)
            
        if not table_name:
            continue
            
        local_rows = 0
        db_rows = 0
        try:
            local_rows, first_dt, last_dt = csv_data_info(fp, table_name)
        except Exception as e:
            logger.error(f"Error reading CSV info for {filename}: {e}")

        file_infos.append((fp, filename, table_name, local_rows, first_dt, last_dt, db_logs.get(filename)))

    db_counts = {}
    try:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                table_names = sorted({info[2] for info in file_infos})
                for table_name in table_names:
                    ranges = [
                        (filename, first_dt, last_dt)
                        for fp, filename, item_table, local_rows, first_dt, last_dt, db_log in file_infos
                        if item_table == table_name and local_rows and first_dt and last_dt
                    ]
                    if not ranges:
                        continue

                    if table_name.startswith("marketdata_xauusd_"):
                        year_ranges = [(filename, filename_year(filename)) for filename, first_dt, last_dt in ranges]
                        year_ranges = [(filename, year) for filename, year in year_ranges if year]
                        if not year_ranges:
                            continue
                        values_sql = ", ".join(["(%s, %s)"] * len(year_ranges))
                        params = []
                        for filename, year in year_ranges:
                            params.extend([filename, year])
                        cur.execute(
                            f"""
                            WITH ranges(filename, year) AS (
                                VALUES {values_sql}
                            )
                            SELECT r.filename, COUNT(t.*)
                            FROM ranges r
                            LEFT JOIN {table_name} t
                              ON EXTRACT(YEAR FROM t.time)::int = r.year::int
                            GROUP BY r.filename
                            """,
                            params,
                        )
                    else:
                        filenames = [filename for filename, first_dt, last_dt in ranges]
                        values_sql = ", ".join(["%s"] * len(filenames))
                        cur.execute(
                            f"SELECT csv_filename, COUNT(*) FROM {table_name} WHERE csv_filename IN ({values_sql}) GROUP BY csv_filename;",
                            filenames,
                        )
                    for row in cur.fetchall():
                        db_counts[row[0]] = row[1]
    except Exception as exc:
        logger.error(f"[DB] Error counting actual sync rows: {exc}")

    result = []
    for fp, filename, table_name, local_rows, first_dt, last_dt, db_log in file_infos:
        db_rows = db_counts.get(filename)
        
        # If we have a successful sync log, trust its count if it is larger (handles duplicate rows skipped via ON CONFLICT)
        # We only apply this to non-marketdata tables, because marketdata tables query counts by year directly and are always accurate.
        if not table_name.startswith("marketdata_xauusd_"):
            if db_rows is None:
                db_rows = 0
            if db_log and db_log.get("status") == "success":
                header_count = 2 if table_name == "llhhbosdata_xauusd" else 1
                log_data_rows = max(0, db_log.get("rows_loaded", 0) - header_count)
                db_rows = max(db_rows, log_data_rows)
        else:
            if db_rows is None:
                db_rows = 0

        status = db_log["status"] if db_log else ("success" if local_rows == db_rows and local_rows > 0 else "not_synced")
        loaded_at = db_log["loaded_at"] if db_log else None
        
        is_up_to_date = (local_rows == db_rows) and local_rows > 0
        
        result.append(
            CsvSyncStatusItem(
                filename=filename,
                table_name=table_name,
                local_rows=local_rows,
                db_rows=db_rows,
                status=status,
                loaded_at=loaded_at,
                is_up_to_date=is_up_to_date
            )
        )
        
    return result


@router.get("/sync-diff", response_model=SyncDiffResponse)
def get_sync_diff(filename: str = Query(..., description="Name of the CSV file")):
    """Compares CSV rows with database table records based on unique keys."""
    watch_path = get_csv_watch_path()
        
    if not watch_path or not watch_path.exists():
        raise HTTPException(status_code=404, detail="CSV watch path not found")

    file_path = watch_path / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="CSV file not found")
        
    table_name = map_filename_to_table(filename)
        
    if not table_name:
        raise HTTPException(status_code=400, detail="Unsupported file name pattern")
        
    # Count local lines
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception as e:
        logger.error(f"Error reading file {filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to read CSV file: {str(e)}")
        
    header_idx = 1 if table_name == "llhhbosdata_xauusd" else 0

    # If file is empty or just has header
    if len(lines) <= header_idx + 1:
        return SyncDiffResponse(type="synced", count=0, columns=[], rows=[])
        
    # Get columns from header
    header_line = lines[header_idx]
    reader = csv.reader(io.StringIO(header_line))
    columns = next(reader, [])
    
    # Parse all CSV rows
    csv_data = "".join(lines[header_idx:])
    dict_reader = csv.DictReader(io.StringIO(csv_data))
    parsed_rows = [row for row in dict_reader]

    # Define unique columns
    unique_cols = []
    if table_name == "llhhbosdata_xauusd":
        unique_cols = ["time", "timeframe", "type", "price"]
    elif table_name == "backtest_results_xauusd":
        unique_cols = ["entry_time", "ticket", "type"]
    elif table_name in ("marketdata_xauusd_m15", "marketdata_xauusd_h1", "marketdata_xauusd_h4"):
        unique_cols = ["time"]
    elif table_name == "sessionzone_xauusd":
        unique_cols = ["start_time", "session"]
        
    def get_key_tuple(row_dict):
        vals = []
        for col in unique_cols:
            v = row_get(row_dict, col)
            if col in ("time", "entry_time", "start_time"):
                vals.append(parse_dt(v))
            elif col in ("price", "entry_price", "exit_price", "sl", "tp"):
                vals.append(parse_float(v))
            elif col in ("ticket", "magic_number"):
                vals.append(parse_int(v))
            else:
                vals.append(v)
        return tuple(vals)

    if table_name.startswith("marketdata_xauusd_"):
        year = filename_year(filename)
        if year:
            try:
                with get_db_conn() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            f"SELECT time, open, high, low, close, volume, spread, ema200, csv_filename FROM {table_name} WHERE EXTRACT(YEAR FROM time)::int = %s ORDER BY time;",
                            (year,),
                        )
                        db_rows = cur.fetchall()
                        db_colnames = [desc[0] for desc in cur.description]

                csv_by_time = {get_key_tuple(row)[0]: row for row in parsed_rows}
                db_by_time = {row[0]: row for row in db_rows}
                csv_only = [row for key, row in csv_by_time.items() if key not in db_by_time]

                if csv_only:
                    return SyncDiffResponse(
                        type="csv_extra",
                        count=len(csv_only),
                        columns=columns,
                        rows=csv_only[:50],
                    )

                db_only_rows = []
                for key, row in db_by_time.items():
                    if key in csv_by_time:
                        continue
                    row_dict = {}
                    for col, val in zip(db_colnames, row):
                        row_dict[col] = val.isoformat() if hasattr(val, "isoformat") else val
                    db_only_rows.append(row_dict)

                if db_only_rows:
                    return SyncDiffResponse(
                        type="db_extra",
                        count=len(db_only_rows),
                        columns=db_colnames,
                        rows=db_only_rows[:50],
                    )

                return SyncDiffResponse(type="synced", count=0, columns=columns, rows=[])
            except Exception as exc:
                logger.error(f"[DB] Error diffing MarketData year rows: {exc}")
        
    # Limit check range for performance safety on huge files
    csv_rows_to_check = parsed_rows
    if len(parsed_rows) > 5000:
        csv_rows_to_check = parsed_rows[-2000:]
        
    csv_keys = [get_key_tuple(r) for r in csv_rows_to_check]
    
    # Query database in batches using tuple IN
    existing_keys = set()
    cols_str = ", ".join(unique_cols)
    placeholders = ", ".join(["%s"] * len(unique_cols))
    
    batch_size = 1000
    for i in range(0, len(csv_keys), batch_size):
        batch = csv_keys[i:i+batch_size]
        flat_params = []
        if len(unique_cols) == 1:
            tuples_placeholders = ", ".join(["%s"] * len(batch))
            query = f"SELECT {cols_str} FROM {table_name} WHERE {cols_str} IN ({tuples_placeholders});"
            flat_params = [t[0] for t in batch]
        else:
            tuples_placeholders = ", ".join([f"({placeholders})" for _ in batch])
            query = f"SELECT {cols_str} FROM {table_name} WHERE ({cols_str}) IN ({tuples_placeholders});"
            for t in batch:
                flat_params.extend(t)
            
        try:
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, flat_params)
                    db_rows_fetched = cur.fetchall()
                    for r in db_rows_fetched:
                        # Normalize key tuple to matching python types
                        normalized = tuple(
                            parse_dt(val) if isinstance(val, datetime)
                            else parse_float(val) if hasattr(val, "as_tuple") # Decimal
                            else val
                            for val in r
                        )
                        existing_keys.add(normalized)
        except Exception as exc:
            logger.error(f"[DB] Error querying unique keys in diff: {exc}")
            
    # Find CSV rows missing from DB
    missing_csv_rows = []
    for r in parsed_rows:
        key = get_key_tuple(r)
        if key not in existing_keys:
            missing_csv_rows.append(r)
            
    # CASE 1: CSV has missing rows (needs import)
    if len(missing_csv_rows) > 0:
        return SyncDiffResponse(
            type="csv_extra",
            count=len(missing_csv_rows),
            columns=columns,
            rows=missing_csv_rows[:50]
        )
        
    # CASE 2: DB has extra rows for this file
    db_rows_count = 0
    try:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(id) FROM {table_name} WHERE csv_filename = %s;", (filename,))
                db_rows_count = cur.fetchone()[0]
    except Exception as exc:
        logger.error(f"[DB] Error getting actual DB row count: {exc}")
        
    if db_rows_count > len(parsed_rows):
        limit = db_rows_count - len(parsed_rows)
        sort_col = "id"
        if table_name in ("llhhbosdata_xauusd", "sessionzone_xauusd", "marketdata_xauusd_m15", "marketdata_xauusd_h1", "marketdata_xauusd_h4"):
            sort_col = "time"
        elif table_name == "backtest_results_xauusd":
            sort_col = "entry_time"
            
        db_rows_list = []
        colnames = []
        try:
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(f"SELECT * FROM {table_name} WHERE csv_filename = %s ORDER BY {sort_col} DESC LIMIT %s;", (filename, limit))
                    rows = cur.fetchall()
                    colnames = [desc[0] for desc in cur.description]
                    for r in rows:
                        row_dict = {}
                        for col, val in zip(colnames, r):
                            if hasattr(val, "isoformat"):
                                row_dict[col] = val.isoformat()
                            else:
                                row_dict[col] = val
                        db_rows_list.append(row_dict)
        except Exception as exc:
            logger.error(f"[DB] Error querying extra DB rows: {exc}")
            
        return SyncDiffResponse(
            type="db_extra",
            count=len(db_rows_list),
            columns=colnames,
            rows=db_rows_list[:50]
        )
        
    # CASE 3: Synced
    if not table_name.startswith("marketdata_xauusd_"):
        try:
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO csv_load_log (filename, file_date, rows_loaded, loaded_at, status)
                        VALUES (%s, %s, %s, NOW(), 'success')
                        ON CONFLICT (filename) DO UPDATE 
                        SET rows_loaded = EXCLUDED.rows_loaded, loaded_at = NOW(), status = 'success'
                    """, (filename, datetime.now().date(), len(lines)))
                conn.commit()
            logger.info(f"🔄 Auto-healed load log count for {filename} to {len(lines)} because DB is already fully synced.")
        except Exception as exc:
            logger.error(f"[DB] Error auto-healing load log: {exc}")

    return SyncDiffResponse(
        type="synced",
        count=0,
        columns=columns,
        rows=[]
    )


@router.post("/sync")
def trigger_manual_sync(request: Request):
    """Triggers manual CSV synchronization to NeonDB and LanceDB."""
    from fastapi import Request
    try:
        watcher = getattr(request.app.state, "watcher", None)
        if watcher:
            logger.info("[API] Manual sync triggered by user.")
            watcher._scan_and_load_all()
            return {"status": "success", "message": "Synchronization completed successfully."}
        else:
            from app.services.csv_watcher_service import CSVWatcherService
            import sys
            logger.warning("[API] Watcher not active in app state. Running one-off CSVWatcherService scan.")
            temp_watcher = CSVWatcherService()
            try:
                project_root = temp_watcher.backtest_dir.parent
                lancedb_path = project_root / "ValueCell_MT5" / "python" / "valuecell" / "data" / "lancedb"
                py_dir = str(project_root / "ValueCell_MT5" / "python")
                if py_dir not in sys.path:
                    sys.path.insert(0, py_dir)
                from valuecell.knowledge.lance_db import LanceDBManager
                temp_watcher.lancedb = LanceDBManager(str(lancedb_path))
            except Exception as le:
                logger.error(f"Failed to init LanceDB in manual sync: {le}")
            
            temp_watcher._scan_and_load_all()
            return {"status": "success", "message": "One-off sync completed successfully."}
    except Exception as exc:
        logger.error(f"[API] Error during manual sync: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/sync-progress")
def get_sync_progress(request: Request):
    """Get the current background CSV watcher sync progress."""
    watcher = getattr(request.app.state, "watcher", None)
    if watcher:
        return {
            "is_syncing": watcher.is_syncing,
            "percent": watcher.sync_percent,
            "step": watcher.sync_step
        }
    return {"is_syncing": False, "percent": 0, "step": "Watcher offline"}
