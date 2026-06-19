"""
Analyze why Dev_Bot detected HH 4363.50 @ June 10 21:00
but Python detected it @ June 9 16:45

This script will show the detailed price action around that level.
"""

import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

from dotenv import load_dotenv
from valuecell.adapters.mt5 import MT5Adapter
from valuecell.adapters.mt5.mt5_adapter import TIMEFRAME_M15


def main():
    """Analyze HH 4363.50 discrepancy."""
    print("=" * 80)
    print("🔍 ANALYZING HH 4363.50 DISCREPANCY")
    print("=" * 80)
    print("\nDev_Bot says: June 10 @ 21:00")
    print("Python says:  June 9 @ 16:45\n")
    
    load_dotenv()
    
    adapter = MT5Adapter()
    if not adapter.initialize():
        print("❌ Failed to initialize MT5")
        return
    
    print("✅ MT5 Connected\n")
    
    # Fetch data
    df = adapter.get_rates("XAUUSD", TIMEFRAME_M15, count=200)
    
    if df is None:
        print("❌ Failed to fetch data")
        adapter.shutdown()
        return
    
    # Find candles around 4363.50
    print("📊 Candles with High >= 4363.50:")
    print("-" * 80)
    print(f"{'Time':<20} {'Open':<10} {'High':<10} {'Low':<10} {'Close':<10}")
    print("-" * 80)
    
    high_candles = df[df['high'] >= 4363.50].copy()
    
    for _, row in high_candles.iterrows():
        print(f"{str(row['time']):<20} {row['open']:>9.2f} {row['high']:>9.2f} {row['low']:>9.2f} {row['close']:>9.2f}")
    
    # Find exact 4363.50
    exact_match = df[df['high'] == 4363.50]
    
    if len(exact_match) > 0:
        print(f"\n✅ Found EXACT match: 4363.50")
        for _, row in exact_match.iterrows():
            print(f"   Time: {row['time']}")
            print(f"   OHLC: {row['open']:.2f}, {row['high']:.2f}, {row['low']:.2f}, {row['close']:.2f}")
    else:
        print(f"\n⚠️  No EXACT match for 4363.50, showing closest:")
        closest = high_candles.iloc[0] if len(high_candles) > 0 else None
        if closest is not None:
            print(f"   Time: {closest['time']}")
            print(f"   High: {closest['high']:.2f}")
    
    # Show June 9-10 timeline
    print(f"\n📅 June 9-10 Timeline (showing all highs > 4300):")
    print("-" * 80)
    
    june9_start = pd.Timestamp('2026-06-09 00:00:00')
    june10_end = pd.Timestamp('2026-06-10 23:59:59')
    
    df_period = df[(df['time'] >= june9_start) & (df['time'] <= june10_end)].copy()
    df_period = df_period[df_period['high'] >= 4300.0].copy()
    
    print(f"{'Date':<12} {'Time':<8} {'High':<10} {'Low':<10} {'Note'}")
    print("-" * 80)
    
    for _, row in df_period.iterrows():
        date_str = row['time'].strftime('%Y-%m-%d')
        time_str = row['time'].strftime('%H:%M')
        note = ""
        
        if row['high'] >= 4363.0:
            note = "← Potential HH"
        
        print(f"{date_str:<12} {time_str:<8} {row['high']:>9.2f} {row['low']:>9.2f} {note}")
    
    # Check swing high detection window
    print(f"\n🔍 Swing High Detection Analysis (swing_length=5):")
    print("   A swing high requires 5 candles on each side with lower highs\n")
    
    # Find the 4363.50 candle
    target_candle = df[df['high'] >= 4363.49].iloc[0] if len(df[df['high'] >= 4363.49]) > 0 else None
    
    if target_candle is not None:
        target_idx = df[df['time'] == target_candle['time']].index[0]
        
        print(f"   Target candle: {target_candle['time']} (high: {target_candle['high']:.2f})")
        print(f"   Index: {target_idx}\n")
        
        # Show 5 candles before and after
        start_idx = max(0, target_idx - 5)
        end_idx = min(len(df), target_idx + 6)
        
        window = df.iloc[start_idx:end_idx].copy()
        
        print(f"   {'Time':<20} {'High':<10} {'Position'}")
        print("   " + "-" * 60)
        
        for idx, row in window.iterrows():
            pos = ""
            if idx == target_idx:
                pos = "← TARGET"
            elif idx < target_idx:
                pos = f"← {target_idx - idx} bars before"
            else:
                pos = f"→ {idx - target_idx} bars after"
            
            print(f"   {str(row['time']):<20} {row['high']:>9.2f} {pos}")
        
        # Check if it's a valid swing high
        print(f"\n   Validation (need 5 candles each side with lower high):")
        
        valid_swing = True
        
        # Check 5 candles before
        for i in range(1, 6):
            if target_idx - i < 0:
                continue
            if df.iloc[target_idx - i]['high'] >= target_candle['high']:
                valid_swing = False
                print(f"   ❌ Candle {i} bars before has higher/equal high: {df.iloc[target_idx - i]['high']:.2f}")
        
        # Check 5 candles after
        for i in range(1, 6):
            if target_idx + i >= len(df):
                continue
            if df.iloc[target_idx + i]['high'] >= target_candle['high']:
                valid_swing = False
                print(f"   ❌ Candle {i} bars after has higher/equal high: {df.iloc[target_idx + i]['high']:.2f}")
        
        if valid_swing:
            print(f"   ✅ Valid swing high detected!")
        else:
            print(f"   ⚠️  Not a valid swing high with swing_length=5")
    
    print(f"\n" + "=" * 80)
    print("💡 CONCLUSION")
    print("=" * 80)
    print("\nDev_Bot and Python might differ because:")
    print("1. Different swing_length parameters")
    print("2. Dev_Bot might use different swing detection logic")
    print("3. Dev_Bot might have session-based resets")
    print("4. Timestamp differences (bar open vs bar close)")
    print("=" * 80)
    
    adapter.shutdown()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
