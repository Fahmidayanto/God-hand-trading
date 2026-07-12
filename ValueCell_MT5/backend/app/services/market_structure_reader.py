"""
Market Structure Reader Service
Reads market structure state from LLHHBOSData CSV files in Backtest_result/.
Data is auto-updated by MT5 every M15 candle close.
"""

import csv
import io
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class MarketStructureReader:
    """Reads market structure state from LLHHBOSData CSV (auto-updated by MT5)."""

    # Broker timezone offset from UTC (default 3 = GMT+3, matching MT5_BROKER_TIMEZONE_OFFSET)
    BROKER_OFFSET_HOURS: int = 3

    def __init__(self, broker_offset_hours: int | None = None):
        backend_dir = Path(__file__).parent.parent.parent
        project_root = backend_dir.parent
        self.backtest_dir = project_root.parent / "Backtest_result"
        logger.debug(f"[MarketStructureReader] Backtest dir: {self.backtest_dir}")

        # Allow caller to override broker offset; fall back to config if available
        if broker_offset_hours is not None:
            self.BROKER_OFFSET_HOURS = broker_offset_hours
        else:
            try:
                from app.config import get_settings
                self.BROKER_OFFSET_HOURS = get_settings().MT5_BROKER_TIMEZONE_OFFSET
            except Exception:
                pass  # use class default

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_market_structure(self) -> Optional[Dict]:
        """
        Get current market structure state derived from LLHHBOSData CSV.

        Returns:
            Dictionary matching the frontend MarketStructure interface, or None.
        """
        try:
            csv_file = self._get_latest_csv()
            if not csv_file:
                return None

            events = self._parse_csv(csv_file)
            if not events:
                logger.warning("[MarketStructureReader] No events parsed")
                return self._get_fallback_structure()

            structure = self._build_structure_state(events)
            logger.debug(
                f"[MarketStructureReader] {structure['phase_name']} | "
                f"{structure['direction']} | BoS={structure['bos_price']:.2f}"
            )
            return structure

        except Exception as e:
            logger.error(f"[MarketStructureReader] Error: {e}", exc_info=True)
            return self._get_fallback_structure()

    def get_structure_summary(self) -> str:
        structure = self.get_market_structure()
        if not structure:
            return "Market structure data not available"
        phase = structure["phase_name"]
        direction = structure["direction"]
        entry = "VALID ✅" if structure["is_entry_valid"] else "NOT VALID ❌"
        return f"{phase} | {direction} | Entry: {entry}"

    def get_trading_signal(self) -> Optional[Dict]:
        """
        Derive a trading signal from LLHHBOSData CSV market structure.

        Logic:
        - BUY  when direction=BULLISH and BoS is fresh (phase 3 or 4)
        - SELL when direction=BEARISH and BoS is fresh (phase 3 or 4)
        - HOLD otherwise (NEUTRAL or no fresh BoS)

        SL = latest LL (for BUY) or latest HH (for SELL)
        TP = latest HH (for BUY) or latest LL (for SELL)
        Confidence = structure confluence / 3

        Returns:
            Dict compatible with frontend TradingSignal format, or None.
        """
        try:
            csv_file = self._get_latest_csv()
            if not csv_file:
                return None

            events = self._parse_csv(csv_file)
            if not events:
                return None

            # Build structure for direction / phase info
            structure = self._build_structure_state(events)
            direction = structure["direction"]
            phase = structure["phase"]

            # Collect latest HH / LL prices (any timeframe, prefer M15 for entry)
            latest_hh_price = 0.0
            latest_ll_price = 0.0
            for ev in reversed(events):
                if ev["type"] == "HH" and latest_hh_price == 0.0:
                    latest_hh_price = ev["price"]
                elif ev["type"] == "LL" and latest_ll_price == 0.0:
                    latest_ll_price = ev["price"]
                if latest_hh_price and latest_ll_price:
                    break

            # Determine signal
            if direction == "BULLISH" and phase in (3, 4):
                signal = "BUY"
                entry_price = latest_ll_price  # entry near recent LL
                stop_loss = latest_ll_price - abs(latest_hh_price - latest_ll_price) * 0.5
                take_profit = latest_hh_price
            elif direction == "BEARISH" and phase in (3, 4):
                signal = "SELL"
                entry_price = latest_hh_price  # entry near recent HH
                stop_loss = latest_hh_price + abs(latest_hh_price - latest_ll_price) * 0.5
                take_profit = latest_ll_price
            else:
                signal = "HOLD"
                entry_price = 0.0
                stop_loss = 0.0
                take_profit = 0.0

            # Confidence from confluence (max 3: bos + choch + h1_trend)
            confluence = structure.get("structure_confluence", 0)
            confidence = min(confluence / 3.0, 1.0)

            result = {
                "signal": signal,
                "confidence": round(confidence, 2),
                "entry_price": round(entry_price, 2),
                "stop_loss": round(stop_loss, 2),
                "take_profit": round(take_profit, 2),
                "timestamp": structure.get("last_updated", datetime.now(timezone.utc).isoformat()),
            }
            logger.debug(
                f"[MarketStructureReader] Signal: {signal} conf={confidence:.0%} "
                f"entry={entry_price:.2f} sl={stop_loss:.2f} tp={take_profit:.2f}"
            )
            return result

        except Exception as e:
            logger.error(f"[MarketStructureReader] Signal error: {e}", exc_info=True)
            return None

    # ------------------------------------------------------------------
    # CSV helpers
    # ------------------------------------------------------------------

    def _get_latest_csv(self) -> Optional[Path]:
        """Find the latest LLHHBOSData CSV file by date in filename."""
        try:
            if not self.backtest_dir.exists():
                logger.warning(f"[MarketStructureReader] Dir not found: {self.backtest_dir}")
                return None
            csv_files = list(self.backtest_dir.glob("LLHHBOSData_XAUUSD_*.csv"))
            if not csv_files:
                logger.warning("[MarketStructureReader] No LLHHBOSData CSV files found")
                return None
            import re
            def extract_date(path: Path) -> str:
                match = re.search(r'(\d{4}-\d{2}-\d{2})', path.stem)
                return match.group(1) if match else '0000-00-00'
            latest = max(csv_files, key=extract_date)
            logger.debug(f"[MarketStructureReader] Using file: {latest.name} (date: {extract_date(latest)})")
            return latest
        except Exception as e:
            logger.error(f"[MarketStructureReader] Error finding CSV: {e}")
            return None

    def _parse_csv(self, csv_path: Path) -> List[Dict]:
        """
        Parse LLHHBOSData CSV into a list of event dicts.
        Only keeps Accepted / Confirmed events (skips Updated to avoid duplicates).
        """
        events: List[Dict] = []
        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Line 0 = title, Line 1 = column header, Line 2+ = data
            if len(lines) < 3:
                return events

            header_idx = -1
            for i, line in enumerate(lines):
                if line.startswith("Type,Direction"):
                    header_idx = i
                    break
            if header_idx == -1:
                return events

            reader = csv.DictReader(lines[header_idx:])
            seen: set = set()
            # Track the earliest HH/LL event per (price, timeframe) so we can keep only
            # the OLDEST (first) touch of each level (avoids duplicate overlapping lines).
            hhll_earliest: Dict[tuple, int] = {}  # key -> index in events list

            for row in reader:
                event_type = row.get("Type", "").strip()
                direction = row.get("Direction/Action", "").strip()
                price_str = row.get("Price", "0")
                time_str = row.get("Time", "").strip()
                timeframe = row.get("Timeframe", "M15").strip()
                status = row.get("Status", "").strip()
                prev_price_str = row.get("PreviousPrice", "").strip()

                if not event_type or not time_str:
                    continue

                # Skip "Updated" rows — keep only Accepted / Confirmed
                if status not in ("Accepted", "Confirmed"):
                    continue

                # Parse time: CSV stores broker/server time (TimeCurrent()).
                # Convert to true UTC by subtracting the broker offset.
                try:
                    from datetime import timedelta
                    event_time_naive = datetime.strptime(time_str, "%Y.%m.%d %H:%M:%S")
                    event_time = (event_time_naive - timedelta(hours=self.BROKER_OFFSET_HOURS)).replace(
                        tzinfo=timezone.utc
                    )
                except ValueError:
                    continue

                # Parse price
                try:
                    price = float(price_str)
                except (ValueError, TypeError):
                    continue

                # Dedup logic:
                # - BoS/CHoCH: dedup by (type, price, timestamp, timeframe) — each break is unique
                # - HH/LL: dedup by (price, timeframe) ONLY — same level touched multiple times
                #   should only draw ONE line. Rows are later sorted oldest → newest, so for
                #   HH/LL we OVERWRITE earlier rows in `hhll_latest` to keep the NEWEST touch.
                is_hh_ll = event_type in ("HH", "LL")
                if is_hh_ll:
                    # Handled by hhll_latest dict after the loop
                    pass
                else:
                    dedup_key = (event_type, price, int(event_time.timestamp()), timeframe)
                    if dedup_key in seen:
                        continue
                    seen.add(dedup_key)

                # Parse previous price (useful for HH/LL chain)
                prev_price = 0.0
                if prev_price_str and prev_price_str != "":
                    try:
                        prev_price = float(prev_price_str)
                    except (ValueError, TypeError):
                        pass

                # Normalise direction
                dir_upper = direction.upper()
                if "BULL" in dir_upper or dir_upper == "UPDATE":
                    norm_dir = "BULLISH" if "BULL" in dir_upper else "NEUTRAL"
                elif "BEAR" in dir_upper:
                    norm_dir = "BEARISH"
                else:
                    norm_dir = "NEUTRAL"

                events.append(
                    {
                        "type": event_type,
                        "direction": norm_dir,
                        "price": price,
                        "time": event_time,
                        "timeframe": timeframe,
                        "status": status,
                        "prev_price": prev_price,
                    }
                )
                # For HH/LL, record earliest index per (price, timeframe) — oldest wins
                if is_hh_ll:
                    hhll_key = (price, timeframe)
                    if hhll_key not in hhll_earliest:
                        hhll_earliest[hhll_key] = len(events) - 1

            # For HH/LL, keep only the earliest occurrence per (price, timeframe).
            # All non-HH/LL events are kept as-is.
            if hhll_earliest:
                keep_indices = set(hhll_earliest.values())
                events = [
                    e for i, e in enumerate(events)
                    if e["type"] not in ("HH", "LL") or i in keep_indices
                ]

            # Sort oldest → newest
            events.sort(key=lambda e: e["time"])
            logger.debug(f"[MarketStructureReader] Parsed {len(events)} events from {csv_path.name}")
            return events

        except Exception as e:
            logger.error(f"[MarketStructureReader] Parse error: {e}", exc_info=True)
            return events

    # ------------------------------------------------------------------
    # State derivation
    # ------------------------------------------------------------------

    def _build_structure_state(self, events: List[Dict]) -> Dict:
        """Derive full market structure state from parsed events."""
        now = datetime.now(timezone.utc)

        # --- Collect latest events per type / timeframe ---
        last_bos: Optional[Dict] = None
        last_choch: Optional[Dict] = None
        hh_h1_list: List[Dict] = []
        ll_h1_list: List[Dict] = []
        hh_m15_list: List[Dict] = []
        ll_m15_list: List[Dict] = []
        bos_chain_count = 0

        for ev in events:
            t = ev["type"]
            tf = ev["timeframe"]

            if t == "BoS":
                last_bos = ev
                bos_chain_count += 1
            elif t == "CHoCH":
                last_choch = ev
                bos_chain_count = 0  # CHoCH resets the chain
            elif t == "HH":
                if tf == "H1":
                    hh_h1_list.append(ev)
                else:
                    hh_m15_list.append(ev)
            elif t == "LL":
                if tf == "H1":
                    ll_h1_list.append(ev)
                else:
                    ll_m15_list.append(ev)

        # --- BoS info ---
        bos_price = last_bos["price"] if last_bos else 0.0
        bos_time = last_bos["time"].isoformat() if last_bos else None
        bos_direction = last_bos["direction"] if last_bos else "NEUTRAL"
        bos_age_hours = (now - last_bos["time"]).total_seconds() / 3600 if last_bos else 9999.0
        bars_since_bos = max(0, int(bos_age_hours * 4)) if bos_age_hours < 9999 else 0

        # --- CHoCH info ---
        choch_price = last_choch["price"] if last_choch else 0.0
        choch_time = last_choch["time"].isoformat() if last_choch else None
        choch_direction = last_choch["direction"] if last_choch else "NEUTRAL"
        choch_age_hours = (now - last_choch["time"]).total_seconds() / 3600 if last_choch else 9999.0

        # --- Direction from H1 HH/LL sequence ---
        direction = self._derive_direction(hh_h1_list, ll_h1_list)

        # --- Phase ---
        bos_aligned = bos_direction == direction and direction != "NEUTRAL"
        choch_aligned = choch_direction == direction and direction != "NEUTRAL"
        phase, phase_name = self._determine_phase(
            bos_age_hours, choch_age_hours, bos_aligned, choch_aligned
        )

        # --- H1 trend approximation ---
        # h1_above_ema200: approximate by checking if H1 structure is rising
        # (latest H1 HH > previous H1 HH → price trending up)
        h1_above_ema200 = False
        if len(hh_h1_list) >= 2:
            h1_above_ema200 = hh_h1_list[-1]["price"] > hh_h1_list[-2]["price"]
        elif len(hh_h1_list) == 1 and len(ll_h1_list) >= 1:
            # Single HH — check if HH > LL (uptrend proxy)
            h1_above_ema200 = hh_h1_list[-1]["price"] > ll_h1_list[-1]["price"]

        # h1_trend_aligned: H1 direction matches overall direction
        h1_trend_aligned = False
        if hh_h1_list and ll_h1_list:
            h1_dir = self._derive_direction(hh_h1_list, ll_h1_list)
            h1_trend_aligned = h1_dir == direction and direction != "NEUTRAL"
        elif direction != "NEUTRAL":
            h1_trend_aligned = True  # fallback if limited data

        # --- Entry validity ---
        is_entry_valid = (
            phase == 3  # BOS_CONFIRMED
            and h1_trend_aligned
            and bos_age_hours <= 4.0
        )

        # --- Last updated = most recent event time ---
        last_event_time = events[-1]["time"].isoformat() if events else None

        return {
            "phase": phase,
            "phase_name": phase_name,
            "direction": direction,
            "choch_price": choch_price,
            "choch_time": choch_time,
            "choch_direction": choch_direction,
            "choch_age_hours": round(choch_age_hours, 1),
            "bos_target_price": 0.0,
            "bos_price": bos_price,
            "bos_time": bos_time,
            "bos_direction": bos_direction,
            "bos_age_hours": round(bos_age_hours, 1),
            "bars_since_bos": bars_since_bos,
            "h1_above_ema200": h1_above_ema200,
            "h1_trend_aligned": h1_trend_aligned,
            "is_entry_valid": is_entry_valid,
            "last_updated": last_event_time,
            "structure_confluence": int(bos_aligned) + int(choch_aligned) + int(h1_trend_aligned),
            "bos_chain_count": bos_chain_count,
            "signal_confidence": 0.0,
            "signal_tier": "UNKNOWN",
        }

    # ------------------------------------------------------------------
    # Direction derivation
    # ------------------------------------------------------------------

    def _derive_direction(
        self, hh_list: List[Dict], ll_list: List[Dict]
    ) -> str:
        """
        Derive trend direction from H1 HH/LL sequence.
        - Higher Highs + Higher Lows → BULLISH
        - Lower Highs  + Lower Lows  → BEARISH
        - Mixed                        → NEUTRAL
        """
        hh_rising = False
        ll_rising = False

        if len(hh_list) >= 2:
            hh_rising = hh_list[-1]["price"] > hh_list[-2]["price"]
        if len(ll_list) >= 2:
            ll_rising = ll_list[-1]["price"] > ll_list[-2]["price"]

        if hh_rising and ll_rising:
            return "BULLISH"
        if not hh_rising and not ll_rising and (len(hh_list) >= 2 or len(ll_list) >= 2):
            return "BEARISH"

        # Fallback: use the latest HH or LL direction field
        latest = None
        if hh_list and ll_list:
            latest = hh_list[-1] if hh_list[-1]["time"] >= ll_list[-1]["time"] else ll_list[-1]
        elif hh_list:
            latest = hh_list[-1]
        elif ll_list:
            latest = ll_list[-1]

        if latest:
            if latest["type"] == "HH":
                return "BULLISH"
            elif latest["type"] == "LL":
                return "BEARISH"

        return "NEUTRAL"

    # ------------------------------------------------------------------
    # Phase determination
    # ------------------------------------------------------------------

    def _determine_phase(
        self,
        bos_age_hours: float,
        choch_age_hours: float,
        bos_aligned: bool,
        choch_aligned: bool,
    ) -> tuple:
        """
        Determine market structure phase.

        0 = NEUTRAL
        1 = CHOCH_PENDING  (CHoCH happened, waiting for BoS)
        2 = BOS_PENDING    (expecting BoS soon)
        3 = BOS_CONFIRMED  (fresh BoS aligned with trend)
        4 = IN_TREND       (BoS confirmed, trend continuing)
        """
        # Fresh BoS aligned with direction
        if bos_age_hours <= 2.0 and bos_aligned:
            return (3, "BOS_CONFIRMED")

        # BoS getting older but still relevant
        if 2.0 < bos_age_hours <= 8.0 and bos_aligned:
            return (4, "IN_TREND")

        # CHoCH recent, no fresh BoS
        if choch_age_hours <= 8.0 and choch_aligned and bos_age_hours > 8.0:
            return (1, "CHOCH_PENDING")

        # Both old — waiting for new structure
        if choch_age_hours <= 16.0 and bos_age_hours > 8.0:
            return (2, "BOS_PENDING")

        return (0, "NEUTRAL")

    # ------------------------------------------------------------------
    # Fallback
    # ------------------------------------------------------------------

    def _get_fallback_structure(self) -> Dict:
        """Return neutral structure when no data available."""
        return {
            "phase": 0,
            "phase_name": "NEUTRAL",
            "direction": "NEUTRAL",
            "choch_price": 0.0,
            "choch_time": None,
            "choch_direction": "NEUTRAL",
            "choch_age_hours": 0.0,
            "bos_target_price": 0.0,
            "bos_price": 0.0,
            "bos_time": None,
            "bos_direction": "NEUTRAL",
            "bos_age_hours": 0.0,
            "bars_since_bos": 0,
            "h1_above_ema200": False,
            "h1_trend_aligned": False,
            "is_entry_valid": False,
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "structure_confluence": 0,
            "bos_chain_count": 0,
            "signal_confidence": 0.0,
            "signal_tier": "UNKNOWN",
        }
