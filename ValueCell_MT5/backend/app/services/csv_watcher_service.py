"""
CSV Watcher Service - Watches Backtest_result/ and loads updates into Neon PostgreSQL.
"""

import os
import sys
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
        self.lancedb = None
        
        # In-memory cache of file metadata: {file_path: (mtime, size)}
        self._file_metadata: Dict[Path, tuple] = {}
        
        # ponytail: Sync monitoring variables
        self.is_syncing = False
        self.sync_percent = 0
        self.sync_step = "Idle"
        
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

        # Initialize LanceDB connection
        try:
            project_root = self.backtest_dir.parent
            lancedb_path = project_root / "ValueCell_MT5" / "python" / "valuecell" / "data" / "lancedb"
            py_dir = str(project_root / "ValueCell_MT5" / "python")
            if py_dir not in sys.path:
                sys.path.insert(0, py_dir)
                
            from valuecell.knowledge.lance_db import LanceDBManager
            self.lancedb = LanceDBManager(str(lancedb_path))
            logger.info("✅ CSVWatcherService connected to LanceDB successfully.")
        except Exception as e:
            logger.error(f"❌ CSVWatcherService failed to connect to LanceDB: {e}", exc_info=True)

        # Phase 1: Startup Historical Scan (Option A)
        try:
            logger.info("📅 Starting Option A: Initial scan of all historical CSV files...")
            self._scan_and_load_all()
            logger.info("✅ Option A complete: Historical files successfully loaded/aligned.")
        except Exception as e:
            logger.error(f"❌ Error during initial historical scan: {e}", exc_info=True)

        # Option B: Active Watcher Loop (periodically check for updates)
        logger.info(f"👀 Option B: Starting active directory watcher. Interval: {self.check_interval}s...")
        while self._running:
            try:
                self._check_for_updates()
            except Exception as e:
                logger.error(f"❌ Error checking CSV updates: {e}", exc_info=True)
            time.sleep(self.check_interval)

    def _scan_and_load_all(self):
        """Scans the directory and processes every CSV file."""
        if not self.backtest_dir.exists():
            logger.warning(f"⚠️ Directory {self.backtest_dir} does not exist. Skipping initial scan.")
            return

        # ponytail: set sync status tracking
        self.is_syncing = True
        self.sync_percent = 0
        self.sync_step = "Scanning directory..."

        # Find all relevant CSV files
        csv_files = list(self.backtest_dir.glob("*.csv"))
        valid_files = [fp for fp in csv_files if self._map_filename_to_table(fp.name)]
        total = len(valid_files)

        logger.info(f"🔍 Found {total} valid CSV files to sync in {self.backtest_dir}")

        if total == 0:
            self.is_syncing = False
            self.sync_percent = 100
            self.sync_step = "No files to sync"
            return

        try:
            for idx, file_path in enumerate(valid_files):
                file_name = file_path.name
                table_name = self._map_filename_to_table(file_name)

                self.sync_step = f"Syncing {file_name} ({idx + 1}/{total})"
                self.sync_percent = int((idx / total) * 100)

                # Update cache metadata to current state
                mtime = file_path.stat().st_mtime
                size = file_path.stat().st_size
                self._file_metadata[file_path] = (mtime, size)

                # Process the file
                self._process_file_incrementally(file_path, table_name)
        finally:
            self.is_syncing = False
            self.sync_percent = 100
            self.sync_step = "Sync complete"

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
            if total_lines < last_line:
                logger.info(f"🔄 File {filename} was truncated or replaced (total lines {total_lines} < last loaded {last_line}). Resetting load cursor to 0.")
                last_line = 0
            elif total_lines == last_line:
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
                # Option B: Sync NeonDB records to LanceDB
                self._sync_to_lancedb_from_neondb(parsed_rows, table_name)
                
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
                    "body_ratio": parse_float(row.get("BodyRatio")),
                    "body_ratio_min": parse_float(row.get("BodyRatioMin")),
                    "body_ratio_passed": row.get("BodyRatioPassed", "NO").strip(),
                    "body_ratio_mode": row.get("BodyRatioMode", "").strip(),
                    "initial_sl": parse_float(row.get("InitialSL")),
                    "initial_tp": parse_float(row.get("InitialTP")),
                    "final_sl": parse_float(row.get("FinalSL")),
                    "final_tp": parse_float(row.get("FinalTP")),
                    "initial_risk_points": parse_int(row.get("InitialRiskPoints")),
                    "initial_reward_points": parse_int(row.get("InitialRewardPoints")),
                    "final_risk_points": parse_int(row.get("FinalRiskPoints")),
                    "final_reward_points": parse_int(row.get("FinalRewardPoints")),
                    "trailing_modified": row.get("TrailingModified", "NO").strip(),
                    "trailing_count": parse_int(row.get("TrailingCount")),
                    "tp_expanded": row.get("TPExpanded", "NO").strip(),
                    "tp_expand_count": parse_int(row.get("TPExpandCount")),
                    "max_favorable_points": parse_int(row.get("MaxFavorablePoints")),
                    "max_adverse_points": parse_int(row.get("MaxAdversePoints")),
                    "close_reason": row.get("CloseReason", "").strip(),
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

    def _sync_to_lancedb_from_neondb(self, parsed_rows: List[Dict[str, Any]], table_name: str):
        """Option B: Fetch recently inserted NeonDB records and push them to LanceDB."""
        if not self.lancedb or not parsed_rows:
            return
            
        try:
            if table_name == "llhhbosdata_xauusd":
                logger.info(f"🔄 Syncing {len(parsed_rows)} structures from NeonDB to LanceDB...")
                patterns_to_add = []
                with get_db_conn() as conn:
                    with conn.cursor() as cur:
                        for row in parsed_rows:
                            is_bullish = 'BULL' in str(row.get('direction_action', '')).upper() or 'HH' in str(row.get('type', '')).upper()
                            expected_type = "BUY" if is_bullish else "SELL"
                            
                            query = """
                                SELECT 
                                    s.type, s.direction_action, s.price, s.time, s.timeframe, s.status,
                                    COALESCE(m15.ema200, h1.ema200, h4.ema200, s.price) as ema200,
                                    r.net_profit, r.session, r.entry_price, r.exit_price, r.entry_time, r.exit_time, r.status,
                                    (
                                        SELECT type FROM llhhbosdata_xauusd 
                                        WHERE timeframe = s.timeframe AND time < s.time AND UPPER(type) IN ('CHOCH', 'BOS')
                                        ORDER BY time DESC 
                                        LIMIT 1
                                    ) as prior_baseline
                                FROM llhhbosdata_xauusd s
                                LEFT JOIN marketdata_xauusd_m15 m15 ON s.time = m15.time AND s.timeframe = 'M15'
                                LEFT JOIN marketdata_xauusd_h1 h1 ON s.time = h1.time AND s.timeframe = 'H1'
                                LEFT JOIN marketdata_xauusd_h4 h4 ON s.time = h4.time AND s.timeframe = 'H4'
                                LEFT JOIN backtest_results_xauusd r ON r.symbol = 'XAUUSD' AND r.timeframe = s.timeframe AND r.type = %s 
                                    AND r.entry_time >= s.time AND r.entry_time <= s.time + interval '5 days'
                                WHERE s.time = %s AND s.timeframe = %s AND s.type = %s AND s.price = %s
                                LIMIT 1
                            """
                            cur.execute(query, (expected_type, row['time'], row['timeframe'], row['type'], row['price']))
                            db_row = cur.fetchone()
                            
                            if db_row:
                                s_type, s_dir, s_price, s_time, s_tf, s_status, ema200, net_profit, session, entry_pr, exit_pr, t_entry, t_exit, r_status, prior_baseline = db_row
                                
                                event_type = "BoS"
                                if "choch" in s_type.lower():
                                    event_type = "CHoCH"
                                elif "hh" in s_type.lower():
                                    event_type = "HH"
                                elif "ll" in s_type.lower():
                                    event_type = "LL"
                                    
                                direction = "Bullish" if is_bullish else "Bearish"
                                prior_choch = prior_baseline is not None and prior_baseline.upper() == "CHOCH"
                                
                                outcome = "PENDING"
                                profit_pips = 0.0
                                duration_minutes = 0
                                norm_session = "London"
                                
                                if net_profit is not None and str(r_status).upper() != "REJECTED":
                                    outcome = "WIN" if float(net_profit) > 0 else "LOSS"
                                    entry_pr = float(entry_pr or 0)
                                    exit_pr = float(exit_pr or 0)
                                    if expected_type == "BUY":
                                        pips = (exit_pr - entry_pr) * 10.0
                                    else:
                                        pips = (entry_pr - exit_pr) * 10.0
                                    profit_pips = round(pips, 2)
                                    
                                    try:
                                        duration_minutes = int((t_exit - t_entry).total_seconds() / 60)
                                    except:
                                        duration_minutes = 0
                                    norm_session = self._normalize_session(session)
                                else:
                                    hour = s_time.hour
                                    if 8 <= hour < 13:
                                        norm_session = "London"
                                    elif 13 <= hour < 22:
                                        norm_session = "NewYork"
                                    elif 22 <= hour or hour < 8:
                                        norm_session = "Asia"
                                        
                                pattern_dict = {
                                    "timestamp": s_time.isoformat(),
                                    "symbol": "XAUUSD",
                                    "timeframe": s_tf,
                                    "event_type": event_type,
                                    "direction": direction,
                                    "price": float(s_price),
                                    "ema200": float(ema200),
                                    "session": norm_session,
                                    "prior_choch": prior_choch,
                                    "outcome": outcome,
                                    "profit_pips": profit_pips,
                                    "duration_minutes": duration_minutes
                                }
                                
                                patterns_to_add.append(pattern_dict)
                
                # Perform high-performance batch write
                if patterns_to_add:
                    self.lancedb.add_structure_patterns_batch(patterns_to_add)
                                
            elif table_name == "backtest_results_xauusd":
                logger.info(f"🔄 Syncing {len(parsed_rows)} trade outcomes from NeonDB to LanceDB...")
                trades_to_add = []
                with get_db_conn() as conn:
                    with conn.cursor() as cur:
                        for row in parsed_rows:
                            query = """
                                SELECT ticket, symbol, type, entry_price, exit_price, net_profit, session, entry_time, exit_time, timeframe, status,
                                       body_ratio, body_ratio_min, body_ratio_passed, body_ratio_mode,
                                       initial_sl, initial_tp, final_sl, final_tp,
                                       initial_risk_points, initial_reward_points, final_risk_points, final_reward_points,
                                       trailing_modified, trailing_count, tp_expanded, tp_expand_count,
                                       max_favorable_points, max_adverse_points, close_reason
                                FROM backtest_results_xauusd
                                WHERE entry_time = %s AND ticket = %s AND type = %s
                                LIMIT 1
                            """
                            cur.execute(query, (row['entry_time'], row['ticket'], row['type']))
                            db_row = cur.fetchone()
                            
                            if db_row:
                                (ticket, symbol, t_type, entry_pr, exit_pr, net_profit, session, t_entry, t_exit, tf, status,
                                 body_ratio, body_ratio_min, body_ratio_passed, body_ratio_mode,
                                 initial_sl, initial_tp, final_sl, final_tp,
                                 initial_risk_points, initial_reward_points, final_risk_points, final_reward_points,
                                 trailing_modified, trailing_count, tp_expanded, tp_expand_count,
                                 max_favorable_points, max_adverse_points, close_reason) = db_row
                                
                                entry_pr = float(entry_pr or 0)
                                exit_pr = float(exit_pr or 0)
                                net_profit = float(net_profit or 0)
                                
                                pips = 0.0
                                if str(status).upper() != "REJECTED":
                                    if str(t_type) == "BUY":
                                        pips = (exit_pr - entry_pr) * 10.0
                                    else:
                                        pips = (entry_pr - exit_pr) * 10.0
                                    outcome = "WIN" if net_profit > 0 else "LOSS"
                                else:
                                    outcome = "PENDING"
                                
                                try:
                                    duration_minutes = int((t_exit - t_entry).total_seconds() / 60)
                                except:
                                    duration_minutes = 0
                                    
                                structure_event = "BoS"
                                expected_dir = "Bullish" if str(t_type) == "BUY" else "Bearish"
                                
                                struct_query = """
                                    SELECT type 
                                    FROM llhhbosdata_xauusd
                                    WHERE timeframe = %s AND time <= %s AND time >= %s - interval '1 hour'
                                    ORDER BY time DESC
                                    LIMIT 1
                                """
                                cur.execute(struct_query, (tf, t_entry, t_entry))
                                s_row = cur.fetchone()
                                if s_row:
                                    raw_type = str(s_row[0]).strip()
                                    if "choch" in raw_type.lower():
                                        structure_event = "CHoCH"
                                    elif "hh" in raw_type.lower():
                                        structure_event = "HH"
                                    elif "ll" in raw_type.lower():
                                        structure_event = "LL"
                                        
                                trade_dict = {
                                    "ticket": int(ticket) if ticket is not None else 0,
                                    "timestamp": t_entry.isoformat(),
                                    "symbol": "XAUUSD",
                                    "type": str(t_type),
                                    "entry_price": entry_pr,
                                    "exit_price": exit_pr,
                                    "profit_pips": round(pips, 2),
                                    "duration_minutes": duration_minutes,
                                    "outcome": outcome,
                                    "structure_event": structure_event,
                                    "session": self._normalize_session(session),
                                    "consensus_score": 0.80,
                                    "body_ratio": float(body_ratio) if body_ratio is not None else None,
                                    "body_ratio_min": float(body_ratio_min) if body_ratio_min is not None else None,
                                    "body_ratio_passed": body_ratio_passed,
                                    "body_ratio_mode": body_ratio_mode,
                                    "initial_sl": float(initial_sl) if initial_sl is not None else None,
                                    "initial_tp": float(initial_tp) if initial_tp is not None else None,
                                    "final_sl": float(final_sl) if final_sl is not None else None,
                                    "final_tp": float(final_tp) if final_tp is not None else None,
                                    "initial_risk_points": initial_risk_points,
                                    "initial_reward_points": initial_reward_points,
                                    "final_risk_points": final_risk_points,
                                    "final_reward_points": final_reward_points,
                                    "trailing_modified": trailing_modified,
                                    "trailing_count": trailing_count,
                                    "tp_expanded": tp_expanded,
                                    "tp_expand_count": tp_expand_count,
                                    "max_favorable_points": max_favorable_points,
                                    "max_adverse_points": max_adverse_points,
                                    "close_reason": close_reason
                                }
                                
                                trades_to_add.append(trade_dict)
                                
                        if trades_to_add:
                            self.lancedb.add_trade_outcomes_batch(trades_to_add)
                            
                        self._recalculate_session_patterns(cur)

            # Trigger hybrid orchestrator run only on specific structure patterns (CHoCH, HH, LL, BoS) or trade outcomes
            should_trigger = False
            if table_name == "llhhbosdata_xauusd":
                # Check if any new structure row contains CHoCH, HH, LL, or BoS
                trigger_types = ["CHOCH", "HH", "LL", "BOS"]
                for row in parsed_rows:
                    row_type = str(row.get("type", "")).upper()
                    if any(t in row_type for t in trigger_types):
                        should_trigger = True
                        break
            elif table_name == "backtest_results_xauusd":
                should_trigger = True

            if should_trigger:
                try:
                    logger.info(f"⚡ Hybrid trigger: new event in {table_name}. Executing orchestrator decision...")
                    from app.services.orchestrator_service import run_orchestrator_from_db
                    run_orchestrator_from_db("XAUUSD")
                except Exception as trigger_err:
                    logger.warning(f"⚠️ Failed to trigger hybrid orchestrator: {trigger_err}")
                        
        except Exception as e:
            logger.error(f"❌ Failed to sync to LanceDB: {e}", exc_info=True)

    def _normalize_session(self, raw_session: str) -> str:
        if not isinstance(raw_session, str):
            return "London"
        raw_lower = raw_session.lower()
        if "london" in raw_lower:
            return "London"
        elif "newyork" in raw_lower or "new_york" in raw_lower:
            return "NewYork"
        elif "asia" in raw_lower or "tokyo" in raw_lower or "sydney" in raw_lower:
            return "Asia"
        return "London"

    def _recalculate_session_patterns(self, cur):
        """Recalculate stats per session and update LanceDB session_patterns table."""
        if not self.lancedb:
            return
            
        logger.info("🔄 Recalculating session patterns in LanceDB...")
        try:
            cur.execute("""
                SELECT 
                    session,
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN net_profit > 0 THEN 1 ELSE 0 END) as wins,
                    AVG(CASE WHEN type = 'BUY' THEN (exit_price - entry_price)*10.0 ELSE (entry_price - exit_price)*10.0 END) as avg_profit_pips
                FROM backtest_results_xauusd
                GROUP BY session
            """)
            rows = cur.fetchall()
            
            sessions_data = []
            for r in rows:
                session_name, total, wins, avg_profit = r
                if not session_name:
                    continue
                norm_name = self._normalize_session(session_name)
                win_rate = float(wins) / float(total) if total > 0 else 0.50
                
                cur.execute("""
                    SELECT s.type
                    FROM backtest_results_xauusd r
                    JOIN llhhbosdata_xauusd s ON s.timeframe = r.timeframe AND s.time <= r.entry_time AND s.time >= r.entry_time - interval '1 hour'
                    WHERE r.session = %s
                    GROUP BY s.type
                    ORDER BY COUNT(*) DESC
                    LIMIT 1
                """, (session_name,))
                s_row = cur.fetchone()
                best_event = "BoS"
                if s_row:
                    raw_type = str(s_row[0]).strip()
                    if "choch" in raw_type.lower():
                        best_event = "CHoCH"
                    elif "hh" in raw_type.lower():
                        best_event = "HH"
                    elif "ll" in raw_type.lower():
                        best_event = "LL"
                        
                sessions_data.append({
                    "id": f"session_{norm_name}",
                    "session": norm_name,
                    "date": datetime.now().date().isoformat(),
                    "win_rate": float(win_rate),
                    "avg_profit_pips": float(avg_profit or 0.0),
                    "total_trades": int(total),
                    "best_event_type": best_event,
                    "vector": [0.0] * 4
                })
                
            if sessions_data:
                self.lancedb.clear_collection("session_patterns")
                table_sp = self.lancedb.db.open_table("session_patterns")
                table_sp.add(sessions_data)
                logger.info("✅ LanceDB session_patterns updated successfully.")
        except Exception as e:
            logger.error(f"❌ Failed to recalculate session patterns: {e}", exc_info=True)
