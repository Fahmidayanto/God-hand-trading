# Test Plan: LL/HH Line Visualization Fix

## 🧪 Manual Testing Steps

### Test 1: Visual Verification

**Steps:**
1. Start frontend development server:
   ```bash
   cd ValueCell_MT5/frontend
   npm run dev
   ```

2. Open browser dan navigate ke chart page yang menampilkan candlestick with structure

3. Enable market structure overlay (BoS, CHoCH, HH, LL)

4. Verify untuk setiap LL marker:
   - ✅ Garis horizontal merah mulai TEPAT dari candle LL
   - ✅ Tidak ada gap antara marker dan start line
   - ✅ Label "LL 4023" terlihat jelas

5. Verify untuk setiap HH marker:
   - ✅ Garis horizontal hijau mulai TEPAT dari candle HH
   - ✅ Tidak ada gap antara marker dan start line
   - ✅ Label "HH 4727" terlihat jelas

6. Cross-check dengan CSV data:
   ```
   Open: Backtest_result/LLHHBOSData_XAUUSD_2026-06-11.csv
   
   Example:
   Line 17: LL,Update,4023.74,2026.06.11 02:00:00,M15,Accepted
   
   Chart should show:
   - LL marker at price 4023.74
   - On candle at time 2026.06.11 02:00:00 (or closest)
   - Red horizontal line starting from that candle
   ```

### Test 2: Timestamp Tolerance Test

**Purpose:** Verify bahwa closest matching works dengan timestamp yang tidak exact

**Test Data:**
Create test scenarios dengan different timestamp tolerances:

1. **Exact Match (0ms difference)**
   - CSV: `2026.06.11 02:00:00`
   - Candle: `2026.06.11 02:00:00`
   - Expected: ✅ Perfect match

2. **Within 1 minute (< 60000ms)**
   - CSV: `2026.06.11 02:00:00`
   - Candle: `2026.06.11 02:00:45`
   - Expected: ✅ Should match (45 seconds tolerance)

3. **Within 1 hour (< 3600000ms)**
   - CSV: `2026.06.11 02:00:00`
   - Candle: `2026.06.11 02:30:00`
   - Expected: ✅ Should match (30 minutes tolerance)

4. **Beyond 1 hour (> 3600000ms)**
   - CSV: `2026.06.11 02:00:00`
   - Candle: `2026.06.11 05:00:00`
   - Expected: ❌ Should NOT match (too far)

### Test 3: Edge Cases

**3.1 LL/HH at Chart Start**
- Verify garis tidak extend ke kiri (sebelum LL terbentuk)
- Line should start from LL candle, not from chart start

**3.2 LL/HH at Chart End**
- Verify garis extend sampai last candle
- Label visible di ujung kanan

**3.3 Multiple LL at Same Price**
- CSV has:
  ```
  LL,Update,4268.51,2026.06.08 08:00:00,H1,Accepted
  LL,Update,4268.51,2026.06.08 08:30:00,M15,Accepted
  ```
- Expected: 2 separate lines (H1 and M15 timeframes)
- Should not overlap or duplicate

**3.4 LL followed by HH (Structure Shift)**
- Verify both lines visible
- LL line should stop or continue separately from HH line

### Test 4: Performance Test

**Purpose:** Ensure no performance degradation with fix

**Steps:**
1. Load chart dengan 1000+ candles
2. Enable all structure overlays (BoS, CHoCH, HH, LL)
3. Measure rendering time:
   - Open browser DevTools > Performance tab
   - Record interaction while scrolling chart
   - Check for any lag or frame drops

**Acceptance Criteria:**
- ✅ Chart renders in < 500ms
- ✅ Scrolling/zooming smooth (60fps)
- ✅ No memory leaks after 5 minutes

### Test 5: Browser Compatibility

Test pada different browsers:
- [ ] Chrome/Edge (Chromium)
- [ ] Firefox
- [ ] Safari (if available)

**Verify:**
- ✅ Lines render correctly
- ✅ No console errors
- ✅ Tooltip works on hover

## 🔧 Debugging Tips

### If lines still don't start from correct candle:

1. **Check console logs:**
   Add debug logging in `findClosestCandleIndex`:
   ```typescript
   const index = findClosestCandleIndex(ll.timestamp);
   console.log(`LL at ${ll.timestamp}: matched to candle index ${index}`);
   console.log(`  LL time: ${new Date(ll.timestamp).toISOString()}`);
   console.log(`  Candle time: ${data[index].time}`);
   ```

2. **Verify timestamp format:**
   - CSV uses: `YYYY.MM.DD HH:MM:SS`
   - Frontend expects: ISO string or unix timestamp
   - Check conversion in `market_structure_lines_reader.py`

3. **Check timezone:**
   - CSV time in broker timezone
   - Frontend displays in browser timezone
   - Backend converts to UTC (see line 98 in market_structure_lines_reader.py)

### If lines are missing:

1. **Check API response:**
   ```
   Open DevTools > Network tab
   Find request to /api/v1/market-structure-lines
   Verify response has ll_points/hh_points array
   ```

2. **Check data filtering:**
   - Default: last 48 hours
   - Older LL/HH won't show
   - Increase `hours_back` parameter if needed

3. **Verify deduplication:**
   - Check if LL/HH being filtered out as duplicate
   - See `deduplicate()` function in backend

## 📊 Success Criteria

Fix is considered successful when:

- ✅ All LL/HH lines start from correct candle (visual confirmation)
- ✅ Timestamp matching works with < 1 hour tolerance
- ✅ No console errors or warnings
- ✅ Performance acceptable (< 500ms render, 60fps scroll)
- ✅ Works across all major browsers
- ✅ Edge cases handled properly

## 📝 Known Limitations

1. **1 Hour Tolerance:**
   - LL/HH with timestamp > 1 hour off will not match
   - This is intentional to avoid false matches

2. **First/Last Candle:**
   - Lines always extend to last visible candle
   - Cannot extend beyond chart data range

3. **Overlapping Lines:**
   - Multiple LL at same price will overlap
   - Use zoom or different timeframe to distinguish

## 🚨 Rollback Plan

If fix causes issues:

1. **Immediate rollback:**
   ```bash
   cd ValueCell_MT5/frontend
   git revert HEAD
   npm run build
   ```

2. **Verify old behavior:**
   - Lines may not start from correct candle (known issue)
   - But should not crash or show errors

3. **Report issue:**
   - Capture screenshot
   - Note browser and data used
   - Check console for errors

---

**Test Status:** ⏳ PENDING  
**Last Updated:** June 18, 2026
