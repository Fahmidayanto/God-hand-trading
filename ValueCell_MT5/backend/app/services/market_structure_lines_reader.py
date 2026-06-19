"""
Market Structure Lines Reader Service
Reads BoS, CHoCH, HH, LL points from LLHHBOSData CSV for chart visualization
"""

import csv
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class MarketStructureLinesReader:
    """Reads market structure points (BoS, CHoCH, HH, LL) for chart overlay"""
    
    def __init__(self):
        # Path to Backtest_result/LLHHBOSData_XAUUSD_*.csv
        backend_dir = Path(__file__).parent.parent.parent
        project_root = backend_dir.parent
        self.backtest_dir = project_root.parent / "Backtest_result"
        
        logger.info(f"[MarketStructureLinesReader] Backtest dir: {self.backtest_dir}")
    
    def get_latest_csv_file(self) -> Optional[Path]:
        """
        Find the latest LLHHBOSData CSV file
        
        Returns:
            Path to the latest CSV file or None
        """
        try:
            if not self.backtest_dir.exists():
                logger.warning(f"[MarketStructureLinesReader] Directory not found: {self.backtest_dir}")
                return None
            
            # Find all LLHHBOSData files
            csv_files = list(self.backtest_dir.glob("LLHHBOSData_XAUUSD_*.csv"))
            
            if not csv_files:
                logger.warning("[MarketStructureLinesReader] No LLHHBOSData CSV files found")
                return None
            
            # Get the latest file by modification time
            latest_file = max(csv_files, key=lambda p: p.stat().st_mtime)
            logger.info(f"[MarketStructureLinesReader] Using file: {latest_file.name}")
            
            return latest_file
        
        except Exception as e:
            logger.error(f"[MarketStructureLinesReader] Error finding CSV: {e}", exc_info=True)
            return None
    
    def get_market_structure_lines(self, hours_back: int = 48) -> Dict[str, List[Dict]]:
        """
        Get market structure lines for the last N hours
        
        Args:
            hours_back: Number of hours to look back (default 48 hours)
            
        Returns:
            Dictionary with lists of BoS, CHoCH, HH, LL points
        """
        try:
            csv_file = self.get_latest_csv_file()
            
            if not csv_file:
                return self._get_empty_structure()
            
            # Read CSV file
            with open(csv_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Skip first line (header title), second line is column headers
            if len(lines) < 3:
                logger.warning("[MarketStructureLinesReader] CSV file too short")
                return self._get_empty_structure()
            
            # Line 0: "=== Market Structure Events..."
            # Line 1: "Type,Direction/Action,Price,Time..."
            # Line 2+: Data rows
            
            logger.info(f"[MarketStructureLinesReader] CSV has {len(lines)} lines")
            logger.debug(f"Header line: {lines[1].strip()}")
            
            # Parse CSV starting from line 1 (header) and line 2+ (data)
            csv_text = ''.join(lines[1:])  # Start from header line
            import io
            reader = csv.DictReader(io.StringIO(csv_text))
            rows = [row for row in reader if row.get('Time') and row.get('Type')]
            
            logger.info(f"[MarketStructureLinesReader] Parsed {len(rows)} data rows")
            
            if not rows:
                logger.warning("[MarketStructureLinesReader] No data rows found")
                return self._get_empty_structure()
            
            # Filter by time range
            cutoff_time = datetime.now() - timedelta(hours=hours_back)
            
            bos_lines = []
            choch_lines = []
            hh_points = []
            ll_points = []
            
            for row in rows:
                try:
                    event_type = row.get('Type', '').upper().strip()
                    direction = row.get('Direction/Action', '').strip()
                    price_str = row.get('Price', '0')
                    time_str = row.get('Time', '')
                    timeframe = row.get('Timeframe', 'M15')
                    status = row.get('Status', '')
                    
                    # Skip if no valid data
                    if not event_type or not time_str or not price_str:
                        continue
                    
                    # Parse time WITHOUT timezone conversion
                    # CSV stores time in broker/local timezone
                    # We need to treat this as UTC to avoid timezone shift
                    try:
                        # Parse as naive datetime
                        event_time_naive = datetime.strptime(time_str, '%Y.%m.%d %H:%M:%S')
                        # Treat it as UTC (no timezone conversion)
                        # This prevents Python from applying local timezone offset
                        from datetime import timezone
                        event_time = event_time_naive.replace(tzinfo=timezone.utc)
                    except:
                        try:
                            event_time_naive = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                            from datetime import timezone
                            event_time = event_time_naive.replace(tzinfo=timezone.utc)
                        except:
                            continue
                    
                    # Skip old events (convert cutoff_time to UTC aware for comparison)
                    from datetime import timezone
                    cutoff_time_utc = cutoff_time.replace(tzinfo=timezone.utc)
                    if event_time < cutoff_time_utc:
                        continue
                    
                    # Parse price
                    try:
                        price = float(price_str)
                    except:
                        continue
                    
                    # Determine if bullish or bearish
                    is_bullish = 'BULL' in direction.upper() or 'UP' in direction.upper()
                    is_bearish = 'BEAR' in direction.upper() or 'DOWN' in direction.upper()
                    
                    # Create point data
                    point = {
                        'time': event_time.isoformat(),
                        'timestamp': int(event_time.timestamp() * 1000),  # milliseconds
                        'price': price,
                        'type': event_type,
                        'direction': 'BULLISH' if is_bullish else ('BEARISH' if is_bearish else 'NEUTRAL'),
                        'timeframe': timeframe,
                        'status': status,
                    }
                    
                    # Categorize by type
                    if event_type == 'BOS':
                        bos_lines.append(point)
                        logger.debug(f"Added BoS: {price} at {time_str}")
                    elif event_type == 'CHOCH':
                        choch_lines.append(point)
                        logger.debug(f"Added CHoCH: {price} at {time_str}")
                    elif event_type == 'HH':
                        hh_points.append(point)
                        logger.debug(f"Added HH: {price} at {time_str}")
                    elif event_type == 'LL':
                        ll_points.append(point)
                        logger.debug(f"Added LL: {price} at {time_str}")
                
                except Exception as e:
                    logger.debug(f"[MarketStructureLinesReader] Error parsing row: {e}")
                    continue
            
            # Sort by time
            bos_lines.sort(key=lambda x: x['timestamp'])
            choch_lines.sort(key=lambda x: x['timestamp'])
            hh_points.sort(key=lambda x: x['timestamp'])
            ll_points.sort(key=lambda x: x['timestamp'])
            
            # Remove duplicates (same price, time, AND timeframe)
            def deduplicate(points):
                seen = set()
                unique = []
                for point in points:
                    # Include timeframe in key so M15 and H1 events at same
                    # price/time are kept as separate structure levels
                    key = (point['price'], point['timestamp'], point.get('timeframe', ''))
                    if key not in seen:
                        seen.add(key)
                        unique.append(point)
                return unique
            
            bos_lines = deduplicate(bos_lines)
            choch_lines = deduplicate(choch_lines)
            hh_points = deduplicate(hh_points)
            ll_points = deduplicate(ll_points)
            
            logger.info(f"After deduplication: BoS={len(bos_lines)}, CHoCH={len(choch_lines)}, HH={len(hh_points)}, LL={len(ll_points)}")
            
            result = {
                'bos_lines': bos_lines,
                'choch_lines': choch_lines,
                'hh_points': hh_points,
                'll_points': ll_points,
                'total_points': len(bos_lines) + len(choch_lines) + len(hh_points) + len(ll_points),
                'time_range_hours': hours_back,
                'last_updated': datetime.now().isoformat(),
            }
            
            logger.info(
                f"[MarketStructureLinesReader] Loaded {result['total_points']} points: "
                f"BoS={len(bos_lines)}, CHoCH={len(choch_lines)}, "
                f"HH={len(hh_points)}, LL={len(ll_points)}"
            )
            
            # Log sample data for debugging
            if bos_lines:
                logger.info(f"[BoS Sample] First: {bos_lines[0]}")
            if choch_lines:
                logger.info(f"[CHoCH Sample] First: {choch_lines[0]}")
            if hh_points:
                logger.info(f"[HH Sample] First: {hh_points[0]}, Last: {hh_points[-1]}")
            if ll_points:
                logger.info(f"[LL Sample] First: {ll_points[0]}, Last: {ll_points[-1]}")
            
            return result
        
        except Exception as e:
            logger.error(f"[MarketStructureLinesReader] Error reading structure lines: {e}", exc_info=True)
            return self._get_empty_structure()
    
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
            data = self.get_market_structure_lines(hours_back=168)  # 1 week
            bos_lines = data.get('bos_lines', [])
            
            if not bos_lines:
                return None
            
            return bos_lines[-1]
        except:
            return None
    
    def get_latest_choch(self) -> Optional[Dict]:
        """Get the most recent CHoCH point"""
        try:
            data = self.get_market_structure_lines(hours_back=168)  # 1 week
            choch_lines = data.get('choch_lines', [])
            
            if not choch_lines:
                return None
            
            return choch_lines[-1]
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
