# Entry, SL, TP Overlay on Chart

**Date:** 2026-06-26
**Status:** Approved

## Problem

Market structure lines (HH, LL, BoS, CHoCH) are already plotted on the chart, but there is no visual representation of where trade entries, stop losses, and take profits occurred. Users want to see Entry/SL/TP lines overlaid on the price chart with shaded profit/loss areas.

## Data Source

7 CSV files in `Backtest_result/Backtest_Results_XAUUSD_*.csv` covering 2020–2026.

**Key columns:**
- `Type`: BUY / SELL
- `EntryPrice`, `SL`, `TP`
- `EntryTime`, `ExitTime`
- `Status`: EXECUTED / REJECTED
- `Profit`, `LotSize`, `Session`

Only `Status == "EXECUTED"` trades (~600 total) are displayed.

## Architecture

```
Backtest_Results_*.csv ──→ backtest_trades_reader.py ──→ GET /api/v1/trading/backtest-trades ──→ useBacktestTrades() hook ──→ Chart overlay
   (7 files, ~600 rows)     (cache 15 min, filter EXECUTED)     (new endpoint)                     (fetch once)                (3 LineSeries per trade + TradesOverlayPrimitive + labels)
```

## Backend

### Service: `backtest_trades_reader.py` (new file)

- Pattern: follows `market_structure_lines_reader.py`
- Reads ALL `Backtest_Results_XAUUSD_*.csv` files
- Filters only rows where `Status == "EXECUTED"`
- Returns list of `BacktestTrade` objects
- Module-level cache, 15-minute TTL

### API: `trading.py` (new route)

```python
@router.get("/backtest-trades")
async def get_backtest_trades(from_date: str = "2020-01-01", to_date: str = "")
```

Returns:
```json
{
  "trades": [
    {
      "type": "BUY",
      "entry_price": 4479.57,
      "sl": 4449.57,
      "tp": 4509.57,
      "profit": -150.05,
      "entry_time": "2026.01.06 16:45:00",
      "exit_time": "2026.01.07 07:43:41",
      "lot_size": 0.01,
      "session": "London_NewYork_Overlap"
    }
  ],
  "total_trades": 29,
  "last_updated": "..."
}
```

## Frontend

### New File: `trades-overlay-primitive.ts`

Custom `ISeriesPrimitive` for shaded areas:
- Green rectangle: Entry price → TP price, from entry_time to exit_time (opacity 15%)
- Red rectangle: SL price → Entry price, from entry_time to exit_time (opacity 15%)
- BUY: TP above Entry, SL below Entry
- SELL: TP below Entry, SL above Entry
- Uses canvas `ctx.fillRect()` with `timeScale.timeToCoordinate()` and `series.priceToCoordinate()`

### New Hook: `useBacktestTrades()` in `mt5_agents.ts`

- Fetches from `GET /api/v1/trading/backtest-trades`
- No automatic refetch (data is historical)
- `staleTime: 900000` (15 min)

### Changes in `trades.tsx`

**New state:**
```typescript
const [showTrades, setShowTrades] = useState(false);
```

**New refs:**
```typescript
const tradeSeriesRef = useRef<{ entry: ISeriesApi<"Line">; sl: ISeriesApi<"Line">; tp: ISeriesApi<"Line"> }[]>([]);
const tradesPrimitiveRef = useRef<TradesOverlayPrimitive | null>(null);
```

**Colors:**

| Element | Color | Style |
|---------|-------|-------|
| Entry line | `#3b82f6` (blue) | Dashed, width 2 |
| TP line | `#22c55e` (green) | Dashed, width 1.5 |
| SL line | `#ef4444` (red) | Dashed, width 1.5 |
| Green shadow | `rgba(34, 197, 94, 0.15)` | Fill rectangle |
| Red shadow | `rgba(239, 68, 68, 0.15)` | Fill rectangle |

**Labels:** HTML overlay (follows `renderStructureLabelsOverlay` pattern):
- `"Entry 4479.57"` (blue)
- `"SL 4449.57"` (red)
- `"TP 4509.57"` (green)

**Toggle button:** New button alongside Structure/Sessions/EMA:
```tsx
<button onClick={() => setShowTrades(!showTrades)}>Trades</button>
```

**Effect:** Follows same pattern as Structure/Sessions/EMA effects.

## No Impact Guarantee

| Component | Why No Impact |
|-----------|---------------|
| Structure lines | Separate refs (`tradeSeriesRef` vs `structureSeriesRef`), separate toggle |
| Session zones | Separate primitive, separate toggle |
| EMA 200 | Separate line, not touched |
| Candles | No changes to candle data |
| Price axis | All lines: `priceLineVisible: false`, `lastValueVisible: false` — no auto-scale |
| Chart scroll/zoom | No changes to `focusChartOnDate`, `setVisibleLogicalRange` |
| Reset Zoom | Not modified |
| Other backend APIs | New endpoint only, 0 changes to existing endpoints |
| Structure data fetching | Separate hook, separate cache |
