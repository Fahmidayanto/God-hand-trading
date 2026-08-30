"""
Main Trading System - Real-time Multi-Agent Trading

This is the main entry point for the autonomous trading system.
It coordinates all components:
1. Market data fetching (MT5 Python API)
2. Signal generation (Orchestrator Agent)
3. State management (State Machine Agent)
4. Order execution (Execution Agent)
5. Position monitoring (continuous loop)

Usage:
    python -m valuecell.trading_system --mode paper
    python -m valuecell.trading_system --mode live

Sprint 4 (2026-07-10):
- Tier 4 #16: Decision audit log. Every orchestrator decision is written to
  ``logs/decisions_<symbol>_<timeframe>.db`` (SQLite); closed positions
  have realized PnL attached. Best-effort writer — failure disables
  logging silently without affecting the trading cycle.
- Tier 4 #17: Source attribution piggy-backed on the audit log. Each
  headline in the news feed carries a ``source`` tag; the DecisionLogger
  exposes ``get_source_stats()`` for per-source PnL/win-rate aggregation.
"""

import time
import MetaTrader5 as mt5
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from loguru import logger
import signal
import sys

from valuecell.agents.orchestrator_agent import OrchestratorAgent
from valuecell.agents.state_machine_agent import StateMachineAgent
from valuecell.execution.execution_agent import ExecutionAgent
from valuecell.adapters.mt5.mt5_adapter import MT5Adapter
from valuecell.adapters.news.news_feed import NewsFeed
from valuecell.adapters.calendar.economic_calendar import get_upcoming_events_naive
from valuecell.adapters.db.decision_log import DecisionLogger
from valuecell.safety.circuit_breaker import CircuitBreaker
from valuecell.safety.notifier import Notifier


class TradingSystem:
    """
    Main Trading System - Coordinates all components.
    
    Features:
    - Real-time market data fetching
    - Bar close detection
    - Multi-agent signal generation
    - State management
    - Order execution
    - Position monitoring
    - Automatic SL/TP updates
    - Error recovery
    """
    
    def __init__(
        self,
        symbol: str = "XAUUSD",
        timeframe: str = "M15",
        mode: str = "paper",
        check_interval: int = 5,
        enable_news_feed: bool = True,
        news_feed_ttl_minutes: int = 10,
        news_feed_query: str = "gold XAUUSD market news today safe haven dollar fed",
        sentiment_shadow_mode: bool = True,
        decision_log_enabled: bool = True,
        decision_log_path: Optional[str] = None,
    ):
        """
        Initialize Trading System.

        Args:
            symbol: Trading symbol
            timeframe: Timeframe for analysis (M15, H1, etc.)
            mode: "paper" or "live" trading
            check_interval: Check interval in seconds
            enable_news_feed: Wire NewsAgent's web_search into market_data so the
                SentimentAgent actually sees headlines. Sprint 1 default: ON.
            news_feed_ttl_minutes: How long to cache fetched news. Default 10
                minutes — keeps the polling loop from hammering Perplexity/Gemini.
            news_feed_query: Search query passed to the underlying provider.
                Default tuned for XAUUSD; override per-symbol as needed.
            sentiment_shadow_mode: When True (default for Sprint 1), the
                SentimentAgent records what it WOULD do but does not veto or
                adjust the upstream signal. Set False to enable real
                sentiment-driven filtering in production.
            decision_log_enabled: When True (default), every orchestrator
                decision is logged to a SQLite DB; closed positions have
                their realized PnL attached. Sprint 4 #16. Set False to
                disable (e.g. for benchmark runs that want zero side-effects).
            decision_log_path: Override the SQLite DB path. Default
                ``logs/decisions_<symbol>_<timeframe>.db`` next to the
                trading-state JSON.
        """
        self.name = "TradingSystem"
        self.version = "1.2.0-sprint4"
        self.symbol = symbol
        self.timeframe = timeframe
        self.mode = mode
        self.check_interval = check_interval
        self.running = False
        self.enable_news_feed = enable_news_feed
        self.sentiment_shadow_mode = sentiment_shadow_mode

        # Convert timeframe to MT5 constant
        self.mt5_timeframe = self._get_mt5_timeframe(timeframe)

        # Initialize components
        logger.info(f"🚀 Initializing {self.name} v{self.version}")
        logger.info(f"   Symbol: {symbol}")
        logger.info(f"   Timeframe: {timeframe}")
        logger.info(f"   Mode: {mode.upper()}")
        logger.info(f"   Check interval: {check_interval}s")
        logger.info(f"   News feed: {'ON' if enable_news_feed else 'OFF'} (ttl={news_feed_ttl_minutes}m)")
        logger.info(f"   Sentiment shadow mode: {'ON' if sentiment_shadow_mode else 'OFF'}")

        # Initialize MT5 adapter
        self.mt5_adapter = MT5Adapter()
        if not self.mt5_adapter.initialize():
            raise RuntimeError("Failed to initialize MT5 adapter")

        # Initialize State Machine
        self.state_machine = StateMachineAgent(
            state_file=f"trading_state_{symbol}_{timeframe}.json"
        )

        # Initialize News Feed (lazy — if import fails we fall back to empty
        # headlines and the SentimentAgent still does its thing on events only)
        self.news_feed: Optional[NewsFeed] = None
        if enable_news_feed:
            try:
                self.news_feed = NewsFeed(
                    query=news_feed_query,
                    ttl_minutes=news_feed_ttl_minutes,
                )
            except Exception as e:
                logger.warning(f"NewsFeed init failed, continuing without news: {e}")

        # Initialize Orchestrator (Sprint 1: pass shadow_mode to SentimentAgent)
        self.orchestrator = OrchestratorAgent(
            enable_llm_msa=True,
            consensus_threshold=0.60,
            market_structure={"swing_length": 5, "timeframe": timeframe},
            risk_management={"account_balance": 10000.0},  # TODO: Get from MT5
            sentiment={"shadow_mode": sentiment_shadow_mode},
            llm_msa={
                "provider": "suniesis",
                "timeout_seconds": 20.0,
                "suniesis_model_timeout_seconds": 15.0,
            },
        )

        # Initialize Execution Agent
        self.execution = ExecutionAgent(
            symbol=symbol,
            enable_paper_trading=(mode == "paper")
        )

        # Initialize Circuit Breaker
        self.circuit_breaker = CircuitBreaker(
            max_consecutive_losses=3,
            max_daily_loss_pct=5.0,
            max_failed_orders=5,
            max_system_errors=3,
            cooldown_minutes=60,
            account_balance=10000.0  # TODO: Get from MT5
        )

        # Initialize Notifier
        self.notifier = Notifier(telegram_enabled=True)

        # Initialize Decision Audit Log (Sprint 4 #16)
        # ponytail: best-effort writer. If it fails to open, sets
        # enabled=False internally and the trading cycle proceeds
        # unchanged. No try/except needed at the call site.
        log_path = decision_log_path or f"logs/decisions_{symbol}_{timeframe}.db"
        self.decision_log = DecisionLogger(
            db_path=log_path,
            enabled=decision_log_enabled,
        )

        # ticket -> decision_id map so we can attach outcome PnL on close
        # (Sprint 4 #16). In-memory only — a process restart will leave
        # earlier tickets unattributed, which is acceptable for measurement.
        self._decision_by_ticket: Dict[int, int] = {}

        # State tracking
        self.last_bar_time = None
        self.current_position_ticket = None

        logger.info("✅ All components initialized successfully")
    
    def _get_mt5_timeframe(self, timeframe: str) -> int:
        """Convert timeframe string to MT5 constant"""
        timeframe_map = {
            "M1": mt5.TIMEFRAME_M1,
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1
        }
        return timeframe_map.get(timeframe, mt5.TIMEFRAME_M15)
    
    def start(self):
        """Start the trading system"""
        logger.info("=" * 70)
        logger.info("🚀 STARTING TRADING SYSTEM")
        logger.info("=" * 70)
        logger.info("")
        
        self.running = True
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        try:
            # Main loop
            while self.running:
                self._trading_cycle()
                time.sleep(self.check_interval)
                
        except Exception as e:
            logger.error(f"❌ Fatal error in trading system: {e}")
            self.stop()
        
        logger.info("Trading system stopped")
    
    def _trading_cycle(self):
        """Execute one trading cycle"""
        try:
            # 1. Check for new bar
            new_bar = self._check_new_bar()
            
            # 2. Monitor existing position (if any)
            if self.current_position_ticket:
                self._monitor_position()
            
            # 3. Generate signal on new bar (if no position)
            if new_bar and not self.current_position_ticket:
                if self.state_machine.can_accept_signal():
                    self._process_new_signal()
            
        except Exception as e:
            logger.error(f"❌ Error in trading cycle: {e}")
            self.circuit_breaker.record_system_error(str(e))
            self.notifier.notify_system_error(str(e), "trading_cycle")
    
    def _check_new_bar(self) -> bool:
        """
        Check if new bar has formed.
        
        Returns:
            True if new bar detected
        """
        try:
            # Get latest bar
            rates = mt5.copy_rates_from_pos(self.symbol, self.mt5_timeframe, 0, 1)
            
            if rates is None or len(rates) == 0:
                return False
            
            bar_time = datetime.fromtimestamp(rates[0]['time'])
            
            # First run
            if self.last_bar_time is None:
                self.last_bar_time = bar_time
                logger.info(f"📊 Initialized at bar: {bar_time.strftime('%Y-%m-%d %H:%M')}")
                return False
            
            # Check if new bar
            if bar_time > self.last_bar_time:
                logger.info(f"🆕 New {self.timeframe} bar: {bar_time.strftime('%Y-%m-%d %H:%M')}")
                self.last_bar_time = bar_time
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Error checking new bar: {e}")
            return False
    
    def _process_new_signal(self):
        """Process new bar and generate trading signal"""
        try:
            # Check circuit breaker FIRST
            circuit_check = self.circuit_breaker.check_before_trade()
            if not circuit_check['allowed']:
                logger.warning(f"⚠️ Circuit breaker: {circuit_check['reason']}")
                self.notifier.notify_circuit_breaker_opened(
                    breaker_type=self.circuit_breaker.opened_by.value if self.circuit_breaker.opened_by else "unknown",
                    reason=circuit_check['reason'],
                    cooldown_minutes=circuit_check.get('cooldown_minutes', 60)
                )
                return
            
            logger.info("🔍 Analyzing market for trading signal...")
            
            # Transition to ANALYZING state
            self.state_machine.signal_received({
                "timestamp": datetime.now().isoformat(),
                "bar_time": self.last_bar_time.isoformat()
            })
            
            # Fetch market data
            market_data = self._fetch_market_data()
            if not market_data:
                logger.warning("Failed to fetch market data")
                self.state_machine.signal_rejected("Failed to fetch market data")
                self.circuit_breaker.record_system_error("Failed to fetch market data")
                return
            
            # Run orchestrator
            result = self.orchestrator.analyze(
                market_data=market_data,
                symbol=self.symbol,
                timeframe=self.timeframe
            )

            logger.info(
                f"📊 Orchestrator result: {result['final_signal']} | "
                f"Confidence: {result['final_confidence']:.3f} | "
                f"Consensus: {result['consensus_level']}"
            )

            # === Sprint 4 #16: log this decision ===
            # Pull market_structure as the "upstream" (entry-point) signal,
            # fall back to final_signal if unavailable (e.g. error path).
            # Attach market_data so DecisionLogger can mine news + sources.
            ms_result = (result.get("agent_results") or {}).get("market_structure") or {}
            upstream_signal = ms_result.get("signal", result.get("final_signal", "HOLD"))
            upstream_confidence = ms_result.get(
                "confidence", result.get("final_confidence", 0.0)
            )
            audit_result = dict(result)
            audit_result["market_data"] = market_data  # so DecisionLogger sees news+ts
            decision_id = self.decision_log.log_decision(
                symbol=self.symbol,
                mode=self.mode,
                timeframe=self.timeframe,
                bar_time=self.last_bar_time,
                upstream_signal=upstream_signal,
                upstream_confidence=upstream_confidence,
                orchestrator_result=audit_result,
            )
            
            # Check if approved
            if not result['approved'] or result['final_signal'] not in ["BUY", "SELL"]:
                logger.info(f"❌ Signal rejected: {result['reasoning']}")
                self.state_machine.signal_rejected(result['reasoning'])
                
                # Notify rejection
                self.notifier.notify_signal_rejected(
                    signal=result['final_signal'],
                    reason=result['reasoning'],
                    confidence=result['final_confidence']
                )
                return
            
            # Signal approved!
            logger.info(f"✅ Signal APPROVED: {result['final_signal']}")
            
            # Transition to WAITING state
            trade_plan = {
                "signal": result['final_signal'],
                "confidence": result['final_confidence'],
                "entry_price": market_data['current_bar']['close'],
                "sl_price": result['sl_tp']['sl_price'],
                "tp_price": result['sl_tp']['tp_price'],
                "lot_size": result['position_sizing']['lot_size'],
                "decision_id": decision_id,  # Sprint 4 #16: link to audit row
            }
            
            self.state_machine.signal_approved(trade_plan)
            
            # Execute trade
            self._execute_trade(trade_plan)
            
        except Exception as e:
            logger.error(f"❌ Error processing signal: {e}")
            self.state_machine.signal_rejected(f"Error: {str(e)}")
            self.circuit_breaker.record_system_error(str(e))
            self.notifier.notify_system_error(str(e), "process_new_signal")
    
    def _fetch_market_data(self) -> Optional[Dict[str, Any]]:
        """Fetch market data for analysis"""
        try:
            # Get M15 data (150 bars)
            m15_rates = mt5.copy_rates_from_pos(self.symbol, self.mt5_timeframe, 0, 150)
            if m15_rates is None or len(m15_rates) == 0:
                return None

            # Convert to DataFrame
            import pandas as pd
            df = pd.DataFrame(m15_rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')

            # Rename tick_volume to volume (required by agents)
            if 'tick_volume' in df.columns:
                df['volume'] = df['tick_volume']

            # Calculate EMA200
            df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()

            # Get current bar
            current_bar = {
                "time": df.iloc[-1]['time'],
                "open": float(df.iloc[-1]['open']),
                "high": float(df.iloc[-1]['high']),
                "low": float(df.iloc[-1]['low']),
                "close": float(df.iloc[-1]['close']),
                "volume": int(df.iloc[-1]['tick_volume'])
            }

            # Calculate ATR (simple)
            df['high_low'] = df['high'] - df['low']
            atr = df['high_low'].tail(14).mean()

            # Get session
            hour = datetime.now().hour
            if 7 <= hour < 16:
                session = "London"
            elif 13 <= hour < 22:
                session = "NewYork"
            elif 0 <= hour < 9:
                session = "Asia"
            else:
                session = "Sydney"

            # === Sprint 1: News feed ===
            # NewsFeed is cached so this is a no-op on most calls; first call
            # per TTL window hits the upstream provider. Never raises into the
            # trading cycle — empty list is fine for SentimentAgent.
            news_headlines: list = []
            if self.news_feed is not None:
                try:
                    news_headlines = self.news_feed.fetch_sync()
                except Exception as e:
                    logger.warning(f"NewsFeed.fetch_sync failed: {e}")
                    news_headlines = []

            # === Sprint 2: Economic calendar ===
            # stdlib-only; in-process cache (1h TTL); FOMC + NFP/CPI/GDP/JC.
            try:
                upcoming_events = get_upcoming_events_naive(hours_ahead=24)
            except Exception as e:
                logger.warning(f"Economic calendar fetch failed: {e}")
                upcoming_events = []

            return {
                "df": df,
                "current_bar": current_bar,
                "structure_events": [],  # TODO: Get from market structure detector
                "m15_history": df,
                "atr": atr,
                "session": session,
                "news_headlines": news_headlines,
                "upcoming_events": upcoming_events,
            }

        except Exception as e:
            logger.error(f"❌ Error fetching market data: {e}")
            return None

    def _execute_trade(self, trade_plan: Dict[str, Any]):
        """Execute trade via Execution Agent"""
        try:
            logger.info(f"📤 Executing {trade_plan['signal']} order...")
            
            result = self.execution.place_order(
                signal=trade_plan['signal'],
                lot_size=trade_plan['lot_size'],
                sl_price=trade_plan['sl_price'],
                tp_price=trade_plan['tp_price'],
                comment=f"Orch {trade_plan['confidence']:.2f}"
            )
            
            if not result['success']:
                logger.error(f"❌ Order failed: {result.get('error', 'Unknown')}")
                self.state_machine.entry_failed(result.get('error', 'Unknown'))
                
                # Record failed order
                self.circuit_breaker.record_failed_order(result.get('error', 'Unknown'))
                self.notifier.notify_system_error(
                    error=f"Order failed: {result.get('error', 'Unknown')}",
                    context="execute_trade"
                )
                return
            
            # Order success!
            logger.info(f"✅ Order executed! Ticket: {result['ticket']}")

            # Sprint 4 #16: link audit row to the live ticket so we can
            # attach realized PnL when the position closes.
            decision_id = trade_plan.get("decision_id")
            if decision_id is not None:
                self._decision_by_ticket[result['ticket']] = int(decision_id)

            # Transition to TRADING state
            self.state_machine.position_opened({
                "ticket": result['ticket'],
                "signal": trade_plan['signal'],
                "entry_price": result['entry_price'],
                "sl_price": trade_plan['sl_price'],
                "tp_price": trade_plan['tp_price'],
                "lot_size": trade_plan['lot_size']
            })
            
            # Track position
            self.current_position_ticket = result['ticket']
            
            # Notify trade opened
            self.notifier.notify_trade_opened(
                signal=trade_plan['signal'],
                ticket=result['ticket'],
                entry_price=result['entry_price'],
                lot_size=trade_plan['lot_size'],
                sl_price=trade_plan['sl_price'],
                tp_price=trade_plan['tp_price'],
                confidence=trade_plan['confidence']
            )
            
        except Exception as e:
            logger.error(f"❌ Error executing trade: {e}")
            self.state_machine.entry_failed(str(e))
            self.circuit_breaker.record_system_error(str(e))
            self.notifier.notify_system_error(str(e), "execute_trade")
    
    def _monitor_position(self):
        """Monitor current open position"""
        try:
            # Get position
            position = self.execution.get_position(self.current_position_ticket)
            
            if not position:
                # Position closed (TP/SL hit)
                logger.info(f"🔚 Position {self.current_position_ticket} closed")

                # Sprint 7 #16 close-out: fetch real realized PnL from
                # MT5 history deals. If MT5 doesn't know about this ticket
                # (paper trading, pre-init, or older than 14d window)
                # we silently fall back to 0.0 — the audit row still
                # lands, just without a number. exit_price is still a TODO
                # since the audit log only needs realized PnL.
                realized = self.execution.get_closed_position_pnl(
                    self.current_position_ticket
                )
                pnl = float(realized) if realized is not None else 0.0
                exit_price = 0.0
                close_reason = "TP/SL hit" if realized is not None else "closed (PnL unknown)"

                # Get signal from state machine
                state_data = self.state_machine.get_current_state()
                signal = state_data.get('context', {}).get('signal', 'UNKNOWN')
                entry_price = state_data.get('context', {}).get('entry_price', 0.0)

                # Sprint 4 #16: attach realized PnL to the audit row, then
                # forget the ticket. pnl=0.0 is acceptable for now — the
                # audit row is still useful (tells us the position closed).
                decision_id = self._decision_by_ticket.pop(
                    self.current_position_ticket, None
                )
                if decision_id is not None:
                    self.decision_log.record_outcome(
                        decision_id=decision_id,
                        pnl=pnl,
                        ticket=self.current_position_ticket,
                    )

                # Record trade result in circuit breaker
                self.circuit_breaker.record_trade_result(pnl)
                
                # Notify trade closed
                self.notifier.notify_trade_closed(
                    ticket=self.current_position_ticket,
                    signal=signal,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    pnl=pnl,
                    close_reason=close_reason
                )
                
                # Update state machine
                self.state_machine.position_closed({
                    "exit_price": exit_price,
                    "pnl": pnl,
                    "close_reason": close_reason
                })
                
                self.state_machine.trade_finalized()
                self.current_position_ticket = None
                return
            
            # Update state machine with current position
            self.state_machine.update_position({
                "current_price": position['current_price'],
                "current_pnl": position['current_pnl']
            })
            
            # Log position status (every 5 checks = 25s)
            if not hasattr(self, '_position_check_count'):
                self._position_check_count = 0
            
            self._position_check_count += 1
            
            if self._position_check_count % 5 == 0:
                logger.info(
                    f"📊 Position #{self.current_position_ticket} | "
                    f"Price: {position['current_price']:.2f} | "
                    f"P&L: ${position['current_pnl']:.2f}"
                )
            
            # TODO: Implement trailing stop logic
            # TODO: Implement breakeven logic
            
        except Exception as e:
            logger.error(f"❌ Error monitoring position: {e}")
            self.circuit_breaker.record_system_error(str(e))
            self.notifier.notify_system_error(str(e), "monitor_position")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.warning("\n⚠️  Shutdown signal received, stopping trading system...")
        self.stop()
    
    def stop(self):
        """Stop the trading system gracefully"""
        logger.info("🛑 Stopping trading system...")
        self.running = False
        
        # Close any open positions (optional, commented for safety)
        # if self.current_position_ticket:
        #     logger.warning(f"⚠️  Open position detected: {self.current_position_ticket}")
        #     logger.warning("   Position will remain open (manual close required)")
        
        # Shutdown components
        if hasattr(self, 'execution'):
            self.execution.shutdown()
        
        logger.info("✅ Trading system stopped successfully")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current system status"""
        state = self.state_machine.get_current_state()
        
        return {
            "system": self.name,
            "version": self.version,
            "running": self.running,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "mode": self.mode,
            "current_state": state['current_state'],
            "has_position": self.current_position_ticket is not None,
            "position_ticket": self.current_position_ticket,
            "last_bar_time": self.last_bar_time.isoformat() if self.last_bar_time else None
        }


# ========== MAIN ENTRY POINT ==========

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Multi-Agent Trading System")
    parser.add_argument(
        "--mode",
        choices=["paper", "live"],
        default="paper",
        help="Trading mode (paper or live)"
    )
    parser.add_argument(
        "--symbol",
        default="XAUUSD",
        help="Trading symbol (default: XAUUSD)"
    )
    parser.add_argument(
        "--timeframe",
        choices=["M1", "M5", "M15", "M30", "H1", "H4", "D1"],
        default="M15",
        help="Timeframe (default: M15)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Check interval in seconds (default: 5)"
    )
    
    args = parser.parse_args()
    
    # Configure logger
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:8}</level> | <level>{message}</level>",
        level="INFO"
    )
    logger.add(
        f"logs/trading_system_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:8} | {message}",
        level="DEBUG",
        rotation="1 day"
    )
    
    # Warning for live mode
    if args.mode == "live":
        logger.warning("=" * 70)
        logger.warning("⚠️  LIVE TRADING MODE ENABLED")
        logger.warning("⚠️  REAL MONEY WILL BE AT RISK!")
        logger.warning("=" * 70)
        response = input("\nType 'YES' to confirm live trading: ")
        if response != "YES":
            logger.info("Live trading cancelled")
            return
    
    # Initialize and start system
    try:
        system = TradingSystem(
            symbol=args.symbol,
            timeframe=args.timeframe,
            mode=args.mode,
            check_interval=args.interval
        )
        
        system.start()
        
    except KeyboardInterrupt:
        logger.info("\n⚠️  Keyboard interrupt received")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
    finally:
        logger.info("Goodbye! 👋")


if __name__ == "__main__":
    main()
