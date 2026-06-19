"""
Test State Machine Agent

This script tests the State Machine Agent with:
1. Complete trade lifecycle (IDLE → ANALYZING → WAITING → TRADING → CLOSED → IDLE)
2. Invalid transition prevention
3. State persistence (save/load)
4. Position tracking
5. State history logging
6. Emergency reset
"""

import sys
import os
from pathlib import Path

# Add python directory to path
project_root = Path(__file__).parent.parent
python_dir = project_root / "python"
sys.path.insert(0, str(python_dir))

import json
from datetime import datetime
from loguru import logger

from valuecell.agents.state_machine_agent import StateMachineAgent, TradingState, StateTransitionError


def test_agent_info():
    """Test agent info retrieval"""
    logger.info("=" * 70)
    logger.info("TEST 1: AGENT INFO")
    logger.info("=" * 70)
    
    agent = StateMachineAgent(state_file="test_state_1.json")
    info = agent.get_info()
    
    logger.info(f"Name: {info['name']}")
    logger.info(f"Version: {info['version']}")
    logger.info(f"Type: {info['type']}")
    logger.info(f"Description: {info['description']}")
    logger.info("")
    logger.info("States:")
    for state in info['states']:
        logger.info(f"  - {state}")
    logger.info("")
    logger.info(f"Current State: {info['current_state']}")
    logger.info(f"Has Active Position: {info['has_active_position']}")
    logger.info("")
    logger.info("Valid Transitions:")
    for from_state, to_states in info['valid_transitions'].items():
        logger.info(f"  {from_state} → {to_states}")
    logger.info("")


def test_complete_trade_lifecycle():
    """Test complete trade lifecycle (happy path)"""
    logger.info("=" * 70)
    logger.info("TEST 2: COMPLETE TRADE LIFECYCLE")
    logger.info("=" * 70)
    
    agent = StateMachineAgent(state_file="test_state_2.json")
    
    # 1. IDLE → ANALYZING (signal received)
    logger.info("\nStep 1: Signal received (IDLE → ANALYZING)")
    result = agent.signal_received({
        "signal": "BUY",
        "symbol": "XAUUSD",
        "confidence": 0.85,
        "source": "orchestrator"
    })
    assert result['success'], "Signal received should succeed"
    assert result['current_state'] == "analyzing", "Should be in ANALYZING state"
    logger.info(f"   ✅ {result['previous_state']} → {result['current_state']}")
    
    # 2. ANALYZING → WAITING (signal approved)
    logger.info("\nStep 2: Signal approved (ANALYZING → WAITING)")
    result = agent.signal_approved({
        "signal": "BUY",
        "entry_price": 2380.0,
        "sl_price": 2366.5,
        "tp_price": 2406.5,
        "lot_size": 0.28
    })
    assert result['success'], "Signal approval should succeed"
    assert result['current_state'] == "waiting", "Should be in WAITING state"
    logger.info(f"   ✅ {result['previous_state']} → {result['current_state']}")
    
    # 3. WAITING → TRADING (position opened)
    logger.info("\nStep 3: Position opened (WAITING → TRADING)")
    result = agent.position_opened({
        "ticket": 123456789,
        "entry_price": 2380.0,
        "sl_price": 2366.5,
        "tp_price": 2406.5,
        "lot_size": 0.28,
        "symbol": "XAUUSD",
        "direction": "BUY"
    })
    assert result['success'], "Position open should succeed"
    assert result['current_state'] == "trading", "Should be in TRADING state"
    logger.info(f"   ✅ {result['previous_state']} → {result['current_state']}")
    
    # 4. Update position (still TRADING)
    logger.info("\nStep 4: Update position (current P&L)")
    result = agent.update_position({
        "current_price": 2390.0,
        "current_pnl": 100.0
    })
    assert result['success'], "Position update should succeed"
    logger.info(f"   ✅ Position updated: P&L = $100.0")
    
    # 5. TRADING → CLOSED (position closed)
    logger.info("\nStep 5: Position closed (TRADING → CLOSED)")
    result = agent.position_closed({
        "exit_price": 2406.5,
        "pnl": 265.0,
        "close_reason": "TP_HIT"
    })
    assert result['success'], "Position close should succeed"
    assert result['current_state'] == "closed", "Should be in CLOSED state"
    logger.info(f"   ✅ {result['previous_state']} → {result['current_state']}")
    
    # 6. CLOSED → IDLE (trade finalized)
    logger.info("\nStep 6: Trade finalized (CLOSED → IDLE)")
    result = agent.trade_finalized()
    assert result['success'], "Trade finalization should succeed"
    assert result['current_state'] == "idle", "Should be back in IDLE state"
    logger.info(f"   ✅ {result['previous_state']} → {result['current_state']}")
    
    logger.info("")
    logger.info("✅ Complete lifecycle test passed!")
    logger.info("")


def test_signal_rejection_flow():
    """Test signal rejection flow"""
    logger.info("=" * 70)
    logger.info("TEST 3: SIGNAL REJECTION FLOW")
    logger.info("=" * 70)
    
    agent = StateMachineAgent(state_file="test_state_3.json")
    
    # Signal received
    logger.info("\nStep 1: Signal received (IDLE → ANALYZING)")
    result = agent.signal_received({
        "signal": "SELL",
        "symbol": "XAUUSD",
        "confidence": 0.45
    })
    assert result['success'], "Signal received should succeed"
    logger.info(f"   ✅ {result['previous_state']} → {result['current_state']}")
    
    # Signal rejected (low consensus)
    logger.info("\nStep 2: Signal rejected (ANALYZING → IDLE)")
    result = agent.signal_rejected("Low consensus (45%)")
    assert result['success'], "Signal rejection should succeed"
    assert result['current_state'] == "idle", "Should be back in IDLE state"
    logger.info(f"   ✅ {result['previous_state']} → {result['current_state']}")
    
    logger.info("")
    logger.info("✅ Signal rejection test passed!")
    logger.info("")


def test_entry_failure_flow():
    """Test entry failure flow"""
    logger.info("=" * 70)
    logger.info("TEST 4: ENTRY FAILURE FLOW")
    logger.info("=" * 70)
    
    agent = StateMachineAgent(state_file="test_state_4.json")
    
    # Get to WAITING state
    agent.signal_received({"signal": "BUY", "symbol": "XAUUSD"})
    agent.signal_approved({"entry_price": 2380.0, "lot_size": 0.28})
    
    logger.info(f"Current state: {agent.current_state.value}")
    
    # Entry fails
    logger.info("\nEntry failed (WAITING → IDLE)")
    result = agent.entry_failed("Insufficient margin")
    assert result['success'], "Entry failure should succeed"
    assert result['current_state'] == "idle", "Should be back in IDLE state"
    logger.info(f"   ✅ {result['previous_state']} → {result['current_state']}")
    
    logger.info("")
    logger.info("✅ Entry failure test passed!")
    logger.info("")


def test_invalid_transitions():
    """Test that invalid transitions are prevented"""
    logger.info("=" * 70)
    logger.info("TEST 5: INVALID TRANSITION PREVENTION")
    logger.info("=" * 70)
    
    agent = StateMachineAgent(state_file="test_state_5.json")
    
    # Test 1: IDLE → TRADING (should fail)
    logger.info("\nTest 1: IDLE → TRADING (should fail)")
    result = agent.transition_to(TradingState.TRADING, reason="Invalid test")
    assert not result['success'], "Invalid transition should fail"
    assert "error" in result, "Should contain error message"
    logger.info(f"   ✅ Correctly blocked: {result['error'][:60]}...")
    
    # Test 2: IDLE → CLOSED (should fail)
    logger.info("\nTest 2: IDLE → CLOSED (should fail)")
    result = agent.transition_to(TradingState.CLOSED, reason="Invalid test")
    assert not result['success'], "Invalid transition should fail"
    logger.info(f"   ✅ Correctly blocked: {result['error'][:60]}...")
    
    # Test 3: Get to TRADING, try to go back to ANALYZING (should fail)
    agent.signal_received({"signal": "BUY"})
    agent.signal_approved({"entry_price": 2380.0})
    agent.position_opened({"ticket": 123, "entry_price": 2380.0})
    
    logger.info("\nTest 3: TRADING → ANALYZING (should fail)")
    result = agent.transition_to(TradingState.ANALYZING, reason="Invalid test")
    assert not result['success'], "Invalid transition should fail"
    logger.info(f"   ✅ Correctly blocked: {result['error'][:60]}...")
    
    logger.info("")
    logger.info("✅ Invalid transition prevention test passed!")
    logger.info("")


def test_state_persistence():
    """Test state save/load persistence"""
    logger.info("=" * 70)
    logger.info("TEST 6: STATE PERSISTENCE (SAVE/LOAD)")
    logger.info("=" * 70)
    
    state_file = "test_state_persistence.json"
    
    # Create agent and advance to TRADING state
    logger.info("\nPhase 1: Create agent and open position")
    agent1 = StateMachineAgent(state_file=state_file)
    agent1.signal_received({"signal": "BUY", "symbol": "XAUUSD"})
    agent1.signal_approved({"entry_price": 2380.0, "sl_price": 2366.5, "tp_price": 2406.5})
    agent1.position_opened({
        "ticket": 999888777,
        "entry_price": 2380.0,
        "lot_size": 0.50,
        "symbol": "XAUUSD"
    })
    
    state1 = agent1.get_current_state()
    logger.info(f"   Agent 1 state: {state1['current_state']}")
    logger.info(f"   Position ticket: {state1['position_data']['ticket']}")
    
    # Create new agent (should load saved state)
    logger.info("\nPhase 2: Create new agent (should load saved state)")
    agent2 = StateMachineAgent(state_file=state_file)
    
    state2 = agent2.get_current_state()
    logger.info(f"   Agent 2 state: {state2['current_state']}")
    logger.info(f"   Position ticket: {state2['position_data']['ticket']}")
    
    # Verify state was loaded correctly
    assert state2['current_state'] == "trading", "State should be TRADING"
    assert state2['position_data']['ticket'] == 999888777, "Position data should match"
    assert state2['position_data']['entry_price'] == 2380.0, "Entry price should match"
    
    logger.info("")
    logger.info("✅ State persistence test passed!")
    logger.info("")


def test_state_history():
    """Test state history logging"""
    logger.info("=" * 70)
    logger.info("TEST 7: STATE HISTORY LOGGING")
    logger.info("=" * 70)
    
    agent = StateMachineAgent(state_file="test_state_7.json")
    
    # Execute several transitions
    agent.signal_received({"signal": "BUY"})
    agent.signal_approved({"entry_price": 2380.0})
    agent.position_opened({"ticket": 111, "entry_price": 2380.0})
    agent.position_closed({"exit_price": 2406.5, "pnl": 265.0, "close_reason": "TP_HIT"})
    agent.trade_finalized()
    
    # Get history
    history = agent.get_state_history()
    logger.info(f"\nTotal transitions: {len(history)}")
    logger.info("\nTransition History:")
    for i, record in enumerate(history, 1):
        logger.info(
            f"   {i}. {record['from_state']:10} → {record['to_state']:10} | "
            f"{record['reason'][:40]}"
        )
    
    assert len(history) == 5, "Should have 5 transitions"
    assert history[0]['from_state'] == "idle", "First transition should start from IDLE"
    assert history[-1]['to_state'] == "idle", "Last transition should end at IDLE"
    
    logger.info("")
    logger.info("✅ State history test passed!")
    logger.info("")


def test_can_accept_signal():
    """Test can_accept_signal() method"""
    logger.info("=" * 70)
    logger.info("TEST 8: CAN ACCEPT SIGNAL CHECK")
    logger.info("=" * 70)
    
    agent = StateMachineAgent(state_file="test_state_8.json")
    
    # Test 1: IDLE state (should accept)
    logger.info("\nTest 1: IDLE state")
    can_accept = agent.can_accept_signal()
    logger.info(f"   Can accept signal: {can_accept}")
    assert can_accept, "Should accept signal in IDLE state"
    
    # Test 2: ANALYZING state (should not accept)
    agent.signal_received({"signal": "BUY"})
    logger.info("\nTest 2: ANALYZING state")
    can_accept = agent.can_accept_signal()
    logger.info(f"   Can accept signal: {can_accept}")
    assert not can_accept, "Should not accept signal in ANALYZING state"
    
    # Test 3: TRADING state (should not accept)
    agent.signal_approved({"entry_price": 2380.0})
    agent.position_opened({"ticket": 222, "entry_price": 2380.0})
    logger.info("\nTest 3: TRADING state")
    can_accept = agent.can_accept_signal()
    logger.info(f"   Can accept signal: {can_accept}")
    assert not can_accept, "Should not accept signal in TRADING state"
    
    logger.info("")
    logger.info("✅ Can accept signal test passed!")
    logger.info("")


def test_emergency_reset():
    """Test emergency reset to IDLE"""
    logger.info("=" * 70)
    logger.info("TEST 9: EMERGENCY RESET")
    logger.info("=" * 70)
    
    agent = StateMachineAgent(state_file="test_state_9.json")
    
    # Get to TRADING state
    agent.signal_received({"signal": "BUY"})
    agent.signal_approved({"entry_price": 2380.0})
    agent.position_opened({"ticket": 333, "entry_price": 2380.0})
    
    logger.info(f"\nBefore reset: {agent.current_state.value}")
    assert agent.current_state == TradingState.TRADING, "Should be in TRADING state"
    
    # Emergency reset
    logger.info("\nExecuting emergency reset...")
    result = agent.reset_to_idle("System crash recovery")
    
    logger.info(f"After reset: {result['current_state']}")
    assert result['success'], "Reset should succeed"
    assert result['current_state'] == "idle", "Should be in IDLE state"
    assert agent.position_data is None, "Position data should be cleared"
    
    logger.info("")
    logger.info("✅ Emergency reset test passed!")
    logger.info("")


def test_position_updates():
    """Test position update tracking"""
    logger.info("=" * 70)
    logger.info("TEST 10: POSITION UPDATE TRACKING")
    logger.info("=" * 70)
    
    agent = StateMachineAgent(state_file="test_state_10.json")
    
    # Get to TRADING state
    agent.signal_received({"signal": "BUY"})
    agent.signal_approved({"entry_price": 2380.0})
    agent.position_opened({
        "ticket": 444,
        "entry_price": 2380.0,
        "sl_price": 2366.5,
        "tp_price": 2406.5
    })
    
    # Update 1: Current P&L
    logger.info("\nUpdate 1: Current price and P&L")
    result = agent.update_position({
        "current_price": 2385.0,
        "current_pnl": 50.0
    })
    assert result['success'], "Update should succeed"
    logger.info(f"   ✅ P&L: ${result['position_data']['current_pnl']}")
    
    # Update 2: SL moved to breakeven
    logger.info("\nUpdate 2: Move SL to breakeven")
    result = agent.update_position({
        "sl_price": 2380.0,
        "current_price": 2395.0,
        "current_pnl": 150.0
    })
    assert result['success'], "Update should succeed"
    logger.info(f"   ✅ New SL: {result['position_data']['sl_price']}")
    
    # Update 3: Trailing stop
    logger.info("\nUpdate 3: Trailing stop")
    result = agent.update_position({
        "sl_price": 2390.0,
        "current_price": 2400.0,
        "current_pnl": 200.0
    })
    assert result['success'], "Update should succeed"
    logger.info(f"   ✅ New SL: {result['position_data']['sl_price']} (trailing)")
    
    # Check state is still TRADING
    state = agent.get_current_state()
    assert state['current_state'] == "trading", "Should still be in TRADING state"
    
    logger.info("")
    logger.info("✅ Position update test passed!")
    logger.info("")


def test_all_scenarios():
    """Run all test scenarios"""
    logger.info("🚀 STARTING STATE MACHINE AGENT TESTS")
    logger.info("=" * 70)
    logger.info("")
    
    # Run all tests
    test_agent_info()
    test_complete_trade_lifecycle()
    test_signal_rejection_flow()
    test_entry_failure_flow()
    test_invalid_transitions()
    test_state_persistence()
    test_state_history()
    test_can_accept_signal()
    test_emergency_reset()
    test_position_updates()
    
    # Summary
    logger.info("=" * 70)
    logger.info("📊 TEST SUMMARY")
    logger.info("=" * 70)
    logger.info("")
    logger.info("✅ All test categories completed:")
    logger.info("   1. Agent Info - PASS")
    logger.info("   2. Complete Trade Lifecycle - PASS")
    logger.info("   3. Signal Rejection Flow - PASS")
    logger.info("   4. Entry Failure Flow - PASS")
    logger.info("   5. Invalid Transition Prevention - PASS")
    logger.info("   6. State Persistence (Save/Load) - PASS")
    logger.info("   7. State History Logging - PASS")
    logger.info("   8. Can Accept Signal Check - PASS")
    logger.info("   9. Emergency Reset - PASS")
    logger.info("   10. Position Update Tracking - PASS")
    logger.info("")
    logger.info("✅ ALL TESTS COMPLETE!")
    logger.info("")


if __name__ == "__main__":
    # Configure logger
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:8}</level> | <level>{message}</level>",
        level="INFO"
    )
    
    # Run all tests
    test_all_scenarios()
