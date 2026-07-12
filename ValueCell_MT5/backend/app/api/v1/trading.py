"""Trading API endpoints."""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, StreamingResponse

from app.core.mt5_manager import MT5Manager
from app.dependencies import get_mt5_manager
from app.models.trading import (
    CandleData,
    MarketSignal,
    OrderRequest,
    OrderResponse,
    Position,
    Trade,
)
from app.utils.validators import validate_symbol, validate_timeframe
from app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()

# ponytail: cache candle+structure DB queries for simulate-event
# Key: (candle_table, date_from, date_to) — events within 1 replay session share same 30-day window
_sim_candle_cache: dict = {}
_SIM_CACHE_MAX = 50  # FIFO eviction


def calculate_ema200(candles: List[dict]) -> List[Optional[float]]:
    """Calculate EMA 200 for a list of candles.
    
    Args:
        candles: List of candle dicts with 'close' price
        
    Returns:
        List of EMA 200 values (None for first 199 candles)
    """
    if len(candles) < 200:
        return [None] * len(candles)
    
    period = 200
    multiplier = 2 / (period + 1)
    ema_values = [None] * len(candles)
    
    # Calculate initial SMA for the first 200 candles
    closes = [c['close'] for c in candles]
    sma = sum(closes[:period]) / period
    ema_values[period - 1] = sma
    
    # Calculate EMA for subsequent candles
    for i in range(period, len(candles)):
        ema_values[i] = (closes[i] * multiplier) + (ema_values[i - 1] * (1 - multiplier))
    
    return ema_values


# ---------------------------------------------------------------------------
# Session schedule helpers (mirror of the MT5 EA logic in Dev_Bot_v11.cs)
#
# Sessions are defined on the MT5 *server* wall-clock (GMT+2 in winter,
# GMT+3 in summer / EU DST). The EA normalises the hour by -1 during DST so the
# windows below are always expressed in the winter (GMT+2) effective hour.
# These helpers let us synthesise the *currently running* session that is not
# yet present in the exported SessionZone CSV (CSV only contains CLOSED sessions).
# ---------------------------------------------------------------------------

# Assumed MT5 server base offset from UTC (winter). DST adds +1.
SERVER_BASE_UTC_OFFSET_HOURS = 2


def _last_sunday_of_month(year: int, month: int) -> int:
    """Return the day-of-month of the last Sunday for the given year/month."""
    from calendar import monthrange

    days_in_month = monthrange(year, month)[1]
    for day in range(days_in_month, 0, -1):
        # weekday(): Monday=0 .. Sunday=6
        from datetime import date

        if date(year, month, day).weekday() == 6:
            return day
    return days_in_month


def _is_server_in_dst(server_dt) -> bool:
    """EU DST window: last Sun of March 03:00 -> last Sun of Oct 04:00 (server time)."""
    month = server_dt.month
    if month < 3 or month > 10:
        return False
    if 3 < month < 10:
        return True

    last_sunday = _last_sunday_of_month(server_dt.year, month)
    if month == 3:
        if server_dt.day < last_sunday:
            return False
        if server_dt.day > last_sunday:
            return True
        return server_dt.hour >= 3
    else:  # October
        if server_dt.day < last_sunday:
            return True
        if server_dt.day > last_sunday:
            return False
        return server_dt.hour < 4


def _effective_hour(server_dt) -> int:
    """Hour normalised so the session windows stay valid in both winter and summer."""
    hour = server_dt.hour
    if _is_server_in_dst(server_dt):
        hour = (hour - 1 + 24) % 24
    return hour


def _get_session(server_dt) -> str:
    """Return the active session name for a given server wall-clock datetime."""
    # weekday(): Monday=0 .. Sunday=6  -> Saturday=5, Sunday=6 are weekend
    if server_dt.weekday() >= 5:
        return "Weekend"

    hour = _effective_hour(server_dt)
    if hour >= 23 or hour < 1:
        return "Sydney"
    if 1 <= hour < 8:
        return "Sydney_Tokyo_Overlap"
    if 8 <= hour < 9:
        return "Asia"
    if 9 <= hour < 10:
        return "Tokyo_London_Overlap"
    if 10 <= hour < 14:
        return "London"
    if 14 <= hour < 18:
        return "London_NewYork_Overlap"
    if 18 <= hour < 23:
        return "NewYork"
    return "NoSession"


def _server_now():
    """Current time expressed in MT5 server wall-clock (naive datetime).

    Built from UTC so it stays consistent with how the chart positions candles
    (MT5 bar time = server wall-clock interpreted as UTC).
    """
    from datetime import datetime, timedelta

    base = datetime.utcnow() + timedelta(hours=SERVER_BASE_UTC_OFFSET_HOURS)
    if _is_server_in_dst(base):
        base = base + timedelta(hours=1)
    return base


def _to_chart_epoch(server_dt) -> int:
    """Convert a server wall-clock datetime to the epoch the chart expects.

    MT5 returns bar time as server wall-clock interpreted as UTC, and the
    lightweight-charts instance renders in UTC. So we treat the server
    wall-clock as UTC here to keep the shadow bands aligned with the candles.
    """
    import calendar

    return int(calendar.timegm(server_dt.timetuple()))


def _generate_session_zones(start_dt, end_dt):
    """Generate a continuous sequence of session zones over [start_dt, end_dt].

    Sessions are derived purely from the deterministic schedule (mirrors the EA),
    so coverage is complete and not limited by the sparse exported CSV. Session
    boundaries always fall on a server clock hour, so we evaluate at each hour
    mark for exact edges. Weekend / NoSession gaps are skipped. The final
    still-running segment is marked OPEN.
    """
    from datetime import timedelta

    zones = []

    def _flush(session_name, start, end, is_open):
        if session_name in ("Weekend", "NoSession"):
            return
        if end <= start:
            return
        zones.append({
            "start_time": _to_chart_epoch(start),
            "end_time": _to_chart_epoch(end),
            "session": session_name,
            "status": "OPEN" if is_open else "CLOSED",
            "open_price": 0.0,
            "high_price": 0.0,
            "low_price": 0.0,
            "close_price": 0.0,
            "range_points": 0.0,
            "duration_bars": 0,
            "is_dst": _is_server_in_dst(start),
        })

    seg_session = _get_session(start_dt)
    seg_start = start_dt

    # Walk the exact top-of-hour boundaries (sessions only switch on the hour).
    cursor = start_dt.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    while cursor < end_dt:
        session_here = _get_session(cursor)
        if session_here != seg_session:
            _flush(seg_session, seg_start, cursor, is_open=False)
            seg_session = session_here
            seg_start = cursor
        cursor += timedelta(hours=1)

    # Final segment runs up to end_dt and is the live one.
    _flush(seg_session, seg_start, end_dt, is_open=True)
    return zones


@router.get("/chart/data")
async def get_chart_data(
    symbol: str = Query("XAUUSD", description="Trading symbol"),
    timeframe: str = Query("M15", description="Timeframe"),
    count: int = Query(100, ge=1, le=6000, description="Number of candles"),
    mt5: MT5Manager = Depends(get_mt5_manager),
):
    """
    Get chart candlestick data in lightweight-charts format.
    
    Args:
        symbol: Trading symbol (e.g., XAUUSD, EURUSD)
        timeframe: Timeframe (M1, M5, M15, M30, H1, H4, D1)
        count: Number of candles to fetch
        
    Returns:
        Chart data with candles array
    """
    try:
        # Validate inputs
        if not validate_symbol(symbol):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid symbol format",
            )

        if not validate_timeframe(timeframe):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid timeframe. Use: M1, M5, M15, M30, H1, H4, D1",
            )

        # Fetch candles
        candles = mt5.get_candles(symbol, timeframe, count)

        if not candles:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No data available for {symbol} {timeframe}",
            )

        # Calculate EMA 200
        ema200_values = calculate_ema200(candles)

        # Format for lightweight-charts with EMA 200
        formatted_candles = []
        for i, candle in enumerate(candles):
            formatted_candle = {
                "time": int(candle["time"]),
                "open": float(candle["open"]),
                "high": float(candle["high"]),
                "low": float(candle["low"]),
                "close": float(candle["close"]),
            }
            if ema200_values[i] is not None:
                formatted_candle["ema200"] = round(ema200_values[i], 2)
            formatted_candles.append(formatted_candle)

        settings = get_settings()
        
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "candles": formatted_candles,
            "ema_periods": {"ema200": 200},
            "timezone": {
                "broker_offset_hours": settings.MT5_BROKER_TIMEZONE_OFFSET,
                "display_mode": settings.CHART_TIMEZONE_DISPLAY,
                "candle_times_are_utc": True
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chart data fetch error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/chart/backtest-data")
async def get_backtest_chart_data(
    symbol: str = Query("XAUUSD"),
    timeframe: str = Query("M15"),
    from_date: str = Query(None, description="Start date YYYY-MM-DD"),
    mode: str = Query("recent", description="Loading mode: 'recent' (6 months) or 'full' (from 2020)"),
    center_date: str = Query(None, description="Center date for jump navigation YYYY-MM-DD (loads ±3 months window)"),
):
    """
    Chart candles from Backtest_result CSV files instead of live MT5.

    Reads MarketData_{symbol}_{timeframe}_*.csv, filters by from_date,
    and returns the same shape as /chart/data so the frontend needs zero
    changes beyond switching the fetch URL.

    Performance optimization:
    - 'recent' mode: Load last 6 months (~20k candles) - FAST (1-2s)
    - 'full' mode: Load from 2020 (~150k candles) - SLOW (8-10s)
    - 'center_date': Load ±3 months window centered on specific date - FAST (1-2s)

    Ponytail: EMA200 is already in the CSV column — no recalculation.
    """
    import csv
    import re
    from pathlib import Path
    from datetime import datetime, timezone, timedelta

    try:
        project_root = Path(__file__).resolve().parent.parent.parent.parent.parent.parent
        backtest_dir = project_root / "Backtest_result"

        matches = sorted(backtest_dir.glob(f"MarketData_{symbol}_{timeframe}_*.csv"))
        if not matches:
            raise HTTPException(status_code=404, detail=f"No MarketData CSV for {symbol} {timeframe}")

        # Determine from_date, to_date and limit based on mode or center_date
        if center_date:
            # Jump navigation: Load ±3 months window centered on selected date
            center_dt = datetime.strptime(center_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            from_dt = center_dt - timedelta(days=90)  # 3 months before
            to_dt = center_dt + timedelta(days=90)    # 3 months after
            limit = 20000  # ~6 months of M15 data
            mode = "window"
            from_date = from_dt.strftime("%Y-%m-%d")
            logger.info(f"[WINDOW MODE] Center: {center_date}, Window: {from_dt} -> {to_dt}, limit={limit}")
        elif mode == "full":
            # Full history mode: Load from 2020
            if not from_date:
                from_date = "2020-01-01"
            from_dt = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            to_dt = None  # No upper limit
            limit = 250000  # ~7 years of M15 data (was 200K, bumped to cover up to Jun 2026)
            logger.info(f"[FULL MODE] Loading from {from_date}, limit={limit}")
        else:
            # Recent mode: Load last 6 months (default, fast)
            if not from_date:
                six_months_ago = datetime.now(timezone.utc) - timedelta(days=180)
                from_date = six_months_ago.strftime("%Y-%m-%d")
            from_dt = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            to_dt = None  # No upper limit
            limit = 30000  # ~6 months of M15 data
            logger.info(f"[RECENT MODE] Loading from {from_date}, limit={limit}")

        from_year = from_dt.year

        formatted_candles = []
        for path in matches:
            # Skip files whose year is before the requested year
            file_year = re.search(r"_(\d{4})-\d{2}-\d{2}\.csv$", path.name)
            if file_year and int(file_year.group(1)) < from_year:
                continue
            
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        dt = datetime.strptime(row["Time"].strip(), "%Y.%m.%d %H:%M:%S").replace(tzinfo=timezone.utc)
                        
                        # Filter by date range
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

        # Sort + dedup by time (CSV files overlap in time range)
        formatted_candles.sort(key=lambda c: c["time"])
        seen = set()
        formatted_candles = [c for c in formatted_candles if not (c["time"] in seen or seen.add(c["time"]))]
        
        # Apply limit after dedup
        formatted_candles = formatted_candles[:limit]

        if not formatted_candles:
            raise HTTPException(status_code=404, detail=f"No candles from {from_date}")

        logger.info(f"Returning {len(formatted_candles)} candles (mode={mode}, from={from_date})")

        return {
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

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Backtest chart data error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chart/backtest-data-stream")
async def get_backtest_chart_data_stream(
    symbol: str = Query("XAUUSD"),
    timeframe: str = Query("M15"),
    from_date: str = Query("2020-01-01", description="Start date YYYY-MM-DD"),
    mode: str = Query("full", description="Loading mode: 'full' (from 2020)"),
):
    """
    Stream candle data with real-time progress via NDJSON.
    Used by the frontend "Load Full History" button to show a progress bar.
    """
    from app.services.market_data_streamer import MarketDataStreamer

    streamer = MarketDataStreamer()

    async def generate():
        async for line in streamer.stream(symbol, timeframe, from_date, mode):
            yield line + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")


@router.get("/candles")
async def get_candles(
    symbol: str = Query("XAUUSD", description="Trading symbol"),
    timeframe: str = Query("M15", description="Timeframe"),
    count: int = Query(100, ge=1, le=6000, description="Number of candles"),
    mt5: MT5Manager = Depends(get_mt5_manager),
):
    """
    Get candlestick data from MT5.
    
    Args:
        symbol: Trading symbol (e.g., XAUUSD, EURUSD)
        timeframe: Timeframe (M1, M5, M15, M30, H1, H4, D1)
        count: Number of candles to fetch
        
    Returns:
        List of OHLC candle data
    """
    try:
        # Validate inputs
        if not validate_symbol(symbol):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid symbol format",
            )

        if not validate_timeframe(timeframe):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid timeframe. Use: M1, M5, M15, M30, H1, H4, D1",
            )

        # Fetch candles
        candles = mt5.get_candles(symbol, timeframe, count)

        if not candles:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No data available for {symbol} {timeframe}",
            )

        return [CandleData(**c) for c in candles]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Candles fetch error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/backtest-trades")
async def get_backtest_trades():
    """
    Get backtest trade entries with SL/TP for chart overlay.

    Reads all Backtest_Results_XAUUSD_*.csv files, returns executed
    trades with entry/SL/TP prices and times for the chart overlay.

    Returns:
        Dictionary containing:
        - trades: List of trade objects with type, prices, times
        - total_trades: Count
        - last_updated: ISO timestamp
    """
    try:
        from app.services.backtest_trades_reader import BacktestTradesReader

        reader = BacktestTradesReader()
        data = reader.get_all_trades()

        logger.info(f"[API] Returning {data['total_trades']} backtest trades")
        return JSONResponse(content=data)

    except Exception as e:
        logger.error(f"Backtest trades error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


# ===========================
# RONGSONKAN ENDPOINTS
# ===========================

@router.get("/chart/rongsokan-data")
async def get_rongsokan_chart_data(
    symbol: str = Query("XAUUSD"),
    timeframe: str = Query("M15"),
    from_date: str = Query("2020-01-01", description="Start date YYYY-MM-DD"),
    mode: str = Query("recent", description="Loading mode: 'recent', 'full', or 'window'"),
    center_date: str = Query(None, description="Center date for jump navigation YYYY-MM-DD"),
):
    """
    Rongsokan chart candles from Backtest_rongsokan CSV files.
    
    Reads MarketData_{symbol}_{timeframe}_*.csv from D:\\Project\\Project MT5\\Other\\Backtest_rongsokan
    
    Modes:
    - 'recent': Last 6 months (fast)
    - 'full': From 2020 (slow, streams via /chart/rongsokan-data-stream)
    - 'window': ±3 months around center_date (for jump navigation)
    """
    try:
        from app.services.rongsokan_data_reader import rongsokan_reader

        data = rongsokan_reader.get_candles(
            symbol=symbol,
            timeframe=timeframe,
            from_date=from_date,
            mode=mode,
            center_date=center_date,
        )

        logger.info(f"[RONGSOKAN API] Returning {data['candles_count']} candles (mode={mode})")
        return data

    except Exception as e:
        logger.error(f"Rongsokan chart data error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/chart/rongsokan-data-stream")
async def get_rongsokan_chart_data_stream(
    symbol: str = Query("XAUUSD"),
    timeframe: str = Query("M15"),
    from_date: str = Query("2020-01-01", description="Start date YYYY-MM-DD"),
    mode: str = Query("full", description="Loading mode: 'full'"),
):
    """
    Stream Rongsokan candle data with real-time progress via NDJSON.
    Used by the frontend "Load Full History" button to show a progress bar.
    """
    from app.services.rongsokan_data_reader import rongsokan_reader

    async def generate():
        async for line in rongsokan_reader.stream_candles(symbol, timeframe, from_date, mode):
            yield line + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")


@router.get("/rongsokan-trades")
async def get_rongsokan_trades():
    """
    Get Rongsokan backtest trade entries with SL/TP for chart overlay.
    
    Reads all Backtest_Results_XAUUSD_*.csv files from D:\\Project\\Project MT5\\Other\\Backtest_rongsokan
    
    Returns:
        Dictionary containing:
        - trades: List of trade objects with type, prices, times
        - total_trades: Count
        - last_updated: ISO timestamp
    """
    try:
        from app.services.rongsokan_data_reader import rongsokan_reader

        data = rongsokan_reader.get_trades()

        logger.info(f"[RONGSOKAN API] Returning {data['total_trades']} backtest trades")
        return data

    except Exception as e:
        logger.error(f"Rongsokan trades error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/rongsokan-structure-lines")
async def get_rongsokan_structure_lines(
    from_date: str = Query("2020-01-01", description="Start date YYYY-MM-DD"),
    to_date: str = Query(None, description="End date YYYY-MM-DD"),
):
    """
    Get Rongsokan market structure lines from LLHHBOSData CSV.
    
    Reads LLHHBOSData_*.csv files from D:\\Project\\Project MT5\\Other\\Backtest_rongsokan
    
    Returns:
        Dictionary containing bos_lines, choch_lines, hh_points, ll_points
    """
    try:
        from app.services.rongsokan_data_reader import rongsokan_reader

        data = rongsokan_reader.get_structure_lines(from_date=from_date, to_date=to_date)

        logger.info(f"[RONGSOKAN API] Structure lines: {data['total_points']} points")
        return data

    except Exception as e:
        logger.error(f"Rongsokan structure lines error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/positions", response_model=List[Position])
async def get_open_positions(
    mt5: MT5Manager = Depends(get_mt5_manager),
):
    """
    Get all open positions.
    
    Returns:
        List of open positions with profit/loss
    """
    try:
        positions = mt5.get_positions()
        return [Position(**pos) for pos in positions]

    except Exception as e:
        logger.error(f"Positions fetch error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/signal")
async def get_current_signal_wrapper(
    symbol: str = Query("XAUUSD"),
    timeframe: str = Query("M15"),
    mt5: MT5Manager = Depends(get_mt5_manager),
):
    """
    Get current trading signal derived from LLHHBOSData CSV (auto-updated by MT5).

    Derives BUY/SELL/HOLD from market structure:
    - BUY  when BULLISH + fresh BoS (phase 3/4)
    - SELL when BEARISH + fresh BoS (phase 3/4)
    - HOLD otherwise

    Frontend expects: { signal, confidence, entry_price, stop_loss, take_profit }
    """
    try:
        from datetime import datetime
        from app.services.market_structure_reader import MarketStructureReader

        # Derive signal from LLHHBOSData CSV
        reader = MarketStructureReader()
        derived_signal = reader.get_trading_signal()

        if derived_signal:
            logger.debug(
                f"[API] Signal from structure: {derived_signal['signal']} "
                f"conf={derived_signal['confidence']}"
            )
            return derived_signal

        # Fallback: get current price from MT5
        logger.warning("[API] No structure signal, using MT5 fallback")
        symbol_info = mt5.get_symbol_info(symbol)
        if not symbol_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Symbol {symbol} not found",
            )

        current_price = symbol_info["bid"]
        return {
            "signal": "HOLD",
            "confidence": 0.0,
            "entry_price": current_price,
            "stop_loss": 0.0,
            "take_profit": 0.0,
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Signal fetch error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )





@router.post("/order", response_model=OrderResponse)
async def place_order(
    order: OrderRequest,
    mt5: MT5Manager = Depends(get_mt5_manager),
):
    """
    Place a trading order.
    
    Note: Only paper trading is enabled by default.
    Set TRADING_MODE=live in .env to enable real trading.
    
    Args:
        order: Order details (symbol, type, volume, sl, tp)
        
    Returns:
        Order placement result
    """
    try:
        result = mt5.place_order(
            symbol=order.symbol,
            order_type=order.type,
            volume=order.volume,
            sl=order.sl,
            tp=order.tp,
            comment=order.comment or "",
        )

        return OrderResponse(**result)

    except Exception as e:
        logger.error(f"Order placement error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/trades/history")
async def get_trades_history(
    days: int = Query(30, ge=1, le=365, description="Number of days"),
    mt5: MT5Manager = Depends(get_mt5_manager),
):
    """
    Get trade history with statistics.
    
    Args:
        days: Number of days to fetch (1-365)
        
    Returns:
        Trades with summary statistics
    """
    try:
        deals = mt5.get_history_deals(days)

        # Group deals into trades
        trades = []
        total_profit = 0
        win_count = 0
        loss_count = 0
        
        for deal in deals[:50]:  # Limit to 50 recent
            # Skip non-trading deals (balance operations, deposits, etc.)
            symbol = deal.get("symbol", "")
            if not symbol or symbol == "":
                continue  # Skip deals without symbol (balance operations)
            
            profit = float(deal.get("profit", 0))
            total_profit += profit
            
            if profit > 0:
                win_count += 1
            elif profit < 0:
                loss_count += 1
            
            trade_data = {
                "trade_id": f"#TRD-{str(deal['ticket']).zfill(3)}",
                "ticket": deal["ticket"],
                "symbol": symbol,
                "type": "BUY" if deal.get("type", 0) == 0 else "SELL",
                "volume": float(deal.get("volume", 0)),
                "entry_price": float(deal.get("price", 0)),
                "exit_price": float(deal.get("price", 0)) if deal.get("entry") == 1 else None,
                "lot_size": float(deal.get("volume", 0)),
                "pnl": profit,
                "profit": profit,
                "status": "CLOSED" if deal.get("entry") == 1 else "OPEN",
                "open_time": deal.get("time", ""),
                "close_time": deal.get("time", "") if deal.get("entry") == 1 else None,
                "comment": deal.get("comment", ""),
            }
            trades.append(trade_data)

        # Calculate statistics
        total_trades = len(trades)
        win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
        
        # Count open positions
        positions = mt5.get_positions()
        open_positions = len(positions) if positions else 0

        return {
            "trades": trades,
            "total_trades": total_trades,
            "win_rate": round(win_rate, 1),
            "total_pnl": round(total_profit, 2),
            "open_positions": open_positions,
        }

    except Exception as e:
        logger.error(f"Trades history fetch error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/history", response_model=List[Trade])
async def get_trade_history(
    days: int = Query(30, ge=1, le=365, description="Number of days"),
    mt5: MT5Manager = Depends(get_mt5_manager),
):
    """
    Get trade history.
    
    Args:
        days: Number of days to fetch (1-365)
        
    Returns:
        List of historical trades
    """
    try:
        deals = mt5.get_history_deals(days)

        # Group deals into trades
        # TODO: Implement proper trade grouping logic
        # For now, return simplified structure

        trades = []
        for deal in deals[:20]:  # Limit to 20 recent
            if deal["entry"] == 0:  # Entry deal
                trades.append(
                    Trade(
                        trade_id=f"#TRD-{deal['ticket']}",
                        ticket=deal["ticket"],
                        symbol=deal["symbol"],
                        type="BUY" if deal["type"] == 0 else "SELL",
                        volume=deal["volume"],
                        entry_price=deal["price"],
                        exit_price=None,
                        profit=deal["profit"],
                        status="CLOSED",
                        open_time=deal["time"],
                        comment=deal.get("comment"),
                    )
                )

        return trades

    except Exception as e:
        logger.error(f"History fetch error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/session-zones")
async def get_session_zones(
    symbol: str = Query("XAUUSD", description="Trading symbol"),
    days: int = Query(7, ge=1, le=3000, description="Number of days to fetch (used if from_date not provided)"),
    from_date: str = Query(None, description="Start date YYYY-MM-DD (overrides days parameter)"),
):
    """
    Get trading session zones for the chart shadow bands.

    Sessions are generated deterministically from the MT5 session schedule
    (mirrors the EA), so the sequence is continuous from `from_date` (or `days` ago)
    up to the live, still-running session. Times are aligned to the candle epoch
    (server wall-clock interpreted as UTC).

    Args:
        symbol: Trading symbol (e.g., XAUUSD)
        days: Number of days to look back (1-3000, used if from_date not provided)
        from_date: Start date in YYYY-MM-DD format (e.g., "2020-01-01")

    Returns:
        List of session zones with start/end time, session type and status.
    """
    try:
        from datetime import timedelta, datetime

        server_now = _server_now()
        
        # Use from_date if provided, otherwise fallback to days parameter
        if from_date:
            try:
                # Parse as naive datetime (no timezone) to match _server_now() behavior
                start_dt = datetime.strptime(from_date, "%Y-%m-%d")
                logger.info(f"Using from_date: {from_date} -> {start_dt}")
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Invalid from_date format. Use YYYY-MM-DD (e.g., 2020-01-01)",
                )
        else:
            start_dt = server_now - timedelta(days=days)
            logger.info(f"Using days lookback: {days} -> {start_dt}")

        all_zones = _generate_session_zones(start_dt, server_now)

        # Sort by start time (oldest first) so historical data is prioritized
        all_zones.sort(key=lambda x: x['start_time'], reverse=False)

        logger.info(
            f"Generated {len(all_zones)} session zones for {symbol} "
            f"({start_dt} -> {server_now} server time)"
        )

        return {
            "zones": all_zones,
            "total_zones": len(all_zones),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Session zones fetch error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


_cached_replay_months = None


@router.get("/replay/months")
async def get_replay_months():
    """
    Get list of available years and months from the marketdata table in NeonDB.
    """
    global _cached_replay_months
    if _cached_replay_months is not None:
        return _cached_replay_months

    from app.core.database import get_db_conn, is_pool_ready

    if not is_pool_ready():
        raise HTTPException(status_code=503, detail="Database not ready")

    try:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT DISTINCT EXTRACT(YEAR FROM time)::int AS y,
                                    EXTRACT(MONTH FROM time)::int AS m
                    FROM marketdata_xauusd_m15
                    ORDER BY y, m
                    """
                )
                month_rows = cur.fetchall()

        result = [{"year": int(r[0]), "month": int(r[1])} for r in month_rows]
        _cached_replay_months = result
        return result

    except Exception as e:
        logger.error(f"Replay months error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


@router.get("/replay")
async def get_replay_data(
    year_from: int = Query(..., description="Start year"),
    month_from: int = Query(..., ge=1, le=12, description="Start month (1-12)"),
    year_to: int = Query(..., description="End year"),
    month_to: int = Query(..., ge=1, le=12, description="End month (1-12)"),
    timeframe: str = Query("M15", description="Timeframe (M15, H1, H4)"),
):
    """
    Fetch replay data for a custom date range from NeonDB.
    Returns M15 candles (with EMA200), LLHH/BoS structure events, and backtest trades.
    """
    from datetime import date, timezone
    from app.core.database import get_db_conn, is_pool_ready

    def _ts(dt) -> int:
        """Convert naive datetime (stored as UTC in DB) to UTC unix timestamp."""
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())

    if not is_pool_ready():
        raise HTTPException(status_code=503, detail="Database not ready")

    # Validate date range
    try:
        date_from = date(year_from, month_from, 1)
        # Last day of end month
        import calendar
        last_day = calendar.monthrange(year_to, month_to)[1]
        date_to = date(year_to, month_to, last_day)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date range: {e}")

    if date_from > date_to:
        raise HTTPException(status_code=400, detail="Start date must be before end date")

    table_map = {"M15": "marketdata_xauusd_m15", "H1": "marketdata_xauusd_h1", "H4": "marketdata_xauusd_h4"}
    candle_table = table_map.get(timeframe.upper(), "marketdata_xauusd_m15")

    try:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                # Fetch candles
                cur.execute(
                    f"""
                    SELECT time, open, high, low, close, volume, ema200
                    FROM {candle_table}
                    WHERE DATE(time) >= %s AND DATE(time) <= %s
                    ORDER BY time ASC
                    """,
                    (date_from, date_to),
                )
                candle_rows = cur.fetchall()

                # Fetch LLHH/BoS structure events
                cur.execute(
                    """
                    SELECT type, direction_action, price, time, timeframe, status, previous_price, previous_time
                    FROM llhhbosdata_xauusd
                    WHERE DATE(time) >= %s AND DATE(time) <= %s
                    AND timeframe = %s
                    ORDER BY time ASC
                    """,
                    (date_from, date_to, timeframe.upper()),
                )
                structure_rows = cur.fetchall()

                # Fetch backtest trades
                cur.execute(
                    """
                    SELECT ticket, type, entry_price, exit_price, sl, tp,
                           net_profit, session, entry_time, exit_time, lot_size
                    FROM backtest_results_xauusd
                    WHERE DATE(entry_time) >= %s AND DATE(entry_time) <= %s
                    ORDER BY entry_time ASC
                    """,
                    (date_from, date_to),
                )
                trade_rows = cur.fetchall()

                # Fetch available months for the dropdown
                cur.execute(
                    """
                    SELECT DISTINCT EXTRACT(YEAR FROM time)::int AS y,
                                    EXTRACT(MONTH FROM time)::int AS m
                    FROM marketdata_xauusd_m15
                    ORDER BY y, m
                    """
                )
                month_rows = cur.fetchall()

        candles = [
            {
                "time": _ts(r[0]),
                "open": float(r[1]),
                "high": float(r[2]),
                "low": float(r[3]),
                "close": float(r[4]),
                "volume": int(r[5]),
                "ema200": float(r[6]) if r[6] is not None else None,
            }
            for r in candle_rows
        ]

        structures = [
            {
                "type": r[0].strip() if r[0] else "",
                "direction": r[1].strip() if r[1] else "",
                "price": float(r[2]) if r[2] else 0.0,
                "time": _ts(r[3]),
                "timeframe": r[4],
                "status": r[5],
                "previous_price": float(r[6]) if r[6] else None,
                "previous_time": _ts(r[7]),
            }
            for r in structure_rows
        ]

        trades = [
            {
                "ticket": r[0],
                "type": r[1],
                "entry_price": float(r[2]) if r[2] else None,
                "exit_price": float(r[3]) if r[3] else None,
                "sl": float(r[4]) if r[4] else None,
                "tp": float(r[5]) if r[5] else None,
                "net_profit": float(r[6]) if r[6] else None,
                "session": r[7],
                "entry_time": _ts(r[8]),
                "exit_time": _ts(r[9]),
                "lot_size": float(r[10]) if r[10] else None,
            }
            for r in trade_rows
        ]

        available_months = [{"year": int(r[0]), "month": int(r[1])} for r in month_rows]

        logger.info(
            f"[Replay] Fetched {len(candles)} candles, {len(structures)} structures, "
            f"{len(trades)} trades for {date_from} → {date_to}"
        )

        return {
            "candles": candles,
            "structures": structures,
            "trades": trades,
            "available_months": available_months,
            "meta": {
                "timeframe": timeframe.upper(),
                "date_from": str(date_from),
                "date_to": str(date_to),
                "total_candles": len(candles),
                "total_structures": len(structures),
                "total_trades": len(trades),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Replay data fetch error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/simulate")
async def get_simulation_data(
    year_from: int = Query(..., description="Start year"),
    month_from: int = Query(..., ge=1, le=12, description="Start month (1-12)"),
    year_to: int = Query(..., description="End year"),
    month_to: int = Query(..., ge=1, le=12, description="End month (1-12)"),
    timeframe: str = Query("M15", description="Timeframe (M15, H1, H4)"),
):
    """Run a separate OrchestratorAgent instance over historical data.

    Returns orchestrator BUY/SELL signals + forward-walked outcome metrics,
    to validate whether the orchestrator actually works on past data.
    """
    import calendar
    from datetime import date, timezone
    from app.core.database import get_db_conn, is_pool_ready
    from app.services.orchestrator_simulator import run_simulation

    if not is_pool_ready():
        raise HTTPException(status_code=503, detail="Database not ready")

    try:
        date_from = date(year_from, month_from, 1)
        last_day = calendar.monthrange(year_to, month_to)[1]
        date_to = date(year_to, month_to, last_day)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date range: {e}")
    if date_from > date_to:
        raise HTTPException(status_code=400, detail="Start date must be before end date")

    table_map = {"M15": "marketdata_xauusd_m15", "H1": "marketdata_xauusd_h1", "H4": "marketdata_xauusd_h4"}
    candle_table = table_map.get(timeframe.upper(), "marketdata_xauusd_m15")

    def _ts(dt):
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())

    try:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT time, open, high, low, close, volume, ema200 "
                    f"FROM {candle_table} WHERE DATE(time) >= %s AND DATE(time) <= %s ORDER BY time ASC",
                    (date_from, date_to),
                )
                candle_rows = cur.fetchall()
                cur.execute(
                    "SELECT id, type, direction_action, price, time, timeframe, status, previous_price, previous_time "
                    "FROM llhhbosdata_xauusd WHERE DATE(time) >= %s AND DATE(time) <= %s AND timeframe = %s ORDER BY time ASC, id ASC",
                    (date_from, date_to, timeframe.upper()),
                )
                structure_rows = cur.fetchall()
                cur.execute(
                    "SELECT ticket, type, entry_price, exit_price, sl, tp, net_profit, session, entry_time, exit_time, lot_size "
                    "FROM backtest_results_xauusd WHERE DATE(entry_time) >= %s AND DATE(entry_time) <= %s ORDER BY entry_time ASC",
                    (date_from, date_to),
                )
                trade_rows = cur.fetchall()
                cur.execute(
                    "SELECT time, open, high, low, close, volume, ema200 "
                    "FROM marketdata_xauusd_h1 WHERE DATE(time) >= %s AND DATE(time) <= %s ORDER BY time ASC",
                    (date_from, date_to),
                )
                h1_rows = cur.fetchall()
                cur.execute(
                    "SELECT time, open, high, low, close, volume, ema200 "
                    "FROM marketdata_xauusd_h4 WHERE DATE(time) >= %s AND DATE(time) <= %s ORDER BY time ASC",
                    (date_from, date_to),
                )
                h4_rows = cur.fetchall()
    except Exception as e:
        logger.error(f"Simulation DB error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    candles = [
        {"time": _ts(r[0]), "open": float(r[1]), "high": float(r[2]), "low": float(r[3]),
         "close": float(r[4]), "volume": int(r[5]), "ema200": float(r[6]) if r[6] is not None else None}
        for r in candle_rows
    ]
    structure_events = [
        {"id": r[0], "type": (r[1] or "").strip(), "direction": (r[2] or "").strip(), "price": float(r[3]) if r[3] is not None else None,
         "time": _ts(r[4]), "timeframe": r[5], "status": r[6],
         "previous_price": float(r[7]) if r[7] is not None else None, "previous_time": _ts(r[8])}
        for r in structure_rows
    ]
    backtest_trades = [
        {"ticket": r[0], "type": r[1], "entry_price": float(r[2]) if r[2] is not None else None,
         "exit_price": float(r[3]) if r[3] is not None else None, "sl": float(r[4]) if r[4] is not None else None,
         "tp": float(r[5]) if r[5] is not None else None, "net_profit": float(r[6]) if r[6] is not None else None,
         "session": r[7], "entry_time": _ts(r[8]), "exit_time": _ts(r[9]),
         "lot_size": float(r[10]) if r[10] is not None else None}
        for r in trade_rows
    ]
    h1_candles = [
        {"time": _ts(r[0]), "open": float(r[1]), "high": float(r[2]), "low": float(r[3]),
         "close": float(r[4]), "volume": int(r[5]), "ema200": float(r[6]) if r[6] is not None else None}
        for r in h1_rows
    ]
    h4_candles = [
        {"time": _ts(r[0]), "open": float(r[1]), "high": float(r[2]), "low": float(r[3]),
         "close": float(r[4]), "volume": int(r[5]), "ema200": float(r[6]) if r[6] is not None else None}
        for r in h4_rows
    ]

    try:
        try:
            from app.services.orchestrator_simulator import reset_simulation_orchestrator
            reset_simulation_orchestrator()
        except Exception as re:
            logger.warning(f"Failed to reset orchestrator state at replay init: {re}")

        result = await run_in_threadpool(
            run_simulation, candles, structure_events, backtest_trades, "XAUUSD", timeframe, 300, h1_candles, h4_candles
        )
    except Exception as e:
        logger.error(f"Simulation run error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    return result


@router.get("/simulate-event")
async def get_single_event_simulation(
    time: int = Query(..., description="Timestamp of the structure event"),
    timeframe: str = Query("M15", description="Timeframe (M15, H1, H4)"),
    symbol: str = "XAUUSD",
    type: Optional[str] = Query(None, description="Type of the structure event (HH, LL, BOS, CHOCH)"),
):
    """Run the OrchestratorAgent for a single historical event timestamp."""
    logger.info(f"--- SIMULATE EVENT ENDPOINT HIT: time={time} type={type} ---")
    from datetime import date, datetime, timedelta, timezone
    from app.core.database import get_db_conn, is_pool_ready
    from app.services.orchestrator_simulator import (
        analyze_with_orchestrator_lock,
        get_orchestrator,
        reconstruct_market_data,
        _build_frame,
    )
    import pandas as pd

    if not is_pool_ready():
        raise HTTPException(status_code=503, detail="Database not ready")

    # Fetch candles and structures 30 days prior for warmup/indicators
    dt_event = datetime.fromtimestamp(time, tz=timezone.utc)
    date_from = (dt_event - timedelta(days=30)).date()
    date_to = dt_event.date()

    table_map = {"M15": "marketdata_xauusd_m15", "H1": "marketdata_xauusd_h1", "H4": "marketdata_xauusd_h4"}
    candle_table = table_map.get(timeframe.upper(), "marketdata_xauusd_m15")

    try:
        cache_key = (candle_table, date_from, date_to)
        if cache_key in _sim_candle_cache:
            candle_rows, structure_rows, h1_rows, h4_rows = _sim_candle_cache[cache_key]
        else:
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    # Fetch candles up to event day
                    cur.execute(
                        f"SELECT time, open, high, low, close, volume, ema200 "
                        f"FROM {candle_table} WHERE DATE(time) >= %s AND DATE(time) <= %s ORDER BY time ASC",
                        (date_from, date_to),
                    )
                    candle_rows = cur.fetchall()

                    # Fetch structures up to the event day
                    cur.execute(
                        "SELECT id, type, direction_action, price, time, timeframe, status, previous_price, previous_time "
                        "FROM llhhbosdata_xauusd WHERE DATE(time) >= %s AND DATE(time) <= %s AND timeframe = %s ORDER BY time ASC, id ASC",
                        (date_from, date_to, timeframe.upper()),
                    )
                    structure_rows = cur.fetchall()

                    # Fetch H1 candles
                    cur.execute(
                        "SELECT time, open, high, low, close, volume, ema200 "
                        "FROM marketdata_xauusd_h1 WHERE DATE(time) >= %s AND DATE(time) <= %s ORDER BY time ASC",
                        (date_from, date_to),
                    )
                    h1_rows = cur.fetchall()

                    # Fetch H4 candles
                    cur.execute(
                        "SELECT time, open, high, low, close, volume, ema200 "
                        "FROM marketdata_xauusd_h4 WHERE DATE(time) >= %s AND DATE(time) <= %s ORDER BY time ASC",
                        (date_from, date_to),
                    )
                    h4_rows = cur.fetchall()

            # Store in cache (FIFO eviction)
            if len(_sim_candle_cache) >= _SIM_CACHE_MAX:
                del _sim_candle_cache[next(iter(_sim_candle_cache))]
            _sim_candle_cache[cache_key] = (candle_rows, structure_rows, h1_rows, h4_rows)
    except Exception as e:
        logger.error(f"Event simulation DB error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    def _ts(dt):
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())

    candles = [
        {"time": _ts(r[0]), "open": float(r[1]), "high": float(r[2]), "low": float(r[3]),
         "close": float(r[4]), "volume": int(r[5]), "ema200": float(r[6]) if r[6] is not None else None}
        for r in candle_rows
    ]
    structure_events = [
        {"id": r[0], "type": (r[1] or "").strip(), "direction": (r[2] or "").strip(), "price": float(r[3]) if r[3] is not None else None,
         "time": _ts(r[4]), "timeframe": r[5], "status": r[6],
         "previous_price": float(r[7]) if r[7] is not None else None, "previous_time": _ts(r[8])}
        for r in structure_rows
    ]

    # Find the target structure event matching the target time
    target_evs = [e for e in structure_events if e["time"] == time]
    if not target_evs:
        # Fallback: create dummy event if not found exactly in db
        target_ev = {"type": "HH", "direction": "Bullish", "price": 0.0, "time": time}
    else:
        if type:
            matched_evs = [e for e in target_evs if e["type"].upper() == type.upper()]
            if matched_evs:
                target_ev = matched_evs[0]
            else:
                target_ev = target_evs[0]
        else:
            target_ev = target_evs[0]

    # Run the orchestrator on this event
    try:
        from loguru import logger as loguru_logger
        base_df = pd.DataFrame(candles)
        base_df["time"] = pd.to_datetime(base_df["time"], unit="s", utc=True)
        if "tick_volume" not in base_df.columns and "volume" in base_df.columns:
            base_df["tick_volume"] = base_df["volume"]
        if "ema200" not in base_df.columns or base_df["ema200"].isna().all():
            base_df["ema200"] = base_df["close"].ewm(span=200, adjust=False).mean()
        base_df["high_low"] = base_df["high"] - base_df["low"]
        base_df = base_df.sort_values("time").reset_index(drop=True)

        h1_candles = [
            {"time": _ts(r[0]), "open": float(r[1]), "high": float(r[2]), "low": float(r[3]),
             "close": float(r[4]), "volume": int(r[5]), "ema200": float(r[6]) if r[6] is not None else None}
            for r in h1_rows
        ]
        h4_candles = [
            {"time": _ts(r[0]), "open": float(r[1]), "high": float(r[2]), "low": float(r[3]),
             "close": float(r[4]), "volume": int(r[5]), "ema200": float(r[6]) if r[6] is not None else None}
            for r in h4_rows
        ]

        h1_df = pd.DataFrame(h1_candles)
        if not h1_df.empty:
            h1_df["time"] = pd.to_datetime(h1_df["time"], unit="s", utc=True)
            if "ema200" not in h1_df.columns or h1_df["ema200"].isna().all():
                h1_df["ema200"] = h1_df["close"].ewm(span=200, adjust=False).mean()
            h1_df = h1_df.sort_values("time").reset_index(drop=True)
        else:
            h1_df = None

        h4_df = pd.DataFrame(h4_candles)
        if not h4_df.empty:
            h4_df["time"] = pd.to_datetime(h4_df["time"], unit="s", utc=True)
            if "ema200" not in h4_df.columns or h4_df["ema200"].isna().all():
                h4_df["ema200"] = h4_df["close"].ewm(span=200, adjust=False).mean()
            h4_df = h4_df.sort_values("time").reset_index(drop=True)
        else:
            h4_df = None

        _ev_type = (target_ev.get("type") or "?").upper()
        _ev_dir = (target_ev.get("direction") or "?")[:4]
        _ev_dt_str = dt_event.strftime("%Y-%m-%d %H:%M")
        _has_news = bool(md.get("news_headlines")) if 'md' in dir() else False
        loguru_logger.info(
            f"🎯 SIM-EVENT | {_ev_dt_str} {_ev_type} {_ev_dir} | "
            f"Candles: {len(candles)} | Structures: {len(structure_events)}"
        )

        md = reconstruct_market_data(
            base_df, time, structure_events, generate_news=True, event_type_hint=type,
            h1_df=h1_df, h4_df=h4_df, target_event_id=target_ev.get("id")
        )
        _news_count = len(md.get("news_headlines", []))
        _cal_count = len(md.get("upcoming_events", []))
        loguru_logger.info(f"   📰 News: {_news_count} headlines | 📅 Calendar: {_cal_count} events")

        orch = get_orchestrator()
        result = await run_in_threadpool(
            analyze_with_orchestrator_lock, orch, md, symbol, timeframe
        )

        # --- Log: per-agent summary ---
        _ar = result.get("agent_results") or {}
        _ms = _ar.get("market_structure", {})
        _ml = _ar.get("ml_prediction", {})
        _st = _ar.get("sentiment", {})
        _fsig = result.get("final_signal", "HOLD")
        _fconf = result.get("final_confidence", 0.0)
        _appr = "✅" if result.get("approved") else "⛔"
        loguru_logger.info(
            f"   → MS:{_ms.get('signal', '-')}({_ms.get('confidence', 0):.2f}) "
            f"ML:{_ml.get('signal', '-')}({_ml.get('confidence', 0):.2f}) "
            f"SENT:{(_st.get('final_signal') or '-')[:4]}({_st.get('final_confidence', 0):.2f}) "
            f"→ {_fsig} {_fconf:.2f} {_appr}"
        )

        # Propagate counter-swing flag from market data into result so _build_frame can include it
        result["is_counter_swing"] = md.get("is_counter_swing", False)

        frame = _build_frame(target_ev, result)
        frame_dict = frame.dict() if hasattr(frame, "dict") else dict(frame)
        frame_dict["debug_news"] = md.get("news_headlines", [])
        frame_dict["debug_events"] = md.get("upcoming_events", [])
        return frame_dict
    except Exception as e:
        logger.error(f"Event simulation run error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/replay/clear-cache")
async def clear_replay_cache():
    """Clear the replay simulation candle, structure cache, and orchestrator state."""
    global _sim_candle_cache
    _sim_candle_cache.clear()
    
    # Also reset the simulation orchestrator state and warmup cache
    try:
        from app.services.orchestrator_simulator import reset_simulation_orchestrator
        reset_simulation_orchestrator()
        logger.info("[Replay] Simulation orchestrator state reset successfully")
    except Exception as re:
        logger.warning(f"Failed to reset orchestrator state at clear-cache: {re}")

    logger.info("[Replay] Simulation candle cache cleared successfully")
    return {"status": "success", "message": "Replay cache cleared"}



