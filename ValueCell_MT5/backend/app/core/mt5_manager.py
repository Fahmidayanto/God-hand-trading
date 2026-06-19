"""MetaTrader 5 connection manager."""

import logging
from datetime import datetime
from typing import Dict, List, Optional

import MetaTrader5 as mt5

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class MT5Manager:
    """MT5 connection and operations manager."""

    def __init__(self):
        """Initialize MT5 manager."""
        self._connected = False
        self._account_info = None

    def connect(self) -> bool:
        """
        Establish connection to MT5.
        
        Returns:
            bool: True if connected successfully
        """
        try:
            # Initialize MT5
            if not mt5.initialize(
                path=settings.MT5_PATH,
                login=settings.MT5_LOGIN,
                password=settings.MT5_PASSWORD,
                server=settings.MT5_SERVER,
                timeout=settings.MT5_TIMEOUT,
            ):
                logger.error(f"MT5 initialization failed: {mt5.last_error()}")
                return False

            # Verify connection
            account_info = mt5.account_info()
            if account_info is None:
                logger.error("Failed to get account info")
                return False

            self._connected = True
            self._account_info = account_info
            logger.info(f"[OK] Connected to MT5 account {account_info.login}")
            return True

        except Exception as e:
            logger.error(f"MT5 connection error: {e}")
            return False

    def disconnect(self):
        """Disconnect from MT5."""
        if self._connected:
            mt5.shutdown()
            self._connected = False
            logger.info("MT5 disconnected")

    def is_connected(self) -> bool:
        """Check if connected to MT5."""
        return self._connected

    def get_account_info(self) -> Optional[Dict]:
        """
        Get account information.
        
        Returns:
            Dict with account data or None
        """
        if not self._connected:
            return None

        try:
            info = mt5.account_info()
            if info is None:
                return None

            return {
                "login": info.login,
                "server": info.server,
                "name": info.name,
                "balance": info.balance,
                "equity": info.equity,
                "margin": info.margin,
                "free_margin": info.margin_free,
                "margin_level": info.margin_level if info.margin > 0 else 0,
                "leverage": info.leverage,
                "profit": info.profit,
                "currency": info.currency,
            }

        except Exception as e:
            logger.error(f"Error getting account info: {e}")
            return None

    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        count: int = 100,
    ) -> List[Dict]:
        """
        Get candlestick data.
        
        Args:
            symbol: Trading symbol (e.g., XAUUSD)
            timeframe: Timeframe (M1, M5, M15, etc.)
            count: Number of candles
            
        Returns:
            List of candle dicts
        """
        if not self._connected:
            return []

        # Map timeframe
        timeframe_map = {
            "M1": mt5.TIMEFRAME_M1,
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1,
            "W1": mt5.TIMEFRAME_W1,
            "MN1": mt5.TIMEFRAME_MN1,
        }

        mt5_timeframe = timeframe_map.get(timeframe, mt5.TIMEFRAME_M15)

        try:
            rates = mt5.copy_rates_from_pos(symbol, mt5_timeframe, 0, count)
            
            if rates is None or len(rates) == 0:
                logger.warning(f"No data for {symbol} {timeframe}")
                return []

            # Convert broker time to UTC
            # MT5 timestamps are in broker server time; subtract offset to get UTC
            broker_offset_hours = settings.MT5_BROKER_TIMEZONE_OFFSET
            broker_offset_seconds = broker_offset_hours * 3600

            candles = []
            for rate in rates:
                # MT5 gives timestamp in broker local time (as Unix seconds)
                # Convert to true UTC by subtracting broker offset
                broker_time = int(rate["time"])
                utc_time = broker_time - broker_offset_seconds
                
                candles.append({
                    "time": utc_time,  # True UTC timestamp
                    "open": float(rate["open"]),
                    "high": float(rate["high"]),
                    "low": float(rate["low"]),
                    "close": float(rate["close"]),
                    "volume": int(rate["tick_volume"]),
                })
            
            logger.debug(f"Fetched {len(candles)} candles for {symbol} {timeframe} (broker offset: GMT{'+' if broker_offset_hours >= 0 else ''}{broker_offset_hours})")
            if candles:
                first_broker = candles[0]['time'] + broker_offset_seconds
                last_broker = candles[-1]['time'] + broker_offset_seconds
                logger.debug(f"First candle - Broker: {first_broker} ({datetime.fromtimestamp(first_broker)}), UTC: {candles[0]['time']} ({datetime.fromtimestamp(candles[0]['time'])})")
                logger.debug(f"Last candle - Broker: {last_broker} ({datetime.fromtimestamp(last_broker)}), UTC: {candles[-1]['time']} ({datetime.fromtimestamp(candles[-1]['time'])})")

            return candles

        except Exception as e:
            logger.error(f"Error getting candles: {e}")
            return []

    def get_symbol_info(self, symbol: str) -> Optional[Dict]:
        """Get symbol information."""
        if not self._connected:
            return None

        try:
            info = mt5.symbol_info(symbol)
            if info is None:
                return None

            return {
                "name": info.name,
                "bid": info.bid,
                "ask": info.ask,
                "spread": info.spread,
                "digits": info.digits,
                "point": info.point,
                "trade_contract_size": info.trade_contract_size,
                "volume_min": info.volume_min,
                "volume_max": info.volume_max,
                "volume_step": info.volume_step,
            }

        except Exception as e:
            logger.error(f"Error getting symbol info: {e}")
            return None

    def get_positions(self) -> List[Dict]:
        """Get open positions."""
        if not self._connected:
            return []

        try:
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
                    "swap": pos.swap,
                    "time": datetime.fromtimestamp(pos.time),
                    "comment": pos.comment,
                })

            return result

        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []

    def get_history_deals(self, days: int = 30) -> List[Dict]:
        """Get trade history."""
        if not self._connected:
            return []

        try:
            from datetime import timedelta
            
            to_date = datetime.now()
            from_date = to_date - timedelta(days=days)

            deals = mt5.history_deals_get(from_date, to_date)
            if deals is None:
                return []

            result = []
            for deal in deals:
                result.append({
                    "ticket": deal.ticket,
                    "order": deal.order,
                    "time": datetime.fromtimestamp(deal.time),
                    "type": deal.type,
                    "entry": deal.entry,
                    "symbol": deal.symbol,
                    "volume": deal.volume,
                    "price": deal.price,
                    "profit": deal.profit,
                    "swap": deal.swap,
                    "commission": deal.commission,
                    "comment": deal.comment,
                })

            return result

        except Exception as e:
            logger.error(f"Error getting history: {e}")
            return []

    def place_order(
        self,
        symbol: str,
        order_type: str,
        volume: float,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
        comment: str = "",
    ) -> Dict:
        """
        Place a trading order (Paper trading mode only).
        
        Args:
            symbol: Trading symbol
            order_type: BUY or SELL
            volume: Lot size
            sl: Stop loss price
            tp: Take profit price
            comment: Order comment
            
        Returns:
            Dict with order result
        """
        # Check trading mode
        if settings.TRADING_MODE != "paper":
            return {
                "success": False,
                "message": "Live trading not enabled. Set TRADING_MODE=live in .env"
            }

        # Paper trading simulation
        logger.info(f"[PAPER] Paper trade: {order_type} {volume} {symbol}")
        
        return {
            "success": True,
            "message": "Paper trade recorded (not executed in MT5)",
            "ticket": None,
            "type": order_type,
            "volume": volume,
            "symbol": symbol,
            "sl": sl,
            "tp": tp,
        }
