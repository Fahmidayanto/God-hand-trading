"""
Populate LanceDB with Backtest Results and SMC Structure Events.

Reads historical data from Backtest_result/ and imports into the LanceDB
historical_structures collection to provide rich context for trading agents.
"""

import os
import sys
import glob
import logging
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

# Add app and python paths to sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
PYTHON_DIR = PROJECT_ROOT / "python"
BACKTEST_DIR = PROJECT_ROOT.parent / "Backtest_result"

if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Setup logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("populate_lancedb")

from valuecell.knowledge.lance_db import LanceDBManager


def parse_dt_safe(time_str: str) -> datetime:
    """Parse time string safely supporting multiple formats."""
    time_str = time_str.strip()
    for fmt in ("%Y.%m.%d %H:%M:%S", "%Y.%m.%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(time_str, fmt)
        except ValueError:
            continue
    return datetime.fromisoformat(time_str)


def load_structure_data(filepath: Path) -> pd.DataFrame:
    """Read LLHHBOSData CSV safely by skipping introduction headers."""
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    header_idx = 0
    for idx, line in enumerate(lines):
        if line.startswith("Type,Direction/Action"):
            header_idx = idx
            break
            
    df = pd.read_csv(filepath, skiprows=header_idx)
    # Strip column names of whitespace
    df.columns = [c.strip() for c in df.columns]
    return df


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
    logger.info("🚀 LANCEDB BATCH POPULATION FROM BACKTEST RESULTS")
    logger.info("=" * 60)
    
    if not BACKTEST_DIR.exists():
        logger.error(f"Backtest directory not found at: {BACKTEST_DIR}")
        sys.exit(1)
        
    logger.info(f"Looking for CSVs in: {BACKTEST_DIR.resolve()}")
    
    # 1. Initialize LanceDB Manager
    db = LanceDBManager(str(PYTHON_DIR / "valuecell" / "data" / "lancedb"))
    
    # Clear existing structures for a clean import
    logger.info("Clearing all existing LanceDB collections...")
    db.clear_collection("historical_structures")
    db.clear_collection("market_conditions")
    db.clear_collection("session_patterns")
    db.clear_collection("trade_outcomes")
    
    # Find files
    structure_files = sorted(glob.glob(str(BACKTEST_DIR / "LLHHBOSData_XAUUSD_*.csv")))
    result_files = sorted(glob.glob(str(BACKTEST_DIR / "Backtest_Results_XAUUSD_*.csv")))
    market_files = sorted(glob.glob(str(BACKTEST_DIR / "MarketData_XAUUSD_*.csv")))
    
    logger.info(f"Found {len(structure_files)} structure files, {len(result_files)} result files, and {len(market_files)} market data files.")
    
    # 2. Build global structure lookup dictionary to resolve prior_choch
    logger.info("Building global structure lookup dictionary...")
    struct_lookup = {"M15": [], "H1": [], "H4": []}
    for s_file in structure_files:
        try:
            df_temp = load_structure_data(Path(s_file))
            for _, s_row in df_temp.iterrows():
                tf_temp = str(s_row.get("Timeframe")).strip()
                if tf_temp not in struct_lookup:
                    struct_lookup[tf_temp] = []
                
                time_str_temp = str(s_row.get("Time")).strip()
                dt_obj = parse_dt_safe(time_str_temp)
                struct_lookup[tf_temp].append({
                    "time": dt_obj,
                    "type": str(s_row.get("Type")).strip(),
                })
        except Exception as e:
            logger.warning(f"Failed to index structure file {s_file} for global lookup: {e}")
            
    # Sort chronologically
    for tf_key in struct_lookup:
        struct_lookup[tf_key].sort(key=lambda x: x["time"])
    logger.info("Global structure lookup dictionary built.")
    
    # Extract years
    years = [Path(f).stem.split("_")[-1] for f in structure_files]
    logger.info(f"Processing years: {years}")
    
    total_imported = 0
    
    for year in years:
        logger.info(f"\n📅 --- Processing Year: {year} ---")
        
        # Load files for this year
        struct_path = BACKTEST_DIR / f"LLHHBOSData_XAUUSD_{year}.csv"
        results_path = BACKTEST_DIR / f"Backtest_Results_XAUUSD_{year}.csv"
        
        if not struct_path.exists():
            logger.warning(f"Structure file missing for year {year}, skipping.")
            continue
            
        df_struct = load_structure_data(struct_path)
        logger.info(f"Loaded {len(df_struct)} structure rows.")
        
        df_results = pd.DataFrame()
        if results_path.exists():
            df_results = pd.read_csv(results_path)
            df_results.columns = [c.strip() for c in df_results.columns]
            logger.info(f"Loaded {len(df_results)} trade outcome rows.")
        else:
            logger.warning(f"Trade results file missing for year {year}, continuing without outcomes.")
            
        # Load market data (M15, H1, H4) to match EMA200
        market_data = {}
        for tf in ["M15", "H1", "H4"]:
            m_path = BACKTEST_DIR / f"MarketData_XAUUSD_{tf}_{year}.csv"
            if m_path.exists():
                df_m = pd.read_csv(m_path)
                df_m.columns = [c.strip() for c in df_m.columns]
                # Set index to Time for fast O(1) lookups
                market_data[tf] = df_m.set_index("Time")
                logger.info(f"Loaded market data {tf}: {len(df_m)} rows indexed.")
            else:
                logger.warning(f"Market data {tf} missing for year {year}.")

        # Convert structures to LanceDB format
        patterns_to_add = []
        seen_events = set()
        
        # Parse structures and try to join with trades/market data
        for _, row in df_struct.iterrows():
            raw_type = str(row.get("Type")).strip()
            raw_dir = str(row.get("Direction/Action")).strip()
            
            # Normalize event_type to match LanceDB (BoS, CHoCH, HH, LL)
            event_type = "BoS"
            if "choch" in raw_type.lower():
                event_type = "CHoCH"
            elif "hh" in raw_type.lower():
                event_type = "HH"
            elif "ll" in raw_type.lower():
                event_type = "LL"
                
            # Normalize direction
            direction = "Bullish"
            if "bearish" in raw_dir.lower() or "bearish" in raw_type.lower():
                direction = "Bearish"
            elif "update" in raw_dir.lower():
                # For updates, get direction from raw_type or direction
                if "bullish" in raw_type.lower() or "hh" in raw_type.lower():
                    direction = "Bullish"
                elif "bearish" in raw_type.lower() or "ll" in raw_type.lower():
                    direction = "Bearish"
            
            tf = str(row.get("Timeframe")).strip()
            price = float(row.get("Price"))
            time_str = str(row.get("Time")).strip()
            
            # Resolve prior_choch
            prior_choch = False
            try:
                row_dt = parse_dt_safe(time_str)
                candidates = struct_lookup.get(tf, [])
                for prev_s in reversed(candidates):
                    if prev_s["time"] >= row_dt:
                        continue
                    prev_raw_type = str(prev_s["type"]).strip().lower()
                    if "choch" in prev_raw_type:
                        prior_choch = True
                        break
                    elif "bos" in prev_raw_type:
                        prior_choch = False
                        break
            except Exception as e:
                logger.warning(f"Error resolving prior_choch: {e}")
            
            # Get EMA200 value
            ema200 = price
            if tf in market_data and time_str in market_data[tf].index:
                ema_val = market_data[tf].loc[time_str].get("EMA200")
                if pd.notna(ema_val):
                    # In case of series/multiple rows, take the first one
                    ema200 = float(ema_val.iloc[0] if isinstance(ema_val, pd.Series) else ema_val)

            # Try to match with a trade in results
            trade_match = None
            if not df_results.empty:
                # Convert time string to datetime to check proximity
                try:
                    struct_time = datetime.strptime(time_str, "%Y.%m.%d %H:%M:%S")
                    
                    # Find candidate trades matching Symbol, Timeframe, Type
                    # BoS/CHoCH Bullish -> BUY, BoS/CHoCH Bearish -> SELL
                    expected_type = "BUY" if direction == "Bullish" else "SELL"
                    
                    # Filter candidate trades
                    candidates = df_results[
                        (df_results["Symbol"] == "XAUUSD") & 
                        (df_results["Timeframe"] == tf) &
                        (df_results["Type"] == expected_type)
                    ]
                    
                    for _, t_row in candidates.iterrows():
                        t_entry_str = str(t_row.get("EntryTime")).strip()
                        t_entry_time = datetime.strptime(t_entry_str, "%Y.%m.%d %H:%M:%S")
                        
                        # Match if entry time is within a 1-hour window after structure time
                        time_diff = t_entry_time - struct_time
                        if timedelta(minutes=0) <= time_diff <= timedelta(hours=1):
                            trade_match = t_row
                            break
                except Exception as ex:
                    logger.debug(f"Error matching trade: {ex}")
            
            # Outcome formatting
            outcome = "PENDING"
            profit_pips = 0.0
            net_profit = None
            duration_minutes = None
            reject_reason_raw = ""
            session = "London"
            
            if trade_match is not None:
                if str(trade_match.get("Status", "EXECUTED")).upper() == "REJECTED":
                    outcome = "REJECTED"
                    reject_reason_raw = str(trade_match.get("Reject_Reason") or "").strip()
                    session = normalize_session(trade_match.get("Session"))
            
            if trade_match is not None and outcome != "REJECTED":
                net_profit = float(trade_match.get("Net_Profit", 0))
                outcome = "WIN" if net_profit > 0 else "LOSS"
                
                # Compute profit in pips (XAUUSD price change * 10)
                entry_pr = float(trade_match.get("EntryPrice", 0))
                exit_pr = float(trade_match.get("ExitPrice", 0))
                
                if str(trade_match.get("Type")) == "BUY":
                    pips = (exit_pr - entry_pr) * 10.0
                else:
                    pips = (entry_pr - exit_pr) * 10.0
                profit_pips = round(pips, 2)
                
                # Compute duration
                try:
                    t_entry = datetime.strptime(str(trade_match.get("EntryTime")), "%Y.%m.%d %H:%M:%S")
                    t_exit = datetime.strptime(str(trade_match.get("ExitTime")), "%Y.%m.%d %H:%M:%S")
                    duration_minutes = int((t_exit - t_entry).total_seconds() / 60)
                except:
                    duration_minutes = 0
                    
                session = normalize_session(trade_match.get("Session"))
            else:
                # Default session based on time_str
                try:
                    hour = datetime.strptime(time_str, "%Y.%m.%d %H:%M:%S").hour
                    if 8 <= hour < 13:
                        session = "London"
                    elif 13 <= hour < 22:
                        session = "NewYork"
                    elif 22 <= hour or hour < 8:
                        session = "Asia"
                except:
                    pass
            
            # Convert YYYY.MM.DD HH:MM:SS to ISO YYYY-MM-DDTHH:MM:SS
            try:
                dt_iso = datetime.strptime(time_str, "%Y.%m.%d %H:%M:%S").isoformat()
            except:
                dt_iso = datetime.now().isoformat()
                
            # Prevent duplicate patterns from same event + time
            event_key = (dt_iso, event_type, direction, tf)
            if event_key in seen_events:
                continue
            seen_events.add(event_key)
                 
            patterns_to_add.append({
                "timestamp": dt_iso,
                "symbol": "XAUUSD",
                "timeframe": tf,
                "event_type": event_type,
                "direction": direction,
                "price": price,
                "ema200": ema200,
                "session": session,
                "outcome": outcome,
                "profit_pips": profit_pips,
                "net_profit": net_profit,
                "duration_minutes": duration_minutes,
                "prior_choch": prior_choch,
                "reject_reason_raw": reject_reason_raw,
                "price_ratio": round(price / 4500.0, 6) if price > 0 else 1.0,
            })
            
        # Add to LanceDB
        logger.info(f"Inserting {len(patterns_to_add)} patterns into LanceDB (bulk)...")
        success_count = 0
        try:
            table = db.db.open_table("historical_structures")
            data_list = [db.prepare_structure_pattern(pattern) for pattern in patterns_to_add]
            
            if data_list:
                table.add(data_list)
                success_count = len(data_list)
        except Exception as exc:
            logger.error(f"Failed to bulk insert: {exc}")
            success_count = 0
                
        logger.info(f"Year {year} import result: {success_count}/{len(patterns_to_add)} imported successfully.")
        total_imported += success_count

    logger.info("\n" + "=" * 60)
    logger.info(f"✅ BATCH IMPORT COMPLETE! Total patterns imported: {total_imported}")
    stats = db.get_stats()
    logger.info(f"LanceDB current statistics: {stats}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
