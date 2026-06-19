"""
State Machine Agent - Trading State & Position Lifecycle Management

This agent manages the trading system's state transitions and position lifecycle:
1. State transitions (IDLE → ANALYZING → WAITING → TRADING → CLOSED)
2. Position tracking (entry, SL/TP updates, exit)
3. State persistence (JSON file storage)
4. State history logging
5. Recovery mechanisms

States:
- IDLE: No active position, waiting for signals
- ANALYZING: Signal received, orchestrator analyzing
- WAITING: Signal approved, waiting for entry confirmation
- TRADING: Position open, monitoring SL/TP
- CLOSED: Position closed, calculating P&L

The state machine ensures:
- No duplicate positions (one position at a time)
- Proper state transitions (can't skip states)
- State persistence across restarts
- Complete position lifecycle tracking
"""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum
from pathlib import Path
from loguru import logger


class TradingState(Enum):
    """Trading system states"""
    IDLE = "idle"                      # No position, waiting for signals
    ANALYZING = "analyzing"            # Orchestrator analyzing signal
    WAITING = "waiting"                # Signal approved, waiting for entry
    TRADING = "trading"                # Position open, monitoring
    CLOSED = "closed"                  # Position closed, calculating P&L


class StateTransitionError(Exception):
    """Raised when invalid state transition attempted"""
    pass


class StateMachineAgent:
    """
    State Machine Agent - Manages trading system state and position lifecycle.
    
    Purpose:
    - Track current system state (IDLE/ANALYZING/WAITING/TRADING/CLOSED)
    - Enforce valid state transitions
    - Store position details (entry, SL/TP, current P&L)
    - Persist state to disk (survive restarts)
    - Log state history for debugging
    - Prevent duplicate positions
    
    State Transitions:
    IDLE → ANALYZING → WAITING → TRADING → CLOSED → IDLE
    
    Allowed transitions:
    - IDLE → ANALYZING: Signal received from orchestrator
    - ANALYZING → WAITING: Signal approved, ready to trade
    - ANALYZING → IDLE: Signal rejected, back to idle
    - WAITING → TRADING: Position opened successfully
    - WAITING → IDLE: Entry failed/cancelled
    - TRADING → CLOSED: Position closed (TP/SL hit)
    - CLOSED → IDLE: P&L calculated, ready for next trade
    """
    
    def __init__(
        self,
        state_file: str = "signal_state.json",
        max_history: int = 100
    ):
        """
        Initialize State Machine Agent.
        
        Args:
            state_file: Path to JSON file for state persistence
            max_history: Maximum number of state history records to keep
        """
        self.name = "StateMachineAgent"
        self.version = "1.0.0"
        self.state_file = Path(state_file)
        self.max_history = max_history
        
        # Current state
        self.current_state = TradingState.IDLE
        self.state_data: Dict[str, Any] = {}
        self.position_data: Optional[Dict[str, Any]] = None
        self.state_history: List[Dict[str, Any]] = []
        
        # Load persisted state if exists
        self._load_state()
        
        # Valid state transitions
        self.valid_transitions = {
            TradingState.IDLE: [TradingState.ANALYZING],
            TradingState.ANALYZING: [TradingState.WAITING, TradingState.IDLE],
            TradingState.WAITING: [TradingState.TRADING, TradingState.IDLE],
            TradingState.TRADING: [TradingState.CLOSED],
            TradingState.CLOSED: [TradingState.IDLE]
        }
        
        logger.info(
            f"✅ {self.name} v{self.version} initialized | "
            f"Current state: {self.current_state.value} | "
            f"State file: {self.state_file}"
        )
    
    def transition_to(
        self,
        new_state: TradingState,
        state_data: Optional[Dict[str, Any]] = None,
        reason: str = ""
    ) -> Dict[str, Any]:
        """
        Transition to a new state.
        
        Args:
            new_state: Target state
            state_data: Additional data for the new state
            reason: Reason for transition
        
        Returns:
            Transition result with status
        
        Raises:
            StateTransitionError: If transition is invalid
        """
        try:
            # Validate transition
            if new_state not in self.valid_transitions.get(self.current_state, []):
                valid_next = [s.value for s in self.valid_transitions.get(self.current_state, [])]
                raise StateTransitionError(
                    f"Invalid transition: {self.current_state.value} → {new_state.value}. "
                    f"Valid transitions: {valid_next}"
                )
            
            # Store previous state
            previous_state = self.current_state
            transition_time = datetime.now()
            
            # Update state
            self.current_state = new_state
            self.state_data = state_data or {}
            
            # Log transition
            transition_record = {
                "timestamp": transition_time.isoformat(),
                "from_state": previous_state.value,
                "to_state": new_state.value,
                "reason": reason,
                "state_data": self.state_data.copy()
            }
            
            self.state_history.append(transition_record)
            
            # Trim history if needed
            if len(self.state_history) > self.max_history:
                self.state_history = self.state_history[-self.max_history:]
            
            # Persist state
            self._save_state()
            
            logger.info(
                f"🔄 State transition: {previous_state.value} → {new_state.value} | "
                f"Reason: {reason or 'N/A'}"
            )
            
            return {
                "success": True,
                "previous_state": previous_state.value,
                "current_state": new_state.value,
                "transition_time": transition_time.isoformat(),
                "reason": reason
            }
            
        except StateTransitionError as e:
            logger.error(f"❌ State transition failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "current_state": self.current_state.value
            }
    
    def signal_received(self, signal_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle signal received from orchestrator.
        Transition: IDLE → ANALYZING
        
        Args:
            signal_data: Signal details from orchestrator
        
        Returns:
            Transition result
        """
        return self.transition_to(
            TradingState.ANALYZING,
            state_data=signal_data,
            reason="Signal received from orchestrator"
        )
    
    def signal_approved(self, trade_plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle signal approved by orchestrator.
        Transition: ANALYZING → WAITING
        
        Args:
            trade_plan: Trade plan (entry, SL, TP, lot size)
        
        Returns:
            Transition result
        """
        return self.transition_to(
            TradingState.WAITING,
            state_data=trade_plan,
            reason="Signal approved, waiting for entry"
        )
    
    def signal_rejected(self, rejection_reason: str) -> Dict[str, Any]:
        """
        Handle signal rejected by orchestrator.
        Transition: ANALYZING → IDLE
        
        Args:
            rejection_reason: Why signal was rejected
        
        Returns:
            Transition result
        """
        return self.transition_to(
            TradingState.IDLE,
            state_data={},
            reason=f"Signal rejected: {rejection_reason}"
        )
    
    def position_opened(self, position_details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle position opened successfully.
        Transition: WAITING → TRADING
        
        Args:
            position_details: Position info (ticket, entry price, SL/TP, etc.)
        
        Returns:
            Transition result
        """
        self.position_data = {
            **position_details,
            "open_time": datetime.now().isoformat(),
            "status": "OPEN"
        }
        
        return self.transition_to(
            TradingState.TRADING,
            state_data=self.position_data,
            reason="Position opened successfully"
        )
    
    def entry_failed(self, error_reason: str) -> Dict[str, Any]:
        """
        Handle entry failed/cancelled.
        Transition: WAITING → IDLE
        
        Args:
            error_reason: Why entry failed
        
        Returns:
            Transition result
        """
        return self.transition_to(
            TradingState.IDLE,
            state_data={},
            reason=f"Entry failed: {error_reason}"
        )
    
    def position_closed(self, close_details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle position closed (TP/SL hit or manual close).
        Transition: TRADING → CLOSED
        
        Args:
            close_details: Close info (exit price, P&L, close reason)
        
        Returns:
            Transition result
        """
        if self.position_data:
            self.position_data.update({
                **close_details,
                "close_time": datetime.now().isoformat(),
                "status": "CLOSED"
            })
        
        return self.transition_to(
            TradingState.CLOSED,
            state_data=self.position_data or close_details,
            reason=f"Position closed: {close_details.get('close_reason', 'Unknown')}"
        )
    
    def trade_finalized(self) -> Dict[str, Any]:
        """
        Finalize trade after P&L calculation.
        Transition: CLOSED → IDLE
        
        Returns:
            Transition result
        """
        result = self.transition_to(
            TradingState.IDLE,
            state_data={},
            reason="Trade finalized, ready for next signal"
        )
        
        # Clear position data
        self.position_data = None
        
        return result
    
    def update_position(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update current position details (SL/TP changes, current P&L).
        
        Args:
            updates: Position updates
        
        Returns:
            Updated position data
        """
        if self.current_state != TradingState.TRADING:
            logger.warning(
                f"⚠️ Cannot update position in state: {self.current_state.value}"
            )
            return {
                "success": False,
                "error": f"Not in TRADING state (current: {self.current_state.value})"
            }
        
        if not self.position_data:
            logger.warning("⚠️ No position data to update")
            return {
                "success": False,
                "error": "No active position"
            }
        
        # Update position data
        self.position_data.update(updates)
        self.position_data["last_update"] = datetime.now().isoformat()
        
        # Update state data
        self.state_data = self.position_data.copy()
        
        # Persist
        self._save_state()
        
        logger.info(f"📝 Position updated: {list(updates.keys())}")
        
        return {
            "success": True,
            "position_data": self.position_data
        }
    
    def get_current_state(self) -> Dict[str, Any]:
        """Get current state information"""
        return {
            "agent": self.name,
            "version": self.version,
            "timestamp": datetime.now().isoformat(),
            "current_state": self.current_state.value,
            "state_data": self.state_data.copy(),
            "position_data": self.position_data.copy() if self.position_data else None,
            "has_active_position": self.current_state in [TradingState.WAITING, TradingState.TRADING],
            "state_history_count": len(self.state_history)
        }
    
    def get_state_history(self, last_n: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get state history.
        
        Args:
            last_n: Number of most recent records (None = all)
        
        Returns:
            List of state transition records
        """
        if last_n:
            return self.state_history[-last_n:]
        return self.state_history.copy()
    
    def can_accept_signal(self) -> bool:
        """Check if system can accept new signal (must be in IDLE state)"""
        return self.current_state == TradingState.IDLE
    
    def reset_to_idle(self, reason: str = "Manual reset") -> Dict[str, Any]:
        """
        Force reset to IDLE state (emergency use only).
        
        Args:
            reason: Reason for reset
        
        Returns:
            Reset result
        """
        logger.warning(f"⚠️ Force reset to IDLE: {reason}")
        
        previous_state = self.current_state
        self.current_state = TradingState.IDLE
        self.state_data = {}
        self.position_data = None
        
        # Log reset
        reset_record = {
            "timestamp": datetime.now().isoformat(),
            "from_state": previous_state.value,
            "to_state": TradingState.IDLE.value,
            "reason": f"FORCE RESET: {reason}",
            "state_data": {}
        }
        self.state_history.append(reset_record)
        
        # Persist
        self._save_state()
        
        return {
            "success": True,
            "previous_state": previous_state.value,
            "current_state": TradingState.IDLE.value,
            "reason": reason
        }
    
    def _save_state(self):
        """Persist current state to JSON file"""
        try:
            state_snapshot = {
                "current_state": self.current_state.value,
                "state_data": self.state_data,
                "position_data": self.position_data,
                "last_update": datetime.now().isoformat(),
                "history": self.state_history[-20:]  # Save last 20 transitions
            }
            
            with open(self.state_file, 'w') as f:
                json.dump(state_snapshot, f, indent=2)
            
            logger.debug(f"💾 State saved to {self.state_file}")
            
        except Exception as e:
            logger.error(f"❌ Failed to save state: {e}")
    
    def _load_state(self):
        """Load persisted state from JSON file"""
        try:
            if not self.state_file.exists():
                logger.info("No existing state file, starting fresh")
                return
            
            with open(self.state_file, 'r') as f:
                state_snapshot = json.load(f)
            
            # Restore state
            self.current_state = TradingState(state_snapshot.get("current_state", "idle"))
            self.state_data = state_snapshot.get("state_data", {})
            self.position_data = state_snapshot.get("position_data")
            self.state_history = state_snapshot.get("history", [])
            
            logger.info(
                f"📂 State loaded from {self.state_file} | "
                f"State: {self.current_state.value}"
            )
            
        except Exception as e:
            logger.error(f"❌ Failed to load state: {e} | Starting fresh")
            self.current_state = TradingState.IDLE
            self.state_data = {}
            self.position_data = None
            self.state_history = []
    
    def get_info(self) -> Dict[str, Any]:
        """Get agent information"""
        return {
            "name": self.name,
            "version": self.version,
            "type": "state_machine",
            "description": "Manages trading system state and position lifecycle",
            "capabilities": [
                "State transition management (5 states)",
                "Position lifecycle tracking",
                "State persistence (JSON)",
                "State history logging",
                "Invalid transition prevention",
                "Emergency reset"
            ],
            "states": [state.value for state in TradingState],
            "current_state": self.current_state.value,
            "has_active_position": self.current_state in [TradingState.WAITING, TradingState.TRADING],
            "state_file": str(self.state_file),
            "history_count": len(self.state_history),
            "valid_transitions": {
                k.value: [v.value for v in vals] 
                for k, vals in self.valid_transitions.items()
            }
        }


# ========== STANDALONE TESTING ==========

if __name__ == "__main__":
    logger.info("Testing StateMachineAgent...")
    
    # Initialize agent
    agent = StateMachineAgent(state_file="test_state.json")
    
    # Get info
    info = agent.get_info()
    logger.info(f"Agent: {info['name']} v{info['version']}")
    logger.info(f"Current state: {info['current_state']}")
    logger.info(f"States: {info['states']}")
    
    logger.info("\n" + "=" * 60)
    logger.info("TEST: Complete Trade Lifecycle")
    logger.info("=" * 60)
    
    # 1. Signal received
    logger.info("\n1. Signal received from orchestrator")
    result = agent.signal_received({
        "signal": "BUY",
        "symbol": "XAUUSD",
        "confidence": 0.85,
        "orchestrator_decision": "approved"
    })
    logger.info(f"   Result: {result['success']} | State: {result.get('current_state')}")
    
    # 2. Signal approved
    logger.info("\n2. Signal approved, ready to trade")
    result = agent.signal_approved({
        "signal": "BUY",
        "entry_price": 2380.0,
        "sl_price": 2366.5,
        "tp_price": 2406.5,
        "lot_size": 0.28
    })
    logger.info(f"   Result: {result['success']} | State: {result.get('current_state')}")
    
    # 3. Position opened
    logger.info("\n3. Position opened successfully")
    result = agent.position_opened({
        "ticket": 123456789,
        "entry_price": 2380.0,
        "sl_price": 2366.5,
        "tp_price": 2406.5,
        "lot_size": 0.28,
        "symbol": "XAUUSD",
        "direction": "BUY"
    })
    logger.info(f"   Result: {result['success']} | State: {result.get('current_state')}")
    
    # 4. Update position (current P&L)
    logger.info("\n4. Update position (current P&L)")
    result = agent.update_position({
        "current_price": 2390.0,
        "current_pnl": 100.0
    })
    logger.info(f"   Result: {result['success']}")
    
    # 5. Position closed (TP hit)
    logger.info("\n5. Position closed (TP hit)")
    result = agent.position_closed({
        "exit_price": 2406.5,
        "pnl": 265.0,
        "close_reason": "TP_HIT"
    })
    logger.info(f"   Result: {result['success']} | State: {result.get('current_state')}")
    
    # 6. Trade finalized
    logger.info("\n6. Trade finalized")
    result = agent.trade_finalized()
    logger.info(f"   Result: {result['success']} | State: {result.get('current_state')}")
    
    # Get state history
    logger.info("\n" + "=" * 60)
    logger.info("STATE HISTORY")
    logger.info("=" * 60)
    history = agent.get_state_history(last_n=10)
    for i, record in enumerate(history, 1):
        logger.info(
            f"{i}. {record['from_state']} → {record['to_state']} | "
            f"{record['reason']}"
        )
    
    # Test invalid transition
    logger.info("\n" + "=" * 60)
    logger.info("TEST: Invalid Transition")
    logger.info("=" * 60)
    logger.info("Attempting IDLE → TRADING (should fail)")
    result = agent.transition_to(TradingState.TRADING, reason="Invalid test")
    logger.info(f"   Result: {result['success']} | Error: {result.get('error', 'N/A')}")
    
    logger.info("\n✅ StateMachineAgent test complete!")
