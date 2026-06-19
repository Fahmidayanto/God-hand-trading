"""Market structure event collector."""

import csv
import glob
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from app.models.activity_log import ActivityLog, EventType, SeverityLevel

logger = logging.getLogger(__name__)


class StructureCollector:
    """Collects market structure events from LLHHBOSData CSV files."""

    def __init__(self, backtest_dir: Optional[str] = None):
        """
        Initialize structure collector.
        
        Args:
            backtest_dir: Path to Backtest_result directory (default: relative to backend)
        """
        if backtest_dir is None:
            # Default path relative to backend directory
            # Backend is in: d:\Project\Project MT5\ValueCell_MT5\backend
            # Target is in: d:\Project\Project MT5\Backtest_result
            backend_dir = Path(__file__).parent.parent.parent.parent
            backtest_dir = backend_dir / ".." / ".." / "Backtest_result"
        
        self.backtest_dir = Path(backtest_dir).resolve()
        logger.info(f"[StructureCollector] Backtest dir: {self.backtest_dir}")
        
        # Cache for parsed events
        self._cached_events: List[ActivityLog] = []
        self._last_scan: Optional[datetime] = None
    
    def _parse_structure_csv(self, csv_path: Path) -> List[ActivityLog]:
        """
        Parse a single structure CSV file.
        
        Args:
            csv_path: Path to LLHHBOSData CSV file
            
        Returns:
            List of ActivityLog entries
        """
        logs: List[ActivityLog] = []
        
        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Skip header lines and find the actual data
            lines = content.strip().split("\n")
            header_idx = -1
            for i, line in enumerate(lines):
                if line.startswith("Type,Direction"):
                    header_idx = i
                    break

            if header_idx == -1:
                logger.warning(f"[StructureCollector] No data header found in {csv_path.name}")
                return logs

            # Parse CSV data (DictReader uses the header row for field names).
            reader = csv.DictReader(lines[header_idx:])
            
            for row in reader:
                try:
                    # Extract data
                    event_type_raw = row.get("Type", "").strip()
                    direction = row.get("Direction/Action", "").strip()
                    price = float(row.get("Price", 0))
                    time_str = row.get("Time", "").strip()
                    timeframe = row.get("Timeframe", "H1").strip()
                    status = row.get("Status", "").strip()
                    
                    # Skip empty rows
                    if not event_type_raw or not time_str:
                        continue
                    
                    # Parse timestamp
                    try:
                        # Format: "2019.11.29 15:00:00"
                        timestamp = datetime.strptime(time_str, "%Y.%m.%d %H:%M:%S")
                        timestamp = timestamp.replace(tzinfo=timezone.utc)
                    except ValueError:
                        logger.warning(f"[StructureCollector] Invalid timestamp: {time_str}")
                        continue
                    
                    # Map event type
                    if event_type_raw == "CHoCH":
                        event_type = EventType.STRUCTURE_CHOCH
                        icon = "GitBranch"
                        title = f"CHoCH [{timeframe}] - {direction}"
                        severity = SeverityLevel.WARNING
                    elif event_type_raw == "BoS":
                        event_type = EventType.STRUCTURE_BOS
                        icon = "TrendingUp"
                        title = f"BoS [{timeframe}] - {direction}"
                        severity = SeverityLevel.INFO
                    elif event_type_raw == "LL":
                        event_type = EventType.STRUCTURE_LL
                        icon = "ArrowDown"
                        title = f"Lower Low [{timeframe}] Detected"
                        severity = SeverityLevel.INFO
                    elif event_type_raw == "HH":
                        event_type = EventType.STRUCTURE_HH
                        icon = "ArrowUp"
                        title = f"Higher High [{timeframe}] Detected"
                        severity = SeverityLevel.INFO
                    else:
                        # Unknown type, skip
                        continue
                    
                    message = f"Market structure event: {event_type_raw} at {price:.2f} ({timeframe}) - {status}"
                    
                    # Create activity log
                    # Include timeframe in ID so M15 and H1 events at same
                    # price/time are treated as distinct structure events
                    log = ActivityLog(
                        id=f"STRUCT_{event_type_raw}_{timestamp.strftime('%Y%m%d%H%M%S')}_{price}_{timeframe}",
                        timestamp=timestamp,
                        event_id=f"{event_type_raw}_{time_str}",
                        event_type=event_type,
                        severity=severity,
                        icon=icon,
                        title=title,
                        message=message,
                        metadata={
                            "type": event_type_raw,
                            "direction": direction,
                            "price": price,
                            "timeframe": timeframe,
                            "status": status,
                            "source_file": csv_path.name,
                        }
                    )
                    
                    logs.append(log)
                
                except (ValueError, KeyError) as e:
                    logger.warning(f"[StructureCollector] Error parsing row: {e}")
                    continue
            
            return logs
        
        except Exception as e:
            logger.error(f"[StructureCollector] Error reading {csv_path.name}: {e}")
            return logs
    
    def collect(self, limit: int = 50, since: Optional[datetime] = None) -> List[ActivityLog]:
        """
        Collect structure events from CSV files.
        
        Args:
            limit: Maximum number of events to return
            since: Only return events after this timestamp
            
        Returns:
            List of ActivityLog entries sorted by timestamp (newest first)
        """
        logs: List[ActivityLog] = []
        
        try:
            if not self.backtest_dir.exists():
                logger.warning(f"[StructureCollector] Directory not found: {self.backtest_dir}")
                return logs
            
            # Find all LLHHBOSData CSV files
            pattern = str(self.backtest_dir / "LLHHBOSData_XAUUSD_*.csv")
            csv_files = glob.glob(pattern)
            
            if not csv_files:
                logger.warning(f"[StructureCollector] No structure files found: {pattern}")
                return logs
            
            # Limit to recent files for performance (last 3 files)
            csv_files = sorted(csv_files, reverse=True)[:3]
            logger.info(f"[StructureCollector] Processing {len(csv_files)} files")
            
            # Parse each file
            all_logs: List[ActivityLog] = []
            for csv_path_str in csv_files:
                csv_path = Path(csv_path_str)
                file_logs = self._parse_structure_csv(csv_path)
                all_logs.extend(file_logs)
            
            # Sort by timestamp (newest first)
            all_logs.sort(key=lambda x: x.timestamp, reverse=True)
            
            # Filter by since parameter
            if since:
                all_logs = [log for log in all_logs if log.timestamp > since]
            
            # Apply limit
            logs = all_logs[:limit]
            
            logger.info(f"[StructureCollector] Collected {len(logs)} structure events")
            return logs
        
        except Exception as e:
            logger.error(f"[StructureCollector] Error collecting events: {e}", exc_info=True)
            return logs
