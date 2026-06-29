"""
Rongsokan Data Reader Service
Reads data from D:\Project\Project MT5\Other\Backtest_rongsokan for chart overlay
"""

import csv
import json
import logging
import re
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional

logger = logging.getLogger(__name__)

# Global cache
_cached_candles: Dict[str, Dict] = {}
_cached_trades: Optional[List[Dict]] = None
_cached_structure_lines: Optional[Dict] = None
_cached_timestamp: float = 0
CACHE_TTL: int = 900

# Rongsokan data directory
RONGSONKAN_DIR = Path(r"D:\Project\Project MT5\Other\Backtest_rongsokan")


class RongsokanDataReader:

    def __init__(self):
        logger.info(f"[RongsokanDataReader] Dir: {RONGSONKAN_DIR}")

    # ===========================
    # CANDLES (MarketData CSVs)
    # ===========================
    def _get_market_data_files(self, symbol: str, timeframe: str) -> List[Path]:
        matches = sorted(RONGSONKAN_DIR.glob(f"MarketData_{symbol}_{timeframe}_*.csv"))
        if not matches:
            logger.warning(f"[RongsokanDataReader] No MarketData CSV for {symbol} {timeframe}")
        return matches

    def count_candle_rows(self, symbol: str = "XAUUSD", timeframe: str = "M15") -> int:
        files = self._get_market_data_files(symbol, timeframe)
        total = 0
        for f in files:
            with open(f, "r", encoding="utf-8") as fh:
                for _ in fh:
                    total += 1
            total -= 1  # header
        return total

    def get_candles(
        self,
        symbol: str = "XAUUSD",
        timeframe: str = "M15",
        from_date: str = "2020-01-01",
        mode: str = "recent",
        center_date: Optional[str] = None,
        limit: int = 30000,
    ) -> Dict:
        """Get candles - supports recent, full, and window modes."""
        cache_key = f"{symbol}_{timeframe}_{mode}_{from_date}_{center_date}_{limit}"
        
        # Check cache
        now = time.time()
        if cache_key in _cached_candles and (now - _cached_candles[cache_key]["timestamp"]) < CACHE_TTL:
            logger.info(f"[RongsokanDataReader] Using cached candles ({_cached_candles[cache_key]['data']['candles_count']} candles)")
            return _cached_candles[cache_key]["data"]

        files = self._get_market_data_files(symbol, timeframe)
        if not files:
            return {"symbol": symbol, "timeframe": timeframe, "candles": [], "candles_count": 0, "mode": mode}

        # Determine date range
        if center_date:
            center_dt = datetime.strptime(center_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            from_dt = center_dt - timedelta(days=90)
            to_dt = center_dt + timedelta(days=90)
            mode = "window"
            limit = 20000
            logger.info(f"[RONGSOKAN WINDOW] Center: {center_date}, Window: {from_dt} -> {to_dt}")
        elif mode == "full":
            from_dt = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            to_dt = None
            limit = 250000
            logger.info(f"[RONGSOKAN FULL] Loading from {from_date}, limit={limit}")
        else:
            from_dt = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            to_dt = None
            limit = 30000
            logger.info(f"[RONGSOKAN RECENT] Loading from {from_date}, limit={limit}")

        formatted_candles = []
        from_year = from_dt.year

        for path in files:
            file_year_match = re.search(r"_(\d{4})-\d{2}-\d{2}\.csv$", path.name)
            if file_year_match and int(file_year_match.group(1)) < from_year:
                continue

            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        dt = datetime.strptime(row["Time"].strip(), "%Y.%m.%d %H:%M:%S").replace(tzinfo=timezone.utc)
                        if dt < from_dt:
                            continue
                        if to_dt and dt > to_dt:
                            continue

                        ts = int(dt.timestamp())
                        candle = {
                            "time": ts,
                            "open": float(row["Open"]),
                            "high": float(row["High"]),
                            "low": float(row["Low"]),
                            "close": float(row["Close"]),
                        }
                        ema = row.get("EMA200", "").strip()
                        if ema:
                            candle["ema200"] = round(float(ema), 2)
                        formatted_candles.append(candle)
                    except (ValueError, KeyError):
                        continue

        formatted_candles.sort(key=lambda c: c["time"])
        seen = set()
        formatted_candles = [c for c in formatted_candles if not (c["time"] in seen or seen.add(c["time"]))]
        formatted_candles = formatted_candles[:limit]

        result = {
            "symbol": symbol,
            "timeframe": timeframe,
            "candles": formatted_candles,
            "ema_periods": {"ema200": 200},
            "mode": mode,
            "from_date": from_date,
            "center_date": center_date,
            "candles_count": len(formatted_candles),
            "timezone": {
                "broker_offset_hours": 0,
                "display_mode": "utc",
                "candle_times_are_utc": True,
            },
        }

        _cached_candles[cache_key] = {"data": result, "timestamp": now}
        logger.info(f"[RongsokanDataReader] Returning {len(formatted_candles)} candles (mode={mode})")
        return result

    async def stream_candles(
        self,
        symbol: str = "XAUUSD",
        timeframe: str = "M15",
        from_date: str = "2020-01-01",
        mode: str = "full",
    ) -> AsyncGenerator[str, None]:
        """Stream candles with NDJSON progress."""
        files = self._get_market_data_files(symbol, timeframe)
        if not files:
            yield json.dumps({"type": "error", "message": f"No MarketData CSV for {symbol} {timeframe}"})
            return

        from_dt = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)

        yield json.dumps({"type": "progress", "percent": 0, "step": "Counting rows...", "total_estimated": 0})
        total_estimated = self.count_candle_rows(symbol, timeframe)
        yield json.dumps({
            "type": "progress", "percent": 0,
            "step": f"{total_estimated:,} rows total. Processing...",
            "total_estimated": total_estimated,
        })

        candles: List[Dict] = []
        row_count = 0
        file_count = len(files)

        for file_idx, file_path in enumerate(files, 1):
            year_match = re.search(r"(\d{4})", file_path.stem)
            year = year_match.group(1) if year_match else "unknown"

            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        ts = datetime.strptime(row["Time"], "%Y.%m.%d %H:%M:%S").replace(tzinfo=timezone.utc)
                        if ts < from_dt:
                            continue
                        candles.append({
                            "time": int(ts.timestamp()),
                            "open": float(row["Open"]),
                            "high": float(row["High"]),
                            "low": float(row["Low"]),
                            "close": float(row["Close"]),
                            "ema200": round(float(row["EMA200"]), 2),
                        })
                    except (KeyError, ValueError) as e:
                        logger.warning(f"Skipping row in {file_path.name}: {e}")
                        continue

                    row_count += 1
                    if row_count % 500 == 0:
                        percent = round(row_count / total_estimated * 100, 1) if total_estimated > 0 else 0
                        step = f"File {file_idx}/{file_count} ({year}) - {row_count:,}/{total_estimated:,} rows"
                        yield json.dumps({
                            "type": "progress", "percent": min(percent, 99.9),
                            "step": step, "total_estimated": total_estimated,
                        })

        candles.sort(key=lambda c: c["time"])
        seen = set()
        unique = []
        for c in candles:
            if c["time"] not in seen:
                seen.add(c["time"])
                unique.append(c)
        candles = unique[:200000]

        yield json.dumps({
            "type": "complete",
            "data": {
                "symbol": symbol,
                "timeframe": timeframe,
                "candles": candles,
                "total": len(candles),
                "mode": mode,
                "timezone": "UTC",
            }
        })

    # ===========================
    # TRADES (Backtest_Results)
    # ===========================
    def get_trades(self) -> Dict:
        """Get all backtest trades with SL/TP for chart overlay."""
        global _cached_trades, _cached_timestamp
        now = time.time()
        if _cached_trades is not None and (now - _cached_timestamp) < CACHE_TTL:
            logger.info(f"[RongsokanDataReader] Using cached trades ({len(_cached_trades)} trades)")
            return self._build_trades_response(_cached_trades)

        if not RONGSONKAN_DIR.exists():
            return self._empty_trades_response()

        csv_files = sorted(RONGSONKAN_DIR.glob("Backtest_Results_XAUUSD_*.csv"))
        if not csv_files:
            return self._empty_trades_response()

        logger.info(f"[RongsokanDataReader] Found {len(csv_files)} Backtest_Results CSV files")
        all_trades = []
        for csv_file in csv_files:
            file_count = 0
            try:
                with open(csv_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        trade = self._parse_trade_row(row)
                        if trade:
                            all_trades.append(trade)
                            file_count += 1
                logger.info(f"[RongsokanDataReader] {csv_file.name}: {file_count} trades")
            except Exception as e:
                logger.warning(f"[RongsokanDataReader] Error {csv_file.name}: {e}")

        trades_by_year = {}
        for trade in all_trades:
            year = datetime.fromisoformat(trade['entry_time'].replace('Z', '+00:00')).year
            trades_by_year[year] = trades_by_year.get(year, 0) + 1
        logger.info(f"[RongsokanDataReader] Total: {len(all_trades)}, by year: {trades_by_year}")

        _cached_trades = all_trades
        _cached_timestamp = now
        return self._build_trades_response(all_trades)

    def _parse_trade_row(self, row: Dict) -> Optional[Dict]:
        try:
            if row.get('Status', '').upper().strip() != 'EXECUTED':
                return None

            trade_type = row.get('Type', '').strip()
            entry_price = self._parse_float(row.get('EntryPrice'))
            sl = self._parse_float(row.get('SL'))
            tp = self._parse_float(row.get('TP'))
            profit = self._parse_float(row.get('Profit'), 0)
            lot = self._parse_float(row.get('LotSize'), 0)
            session = row.get('Session', '')

            if not trade_type or entry_price is None:
                return None

            entry_ts = self._parse_time(row.get('EntryTime', ''))
            if entry_ts is None:
                return None

            exit_str = row.get('ExitTime', '')
            exit_ts = None
            if exit_str and exit_str != '1970.01.01 00:00:00':
                exit_ts = self._parse_time(exit_str)

            return {
                'type': trade_type,
                'entry_price': entry_price,
                'sl': sl,
                'tp': tp,
                'profit': profit,
                'lot_size': lot,
                'session': session,
                'entry_time': entry_ts.isoformat(),
                'entry_time_ts': int(entry_ts.timestamp()),
                'exit_time': exit_ts.isoformat() if exit_ts else None,
                'exit_time_ts': int(exit_ts.timestamp()) if exit_ts else None,
            }
        except Exception:
            return None

    def _parse_float(self, val: Optional[str], default=None) -> Optional[float]:
        if not val:
            return default
        try:
            v = float(val)
            return None if v == 0 and default is None else v
        except (ValueError, TypeError):
            return default

    def _parse_time(self, val: str) -> Optional[datetime]:
        for fmt in ['%Y.%m.%d %H:%M:%S', '%Y-%m-%d %H:%M:%S']:
            try:
                return datetime.strptime(val, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return None

    def _build_trades_response(self, trades: List[Dict]) -> Dict:
        return {
            'trades': trades,
            'total_trades': len(trades),
            'last_updated': datetime.now(timezone.utc).isoformat(),
        }

    def _empty_trades_response(self) -> Dict:
        return {'trades': [], 'total_trades': 0, 'last_updated': datetime.now(timezone.utc).isoformat()}

    # ===========================
    # MARKET STRUCTURE LINES (LLHHBOSData)
    # ===========================
    def get_structure_lines(self, from_date: str = "2020-01-01", to_date: Optional[str] = None) -> Dict:
        """Get market structure lines from LLHHBOSData CSV."""
        global _cached_structure_lines, _cached_timestamp
        now = time.time()
        cache_key = f"structure_{from_date}_{to_date}"
        
        if _cached_structure_lines is not None and (now - _cached_timestamp) < CACHE_TTL:
            logger.info(f"[RongsokanDataReader] Using cached structure lines")
            return _cached_structure_lines

        if not RONGSONKAN_DIR.exists():
            return self._empty_structure_response()

        csv_files = sorted(RONGSONKAN_DIR.glob("LLHHBOSData_*.csv"))
        if not csv_files:
            return self._empty_structure_response()

        from_dt = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        to_dt = datetime.strptime(to_date, "%Y-%m-%d").replace(tzinfo=timezone.utc) if to_date else None

        logger.info(f"[RongsokanDataReader] Found {len(csv_files)} LLHHBOSData CSV files")

        bos_lines = []
        choch_lines = []
        hh_points = []
        ll_points = []

        for csv_file in csv_files:
            try:
                with open(csv_file, 'r', encoding='utf-8') as f:
                    # Skip the first line (header: "=== Market Structure Events (Sorted by Time) ===")
                    first_line = f.readline()
                    reader = csv.DictReader(f)
                    for row in reader:
                        try:
                            # CSV columns: Type,Direction/Action,Price,Time,Timeframe,Status,PreviousPrice,PreviousTime
                            point_type = row.get("Type", "").strip()
                            direction_action = row.get("Direction/Action", "").strip()
                            price_str = row.get("Price", "").strip()
                            time_str = row.get("Time", "").strip()
                            timeframe = row.get("Timeframe", "M15").strip()
                            status = row.get("Status", "").strip()
                            previous_price = row.get("PreviousPrice", "").strip()
                            previous_time = row.get("PreviousTime", "").strip()

                            if not point_type or not price_str or not time_str:
                                continue

                            dt = datetime.strptime(time_str, "%Y.%m.%d %H:%M:%S").replace(tzinfo=timezone.utc)
                            if dt < from_dt:
                                continue
                            if to_dt and dt > to_dt:
                                continue

                            point = {
                                "time": time_str,
                                "timestamp": int(dt.timestamp()),
                                "price": float(price_str),
                                "type": point_type,
                                "direction": direction_action.upper() if direction_action else "",
                                "timeframe": timeframe,
                                "status": status,
                            }

                            if previous_price and previous_price != "1970.01.01 00:00:00":
                                try:
                                    point["previous_price"] = float(previous_price)
                                except ValueError:
                                    pass

                            point_type_upper = point_type.upper()
                            if point_type_upper == "BOS":
                                bos_lines.append(point)
                            elif point_type_upper == "CHOCH":
                                choch_lines.append(point)
                            elif point_type_upper == "HH":
                                hh_points.append(point)
                            elif point_type_upper == "LL":
                                ll_points.append(point)
                        except (ValueError, KeyError) as e:
                            logger.debug(f"Skipping row in {csv_file.name}: {e}")
                            continue
            except Exception as e:
                logger.warning(f"[RongsokanDataReader] Error reading {csv_file.name}: {e}")

        result = {
            "bos_lines": bos_lines,
            "choch_lines": choch_lines,
            "hh_points": hh_points,
            "ll_points": ll_points,
            "total_points": len(bos_lines) + len(choch_lines) + len(hh_points) + len(ll_points),
            "time_range_hours": 0,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

        _cached_structure_lines = result
        _cached_timestamp = now
        logger.info(f"[RongsokanDataReader] Structure: BOS={len(bos_lines)}, CHoCH={len(choch_lines)}, HH={len(hh_points)}, LL={len(ll_points)}")
        return result

    def _empty_structure_response(self) -> Dict:
        return {
            "bos_lines": [], "choch_lines": [], "hh_points": [], "ll_points": [],
            "total_points": 0, "time_range_hours": 0,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }


# Singleton instance
rongsokan_reader = RongsokanDataReader()