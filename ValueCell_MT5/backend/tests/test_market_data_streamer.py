import json
import pytest
from pathlib import Path
from app.services.market_data_streamer import MarketDataStreamer

@pytest.mark.asyncio
async def test_market_data_streamer_no_files(tmp_path: Path):
    """When no CSV files are present, stream should yield an error message."""
    streamer = MarketDataStreamer()
    streamer.backtest_dir = tmp_path
    messages = [msg async for msg in streamer.stream()]
    assert len(messages) == 1
    data = json.loads(messages[0])
    assert data["type"] == "error"
    assert "No MarketData CSV" in data["message"]

@pytest.mark.asyncio
async def test_market_data_streamer_success(tmp_path: Path):
    """Stream should process CSV files and emit progress and complete messages."""
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

    times = [c["time"] for c in data["candles"]]
    assert times == sorted(times)

    first = data["candles"][0]
    assert first["open"] == 100.0
    assert first["high"] == 110.0
    assert first["low"] == 90.0
    assert first["close"] == 105.0
    assert first["ema200"] == 102.0
