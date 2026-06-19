"""Trading Dashboard API Router for ValueCell.

Provides endpoints for:
- Dashboard stats and overview
- Live chart data (OHLC candlesticks)
- Trading history and positions
- Agent performance and consensus
- System health and metrics
"""

from __future__ import annotations

import csv
import os
import re
import MetaTrader5 as mt5
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from loguru import logger

# Path to backtest result directory containing MarketData CSVs with pre-calculated EMA200
BACKTEST_RESULT_DIR = Path(r"d:\Project\Project MT5\Backtest_result")

# MT5 server timezone (typically GMT+2 for most brokers, GMT+3 during DST)
# Adjust if your broker uses a different offset
MT5_SERVER_OFFSET_HOURS = 2
MT5_SERVER_TZ = timezone(timedelta(hours=MT5_SERVER_OFFSET_HOURS))

# Pydantic Models for API responses


class DashboardStats(BaseModel):
    """Dashboard overview statistics."""
    
    balance: float = Field(..., description="Account balance")
    equity: float = Field(..., description="Account equity")
    open_positions: int = Field(..., description="Number of open positions")
    today_pnl: float = Field(..., description="Today's profit/loss")
    today_pnl_pct: float = Field(..., description="Today's P&L percentage")
    system_health: float = Field(..., description="System health percentage")
    uptime_seconds: int = Field(..., description="System uptime in seconds")


class MarketSignal(BaseModel):
    """Current market trading signal."""
    
    symbol: str = Field(..., description="Trading symbol")
    timeframe: str = Field(..., description="Timeframe (e.g., M15)")
    signal_type: str = Field(..., description="Signal type (CHoCH, BoS, HOLD)")
    direction: str = Field(..., description="Direction (BULLISH, BEARISH)")
    price: float = Field(..., description="Current price")
    confidence: float = Field(..., description="Signal confidence 0-100")
    timestamp: str = Field(..., description="Signal timestamp")


class AgentStatus(BaseModel):
    """Individual agent status and performance."""
    
    name: str = Field(..., description="Agent name")
    type: str = Field(..., description="Agent type")
    status: str = Field(..., description="Status (ACTIVE, INACTIVE)")
    signal: str = Field(..., description="Current signal")
    confidence: float = Field(..., description="Confidence 0-100")
    accuracy: float = Field(..., description="Historical accuracy percentage")
    signals_today: int = Field(..., description="Signals generated today")


class AgentConsensus(BaseModel):
    """Overall agent consensus."""
    
    consensus: str = Field(..., description="Consensus decision (BUY, SELL, HOLD)")
    confidence: float = Field(..., description="Overall confidence 0-100")
    threshold: float = Field(..., description="Execution threshold")
    agents: List[AgentStatus] = Field(..., description="Individual agent statuses")


class CandleData(BaseModel):
    """OHLC candlestick data."""
    
    time: int = Field(..., description="Unix timestamp")
    open: float = Field(..., description="Open price")
    high: float = Field(..., description="High price")
    low: float = Field(..., description="Low price")
    close: float = Field(..., description="Close price")
    volume: int = Field(..., description="Tick volume")
    ema200: Optional[float] = Field(None, description="EMA 200 value")


class ChartData(BaseModel):
    """Chart data response."""
    
    symbol: str = Field(..., description="Symbol name")
    timeframe: str = Field(..., description="Timeframe")
    candles: List[CandleData] = Field(..., description="List of candlesticks")
    ema_periods: List[int] = Field(default_factory=list, description="EMA periods included")


class Trade(BaseModel):
    """Individual trade information."""
    
    trade_id: str = Field(..., description="Trade ID")
    symbol: str = Field(..., description="Symbol")
    type: str = Field(..., description="Trade type (BUY, SELL)")
    entry_price: float = Field(..., description="Entry price")
    exit_price: Optional[float] = Field(None, description="Exit price")
    lot_size: float = Field(..., description="Lot size")
    pnl: float = Field(..., description="Profit/Loss")
    status: str = Field(..., description="Status (OPEN, CLOSED)")
    open_time: str = Field(..., description="Open timestamp")
    close_time: Optional[str] = Field(None, description="Close timestamp")


class TradeHistory(BaseModel):
    """Trading history response."""
    
    total_trades: int = Field(..., description="Total number of trades")
    win_rate: float = Field(..., description="Win rate percentage")
    total_pnl: float = Field(..., description="Total P&L")
    trades: List[Trade] = Field(..., description="List of trades")


class PerformanceStats(BaseModel):
    """Performance analytics."""
    
    total_return: float = Field(..., description="Total return percentage")
    win_rate: float = Field(..., description="Win rate percentage")
    profit_factor: float = Field(..., description="Profit factor")
    sharpe_ratio: float = Field(..., description="Sharpe ratio")
    max_drawdown: float = Field(..., description="Maximum drawdown percentage")
    avg_win: float = Field(..., description="Average win amount")
    avg_loss: float = Field(..., description="Average loss amount")


class MonthlyPerformance(BaseModel):
    """Monthly performance data."""
    
    month: str = Field(..., description="Month name")
    trades: int = Field(..., description="Number of trades")
    win_rate: float = Field(..., description="Win rate percentage")
    pnl: float = Field(..., description="Profit/Loss")
    return_pct: float = Field(..., description="Return percentage")
    max_dd: float = Field(..., description="Max drawdown percentage")


# MT5 Helper Functions


def init_mt5() -> bool:
    """Initialize MT5 connection."""
    if not mt5.initialize():
        logger.error("MT5 initialization failed")
        return False
    return True


def get_account_info() -> Dict[str, Any]:
    """Get MT5 account information."""
    if not init_mt5():
        return {}
    
    info = mt5.account_info()
    if info is None:
        return {}
    
    return {
        "balance": info.balance,
        "equity": info.equity,
        "margin": info.margin,
        "free_margin": info.margin_free,
        "margin_level": info.margin_level if info.margin > 0 else 0,
        "profit": info.profit,
    }


# ── EMA 200 from CSV ──────────────────────────────────────────────────────────

# Cache: (timeframe, csv_path) → {unix_timestamp: ema200_value}
_ema200_cache: Dict[str, Dict[int, float]] = {}
_ema200_cache_mtime: Dict[str, float] = {}

MT5_DT_FORMAT = "%Y.%m.%d %H:%M:%S"


def _find_latest_market_data_csv(timeframe: str) -> Optional[Path]:
    """Find the latest MarketData CSV file for a given timeframe."""
    pattern = re.compile(rf"MarketData_XAUUSD_{timeframe}_(\d{{4}}-\d{{2}}-\d{{2}})\.csv")
    best: Optional[Path] = None
    best_date = ""
    
    if not BACKTEST_RESULT_DIR.exists():
        logger.warning(f"[EMA CSV] Directory not found: {BACKTEST_RESULT_DIR}")
        return None
    
    for fpath in BACKTEST_RESULT_DIR.glob(f"MarketData_XAUUSD_{timeframe}_*.csv"):
        m = pattern.match(fpath.name)
        if m:
            date_str = m.group(1)
            if date_str > best_date:
                best_date = date_str
                best = fpath
    
    return best


def _load_ema200_from_csv(timeframe: str) -> Dict[int, float]:
    """Load EMA200 values from the latest MarketData CSV.
    
    Returns dict mapping unix_timestamp → ema200_value.
    Uses file mtime-based caching to avoid re-reading unchanged files.
    """
    csv_path = _find_latest_market_data_csv(timeframe)
    if csv_path is None:
        logger.warning(f"[EMA CSV] No MarketData CSV found for timeframe={timeframe}")
        return {}
    
    cache_key = timeframe
    csv_mtime = csv_path.stat().st_mtime
    
    # Return cached data if file hasn't changed
    if cache_key in _ema200_cache and _ema200_cache_mtime.get(cache_key) == csv_mtime:
        logger.debug(f"[EMA CSV] Using cached EMA200 data for {timeframe} ({len(_ema200_cache[cache_key])} entries)")
        return _ema200_cache[cache_key]
    
    logger.info(f"[EMA CSV] Loading EMA200 from: {csv_path.name}")
    
    ema_map: Dict[int, float] = {}
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                time_str = row.get("Time", "").strip()
                ema_str = row.get("EMA200", "").strip()
                if not time_str or not ema_str:
                    continue
                try:
                    dt = datetime.strptime(time_str, MT5_DT_FORMAT)
                    # CSV times are in MT5 server timezone (GMT+2), convert to UTC Unix timestamp
                    dt_mt5 = dt.replace(tzinfo=MT5_SERVER_TZ)
                    unix_ts = int(dt_mt5.timestamp())
                    ema_val = float(ema_str)
                    ema_map[unix_ts] = ema_val
                except (ValueError, KeyError):
                    continue
    except Exception as e:
        logger.error(f"[EMA CSV] Error reading {csv_path}: {e}")
        return {}
    
    _ema200_cache[cache_key] = ema_map
    _ema200_cache_mtime[cache_key] = csv_mtime
    logger.info(f"[EMA CSV] Loaded {len(ema_map)} EMA200 entries for {timeframe}")
    
    return ema_map


def get_mt5_candles(
    symbol: str,
    timeframe: str,
    count: int = 100,
    ema_periods: Optional[List[int]] = None,
) -> List[Dict[str, Any]]:
    """Get candlestick data from MT5 with EMA 200 from pre-calculated CSV.
    
    EMA 200 is loaded from Backtest_result MarketData CSV files instead of
    being calculated from MT5 data. This ensures accurate EMA 200 values
    based on full historical data.
    
    Args:
        symbol: Trading symbol (e.g. XAUUSD)
        timeframe: Timeframe string (M1, M5, M15, M30, H1, H4, D1)
        count: Number of candles to return
        ema_periods: List of EMA periods requested (e.g. [200])
    
    Returns:
        List of candle dicts with optional ema{period} fields.
    """
    if not init_mt5():
        return []
    
    # Map timeframe string to MT5 constant
    timeframe_map = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1,
    }
    
    mt5_timeframe = timeframe_map.get(timeframe, mt5.TIMEFRAME_M15)
    
    logger.info(
        f"[EMA DEBUG] get_mt5_candles: symbol={symbol} tf={timeframe} "
        f"count={count} ema_periods={ema_periods}"
    )
    
    # Fetch only the requested candles (no extra bars needed for CSV-based EMA)
    rates = mt5.copy_rates_from_pos(symbol, mt5_timeframe, 0, count)
    
    if rates is None or len(rates) == 0:
        logger.warning("[EMA DEBUG] MT5 returned no rates!")
        return []
    
    logger.info(f"[EMA DEBUG] MT5 returned {len(rates)} bars")
    
    # Load EMA 200 from CSV if requested
    ema200_map: Dict[int, float] = {}
    if ema_periods and 200 in ema_periods:
        ema200_map = _load_ema200_from_csv(timeframe)
        if ema200_map:
            logger.info(
                f"[EMA DEBUG] CSV EMA200 loaded: {len(ema200_map)} entries for {timeframe}"
            )
        else:
            logger.warning(
                f"[EMA DEBUG] CSV EMA200 EMPTY for {timeframe} — EMA 200 will not appear!"
            )
    
    # Build candle list with EMA 200 from CSV lookup
    candles = []
    ema200_matched = 0
    ema200_missed = 0
    for rate in rates:
        candle_time = int(rate['time'])
        candle = {
            "time": candle_time,
            "open": float(rate['open']),
            "high": float(rate['high']),
            "low": float(rate['low']),
            "close": float(rate['close']),
            "volume": int(rate['tick_volume']),
        }
        # Attach EMA 200 from CSV
        if ema_periods and 200 in ema_periods:
            ema_val = ema200_map.get(candle_time)
            candle["ema200"] = round(ema_val, 2) if ema_val is not None else None
            if ema_val is not None:
                ema200_matched += 1
            else:
                ema200_missed += 1
        
        candles.append(candle)
    
    if ema_periods and 200 in ema_periods:
        logger.info(
            f"[EMA DEBUG] Returning {len(candles)} candles: "
            f"{ema200_matched} matched EMA200, {ema200_missed} missed"
        )
        if candles:
            first_ema = candles[0].get("ema200")
            last_ema = candles[-1].get("ema200")
            logger.info(
                f"[EMA DEBUG] First candle time={candles[0]['time']} ema200={first_ema}, "
                f"Last candle time={candles[-1]['time']} ema200={last_ema}"
            )
            if ema200_missed > 0 and ema200_matched > 0:
                # Log first missed timestamp for debugging
                for c in candles:
                    if c.get("ema200") is None:
                        logger.info(
                            f"[EMA DEBUG] First missed timestamp: {c['time']} "
                            f"({datetime.fromtimestamp(c['time'])})"
                        )
                        break
    
    return candles


def _calculate_ema(prices: List[float], period: int) -> List[float]:
    """Calculate Exponential Moving Average for a list of prices.
    
    Uses the standard EMA formula:
      EMA_t = close_t * k + EMA_{t-1} * (1 - k)
      where k = 2 / (period + 1)
    
    First EMA value is seeded with SMA of the first `period` bars.
    Returns a list the same length as `prices` (None for bars before the seed).
    """
    if len(prices) < period:
        return [None] * len(prices)
    
    k = 2.0 / (period + 1)
    result: List[Optional[float]] = [None] * (period - 1)
    
    # Seed with SMA
    sma = sum(prices[:period]) / period
    result.append(sma)
    
    # Calculate EMA for remaining bars
    ema_prev = sma
    for i in range(period, len(prices)):
        ema = prices[i] * k + ema_prev * (1 - k)
        result.append(ema)
        ema_prev = ema
    
    return result


def get_open_positions() -> List[Dict[str, Any]]:
    """Get open positions from MT5."""
    if not init_mt5():
        return []
    
    positions = mt5.positions_get()
    if positions is None:
        return []
    
    result = []
    for pos in positions:
        result.append({
            "ticket": pos.ticket,
            "symbol": pos.symbol,
            "type": "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL",
            "volume": pos.volume,
            "price_open": pos.price_open,
            "price_current": pos.price_current,
            "sl": pos.sl,
            "tp": pos.tp,
            "profit": pos.profit,
            "time": datetime.fromtimestamp(pos.time).isoformat(),
        })
    
    return result


def get_trade_history(days: int = 30) -> List[Dict[str, Any]]:
    """Get trade history from MT5."""
    if not init_mt5():
        return []
    
    # Get deals from last N days
    from_date = datetime.now() - timedelta(days=days)
    to_date = datetime.now()
    
    deals = mt5.history_deals_get(from_date, to_date)
    
    if deals is None or len(deals) == 0:
        return []
    
    # Group deals by position ticket
    trades = {}
    for deal in deals:
        ticket = deal.position_id
        if ticket not in trades:
            trades[ticket] = {
                "trade_id": f"#TRD-{ticket}",
                "symbol": deal.symbol,
                "type": "BUY" if deal.type == mt5.DEAL_TYPE_BUY else "SELL",
                "entry_price": 0,
                "exit_price": None,
                "lot_size": deal.volume,
                "pnl": 0,
                "status": "OPEN",
                "open_time": datetime.fromtimestamp(deal.time).isoformat(),
                "close_time": None,
            }
        
        # Update with deal info
        if deal.entry == mt5.DEAL_ENTRY_IN:
            trades[ticket]["entry_price"] = deal.price
        elif deal.entry == mt5.DEAL_ENTRY_OUT:
            trades[ticket]["exit_price"] = deal.price
            trades[ticket]["status"] = "CLOSED"
            trades[ticket]["close_time"] = datetime.fromtimestamp(deal.time).isoformat()
        
        trades[ticket]["pnl"] += deal.profit
    
    return list(trades.values())


# Create Router

def create_trading_dashboard_router() -> APIRouter:
    """Create trading dashboard router."""
    
    router = APIRouter(prefix="/trading", tags=["Trading Dashboard"])
    
    @router.get("/dashboard/stats", response_model=DashboardStats)
    async def get_dashboard_stats():
        """Get dashboard overview statistics."""
        try:
            account_info = get_account_info()
            open_positions = get_open_positions()
            
            # Calculate today's P&L (placeholder - needs historical data)
            today_pnl = account_info.get("profit", 0.0)
            balance = account_info.get("balance", 0.0)
            today_pnl_pct = (today_pnl / balance * 100) if balance > 0 else 0.0
            
            return DashboardStats(
                balance=balance,
                equity=account_info.get("equity", balance),
                open_positions=len(open_positions),
                today_pnl=today_pnl,
                today_pnl_pct=today_pnl_pct,
                system_health=100.0,  # Placeholder
                uptime_seconds=3600,  # Placeholder
            )
        except Exception as e:
            logger.error(f"Error getting dashboard stats: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/signal/current", response_model=MarketSignal)
    async def get_current_signal(
        symbol: str = Query("XAUUSD", description="Trading symbol"),
        timeframe: str = Query("M15", description="Timeframe")
    ):
        """Get current market signal."""
        try:
            # TODO: Integrate with actual trading system signal detection
            # For now, return placeholder
            
            candles = get_mt5_candles(symbol, timeframe, 1)
            current_price = candles[0]["close"] if candles else 0.0
            
            return MarketSignal(
                symbol=symbol,
                timeframe=timeframe,
                signal_type="CHoCH",
                direction="BEARISH",
                price=current_price,
                confidence=40.0,
                timestamp=datetime.now().isoformat(),
            )
        except Exception as e:
            logger.error(f"Error getting current signal: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/agents/consensus", response_model=AgentConsensus)
    async def get_agent_consensus():
        """Get agent consensus and individual status."""
        try:
            # TODO: Integrate with actual agent system
            # For now, return placeholder data
            
            agents = [
                AgentStatus(
                    name="Price Action Agent",
                    type="technical",
                    status="ACTIVE",
                    signal="HOLD",
                    confidence=40.0,
                    accuracy=72.3,
                    signals_today=12,
                ),
                AgentStatus(
                    name="Market Structure Agent",
                    type="structure",
                    status="ACTIVE",
                    signal="HOLD",
                    confidence=40.0,
                    accuracy=68.7,
                    signals_today=8,
                ),
                AgentStatus(
                    name="ML Filter Agent",
                    type="ml",
                    status="ACTIVE",
                    signal="PENDING",
                    confidence=0.0,
                    accuracy=76.5,
                    signals_today=0,
                ),
                AgentStatus(
                    name="Risk Manager",
                    type="risk",
                    status="ACTIVE",
                    signal="ACTIVE",
                    confidence=100.0,
                    accuracy=100.0,
                    signals_today=0,
                ),
            ]
            
            return AgentConsensus(
                consensus="HOLD",
                confidence=40.0,
                threshold=40.0,
                agents=agents,
            )
        except Exception as e:
            logger.error(f"Error getting agent consensus: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/chart/data", response_model=ChartData)
    async def get_chart_data(
        symbol: str = Query("XAUUSD", description="Trading symbol"),
        timeframe: str = Query("M15", description="Timeframe"),
        count: int = Query(100, description="Number of candles", ge=1, le=1000),
        ema: Optional[str] = Query(None, description="Comma-separated EMA periods (e.g. '200' or '50,200')")
    ):
        """Get chart candlestick data with optional EMA overlays."""
        try:
            # Parse EMA periods from query string
            ema_periods = None
            if ema:
                try:
                    ema_periods = [int(p.strip()) for p in ema.split(",") if p.strip()]
                except ValueError:
                    raise HTTPException(status_code=400, detail="Invalid EMA period format. Use comma-separated integers.")
            
            logger.info(
                f"[EMA DEBUG] /chart/data request: symbol={symbol} tf={timeframe} "
                f"count={count} ema_param={ema!r} ema_periods={ema_periods}"
            )
            
            candles = get_mt5_candles(symbol, timeframe, count, ema_periods=ema_periods)
            
            if not candles:
                raise HTTPException(status_code=404, detail="No data available")
            
            # Log EMA data in response
            if ema_periods:
                ema_sample = [c.get("ema200") for c in candles if c.get("ema200") is not None]
                logger.info(
                    f"[EMA DEBUG] /chart/data response: {len(candles)} candles, "
                    f"{len(ema_sample)} with ema200, "
                    f"sample_values(first 3)={ema_sample[:3]}"
                )
            
            return ChartData(
                symbol=symbol,
                timeframe=timeframe,
                candles=[CandleData(**c) for c in candles],
                ema_periods=ema_periods or [],
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting chart data: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/trades/history", response_model=TradeHistory)
    async def get_trade_history_endpoint(
        days: int = Query(30, description="Number of days", ge=1, le=365)
    ):
        """Get trade history."""
        try:
            trades_data = get_trade_history(days)
            
            # Calculate statistics
            total_trades = len(trades_data)
            closed_trades = [t for t in trades_data if t["status"] == "CLOSED"]
            winning_trades = [t for t in closed_trades if t["pnl"] > 0]
            
            win_rate = (len(winning_trades) / len(closed_trades) * 100) if closed_trades else 0.0
            total_pnl = sum(t["pnl"] for t in trades_data)
            
            return TradeHistory(
                total_trades=total_trades,
                win_rate=win_rate,
                total_pnl=total_pnl,
                trades=[Trade(**t) for t in trades_data[:20]],  # Limit to 20 recent
            )
        except Exception as e:
            logger.error(f"Error getting trade history: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/performance/stats", response_model=PerformanceStats)
    async def get_performance_stats():
        """Get performance statistics."""
        try:
            trades_data = get_trade_history(180)  # 6 months
            closed_trades = [t for t in trades_data if t["status"] == "CLOSED"]
            
            if not closed_trades:
                return PerformanceStats(
                    total_return=0.0,
                    win_rate=0.0,
                    profit_factor=0.0,
                    sharpe_ratio=0.0,
                    max_drawdown=0.0,
                    avg_win=0.0,
                    avg_loss=0.0,
                )
            
            winning_trades = [t for t in closed_trades if t["pnl"] > 0]
            losing_trades = [t for t in closed_trades if t["pnl"] < 0]
            
            win_rate = (len(winning_trades) / len(closed_trades) * 100) if closed_trades else 0.0
            total_wins = sum(t["pnl"] for t in winning_trades)
            total_losses = abs(sum(t["pnl"] for t in losing_trades))
            profit_factor = (total_wins / total_losses) if total_losses > 0 else 0.0
            
            avg_win = (total_wins / len(winning_trades)) if winning_trades else 0.0
            avg_loss = (total_losses / len(losing_trades)) if losing_trades else 0.0
            
            # Calculate total return
            account_info = get_account_info()
            balance = account_info.get("balance", 10000.0)
            total_pnl = sum(t["pnl"] for t in closed_trades)
            total_return = (total_pnl / balance * 100) if balance > 0 else 0.0
            
            return PerformanceStats(
                total_return=total_return,
                win_rate=win_rate,
                profit_factor=profit_factor,
                sharpe_ratio=1.87,  # Placeholder - needs calculation
                max_drawdown=-8.3,  # Placeholder - needs calculation
                avg_win=avg_win,
                avg_loss=-avg_loss,
            )
        except Exception as e:
            logger.error(f"Error getting performance stats: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/performance/monthly", response_model=List[MonthlyPerformance])
    async def get_monthly_performance():
        """Get monthly performance data."""
        try:
            # TODO: Calculate actual monthly performance from trade history
            # For now, return placeholder data
            
            months_data = [
                MonthlyPerformance(
                    month="June 2026",
                    trades=24,
                    win_rate=70.8,
                    pnl=456.78,
                    return_pct=4.57,
                    max_dd=-2.1,
                ),
                MonthlyPerformance(
                    month="May 2026",
                    trades=31,
                    win_rate=67.7,
                    pnl=623.45,
                    return_pct=6.23,
                    max_dd=-3.4,
                ),
                MonthlyPerformance(
                    month="April 2026",
                    trades=28,
                    win_rate=64.3,
                    pnl=512.90,
                    return_pct=5.13,
                    max_dd=-4.2,
                ),
                MonthlyPerformance(
                    month="March 2026",
                    trades=35,
                    win_rate=71.4,
                    pnl=789.23,
                    return_pct=7.89,
                    max_dd=-2.8,
                ),
                MonthlyPerformance(
                    month="February 2026",
                    trades=26,
                    win_rate=61.5,
                    pnl=345.67,
                    return_pct=3.46,
                    max_dd=-5.1,
                ),
                MonthlyPerformance(
                    month="January 2026",
                    trades=29,
                    win_rate=69.0,
                    pnl=728.75,
                    return_pct=7.29,
                    max_dd=-3.6,
                ),
            ]
            
            return months_data
        except Exception as e:
            logger.error(f"Error getting monthly performance: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    return router

