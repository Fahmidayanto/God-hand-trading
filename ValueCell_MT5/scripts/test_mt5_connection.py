"""
Test MT5 Connection

Quick script to verify MT5 Python API is working.
This should be the first test after setting up the project.

Usage:
    cd python
    python ../scripts/test_mt5_connection.py
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

from dotenv import load_dotenv
from valuecell.adapters.mt5 import MT5Adapter
from valuecell.adapters.mt5.mt5_adapter import (
    TIMEFRAME_M15,
    TIMEFRAME_M1,
    TIMEFRAME_M5,
    TIMEFRAME_M30,
    TIMEFRAME_H1,
    TIMEFRAME_H4,
    TIMEFRAME_D1
)
from loguru import logger

# Configure logger
logger.remove()
logger.add(sys.stdout, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")


def main():
    """Test MT5 connection."""
    print("=" * 60)
    print("🧪 MT5 CONNECTION TEST")
    print("=" * 60)
    
    # Load environment variables
    load_dotenv()
    
    # Get trading symbol from .env
    symbol = os.getenv("TRADING_SYMBOL", "XAUUSD")
    
    # Initialize adapter
    print("\n1️⃣  Initializing MT5 Adapter...")
    adapter = MT5Adapter()
    
    # Test connection
    print("\n2️⃣  Connecting to MT5 Terminal...")
    if not adapter.initialize():
        print("❌ FAILED: Could not connect to MT5")
        print("\n🔍 Troubleshooting:")
        print("   - Make sure MT5 terminal is running")
        print("   - Check your MT5_PATH in .env file")
        print("   - Verify MT5 login credentials")
        return False
    
    print("✅ SUCCESS: Connected to MT5")
    
    # Get account info
    print("\n3️⃣  Fetching Account Information...")
    account = adapter.get_account_info()
    if account:
        print(f"   ✅ Login: {account['login']}")
        print(f"   ✅ Balance: ${account['balance']:.2f}")
        print(f"   ✅ Equity: ${account['equity']:.2f}")
        print(f"   ✅ Margin Free: ${account['margin_free']:.2f}")
        print(f"   ✅ Leverage: 1:{account['leverage']}")
    else:
        print("   ⚠️  Could not fetch account info (might be demo account)")
    
    # Get symbol info
    print(f"\n4️⃣  Checking Symbol: {symbol}")
    symbol_info = adapter.get_symbol_info(symbol)
    if symbol_info:
        spread_pips = symbol_info['spread'] * symbol_info['point'] * 10
        print(f"   ✅ Digits: {symbol_info['digits']}")
        print(f"   ✅ Spread: {symbol_info['spread']} points ({spread_pips:.1f} pips)")
        print(f"   ✅ Min Volume: {symbol_info['volume_min']}")
        print(f"   ✅ Max Volume: {symbol_info['volume_max']}")
    else:
        print(f"   ❌ FAILED: Could not get symbol info for {symbol}")
        adapter.shutdown()
        return False
    
    # Check spread
    print(f"\n5️⃣  Checking Spread Conditions...")
    max_spread = float(os.getenv("MAX_SPREAD_PIPS", "5.0"))
    if adapter.check_spread(symbol, max_spread):
        print(f"   ✅ Spread OK: {spread_pips:.1f} pips (max: {max_spread} pips)")
    else:
        print(f"   ⚠️  Spread HIGH: {spread_pips:.1f} pips (max: {max_spread} pips)")
    
    # Get latest rates
    print(f"\n6️⃣  Fetching Latest Market Data ({symbol} M15)...")
    rates = adapter.get_rates(symbol, TIMEFRAME_M15, count=5)
    if rates is not None:
        print(f"   ✅ Retrieved {len(rates)} bars")
        print("\n   Latest 5 bars:")
        print(rates[['time', 'open', 'high', 'low', 'close']].to_string(index=False))
    else:
        print("   ❌ FAILED: Could not fetch market data")
        adapter.shutdown()
        return False
    
    # Health check
    print(f"\n7️⃣  Performing Health Check...")
    health = adapter.health_check()
    print(f"   ✅ Initialized: {health['initialized']}")
    print(f"   ✅ Connected: {health['connected']}")
    print(f"   ✅ Terminal: {health.get('terminal', {}).get('company', 'N/A')}")
    
    # Shutdown
    print(f"\n8️⃣  Closing Connection...")
    adapter.shutdown()
    print("   ✅ Connection closed")
    
    # Summary
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED - MT5 API IS WORKING")
    print("=" * 60)
    print("\n🎯 Next Steps:")
    print("   1. Create Market Structure Detector")
    print("   2. Build Neon PostgreSQL integration")
    print("   3. Implement LangGraph orchestrator")
    print("   4. Build trading agents")
    
    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
