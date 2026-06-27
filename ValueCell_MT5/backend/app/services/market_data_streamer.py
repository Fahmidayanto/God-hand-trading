"""
MarketData Streamer Service
Reads MarketData CSV files and streams progress via NDJSON for full history loading
"""

import csv
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional

logger = logging.getLogger(__name__)


class MarketDataStreamer:

    def __init__(self):
        project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
        self.backtest_dir = project_root / "Backtest_result"
        logger.info(f"[MarketDataStreamer] Dir: {self.backtest_dir}")

    def count_rows(self, files: List[Path]) -> int:
        """Count total rows across all CSV files (readline only, no parse)."""
        total = 0
        for f in files:
            with open(f, "r", encoding="utf-8") as fh:
                for _ in fh:
                    total += 1
            total -= 1
        return total

    async def stream(self, symbol: str = "XAUUSD", timeframe: str = "M15",
                     from_date: str = "2020-01-01", mode: str = "full") -> AsyncGenerator[str, None]:
        """
        Stream NDJSON lines — progress events then complete event.
        Yields JSON strings, one per line.
        """
        matches = sorted(self.backtest_dir.glob(f"MarketData_{symbol}_{timeframe}_*.csv"))
        if not matches:
            yield json.dumps({"type": "error", "message": f"No MarketData CSV for {symbol} {timeframe}"})
            return

        from_dt = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)

        yield json.dumps({"type": "progress", "percent": 0, "step": "Counting rows...", "total_estimated": 0})
        total_estimated = self.count_rows(matches)
        yield json.dumps({
            "type": "progress", "percent": 0,
            "step": f"{total_estimated:,} rows total. Processing...",
            "total_estimated": total_estimated,
        })

        candles: List[Dict] = []
        row_count = 0
        file_count = len(matches)

        for file_idx, file_path in enumerate(matches, 1):
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

        yield json.dumps({"type": "progress", "percent": 100, "step": "Sorting & finalizing...", "total_estimated": total_estimated})

        candles.sort(key=lambda c: c["time"])
        seen: set = set()
        unique: List[Dict] = []
        for c in candles:
            if c["time"] not in seen:
                seen.add(c["time"])
                unique.append(c)
        candles = unique[:250000]

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
