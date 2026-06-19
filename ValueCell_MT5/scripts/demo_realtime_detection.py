"""
Demo Real-Time Detection

Demonstrates the difference between:
1. Backtest Mode: Detects ALL events in historical data
2. Realtime Mode: Only detects NEW events incrementally

Usage:
    venv\Scripts\activate
    python scripts\demo_realtime_detection.py
"""

import sys
import os
from pathlib import Path
import time

sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

from dotenv import load_dotenv
from valuecell.adapters.mt5 import MT5Adapter, MarketStructureDetector
from valuecell.adapters.mt5.mt5_adapter import TIMEFRAME_M15
from loguru import logger

logger.remove()
logger.add(sys.stdout, level="INFO", 
           format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")


def demo_backtest_mode():
    """Demo: Backtest Mode (detects ALL events)."""
    print("=" * 70)
    print("🔬 DEMO 1: BACKTEST MODE")
    print("=" * 70)
    print("Menganalisis 200 bars historis SEKALIGUS\n")
    
    load_dotenv()
    adapter = MT5Adapter()
    
    if not adapter.initialize():
        print("❌ Failed to connect to MT5")
        return
    
    # Get 200 bars
    print("📊 Fetching 200 bars...")
    df = adapter.get_rates("XAUUSD", TIMEFRAME_M15, count=200)
    
    if df is None:
        adapter.shutdown()
        return
    
    print(f"✅ Retrieved {len(df)} bars\n")
    
    # Initialize detector in BACKTEST mode
    print("🔧 Initializing detector (realtime_mode=False)...")
    detector = MarketStructureDetector(swing_length=5, timeframe="M15", realtime_mode=False)
    
    # Run detection ONCE
    print("🔍 Running detection...\n")
    events = detector.detect(df)
    
    print(f"✅ Detected {len(events)} events:")
    print(f"   - This analyzed ALL 200 bars")
    print(f"   - Found all HH/LL in history")
    print(f"   - Good for: Backtesting, validation\n")
    
    # Show breakdown
    hh_count = len([e for e in events if e.type.value == "HH"])
    ll_count = len([e for e in events if e.type.value == "LL"])
    choch_count = len([e for e in events if "CHoCH" in e.type.value])
    bos_count = len([e for e in events if "BoS" in e.type.value])
    
    print(f"📊 Breakdown:")
    print(f"   HH: {hh_count}")
    print(f"   LL: {ll_count}")
    print(f"   CHoCH: {choch_count}")
    print(f"   BoS: {bos_count}\n")
    
    adapter.shutdown()
    

def demo_realtime_mode():
    """Demo: Realtime Mode (only detects NEW events)."""
    print("\n" + "=" * 70)
    print("⚡ DEMO 2: REALTIME MODE")
    print("=" * 70)
    print("Simulasi real-time detection (incremental)\n")
    
    load_dotenv()
    adapter = MT5Adapter()
    
    if not adapter.initialize():
        print("❌ Failed to connect to MT5")
        return
    
    # Initialize detector in REALTIME mode
    print("🔧 Initializing detector (realtime_mode=True)...")
    detector = MarketStructureDetector(swing_length=5, timeframe="M15", realtime_mode=True)
    
    print("\n🔄 Simulating 3 detection cycles (like main loop)...\n")
    
    for cycle in range(1, 4):
        print(f"{'─' * 70}")
        print(f"⏰ Cycle {cycle}: Fetching latest 100 bars...")
        
        # Fetch latest 100 bars (like in main loop)
        df = adapter.get_rates("XAUUSD", TIMEFRAME_M15, count=100)
        
        if df is None:
            break
        
        print(f"   Latest bar: {df.iloc[-1]['time']} | Close: {df.iloc[-1]['close']:.2f}")
        
        # Run detection
        print(f"   🔍 Running detection...")
        events = detector.detect(df)
        
        if len(events) > 0:
            print(f"   ✅ NEW events detected: {len(events)}")
            for event in events:
                print(f"      - {event.type.value}: {event.price:.2f} @ {event.time}")
        else:
            print(f"   ℹ️  No NEW events (bars already processed)")
        
        # Show state
        state = detector.get_current_state()
        print(f"   📊 Current state:")
        print(f"      Last HH: {state['last_accepted_hh']:.2f}")
        print(f"      Last LL: {state['last_accepted_ll']:.2f}")
        
        if cycle < 3:
            print(f"\n   ⏳ Waiting 3 seconds before next cycle...")
            time.sleep(3)
    
    print(f"\n{'─' * 70}")
    print(f"\n✅ Realtime simulation complete")
    print(f"   Total events detected: {len(detector.structure_events)}")
    print(f"   - Only NEW events counted")
    print(f"   - No duplicate detections")
    print(f"   - Good for: Live trading\n")
    
    adapter.shutdown()


def main():
    """Run both demos."""
    print("\n" + "=" * 70)
    print("🎯 MARKET STRUCTURE DETECTION MODES COMPARISON")
    print("=" * 70)
    print("\nThis demo shows the difference between:")
    print("1. BACKTEST MODE: Analyze all historical data at once")
    print("2. REALTIME MODE: Incremental detection (only new events)")
    print("\n" + "=" * 70)
    
    # Demo 1: Backtest mode
    demo_backtest_mode()
    
    print("\n⏸️  Press Enter to continue to Realtime Mode demo...")
    input()
    
    # Demo 2: Realtime mode
    demo_realtime_mode()
    
    # Summary
    print("\n" + "=" * 70)
    print("📝 SUMMARY")
    print("=" * 70)
    print("\n✅ BACKTEST MODE (realtime_mode=False):")
    print("   - Detects ALL events in dataframe")
    print("   - Good for: Testing, validation, backtesting")
    print("   - Used in: test_structure_detector.py")
    
    print("\n✅ REALTIME MODE (realtime_mode=True):")
    print("   - Only detects NEW events")
    print("   - Prevents duplicate detections")
    print("   - Good for: Live trading, main loop")
    print("   - Used in: main_mt5.py (akan dibuat)")
    
    print("\n🎯 FOR YOUR QUESTION:")
    print("   Ya, detector bisa detect bar TERBARU sebagai patokan!")
    print("   - Gunakan realtime_mode=True")
    print("   - Setiap cycle hanya detect event BARU")
    print("   - Tidak re-detect event lama")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️  Demo interrupted")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
