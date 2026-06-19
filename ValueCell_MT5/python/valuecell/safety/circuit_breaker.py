"""
Circuit Breaker - Safety Mechanism for Trading System

Implements circuit breaker pattern to protect against:
1. Consecutive losses (max 3 losses in a row)
2. Daily loss limit (max 5% of account)
3. Excessive failed orders (max 5 failures)
4. System errors (max 3 errors)

When circuit breaker opens:
- All trading is blocked
- System remains in monitoring mode
- Manual reset required or auto-reset after cooldown
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from enum import Enum
from loguru import logger


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Trading blocked
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreakerType(Enum):
    """Types of circuit breakers"""
    CONSECUTIVE_LOSSES = "consecutive_losses"
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    FAILED_ORDERS = "failed_orders"
    SYSTEM_ERRORS = "system_errors"


class CircuitBreaker:
    """
    Circuit Breaker - Protects trading system from catastrophic failures.
    
    Features:
    - Multiple circuit types
    - Automatic state management
    - Cooldown period
    - Manual reset capability
    - Detailed logging
    """
    
    def __init__(
        self,
        max_consecutive_losses: int = 3,
        max_daily_loss_pct: float = 5.0,
        max_failed_orders: int = 5,
        max_system_errors: int = 3,
        cooldown_minutes: int = 60,
        account_balance: float = 10000.0
    ):
        """
        Initialize Circuit Breaker.
        
        Args:
            max_consecutive_losses: Max consecutive losing trades
            max_daily_loss_pct: Max daily loss percentage
            max_failed_orders: Max failed order attempts
            max_system_errors: Max system errors
            cooldown_minutes: Cooldown period before auto-reset
            account_balance: Account balance for loss calculations
        """
        self.name = "CircuitBreaker"
        self.version = "1.0.0"
        
        # Configuration
        self.max_consecutive_losses = max_consecutive_losses
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_failed_orders = max_failed_orders
        self.max_system_errors = max_system_errors
        self.cooldown_minutes = cooldown_minutes
        self.account_balance = account_balance
        
        # State tracking
        self.state = CircuitState.CLOSED
        self.opened_at: Optional[datetime] = None
        self.opened_by: Optional[CircuitBreakerType] = None
        self.opened_reason: str = ""
        
        # Counters
        self.consecutive_losses = 0
        self.daily_loss_usd = 0.0
        self.failed_orders = 0
        self.system_errors = 0
        self.last_reset_date = datetime.now().date()
        
        # History
        self.trip_history: list = []
        
        logger.info(
            f"✅ {self.name} v{self.version} initialized | "
            f"Max losses: {max_consecutive_losses} | "
            f"Daily limit: {max_daily_loss_pct}% | "
            f"Cooldown: {cooldown_minutes}min"
        )
    
    def check_before_trade(self) -> Dict[str, Any]:
        """
        Check if trading is allowed.
        
        Returns:
            Dict with allowed status and reason
        """
        # Reset daily counters if new day
        self._check_daily_reset()
        
        # Check circuit state
        if self.state == CircuitState.OPEN:
            # Check if cooldown expired
            if self._check_cooldown():
                logger.info("⏰ Cooldown expired, moving to HALF_OPEN")
                self.state = CircuitState.HALF_OPEN
            else:
                remaining = self._get_remaining_cooldown()
                return {
                    "allowed": False,
                    "state": self.state.value,
                    "reason": f"Circuit breaker OPEN: {self.opened_reason}",
                    "opened_at": self.opened_at.isoformat() if self.opened_at else None,
                    "cooldown_remaining_minutes": remaining
                }
        
        # Check all circuit conditions
        checks = [
            self._check_consecutive_losses(),
            self._check_daily_loss_limit(),
            self._check_failed_orders(),
            self._check_system_errors()
        ]
        
        # If any check fails, open circuit
        for check in checks:
            if not check["passed"]:
                self._open_circuit(check["type"], check["reason"])
                return {
                    "allowed": False,
                    "state": self.state.value,
                    "reason": check["reason"],
                    "opened_at": self.opened_at.isoformat(),
                    "cooldown_minutes": self.cooldown_minutes
                }
        
        return {
            "allowed": True,
            "state": self.state.value,
            "consecutive_losses": self.consecutive_losses,
            "daily_loss_usd": self.daily_loss_usd,
            "daily_loss_pct": (self.daily_loss_usd / self.account_balance) * 100
        }
    
    def record_trade_result(self, pnl: float):
        """
        Record trade result and update counters.
        
        Args:
            pnl: Profit/Loss in USD
        """
        # Update daily loss
        if pnl < 0:
            self.daily_loss_usd += abs(pnl)
        
        # Update consecutive losses
        if pnl < 0:
            self.consecutive_losses += 1
            logger.warning(f"⚠️ Consecutive losses: {self.consecutive_losses}/{self.max_consecutive_losses}")
        else:
            # Reset on win
            if self.consecutive_losses > 0:
                logger.info(f"✅ Win! Resetting consecutive losses (was {self.consecutive_losses})")
            self.consecutive_losses = 0
        
        # Check if half-open and successful
        if self.state == CircuitState.HALF_OPEN and pnl > 0:
            logger.info("✅ Successful trade in HALF_OPEN state, closing circuit")
            self.close_circuit()
    
    def record_failed_order(self, reason: str):
        """Record failed order attempt"""
        self.failed_orders += 1
        logger.warning(f"⚠️ Failed order: {self.failed_orders}/{self.max_failed_orders} | Reason: {reason}")
    
    def record_system_error(self, error: str):
        """Record system error"""
        self.system_errors += 1
        logger.error(f"❌ System error: {self.system_errors}/{self.max_system_errors} | Error: {error}")
    
    def _check_consecutive_losses(self) -> Dict[str, Any]:
        """Check consecutive losses limit"""
        if self.consecutive_losses >= self.max_consecutive_losses:
            return {
                "passed": False,
                "type": CircuitBreakerType.CONSECUTIVE_LOSSES,
                "reason": f"Max consecutive losses reached ({self.consecutive_losses}/{self.max_consecutive_losses})"
            }
        return {"passed": True}
    
    def _check_daily_loss_limit(self) -> Dict[str, Any]:
        """Check daily loss limit"""
        daily_loss_pct = (self.daily_loss_usd / self.account_balance) * 100
        
        if daily_loss_pct >= self.max_daily_loss_pct:
            return {
                "passed": False,
                "type": CircuitBreakerType.DAILY_LOSS_LIMIT,
                "reason": f"Daily loss limit reached (${self.daily_loss_usd:.2f} = {daily_loss_pct:.1f}%)"
            }
        return {"passed": True}
    
    def _check_failed_orders(self) -> Dict[str, Any]:
        """Check failed orders limit"""
        if self.failed_orders >= self.max_failed_orders:
            return {
                "passed": False,
                "type": CircuitBreakerType.FAILED_ORDERS,
                "reason": f"Max failed orders reached ({self.failed_orders}/{self.max_failed_orders})"
            }
        return {"passed": True}
    
    def _check_system_errors(self) -> Dict[str, Any]:
        """Check system errors limit"""
        if self.system_errors >= self.max_system_errors:
            return {
                "passed": False,
                "type": CircuitBreakerType.SYSTEM_ERRORS,
                "reason": f"Max system errors reached ({self.system_errors}/{self.max_system_errors})"
            }
        return {"passed": True}
    
    def _open_circuit(self, breaker_type: CircuitBreakerType, reason: str):
        """Open circuit breaker"""
        self.state = CircuitState.OPEN
        self.opened_at = datetime.now()
        self.opened_by = breaker_type
        self.opened_reason = reason
        
        # Record in history
        self.trip_history.append({
            "timestamp": self.opened_at.isoformat(),
            "type": breaker_type.value,
            "reason": reason
        })
        
        logger.critical("=" * 70)
        logger.critical("🚨 CIRCUIT BREAKER OPENED!")
        logger.critical(f"   Type: {breaker_type.value}")
        logger.critical(f"   Reason: {reason}")
        logger.critical(f"   Cooldown: {self.cooldown_minutes} minutes")
        logger.critical("   ALL TRADING IS BLOCKED")
        logger.critical("=" * 70)
    
    def close_circuit(self):
        """Close circuit breaker (manual or after successful recovery)"""
        if self.state == CircuitState.CLOSED:
            return
        
        logger.info("✅ Circuit breaker CLOSED - Normal operation resumed")
        self.state = CircuitState.CLOSED
        self.opened_at = None
        self.opened_by = None
        self.opened_reason = ""
    
    def manual_reset(self) -> Dict[str, Any]:
        """Manual reset of circuit breaker"""
        logger.warning("⚠️ MANUAL RESET initiated")
        
        # Reset all counters
        self.consecutive_losses = 0
        self.failed_orders = 0
        self.system_errors = 0
        # Keep daily_loss_usd (for daily tracking)
        
        # Close circuit
        self.close_circuit()
        
        return {
            "success": True,
            "message": "Circuit breaker manually reset",
            "timestamp": datetime.now().isoformat()
        }
    
    def _check_cooldown(self) -> bool:
        """Check if cooldown period has expired"""
        if not self.opened_at:
            return True
        
        elapsed = datetime.now() - self.opened_at
        return elapsed.total_seconds() >= (self.cooldown_minutes * 60)
    
    def _get_remaining_cooldown(self) -> int:
        """Get remaining cooldown time in minutes"""
        if not self.opened_at:
            return 0
        
        elapsed = datetime.now() - self.opened_at
        remaining_seconds = (self.cooldown_minutes * 60) - elapsed.total_seconds()
        return max(0, int(remaining_seconds / 60))
    
    def _check_daily_reset(self):
        """Reset daily counters if new day"""
        today = datetime.now().date()
        
        if today > self.last_reset_date:
            logger.info(f"📅 New day - Resetting daily counters (loss was ${self.daily_loss_usd:.2f})")
            self.daily_loss_usd = 0.0
            self.failed_orders = 0
            self.system_errors = 0
            self.last_reset_date = today
    
    def get_status(self) -> Dict[str, Any]:
        """Get current circuit breaker status"""
        return {
            "name": self.name,
            "version": self.version,
            "state": self.state.value,
            "counters": {
                "consecutive_losses": f"{self.consecutive_losses}/{self.max_consecutive_losses}",
                "daily_loss_usd": f"${self.daily_loss_usd:.2f}",
                "daily_loss_pct": f"{(self.daily_loss_usd / self.account_balance) * 100:.2f}%",
                "failed_orders": f"{self.failed_orders}/{self.max_failed_orders}",
                "system_errors": f"{self.system_errors}/{self.max_system_errors}"
            },
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
            "opened_by": self.opened_by.value if self.opened_by else None,
            "opened_reason": self.opened_reason,
            "cooldown_remaining_minutes": self._get_remaining_cooldown() if self.state == CircuitState.OPEN else 0,
            "trip_count": len(self.trip_history)
        }


# ========== STANDALONE TESTING ==========

if __name__ == "__main__":
    logger.info("Testing CircuitBreaker...")
    
    # Initialize
    cb = CircuitBreaker(
        max_consecutive_losses=3,
        max_daily_loss_pct=5.0,
        account_balance=10000.0,
        cooldown_minutes=1  # 1 minute for testing
    )
    
    # Test 1: Normal operation
    logger.info("\n" + "=" * 60)
    logger.info("TEST 1: Normal operation")
    result = cb.check_before_trade()
    logger.info(f"Allowed: {result['allowed']}")
    
    # Test 2: Record losses
    logger.info("\n" + "=" * 60)
    logger.info("TEST 2: Consecutive losses")
    cb.record_trade_result(-100)  # Loss 1
    cb.record_trade_result(-100)  # Loss 2
    cb.record_trade_result(-100)  # Loss 3
    
    # Test 3: Check circuit (should be open)
    logger.info("\n" + "=" * 60)
    logger.info("TEST 3: Check circuit after 3 losses")
    result = cb.check_before_trade()
    logger.info(f"Allowed: {result['allowed']}")
    logger.info(f"Reason: {result.get('reason', 'N/A')}")
    
    # Test 4: Manual reset
    logger.info("\n" + "=" * 60)
    logger.info("TEST 4: Manual reset")
    reset_result = cb.manual_reset()
    logger.info(f"Reset success: {reset_result['success']}")
    
    # Test 5: Check after reset
    result = cb.check_before_trade()
    logger.info(f"Allowed after reset: {result['allowed']}")
    
    # Get status
    logger.info("\n" + "=" * 60)
    logger.info("FINAL STATUS:")
    status = cb.get_status()
    logger.info(f"State: {status['state']}")
    logger.info(f"Counters: {status['counters']}")
    
    logger.info("\n✅ CircuitBreaker test complete!")
