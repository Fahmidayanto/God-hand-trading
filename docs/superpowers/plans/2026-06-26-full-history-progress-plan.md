# Full History Progress Indicator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add real-time progress popup (0-100%) when clicking "Load Full History"

**Architecture:** NDJSON streaming — single HTTP connection, backend counts rows then streams progress every 500 rows, frontend reads via `response.body.getReader()`

**Tech Stack:** FastAPI (Python 3.11+), React 18 + TypeScript, lightweight-charts

## Global Constraints

- Must NOT modify existing `/chart/backtest-data` endpoint
- Must NOT affect recent mode or jump navigation
- Progress must be sequential (per-row), not step-loncat
- Follow existing path resolution pattern: `Path(__file__).resolve().parent.parent.parent.parent.parent / "Backtest_result"`

---

### Task 1: Backend — MarketDataStreamer class

**Files:**
- Create: `backend/app/services/market_data_streamer.py`

**Interfaces:**
- Produces: `MarketDataStreamer(symbol, timeframe, from_date, mode).stream()` → `AsyncGenerator[str, None]`

- [ ] **Step 1: Create MarketDataStreamer class with count_pass + process_pass**

```python
class MarketDataStreamer:

    def __init__(self):
        project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
        self.backtest_dir = project_root / "Backtest_result"

    def count_rows(self, files: List[Path]) -> int:
        total = 0
        for f in files:
            with open(f, "r", encoding="utf-8") as fh:
                for _ in fh:
                    total += 1
            total -= 1
        return total

    async def stream(self, symbol="XAUUSD", timeframe="M15", from_date="2020-01-01", mode="full"):
        matches = sorted(self.backtest_dir.glob(f"MarketData_{symbol}_{timeframe}_*.csv"))
        if not matches:
            yield json.dumps({"type": "error", "message": f"No MarketData CSV for {symbol} {timeframe}"})
            return

        from_dt = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        yield json.dumps({"type": "progress", "percent": 0, "step": "Counting rows...", "total_estimated": 0})
        total_estimated = self.count_rows(matches)
        yield json.dumps({"type": "progress", "percent": 0, "step": f"{total_estimated:,} rows total. Processing...", "total_estimated": total_estimated})

        candles = []
        row_count = 0
        for file_idx, file_path in enumerate(matches, 1):
            year_match = re.search(r"(\d{4})", file_path.stem)
            year = year_match.group(1) if year_match else "unknown"
            with open(file_path, "r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    ts = datetime.strptime(row["Time"], "%Y.%m.%d %H:%M:%S").replace(tzinfo=timezone.utc)
                    if ts < from_dt: continue
                    candles.append({"time": int(ts.timestamp()), "open": float(row["Open"]), "high": float(row["High"]), "low": float(row["Low"]), "close": float(row["Close"]), "ema200": round(float(row["EMA200"]), 2)})
                    row_count += 1
                    if row_count % 500 == 0:
                        percent = round(row_count / total_estimated * 100, 1)
                        yield json.dumps({"type": "progress", "percent": min(percent, 99.9), "step": f"File {file_idx}/{len(matches)} ({year}) - {row_count:,}/{total_estimated:,} rows", "total_estimated": total_estimated})

        candles.sort(key=lambda c: c["time"])
        seen = set()
        unique = [c for c in candles if not (c["time"] in seen or seen.add(c["time"]))]
        yield json.dumps({"type": "complete", "data": {"symbol": symbol, "timeframe": timeframe, "candles": unique[:200000], "total": len(unique), "mode": mode, "timezone": "UTC"}})
```

- [ ] **Step 2: Verify import + stream test**

```bash
python -c "from app.services.market_data_streamer import MarketDataStreamer; print('OK')"
```

---

### Task 2: Backend — New endpoint in trading.py

**Files:**
- Modify: `backend/app/api/v1/trading.py`

- [ ] **Step 1: Add StreamingResponse import**

At line 7: `from fastapi.responses import JSONResponse, StreamingResponse`

- [ ] **Step 2: Add new route after get_backtest_chart_data**

```python
@router.get("/chart/backtest-data-stream")
async def get_backtest_chart_data_stream(
    symbol: str = Query("XAUUSD"),
    timeframe: str = Query("M15"),
    from_date: str = Query("2020-01-01"),
    mode: str = Query("full"),
):
    from app.services.market_data_streamer import MarketDataStreamer
    streamer = MarketDataStreamer()
    async def generate():
        async for line in streamer.stream(symbol, timeframe, from_date, mode):
            yield line + "\n"
    return StreamingResponse(generate(), media_type="application/x-ndjson")
```

- [ ] **Step 3: Test endpoint**

```bash
curl -N "http://localhost:8000/api/v1/trading/chart/backtest-data-stream?symbol=XAUUSD&timeframe=M15&mode=full"
```
Expected: NDJSON lines streaming

---

### Task 3: Frontend — Progress state + streaming fetch + popup UI

**Files:**
- Modify: `frontend/src/app/mt5/trades.tsx`

- [ ] **Step 1: Add loadProgress state** (after `chartCandles` state)

```typescript
const [loadProgress, setLoadProgress] = useState<{
  visible: boolean;
  percent: number;
  step: string;
  total: number;
}>({ visible: false, percent: 0, step: '', total: 0 });
```

- [ ] **Step 2: Replace loadFullHistory** with streaming version

```typescript
const loadFullHistory = async () => {
  setLoadProgress({ visible: true, percent: 0, step: 'Counting rows...', total: 0 });
  // ... cache check first ...
  // If cached: reuse + close popup
  // If not cached: fetch with streaming
  const response = await fetch(`${apiUrl}/trading/chart/backtest-data-stream?...`);
  const reader = response.body!.getReader();
  // parse NDJSON lines, update progress, handle complete/error
};
```

- [ ] **Step 3: Add progress popup JSX** (before footer)

```tsx
{loadProgress.visible && (
  <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
    <div className="bg-gray-900 border border-purple-500/30 rounded-xl p-6 shadow-2xl w-96">
      <div className="text-3xl font-bold">{loadProgress.percent}%</div>
      <div className="text-xs">{loadProgress.step}</div>
      <div className="w-full h-2 bg-gray-700 rounded-full overflow-hidden">
        <div className="h-full bg-gradient-to-r from-purple-500 to-blue-500" style={{width:`${loadProgress.percent}%`}} />
      </div>
    </div>
  </div>
)}
```

- [ ] **Step 4: Update button condition**

Add `!loadProgress.visible` to hide button during loading:
```tsx
{!fullHistoryLoadedRef.current[activeTimeframe] && dataMode !== 'loading' && !loadProgress.visible && (
```

- [ ] **Step 5: Verify TypeScript**

```bash
npx tsc --noEmit --pretty | Select-String "TS[0-9]+:" | Measure-Object | % Count
```
Expected: 15 (same as before, 0 new errors)

---

### Task 4: End-to-end verification

- [ ] **Step 1: Start backend**

```bash
cd backend && uvicorn app.main:app --reload
```

- [ ] **Step 2: Start frontend**

```bash
cd frontend && npm run dev
```

- [ ] **Step 3: Test flow**

1. Open browser to MT5 page
2. Click "Load Full History"
3. Verify popup appears with % progress
4. Verify progress updates smoothly (0% → 100%)
5. Verify popup closes and chart renders candles
6. Verify button disappears after loading
7. Verify second click uses cache (no popup)
