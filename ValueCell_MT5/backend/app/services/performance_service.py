"""
Performance Service — Lapisan 4: Performa Historis Sistem.

Menyediakan tiga fungsi utama:
1. get_session_performance()  → win rate per sesi (London, Asia, dll.)
2. get_last_n_signals()       → N signal terakhir + label WIN/LOSS/PENDING
3. get_real_drawdown()        → max drawdown real dari agent_decisions

Catatan: Karena tabel `trades` masih kosong (paper trading mode, MT5 tidak aktif),
win rate dan drawdown dihitung dari sinyal di `agent_decisions` vs harga aktual
di `realtime_ohlcv` (signal quality / predictive accuracy).
"""

import json
import logging
import bisect
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ─── Session definitions ──────────────────────────────────────────────────────

SESSION_LABELS = {
    "SYDNEY":   "Sydney",
    "LONDON":   "London",
    "NEW_YORK": "New York",
    "OVERLAP":  "London/NY Overlap",
    "UNKNOWN":  "Unknown",
}


# ─── Candle Cache Helper to Avoid N+1 DB Queries ─────────────────────────────

class CandlePriceHelper:
    """Helper to query all M15 candles once and search them in-memory to avoid N+1 database roundtrips."""
    def __init__(self, cur, symbol: str, since_ts: datetime):
        self.symbol = symbol
        # Query candles starting 1 day before since_ts to ensure entry prices are found for decisions near since_ts
        start_query = since_ts - timedelta(days=1)
        cur.execute(
            """
            SELECT timestamp, close
            FROM realtime_ohlcv
            WHERE symbol = %s
              AND timeframe = 'M15'
              AND timestamp >= %s
            ORDER BY timestamp ASC
            """,
            (symbol, start_query),
        )
        rows = cur.fetchall()
        # Store candles as list of (datetime, close)
        self.candles = []
        for ts, close in rows:
            if ts is not None and close is not None:
                self.candles.append((ts.replace(tzinfo=None) if ts.tzinfo else ts, float(close)))
        
        # Precompute a list of timestamps for binary search
        self.timestamps = [c[0] for c in self.candles]

    def get_entry_price(self, near_ts: datetime) -> Optional[float]:
        if not self.candles:
            return None
        near_ts = near_ts.replace(tzinfo=None) if near_ts.tzinfo else near_ts
        
        # bisect_right returns index where near_ts would be inserted to the right of any equal elements.
        # Index - 1 is the last element with timestamp <= near_ts.
        idx = bisect.bisect_right(self.timestamps, near_ts)
        if idx > 0:
            return self.candles[idx - 1][1]
        return None

    def get_price_after(self, after_ts: datetime, candles_forward: int = 3) -> Optional[float]:
        if not self.candles:
            return None
        after_ts = after_ts.replace(tzinfo=None) if after_ts.tzinfo else after_ts
        target_ts = after_ts + timedelta(minutes=15 * candles_forward)
        
        # Find closest candle within 15 minutes of target_ts
        idx = bisect.bisect_left(self.timestamps, target_ts)
        
        best_price = None
        min_diff = timedelta(minutes=15)
        
        # Check surrounding indices
        for i in (idx - 1, idx, idx + 1):
            if 0 <= i < len(self.candles):
                diff = abs(self.candles[i][0] - target_ts)
                if diff <= min_diff:
                    min_diff = diff
                    best_price = self.candles[i][1]
                    
        return best_price


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _parse_final_decision(row_decision: str) -> Optional[str]:
    """Normalise final_decision to BUY / SELL / HOLD / None."""
    if not row_decision:
        return None
    d = row_decision.strip().upper()
    if d in ("BUY", "SELL", "HOLD"):
        return d
    return None


def _evaluate_signal(direction: str, entry: float, future: float) -> str:
    """Return WIN / LOSS based on direction and price movement."""
    if direction == "BUY":
        return "WIN" if future > entry else "LOSS"
    elif direction == "SELL":
        return "WIN" if future < entry else "LOSS"
    return "NEUTRAL"


# ─── Public API ───────────────────────────────────────────────────────────────

def get_session_performance(days_back: int = 30) -> Dict:
    """
    Win rate per trading session, calculated from agent_decisions signals.

    Returns:
        {
          "sessions": {
            "LONDON":   {"win_rate": 68.5, "total": 14, "wins": 10, "losses": 4},
            ...
          },
          "days_back": 30,
          "computed_at": "...",
          "method": "signal_quality"
        }
    """
    from app.core.database import get_db_conn, is_pool_ready

    result = {
        "sessions": {},
        "days_back": days_back,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "method": "signal_quality",
        "note": "Based on agent signal direction vs next 3 M15 candles (paper trading mode)",
    }

    if not is_pool_ready():
        return result

    try:
        since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days_back)

        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, timestamp, symbol, final_decision, session
                    FROM agent_decisions
                    WHERE timestamp >= %s
                      AND final_decision IN ('BUY', 'SELL')
                    ORDER BY timestamp ASC
                    """,
                    (since,),
                )
                rows = cur.fetchall()

                # Initialize CandlePriceHelpers cache
                helpers = {}
                def get_helper(symbol: str) -> CandlePriceHelper:
                    sym = symbol or "XAUUSD"
                    if sym not in helpers:
                        helpers[sym] = CandlePriceHelper(cur, sym, since)
                    return helpers[sym]

                # Per-session accumulators
                buckets: Dict[str, Dict] = {}

                for row_id, ts, symbol, decision, session in rows:
                    if not ts or not decision:
                        continue

                    session_key = (session or "UNKNOWN").upper()
                    if session_key not in buckets:
                        buckets[session_key] = {"wins": 0, "losses": 0, "pending": 0}

                    helper = get_helper(symbol)
                    entry_price = helper.get_entry_price(ts)
                    future_price = helper.get_price_after(ts, candles_forward=3)

                    if entry_price is None or future_price is None:
                        buckets[session_key]["pending"] += 1
                        continue

                    outcome = _evaluate_signal(decision, entry_price, future_price)
                    if outcome == "WIN":
                        buckets[session_key]["wins"] += 1
                    else:
                        buckets[session_key]["losses"] += 1

                # Format output
                for skey, counts in buckets.items():
                    total = counts["wins"] + counts["losses"]
                    result["sessions"][skey] = {
                        "label":    SESSION_LABELS.get(skey, skey),
                        "win_rate": round(counts["wins"] / total * 100, 1) if total > 0 else 0.0,
                        "total":    total,
                        "wins":     counts["wins"],
                        "losses":   counts["losses"],
                        "pending":  counts["pending"],
                    }

    except Exception as exc:
        logger.error(f"[PerfService] get_session_performance error: {exc}", exc_info=True)

    return result


def get_last_n_signals(n: int = 3) -> Dict:
    """
    Return the last N non-HOLD signals with result (WIN / LOSS / PENDING).

    Returns:
        {
          "signals": [
            {
              "id": 28,
              "timestamp": "...",
              "session": "LONDON",
              "direction": "BUY",
              "consensus_score": 0.72,
              "entry_price": 3312.5,
              "exit_price": 3315.2,
              "pnl_estimate": 2.7,
              "result": "WIN"
            },
            ...
          ],
          "computed_at": "..."
        }
    """
    from app.core.database import get_db_conn, is_pool_ready

    result = {
        "signals": [],
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }

    if not is_pool_ready():
        return result

    try:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, timestamp, symbol, final_decision,
                           consensus_score, session
                    FROM agent_decisions
                    WHERE final_decision IN ('BUY', 'SELL')
                    ORDER BY timestamp DESC
                    LIMIT %s
                    """,
                    (n,),
                )
                rows = cur.fetchall()

                if rows:
                    # Find the oldest timestamp to scope the CandlePriceHelper query
                    oldest_ts = min(row[1] for row in rows if row[1] is not None)
                    since = oldest_ts.replace(tzinfo=None) if oldest_ts.tzinfo else oldest_ts
                    
                    helpers = {}
                    def get_helper(symbol: str) -> CandlePriceHelper:
                        sym = symbol or "XAUUSD"
                        if sym not in helpers:
                            helpers[sym] = CandlePriceHelper(cur, sym, since)
                        return helpers[sym]

                    for row_id, ts, symbol, direction, score, session in rows:
                        sym = symbol or "XAUUSD"
                        helper = get_helper(sym)
                        entry_price = helper.get_entry_price(ts) if ts else None
                        future_price = helper.get_price_after(ts, candles_forward=3) if ts else None

                        if entry_price and future_price:
                            res = _evaluate_signal(direction, entry_price, future_price)
                            pnl = round(future_price - entry_price, 2) if direction == "BUY" else round(entry_price - future_price, 2)
                        else:
                            res = "PENDING"
                            pnl = None

                        result["signals"].append({
                            "id":              row_id,
                            "timestamp":       ts.isoformat() if ts else None,
                            "session":         session or "UNKNOWN",
                            "session_label":   SESSION_LABELS.get((session or "UNKNOWN").upper(), session),
                            "direction":       direction,
                            "consensus_score": float(score) if score else 0.0,
                            "entry_price":     entry_price,
                            "exit_price":      future_price,
                            "pnl_estimate":    pnl,
                            "result":          res,
                        })

    except Exception as exc:
        logger.error(f"[PerfService] get_last_n_signals error: {exc}", exc_info=True)

    return result


def get_real_drawdown(days_back: int = 30) -> Dict:
    """
    Compute max drawdown from agent_decisions equity simulation.

    Logic:
    - Each BUY/SELL signal is evaluated against +3 M15 candles.
    - WIN adds +1 unit to equity, LOSS subtracts -1 unit.
    - Max drawdown = largest trough from peak in this equity curve.

    Returns:
        {
          "current_drawdown_pct": -3.2,
          "max_drawdown_pct": -8.7,
          "total_signals": 18,
          "wins": 12,
          "losses": 6,
          "win_rate": 66.7,
          "equity_curve": [...],
          "method": "simulated",
          "computed_at": "..."
        }
    """
    from app.core.database import get_db_conn, is_pool_ready

    result = {
        "current_drawdown_pct": 0.0,
        "max_drawdown_pct":     0.0,
        "total_signals":        0,
        "wins":                 0,
        "losses":               0,
        "win_rate":             0.0,
        "equity_curve":         [],
        "method":               "simulated",
        "computed_at":          datetime.now(timezone.utc).isoformat(),
        "note":                 "Simulated equity from signal quality (paper trading mode)",
    }

    if not is_pool_ready():
        return result

    try:
        since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days_back)

        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT timestamp, symbol, final_decision, consensus_score
                    FROM agent_decisions
                    WHERE timestamp >= %s
                      AND final_decision IN ('BUY', 'SELL')
                    ORDER BY timestamp ASC
                    """,
                    (since,),
                )
                rows = cur.fetchall()

                # Initialize CandlePriceHelpers cache
                helpers = {}
                def get_helper(symbol: str) -> CandlePriceHelper:
                    sym = symbol or "XAUUSD"
                    if sym not in helpers:
                        helpers[sym] = CandlePriceHelper(cur, sym, since)
                    return helpers[sym]

                equity = 100.0  # Start at 100 units
                peak   = equity
                max_dd = 0.0
                wins   = 0
                losses = 0
                curve  = []

                for ts, symbol, direction, score in rows:
                    sym = symbol or "XAUUSD"
                    helper = get_helper(sym)
                    entry  = helper.get_entry_price(ts) if ts else None
                    future = helper.get_price_after(ts, candles_forward=3) if ts else None

                    if entry is None or future is None:
                        continue  # Skip pending signals

                    outcome = _evaluate_signal(direction, entry, future)

                    # Simulate equity: +1% for win, -0.7% for loss (asymmetric R:R ~1.4)
                    if outcome == "WIN":
                        equity *= 1.01
                        wins += 1
                    else:
                        equity *= 0.993
                        losses += 1

                    # Track peak
                    if equity > peak:
                        peak = equity

                    # Drawdown from peak
                    dd = (equity - peak) / peak * 100
                    if dd < max_dd:
                        max_dd = dd

                    curve.append({
                        "timestamp": ts.isoformat() if ts else None,
                        "equity":    round(equity, 4),
                        "drawdown":  round(dd, 2),
                        "outcome":   outcome,
                    })

                total = wins + losses
                current_dd = (equity - peak) / peak * 100 if peak > 0 else 0.0

                result.update({
                    "current_drawdown_pct": round(current_dd, 2),
                    "max_drawdown_pct":     round(max_dd, 2),
                    "total_signals":        total,
                    "wins":                 wins,
                    "losses":               losses,
                    "win_rate":             round(wins / total * 100, 1) if total > 0 else 0.0,
                    "equity_curve":         curve[-50:],  # Last 50 points for charting
                    "peak_equity":          round(peak, 4),
                    "current_equity":       round(equity, 4),
                })

    except Exception as exc:
        logger.error(f"[PerfService] get_real_drawdown error: {exc}", exc_info=True)

    return result


def get_monthly_pnl_from_csv(symbol: str = "XAUUSD", year: Optional[int] = None, month: Optional[int] = None) -> List[Dict]:
    """
    Calculate monthly Profit/Loss from Backtest_Results CSV files.
    
    Args:
        symbol: Trading symbol (default: XAUUSD)
        year: Specific year to fetch (if None, reads from all available files)
        month: Specific month to filter (1-12, if None shows all months)
    
    Returns:
        List of monthly P&L data:
        [
            {
                "month": "January",
                "year": 2025,
                "month_num": 1,
                "trades": 12,
                "executed_trades": 10,
                "profit": 450.50,
                "loss": -200.30,
                "net_profit": 250.20,
                "win_rate": 70.0,
                "winning_trades": 7,
                "losing_trades": 3
            },
            ...
        ]
    """
    import os
    import csv
    from pathlib import Path
    
    try:
        # Find backtest_result directory
        project_root = Path(__file__).parent.parent.parent.parent.parent  # go up to Project MT5
        backtest_dir = project_root / "Backtest_result"
        
        if not backtest_dir.exists():
            logger.warning(f"Backtest directory not found: {backtest_dir}")
            return []
        
        # Get all backtest files
        pattern = f"Backtest_Results_{symbol}_*.csv"
        matching_files = list(backtest_dir.glob(pattern))
        
        if not matching_files:
            logger.warning(f"No backtest files found for {symbol}")
            return []
        
        # Sort by filename
        matching_files.sort()
        
        # Filter files by year if specified
        files_to_process = []
        if year:
            for f in matching_files:
                # Extract year from filename: Backtest_Results_XAUUSD_YYYY-MM-DD.csv
                try:
                    parts = f.stem.split('_')
                    if len(parts) >= 4:
                        date_parts = parts[-1].split('-')
                        if len(date_parts) >= 1 and date_parts[0].isdigit():
                            file_year = int(date_parts[0])
                            if file_year == year:
                                files_to_process.append(f)
                except (ValueError, IndexError):
                    continue
            
            if not files_to_process:
                logger.warning(f"No backtest files found for year {year}")
                return []
        else:
            # If no year specified, use all files
            files_to_process = matching_files
        
        logger.info(f"Processing {len(files_to_process)} backtest file(s) for year={year}, month={month}")
        
        # Parse CSV and group by month
        monthly_data: Dict[tuple, Dict] = {}  # (year, month_num) -> data
        
        for csv_file in files_to_process:
            logger.info(f"Reading backtest file: {csv_file}")
            
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    # Skip rejected trades
                    if row.get('Status', '').upper() == 'REJECTED':
                        continue
                    
                    # Skip trades without exit time
                    exit_time_str = row.get('ExitTime', '')
                    if not exit_time_str or exit_time_str == '1970.01.01 00:00:00':
                        continue
                    
                    try:
                        # Parse exit time
                        exit_dt = datetime.strptime(exit_time_str, '%Y.%m.%d %H:%M:%S')
                        year_key = exit_dt.year
                        month_key = exit_dt.month
                        
                        # Filter by month if specified
                        if month and month_key != month:
                            continue
                        
                        month_key_tuple = (year_key, month_key)
                        
                        # Initialize month bucket if not exists
                        if month_key_tuple not in monthly_data:
                            month_names = ['', 'January', 'February', 'March', 'April', 'May', 
                                          'June', 'July', 'August', 'September', 'October', 'November', 'December']
                            monthly_data[month_key_tuple] = {
                                'month': month_names[month_key],
                                'year': year_key,
                                'month_num': month_key,
                                'trades': 0,
                                'executed_trades': 0,
                                'winning_trades': 0,
                                'losing_trades': 0,
                                'profit': 0.0,
                                'loss': 0.0,
                                'net_profit': 0.0,
                                'win_rate': 0.0,
                            }
                        
                        monthly_data[month_key_tuple]['trades'] += 1
                        monthly_data[month_key_tuple]['executed_trades'] += 1
                        
                        # Get net profit
                        try:
                            net_profit = float(row.get('Net_Profit', 0))
                        except (ValueError, TypeError):
                            net_profit = 0.0
                        
                        if net_profit > 0:
                            monthly_data[month_key_tuple]['winning_trades'] += 1
                            monthly_data[month_key_tuple]['profit'] += net_profit
                        elif net_profit < 0:
                            monthly_data[month_key_tuple]['losing_trades'] += 1
                            monthly_data[month_key_tuple]['loss'] += net_profit
                        
                        monthly_data[month_key_tuple]['net_profit'] += net_profit
                        
                    except ValueError as e:
                        logger.warning(f"Error parsing row: {e}")
                        continue
        
        # Calculate win rates and convert to list
        result = []
        for (year_key, month_num), data in sorted(monthly_data.items()):
            total = data['executed_trades']
            if total > 0:
                data['win_rate'] = round(data['winning_trades'] / total * 100, 2)
            else:
                data['win_rate'] = 0.0
            
            # Round monetary values
            data['profit'] = round(data['profit'], 2)
            data['loss'] = round(data['loss'], 2)
            data['net_profit'] = round(data['net_profit'], 2)
            
            result.append(data)
        
        logger.info(f"Calculated monthly P&L for {len(result)} months")
        return result
    
    except Exception as e:
        logger.error(f"Error reading backtest CSV: {e}", exc_info=True)
        return []


def list_available_backtest_files(symbol: str = "XAUUSD") -> List[Dict]:
    """List available backtest result files."""
    from pathlib import Path

    try:
        project_root = Path(__file__).parent.parent.parent.parent.parent
        backtest_dir = project_root / "Backtest_result"
        
        if not backtest_dir.exists():
            return []
        
        pattern = f"Backtest_Results_{symbol}_*.csv"
        matching_files = list(backtest_dir.glob(pattern))
        
        result = []
        for f in matching_files:
            # Extract date from filename: Backtest_Results_XAUUSD_YYYY-MM-DD.csv
            parts = f.stem.split('_')
            if len(parts) >= 4:
                date_str = '_'.join(parts[-3:])  # Get YYYY-MM-DD
                result.append({
                    'filename': f.name,
                    'date': date_str,
                    'path': str(f)
                })
        
        # Sort by date descending
        result.sort(key=lambda x: x['date'], reverse=True)
        return result
    
    except Exception as e:
        logger.error(f"Error listing backtest files: {e}")
        return []


def list_available_years(symbol: str = "XAUUSD") -> List[int]:
    """
    List available years from backtest CSV files.
    
    Returns:
        List of years: [2020, 2021, 2022, 2023, 2024, 2025, 2026]
    """
    from pathlib import Path
    
    try:
        project_root = Path(__file__).parent.parent.parent.parent.parent
        backtest_dir = project_root / "Backtest_result"
        
        if not backtest_dir.exists():
            return []
        
        # Find all backtest result files for this symbol
        pattern = f"Backtest_Results_{symbol}_*.csv"
        matching_files = list(backtest_dir.glob(pattern))
        
        years = set()
        for f in matching_files:
            # Extract year from filename: Backtest_Results_XAUUSD_YYYY-MM-DD.csv
            # or Backtest_Results_XAUUSD_2025-12-30.csv
            try:
                parts = f.stem.split('_')
                if len(parts) >= 4:
                    # Get date part: YYYY-MM-DD
                    date_parts = parts[-1].split('-')
                    if len(date_parts) >= 1 and date_parts[0].isdigit():
                        year = int(date_parts[0])
                        years.add(year)
            except (ValueError, IndexError):
                continue
        
        return sorted(list(years))

    except Exception as e:
        logger.error(f"Error listing available years: {e}")
        return []


def get_backtest_summary_from_csv(symbol: str = "XAUUSD", year: Optional[int] = None) -> Dict:
    """
    Read real performance metrics from Backtest_Summary_{symbol}_*.csv files.

    Returns aggregated or per-year summary:
        {
            "max_drawdown": float,       # largest across matched files
            "profit_factor": float,      # profit-weighted across matched files
            "win_rate": float,
            "total_trades": int,
            "winning_trades": int,
            "losing_trades": int,
            "total_profit": float,
            "per_year": { 2020: {...}, ... }   # only when year is None
        }
    """
    import csv
    from pathlib import Path

    try:
        project_root = Path(__file__).parent.parent.parent.parent.parent
        backtest_dir = project_root / "Backtest_result"

        if not backtest_dir.exists():
            return {}

        matching = sorted(backtest_dir.glob(f"Backtest_Summary_{symbol}_*.csv"))
        if not matching:
            return {}

        per_year: Dict[int, Dict] = {}
        for f in matching:
            parts = f.stem.split('_')
            if len(parts) < 4:
                continue
            file_year = int(parts[-1].split('-')[0])
            if year and file_year != year:
                continue
            with open(f, 'r', encoding='utf-8') as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    try:
                        per_year[file_year] = {
                            "total_trades": int(float(row.get("TotalTrades", 0) or 0)),
                            "winning_trades": int(float(row.get("WinningTrades", 0) or 0)),
                            "losing_trades": int(float(row.get("LosingTrades", 0) or 0)),
                            "win_rate": float(row.get("WinRate", 0) or 0),
                            "total_profit": float(row.get("TotalProfit", 0) or 0),
                            "max_drawdown": float(row.get("MaxDrawdown", 0) or 0),
                            "profit_factor": float(row.get("ProfitFactor", 0) or 0),
                        }
                    except (ValueError, TypeError):
                        continue

        if not per_year:
            return {}

        # Aggregate: profit-weighted PF, largest drawdown
        total_profit = sum(d["total_profit"] for d in per_year.values())
        total_trades = sum(d["total_trades"] for d in per_year.values())
        winning_trades = sum(d["winning_trades"] for d in per_year.values())
        losing_trades = sum(d["losing_trades"] for d in per_year.values())
        max_drawdown = max((d["max_drawdown"] for d in per_year.values()), default=0.0)

        # ponytail: profit-weighted PF — sum(profit*pf)/sum(profit), falls back to mean
        pf_num = sum(d["profit_factor"] * d["total_profit"] for d in per_year.values() if d["total_profit"] > 0)
        pf_den = sum(d["total_profit"] for d in per_year.values() if d["total_profit"] > 0)
        profit_factor = (pf_num / pf_den) if pf_den > 0 else (
            sum(d["profit_factor"] for d in per_year.values()) / len(per_year)
        )

        return {
            "max_drawdown": round(max_drawdown, 2),
            "profit_factor": round(profit_factor, 2),
            "win_rate": round((winning_trades / total_trades * 100) if total_trades > 0 else 0, 2),
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "total_profit": round(total_profit, 2),
            "per_year": per_year if year is None else None,
        }

    except Exception as e:
        logger.error(f"Error reading backtest summary CSV: {e}", exc_info=True)
        return {}
