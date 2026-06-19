"""
Test script untuk memverifikasi fungsi filter performance berdasarkan year dan month.
"""

import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from app.services.performance_service import (
    get_monthly_pnl_from_csv,
    list_available_years
)

def test_list_available_years():
    """Test fungsi list available years"""
    print("=" * 60)
    print("Testing list_available_years()...")
    print("=" * 60)
    
    years = list_available_years()
    print(f"Available years: {years}")
    print()

def test_get_all_data():
    """Test mengambil semua data tanpa filter"""
    print("=" * 60)
    print("Testing get_monthly_pnl_from_csv() - All Data")
    print("=" * 60)
    
    data = get_monthly_pnl_from_csv()
    print(f"Total months: {len(data)}")
    if data:
        print(f"First record: {data[0]}")
        print(f"Last record: {data[-1]}")
    print()

def test_filter_by_year(year):
    """Test filter berdasarkan year"""
    print("=" * 60)
    print(f"Testing get_monthly_pnl_from_csv(year={year})")
    print("=" * 60)
    
    data = get_monthly_pnl_from_csv(year=year)
    print(f"Total months for year {year}: {len(data)}")
    if data:
        for record in data:
            print(f"  {record['month']} {record['year']}: "
                  f"Net Profit = ${record['net_profit']:.2f}, "
                  f"Trades = {record['executed_trades']}, "
                  f"Win Rate = {record['win_rate']:.1f}%")
    print()

def test_filter_by_year_and_month(year, month):
    """Test filter berdasarkan year dan month"""
    print("=" * 60)
    print(f"Testing get_monthly_pnl_from_csv(year={year}, month={month})")
    print("=" * 60)
    
    data = get_monthly_pnl_from_csv(year=year, month=month)
    print(f"Total records: {len(data)}")
    if data:
        for record in data:
            print(f"  {record['month']} {record['year']}: "
                  f"Net Profit = ${record['net_profit']:.2f}, "
                  f"Trades = {record['executed_trades']}, "
                  f"Win Rate = {record['win_rate']:.1f}%")
    print()

def test_filter_by_month_only(month):
    """Test filter hanya berdasarkan month (across all years)"""
    print("=" * 60)
    print(f"Testing get_monthly_pnl_from_csv(month={month})")
    print("=" * 60)
    
    data = get_monthly_pnl_from_csv(month=month)
    print(f"Total records for month {month}: {len(data)}")
    if data:
        for record in data:
            print(f"  {record['month']} {record['year']}: "
                  f"Net Profit = ${record['net_profit']:.2f}, "
                  f"Trades = {record['executed_trades']}")
    print()

if __name__ == "__main__":
    # Test 1: List available years
    test_list_available_years()
    
    # Test 2: Get all data
    test_get_all_data()
    
    # Test 3: Filter by year 2025
    test_filter_by_year(2025)
    
    # Test 4: Filter by year 2024
    test_filter_by_year(2024)
    
    # Test 5: Filter by year 2025 and month January (1)
    test_filter_by_year_and_month(2025, 1)
    
    # Test 6: Filter by year 2025 and month June (6)
    test_filter_by_year_and_month(2025, 6)
    
    # Test 7: Filter by month only (June across all years)
    test_filter_by_month_only(6)
    
    print("=" * 60)
    print("✅ All tests completed!")
    print("=" * 60)
