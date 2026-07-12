"""
Market Structure Lines Reader Service
Reads BoS, CHoCH, HH, LL points from LLHHBOSData CSV for chart visualization
"""

import csv
import io
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Module-level cache: all parsed rows from all CSV files, refreshed every 15min
_cached_all_rows: Optional[List[Dict]] = None
_cached_timestamp: float = 0
CACHE_TTL: int = 900  # 15 minutes


class MarketStructureLinesReader:
    """Reads market structure points (BoS, CHoCH, HH, LL) for chart overlay"""

    # Broker timezone offset from UTC (default 3 = GMT+3, matching MT5_BROKER_TIMEZONE_OFFSET)
    BROKER_OFFSET_HOURS: int = 3

    def __init__(self, broker_offset_hours: int | None = None):
        # Path to Backtest_result/LLHHBOSData_XAUUSD_*.csv
        backend_dir = Path(__file__).parent.parent.parent
        project_root = backend_dir.parent
        self.backtest_dir = project_root.parent / "Backtest_result"

        # Allow caller to override broker offset; fall back to config if available
        if broker_offset_hours is not None:
            self.BROKER_OFFSET_HOURS = broker_offset_hours
        else:
            try:
                from app.config import get_settings
                self.BROKER_OFFSET_HOURS = get_settings().MT5_BROKER_TIMEZONE_OFFSET
            except Exception:
                pass  # use class default

        logger.info(f"[MarketStructureLinesReader] Backtest dir: {self.backtest_dir}, broker offset: GMT+{self.BROKER_OFFSET_HOURS}")

    def _extract_date(self, path: Path) -> str:
        match = re.search(r'(\d{4}-\d{2}-\d{2})', path.stem)
        return match.group(1) if match else '0000-00-00'

    def _parse_row(self, row: Dict) -> Optional[Dict]:
        try:
            event_type = row.get('Type', '').upper().strip()
            direction = row.get('Direction/Action', '').strip()
            price_str = row.get('Price', '0')
            time_str = row.get('Time', '')
            timeframe = row.get('Timeframe', 'M15')
            status = row.get('Status', '')
            prev_price_str = row.get('PreviousPrice', '').strip()

            if not event_type or not time_str or not price_str:
                return None

            try:
                event_time_naive = datetime.strptime(time_str, '%Y.%m.%d %H:%M:%S')
                event_time = event_time_naive.replace(tzinfo=timezone.utc)
            except:
                try:
                    event_time_naive = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                    event_time = event_time_naive.replace(tzinfo=timezone.utc)
                except:
                    return None

            try:
                price = float(price_str)
            except:
                return None

            is_bullish = 'BULL' in direction.upper() or 'UP' in direction.upper()
            is_bearish = 'BEAR' in direction.upper() or 'DOWN' in direction.upper()

            previous_price = 0.0
            if prev_price_str and prev_price_str != '':
                try:
                    previous_price = float(prev_price_str)
                except:
                    previous_price = 0.0

            return {
                'time': event_time.isoformat(),
                'timestamp': int(event_time.timestamp() * 1000),
                'price': price,
                'type': event_type,
                'direction': 'BULLISH' if is_bullish else ('BEARISH' if is_bearish else 'NEUTRAL'),
                'timeframe': timeframe,
                'status': status,
                'previous_price': previous_price,
                '_event_time': event_time,
            }
        except Exception:
            return None

    def _load_all_csv_files(self) -> List[Dict]:
        global _cached_all_rows, _cached_timestamp
        now = time.time()
        if _cached_all_rows is not None and (now - _cached_timestamp) < CACHE_TTL:
            return _cached_all_rows

        if not self.backtest_dir.exists():
            logger.warning(f"[MarketStructureLinesReader] Directory not found: {self.backtest_dir}")
            _cached_all_rows = []
            _cached_timestamp = now
            return []

        csv_files = sorted(
            list(self.backtest_dir.glob("LLHHBOSData_XAUUSD_*.csv")),
            key=self._extract_date
        )

        if not csv_files:
            logger.warning("[MarketStructureLinesReader] No CSV files found")
            _cached_all_rows = []
            _cached_timestamp = now
            return []

        all_rows = []
        for csv_file in csv_files:
            file_rows = 0
            try:
                with open(csv_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                if len(lines) < 3:
                    continue
                csv_text = ''.join(lines[1:])
                reader = csv.DictReader(io.StringIO(csv_text))
                for row in reader:
                    parsed = self._parse_row(row)
                    if parsed:
                        all_rows.append(parsed)
                        file_rows += 1
                logger.info(f"[MarketStructureLinesReader] Loaded {self._extract_date(csv_file)}: {file_rows} rows")
            except Exception as e:
                logger.warning(f"[MarketStructureLinesReader] Error reading {csv_file.name}: {e}")

        logger.info(f"[MarketStructureLinesReader] Total loaded: {len(all_rows)} rows from {len(csv_files)} files")
        _cached_all_rows = all_rows
        _cached_timestamp = now
        return all_rows

    def _deduplicate(self, points, by_price_timeframe_only=False):
        seen = set()
        unique = []
        for point in points:
            if by_price_timeframe_only:
                key = (point['price'], point.get('timeframe', ''))
            else:
                key = (point['price'], point['timestamp'], point.get('timeframe', ''))
            if key not in seen:
                seen.add(key)
                unique.append(point)
        return unique

    def _categorize_and_finalize(self, rows: List[Dict]) -> Dict[str, List[Dict]]:
        bos_lines = []
        choch_lines = []
        hh_points = []
        ll_points = []

        for point in rows:
            event_type = point['type']
            clean_point = {k: v for k, v in point.items() if k != '_event_time'}
            if event_type == 'BOS':
                bos_lines.append(clean_point)
            elif event_type == 'CHOCH':
                choch_lines.append(clean_point)
            elif event_type == 'HH':
                hh_points.append(clean_point)
            elif event_type == 'LL':
                ll_points.append(clean_point)

        bos_lines.sort(key=lambda x: x['timestamp'])
        choch_lines.sort(key=lambda x: x['timestamp'])
        hh_points.sort(key=lambda x: x['timestamp'])
        ll_points.sort(key=lambda x: x['timestamp'])

        bos_lines = self._deduplicate(bos_lines)
        choch_lines = self._deduplicate(choch_lines)
        hh_points = self._deduplicate(hh_points, by_price_timeframe_only=True)
        ll_points = self._deduplicate(ll_points, by_price_timeframe_only=True)

        return {
            'bos_lines': bos_lines,
            'choch_lines': choch_lines,
            'hh_points': hh_points,
            'll_points': ll_points,
            'total_points': len(bos_lines) + len(choch_lines) + len(hh_points) + len(ll_points),
        }

    def get_market_structure_lines(self, hours_back: int = 48, from_date: Optional[str] = None, to_date: Optional[str] = None) -> Dict[str, List[Dict]]:
        """
        Get market structure lines.
        
        Args:
            hours_back: Number of hours to look back (default 48). Used when from_date is None.
            from_date: ISO date string (e.g. "2020-01-01"). If provided, uses absolute date range instead of hours_back.
            to_date: ISO date string (e.g. "2026-06-26"). Defaults to now if from_date is provided.
            
        Returns:
            Dictionary with lists of BoS, CHoCH, HH, LL points
        """
        try:
            if from_date is not None:
                return self._get_structure_by_date_range(from_date, to_date)

            # Legacy path: single latest CSV + hours_back
            csv_file = self._get_latest_csv_file()
            if not csv_file:
                return self._get_empty_structure()

            with open(csv_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            if len(lines) < 3:
                return self._get_empty_structure()

            csv_text = ''.join(lines[1:])
            reader = csv.DictReader(io.StringIO(csv_text))
            rows = [row for row in reader if row.get('Time') and row.get('Type')]

            cutoff_time = datetime.now() - timedelta(hours=hours_back)
            cutoff_time_utc = cutoff_time.replace(tzinfo=timezone.utc)

            filtered = []
            for row in rows:
                parsed = self._parse_row(row)
                if parsed and parsed['_event_time'] >= cutoff_time_utc:
                    filtered.append(parsed)

            result = self._categorize_and_finalize(filtered)
            result['time_range_hours'] = hours_back
            result['last_updated'] = datetime.now().isoformat()

            logger.info(f"[MarketStructureLinesReader] Loaded {result['total_points']} points (legacy, last {hours_back}h)")
            return result

        except Exception as e:
            logger.error(f"[MarketStructureLinesReader] Error: {e}", exc_info=True)
            return self._get_empty_structure()

    def _get_structure_by_date_range(self, from_date: str, to_date: Optional[str] = None) -> Dict[str, List[Dict]]:
        all_rows = self._load_all_csv_files()
        if not all_rows:
            return self._get_empty_structure()

        try:
            from_dt = datetime.strptime(from_date, '%Y-%m-%d').replace(tzinfo=timezone.utc)
        except:
            logger.warning(f"[MarketStructureLinesReader] Invalid from_date: {from_date}")
            return self._get_empty_structure()

        if to_date:
            try:
                to_dt = datetime.strptime(to_date, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            except:
                to_dt = datetime.now(timezone.utc)
        else:
            to_dt = datetime.now(timezone.utc)

        filtered = [r for r in all_rows if from_dt <= r['_event_time'] <= to_dt]

        result = self._categorize_and_finalize(filtered)
        result['time_range_hours'] = 0
        result['last_updated'] = datetime.now().isoformat()
        result['from_date'] = from_date
        result['to_date'] = to_dt.isoformat()

        logger.debug(f"[MarketStructureLinesReader] Loaded {result['total_points']} points ({from_date} to {to_dt.date()})")
        return result

    def _get_latest_csv_file(self) -> Optional[Path]:
        try:
            if not self.backtest_dir.exists():
                return None
            csv_files = list(self.backtest_dir.glob("LLHHBOSData_XAUUSD_*.csv"))
            if not csv_files:
                return None
            latest = max(csv_files, key=self._extract_date)
            logger.debug(f"[MarketStructureLinesReader] Using file: {latest.name}")
            return latest
        except Exception as e:
            logger.error(f"[MarketStructureLinesReader] Error finding CSV: {e}", exc_info=True)
            return None

    def _get_empty_structure(self) -> Dict[str, List]:
        """Return empty structure when no data available"""
        return {
            'bos_lines': [],
            'choch_lines': [],
            'hh_points': [],
            'll_points': [],
            'total_points': 0,
            'time_range_hours': 0,
            'last_updated': datetime.now().isoformat(),
        }

    def get_latest_bos(self) -> Optional[Dict]:
        """Get the most recent BoS point"""
        try:
            data = self.get_market_structure_lines(hours_back=168)
            bos_lines = data.get('bos_lines', [])
            return bos_lines[-1] if bos_lines else None
        except:
            return None

    def get_latest_choch(self) -> Optional[Dict]:
        """Get the most recent CHoCH point"""
        try:
            data = self.get_market_structure_lines(hours_back=168)
            choch_lines = data.get('choch_lines', [])
            return choch_lines[-1] if choch_lines else None
        except:
            return None

    def get_structure_summary(self, hours_back: int = 48) -> str:
        """
        Get human-readable summary of recent structure
        
        Returns:
            String summary
        """
        try:
            data = self.get_market_structure_lines(hours_back)
            bos_count = len(data['bos_lines'])
            choch_count = len(data['choch_lines'])
            hh_count = len(data['hh_points'])
            ll_count = len(data['ll_points'])
            return (
                f"Last {hours_back}h: "
                f"{bos_count} BoS, {choch_count} CHoCH, "
                f"{hh_count} HH, {ll_count} LL"
            )
        except:
            return "Structure data not available"
