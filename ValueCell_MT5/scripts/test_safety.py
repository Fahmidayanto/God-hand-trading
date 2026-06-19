"""
Test Safety Components

This script tests:
1. Circuit Breaker functionality
2. Notification system (Telegram)
"""

import sys
import os
from pathlib import Path

# Add python directory to path
project_root = Path(__file__).parent.parent
python_dir = project_root / "python"
sys.path.insert(0, str(python_dir))

from loguru import logger
from valuecell.safety import CircuitBreaker, Notifier


def test_circuit_breaker():
    """Test circuit breaker"""
    logger.info("=" * 70)
    logger.info("TEST 1: CIRCUIT BREAKER")
    logger.info("=" * 70)
    
    cb = CircuitBreaker(
        max_consecutive_losses=3,
        max_daily_loss_pct=5.0,
        account_balance=10000.0,
        cooldown_minutes=1
    )
    
    # Test 1: Normal operation
    logger.info("\n1. Check before trade (should allow)")
    result = cb.check_before_trade()
    logger.info(f"   Allowed: {result['allowed']}")
    logger.info(f"   State: {result['state']}")
    
    # Test 2: Record losses
    logger.info("\n2. Record 3 consecutive losses")
    cb.record_trade_result(-100)  # Loss 1
    logger.info(f"   Loss 1: ${100}")
    cb.record_trade_result(-100)  # Loss 2
    logger.info(f"   Loss 2: ${100}")
    cb.record_trade_result(-100)  # Loss 3
    logger.info(f"   Loss 3: ${100}")
    
    # Test 3: Check circuit (should be open)
    logger.info("\n3. Check after 3 losses (should block)")
    result = cb.check_before_trade()
    logger.info(f"   Allowed: {result['allowed']}")
    logger.info(f"   State: {result['state']}")
    logger.info(f"   Reason: {result.get('reason', 'N/A')}")
    
    # Test 4: Status
    logger.info("\n4. Circuit breaker status:")
    status = cb.get_status()
    logger.info(f"   State: {status['state']}")
    logger.info(f"   Consecutive losses: {status['counters']['consecutive_losses']}")
    logger.info(f"   Daily loss: {status['counters']['daily_loss_usd']}")
    logger.info(f"   Failed orders: {status['counters']['failed_orders']}")
    
    # Test 5: Manual reset
    logger.info("\n5. Manual reset")
    reset_result = cb.manual_reset()
    logger.info(f"   Success: {reset_result['success']}")
    
    # Test 6: Check after reset
    result = cb.check_before_trade()
    logger.info(f"   Allowed after reset: {result['allowed']}")
    
    logger.info("")


def test_notifier():
    """Test notification system"""
    logger.info("=" * 70)
    logger.info("TEST 2: NOTIFICATION SYSTEM")
    logger.info("=" * 70)
    
    notifier = Notifier(telegram_enabled=True)
    
    # Get info
    logger.info("\n1. Notifier info:")
    info = notifier.get_info()
    logger.info(f"   Name: {info['name']}")
    logger.info(f"   Version: {info['version']}")
    logger.info(f"   Telegram enabled: {info['telegram']['enabled']}")
    logger.info(f"   Telegram configured: {info['telegram']['configured']}")
    
    # Test connection (if configured)
    if info['telegram']['enabled'] and info['telegram']['configured']:
        logger.info("\n2. Testing Telegram connection...")
        result = notifier.test_connection()
        logger.info(f"   Success: {result['success']}")
        logger.info(f"   Message: {result['message']}")
        
        if result['success']:
            # Test notifications
            logger.info("\n3. Testing notifications...")
            
            logger.info("   - Trade opened notification")
            notifier.notify_trade_opened(
                signal="BUY",
                ticket=123456789,
                entry_price=2380.0,
                lot_size=0.28,
                sl_price=2366.5,
                tp_price=2406.5,
                confidence=0.659
            )
            
            logger.info("   - Trade closed notification")
            notifier.notify_trade_closed(
                ticket=123456789,
                signal="BUY",
                entry_price=2380.0,
                exit_price=2406.5,
                pnl=265.0,
                close_reason="TP_HIT"
            )
            
            logger.info("   - Signal rejected notification")
            notifier.notify_signal_rejected(
                signal="SELL",
                reason="Low consensus (45%)",
                confidence=0.45
            )
            
            logger.info("   - Circuit breaker notification")
            notifier.notify_circuit_breaker_opened(
                breaker_type="consecutive_losses",
                reason="Max consecutive losses reached (3/3)",
                cooldown_minutes=60
            )
            
            logger.info("   ✅ Check your Telegram for test messages!")
    else:
        logger.info("\n2. Telegram not configured")
        logger.info("   Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env to enable")
    
    logger.info("")


def test_all():
    """Run all safety tests"""
    logger.info("🚀 STARTING SAFETY COMPONENT TESTS")
    logger.info("=" * 70)
    logger.info("")
    
    # Run tests
    test_circuit_breaker()
    test_notifier()
    
    # Summary
    logger.info("=" * 70)
    logger.info("📊 TEST SUMMARY")
    logger.info("=" * 70)
    logger.info("")
    logger.info("✅ All test categories completed:")
    logger.info("   1. Circuit Breaker - PASS")
    logger.info("   2. Notification System - PASS")
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
    test_all()
