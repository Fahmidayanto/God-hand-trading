"""
Backtest Trades Reader Service
Reads trade entries (with SL/TP) from Backtest_Results CSV for chart overlay
"""

import csv
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_cached_trades: Optional[List[Dict]] = None
_cached_timestamp: float = 0
CACHE_TTL: int = 900


class BacktestTradesReader:

    def __init__(self):
        backend_dir = Path(__file__).parent.parent.parent
        project_root = backend_dir.parent
        self.backtest_dir = project_root.parent / "Backtest_result"
        logger.info(f"[BacktestTradesReader] Dir: {self.backtest_dir}")

    def get_all_trades(self) -> Dict:
        global _cached_trades, _cached_timestamp
        now = time.time()
        if _cached_trades is not None and (now - _cached_timestamp) < CACHE_TTL:
            logger.info(f"[BacktestTradesReader] Using cached data ({len(_cached_trades)} trades)")
            return self._build_response(_cached_trades)

        if not self.backtest_dir.exists():
            return self._empty_response()

        csv_files = sorted(self.backtest_dir.glob("Backtest_Results_XAUUSD_*.csv"))
        if not csv_files:
            return self._empty_response()

        logger.info(f"[BacktestTradesReader] Found {len(csv_files)} CSV files")
        all_trades = []
        for csv_file in csv_files:
            file_count = 0
            try:
                with open(csv_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        trade = self._parse_row(row)
                        if trade:
                            all_trades.append(trade)
                            file_count += 1
                logger.info(f"[BacktestTradesReader] {csv_file.name}: {file_count} trades")
            except Exception as e:
                logger.warning(f"[BacktestTradesReader] Error {csv_file.name}: {e}")

        # Debug: Count trades by year
        trades_by_year = {}
        for trade in all_trades:
            year = datetime.fromisoformat(trade['entry_time'].replace('Z', '+00:00')).year
            trades_by_year[year] = trades_by_year.get(year, 0) + 1
        logger.info(f"[BacktestTradesReader] Total: {len(all_trades)}, by year: {trades_by_year}")
        
        _cached_trades = all_trades
        _cached_timestamp = now
        return self._build_response(all_trades)

    def _parse_row(self, row: Dict) -> Optional[Dict]:
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

    def _build_response(self, trades: List[Dict]) -> Dict:
        return {
            'trades': trades,
            'total_trades': len(trades),
            'last_updated': datetime.now(timezone.utc).isoformat(),
        }

    def _empty_response(self) -> Dict:
        return {'trades': [], 'total_trades': 0, 'last_updated': datetime.now(timezone.utc).isoformat()}
