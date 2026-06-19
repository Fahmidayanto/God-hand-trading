"""
Validate Python detector using EXACT SAME data from Dev_Bot CSV files.

This ensures apple-to-apple comparison:
- Python detector reads OHLCV from MarketData_XAUUSD_M15_2026-06-10.csv
- Compares output with LLHHBOSData_XAUUSD_2026-06-10.csv
- Both use EXACT same price data from the chart
"""

import sys
from pathlib import Path
import pandas as pd
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

from valuecell.adapters.mt5 import MarketStructureDetector


def load_market_data_csv(csv_path: Path) -> pd.DataFrame:
    """Load OHLCV data from Dev_Bot MarketData CSV."""
    print(f"\n📂 Loading Market Data: {csv_path.name}")
    
    df = pd.read_csv(csv_path)
    
    # Parse datetime
    df['time'] = pd.to_datetime(df['Time'])
    
    # Rename columns to match detector expected format
    df = df.rename(columns={
        'Open': 'open',
        'High': 'high',
        'Low': 'low',
        'Close': 'close',
        'Volume': 'volume',
        'Spread': 'spread'
    })
    
    # Select only required columns
    df = df[['time', 'open', 'high', 'low', 'close', 'volume']].copy()
    
    # Sort by time (oldest first)
    df = df.sort_values('time').reset_index(drop=True)
    
    print(f"✅ Loaded {len(df)} bars")
    print(f"   Date Range: {df.iloc[0]['time']} to {df.iloc[-1]['time']}")
    
    return df


def load_llhhbos_csv(csv_path: Path, timeframe: str = "M15") -> pd.DataFrame:
    """Load Dev_Bot structure events CSV."""
    print(f"\n📂 Loading Structure Events: {csv_path.name}")
    
    df = pd.read_csv(csv_path, skiprows=1)
    
    # Filter by timeframe
    df_filtered = df[df['Timeframe'] == timeframe].copy()
    
    # Parse datetime
    df_filtered['DateTime'] = pd.to_datetime(df_filtered['Time'], format='%Y.%m.%d %H:%M:%S')
    
    # Clean up columns
    df_filtered['Type'] = df_filtered['Type'].str.strip()
    df_filtered['Direction/Action'] = df_filtered['Direction/Action'].str.strip()
    
    print(f"✅ Loaded {len(df)} total events")
    print(f"✅ Filtered to {len(df_filtered)} events for {timeframe}")
    
    return df_filtered


def categorize_devbot_events(df: pd.DataFrame) -> dict:
    """Categorize Dev_Bot events."""
    result = {
        'HH': [],
        'LL': [],
        'CHoCH': [],
        'BoS': []
    }
    
    for idx, row in df.iterrows():
        event_type = row['Type']
        action = row['Direction/Action']
        
        # HH events (Update only)
        if event_type == 'HH' and action == 'Update':
            result['HH'].append({
                'price': float(row['Price']),
                'time': row['DateTime']
            })
        
        # LL events (Update only)
        elif event_type == 'LL' and action == 'Update':
            result['LL'].append({
                'price': float(row['Price']),
                'time': row['DateTime']
            })
        
        # CHoCH events
        elif event_type == 'CHoCH':
            result['CHoCH'].append({
                'price': float(row['Price']),
                'time': row['DateTime'],
                'direction': action
            })
        
        # BoS events
        elif event_type == 'BoS':
            result['BoS'].append({
                'price': float(row['Price']),
                'time': row['DateTime'],
                'direction': action
            })
    
    return result


def run_python_detector(df: pd.DataFrame) -> dict:
    """Run Python detector on DataFrame."""
    print(f"\n🔍 Running Python Detector...")
    print(f"   Data: {len(df)} bars from {df.iloc[0]['time']} to {df.iloc[-1]['time']}")
    
    # Initialize detector
    detector = MarketStructureDetector(swing_length=5, timeframe="M15", realtime_mode=False)
    
    # Run detection
    events = detector.detect(df)
    
    print(f"✅ Detected {len(events)} total events")
    
    # Categorize events
    result = {
        'HH': [],
        'LL': [],
        'CHoCH': [],
        'BoS': []
    }
    
    for event in events:
        if event.type.value == 'HH' and event.status.value != 'Reference':
            result['HH'].append({
                'price': event.price,
                'time': event.time
            })
        
        elif event.type.value == 'LL' and event.status.value != 'Reference':
            result['LL'].append({
                'price': event.price,
                'time': event.time
            })
        
        elif 'CHoCH' in event.type.value:
            direction = 'Bullish' if 'Bullish' in event.type.value else 'Bearish'
            result['CHoCH'].append({
                'price': event.price,
                'time': event.time,
                'direction': direction
            })
        
        elif 'BoS' in event.type.value:
            direction = 'Bullish' if 'Bullish' in event.type.value else 'Bearish'
            result['BoS'].append({
                'price': event.price,
                'time': event.time,
                'direction': direction
            })
    
    print(f"   📊 Breakdown:")
    print(f"      HH: {len(result['HH'])}")
    print(f"      LL: {len(result['LL'])}")
    print(f"      CHoCH: {len(result['CHoCH'])}")
    print(f"      BoS: {len(result['BoS'])}")
    
    return result


def compare_events(devbot_events: dict, python_events: dict, tolerance_pips: float = 1.0):
    """Compare Dev_Bot vs Python events."""
    print(f"\n" + "=" * 80)
    print("🔄 DETAILED COMPARISON (Using Same CSV Data)")
    print("=" * 80)
    
    time_tolerance_sec = 900  # 15 minutes
    
    results = {}
    
    for event_type in ['HH', 'LL', 'CHoCH', 'BoS']:
        print(f"\n📊 {event_type} Events:")
        print(f"{'Dev_Bot':<35} {'Python':<35} {'Match?'}")
        print("-" * 80)
        
        devbot = devbot_events[event_type]
        python = python_events[event_type]
        
        matches = 0
        matched_python = set()
        
        # Match Dev_Bot events to Python events
        for db_event in devbot:
            db_str = f"{db_event['price']:.2f} @ {db_event['time'].strftime('%m-%d %H:%M')}"
            py_str = ""
            match_str = ""
            
            # Try to find matching Python event
            for idx, py_event in enumerate(python):
                if idx in matched_python:
                    continue
                
                price_diff_pips = abs(db_event['price'] - py_event['price']) * 10
                time_diff = abs((db_event['time'] - py_event['time']).total_seconds())
                
                if price_diff_pips <= tolerance_pips and time_diff <= time_tolerance_sec:
                    py_str = f"{py_event['price']:.2f} @ {py_event['time'].strftime('%m-%d %H:%M')}"
                    match_str = f"✅ ({price_diff_pips:.1f} pips, {int(time_diff/60)} min)"
                    matches += 1
                    matched_python.add(idx)
                    break
            
            if not py_str:
                py_str = "-"
                match_str = "❌ Missing in Python"
            
            print(f"{db_str:<35} {py_str:<35} {match_str}")
        
        # Show extra Python events
        for idx, py_event in enumerate(python):
            if idx not in matched_python:
                py_str = f"{py_event['price']:.2f} @ {py_event['time'].strftime('%m-%d %H:%M')}"
                print(f"{'-':<35} {py_str:<35} ⚠️  Extra in Python")
        
        # Calculate accuracy
        total_devbot = len(devbot)
        accuracy = (matches / total_devbot * 100) if total_devbot > 0 else (100 if len(python) == 0 else 0)
        
        print(f"\n   {event_type} Accuracy: {accuracy:.1f}% ({matches}/{total_devbot} matches)")
        
        results[event_type] = {
            'devbot_count': len(devbot),
            'python_count': len(python),
            'matches': matches,
            'accuracy': accuracy
        }
    
    return results


def main():
    """Main validation function."""
    print("=" * 80)
    print("🎯 ACCURACY VALIDATION - USING DEV_BOT CSV DATA")
    print("=" * 80)
    print("\nApple-to-Apple Comparison:")
    print("✅ Python detector reads from: MarketData_XAUUSD_M15_2026-06-10.csv")
    print("✅ Dev_Bot events from:        LLHHBOSData_XAUUSD_2026-06-10.csv")
    print("✅ Both use EXACT same price data\n")
    
    csv_folder = Path("d:/Project/Project MT5/Backtest_result")
    
    # Load OHLCV data
    market_data_path = csv_folder / "MarketData_XAUUSD_M15_2026-06-10.csv"
    
    if not market_data_path.exists():
        print(f"❌ Market data CSV not found: {market_data_path}")
        return False
    
    df_market = load_market_data_csv(market_data_path)
    
    # Load Dev_Bot structure events
    llhhbos_path = csv_folder / "LLHHBOSData_XAUUSD_2026-06-10.csv"
    
    if not llhhbos_path.exists():
        print(f"❌ Structure events CSV not found: {llhhbos_path}")
        return False
    
    df_events = load_llhhbos_csv(llhhbos_path, timeframe="M15")
    
    # Categorize Dev_Bot events
    print(f"\n📊 Categorizing Dev_Bot Events...")
    devbot_events = categorize_devbot_events(df_events)
    
    print(f"   ✅ Dev_Bot Event Breakdown (M15):")
    print(f"      HH: {len(devbot_events['HH'])} events")
    for event in devbot_events['HH']:
        print(f"         - {event['price']:.2f} @ {event['time'].strftime('%m-%d %H:%M')}")
    
    print(f"      LL: {len(devbot_events['LL'])} events")
    for event in devbot_events['LL']:
        print(f"         - {event['price']:.2f} @ {event['time'].strftime('%m-%d %H:%M')}")
    
    print(f"      CHoCH: {len(devbot_events['CHoCH'])} events")
    print(f"      BoS: {len(devbot_events['BoS'])} events")
    
    # Run Python detector on SAME data
    python_events = run_python_detector(df_market)
    
    print(f"\n   📊 Python Event Breakdown:")
    print(f"      HH: {len(python_events['HH'])} events")
    for event in python_events['HH']:
        print(f"         - {event['price']:.2f} @ {event['time'].strftime('%m-%d %H:%M')}")
    
    print(f"      LL: {len(python_events['LL'])} events")
    for event in python_events['LL']:
        print(f"         - {event['price']:.2f} @ {event['time'].strftime('%m-%d %H:%M')}")
    
    print(f"      CHoCH: {len(python_events['CHoCH'])} events")
    for event in python_events['CHoCH']:
        print(f"         - {event['direction']} {event['price']:.2f} @ {event['time'].strftime('%m-%d %H:%M')}")
    
    print(f"      BoS: {len(python_events['BoS'])} events")
    for event in python_events['BoS']:
        print(f"         - {event['direction']} {event['price']:.2f} @ {event['time'].strftime('%m-%d %H:%M')}")
    
    # Compare events
    comparison = compare_events(devbot_events, python_events, tolerance_pips=1.0)
    
    # Overall summary
    print(f"\n" + "=" * 80)
    print("📊 OVERALL ACCURACY SUMMARY")
    print("=" * 80)
    
    total_devbot = sum(r['devbot_count'] for r in comparison.values())
    total_matches = sum(r['matches'] for r in comparison.values())
    overall_accuracy = (total_matches / total_devbot * 100) if total_devbot > 0 else 0
    
    print(f"\n   Total Dev_Bot Events: {total_devbot}")
    print(f"   Total Python Events: {sum(r['python_count'] for r in comparison.values())}")
    print(f"   Total Matches: {total_matches}")
    print(f"   Overall Accuracy: {overall_accuracy:.1f}%")
    
    print(f"\n   📈 Accuracy by Event Type:")
    for event_type, result in comparison.items():
        status_icon = "✅" if result['accuracy'] >= 90 else ("⚠️ " if result['accuracy'] >= 75 else "❌")
        print(f"      {status_icon} {event_type:8} : {result['accuracy']:>5.1f}% ({result['matches']}/{result['devbot_count']} matches, {result['python_count']} Python total)")
    
    print(f"\n" + "=" * 80)
    
    if overall_accuracy >= 95:
        print("✅ EXCELLENT - Accuracy >= 95%")
        print("   Detector is production-ready!")
    elif overall_accuracy >= 90:
        print("✅ GOOD - Accuracy >= 90%")
        print("   Detector is acceptable for production")
    elif overall_accuracy >= 75:
        print("⚠️  ACCEPTABLE - Accuracy >= 75%")
        print("   Detector works but could be improved")
        print("   Consider tuning swing_length parameter")
    else:
        print("❌ NEEDS IMPROVEMENT - Accuracy < 75%")
        print("   Recommendations:")
        print("   1. Check swing_length parameter (currently 5)")
        print("   2. Investigate logic differences")
        print("   3. Verify Dev_Bot detection algorithm")
    
    print("=" * 80)
    
    return overall_accuracy >= 75


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️  Validation interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
