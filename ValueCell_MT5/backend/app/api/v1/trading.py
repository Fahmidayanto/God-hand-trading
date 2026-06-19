"""Trading API endpoints."""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

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
    count: int = Query(100, ge=1, le=1000, description="Number of candles"),
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


@router.get("/candles", response_model=List[CandleData])
async def get_candles(
    symbol: str = Query("XAUUSD", description="Trading symbol"),
    timeframe: str = Query("M15", description="Timeframe"),
    count: int = Query(100, ge=1, le=1000, description="Number of candles"),
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
            logger.info(
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
    days: int = Query(7, ge=1, le=30, description="Number of days to fetch"),
):
    """
    Get trading session zones for the chart shadow bands.

    Sessions are generated deterministically from the MT5 session schedule
    (mirrors the EA), so the sequence is continuous from `days` ago up to the
    live, still-running session. Times are aligned to the candle epoch (server
    wall-clock interpreted as UTC).

    Args:
        symbol: Trading symbol (e.g., XAUUSD)
        days: Number of days to look back (1-30)

    Returns:
        List of session zones with start/end time, session type and status.
    """
    try:
        from datetime import timedelta

        server_now = _server_now()
        start_dt = server_now - timedelta(days=days)

        all_zones = _generate_session_zones(start_dt, server_now)

        # Sort by start time (newest first)
        all_zones.sort(key=lambda x: x['start_time'], reverse=True)

        logger.info(
            f"Generated {len(all_zones)} session zones for {symbol} "
            f"({start_dt} -> {server_now} server time)"
        )

        return {
            "zones": all_zones[:200],
            "total_zones": len(all_zones),
        }

    except Exception as e:
        logger.error(f"Session zones fetch error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
