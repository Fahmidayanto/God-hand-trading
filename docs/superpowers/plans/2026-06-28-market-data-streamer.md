# MarketDataStreamer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the MarketDataStreamer service to stream market data CSV files with correct progress updates and final payload.

**Architecture:** The service reads CSV files from the Backtest_result directory, counts rows, yields progress JSON messages, parses rows into candle dictionaries, sorts and dedupes them, and yields a complete JSON message. It must conform to the spec in `.superpowers/sdd/task-1-brief.md`.

**Tech Stack:** Python 3.11, FastAPI, asyncio, csv, pathlib.

---

### Task 1: Write failing test for MarketDataStreamer

**Files:**
- Create: `backend/tests/test_market_data_streamer.py`

**Interfaces:**
- Consumes: `MarketDataStreamer` class.
- Produces: JSON stream messages.

- [ ] **Step 1: Write test for no files case**
```python
import json
import pytest
from pathlib import Path
from app.services.market_data_streamer import MarketDataStreamer

@pytest.mark.asyncio
async def test_market_data_streamer_no_files(tmp_path: Path):
    streamer = MarketDataStreamer()
    streamer.backtest_dir = tmp_path
    messages = [msg async for msg in streamer.stream()]
    assert len(messages) == 1
    data = json.loads(messages[0])
    assert data["type"] == "error"
    assert "No MarketData CSV" in data["message"]
```

- [ ] **Step 2: Write test for successful streaming**
```python
import json
import pytest
from pathlib import Path
from app.services.market_data_streamer import MarketDataStreamer

@pytest.mark.asyncio
async def test_market_data_streamer_success(tmp_path: Path):
    csv_content = (
        "Time,Open,High,Low,Close,EMA200\n"
        "2020.01.01 00:00:00,100,110,90,105,102\n"
        "2020.01.01 00:01:00,105,112,101,108,103\n"
    )
    csv_path = tmp_path / "MarketData_XAUUSD_M15_2020.csv"
    csv_path.write_text(csv_content, encoding="utf-8")

    streamer = MarketDataStreamer()
    streamer.backtest_dir = tmp_path
    messages = [msg async for msg in streamer.stream(symbol="XAUUSD", timeframe="M15", from_date="2020-01-01", mode="full")]
    parsed = [json.loads(m) for m in messages]
    # progress counting rows
    assert any(p["type"] == "progress" and "Counting rows" in p["step"] for p in parsed)
    rows_progress = next(p for p in parsed if p["type"] == "progress" and "rows total" in p["step"])
    assert rows_progress["total_estimated"] == 2
    complete = next(p for p in parsed if p["type"] == "complete")
    data = complete["data"]
    assert data["symbol"] == "XAUUSD"
    assert data["timeframe"] == "M15"
    assert data["mode"] == "full"
    assert data["total"] == 2
    assert len(data["candles"]) == 2
    # ensure timestamps are sorted
    times = [c["time"] for c in data["candles"]]
    assert times == sorted(times)
    first = data["candles"][0]
    assert first["open"] == 100.0
    assert first["high"] == 110.0
    assert first["low"] == 90.0
    assert first["close"] == 105.0
    assert first["ema200"] == 102.0
```

- [ ] **Step 3: Run pytest to confirm tests fail** (they will fail because `MarketDataStreamer` currently yields an extra progress step and truncates to 250k rows).

---

### Task 2: Adjust MarketDataStreamer implementation

**Files:**
- Modify: `backend/app/services/market_data_streamer.py`

**Interfaces:**
- Consumes: CSV files.
- Produces: Progress and complete JSON strings.

- [ ] **Step 1: Remove extra "Sorting & finalizing..." progress message** (line yielding 100% progress).
- [ ] **Step 2: Ensure candle list truncation matches spec (200,000 rows)**.
- [ ] **Step 3: Keep deduplication logic identical to spec (set‑based unique filter).
- [ ] **Step 4: Run pytest again; tests should now pass.

---

### Task 3: Commit changes

- [ ] `git add backend/app/services/market_data_streamer.py backend/tests/test_market_data_streamer.py docs/superpowers/plans/2026-06-28-market-data-streamer.md`
- [ ] `git commit -m "feat: implement MarketDataStreamer with proper streaming behavior"`

---

### Task 4: Self‑review

- Verify that the class matches the specification.
- Ensure tests cover error case and normal case.
- Confirm no regressions in existing API tests.

---

### Task 5: Write detailed report

- Create: `.superpowers/sdd/task-1-report.md` (see next step).

---

### Execution handoff

**Plan complete and saved to `docs/superpowers/plans/2026-06-28-market-data-streamer.md`.**

**Choose execution option:**
- 1. Subagent‑Driven (recommended) – dispatch subagents for each task.
- 2. Inline Execution – run tasks sequentially in this session.

(Select option as appropriate.)