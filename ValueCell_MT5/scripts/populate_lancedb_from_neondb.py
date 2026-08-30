import os
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import psycopg2
from dotenv import load_dotenv

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
logger = logging.getLogger("populate_lancedb_from_neondb")

# Load environment
env_path = PROJECT_ROOT / ".env"
load_dotenv(env_path)

from valuecell.knowledge.lance_db import LanceDBManager
from valuecell.knowledge.historical_market_features import (
    build_market_feature_frame,
    extract_historical_market_features,
)
from valuecell.knowledge.historical_trade_matching import (
    build_structure_trade_matches,
    normalize_structure_direction,
    normalize_structure_event,
)

def get_neon_conn():
    """Establish connection to Neon PostgreSQL"""
    try:
        conn = psycopg2.connect(
            host=os.getenv("PGHOST"),
            database=os.getenv("PGDATABASE"),
            user=os.getenv("PGUSER"),
            password=os.getenv("PGPASSWORD"),
            sslmode=os.getenv("PGSSLMODE", "require")
        )
        return conn
    except Exception as e:
        logger.error(f"[ERROR] Failed to connect to Neon DB: {e}")
        raise

def fetch_table_chunked(table: str, columns: str, time_col: str = "time", chunk_days: int = 90, max_retries: int = 3) -> pd.DataFrame:
    """
    Fetch a time-series table in date-range chunks, each over its own fresh
    connection, instead of one query over one long-lived connection.

    In practice, a single ~12-minute query for 224k M15 rows left the connection
    stale enough that the very next query on it failed with "SSL connection has
    been closed unexpectedly", and the whole migration silently produced empty
    LanceDB collections. Keeping every round-trip short and reconnecting between
    chunks avoids that failure mode.
    """
    conn = get_neon_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT MIN({time_col}), MAX({time_col}) FROM {table}")
            min_time, max_time = cur.fetchone()
    finally:
        conn.close()

    if min_time is None:
        return pd.DataFrame()

    chunks = []
    step = timedelta(days=chunk_days)
    chunk_start = min_time
    while chunk_start <= max_time:
        chunk_end = min(chunk_start + step, max_time + timedelta(seconds=1))
        last_err = None
        for attempt in range(1, max_retries + 1):
            try:
                chunk_conn = get_neon_conn()
                try:
                    df_chunk = pd.read_sql(
                        f"SELECT {columns} FROM {table} WHERE {time_col} >= %(start)s AND {time_col} < %(end)s",
                        chunk_conn,
                        params={"start": chunk_start, "end": chunk_end},
                    )
                finally:
                    chunk_conn.close()
                chunks.append(df_chunk)
                logger.info(f"  {table}: {chunk_start} .. {chunk_end} -> {len(df_chunk)} rows")
                last_err = None
                break
            except Exception as e:
                last_err = e
                logger.warning(f"  {table}: chunk {chunk_start}..{chunk_end} attempt {attempt}/{max_retries} failed: {e}")
        if last_err is not None:
            raise last_err
        chunk_start = chunk_end

    return pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()

def normalize_session(raw_session: str) -> str:
    """Normalize session string to match LanceDB expectations."""
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

def main():
    logger.info("=" * 60)
    logger.info("LANCEDB MIGRATION STARTING: POPULATING FROM NEONDB")
    logger.info("=" * 60)

    # 1. Initialize LanceDB
    db = LanceDBManager(str(PYTHON_DIR / "valuecell" / "data" / "lancedb"))

    # 2. Clear all 4 collections
    logger.info("Clearing existing LanceDB collections...")
    db.clear_collection("historical_structures")
    db.clear_collection("market_conditions")
    db.clear_collection("session_patterns")
    db.clear_collection("trade_outcomes")

    try:
        # Load NeonDB tables into DataFrames for fast O(1) in-memory joining
        logger.info("Fetching data from NeonDB...")

        # Load market data in date-range chunks over fresh connections each (see
        # fetch_table_chunked docstring for why -- these are the largest tables).
        MARKET_COLS = "time, open::float, high::float, low::float, close::float, volume, spread, ema200::float"
        df_m15 = fetch_table_chunked("marketdata_xauusd_m15", MARKET_COLS)
        df_h1 = fetch_table_chunked("marketdata_xauusd_h1", MARKET_COLS)
        df_h4 = fetch_table_chunked("marketdata_xauusd_h4", MARKET_COLS)

        logger.info(f"Loaded market data: M15={len(df_m15)} rows, H1={len(df_h1)} rows, H4={len(df_h4)} rows.")

        # Optimize O(1) timeframe lookup using python dicts
        market_data_dict = {
            "M15": df_m15.set_index("time")["ema200"].to_dict(),
            "H1": df_h1.set_index("time")["ema200"].to_dict(),
            "H4": df_h4.set_index("time")["ema200"].to_dict()
        }
        market_feature_frames = {
            "M15": build_market_feature_frame(df_m15),
            "H1": build_market_feature_frame(df_h1),
            "H4": build_market_feature_frame(df_h4),
        }

        # Load backtest results (trade outcomes) -- small table, one query is fine,
        # but still on its own fresh connection rather than one reused for everything.
        conn = get_neon_conn()
        try:
            df_results = pd.read_sql("SELECT ticket, symbol, type, entry_structure, entry_price::float, exit_price::float, profit::float, net_profit::float, session, entry_time, exit_time, timeframe, status, reject_reason, close_reason, Magic_number as magic_number FROM backtest_results_xauusd", conn)
        finally:
            conn.close()
        logger.info(f"Loaded {len(df_results)} trade outcome rows from backtest_results_xauusd.")

        # REJECTED rows are signals the pre-trade filter blocked before execution -- no
        # ticket, exit_price=0 and exit_time=NULL as placeholders. historical_structures
        # (Stage 1) still needs to see these to know "a signal formed here but was
        # filtered out", so trade_lookup is built from the full, unfiltered df_results;
        # the REJECTED case is handled explicitly where trade_match is turned into an
        # outcome below. trade_outcomes (Stage 3) only records real, executed trades,
        # so it uses the executed-only slice defined here.
        df_results_executed = df_results[
            (df_results["status"] != "REJECTED") & df_results["exit_time"].notna()
        ].reset_index(drop=True)
        logger.info(f"{len(df_results_executed)} of those rows are actually executed trades.")

        # Load llhhbosdata -- also small, own fresh connection.
        conn = get_neon_conn()
        try:
            df_struct = pd.read_sql("SELECT type, direction_action, price::float, time, timeframe, status FROM llhhbosdata_xauusd", conn)
        finally:
            conn.close()
        logger.info(f"Loaded {len(df_struct)} structure rows from llhhbosdata_xauusd.")

        matching_structures = []
        for _, structure_row in df_struct.iterrows():
            structure_time = pd.Timestamp(structure_row["time"])
            structure_type = normalize_structure_event(structure_row["type"])
            structure_direction = normalize_structure_direction(
                structure_row["type"],
                structure_row["direction_action"],
            )
            structure_timeframe = str(structure_row["timeframe"]).strip()
            event_key = (
                structure_time.isoformat(),
                structure_type,
                structure_direction,
                structure_timeframe,
            )
            matching_structures.append({
                "event_key": event_key,
                "event_time": structure_time,
                "event_type": structure_type,
                "direction": structure_direction,
                "timeframe": structure_timeframe,
            })

        matching_trades = df_results.copy()
        matching_trades["trade_key"] = matching_trades.index
        trade_matches, match_stats = build_structure_trade_matches(
            pd.DataFrame(matching_structures),
            matching_trades,
        )
        logger.info(
            "One-to-one trade matching: %s matched, %s unmatched, %s exact event, %s fallback.",
            match_stats["matched"],
            match_stats["unmatched"],
            match_stats["exact_event"],
            match_stats["fallback"],
        )

        # Optimize structure lookup for stage 3
        struct_lookup = {}
        for _, s_row in df_struct.iterrows():
            tf = str(s_row["timeframe"]).strip()
            if tf not in struct_lookup:
                struct_lookup[tf] = []
            struct_lookup[tf].append(s_row.to_dict())

        for tf in struct_lookup:
            struct_lookup[tf].sort(key=lambda x: x["time"])

        # -------------------------------------------------------------
        # STAGE 1: Populate historical_structures
        # -------------------------------------------------------------
        logger.info("Processing historical_structures...")
        patterns_to_add = []
        seen_events = set()
        
        for _, row in df_struct.iterrows():
            raw_type = str(row["type"]).strip()
            raw_dir = str(row["direction_action"]).strip()
            
            # Normalize event_type
            event_type = normalize_structure_event(raw_type)
                
            # Normalize direction
            direction = normalize_structure_direction(raw_type, raw_dir)

            tf = str(row["timeframe"]).strip()
            price = float(row["price"])
            struct_time = row["time"] # pandas Timestamp object

            # Resolve prior_choch
            prior_choch = False
            struct_candidates = struct_lookup.get(tf, [])
            for prev_s in reversed(struct_candidates):
                if prev_s["time"] >= struct_time:
                    continue
                prev_raw_type = str(prev_s["type"]).strip().lower()
                if "choch" in prev_raw_type:
                    prior_choch = True
                    break
                elif "bos" in prev_raw_type:
                    prior_choch = False
                    break

            # Resolve EMA200 using dictionary lookup
            ema200 = price
            if tf in market_data_dict and struct_time in market_data_dict[tf]:
                ema_val = market_data_dict[tf][struct_time]
                if pd.notna(ema_val):
                    ema200 = float(ema_val)

            event_key = (struct_time.isoformat(), event_type, direction, tf)
            if event_key in seen_events:
                continue
            seen_events.add(event_key)

            trade_match = trade_matches.get(event_key)

            # Outcome formatting
            outcome = "PENDING"
            profit_pips = 0.0
            net_profit = None
            duration_minutes = None
            reject_reason_raw = ""
            reject_reason_code = "NONE"
            session = "London"

            if trade_match is not None and str(trade_match.get("status")) == "REJECTED":
                # A trade was attempted here but the pre-trade quality filter blocked
                # it -- worth keeping as its own outcome (distinct from "no signal at
                # all"), but there's no real entry/exit to derive pips or duration from.
                outcome = "REJECTED"
                profit_pips = 0.0
                reject_reason_raw = str(trade_match.get("reject_reason") or "").strip()
                reject_reason_code = db.prepare_structure_pattern({
                    "timestamp": struct_time.isoformat(),
                    "symbol": "XAUUSD",
                    "timeframe": tf,
                    "event_type": event_type,
                    "direction": direction,
                    "price": price,
                    "outcome": outcome,
                    "reject_reason_raw": reject_reason_raw,
                })["reject_reason_code"]
                session = normalize_session(trade_match.get("session"))
            elif trade_match is not None:
                net_profit = float(trade_match.get("net_profit", 0))
                outcome = "WIN" if net_profit > 0 else "LOSS"

                entry_pr = float(trade_match.get("entry_price", 0))
                exit_pr = float(trade_match.get("exit_price", 0))

                if str(trade_match.get("type")) == "BUY":
                    pips = (exit_pr - entry_pr) * 10.0
                else:
                    pips = (entry_pr - exit_pr) * 10.0
                profit_pips = round(pips, 2)

                try:
                    duration_minutes = int((trade_match["exit_time"] - trade_match["entry_time"]).total_seconds() / 60)
                except:
                    duration_minutes = 0
                    
                session = normalize_session(trade_match.get("session"))
            else:
                hour = struct_time.hour
                if 8 <= hour < 13:
                    session = "London"
                elif 13 <= hour < 22:
                    session = "NewYork"
                elif 22 <= hour or hour < 8:
                    session = "Asia"

            entry_price = None
            if trade_match is not None:
                entry_value = trade_match.get("entry_price")
                if entry_value is not None and pd.notna(entry_value):
                    entry_price = float(entry_value)

            market_features = extract_historical_market_features(
                event_time=struct_time,
                structure_price=price,
                entry_price=entry_price,
                m15=market_feature_frames["M15"],
                h1=market_feature_frames["H1"],
                h4=market_feature_frames["H4"],
            )

            patterns_to_add.append({
                "id": f"XAUUSD_{struct_time.isoformat()}",
                "timestamp": struct_time.isoformat(),
                "symbol": "XAUUSD",
                "timeframe": tf,
                "event_type": event_type,
                "direction": direction,
                "price": price,
                "ema200": ema200,
                "ema_distance": price - ema200,
                "session": session,
                "prior_choch": prior_choch,
                "outcome": outcome,
                "profit_pips": profit_pips,
                "net_profit": net_profit,
                "duration_minutes": duration_minutes,
                "entry_time": trade_match.get("entry_time") if trade_match is not None else None,
                "entry_price": trade_match.get("entry_price") if trade_match is not None else None,
                "exit_time": trade_match.get("exit_time") if trade_match is not None else None,
                "exit_price": trade_match.get("exit_price") if trade_match is not None else None,
                "close_reason": trade_match.get("close_reason") if trade_match is not None else None,
                "reject_reason_raw": reject_reason_raw,
                "reject_reason_code": reject_reason_code,
                "price_ratio": round(price / 4500.0, 6) if price > 0 else 1.0,
                **market_features,
            })

        # Insert to LanceDB
        logger.info(f"Adding {len(patterns_to_add)} patterns to historical_structures...")
        table_struct = db.db.open_table("historical_structures")
        data_list_struct = [db.prepare_structure_pattern(pattern) for pattern in patterns_to_add]
            
        if data_list_struct:
            table_struct.add(data_list_struct)
            logger.info("historical_structures populated successfully!")

        # -------------------------------------------------------------
        # STAGE 2: Populate market_conditions
        # -------------------------------------------------------------
        logger.info("Processing market_conditions...")
        if not df_m15.empty:
            df_m15_sorted = df_m15.sort_values("time").copy()
            # Calculate ATR 14 via pandas
            high_low = df_m15_sorted["high"] - df_m15_sorted["low"]
            high_cp = (df_m15_sorted["high"] - df_m15_sorted["close"].shift(1)).abs()
            low_cp = (df_m15_sorted["low"] - df_m15_sorted["close"].shift(1)).abs()
            tr = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
            df_m15_sorted["atr"] = tr.rolling(14).mean().fillna(0.0)

            conditions_to_add = []
            for _, row in df_m15_sorted.iterrows():
                t = row["time"]
                hour = t.hour
                session = "London"
                if 8 <= hour < 13:
                    session = "London"
                elif 13 <= hour < 22:
                    session = "NewYork"
                elif 22 <= hour or hour < 8:
                    session = "Asia"

                conditions_to_add.append({
                    "id": f"XAUUSD_M15_{t.isoformat()}",
                    "timestamp": t.isoformat(),
                    "symbol": "XAUUSD",
                    "timeframe": "M15",
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": int(row["volume"]),
                    "ema200": float(row["ema200"]),
                    "atr": float(row["atr"]),
                    "session": session,
                    "vector": [0.0] * 8
                })

            logger.info(f"Adding {len(conditions_to_add)} records to market_conditions...")
            table_mc = db.db.open_table("market_conditions")
            if conditions_to_add:
                table_mc.add(conditions_to_add)
                logger.info("market_conditions populated successfully!")

        # -------------------------------------------------------------
        # STAGE 3: Populate trade_outcomes
        # -------------------------------------------------------------
        logger.info("Processing trade_outcomes...")
        trades_to_add = []
        for _, row in df_results_executed.iterrows():
            t_entry = row["entry_time"]
            t_exit = row["exit_time"]
            
            entry_pr = float(row.get("entry_price", 0))
            exit_pr = float(row.get("exit_price", 0))
            
            pips = 0.0
            if str(row["type"]) == "BUY":
                pips = (exit_pr - entry_pr) * 10.0
            else:
                pips = (entry_pr - exit_pr) * 10.0
                
            net_profit = float(row.get("net_profit", 0))
            outcome = "WIN" if net_profit > 0 else "LOSS"
            
            try:
                duration_minutes = int((t_exit - t_entry).total_seconds() / 60)
            except:
                duration_minutes = 0

            # Estimate structure event context using optimized backwards search in structures list
            structure_event = "BoS"
            candidates = struct_lookup.get(row["timeframe"], [])
            
            for s_dict in reversed(candidates):
                s_time = s_dict["time"]
                if s_time > t_entry:
                    continue
                if s_time < (t_entry - timedelta(hours=1)):
                    break # since sorted, all subsequent are older than 1 hour
                
                # Check direction/type alignment
                raw_type = str(s_dict["type"]).strip()
                raw_dir = str(s_dict["direction_action"]).strip()
                s_direction = "Bullish"
                if "bearish" in raw_dir.lower() or "bearish" in raw_type.lower():
                    s_direction = "Bearish"
                elif "update" in raw_dir.lower():
                    if "bullish" in raw_type.lower() or "hh" in raw_type.lower():
                        s_direction = "Bullish"
                    elif "bearish" in raw_type.lower() or "ll" in raw_type.lower():
                        s_direction = "Bearish"
                
                expected_dir = "Bullish" if str(row["type"]) == "BUY" else "Bearish"
                if s_direction == expected_dir:
                    if "choch" in raw_type.lower():
                        structure_event = "CHoCH"
                    elif "hh" in raw_type.lower():
                        structure_event = "HH"
                    elif "ll" in raw_type.lower():
                        structure_event = "LL"
                    else:
                        structure_event = "BoS"
                    break

            trade_dict = {
                "ticket": int(row["ticket"]) if pd.notna(row["ticket"]) else 0,
                "timestamp": t_entry.isoformat(),
                "symbol": "XAUUSD",
                "type": str(row["type"]),
                "entry_price": entry_pr,
                "exit_price": exit_pr,
                "profit_pips": round(pips, 2),
                "duration_minutes": duration_minutes,
                "outcome": outcome,
                "structure_event": structure_event,
                "session": normalize_session(row.get("session")),
                "consensus_score": 0.80 # default backup consensus score for historical trades
            }

            vector = db._trade_to_vector(trade_dict)
            
            trades_to_add.append({
                "id": f"trade_{trade_dict['ticket'] or t_entry.timestamp()}",
                "ticket": trade_dict["ticket"],
                "timestamp": trade_dict["timestamp"],
                "symbol": trade_dict["symbol"],
                "type": trade_dict["type"],
                "entry_price": trade_dict["entry_price"],
                "exit_price": trade_dict["exit_price"],
                "profit_pips": trade_dict["profit_pips"],
                "duration_minutes": trade_dict["duration_minutes"],
                "outcome": trade_dict["outcome"],
                "structure_event": trade_dict["structure_event"],
                "session": trade_dict["session"],
                "consensus_score": trade_dict["consensus_score"],
                "vector": vector
            })

        logger.info(f"Adding {len(trades_to_add)} records to trade_outcomes...")
        table_to = db.db.open_table("trade_outcomes")
        if trades_to_add:
            table_to.add(trades_to_add)
            logger.info("trade_outcomes populated successfully!")

        # -------------------------------------------------------------
        # STAGE 4: Populate session_patterns
        # -------------------------------------------------------------
        logger.info("Processing session_patterns...")
        if trades_to_add:
            df_trades = pd.DataFrame([{k: v for k, v in t.items() if k != "vector"} for t in trades_to_add])
            
            sessions_data = []
            for session_name in ["London", "NewYork", "Asia"]:
                session_trades = df_trades[df_trades["session"] == session_name]
                
                if not session_trades.empty:
                    wins = len(session_trades[session_trades["outcome"] == "WIN"])
                    total = len(session_trades)
                    win_rate = wins / total
                    avg_profit = session_trades["profit_pips"].mean()
                    
                    # Find most frequent structure event
                    best_event = str(session_trades["structure_event"].mode().iloc[0]) if not session_trades["structure_event"].empty else "BoS"
                else:
                    win_rate = 0.50
                    avg_profit = 0.0
                    total = 0
                    best_event = "BoS"

                sessions_data.append({
                    "id": f"session_{session_name}",
                    "session": session_name,
                    "date": datetime.now().date().isoformat(),
                    "win_rate": float(win_rate),
                    "avg_profit_pips": float(avg_profit),
                    "total_trades": int(total),
                    "best_event_type": best_event,
                    "vector": [0.0] * 4
                })

            logger.info(f"Adding {len(sessions_data)} records to session_patterns...")
            table_sp = db.db.open_table("session_patterns")
            if sessions_data:
                table_sp.add(sessions_data)
                logger.info("session_patterns populated successfully!")

    except Exception as e:
        logger.error(f"[ERROR] Error during migration process: {e}", exc_info=True)
        logger.error("=" * 60)
        logger.error("MIGRATION PROCESS FAILED -- LanceDB collections were cleared but")
        logger.error("NOT fully repopulated. Do not treat this run as successful.")
        logger.error("=" * 60)
        raise
    else:
        logger.info("=" * 60)
        logger.info("MIGRATION PROCESS COMPLETE")
        logger.info("=" * 60)

if __name__ == "__main__":
    main()
