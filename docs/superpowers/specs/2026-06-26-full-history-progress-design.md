# Full History Loading Progress Indicator

**Date:** 2026-06-26
**Status:** Approved

## Problem

Clicking "Load Full History" (loads ~150k candles from 2020) currently blocks the UI for 8-10 seconds with no feedback. Users don't know if the system is working, stuck, or crashed.

## Solution

Add real-time progress tracking via NDJSON streaming. Backend counts total rows first, then streams progress updates every 500 rows during processing. Frontend shows a modal popup with percentage bar and current step description.

**Approach:** NDJSON streaming (1 HTTP connection, no additional libraries)

## Architecture

```
User clicks [Load Full History]
  → frontend fetch GET /chart/backtest-data-stream (NEW endpoint)
  → backend count pass: scan CSVs, count total rows (~0.5s)
  → backend process pass: read CSVs row by row, emit progress every 500 rows
  → frontend reader reads stream, updates popup progress bar
  → backend emits {"type":"complete","data":{candles:[...]}}
  → frontend closes popup, renders candles (same flow as existing)
```

## Backend Changes

### New endpoint: `GET /chart/backtest-data-stream`

Same parameters as existing `/chart/backtest-data` but returns `Content-Type: application/x-ndjson`.

### New file: `backend/app/services/market_data_streamer.py`

Class `MarketDataStreamer` with method `stream()`:
- Same CSV reading logic as current inline code in `trading.py`
- Added: count pass (readline only, no parse)
- Added: yield JSON lines for progress every 500 rows
- Emits 3 types of NDJSON lines:
  - `{"type":"progress","percent":0,"step":"Counting rows...","total_estimated":150230}`
  - `{"type":"progress","percent":42,"step":"File 3/7 (2022) - 63.096/150.230 rows","total_estimated":150230}`
  - `{"type":"progress","percent":100,"step":"Finalizing..."}`
  - `{"type":"complete","data":{symbol, timeframe, candles[], ...}}`
  - `{"type":"error","message":"File not found"}`

### Endpoint registration

In `trading.py`, new route next to existing `get_backtest_chart_data`.

Existing endpoint `GET /chart/backtest-data` — **unchanged** (still used by recent mode and jump navigation).

## Frontend Changes

### File: `frontend/src/app/mt5/trades.tsx`

**New state:**
```typescript
const [loadProgress, setLoadProgress] = useState<{
  visible: boolean;
  percent: number;
  step: string;
  total: number;
}>({ visible: false, percent: 0, step: '', total: 0 });
```

**Modified function:** `loadFullHistory`
- Replace `await fetch(...)` + `await response.json()` with streaming fetch:
  - `response.body.getReader()` + `TextDecoder` to read line-delimited JSON
  - On `progress` line: update `loadProgress` state
  - On `complete` line: process and render candles (same cache + render as current code)
  - On stream error: fallback to `setDataMode('recent')`

**New component:** `FullHistoryProgress` — modal popup with:
- Semi-transparent backdrop
- Purple gradient progress bar (same style as button)
- Percentage number (large font)
- Current step description
- Total rows count (smaller font)

**Button change:**
```tsx
// Before:
{!fullHistoryLoadedRef.current[activeTimeframe] && dataMode !== 'loading' && (
// After:
{!fullHistoryLoadedRef.current[activeTimeframe] && dataMode !== 'loading' && !loadProgress.visible && (
```

## Error Handling

| Scenario | Handling |
|----------|----------|
| Connection lost mid-stream | `catch` → popup close → `setDataMode('recent')` |
| Empty data (no rows) | Complete with `candles: []` → popup notif "No data" |
| Double-click button | Button hidden while `loadProgress.visible === true` |
| Timeframe switch during load | Abort controller cancels fetch → popup close |
| Backend error | Emit `{"type":"error","message":"..."}` → popup shows error |

## Non-Goals

- No changes to recent mode (6-month auto-refresh)
- No changes to jump navigation
- No changes to structure/session/EMA overlays
- No changes to existing `/chart/backtest-data` endpoint

## Files Changed

| File | Change |
|------|--------|
| `backend/app/services/market_data_streamer.py` | NEW — streaming reader with progress |
| `backend/app/api/v1/trading.py` | NEW route + import streamer |
| `frontend/src/app/mt5/trades.tsx` | Modify `loadFullHistory`, add popup state + UI, update button condition |
