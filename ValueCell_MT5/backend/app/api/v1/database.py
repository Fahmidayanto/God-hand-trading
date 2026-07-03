import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from app.core.database import get_db_conn

logger = logging.getLogger(__name__)
router = APIRouter()

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
        # LanceDB path relative to this file
        base_dir = Path(__file__).parent.parent.parent.parent
        lancedb_path = base_dir / "python" / "valuecell" / "data" / "lancedb"
        
        if lancedb_path.exists() and (lancedb_path / "historical_structures.lance").exists():
            import lancedb
            db = lancedb.connect(str(lancedb_path))
            lancedb_active = True
            for table_name in db.table_names():
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
