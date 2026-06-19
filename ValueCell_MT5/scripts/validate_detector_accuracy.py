"""
Validate Market Structure Detector Accuracy

Compares Python detector output with Dev_Bot_v11.cs CSV output to calculate accuracy.

Target: >95% accuracy match

Usage:
    venv\Scripts\activate
    python scripts\validate_detector_accuracy.py
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

from dotenv import load_dotenv
from valuecell.adapters.mt5 import MT5Adapter, MarketStructureDetector
from valuecell.adapters.mt5.mt5_adapter import TIMEFRAME_M15, TIMEFRAME_H1
from loguru import logger

logger.remove()
logger.add(sys.stdout, level="INFO", 
           format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")


def load_dev_bot_csv(csv_path: Path, timeframe: str = "M15") -> pd.DataFrame:
    """
    Load Dev_Bot_v11.cs CSV and filter for specific timeframe.
    
    Args:
        csv_path: Path to LLHHBOSData CSV file
        timeframe: Timeframe to filter (M15, H1, H4)
    
    Returns:
        DataFrame with Dev_Bot events
    """
    print(f"\n📂 Loading Dev_Bot CSV: {csv_path.name}")
    
    try:
        # Read CSV, skip first header line
        df = pd.read_csv(csv_path, skiprows=1)
        
        print(f"   ✅ Loaded {len(df)} total events")
        
        # Filter by timeframe
        df_filtered = df[df['Timeframe'] == timeframe].copy()
        
        print(f"   ✅ Filtered to {len(df_filtered)} events for {timeframe}")
        
        # Parse datetime
        df_filtered['DateTime'] = pd.to_datetime(df_filtered['Time'], format='%Y.%m.%d %H:%M:%S')
        
        # Clean up type column
        df_filtered['Type'] = df_filtered['Type'].str.strip()
        df_filtered['Direction/Action'] = df_filtered['Direction/Action'].str.strip()
        
        return df_filtered
        
    except Exception as e:
        print(f"   ❌ Error loading CSV: {e}")
        return None


def categorize_events(df: pd.DataFrame) -> dict:
    """
    Categorize events into HH, LL, CHoCH, BoS.
    
    Args:
        df: DataFrame from Dev_Bot CSV
    
    Returns:
        Dict with categorized events
    """
    result = {
        'HH': [],
        'LL': [],
        'CHoCH': [],
        'BoS': []
    }
    
    for idx, row in df.iterrows():
        event_type = row['Type']
        action = row['Direction/Action']
        
        # HH events (Update only, skip Bullish/Bearish updates)
        if event_type == 'HH' and action == 'Update':
            result['HH'].append({
                'price': float(row['Price']),
                'time': row['DateTime'],
                'status': row['Status']
            })
        
        # LL events (Update only, skip Bullish/Bearish updates)
        elif event_type == 'LL' and action == 'Update':
            result['LL'].append({
                'price': float(row['Price']),
                'time': row['DateTime'],
                'status': row['Status']
            })
        
        # CHoCH events
        elif event_type == 'CHoCH':
            result['CHoCH'].append({
                'price': float(row['Price']),
                'time': row['DateTime'],
                'direction': action,
                'status': row['Status']
            })
        
        # BoS events
        elif event_type == 'BoS':
            result['BoS'].append({
                'price': float(row['Price']),
                'time': row['DateTime'],
                'direction': action,
                'status': row['Status']
            })
    
    return result


def run_python_detector(adapter: MT5Adapter, symbol: str, timeframe_mt5: int, 
                       timeframe_str: str, bars_count: int = 1000) -> dict:
    """
    Run Python detector on historical data.
    
    Args:
        adapter: MT5Adapter instance
        symbol: Trading symbol
        timeframe_mt5: MT5 timeframe constant
        timeframe_str: Timeframe string (M15, H1, etc.)
        bars_count: Number of bars to analyze
    
    Returns:
        Dict with detected events
    """
    print(f"\n🔍 Running Python Detector ({timeframe_str})...")
    print(f"   Fetching {bars_count} bars...")
    
    # Fetch historical data
    df = adapter.get_rates(symbol, timeframe_mt5, count=bars_count)
    
    if df is None:
        print("   ❌ Failed to fetch data")
        return None
    
    print(f"   ✅ Retrieved {len(df)} bars")
    print(f"   Date Range: {df.iloc[0]['time']} to {df.iloc[-1]['time']}")
    
    # Initialize detector
    detector = MarketStructureDetector(swing_length=5, timeframe=timeframe_str, realtime_mode=False)
    
    # Run detection
    events = detector.detect(df)
    
    print(f"   ✅ Detected {len(events)} structure events")
    
    # Categorize events
    result = {
        'HH': [],
        'LL': [],
        'CHoCH': [],
        'BoS': []
    }
    
    for event in events:
        if event.type.value == 'HH':
            if event.status.value != 'Reference':  # Skip reference events
                result['HH'].append({
                    'price': event.price,
                    'time': event.time,
                    'status': event.status.value
                })
        
        elif event.type.value == 'LL':
            if event.status.value != 'Reference':  # Skip reference events
                result['LL'].append({
                    'price': event.price,
                    'time': event.time,
                    'status': event.status.value
                })
        
        elif 'CHoCH' in event.type.value:
            direction = 'Bullish' if 'Bullish' in event.type.value else 'Bearish'
            result['CHoCH'].append({
                'price': event.price,
                'time': event.time,
                'direction': direction,
                'status': event.status.value
            })
        
        elif 'BoS' in event.type.value:
            direction = 'Bullish' if 'Bullish' in event.type.value else 'Bearish'
            result['BoS'].append({
                'price': event.price,
                'time': event.time,
                'direction': direction,
                'status': event.status.value
            })
    
    print(f"   📊 Breakdown:")
    print(f"      HH: {len(result['HH'])}")
    print(f"      LL: {len(result['LL'])}")
    print(f"      CHoCH: {len(result['CHoCH'])}")
    print(f"      BoS: {len(result['BoS'])}")
    
    return result


def compare_events(dev_bot_events: dict, python_events: dict, tolerance_pips: float = 1.0) -> dict:
    """
    Compare Dev_Bot events with Python detector events.
    
    Args:
        dev_bot_events: Events from Dev_Bot CSV
        python_events: Events from Python detector
        tolerance_pips: Price tolerance in pips for matching
    
    Returns:
        Dict with comparison results
    """
    print(f"\n📊 Comparing Events (tolerance: {tolerance_pips} pips)...")
    
    results = {}
    
    for event_type in ['HH', 'LL', 'CHoCH', 'BoS']:
        dev_bot = dev_bot_events[event_type]
        python = python_events[event_type]
        
        print(f"\n   🔹 {event_type}:")
        print(f"      Dev_Bot: {len(dev_bot)} events")
        print(f"      Python:  {len(python)} events")
        
        matches = 0
        mismatches = 0
        missing_in_python = 0
        extra_in_python = 0
        
        # Track matched Dev_Bot events
        matched_dev_bot = set()
        
        # Match Python events to Dev_Bot events
        for py_event in python:
            matched = False
            
            for idx, db_event in enumerate(dev_bot):
                if idx in matched_dev_bot:
                    continue
                
                # Check if prices match within tolerance
                price_diff_pips = abs(py_event['price'] - db_event['price']) * 10  # Convert to pips
                
                # Check if times match (within 15 minutes for swing detection lag)
                time_diff = abs((py_event['time'] - db_event['time']).total_seconds())
                
                if price_diff_pips <= tolerance_pips and time_diff <= 900:  # 15 minutes
                    matches += 1
                    matched_dev_bot.add(idx)
                    matched = True
                    break
            
            if not matched:
                extra_in_python += 1
        
        # Count missing events
        missing_in_python = len(dev_bot) - len(matched_dev_bot)
        
        # Calculate accuracy
        total_dev_bot = len(dev_bot)
        accuracy = (matches / total_dev_bot * 100) if total_dev_bot > 0 else 0
        
        print(f"      ✅ Matches: {matches}")
        print(f"      ⚠️  Missing in Python: {missing_in_python}")
        print(f"      ⚠️  Extra in Python: {extra_in_python}")
        print(f"      📈 Accuracy: {accuracy:.1f}%")
        
        results[event_type] = {
            'dev_bot_count': len(dev_bot),
            'python_count': len(python),
            'matches': matches,
            'missing_in_python': missing_in_python,
            'extra_in_python': extra_in_python,
            'accuracy': accuracy
        }
    
    return results


def main():
    """Main validation function."""
    print("=" * 80)
    print("🎯 MARKET STRUCTURE DETECTOR ACCURACY VALIDATION")
    print("=" * 80)
    print("\nComparing Python detector with Dev_Bot_v11.cs CSV output")
    print("Target: >95% accuracy match\n")
    
    # Load environment
    load_dotenv()
    
    # Find latest CSV file
    csv_folder = Path("d:/Project/Project MT5/Backtest_result")
    csv_files = sorted(csv_folder.glob("LLHHBOSData_XAUUSD_*.csv"), reverse=True)
    
    if not csv_files:
        print("❌ No CSV files found in Backtest_result folder")
        print("   Please run Dev_Bot_v11.cs first to generate reference data")
        return False
    
    csv_path = csv_files[0]
    
    # Load Dev_Bot CSV (M15 timeframe)
    dev_bot_df = load_dev_bot_csv(csv_path, timeframe="M15")
    
    if dev_bot_df is None:
        return False
    
    # Categorize Dev_Bot events
    print(f"\n📊 Categorizing Dev_Bot Events...")
    dev_bot_events = categorize_events(dev_bot_df)
    
    print(f"   ✅ Dev_Bot Event Breakdown:")
    print(f"      HH: {len(dev_bot_events['HH'])}")
    print(f"      LL: {len(dev_bot_events['LL'])}")
    print(f"      CHoCH: {len(dev_bot_events['CHoCH'])}")
    print(f"      BoS: {len(dev_bot_events['BoS'])}")
    
    # Initialize MT5
    print(f"\n🔌 Connecting to MT5...")
    adapter = MT5Adapter()
    
    if not adapter.initialize():
        print("❌ Failed to connect to MT5")
        return False
    
    print("✅ MT5 Connected")
    
    # Run Python detector
    symbol = os.getenv("TRADING_SYMBOL", "XAUUSD")
    python_events = run_python_detector(adapter, symbol, TIMEFRAME_M15, "M15", bars_count=1000)
    
    if python_events is None:
        adapter.shutdown()
        return False
    
    # Compare events
    comparison = compare_events(dev_bot_events, python_events, tolerance_pips=1.0)
    
    # Calculate overall accuracy
    print(f"\n" + "=" * 80)
    print("📊 OVERALL ACCURACY SUMMARY")
    print("=" * 80)
    
    total_dev_bot = sum(r['dev_bot_count'] for r in comparison.values())
    total_matches = sum(r['matches'] for r in comparison.values())
    overall_accuracy = (total_matches / total_dev_bot * 100) if total_dev_bot > 0 else 0
    
    print(f"\n   Total Dev_Bot Events: {total_dev_bot}")
    print(f"   Total Matches: {total_matches}")
    print(f"   Overall Accuracy: {overall_accuracy:.1f}%")
    
    # Accuracy by event type
    print(f"\n   📈 Accuracy by Event Type:")
    for event_type, result in comparison.items():
        status_icon = "✅" if result['accuracy'] >= 95 else "⚠️"
        print(f"      {status_icon} {event_type:8} : {result['accuracy']:5.1f}%")
    
    # Pass/Fail
    print(f"\n" + "=" * 80)
    
    if overall_accuracy >= 95:
        print("✅ VALIDATION PASSED - Accuracy >= 95%")
        print(f"   Detector is ready for production use!")
    elif overall_accuracy >= 90:
        print("⚠️  VALIDATION WARNING - Accuracy 90-95%")
        print(f"   Detector is acceptable but could be improved")
        print(f"   Consider tuning swing_length parameter")
    else:
        print("❌ VALIDATION FAILED - Accuracy < 90%")
        print(f"   Detector needs improvement")
        print(f"   Recommendations:")
        print(f"      1. Tune swing_length parameter (try 3, 4, 6, 7)")
        print(f"      2. Check price tolerance (currently 1.0 pips)")
        print(f"      3. Verify time synchronization")
    
    print("=" * 80)
    
    # Cleanup
    adapter.shutdown()
    
    return overall_accuracy >= 95


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
