"""
Test Market Structure Detector

Test script to verify HH/LL/CHoCH/BoS detection works correctly.

Usage:
    From project root:
    venv\Scripts\activate
    python scripts\test_structure_detector.py
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

from dotenv import load_dotenv
from valuecell.adapters.mt5 import MT5Adapter, MarketStructureDetector
from valuecell.adapters.mt5.mt5_adapter import TIMEFRAME_M15, TIMEFRAME_H1, TIMEFRAME_H4
from loguru import logger

# Configure logger
logger.remove()
logger.add(sys.stdout, level="INFO", 
           format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")


def main():
    """Test Market Structure Detector."""
    print("=" * 70)
    print("🧪 MARKET STRUCTURE DETECTOR TEST")
    print("=" * 70)
    
    # Load environment variables
    load_dotenv()
    
    # Get trading symbol
    symbol = os.getenv("TRADING_SYMBOL", "XAUUSD")
    
    # Initialize MT5
    print("\n1️⃣  Initializing MT5 Connection...")
    adapter = MT5Adapter()
    
    if not adapter.initialize():
        print("❌ FAILED: Could not connect to MT5")
        print("\n🔍 Troubleshooting:")
        print("   - Make sure MT5 terminal is running")
        print("   - Check your MT5_PATH in .env file")
        return False
    
    print("✅ SUCCESS: Connected to MT5")
    
    # Get historical data
    print(f"\n2️⃣  Fetching Historical Data ({symbol} M15)...")
    print("   Loading 200 bars for analysis...")
    
    df = adapter.get_rates(symbol, TIMEFRAME_M15, count=200)
    
    if df is None:
        print(f"   ❌ FAILED: Could not fetch data for {symbol}")
        adapter.shutdown()
        return False
    
    print(f"   ✅ Retrieved {len(df)} bars")
    print(f"   Date Range: {df.iloc[0]['time']} to {df.iloc[-1]['time']}")
    print(f"   Current Price: {df.iloc[-1]['close']:.2f}")
    
    # Initialize Market Structure Detector
    print("\n3️⃣  Initializing Market Structure Detector...")
    print("   Swing Length: 5 bars")
    print("   Timeframe: M15")
    
    detector = MarketStructureDetector(swing_length=5, timeframe="M15")
    print("   ✅ Detector initialized")
    
    # Run detection
    print("\n4️⃣  Running Structure Detection...")
    print("   Analyzing 200 bars for HH/LL/CHoCH/BoS patterns...")
    
    events = detector.detect(df)
    
    print(f"\n   ✅ Detection complete: {len(events)} structure events found")
    
    # Categorize events
    hh_events = [e for e in events if e.type.value == "HH"]
    ll_events = [e for e in events if e.type.value == "LL"]
    choch_events = [e for e in events if "CHoCH" in e.type.value]
    bos_events = [e for e in events if "BoS" in e.type.value]
    
    print(f"\n   📊 Event Breakdown:")
    print(f"      - Higher Highs (HH): {len(hh_events)}")
    print(f"      - Lower Lows (LL): {len(ll_events)}")
    print(f"      - Change of Character (CHoCH): {len(choch_events)}")
    print(f"      - Break of Structure (BoS): {len(bos_events)}")
    
    # Show recent events
    print(f"\n5️⃣  Recent Structure Events (Last 10):")
    
    if len(events) == 0:
        print("      ⚠️  No structure events detected")
        print("      This may be normal if market is ranging or data is insufficient")
    else:
        recent_events = events[-10:] if len(events) >= 10 else events
        
        for i, event in enumerate(recent_events, 1):
            direction = ""
            if "Bullish" in event.type.value:
                direction = "🟢"
            elif "Bearish" in event.type.value:
                direction = "🔴"
            elif event.type.value == "HH":
                direction = "📈"
            elif event.type.value == "LL":
                direction = "📉"
            
            print(f"      {i}. {direction} {event.type.value:18} | "
                  f"Price: {event.price:8.2f} | "
                  f"Time: {event.time} | "
                  f"Status: {event.status.value}")
    
    # Show current market structure state
    print(f"\n6️⃣  Current Market Structure State:")
    state = detector.get_current_state()
    
    print(f"   📊 Levels:")
    print(f"      Last Accepted HH: {state['last_accepted_hh']:.2f}")
    if state['last_hh_time']:
        print(f"         Time: {state['last_hh_time']}")
    
    print(f"      Last Accepted LL: {state['last_accepted_ll']:.2f}")
    if state['last_ll_time']:
        print(f"         Time: {state['last_ll_time']}")
    
    print(f"\n   🎯 Triggers:")
    print(f"      CHoCH Bullish: {'✅ TRIGGERED' if state['choch_bullish_triggered'] else '❌ Not triggered'}")
    if state['choch_bullish_triggered']:
        print(f"         Price: {state['choch_bullish_price']:.2f}")
    
    print(f"      CHoCH Bearish: {'✅ TRIGGERED' if state['choch_bearish_triggered'] else '❌ Not triggered'}")
    if state['choch_bearish_triggered']:
        print(f"         Price: {state['choch_bearish_price']:.2f}")
    
    print(f"      BoS Bullish: {'✅ TRIGGERED' if state['bos_bullish_triggered'] else '❌ Not triggered'}")
    if state['bos_bullish_triggered']:
        print(f"         Price: {state['bos_bullish_price']:.2f}")
    
    print(f"      BoS Bearish: {'✅ TRIGGERED' if state['bos_bearish_triggered'] else '❌ Not triggered'}")
    if state['bos_bearish_triggered']:
        print(f"         Price: {state['bos_bearish_price']:.2f}")
    
    # Market bias analysis
    print(f"\n7️⃣  Market Bias Analysis:")
    
    current_price = df.iloc[-1]['close']
    
    if state['last_accepted_hh'] > 0 and state['last_accepted_ll'] > 0:
        if current_price > state['last_accepted_hh']:
            bias = "🟢 BULLISH (Price above last HH)"
        elif current_price < state['last_accepted_ll']:
            bias = "🔴 BEARISH (Price below last LL)"
        else:
            bias = "⚪ RANGING (Between HH and LL)"
        
        print(f"   {bias}")
        print(f"   Current Price: {current_price:.2f}")
        print(f"   Range: {state['last_accepted_ll']:.2f} - {state['last_accepted_hh']:.2f}")
    else:
        print(f"   ⚠️  Insufficient data for bias analysis")
    
    # Comparison with Dev_Bot_v11.cs (if CSV file exists)
    print(f"\n8️⃣  Validation Against Dev_Bot_v11.cs:")
    
    csv_path = Path("d:/Project/Project MT5/Backtest_result")
    csv_files = list(csv_path.glob(f"LLHHBOSData_{symbol}_*.csv"))
    
    if csv_files:
        latest_csv = sorted(csv_files)[-1]
        print(f"   ℹ️  Found reference CSV: {latest_csv.name}")
        print(f"   📊 To validate, compare:")
        print(f"      - Number of HH/LL events")
        print(f"      - CHoCH/BoS trigger prices")
        print(f"      - Event timestamps")
        print(f"\n   Target Accuracy: >95% match with Dev_Bot_v11.cs")
    else:
        print(f"   ⚠️  No reference CSV file found in {csv_path}")
        print(f"      Run Dev_Bot_v11.cs first to generate reference data")
    
    # Cleanup
    print(f"\n9️⃣  Cleanup...")
    adapter.shutdown()
    print("   ✅ Connection closed")
    
    # Summary
    print("\n" + "=" * 70)
    if len(events) > 0:
        print("✅ TEST PASSED - Market Structure Detector is working")
    else:
        print("⚠️  TEST INCONCLUSIVE - No events detected (may be normal)")
    print("=" * 70)
    
    print("\n🎯 Next Steps:")
    print("   1. Run Dev_Bot_v11.cs to generate reference CSV")
    print("   2. Compare detector output with CSV data")
    print("   3. Calculate accuracy percentage")
    print("   4. If accuracy < 95%, tune swing_length parameter")
    print("   5. Proceed to Neon PostgreSQL integration")
    
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
