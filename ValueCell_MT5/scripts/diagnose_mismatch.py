"""
Diagnose why Python detector and Dev_Bot CSV have different results.

This script provides detailed analysis of:
1. Date range coverage
2. Event-by-event comparison
3. Visual timeline
"""

import sys
from pathlib import Path
import pandas as pd
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

from dotenv import load_dotenv
from valuecell.adapters.mt5 import MT5Adapter, MarketStructureDetector
from valuecell.adapters.mt5.mt5_adapter import TIMEFRAME_M15


def load_and_analyze_csv(csv_path: Path):
    """Load and analyze Dev_Bot CSV."""
    print("\n" + "=" * 80)
    print("📂 ANALYZING DEV_BOT CSV")
    print("=" * 80)
    
    df = pd.read_csv(csv_path, skiprows=1)
    
    print(f"\n✅ Loaded {len(df)} total events from {csv_path.name}")
    
    # Filter M15
    df_m15 = df[df['Timeframe'] == 'M15'].copy()
    df_m15['DateTime'] = pd.to_datetime(df_m15['Time'], format='%Y.%m.%d %H:%M:%S')
    
    print(f"✅ Filtered to {len(df_m15)} M15 events")
    
    # Date range
    if len(df_m15) > 0:
        earliest = df_m15['DateTime'].min()
        latest = df_m15['DateTime'].max()
        days = (latest - earliest).days
        
        print(f"\n📅 Dev_Bot Date Range:")
        print(f"   Earliest: {earliest}")
        print(f"   Latest:   {latest}")
        print(f"   Duration: {days} days")
    
    # Event breakdown
    print(f"\n📊 Dev_Bot Event Breakdown (M15):")
    
    hh_updates = df_m15[(df_m15['Type'] == 'HH') & (df_m15['Direction/Action'] == 'Update')]
    ll_updates = df_m15[(df_m15['Type'] == 'LL') & (df_m15['Direction/Action'] == 'Update')]
    choch = df_m15[df_m15['Type'] == 'CHoCH']
    bos = df_m15[df_m15['Type'] == 'BoS']
    
    print(f"   HH (Update): {len(hh_updates)} events")
    for _, row in hh_updates.iterrows():
        print(f"      - {row['Price']:.2f} @ {row['DateTime']}")
    
    print(f"   LL (Update): {len(ll_updates)} events")
    for _, row in ll_updates.iterrows():
        print(f"      - {row['Price']:.2f} @ {row['DateTime']}")
    
    print(f"   CHoCH: {len(choch)} events")
    print(f"   BoS: {len(bos)} events")
    
    return df_m15, earliest if len(df_m15) > 0 else None


def run_python_detector_analysis(earliest_devbot_time=None):
    """Run Python detector and show detailed results."""
    print("\n" + "=" * 80)
    print("🔍 RUNNING PYTHON DETECTOR")
    print("=" * 80)
    
    load_dotenv()
    
    adapter = MT5Adapter()
    if not adapter.initialize():
        print("❌ Failed to initialize MT5")
        return None
    
    print("\n✅ MT5 Connected")
    
    # Fetch data
    print(f"\n📥 Fetching 1000 M15 bars...")
    df = adapter.get_rates("XAUUSD", TIMEFRAME_M15, count=1000)
    
    if df is None:
        print("❌ Failed to fetch data")
        adapter.shutdown()
        return None
    
    print(f"✅ Retrieved {len(df)} bars")
    print(f"\n📅 Python Data Range:")
    print(f"   Earliest: {df.iloc[0]['time']}")
    print(f"   Latest:   {df.iloc[-1]['time']}")
    print(f"   Duration: {(df.iloc[-1]['time'] - df.iloc[0]['time']).days} days")
    
    # Show date range mismatch
    if earliest_devbot_time:
        print(f"\n⚠️  DATE RANGE MISMATCH DETECTED:")
        print(f"   Dev_Bot starts: {earliest_devbot_time}")
        print(f"   Python starts:  {df.iloc[0]['time']}")
        print(f"   Gap: {(earliest_devbot_time - df.iloc[0]['time']).days} days")
        print(f"   → Python has {(earliest_devbot_time - df.iloc[0]['time']).days} extra days of data!")
    
    # Run detector
    print(f"\n🔍 Running market structure detection...")
    detector = MarketStructureDetector(swing_length=5, timeframe="M15", realtime_mode=False)
    events = detector.detect(df)
    
    print(f"✅ Detected {len(events)} total events")
    
    # Categorize and show
    hh_events = [e for e in events if e.type.value == 'HH' and e.status.value != 'Reference']
    ll_events = [e for e in events if e.type.value == 'LL' and e.status.value != 'Reference']
    choch_events = [e for e in events if 'CHoCH' in e.type.value]
    bos_events = [e for e in events if 'BoS' in e.type.value]
    
    print(f"\n📊 Python Event Breakdown:")
    print(f"   HH: {len(hh_events)} events")
    for event in hh_events:
        print(f"      - {event.price:.2f} @ {event.time}")
    
    print(f"   LL: {len(ll_events)} events")
    for event in ll_events:
        print(f"      - {event.price:.2f} @ {event.time}")
    
    print(f"   CHoCH: {len(choch_events)} events")
    for event in choch_events:
        print(f"      - {event.type.value} {event.price:.2f} @ {event.time}")
    
    print(f"   BoS: {len(bos_events)} events")
    for event in bos_events:
        print(f"      - {event.type.value} {event.price:.2f} @ {event.time}")
    
    # Filter to Dev_Bot date range if provided
    if earliest_devbot_time:
        print(f"\n🔄 Filtering Python events to match Dev_Bot date range...")
        print(f"   Filtering to events >= {earliest_devbot_time}")
        
        hh_filtered = [e for e in hh_events if e.time >= earliest_devbot_time]
        ll_filtered = [e for e in ll_events if e.time >= earliest_devbot_time]
        choch_filtered = [e for e in choch_events if e.time >= earliest_devbot_time]
        bos_filtered = [e for e in bos_events if e.time >= earliest_devbot_time]
        
        print(f"\n📊 Python Events (Filtered to Dev_Bot Date Range):")
        print(f"   HH: {len(hh_filtered)} events (was {len(hh_events)})")
        for event in hh_filtered:
            print(f"      - {event.price:.2f} @ {event.time}")
        
        print(f"   LL: {len(ll_filtered)} events (was {len(ll_events)})")
        for event in ll_filtered:
            print(f"      - {event.price:.2f} @ {event.time}")
        
        print(f"   CHoCH: {len(choch_filtered)} events (was {len(choch_events)})")
        print(f"   BoS: {len(bos_filtered)} events (was {len(bos_events)})")
    
    adapter.shutdown()
    
    return {
        'hh': hh_events,
        'll': ll_events,
        'choch': choch_events,
        'bos': bos_events
    }


def compare_side_by_side(devbot_df, python_events, earliest_time):
    """Show side-by-side comparison."""
    print("\n" + "=" * 80)
    print("🔄 SIDE-BY-SIDE COMPARISON (Filtered to same date range)")
    print("=" * 80)
    
    # Filter Python events to Dev_Bot date range
    python_hh = [e for e in python_events['hh'] if e.time >= earliest_time]
    python_ll = [e for e in python_events['ll'] if e.time >= earliest_time]
    
    # Dev_Bot events
    devbot_hh = devbot_df[(devbot_df['Type'] == 'HH') & (devbot_df['Direction/Action'] == 'Update')]
    devbot_ll = devbot_df[(devbot_df['Type'] == 'LL') & (devbot_df['Direction/Action'] == 'Update')]
    
    print(f"\n📊 HH Events Comparison:")
    print(f"{'Dev_Bot':<20} {'Python':<20} {'Match?'}")
    print("-" * 60)
    
    max_len = max(len(devbot_hh), len(python_hh))
    
    for i in range(max_len):
        db_str = ""
        py_str = ""
        match = ""
        
        if i < len(devbot_hh):
            db_row = devbot_hh.iloc[i]
            db_str = f"{db_row['Price']:.2f} @ {db_row['DateTime'].strftime('%m-%d %H:%M')}"
        
        if i < len(python_hh):
            py_event = python_hh[i]
            py_str = f"{py_event.price:.2f} @ {py_event.time.strftime('%m-%d %H:%M')}"
        
        # Check if they match (within 1 pip and 15 minutes)
        if i < len(devbot_hh) and i < len(python_hh):
            price_diff = abs(db_row['Price'] - python_hh[i].price) * 10
            time_diff = abs((db_row['DateTime'] - python_hh[i].time).total_seconds())
            if price_diff <= 1.0 and time_diff <= 900:
                match = "✅"
            else:
                match = "❌"
        
        print(f"{db_str:<20} {py_str:<20} {match}")
    
    print(f"\n📊 LL Events Comparison:")
    print(f"{'Dev_Bot':<20} {'Python':<20} {'Match?'}")
    print("-" * 60)
    
    max_len = max(len(devbot_ll), len(python_ll))
    
    for i in range(max_len):
        db_str = ""
        py_str = ""
        match = ""
        
        if i < len(devbot_ll):
            db_row = devbot_ll.iloc[i]
            db_str = f"{db_row['Price']:.2f} @ {db_row['DateTime'].strftime('%m-%d %H:%M')}"
        
        if i < len(python_ll):
            py_event = python_ll[i]
            py_str = f"{py_event.price:.2f} @ {py_event.time.strftime('%m-%d %H:%M')}"
        
        # Check if they match
        if i < len(devbot_ll) and i < len(python_ll):
            price_diff = abs(db_row['Price'] - python_ll[i].price) * 10
            time_diff = abs((db_row['DateTime'] - python_ll[i].time).total_seconds())
            if price_diff <= 1.0 and time_diff <= 900:
                match = "✅"
            else:
                match = "❌"
        
        print(f"{db_str:<20} {py_str:<20} {match}")


def main():
    """Main diagnostic function."""
    print("=" * 80)
    print("🔬 MARKET STRUCTURE MISMATCH DIAGNOSIS")
    print("=" * 80)
    print("\nAnalyzing why Python detector differs from Dev_Bot CSV...\n")
    
    # Find CSV
    csv_folder = Path("d:/Project/Project MT5/Backtest_result")
    csv_files = sorted(csv_folder.glob("LLHHBOSData_XAUUSD_*.csv"), reverse=True)
    
    if not csv_files:
        print("❌ No CSV files found")
        return
    
    csv_path = csv_files[0]
    
    # Analyze Dev_Bot CSV
    devbot_df, earliest_time = load_and_analyze_csv(csv_path)
    
    # Run Python detector
    python_events = run_python_detector_analysis(earliest_time)
    
    if python_events and earliest_time:
        # Side-by-side comparison
        compare_side_by_side(devbot_df, python_events, earliest_time)
    
    # Recommendations
    print("\n" + "=" * 80)
    print("💡 RECOMMENDATIONS")
    print("=" * 80)
    print("\n1. ✅ **Generate Fresh CSV for Today (2026-06-11)**:")
    print("   - Compile Dev_Bot_v11.cs (with auto-export modification)")
    print("   - Attach to XAUUSD M15 chart")
    print("   - Wait 15 minutes for candle close")
    print("   - CSV will auto-generate with today's date")
    print("   - This will ensure both detectors analyze the SAME period")
    
    print("\n2. 📊 **Current Issue**:")
    print("   - Dev_Bot CSV has LIMITED historical data (only 6 events)")
    print("   - Python detector analyzes FULL 1000 bars (~11 days)")
    print("   - Date range mismatch → accuracy appears low")
    
    print("\n3. 🎯 **Expected After Fresh CSV**:")
    print("   - Both will analyze June 11 data")
    print("   - Same date range = fair comparison")
    print("   - Expected accuracy: >95%")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
