"""
Execution Agent - MT5 Order Placement & Position Monitoring

This agent handles:
1. Order placement via MT5 Python API
2. Position monitoring (real-time P&L tracking)
3. SL/TP modifications (breakeven, trailing stop)
4. Position closure (manual or automatic)
5. Order validation and risk checks

Integrates with:
- State Machine Agent (state transitions)
- Risk Management Agent (position sizing)
- MT5 Terminal (order execution)
"""

import MetaTrader5 as mt5
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
from loguru import logger


class OrderType(Enum):
    """MT5 order types"""
    BUY = mt5.ORDER_TYPE_BUY
    SELL = mt5.ORDER_TYPE_SELL


class ExecutionAgent:
    """
    Execution Agent - Handles order placement and position monitoring.
    
    Purpose:
    - Place market orders (BUY/SELL)
    - Monitor open positions
    - Update SL/TP levels
    - Close positions
    - Track order history
    - Error handling and retry logic
    
    MT5 Integration:
    - Uses MetaTrader5 Python API
    - Requires active MT5 terminal connection
    - Supports XAUUSD and other symbols
    """
    
    def __init__(
        self,
        symbol: str = "XAUUSD",
        magic_number: int = 234000,
        deviation: int = 20,
        enable_paper_trading: bool = False
    ):
        """
        Initialize Execution Agent.
        
        Args:
            symbol: Trading symbol (default: XAUUSD)
            magic_number: Unique identifier for orders
            deviation: Max price deviation in points
            enable_paper_trading: If True, simulate orders without real execution
        """
        self.name = "ExecutionAgent"
        self.version = "1.0.0"
        self.symbol = symbol
        self.magic_number = magic_number
        self.deviation = deviation
        self.paper_trading = enable_paper_trading
        
        # Initialize MT5
        self.mt5_initialized = False
        self._initialize_mt5()
        
        logger.info(
            f"✅ {self.name} v{self.version} initialized | "
            f"Symbol: {symbol} | "
            f"Magic: {magic_number} | "
            f"Paper trading: {enable_paper_trading}"
        )
    
    def _initialize_mt5(self) -> bool:
        """Initialize MT5 connection"""
        try:
            if not mt5.initialize():
                logger.error(f"❌ MT5 initialization failed: {mt5.last_error()}")
                return False
            
            self.mt5_initialized = True
            
            # Get terminal info
            terminal_info = mt5.terminal_info()
            if terminal_info:
                logger.info(f"📊 MT5 Terminal: {terminal_info.company} (Build {terminal_info.build})")
            
            # Get account info
            account_info = mt5.account_info()
            if account_info:
                logger.info(
                    f"💼 Account: {account_info.login} | "
                    f"Balance: ${account_info.balance:.2f} | "
                    f"Equity: ${account_info.equity:.2f}"
                )
            
            return True
            
        except Exception as e:
            logger.error(f"❌ MT5 initialization error: {e}")
            return False
    
    def place_order(
        self,
        signal: str,
        lot_size: float,
        sl_price: float,
        tp_price: float,
        comment: str = ""
    ) -> Dict[str, Any]:
        """
        Place market order (BUY or SELL).
        
        Args:
            signal: "BUY" or "SELL"
            lot_size: Position size in lots
            sl_price: Stop loss price
            tp_price: Take profit price
            comment: Order comment
        
        Returns:
            Order result with ticket, entry price, and status
        """
        try:
            if not self.mt5_initialized:
                return self._error_response("MT5 not initialized")
            
            # Validate inputs
            if signal not in ["BUY", "SELL"]:
                return self._error_response(f"Invalid signal: {signal}")
            
            if lot_size <= 0:
                return self._error_response(f"Invalid lot size: {lot_size}")
            
            # Get current price
            tick = mt5.symbol_info_tick(self.symbol)
            if tick is None:
                return self._error_response(f"Failed to get tick for {self.symbol}")
            
            # Determine order type and price
            if signal == "BUY":
                order_type = mt5.ORDER_TYPE_BUY
                price = tick.ask
            else:
                order_type = mt5.ORDER_TYPE_SELL
                price = tick.bid
            
            # Paper trading mode (simulate only)
            if self.paper_trading:
                logger.warning("📄 PAPER TRADING MODE - Order simulated (not executed)")
                return {
                    "success": True,
                    "paper_trading": True,
                    "ticket": 999999999,  # Fake ticket
                    "signal": signal,
                    "entry_price": price,
                    "lot_size": lot_size,
                    "sl_price": sl_price,
                    "tp_price": tp_price,
                    "timestamp": datetime.now().isoformat(),
                    "comment": f"PAPER: {comment}"
                }
            
            # Prepare order request
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": lot_size,
                "type": order_type,
                "price": price,
                "sl": sl_price,
                "tp": tp_price,
                "deviation": self.deviation,
                "magic": self.magic_number,
                "comment": comment[:31],  # MT5 limit: 31 chars
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            logger.info(
                f"📤 Placing {signal} order: {lot_size:.2f} lots @ {price:.2f} | "
                f"SL: {sl_price:.2f} | TP: {tp_price:.2f}"
            )
            
            # Send order
            result = mt5.order_send(request)
            
            if result is None:
                return self._error_response("order_send returned None")
            
            # Check result
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                error_msg = f"Order failed: {result.retcode} - {result.comment}"
                logger.error(f"❌ {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "retcode": result.retcode,
                    "comment": result.comment
                }
            
            # Success!
            logger.info(
                f"✅ Order executed successfully! | "
                f"Ticket: {result.order} | "
                f"Entry: {result.price:.2f}"
            )
            
            return {
                "success": True,
                "paper_trading": False,
                "ticket": result.order,
                "signal": signal,
                "entry_price": result.price,
                "lot_size": lot_size,
                "sl_price": sl_price,
                "tp_price": tp_price,
                "timestamp": datetime.now().isoformat(),
                "comment": comment,
                "retcode": result.retcode
            }
            
        except Exception as e:
            logger.error(f"❌ Order placement failed: {e}")
            return self._error_response(str(e))
    
    def get_position(self, ticket: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Get position details by ticket or get all positions.
        
        Args:
            ticket: Position ticket (if None, returns all positions)
        
        Returns:
            Position details or None if not found
        """
        try:
            if not self.mt5_initialized:
                logger.warning("MT5 not initialized")
                return None
            
            # Get positions
            if ticket:
                positions = mt5.positions_get(ticket=ticket)
            else:
                positions = mt5.positions_get(symbol=self.symbol)
            
            if positions is None or len(positions) == 0:
                return None
            
            # Convert first position to dict
            pos = positions[0]
            
            # Calculate current P&L
            tick = mt5.symbol_info_tick(self.symbol)
            if tick:
                if pos.type == mt5.POSITION_TYPE_BUY:
                    current_price = tick.bid
                else:
                    current_price = tick.ask
                
                # P&L calculation (simplified for XAUUSD: $10 per pip)
                price_diff = current_price - pos.price_open if pos.type == mt5.POSITION_TYPE_BUY else pos.price_open - current_price
                pips = price_diff / 0.01  # For XAUUSD, 1 pip = 0.01
                current_pnl = pips * 10 * pos.volume  # $10 per pip
            else:
                current_price = pos.price_current
                current_pnl = pos.profit
            
            return {
                "ticket": pos.ticket,
                "symbol": pos.symbol,
                "type": "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL",
                "volume": pos.volume,
                "entry_price": pos.price_open,
                "current_price": current_price,
                "sl": pos.sl,
                "tp": pos.tp,
                "profit": pos.profit,
                "current_pnl": current_pnl,
                "magic": pos.magic,
                "comment": pos.comment,
                "time": datetime.fromtimestamp(pos.time).isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get position: {e}")
            return None
    
    def modify_position(
        self,
        ticket: int,
        new_sl: Optional[float] = None,
        new_tp: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Modify position SL/TP.
        
        Args:
            ticket: Position ticket
            new_sl: New stop loss price (None = no change)
            new_tp: New take profit price (None = no change)
        
        Returns:
            Modification result
        """
        try:
            if not self.mt5_initialized:
                return self._error_response("MT5 not initialized")
            
            # Get current position
            position = self.get_position(ticket)
            if not position:
                return self._error_response(f"Position {ticket} not found")
            
            # Use current values if not specified
            sl = new_sl if new_sl is not None else position["sl"]
            tp = new_tp if new_tp is not None else position["tp"]
            
            # Paper trading mode
            if self.paper_trading:
                logger.warning("📄 PAPER TRADING MODE - Modification simulated")
                return {
                    "success": True,
                    "paper_trading": True,
                    "ticket": ticket,
                    "new_sl": sl,
                    "new_tp": tp,
                    "timestamp": datetime.now().isoformat()
                }
            
            # Prepare modification request
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "symbol": self.symbol,
                "sl": sl,
                "tp": tp,
                "position": ticket
            }
            
            logger.info(
                f"🔧 Modifying position {ticket}: "
                f"SL: {position['sl']:.2f} → {sl:.2f} | "
                f"TP: {position['tp']:.2f} → {tp:.2f}"
            )
            
            # Send modification
            result = mt5.order_send(request)
            
            if result is None:
                return self._error_response("order_send returned None")
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                error_msg = f"Modification failed: {result.retcode} - {result.comment}"
                logger.error(f"❌ {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "retcode": result.retcode
                }
            
            logger.info(f"✅ Position {ticket} modified successfully")
            
            return {
                "success": True,
                "paper_trading": False,
                "ticket": ticket,
                "new_sl": sl,
                "new_tp": tp,
                "timestamp": datetime.now().isoformat(),
                "retcode": result.retcode
            }
            
        except Exception as e:
            logger.error(f"❌ Position modification failed: {e}")
            return self._error_response(str(e))
    
    def close_position(
        self,
        ticket: int,
        reason: str = "Manual close"
    ) -> Dict[str, Any]:
        """
        Close position at market price.
        
        Args:
            ticket: Position ticket
            reason: Close reason for logging
        
        Returns:
            Close result with final P&L
        """
        try:
            if not self.mt5_initialized:
                return self._error_response("MT5 not initialized")
            
            # Get position
            position = self.get_position(ticket)
            if not position:
                return self._error_response(f"Position {ticket} not found")
            
            # Paper trading mode
            if self.paper_trading:
                logger.warning("📄 PAPER TRADING MODE - Close simulated")
                return {
                    "success": True,
                    "paper_trading": True,
                    "ticket": ticket,
                    "exit_price": position["current_price"],
                    "pnl": position["current_pnl"],
                    "close_reason": reason,
                    "timestamp": datetime.now().isoformat()
                }
            
            # Determine close order type (opposite of position)
            if position["type"] == "BUY":
                order_type = mt5.ORDER_TYPE_SELL
                price = mt5.symbol_info_tick(self.symbol).bid
            else:
                order_type = mt5.ORDER_TYPE_BUY
                price = mt5.symbol_info_tick(self.symbol).ask
            
            # Prepare close request
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": position["volume"],
                "type": order_type,
                "position": ticket,
                "price": price,
                "deviation": self.deviation,
                "magic": self.magic_number,
                "comment": f"Close: {reason[:20]}",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            logger.info(f"🔚 Closing position {ticket} @ {price:.2f} | Reason: {reason}")
            
            # Send close order
            result = mt5.order_send(request)
            
            if result is None:
                return self._error_response("order_send returned None")
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                error_msg = f"Close failed: {result.retcode} - {result.comment}"
                logger.error(f"❌ {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "retcode": result.retcode
                }
            
            # Calculate final P&L
            final_pnl = position["current_pnl"]
            
            logger.info(
                f"✅ Position {ticket} closed successfully | "
                f"Exit: {result.price:.2f} | "
                f"P&L: ${final_pnl:.2f}"
            )
            
            return {
                "success": True,
                "paper_trading": False,
                "ticket": ticket,
                "exit_price": result.price,
                "pnl": final_pnl,
                "close_reason": reason,
                "timestamp": datetime.now().isoformat(),
                "retcode": result.retcode
            }
            
        except Exception as e:
            logger.error(f"❌ Position close failed: {e}")
            return self._error_response(str(e))
    
    def move_to_breakeven(self, ticket: int) -> Dict[str, Any]:
        """
        Move stop loss to breakeven (entry price).
        
        Args:
            ticket: Position ticket
        
        Returns:
            Modification result
        """
        position = self.get_position(ticket)
        if not position:
            return self._error_response(f"Position {ticket} not found")
        
        entry_price = position["entry_price"]
        logger.info(f"🎯 Moving position {ticket} to breakeven: SL → {entry_price:.2f}")
        
        return self.modify_position(ticket, new_sl=entry_price)
    
    def apply_trailing_stop(
        self,
        ticket: int,
        trailing_distance_pips: float
    ) -> Dict[str, Any]:
        """
        Apply trailing stop (distance from current price).
        
        Args:
            ticket: Position ticket
            trailing_distance_pips: Distance in pips
        
        Returns:
            Modification result
        """
        position = self.get_position(ticket)
        if not position:
            return self._error_response(f"Position {ticket} not found")
        
        current_price = position["current_price"]
        distance = trailing_distance_pips * 0.01  # Convert pips to price
        
        if position["type"] == "BUY":
            new_sl = current_price - distance
        else:
            new_sl = current_price + distance
        
        logger.info(
            f"📌 Applying trailing stop to position {ticket}: "
            f"{trailing_distance_pips:.1f} pips → SL: {new_sl:.2f}"
        )
        
        return self.modify_position(ticket, new_sl=new_sl)
    
    def _error_response(self, error: str) -> Dict[str, Any]:
        """Generate error response"""
        return {
            "success": False,
            "error": error,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_info(self) -> Dict[str, Any]:
        """Get agent information"""
        return {
            "name": self.name,
            "version": self.version,
            "type": "execution",
            "description": "Handles order placement and position monitoring via MT5 Python API",
            "capabilities": [
                "Place market orders (BUY/SELL)",
                "Monitor open positions",
                "Modify SL/TP levels",
                "Close positions",
                "Move to breakeven",
                "Apply trailing stop",
                "Paper trading mode"
            ],
            "config": {
                "symbol": self.symbol,
                "magic_number": self.magic_number,
                "deviation": self.deviation,
                "paper_trading": self.paper_trading,
                "mt5_initialized": self.mt5_initialized
            }
        }
    
    def shutdown(self):
        """Shutdown MT5 connection"""
        if self.mt5_initialized:
            mt5.shutdown()
            self.mt5_initialized = False
            logger.info("MT5 connection closed")


# ========== STANDALONE TESTING ==========

if __name__ == "__main__":
    logger.info("Testing ExecutionAgent...")
    
    # Initialize agent (paper trading mode)
    agent = ExecutionAgent(
        symbol="XAUUSD",
        enable_paper_trading=True  # Safe testing
    )
    
    # Get info
    info = agent.get_info()
    logger.info(f"Agent: {info['name']} v{info['version']}")
    logger.info(f"Paper trading: {info['config']['paper_trading']}")
    
    logger.info("\n" + "=" * 60)
    logger.info("TEST: Place BUY Order (Paper Trading)")
    logger.info("=" * 60)
    
    # Place order
    result = agent.place_order(
        signal="BUY",
        lot_size=0.28,
        sl_price=2366.5,
        tp_price=2406.5,
        comment="Test order"
    )
    
    logger.info(f"Success: {result['success']}")
    if result['success']:
        logger.info(f"Ticket: {result['ticket']}")
        logger.info(f"Entry: {result['entry_price']:.2f}")
        logger.info(f"Paper trading: {result.get('paper_trading', False)}")
    
    # Shutdown
    agent.shutdown()
    logger.info("\n✅ ExecutionAgent test complete!")
