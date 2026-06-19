"""
Validate accuracy for June 10, 2026 ONLY.

Compare Python detector with Dev_Bot CSV for a single day to get accurate comparison.
"""

import sys
from pathlib import Path
import pandas as pd
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

from dotenv import load_dotenv
from valuecell.adapters.mt5 import MT5Adapter, MarketStructureDetector
from valuecell.adapters.mt5.mt5_adapter import TIMEFRAME_M15
from loguru import logger

logger.remove()
logger.add(sys.stdout, level="INFO", 
           format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")


def main():
    """Validate accuracy for June 10, 2026 only."""
    print("=" * 80)
    print("🎯 ACCURACY VALIDATION - JUNE 10, 2026 ONLY")
    print("=" * 80)
    print("\nComparing Python detector with Dev_Bot CSV for single day\n")
    
    load_dotenv()
    
    # Load Dev_Bot CSV
    csv_folder = Path("d:/Project/Project MT5/Backtest_result")
    csv_path = csv_folder / "LLHHBOSData_XAUUSD_2026-06-10.csv"
    
    if not csv_path.exists():
        print(f"❌ CSV not found: {csv_path}")
        return False
    
    print(f"📂 Loading: {csv_path.name}")
    df = pd.read_csv(csv_path, skiprows=1)
    
    # Filter for M15 and June 10 only
    df_m15 = df[df['Timeframe'] == 'M15'].copy()
    df_m15['DateTime'] = pd.to_datetime(df_m15['Time'], format='%Y.%m.%d %H:%M:%S')
    
    # Filter for June 10 only
    june10_start = pd.Timestamp('2026-06-10 00:00:00')
    june10_end = pd.Timestamp('2026-06-10 23:59:59')
    
    df_june10 = df_m15[(df_m15['DateTime'] >= june10_start) & 
                        (df_m15['DateTime'] <= june10_end)].copy()
    
    print(f"✅ Total M15 events: {len(df_m15)}")
    print(f"✅ June 10 events: {len(df_june10)}")
    
    # Categorize Dev_Bot events
    devbot_hh = df_june10[(df_june10['Type'] == 'HH') & (df_june10['Direction/Action'] == 'Update')]
    devbot_ll = df_june10[(df_june10['Type'] == 'LL') & (df_june10['Direction/Action'] == 'Update')]
    devbot_choch = df_june10[df_june10['Type'] == 'CHoCH']
    devbot_bos = df_june10[df_june10['Type'] == 'BoS']
    
    print(f"\n📊 Dev_Bot Events (June 10 M15):")
    print(f"   HH: {len(devbot_hh)} events")
    for _, row in devbot_hh.iterrows():
        print(f"      - {row['Price']:.2f} @ {row['DateTime'].strftime('%H:%M')}")
    
    print(f"   LL: {len(devbot_ll)} events")
    for _, row in devbot_ll.iterrows():
        print(f"      - {row['Price']:.2f} @ {row['DateTime'].strftime('%H:%M')}")
    
    print(f"   CHoCH: {len(devbot_choch)} events")
    for _, row in devbot_choch.iterrows():
        print(f"      - {row['Direction/Action']} {row['Price']:.2f} @ {row['DateTime'].strftime('%H:%M')}")
    
    print(f"   BoS: {len(devbot_bos)} events")
    for _, row in devbot_bos.iterrows():
        print(f"      - {row['Direction/Action']} {row['Price']:.2f} @ {row['DateTime'].strftime('%H:%M')}")
    
    # Initialize MT5 and fetch June 10 data
    print(f"\n🔌 Connecting to MT5...")
    adapter = MT5Adapter()
    
    if not adapter.initialize():
        print("❌ Failed to initialize MT5")
        return False
    
    print("✅ MT5 Connected")
    
    # Fetch enough data to include June 10
    print(f"\n📥 Fetching M15 data...")
    df_mt5 = adapter.get_rates("XAUUSD", TIMEFRAME_M15, count=200)
    
    if df_mt5 is None:
        print("❌ Failed to fetch data")
        adapter.shutdown()
        return False
    
    print(f"✅ Retrieved {len(df_mt5)} bars")
    print(f"   Date range: {df_mt5.iloc[0]['time']} to {df_mt5.iloc[-1]['time']}")
    
    # Filter to June 10 only
    df_june10_mt5 = df_mt5[(df_mt5['time'] >= june10_start) & 
                            (df_mt5['time'] <= june10_end)].copy()
    
    print(f"✅ June 10 bars: {len(df_june10_mt5)}")
    
    if len(df_june10_mt5) == 0:
        print("⚠️  No June 10 data in MT5 feed - date might be too old")
        print("    Using last available day instead...")
        # Use last day available
        last_date = df_mt5.iloc[-1]['time'].date()
        df_june10_mt5 = df_mt5[df_mt5['time'].dt.date == last_date].copy()
        print(f"✅ Using {last_date}: {len(df_june10_mt5)} bars")
    
    # Run detector on FULL dataset (need context for swing detection)
    print(f"\n🔍 Running Python detector (need full context for swings)...")
    detector = MarketStructureDetector(swing_length=5, timeframe="M15", realtime_mode=False)
    
    all_events = detector.detect(df_mt5)
    
    print(f"✅ Detected {len(all_events)} total events (all dates)")
    
    # Filter events to June 10 only
    june10_events = [e for e in all_events if june10_start <= e.time <= june10_end]
    
    print(f"✅ Filtered to {len(june10_events)} events on June 10")
    
    # Categorize Python events
    python_hh = [e for e in june10_events if e.type.value == 'HH' and e.status.value != 'Reference']
    python_ll = [e for e in june10_events if e.type.value == 'LL' and e.status.value != 'Reference']
    python_choch = [e for e in june10_events if 'CHoCH' in e.type.value]
    python_bos = [e for e in june10_events if 'BoS' in e.type.value]
    
    print(f"\n📊 Python Events (June 10 M15):")
    print(f"   HH: {len(python_hh)} events")
    for event in python_hh:
        print(f"      - {event.price:.2f} @ {event.time.strftime('%H:%M')}")
    
    print(f"   LL: {len(python_ll)} events")
    for event in python_ll:
        print(f"      - {event.price:.2f} @ {event.time.strftime('%H:%M')}")
    
    print(f"   CHoCH: {len(python_choch)} events")
    for event in python_choch:
        direction = 'Bullish' if 'Bullish' in event.type.value else 'Bearish'
        print(f"      - {direction} {event.price:.2f} @ {event.time.strftime('%H:%M')}")
    
    print(f"   BoS: {len(python_bos)} events")
    for event in python_bos:
        direction = 'Bullish' if 'Bullish' in event.type.value else 'Bearish'
        print(f"      - {direction} {event.price:.2f} @ {event.time.strftime('%H:%M')}")
    
    # Compare events
    print(f"\n" + "=" * 80)
    print("🔄 COMPARISON - JUNE 10, 2026")
    print("=" * 80)
    
    tolerance_pips = 1.0
    time_tolerance_sec = 900  # 15 minutes
    
    # HH Comparison
    print(f"\n📊 HH Events:")
    print(f"{'Dev_Bot':<30} {'Python':<30} {'Match?'}")
    print("-" * 70)
    
    hh_matches = 0
    matched_python_hh = set()
    
    for _, db_row in devbot_hh.iterrows():
        db_str = f"{db_row['Price']:.2f} @ {db_row['DateTime'].strftime('%H:%M')}"
        py_str = ""
        match = ""
        
        # Try to find matching Python event
        for idx, py_event in enumerate(python_hh):
            if idx in matched_python_hh:
                continue
            
            price_diff_pips = abs(db_row['Price'] - py_event.price) * 10
            time_diff = abs((db_row['DateTime'] - py_event.time).total_seconds())
            
            if price_diff_pips <= tolerance_pips and time_diff <= time_tolerance_sec:
                py_str = f"{py_event.price:.2f} @ {py_event.time.strftime('%H:%M')}"
                match = f"✅ ({price_diff_pips:.1f} pips)"
                hh_matches += 1
                matched_python_hh.add(idx)
                break
        
        if not py_str:
            py_str = "-"
            match = "❌ Missing"
        
        print(f"{db_str:<30} {py_str:<30} {match}")
    
    # Extra Python HH events
    for idx, py_event in enumerate(python_hh):
        if idx not in matched_python_hh:
            py_str = f"{py_event.price:.2f} @ {py_event.time.strftime('%H:%M')}"
            print(f"{'-':<30} {py_str:<30} ⚠️  Extra")
    
    hh_accuracy = (hh_matches / len(devbot_hh) * 100) if len(devbot_hh) > 0 else 0
    print(f"\n   HH Accuracy: {hh_accuracy:.1f}% ({hh_matches}/{len(devbot_hh)} matches)")
    
    # LL Comparison
    print(f"\n📊 LL Events:")
    print(f"{'Dev_Bot':<30} {'Python':<30} {'Match?'}")
    print("-" * 70)
    
    ll_matches = 0
    matched_python_ll = set()
    
    for _, db_row in devbot_ll.iterrows():
        db_str = f"{db_row['Price']:.2f} @ {db_row['DateTime'].strftime('%H:%M')}"
        py_str = ""
        match = ""
        
        # Try to find matching Python event
        for idx, py_event in enumerate(python_ll):
            if idx in matched_python_ll:
                continue
            
            price_diff_pips = abs(db_row['Price'] - py_event.price) * 10
            time_diff = abs((db_row['DateTime'] - py_event.time).total_seconds())
            
            if price_diff_pips <= tolerance_pips and time_diff <= time_tolerance_sec:
                py_str = f"{py_event.price:.2f} @ {py_event.time.strftime('%H:%M')}"
                match = f"✅ ({price_diff_pips:.1f} pips)"
                ll_matches += 1
                matched_python_ll.add(idx)
                break
        
        if not py_str:
            py_str = "-"
            match = "❌ Missing"
        
        print(f"{db_str:<30} {py_str:<30} {match}")
    
    # Extra Python LL events
    for idx, py_event in enumerate(python_ll):
        if idx not in matched_python_ll:
            py_str = f"{py_event.price:.2f} @ {py_event.time.strftime('%H:%M')}"
            print(f"{'-':<30} {py_str:<30} ⚠️  Extra")
    
    ll_accuracy = (ll_matches / len(devbot_ll) * 100) if len(devbot_ll) > 0 else 0
    print(f"\n   LL Accuracy: {ll_accuracy:.1f}% ({ll_matches}/{len(devbot_ll)} matches)")
    
    # CHoCH Comparison
    print(f"\n📊 CHoCH Events:")
    choch_accuracy = 0
    if len(devbot_choch) == 0 and len(python_choch) == 0:
        print("   Both: 0 events - N/A")
        choch_accuracy = 100
    else:
        print(f"   Dev_Bot: {len(devbot_choch)} events")
        print(f"   Python:  {len(python_choch)} events")
        # TODO: Add detailed comparison if needed
        choch_accuracy = 0
    
    # BoS Comparison
    print(f"\n📊 BoS Events:")
    bos_accuracy = 0
    if len(devbot_bos) == 0 and len(python_bos) == 0:
        print("   Both: 0 events - N/A")
        bos_accuracy = 100
    else:
        print(f"   Dev_Bot: {len(devbot_bos)} events")
        print(f"   Python:  {len(python_bos)} events")
        # TODO: Add detailed comparison if needed
        bos_accuracy = 0
    
    # Overall Summary
    print(f"\n" + "=" * 80)
    print("📊 OVERALL ACCURACY - JUNE 10, 2026")
    print("=" * 80)
    
    total_devbot = len(devbot_hh) + len(devbot_ll)
    total_matches = hh_matches + ll_matches
    overall_accuracy = (total_matches / total_devbot * 100) if total_devbot > 0 else 0
    
    print(f"\n   Total Dev_Bot Events: {total_devbot}")
    print(f"   Total Matches: {total_matches}")
    print(f"   Overall Accuracy: {overall_accuracy:.1f}%")
    
    print(f"\n   📈 By Event Type:")
    print(f"      HH:    {hh_accuracy:>5.1f}% ({hh_matches}/{len(devbot_hh)})")
    print(f"      LL:    {ll_accuracy:>5.1f}% ({ll_matches}/{len(devbot_ll)})")
    
    print(f"\n" + "=" * 80)
    
    if overall_accuracy >= 95:
        print("✅ EXCELLENT - Accuracy >= 95%")
    elif overall_accuracy >= 90:
        print("✅ GOOD - Accuracy >= 90%")
    elif overall_accuracy >= 75:
        print("⚠️  ACCEPTABLE - Accuracy >= 75%")
    else:
        print("❌ NEEDS IMPROVEMENT - Accuracy < 75%")
    
    print("=" * 80)
    
    adapter.shutdown()
    
    return overall_accuracy >= 75


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
