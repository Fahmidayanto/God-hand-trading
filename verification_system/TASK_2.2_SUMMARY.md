# Task 2.2: Create Signal Key Generation Function

## Summary
Successfully implemented the `create_signal_key` function in `loaders/csv_loader.py`. This function creates unique identifiers for trading signals by combining entry time, trade type, and entry price.

## Implementation Details

### Function Signature
```python
def create_signal_key(entry_time: str, trade_type: str, entry_price: float) -> str
```

### Functionality
- **Input Format**: Accepts `EntryTime` in format "YYYY.MM.DD HH:MM:SS" or "YYYY.MM.DD HH:MM"
- **Time Truncation**: Automatically truncates seconds to minute precision ("YYYY.MM.DD HH:MM")
- **Key Format**: Returns "{EntryTime}_{Type}_{EntryPrice}" (e.g., "2023.01.04 09:15_BUY_1851.18")
- **Whitespace Handling**: Properly handles extra whitespace in input

### Key Features
1. **Minute-level Precision**: Truncates timestamps to minute precision to ensure consistent keys
2. **Type-safe**: Uses type hints for better code clarity
3. **Flexible Input**: Handles timestamps with or without seconds
4. **Unique Keys**: Different signals (different time/type/price) produce different keys

## Testing

### Unit Tests
Created comprehensive unit tests in `tests/test_csv_loader.py` with 9 test cases:

1. ✅ `test_create_signal_key_with_seconds` - Timestamp with seconds
2. ✅ `test_create_signal_key_without_seconds` - Timestamp without seconds
3. ✅ `test_create_signal_key_buy_signal` - BUY signal
4. ✅ `test_create_signal_key_sell_signal` - SELL signal
5. ✅ `test_create_signal_key_with_integer_price` - Integer price (1900.0)
6. ✅ `test_create_signal_key_with_high_precision_price` - High precision price
7. ✅ `test_create_signal_key_truncates_to_minutes` - Verifies second truncation
8. ✅ `test_create_signal_key_with_whitespace` - Handles extra whitespace
9. ✅ `test_create_signal_key_uniqueness` - Different signals produce different keys

### Test Results
```
21 passed in 1.53s
```
All tests passed, including:
- 12 existing tests for `load_csv` and `validate_csv_structure`
- 9 new tests for `create_signal_key`

### Integration Testing
Verified function works correctly with actual CSV data from `backtest_v7/Backtest_Results_XAUUSD_2023-12-29.csv`:
- Successfully loaded 70 records
- Generated correct signal keys for all records
- Example output:
  - `2023.01.04 09:15:00` + `BUY` + `1851.18` → `2023.01.04 09:15_BUY_1851.18`
  - `2023.01.18 05:30:00` + `SELL` + `1902.18` → `2023.01.18 05:30_SELL_1902.18`

## Requirements Validation
✅ **Requirement 1.1**: Correctly parses EntryTime format  
✅ **Requirement 1.2**: Creates unique keys with proper format

## Examples

### Example 1: Signal with seconds
```python
create_signal_key("2023.01.04 09:15:30", "BUY", 1851.18)
# Returns: "2023.01.04 09:15_BUY_1851.18"
```

### Example 2: Signal without seconds
```python
create_signal_key("2023.01.04 09:15", "SELL", 1850.50)
# Returns: "2023.01.04 09:15_SELL_1850.5"
```

### Example 3: Time truncation (different seconds, same key)
```python
create_signal_key("2023.01.04 09:15:00", "BUY", 1851.18)
create_signal_key("2023.01.04 09:15:30", "BUY", 1851.18)
create_signal_key("2023.01.04 09:15:59", "BUY", 1851.18)
# All return: "2023.01.04 09:15_BUY_1851.18"
```

## Next Steps
Task 2.2 is complete and ready for integration with Task 2.3 (unified signal dictionary builder), which will use this function to create keys for all signals across the 4 CSV versions.

## Files Modified
- `verification_system/loaders/csv_loader.py` - Added `create_signal_key` function
- `verification_system/tests/test_csv_loader.py` - Added 9 unit tests for the function
