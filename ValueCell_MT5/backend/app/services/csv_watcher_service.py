"""
CSV Watcher Service - Watches Backtest_result/ and loads updates into Neon PostgreSQL.
"""

import os
import csv
import time
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from app.core.database import get_db_conn, is_pool_ready
from psycopg2.extras import execute_values

logger = logging.getLogger(__name__)


def parse_datetime(val: str) -> Optional[datetime]:
    """Parse MT5 formatted datetime string YYYY.MM.DD HH:MM:SS."""
    if not val or not isinstance(val, str):
        return None
    val = val.strip()
    if val == "" or val.startswith("1970.01.01"):
        return None
    try:
        return datetime.strptime(val, "%Y.%m.%d %H:%M:%S")
    except ValueError:
        try:
            # Fallback for ISO format
            return datetime.fromisoformat(val)
        except ValueError:
            return None


def parse_float(val: str) -> Optional[float]:
    """Safely parse string float."""
    if not val or not isinstance(val, str):
        return None
    val = val.strip()
    if val == "" or val.lower() == "n/a":
        return None
    try:
        return float(val)
    except ValueError:
        return None


def parse_int(val: str) -> Optional[int]:
    """Safely parse string int."""
    if not val or not isinstance(val, str):
        return None
    val = val.strip()
    if val == "" or val.lower() == "n/a":
        return None
    try:
        return int(val)
    except ValueError:
        return None


class CSVWatcherService:
    """
    Watches MT5 backtest output directory.
    - Imports all historical CSV records at startup (if not already loaded).
    - Uses OS file modification time (mtime) and size to incrementally parse new rows.
    """

    def __init__(self, check_interval_seconds: int = 5):
        self.name = "CSVWatcherService"
        self.check_interval = check_interval_seconds
        
        # Set database directory path relative to project
        # Project structure: ValueCell_MT5/backend/app/services/csv_watcher_service.py
        # Backtest_result is located at ValueCell_MT5/../Backtest_result (which is Project MT5/Backtest_result)
        self.backtest_dir = Path(__file__).resolve().parent.parent.parent.parent.parent / "Backtest_result"
        
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        # In-memory cache of file metadata: {file_path: (mtime, size)}
        self._file_metadata: Dict[Path, tuple] = {}
        
        logger.info(f"📊 {self.name} initialized. Target directory: {self.backtest_dir}")

    def start(self):
        """Start the background watcher thread."""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, name="csv-watcher-thread", daemon=True)
        self._thread.start()
        logger.info(f"🚀 {self.name} background thread started.")

    def stop(self):
        """Stop the background watcher thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            logger.info(f"🛑 {self.name} background thread stopped.")

    def _run_loop(self):
        """Main loop that scans files periodically."""
        # Wait a moment for the database pool to be initialized by lifespan
        time.sleep(2.0)
        
        if not is_pool_ready():
            logger.error("❌ Neon DB Pool is not initialized. Watcher thread exiting.")
            return

        # Phase 1: Startup Historical Scan (Option A)
        try:
            logger.info("📅 Starting Option A: Initial scan of all historical CSV files...")
            self._scan_and_load_all()
            logger.info("✅ Option A complete: Historical files successfully loaded/aligned.")
        except Exception as e:
            logger.error(f"❌ Error during initial historical scan: {e}", exc_info=True)

        # Phase 2: Active Watcher Loop
        while self._running:
            try:
                self._check_for_updates()
            except Exception as e:
                logger.error(f"❌ Error in check loop: {e}", exc_info=True)
            time.sleep(self.check_interval)

    def _scan_and_load_all(self):
        """Scans the directory and processes every CSV file."""
        if not self.backtest_dir.exists():
            logger.warning(f"⚠️ Directory {self.backtest_dir} does not exist. Skipping initial scan.")
            return

        # Find all relevant CSV files
        csv_files = list(self.backtest_dir.glob("*.csv"))
        logger.info(f"🔍 Found {len(csv_files)} CSV files in {self.backtest_dir}")

        for file_path in csv_files:
            file_name = file_path.name
            
            # Map filename to table name
            table_name = self._map_filename_to_table(file_name)
            if not table_name:
                continue

            # Update cache metadata to current state
            mtime = file_path.stat().st_mtime
            size = file_path.stat().st_size
            self._file_metadata[file_path] = (mtime, size)

            # Process the file
            self._process_file_incrementally(file_path, table_name)

    def _check_for_updates(self):
        """Scans directory and checks if mtime or size of any file has changed."""
        if not self.backtest_dir.exists():
            return

        csv_files = list(self.backtest_dir.glob("*.csv"))
        for file_path in csv_files:
            file_name = file_path.name
            table_name = self._map_filename_to_table(file_name)
            if not table_name:
                continue

            mtime = file_path.stat().st_mtime
            size = file_path.stat().st_size
            
            # Get cached values
            cached = self._file_metadata.get(file_path)
            
            if cached is None or cached[0] != mtime or cached[1] != size:
                logger.info(f"🔔 File modified: {file_name} (mtime changed or size changed). Processing...")
                self._file_metadata[file_path] = (mtime, size)
                self._process_file_incrementally(file_path, table_name)

    def _map_filename_to_table(self, filename: str) -> Optional[str]:
        """Maps MT5 exported CSV file prefix to Neon table name (without dates)."""
        fn_lower = filename.lower()
        if fn_lower.startswith("llhhbosdata_xauusd"):
            return "llhhbosdata_xauusd"
        elif fn_lower.startswith("backtest_results_xauusd"):
            return "backtest_results_xauusd"
        elif fn_lower.startswith("marketdata_xauusd_m15"):
            return "marketdata_xauusd_m15"
        elif fn_lower.startswith("marketdata_xauusd_h1"):
            return "marketdata_xauusd_h1"
        elif fn_lower.startswith("marketdata_xauusd_h4"):
            return "marketdata_xauusd_h4"
        elif fn_lower.startswith("sessionzone_xauusd"):
            return "sessionzone_xauusd"
        return None

    def _get_last_processed_line(self, filename: str) -> int:
        """Query csv_load_log to get the last line processed for this file."""
        try:
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT rows_loaded FROM csv_load_log WHERE filename = %s",
                        (filename,)
                    )
                    row = cur.fetchone()
                    return row[0] if row else 0
        except Exception as e:
            logger.error(f"Error fetching last processed line for {filename}: {e}")
            return 0

    def _save_last_processed_line(self, filename: str, rows: int):
        """Upsert the csv_load_log to update the last line processed."""
        try:
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO csv_load_log (filename, file_date, rows_loaded, loaded_at, status)
                        VALUES (%s, %s, %s, NOW(), 'success')
                        ON CONFLICT (filename) DO UPDATE 
                        SET rows_loaded = EXCLUDED.rows_loaded, loaded_at = NOW(), status = 'success'
                    """, (filename, datetime.now().date(), rows))
                conn.commit()
        except Exception as e:
            logger.error(f"Error updating csv_load_log for {filename}: {e}")

    def _process_file_incrementally(self, file_path: Path, table_name: str):
        """Reads new rows from file starting from last processed line index and inserts them."""
        filename = file_path.name
        last_line = self._get_last_processed_line(filename)
        
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                
            total_lines = len(lines)
            if total_lines <= last_line:
                # No new lines to process
                return
                
            # Parse headers and data
            # Check if this is LLHHBOSData which contains a title line first
            is_llhhbos = table_name == "llhhbosdata_xauusd"
            
            header_idx = 0
            if is_llhhbos:
                # First line is a title description, header is on line 2 (index 1)
                header_idx = 1
                
            # If file has changed but we have not loaded headers yet, handle it
            if total_lines <= header_idx + 1:
                return

            headers = [h.strip() for h in lines[header_idx].split(",")]
            
            # Start slice of new data lines
            start_idx = max(last_line, header_idx + 1)
            new_lines = lines[start_idx:]
            
            if not new_lines:
                return
                
            # Convert lines to dicts using csv.reader
            reader = csv.reader(new_lines)
            
            parsed_rows = []
            for row in reader:
                if not row or len(row) < len(headers):
                    continue
                # Map row columns to headers
                row_dict = {headers[i]: row[i] for i in range(len(headers))}
                parsed_row = self._parse_row_by_table(row_dict, table_name, filename)
                if parsed_row:
                    parsed_rows.append(parsed_row)
                    
            if parsed_rows:
                logger.info(f"📥 Loading {len(parsed_rows)} new rows from {filename} into {table_name}...")
                self._bulk_insert_rows(parsed_rows, table_name)
                
            # Update log
            self._save_last_processed_line(filename, total_lines)
            
        except Exception as e:
            logger.error(f"❌ Failed to parse/load CSV {filename}: {e}", exc_info=True)
            # Update log as error
            try:
                with get_db_conn() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO csv_load_log (filename, file_date, rows_loaded, loaded_at, status, error_message)
                            VALUES (%s, %s, %s, NOW(), 'error', %s)
                            ON CONFLICT (filename) DO UPDATE 
                            SET status = 'error', error_message = EXCLUDED.error_message, loaded_at = NOW()
                        """, (filename, datetime.now().date(), last_line, str(e)))
                    conn.commit()
            except:
                pass

    def _parse_row_by_table(self, row: Dict[str, str], table_name: str, filename: str) -> Optional[Dict[str, Any]]:
        """Parses a raw CSV row string dictionary into structured SQL field values."""
        try:
            if table_name == "llhhbosdata_xauusd":
                time_val = parse_datetime(row.get("Time"))
                if not time_val:
                    return None
                return {
                    "type": row.get("Type", "").strip(),
                    "direction_action": row.get("Direction/Action", "").strip(),
                    "price": parse_float(row.get("Price")),
                    "time": time_val,
                    "timeframe": row.get("Timeframe", "").strip(),
                    "status": row.get("Status", "").strip(),
                    "previous_price": parse_float(row.get("PreviousPrice")),
                    "previous_time": parse_datetime(row.get("PreviousTime")),
                    "csv_filename": filename
                }
                
            elif table_name == "backtest_results_xauusd":
                entry_time = parse_datetime(row.get("EntryTime"))
                if not entry_time:
                    return None
                return {
                    "ticket": parse_int(row.get("Ticket")),
                    "symbol": row.get("Symbol", "XAUUSD").strip(),
                    "type": row.get("Type", "").strip(),
                    "entry_price": parse_float(row.get("EntryPrice")),
                    "exit_price": parse_float(row.get("ExitPrice")),
                    "sl": parse_float(row.get("SL")),
                    "tp": parse_float(row.get("TP")),
                    "profit": parse_float(row.get("Profit")),
                    "spread_cost": parse_float(row.get("Spread_Cost")),
                    "commission": parse_float(row.get("Commission")),
                    "swap": parse_float(row.get("Swap")),
                    "net_profit": parse_float(row.get("Net_Profit")),
                    "session": row.get("Session", "").strip(),
                    "session_isdst": row.get("Session_IsDST", "NO").strip(),
                    "entry_time": entry_time,
                    "exit_time": parse_datetime(row.get("ExitTime")),
                    "lot_size": parse_float(row.get("LotSize")),
                    "magic_number": parse_int(row.get("MagicNumber")),
                    "timeframe": row.get("Timeframe", "M15").strip(),
                    "status": row.get("Status", "").strip(),
                    "reject_reason": row.get("Reject_Reason", "").strip(),
                    "csv_filename": filename
                }
                
            elif table_name in ("marketdata_xauusd_m15", "marketdata_xauusd_h1", "marketdata_xauusd_h4"):
                time_val = parse_datetime(row.get("Time"))
                if not time_val:
                    return None
                return {
                    "time": time_val,
                    "open": parse_float(row.get("Open")),
                    "high": parse_float(row.get("High")),
                    "low": parse_float(row.get("Low")),
                    "close": parse_float(row.get("Close")),
                    "volume": parse_int(row.get("Volume")),
                    "spread": parse_int(row.get("Spread")),
                    "ema200": parse_float(row.get("EMA200")),
                    "csv_filename": filename
                }
                
            elif table_name == "sessionzone_xauusd":
                start_time = parse_datetime(row.get("StartTime"))
                if not start_time:
                    return None
                return {
                    "start_time": start_time,
                    "end_time": parse_datetime(row.get("EndTime")),
                    "duration_bars": parse_int(row.get("DurationBars")),
                    "session": row.get("Session", "").strip(),
                    "status": row.get("Status", "").strip(),
                    "is_dst": row.get("IsDST", "NO").strip(),
                    "open_price": parse_float(row.get("OpenPrice")),
                    "high_price": parse_float(row.get("HighPrice")),
                    "low_price": parse_float(row.get("LowPrice")),
                    "close_price": parse_float(row.get("ClosePrice")),
                    "range_points": parse_int(row.get("RangePoints")),
                    "csv_filename": filename
                }
        except Exception as e:
            logger.warning(f"Error parsing row from {filename}: {e}")
            return None
        return None

    def _bulk_insert_rows(self, rows: List[Dict[str, Any]], table_name: str):
        """Bulk inserts list of parsed rows into the target Neon Postgres SQL table."""
        if not rows:
            return
            
        columns = list(rows[0].keys())
        query = f"""
            INSERT INTO {table_name} ({', '.join(columns)})
            VALUES %s
        """
        
        # Check table constraints for upsert matching
        if table_name == "llhhbosdata_xauusd":
            query += " ON CONFLICT (time, timeframe, type, price) DO NOTHING"
        elif table_name == "backtest_results_xauusd":
            query += " ON CONFLICT (entry_time, ticket, type) DO NOTHING"
        elif table_name in ("marketdata_xauusd_m15", "marketdata_xauusd_h1", "marketdata_xauusd_h4"):
            query += " ON CONFLICT (time) DO NOTHING"
        elif table_name == "sessionzone_xauusd":
            query += " ON CONFLICT (start_time, session) DO NOTHING"

        # Prepare values tuple list
        values = [tuple(row[col] for col in columns) for row in rows]
        
        try:
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    execute_values(cur, query, values, page_size=2000)
                conn.commit()
            logger.info(f"✅ Loaded {len(rows)} records into table '{table_name}'")
        except Exception as e:
            logger.error(f"❌ Failed to bulk insert into {table_name}: {e}")
            raise e
