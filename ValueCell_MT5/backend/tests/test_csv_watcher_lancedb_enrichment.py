from datetime import datetime, timedelta

from app.services.csv_watcher_service import CSVWatcherService


class FakeLanceDB:
    def __init__(self):
        self.patterns = []
        self.enriched_trades = []
        self.trades = []

    def add_structure_patterns_batch(self, patterns):
        self.patterns.extend(patterns)
        return True

    def enrich_structure_pattern_from_trade(self, trade):
        self.enriched_trades.append(trade)
        return True

    def add_trade_outcomes_batch(self, trades):
        self.trades.extend(trades)
        return True


def _market_rows(start: datetime, *, ema200: float):
    return [
        {
            "time": start + timedelta(minutes=15 * index),
            "open": 2300.0 + index,
            "high": 2302.0 + index,
            "low": 2299.0 + index,
            "close": 2301.0 + index,
            "volume": 100 + index,
            "spread": 20,
            "ema200": ema200,
        }
        for index in range(20)
    ]


def test_live_structure_includes_market_features_without_trigger_distance():
    watcher = CSVWatcherService()
    watcher.lancedb = FakeLanceDB()
    watcher.is_syncing = True
    start = datetime(2026, 8, 28, 8, 0)

    watcher._sync_to_lancedb_from_neondb(_market_rows(start, ema200=2305.0), "marketdata_xauusd_m15")
    watcher._sync_to_lancedb_from_neondb(_market_rows(start, ema200=2300.0), "marketdata_xauusd_h1")
    watcher._sync_to_lancedb_from_neondb(_market_rows(start, ema200=2295.0), "marketdata_xauusd_h4")
    watcher._sync_to_lancedb_from_neondb(
        [{
            "type": "CHoCH",
            "direction_action": "Bullish",
            "time": start + timedelta(minutes=15 * 19),
            "price": 2320.0,
            "timeframe": "M15",
        }],
        "llhhbosdata_xauusd",
    )

    pattern = watcher.lancedb.patterns[0]
    assert pattern["atr"] is not None
    assert pattern["body_ratio"] is not None
    assert pattern["range_atr_ratio"] is not None
    assert pattern["ema200_h1_distance_scaled"] is not None
    assert pattern["ema200_h4_distance_scaled"] is not None
    assert pattern["spread_atr_ratio"] is not None
    assert pattern["volume_ratio"] is not None
    assert pattern["trigger_distance_atr"] is None


def test_market_feature_cache_hydrates_from_latest_csv_and_stays_bounded(tmp_path):
    watcher = CSVWatcherService()
    watcher.backtest_dir = tmp_path
    rows = _market_rows(datetime(2026, 8, 28, 8, 0), ema200=2305.0)
    csv_path = tmp_path / "MarketData_XAUUSD_M15_2026-08-28.csv"
    csv_path.write_text(
        "Time,Open,High,Low,Close,Volume,Spread,EMA200\n"
        + "\n".join(
            f"{row['time']:%Y.%m.%d %H:%M:%S},{row['open']},{row['high']},{row['low']},"
            f"{row['close']},{row['volume']},{row['spread']},{row['ema200']}"
            for row in rows
        ),
        encoding="utf-8",
    )

    watcher._hydrate_market_feature_cache([csv_path])
    watcher._market_feature_rows["M15"].extend(rows * 20)
    watcher.lancedb = FakeLanceDB()
    watcher._sync_to_lancedb_from_neondb([rows[-1]], "marketdata_xauusd_m15")

    assert len(watcher._market_feature_rows["M15"]) == watcher.MARKET_FEATURE_CACHE_LIMIT
    assert watcher._market_feature_rows["M15"][-1]["time"] == rows[-1]["time"]


def test_live_trade_requests_structure_enrichment_and_preserves_rejected_status(monkeypatch):
    watcher = CSVWatcherService()
    watcher.lancedb = FakeLanceDB()
    watcher.is_syncing = True
    monkeypatch.setattr(watcher, "_recalculate_session_patterns", lambda cursor: None)

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def cursor(self):
            return FakeCursor()

    monkeypatch.setattr(
        "app.services.csv_watcher_service.get_db_conn",
        lambda: FakeConnection(),
    )

    entry_time = datetime(2026, 8, 28, 13, 30)
    trade = {
        "ticket": 0,
        "symbol": "XAUUSD",
        "type": "BUY",
        "entry_structure": "REJECTED",
        "entry_price": 2330.0,
        "exit_price": 0.0,
        "net_profit": None,
        "session": "NewYork",
        "entry_time": entry_time,
        "exit_time": None,
        "timeframe": "M15",
        "status": "REJECTED",
        "reject_reason": "H1 EMA filter",
    }

    watcher._sync_to_lancedb_from_neondb([trade], "backtest_results_xauusd")

    enriched = watcher.lancedb.enriched_trades[0]
    assert enriched["outcome"] == "REJECTED"
    assert enriched["net_profit"] is None
    assert enriched["reject_reason_raw"] == "H1 EMA filter"
    assert enriched["entry_structure"] == ""