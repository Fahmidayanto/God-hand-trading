"""
MT5 Adapter - Real-time Market Data Integration

Track 1 (Primary): Real-time trading via MT5 Python API
- Connects to MT5 terminal
- Fetches OHLCV data in real-time
- Provides market data to structure detector
- No CSV file I/O latency
"""

import os
import time
from datetime import datetime
from typing import Optional, Dict, List, Any
import MetaTrader5 as mt5
import pandas as pd
from loguru import logger


class MT5Adapter:
    """
    Adapter for MetaTrader 5 Python API integration.
    
    Features:
    - Initialize MT5 connection
    - Fetch real-time OHLCV data
    - Subscribe to symbols
    - Retrieve account info
    - Health check
    """
    
    def __init__(
        self,
        login: Optional[int] = None,
        password: Optional[str] = None,
        server: Optional[str] = None,
        path: Optional[str] = None,
    ):
        """
        Initialize MT5 Adapter.
        
        Args:
            login: MT5 account login (from .env)
            password: MT5 account password (from .env)
            server: MT5 broker server (from .env)
            path: Path to MT5 terminal executable (from .env)
        """
        self.login = login or int(os.getenv("MT5_LOGIN", "0"))
        self.password = password or os.getenv("MT5_PASSWORD", "")
        self.server = server or os.getenv("MT5_SERVER", "")
        self.path = path or os.getenv("MT5_PATH", "")
        
        self.connected = False
        self.initialized = False
        
        logger.info("MT5Adapter initialized with configuration")
    
    def initialize(self) -> bool:
        """
        Initialize connection to MT5 terminal.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Initialize MT5 connection
            if self.path:
                initialized = mt5.initialize(
                    path=self.path,
                    login=self.login,
                    password=self.password,
                    server=self.server
                )
            else:
                initialized = mt5.initialize()
            
            if not initialized:
                logger.error(f"MT5 initialization failed: {mt5.last_error()}")
                return False
            
            # Get terminal info
            terminal_info = mt5.terminal_info()
            if terminal_info is None:
                logger.error("Failed to get terminal info")
                mt5.shutdown()
                return False
            
            self.initialized = True
            self.connected = terminal_info.connected
            
            logger.info(f"✅ MT5 initialized successfully")
            logger.info(f"   Company: {terminal_info.company}")
            logger.info(f"   Version: {mt5.version()}")
            logger.info(f"   Connected: {self.connected}")
            
            # Get account info if connected
            if self.connected:
                account_info = mt5.account_info()
                if account_info:
                    logger.info(f"   Account: {account_info.login}")
                    logger.info(f"   Balance: ${account_info.balance:.2f}")
                    logger.info(f"   Leverage: 1:{account_info.leverage}")
            
            return True
            
        except Exception as e:
            logger.error(f"Exception during MT5 initialization: {e}")
            return False
    
    def shutdown(self):
        """Shutdown MT5 connection."""
        if self.initialized:
            mt5.shutdown()
            self.initialized = False
            self.connected = False
            logger.info("MT5 connection closed")
    
    def get_rates(
        self,
        symbol: str,
        timeframe: int,
        count: int = 100,
        position: int = 0
    ) -> Optional[pd.DataFrame]:
        """
        Get OHLCV rates from MT5.
        
        Args:
            symbol: Trading symbol (e.g., "XAUUSD")
            timeframe: MT5 timeframe constant (e.g., mt5.TIMEFRAME_M15)
            count: Number of bars to retrieve
            position: Starting position (0 = latest)
        
        Returns:
            DataFrame with columns: time, open, high, low, close, tick_volume, real_volume
        """
        if not self.initialized:
            logger.error("MT5 not initialized. Call initialize() first.")
            return None
        
        try:
            # Fetch rates
            rates = mt5.copy_rates_from_pos(symbol, timeframe, position, count)
            
            if rates is None:
                logger.error(f"Failed to get rates for {symbol}: {mt5.last_error()}")
                return None
            
            if len(rates) == 0:
                logger.warning(f"No rates returned for {symbol}")
                return None
            
            # Convert to DataFrame
            df = pd.DataFrame(rates)
            
            # Convert time to datetime
            df['time'] = pd.to_datetime(df['time'], unit='s')
            
            logger.debug(f"Retrieved {len(df)} bars for {symbol} (TF: {timeframe})")
            
            return df
            
        except Exception as e:
            logger.error(f"Exception while fetching rates: {e}")
            return None
    
    def get_symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get symbol information.
        
        Args:
            symbol: Trading symbol (e.g., "XAUUSD")
        
        Returns:
            Dict with symbol properties (spread, point, digits, etc.)
        """
        if not self.initialized:
            logger.error("MT5 not initialized.")
            return None
        
        try:
            info = mt5.symbol_info(symbol)
            
            if info is None:
                logger.error(f"Failed to get symbol info for {symbol}")
                return None
            
            return {
                "name": info.name,
                "digits": info.digits,
                "point": info.point,
                "spread": info.spread,
                "trade_mode": info.trade_mode,
                "volume_min": info.volume_min,
                "volume_max": info.volume_max,
                "volume_step": info.volume_step,
            }
            
        except Exception as e:
            logger.error(f"Exception while getting symbol info: {e}")
            return None
    
    def check_spread(self, symbol: str, max_spread_pips: float = 5.0) -> bool:
        """
        Check if current spread is acceptable.
        
        Args:
            symbol: Trading symbol
            max_spread_pips: Maximum acceptable spread in pips
        
        Returns:
            True if spread is acceptable, False otherwise
        """
        info = self.get_symbol_info(symbol)
        if not info:
            return False
        
        spread_pips = info['spread'] * info['point'] * 10  # Convert to pips
        
        if spread_pips > max_spread_pips:
            logger.warning(f"Spread too high: {spread_pips:.1f} pips (max: {max_spread_pips})")
            return False
        
        return True
    
    def get_account_info(self) -> Optional[Dict[str, Any]]:
        """
        Get current account information.
        
        Returns:
            Dict with account balance, equity, margin, etc.
        """
        if not self.initialized or not self.connected:
            logger.error("MT5 not connected.")
            return None
        
        try:
            account = mt5.account_info()
            
            if account is None:
                logger.error("Failed to get account info")
                return None
            
            return {
                "login": account.login,
                "balance": account.balance,
                "equity": account.equity,
                "margin": account.margin,
                "margin_free": account.margin_free,
                "margin_level": account.margin_level,
                "profit": account.profit,
                "leverage": account.leverage,
            }
            
        except Exception as e:
            logger.error(f"Exception while getting account info: {e}")
            return None
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on MT5 connection.
        
        Returns:
            Dict with health status
        """
        status = {
            "initialized": self.initialized,
            "connected": self.connected,
            "timestamp": datetime.now().isoformat(),
        }
        
        if self.initialized:
            terminal_info = mt5.terminal_info()
            if terminal_info:
                status["connected"] = terminal_info.connected
                status["terminal"] = {
                    "company": terminal_info.company,
                    "name": terminal_info.name,
                }
        
        return status


# Timeframe constants (for easy reference)
TIMEFRAME_M1 = mt5.TIMEFRAME_M1
TIMEFRAME_M5 = mt5.TIMEFRAME_M5
TIMEFRAME_M15 = mt5.TIMEFRAME_M15
TIMEFRAME_M30 = mt5.TIMEFRAME_M30
TIMEFRAME_H1 = mt5.TIMEFRAME_H1
TIMEFRAME_H4 = mt5.TIMEFRAME_H4
TIMEFRAME_D1 = mt5.TIMEFRAME_D1


if __name__ == "__main__":
    """
    Test script for MT5Adapter.
    
    Usage:
        cd python
        python -m valuecell.adapters.mt5.mt5_adapter
    """
    from dotenv import load_dotenv
    
    # Load environment variables
    load_dotenv()
    
    # Initialize adapter
    adapter = MT5Adapter()
    
    # Test connection
    if adapter.initialize():
        print("✅ MT5 connection successful")
        
        # Get account info
        account = adapter.get_account_info()
        if account:
            print(f"\n📊 Account Info:")
            print(f"   Login: {account['login']}")
            print(f"   Balance: ${account['balance']:.2f}")
            print(f"   Equity: ${account['equity']:.2f}")
        
        # Get symbol info
        symbol = os.getenv("TRADING_SYMBOL", "XAUUSD")
        symbol_info = adapter.get_symbol_info(symbol)
        if symbol_info:
            print(f"\n💎 Symbol: {symbol}")
            print(f"   Digits: {symbol_info['digits']}")
            print(f"   Spread: {symbol_info['spread']} points")
            print(f"   Point: {symbol_info['point']}")
        
        # Get latest rates
        rates = adapter.get_rates(symbol, TIMEFRAME_M15, count=10)
        if rates is not None:
            print(f"\n📈 Latest 10 bars ({symbol} M15):")
            print(rates[['time', 'open', 'high', 'low', 'close']].to_string())
        
        # Health check
        health = adapter.health_check()
        print(f"\n🏥 Health Check:")
        print(f"   Status: {'✅ Healthy' if health['connected'] else '❌ Disconnected'}")
        
        # Shutdown
        adapter.shutdown()
    else:
        print("❌ MT5 connection failed")
