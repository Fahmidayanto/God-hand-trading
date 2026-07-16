import json
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_backtest_chart_data_stream(monkeypatch, tmp_path):
    """Test streaming backtest chart data endpoint returns NDJSON with expected content."""
    # Prepare a minimal CSV file in a temporary directory
    csv_content = (
        "Time,Open,High,Low,Close,EMA200\n"
        "2020.01.01 00:00:00,100,110,90,105,102\n"
        "2020.01.01 00:01:00,105,112,101,108,103\n"
    )
    csv_path = tmp_path / "MarketData_XAUUSD_M15_2020.csv"
    csv_path.write_text(csv_content, encoding="utf-8")

    # Patch MarketDataStreamer to use the temporary CSV directory
    from app.services.market_data_streamer import MarketDataStreamer
    original_init = MarketDataStreamer.__init__

    def patched_init(self):
        original_init(self)
        self.backtest_dir = tmp_path

    monkeypatch.setattr(MarketDataStreamer, "__init__", patched_init)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/trading/chart/backtest-data-stream",
            params={
                "symbol": "XAUUSD",
                "timeframe": "M15",
                "from_date": "2020-01-01",
                "mode": "full",
            },
        )
        assert response.status_code == 200
        # The whole response is read into memory by default
        text = response.text
        lines = [ln for ln in text.splitlines() if ln]
        assert lines, "Expected at least one line in the NDJSON stream"
        parsed = [json.loads(ln) for ln in lines]
        # Expect at least one progress message and a final complete message
        assert any(item["type"] == "progress" for item in parsed)
        complete = next(item for item in parsed if item["type"] == "complete")
        data = complete["data"]
        assert data["symbol"] == "XAUUSD"
        assert data["timeframe"] == "M15"
        assert data["mode"] == "full"
        assert data["total"] == 2
        assert len(data["candles"]) == 2
        first = data["candles"][0]
        assert first["open"] == 100.0
        assert first["high"] == 110.0
        assert first["low"] == 90.0
        assert first["close"] == 105.0
        assert first["ema200"] == 102.0
