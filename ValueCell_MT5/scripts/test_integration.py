"""
Integration Test Suite - End-to-End System Testing

Tests complete trading workflow:
1. MT5 connection and data fetching
2. Market structure detection
3. Agent orchestration
4. Signal generation
5. Order execution (paper mode)
6. Position monitoring
7. Safety mechanisms
8. Notifications

Usage:
    python scripts/test_integration.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'python'))

from loguru import logger
import MetaTrader5 as mt5
from datetime import datetime
import time

# Import components
from valuecell.adapters.mt5.mt5_adapter import MT5Adapter
from valuecell.agents.orchestrator_agent import OrchestratorAgent
from valuecell.agents.state_machine_agent import StateMachineAgent
from valuecell.execution.execution_agent import ExecutionAgent
from valuecell.safety.circuit_breaker import CircuitBreaker
from valuecell.safety.notifier import Notifier


class IntegrationTester:
    """
    Integration Test Suite - Tests complete system workflow
    """
    
    def __init__(self):
        self.name = "IntegrationTester"
        self.version = "1.0.0"
        self.tests_passed = 0
        self.tests_failed = 0
        self.test_results = []
        
        logger.info(f"🧪 {self.name} v{self.version} initialized")
    
    def run_test(self, test_name: str, test_func):
        """Run a single test"""
        logger.info(f"\n{'='*70}")
        logger.info(f"TEST: {test_name}")
        logger.info(f"{'='*70}")
        
        try:
            test_func()
            self.tests_passed += 1
            self.test_results.append({"name": test_name, "status": "✅ PASS"})
            logger.info(f"✅ {test_name} - PASSED")
        except Exception as e:
            self.tests_failed += 1
            self.test_results.append({"name": test_name, "status": f"❌ FAIL: {e}"})
            logger.error(f"❌ {test_name} - FAILED: {e}")
    
    def test_mt5_connection(self):
        """Test 1: MT5 connection and data fetching"""
        logger.info("Testing MT5 connection...")
        
        adapter = MT5Adapter()
        assert adapter.initialize(), "Failed to initialize MT5"
        
        # Test data fetching
        rates = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_M15, 0, 10)
        assert rates is not None, "Failed to fetch M15 data"
        assert len(rates) > 0, "No data returned"
        
        logger.info(f"✅ Fetched {len(rates)} M15 bars")
        
        adapter.shutdown()
    
    def test_market_structure_detection(self):
        """Test 2: Market structure detection"""
        logger.info("Testing market structure detection...")
        
        adapter = MT5Adapter()
        adapter.initialize()
        
        # Fetch data
        rates = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_M15, 0, 150)
        assert rates is not None, "Failed to fetch data"
        
        # Convert to DataFrame
        import pandas as pd
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        # Calculate EMA200
        df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
        
        assert 'ema200' in df.columns, "EMA200 not calculated"
        assert not df['ema200'].isna().all(), "EMA200 is all NaN"
        
        logger.info(f"✅ Market structure data prepared: {len(df)} bars")
        
        adapter.shutdown()
    
    def test_orchestrator_analysis(self):
        """Test 3: Orchestrator agent analysis"""
        logger.info("Testing orchestrator analysis...")
        
        # Initialize orchestrator
        orchestrator = OrchestratorAgent(
            consensus_threshold=0.60,
            market_structure={"swing_length": 5, "timeframe": "M15"},
            risk_management={"account_balance": 10000.0}
        )
        
        # Create mock market data
        import pandas as pd
        mock_data = {
            "df": pd.DataFrame({
                'time': [datetime.now()],
                'open': [2350.0],
                'high': [2355.0],
                'low': [2348.0],
                'close': [2352.0],
                'tick_volume': [1000],
                'ema200': [2340.0]
            }),
            "current_bar": {
                "time": datetime.now(),
                "open": 2350.0,
                "high": 2355.0,
                "low": 2348.0,
                "close": 2352.0,
                "volume": 1000
            },
            "structure_events": [],
            "atr": 8.5,
            "session": "London",
            "news_headlines": [],
            "upcoming_events": []
        }
        
        # Run analysis
        result = orchestrator.analyze(
            market_data=mock_data,
            symbol="XAUUSD",
            timeframe="M15"
        )
        
        assert "final_signal" in result, "No final_signal in result"
        assert "final_confidence" in result, "No final_confidence in result"
        assert "approved" in result, "No approved in result"
        
        logger.info(f"✅ Orchestrator result: {result['final_signal']} "
                   f"(confidence: {result['final_confidence']:.2f})")
    
    def test_state_machine(self):
        """Test 4: State machine transitions"""
        logger.info("Testing state machine...")
        
        state_machine = StateMachineAgent(
            state_file="test_state_machine.json"
        )
        
        # Test transitions
        initial_state = state_machine.get_current_state()
        assert initial_state['current_state'] == "IDLE", "Initial state not IDLE"
        
        # Signal received
        state_machine.signal_received({"test": "data"})
        state = state_machine.get_current_state()
        assert state['current_state'] == "ANALYZING", "State not ANALYZING after signal"
        
        # Signal approved
        state_machine.signal_approved({"signal": "BUY"})
        state = state_machine.get_current_state()
        assert state['current_state'] == "WAITING", "State not WAITING after approval"
        
        # Position opened
        state_machine.position_opened({"ticket": 12345})
        state = state_machine.get_current_state()
        assert state['current_state'] == "TRADING", "State not TRADING after open"
        
        # Position closed
        state_machine.position_closed({"pnl": 100})
        state = state_machine.get_current_state()
        assert state['current_state'] == "CLOSED", "State not CLOSED after close"
        
        # Finalize
        state_machine.trade_finalized()
        state = state_machine.get_current_state()
        assert state['current_state'] == "IDLE", "State not IDLE after finalize"
        
        logger.info("✅ All state transitions working correctly")
        
        # Cleanup
        import os
        if os.path.exists("test_state_machine.json"):
            os.remove("test_state_machine.json")
    
    def test_execution_agent_paper(self):
        """Test 5: Execution agent (paper mode)"""
        logger.info("Testing execution agent in paper mode...")
        
        execution = ExecutionAgent(
            symbol="XAUUSD",
            enable_paper_trading=True
        )
        
        # Test paper order
        result = execution.place_order(
            signal="BUY",
            lot_size=0.01,
            sl_price=2340.0,
            tp_price=2360.0,
            comment="Integration Test"
        )
        
        assert result['success'], "Paper order failed"
        assert 'ticket' in result, "No ticket in result"
        assert result['ticket'] > 0, "Invalid ticket number"
        
        logger.info(f"✅ Paper order executed: Ticket #{result['ticket']}")
        
        # Test position retrieval
        position = execution.get_position(result['ticket'])
        assert position is not None, "Position not found"
        assert position['ticket'] == result['ticket'], "Ticket mismatch"
        
        logger.info(f"✅ Position retrieved: P&L ${position['current_pnl']:.2f}")
        
        # Test position close
        close_result = execution.close_position(result['ticket'])
        assert close_result['success'], "Failed to close position"
        
        logger.info("✅ Position closed successfully")
        
        execution.shutdown()
    
    def test_circuit_breaker(self):
        """Test 6: Circuit breaker functionality"""
        logger.info("Testing circuit breaker...")
        
        cb = CircuitBreaker(
            max_consecutive_losses=3,
            max_daily_loss_pct=5.0,
            account_balance=10000.0,
            cooldown_minutes=1
        )
        
        # Test normal operation
        check = cb.check_before_trade()
        assert check['allowed'], "Circuit breaker blocking normal operation"
        logger.info("✅ Normal operation allowed")
        
        # Test consecutive losses
        cb.record_trade_result(-100)
        cb.record_trade_result(-100)
        cb.record_trade_result(-100)  # 3rd loss
        
        check = cb.check_before_trade()
        assert not check['allowed'], "Circuit breaker not blocking after 3 losses"
        logger.info("✅ Circuit breaker opened after 3 consecutive losses")
        
        # Test manual reset
        reset_result = cb.manual_reset()
        assert reset_result['success'], "Manual reset failed"
        
        check = cb.check_before_trade()
        assert check['allowed'], "Circuit breaker still blocking after reset"
        logger.info("✅ Manual reset working")
    
    def test_notifier(self):
        """Test 7: Notifier functionality"""
        logger.info("Testing notifier...")
        
        notifier = Notifier(telegram_enabled=False)  # Disable Telegram for test
        
        # Test various notifications (will log only)
        notifier.notify_trade_opened(
            signal="BUY",
            ticket=12345,
            entry_price=2350.0,
            lot_size=0.01,
            sl_price=2340.0,
            tp_price=2360.0,
            confidence=0.85
        )
        logger.info("✅ Trade opened notification sent")
        
        notifier.notify_trade_closed(
            ticket=12345,
            signal="BUY",
            entry_price=2350.0,
            exit_price=2360.0,
            pnl=100.0,
            close_reason="TP hit"
        )
        logger.info("✅ Trade closed notification sent")
        
        notifier.notify_signal_rejected(
            signal="SELL",
            reason="Low confidence",
            confidence=0.45
        )
        logger.info("✅ Signal rejected notification sent")
        
        info = notifier.get_info()
        assert info['name'] == "Notifier", "Notifier info incorrect"
        logger.info("✅ Notifier info retrieved")
    
    def test_integration_workflow(self):
        """Test 8: Complete integration workflow"""
        logger.info("Testing complete integration workflow...")
        
        # 1. Initialize all components
        logger.info("Step 1: Initializing components...")
        adapter = MT5Adapter()
        assert adapter.initialize(), "MT5 initialization failed"
        
        orchestrator = OrchestratorAgent(
            consensus_threshold=0.60,
            market_structure={"swing_length": 5, "timeframe": "M15"},
            risk_management={"account_balance": 10000.0}
        )
        
        state_machine = StateMachineAgent(
            state_file="test_workflow_state.json"
        )
        
        execution = ExecutionAgent(
            symbol="XAUUSD",
            enable_paper_trading=True
        )
        
        circuit_breaker = CircuitBreaker(
            max_consecutive_losses=3,
            max_daily_loss_pct=5.0,
            account_balance=10000.0
        )
        
        notifier = Notifier(telegram_enabled=False)
        
        logger.info("✅ All components initialized")
        
        # 2. Check circuit breaker
        logger.info("Step 2: Checking circuit breaker...")
        cb_check = circuit_breaker.check_before_trade()
        assert cb_check['allowed'], "Circuit breaker blocking"
        logger.info("✅ Circuit breaker allows trading")
        
        # 3. Fetch market data
        logger.info("Step 3: Fetching market data...")
        rates = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_M15, 0, 150)
        assert rates is not None, "Failed to fetch data"
        
        import pandas as pd
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
        
        current_bar = {
            "time": df.iloc[-1]['time'],
            "open": float(df.iloc[-1]['open']),
            "high": float(df.iloc[-1]['high']),
            "low": float(df.iloc[-1]['low']),
            "close": float(df.iloc[-1]['close']),
            "volume": int(df.iloc[-1]['tick_volume'])
        }
        
        market_data = {
            "df": df,
            "current_bar": current_bar,
            "structure_events": [],
            "atr": 8.5,
            "session": "London",
            "news_headlines": [],
            "upcoming_events": []
        }
        logger.info("✅ Market data fetched")
        
        # 4. State machine: Signal received
        logger.info("Step 4: Processing signal...")
        state_machine.signal_received({"timestamp": datetime.now().isoformat()})
        assert state_machine.get_current_state()['current_state'] == "ANALYZING"
        logger.info("✅ State: ANALYZING")
        
        # 5. Run orchestrator
        logger.info("Step 5: Running orchestrator analysis...")
        result = orchestrator.analyze(
            market_data=market_data,
            symbol="XAUUSD",
            timeframe="M15"
        )
        logger.info(f"✅ Orchestrator result: {result['final_signal']} "
                   f"(confidence: {result['final_confidence']:.2f})")
        
        # 6. If approved, execute
        if result['approved'] and result['final_signal'] in ["BUY", "SELL"]:
            logger.info("Step 6: Signal approved, executing trade...")
            
            # State machine: Signal approved
            trade_plan = {
                "signal": result['final_signal'],
                "confidence": result['final_confidence'],
                "sl_price": result['sl_tp']['sl_price'],
                "tp_price": result['sl_tp']['tp_price'],
                "lot_size": result['position_sizing']['lot_size']
            }
            state_machine.signal_approved(trade_plan)
            assert state_machine.get_current_state()['current_state'] == "WAITING"
            logger.info("✅ State: WAITING")
            
            # Execute order
            order_result = execution.place_order(
                signal=trade_plan['signal'],
                lot_size=trade_plan['lot_size'],
                sl_price=trade_plan['sl_price'],
                tp_price=trade_plan['tp_price'],
                comment="Integration Test"
            )
            
            assert order_result['success'], "Order execution failed"
            logger.info(f"✅ Order executed: Ticket #{order_result['ticket']}")
            
            # Notify
            notifier.notify_trade_opened(
                signal=trade_plan['signal'],
                ticket=order_result['ticket'],
                entry_price=order_result['entry_price'],
                lot_size=trade_plan['lot_size'],
                sl_price=trade_plan['sl_price'],
                tp_price=trade_plan['tp_price'],
                confidence=trade_plan['confidence']
            )
            
            # State machine: Position opened
            state_machine.position_opened({
                "ticket": order_result['ticket'],
                "signal": trade_plan['signal']
            })
            assert state_machine.get_current_state()['current_state'] == "TRADING"
            logger.info("✅ State: TRADING")
            
            # Simulate position monitoring
            logger.info("Step 7: Monitoring position...")
            time.sleep(1)
            position = execution.get_position(order_result['ticket'])
            assert position is not None, "Position not found"
            logger.info(f"✅ Position monitored: P&L ${position['current_pnl']:.2f}")
            
            # Close position
            logger.info("Step 8: Closing position...")
            close_result = execution.close_position(order_result['ticket'])
            assert close_result['success'], "Failed to close position"
            
            # Record result in circuit breaker
            pnl = position['current_pnl']
            circuit_breaker.record_trade_result(pnl)
            logger.info(f"✅ Trade result recorded: ${pnl:.2f}")
            
            # Notify
            notifier.notify_trade_closed(
                ticket=order_result['ticket'],
                signal=trade_plan['signal'],
                entry_price=order_result['entry_price'],
                exit_price=close_result.get('exit_price', 0),
                pnl=pnl,
                close_reason="Manual close"
            )
            
            # State machine: Position closed
            state_machine.position_closed({"pnl": pnl})
            assert state_machine.get_current_state()['current_state'] == "CLOSED"
            logger.info("✅ State: CLOSED")
            
            # State machine: Finalize
            state_machine.trade_finalized()
            assert state_machine.get_current_state()['current_state'] == "IDLE"
            logger.info("✅ State: IDLE")
            
        else:
            logger.info("Signal rejected by orchestrator")
            state_machine.signal_rejected(result['reasoning'])
            notifier.notify_signal_rejected(
                signal=result['final_signal'],
                reason=result['reasoning'],
                confidence=result['final_confidence']
            )
        
        # Cleanup
        adapter.shutdown()
        execution.shutdown()
        import os
        if os.path.exists("test_workflow_state.json"):
            os.remove("test_workflow_state.json")
        
        logger.info("✅ Complete workflow test passed!")
    
    def run_all_tests(self):
        """Run all integration tests"""
        logger.info("\n" + "="*70)
        logger.info("🧪 INTEGRATION TEST SUITE - START")
        logger.info("="*70)
        
        # Run tests
        self.run_test("1. MT5 Connection", self.test_mt5_connection)
        self.run_test("2. Market Structure Detection", self.test_market_structure_detection)
        self.run_test("3. Orchestrator Analysis", self.test_orchestrator_analysis)
        self.run_test("4. State Machine", self.test_state_machine)
        self.run_test("5. Execution Agent (Paper)", self.test_execution_agent_paper)
        self.run_test("6. Circuit Breaker", self.test_circuit_breaker)
        self.run_test("7. Notifier", self.test_notifier)
        self.run_test("8. Complete Integration Workflow", self.test_integration_workflow)
        
        # Print summary
        self.print_summary()
    
    def print_summary(self):
        """Print test summary"""
        logger.info("\n" + "="*70)
        logger.info("📊 TEST SUMMARY")
        logger.info("="*70)
        
        total = self.tests_passed + self.tests_failed
        pass_rate = (self.tests_passed / total * 100) if total > 0 else 0
        
        for result in self.test_results:
            logger.info(f"{result['status']} - {result['name']}")
        
        logger.info("\n" + "="*70)
        logger.info(f"Total Tests: {total}")
        logger.info(f"✅ Passed: {self.tests_passed}")
        logger.info(f"❌ Failed: {self.tests_failed}")
        logger.info(f"Pass Rate: {pass_rate:.1f}%")
        logger.info("="*70)
        
        if self.tests_failed == 0:
            logger.info("🎉 ALL TESTS PASSED!")
        else:
            logger.warning(f"⚠️ {self.tests_failed} TEST(S) FAILED")


# ========== MAIN ENTRY POINT ==========

if __name__ == "__main__":
    # Configure logger
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:8}</level> | <level>{message}</level>",
        level="INFO"
    )
    
    # Run tests
    tester = IntegrationTester()
    tester.run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if tester.tests_failed == 0 else 1)
