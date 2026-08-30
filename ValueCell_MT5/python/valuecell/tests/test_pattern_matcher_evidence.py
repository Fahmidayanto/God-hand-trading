from datetime import datetime

import pandas as pd
import pyarrow as pa
import pytest

from valuecell.knowledge.lance_db import LanceDBManager, VECTOR_VERSION, normalize_reject_reason
from valuecell.knowledge.pattern_matcher import PatternMatcher


class FakeLanceDB:
    def __init__(self, patterns):
        self.patterns = patterns
        self.current_pattern = None

    def search_similar_patterns(self, current_pattern, limit, min_similarity):
        self.current_pattern = current_pattern
        return self.patterns


@pytest.mark.parametrize(
    ("raw_reason", "expected_code"),
    [
        ("H1 EMA200 Filter", "H1_EMA200_FILTER"),
        ("H4 EMA Filter", "H4_EMA_FILTER"),
        ("Body Ratio Filter", "BODY_RATIO_FILTER"),
        ("EMA Stretch Filter", "EMA_STRETCH_FILTER"),
        ("Max BOS Cycle", "BOS_CYCLE_LIMIT"),
        ("Session Filter", "SESSION_FILTER"),
        ("Low consensus (45%)", "LOW_CONSENSUS"),
        ("", "UNKNOWN"),
        (None, "UNKNOWN"),
    ],
)
def test_reject_reason_normalization(raw_reason, expected_code):
    assert normalize_reject_reason(raw_reason) == expected_code


def test_rejected_pattern_keeps_reason_and_null_trade_metrics():
    manager = LanceDBManager.__new__(LanceDBManager)

    serialized = manager.prepare_structure_pattern({
        "timestamp": "2026-08-27T10:30:00",
        "symbol": "XAUUSD",
        "timeframe": "M15",
        "event_type": "BoS",
        "direction": "Bullish",
        "price": 3378.6,
        "ema200": 3358.2,
        "outcome": "REJECTED",
        "reject_reason_raw": "H4 EMA Filter",
        "net_profit": None,
        "duration_minutes": None,
        "price_ratio": 0.7508,
    })

    assert serialized["outcome"] == "REJECTED"
    assert serialized["reject_reason_raw"] == "H4 EMA Filter"
    assert serialized["reject_reason_code"] == "H4_EMA_FILTER"
    assert serialized["net_profit"] is None
    assert serialized["duration_minutes"] is None
    assert serialized["price_ratio"] == pytest.approx(0.7508)


def test_structure_pattern_preserves_extended_market_features():
    manager = LanceDBManager.__new__(LanceDBManager)

    serialized = manager.prepare_structure_pattern({
        "timestamp": "2026-08-27T10:30:00",
        "symbol": "XAUUSD",
        "timeframe": "M15",
        "event_type": "BoS",
        "direction": "Bullish",
        "price": 3378.6,
        "ema200": 3358.2,
        "atr": 5.2,
        "body_ratio": 0.68,
        "range_atr_ratio": 0.81,
        "ema200_h1_distance_scaled": 8.1,
        "ema200_h4_distance_scaled": 23.5,
        "spread_atr_ratio": 0.04,
        "volume_ratio": 1.35,
        "trigger_distance_atr": 0.3,
    })

    assert serialized["atr"] == pytest.approx(5.2)
    assert serialized["body_ratio"] == pytest.approx(0.68)
    assert serialized["range_atr_ratio"] == pytest.approx(0.81)
    assert serialized["ema200_h1_distance_scaled"] == pytest.approx(8.1)
    assert serialized["ema200_h4_distance_scaled"] == pytest.approx(23.5)
    assert serialized["spread_atr_ratio"] == pytest.approx(0.04)
    assert serialized["volume_ratio"] == pytest.approx(1.35)
    assert serialized["trigger_distance_atr"] == pytest.approx(0.3)


def test_structure_pattern_keeps_missing_extended_features_nullable():
    manager = LanceDBManager.__new__(LanceDBManager)

    serialized = manager.prepare_structure_pattern({
        "timestamp": "2026-08-27T10:30:00",
        "symbol": "XAUUSD",
        "timeframe": "M15",
        "event_type": "BoS",
        "direction": "Bullish",
        "price": 3378.6,
        "ema200": 3358.2,
    })

    for field in (
        "atr",
        "body_ratio",
        "range_atr_ratio",
        "ema200_h1_distance_scaled",
        "ema200_h4_distance_scaled",
        "spread_atr_ratio",
        "volume_ratio",
        "trigger_distance_atr",
    ):
        assert serialized[field] is None


def test_vector_v2_lite_uses_price_scaling_and_market_context():
    manager = LanceDBManager.__new__(LanceDBManager)

    vector = manager._pattern_to_vector({
        "timestamp": "2026-08-27T10:30:00",
        "event_type": "BoS",
        "direction": "Bullish",
        "price": 2250.0,
        "ema200": 2225.0,
        "session": "London",
        "timeframe": "M15",
        "price_ratio": 0.5,
        "body_ratio": 0.75,
        "range_atr_ratio": 1.5,
        "ema200_h1_distance_scaled": 15.0,
        "ema200_h4_distance_scaled": 30.0,
    })

    assert len(vector) == 16
    assert vector[5] == pytest.approx(1.0)
    assert vector[13] == pytest.approx(0.5)
    assert vector[14] == pytest.approx(0.0)
    assert vector[15] == pytest.approx(0.5)


def test_vector_v2_lite_treats_missing_market_context_as_neutral():
    manager = LanceDBManager.__new__(LanceDBManager)

    vector = manager._pattern_to_vector({
        "timestamp": "2026-08-27T10:30:00",
        "event_type": "BoS",
        "direction": "Bullish",
        "price": 3378.6,
        "ema200": 3358.2,
        "session": "London",
        "timeframe": "M15",
        "price_ratio": 0.7508,
    })

    assert vector[13:16] == [0.0, 0.0, 0.0]


def test_pattern_matcher_forwards_vector_v2_lite_features():
    fake_db = FakeLanceDB([])
    matcher = PatternMatcher(db_manager=fake_db)

    matcher.find_similar_patterns(
        event_type="BoS",
        direction="Bullish",
        price=3378.6,
        ema200=3358.2,
        session="London",
        timestamp="2026-08-27T10:30:00",
        price_ratio=0.7508,
        body_ratio=0.68,
        range_atr_ratio=0.81,
        ema200_h1_distance_scaled=8.1,
        ema200_h4_distance_scaled=23.5,
    )

    assert fake_db.current_pattern["body_ratio"] == pytest.approx(0.68)
    assert fake_db.current_pattern["range_atr_ratio"] == pytest.approx(0.81)
    assert fake_db.current_pattern["ema200_h1_distance_scaled"] == pytest.approx(8.1)
    assert fake_db.current_pattern["ema200_h4_distance_scaled"] == pytest.approx(23.5)


def test_historical_structure_schema_migration_adds_nullable_market_fields_once():
    class FakeTable:
        def __init__(self):
            self.schema = pa.schema([pa.field("id", pa.string())])
            self.added_fields = []

        def add_columns(self, fields):
            self.added_fields.extend(fields)
            self.schema = pa.schema([*self.schema, *fields])

    manager = LanceDBManager.__new__(LanceDBManager)
    table = FakeTable()

    manager._ensure_historical_structures_schema(table)
    manager._ensure_historical_structures_schema(table)

    assert [field.name for field in table.added_fields] == [
        "atr",
        "body_ratio",
        "range_atr_ratio",
        "ema200_h1_distance_scaled",
        "ema200_h4_distance_scaled",
        "spread_atr_ratio",
        "volume_ratio",
        "trigger_distance_atr",
        "entry_time",
        "entry_price",
        "exit_time",
        "exit_price",
        "close_reason",
    ]
    assert all(
        field.type == pa.float64()
        for field in table.added_fields[:8]
    )
    assert [field.type for field in table.added_fields[8:]] == [
        pa.string(),
        pa.float64(),
        pa.string(),
        pa.float64(),
        pa.string(),
    ]
    assert all(field.nullable for field in table.added_fields)


def test_trade_enrichment_updates_latest_matching_structure(tmp_path):
    manager = LanceDBManager(str(tmp_path / "lancedb"))
    assert manager.db.open_table("historical_structures").count_rows() == 0

    manager.add_structure_patterns_batch([
        {
            "timestamp": "2026-08-28T12:45:00",
            "symbol": "XAUUSD",
            "timeframe": "M15",
            "event_type": "CHoCH",
            "direction": "Bullish",
            "price": 2320.0,
            "ema200": 2300.0,
            "session": "London",
            "atr": 5.0,
        },
        {
            "timestamp": "2026-08-28T13:15:00",
            "symbol": "XAUUSD",
            "timeframe": "M15",
            "event_type": "CHoCH",
            "direction": "Bullish",
            "price": 2325.0,
            "ema200": 2300.0,
            "session": "NewYork",
            "atr": 5.0,
        },
    ])

    assert manager.enrich_structure_pattern_from_trade({
        "entry_time": datetime.fromisoformat("2026-08-28T13:30:00"),
        "timeframe": "M15",
        "type": "BUY",
        "entry_structure": "CHoCH",
        "entry_price": 2330.0,
        "outcome": "REJECTED",
        "net_profit": None,
        "profit_pips": 0.0,
        "duration_minutes": None,
        "reject_reason_raw": "H1 EMA200 Filter",
    })

    rows = manager.db.open_table("historical_structures").to_pandas()
    enriched = rows.loc[rows["timestamp"] == "2026-08-28T13:15:00"].iloc[0]
    untouched = rows.loc[rows["timestamp"] == "2026-08-28T12:45:00"].iloc[0]
    assert enriched["outcome"] == "REJECTED"
    assert enriched["net_profit"] is None or pd.isna(enriched["net_profit"])
    assert enriched["reject_reason_code"] == "H1_EMA200_FILTER"
    assert enriched["trigger_distance_atr"] == pytest.approx(1.0)
    assert untouched["outcome"] == "PENDING"


def test_trade_enrichment_preserves_loss_entry_exit_facts(tmp_path):
    manager = LanceDBManager(str(tmp_path / "lancedb"))
    manager.add_structure_pattern({
        "timestamp": "2026-01-06T16:30:00",
        "symbol": "XAUUSD",
        "timeframe": "M15",
        "event_type": "BoS",
        "direction": "Bullish",
        "price": 4475.0,
        "ema200": 4450.0,
        "session": "NewYork",
    })

    assert manager.enrich_structure_pattern_from_trade({
        "entry_time": datetime.fromisoformat("2026-01-06T16:45:00"),
        "exit_time": datetime.fromisoformat("2026-01-07T15:06:57"),
        "timeframe": "M15",
        "type": "BUY",
        "entry_structure": "BoS",
        "entry_price": 4479.57,
        "exit_price": 4438.61,
        "outcome": "LOSS",
        "net_profit": -206.23,
        "profit_pips": -409.6,
        "duration_minutes": 1341,
        "close_reason": "STOP_LOSS",
    })

    enriched = manager.db.open_table("historical_structures").to_pandas().iloc[0]
    assert enriched["entry_time"] == "2026-01-06T16:45:00"
    assert enriched["entry_price"] == pytest.approx(4479.57)
    assert enriched["exit_time"] == "2026-01-07T15:06:57"
    assert enriched["exit_price"] == pytest.approx(4438.61)
    assert enriched["close_reason"] == "STOP_LOSS"
    assert enriched["net_profit"] == pytest.approx(-206.23)


def test_fresh_historical_collection_supports_vector_search(tmp_path):
    manager = LanceDBManager(str(tmp_path / "lancedb"))
    manager.add_structure_pattern({
        "timestamp": "2026-01-06T16:30:00",
        "symbol": "XAUUSD",
        "timeframe": "M15",
        "event_type": "BoS",
        "direction": "Bullish",
        "price": 4475.0,
        "ema200": 4450.0,
        "session": "NewYork",
    })

    matches = manager.search_similar_patterns({
        "timestamp": "2026-01-06T16:45:00",
        "symbol": "XAUUSD",
        "timeframe": "M15",
        "event_type": "BoS",
        "direction": "Bullish",
        "price": 4479.57,
        "ema200": 4450.0,
        "session": "NewYork",
    })

    assert len(matches) == 1


def test_empty_pattern_evidence_keeps_stable_contract():
    matcher = PatternMatcher(db_manager=FakeLanceDB([]))

    result = matcher.find_similar_patterns(
        event_type="BoS",
        direction="Bearish",
        price=3378.6,
        ema200=3390.0,
        session="NewYork",
        timestamp="2026-08-27T14:30:00",
    )

    assert result["outcome_distribution"] == {
        "matches": 0,
        "executed": 0,
        "wins": 0,
        "losses": 0,
        "rejected": 0,
        "pending": 0,
        "executed_win_rate": 0.0,
        "rejection_rate": 0.0,
        "completion_rate": 0.0,
    }
    assert result["net_profit_statistics"] == {"total": 0.0, "average": 0.0}
    assert result["vector_version"] == VECTOR_VERSION
    assert result["rejection_analysis"] == {
        "total_rejected": 0,
        "reason_distribution": [],
    }
    assert result["top_matches"] == []


def test_pattern_evidence_uses_market_time_and_preserves_rejection_reasons():
    patterns = [
        {
            "id": "win-1",
            "timestamp": "2025-08-14T10:15:00",
            "outcome": "WIN",
            "net_profit": 34.2,
            "profit_pips": 42.0,
            "similarity": 0.87,
            "duration_minutes": 75,
            "reject_reason_raw": None,
            "reject_reason_code": "NONE",
        },
        {
            "id": "loss-1",
            "timestamp": "2025-09-10T10:30:00",
            "outcome": "LOSS",
            "net_profit": -12.4,
            "profit_pips": -18.0,
            "similarity": 0.81,
            "duration_minutes": 40,
            "reject_reason_raw": None,
            "reject_reason_code": "NONE",
        },
        {
            "id": "reject-h4",
            "timestamp": "2025-10-02T10:00:00",
            "outcome": "REJECTED",
            "net_profit": None,
            "profit_pips": 0.0,
            "similarity": 0.91,
            "duration_minutes": None,
            "reject_reason_raw": "H4 EMA Filter",
            "reject_reason_code": "H4_EMA_FILTER",
        },
        {
            "id": "pending-1",
            "timestamp": "2025-11-06T10:45:00",
            "outcome": "PENDING",
            "net_profit": None,
            "profit_pips": 0.0,
            "similarity": 0.76,
            "duration_minutes": None,
            "reject_reason_raw": None,
            "reject_reason_code": "NONE",
        },
    ]
    fake_db = FakeLanceDB(patterns)
    matcher = PatternMatcher(db_manager=fake_db)
    market_time = datetime.fromisoformat("2026-08-27T10:30:00")

    result = matcher.find_similar_patterns(
        event_type="BoS",
        direction="Bullish",
        price=3378.6,
        ema200=3358.2,
        session="London",
        timestamp=market_time,
        price_ratio=0.7508,
    )

    assert fake_db.current_pattern["timestamp"] == market_time.isoformat()
    assert fake_db.current_pattern["price_ratio"] == pytest.approx(0.7508)
    assert result["vector_version"] == VECTOR_VERSION
    assert result["outcome_distribution"] == {
        "matches": 4,
        "executed": 2,
        "wins": 1,
        "losses": 1,
        "rejected": 1,
        "pending": 1,
        "executed_win_rate": 0.5,
        "rejection_rate": 0.25,
        "completion_rate": 0.5,
    }
    assert result["net_profit_statistics"] == {
        "total": pytest.approx(21.8),
        "average": pytest.approx(10.9),
    }
    assert result["rejection_analysis"]["reason_distribution"] == [
        {
            "reason_code": "H4_EMA_FILTER",
            "reason_raw": "H4 EMA Filter",
            "count": 1,
            "share_of_rejections": 1.0,
            "average_similarity": pytest.approx(0.91),
            "max_similarity": pytest.approx(0.91),
        }
    ]
    assert result["top_matches"][0]["id"] == "reject-h4"
    assert result["top_matches"][0]["reject_reason_code"] == "H4_EMA_FILTER"
    assert result["top_matches"][0]["net_profit"] is None


def test_top_three_matches_include_numeric_similarity_breakdown():
    patterns = [{
        "id": "loss-nearest",
        "timestamp": "2026-03-10T10:30:00",
        "event_type": "BoS",
        "direction": "Bullish",
        "price": 5186.0,
        "ema200": 5110.0,
        "price_ratio": 1.1524,
        "session": "London",
        "timeframe": "M15",
        "prior_choch": True,
        "body_ratio": 0.61,
        "range_atr_ratio": 1.31,
        "ema200_h1_distance_scaled": 18.0,
        "ema200_h4_distance_scaled": 42.0,
        "outcome": "LOSS",
        "similarity": 0.9387,
        "net_profit": -97.0,
    }]
    matcher = PatternMatcher(db_manager=FakeLanceDB(patterns))

    result = matcher.find_similar_patterns(
        event_type="BoS",
        direction="Bullish",
        price=4455.65,
        ema200=4383.81,
        session="London",
        timeframe="M15",
        timestamp="2026-01-05T17:00:00",
        price_ratio=0.9901,
        prior_choch=True,
        body_ratio=0.6626,
        range_atr_ratio=None,
        ema200_h1_distance_scaled=70.09,
        ema200_h4_distance_scaled=176.77,
    )

    breakdown = result["top_matches"][0]["similarity_breakdown"]
    assert breakdown["total_similarity"] == pytest.approx(0.9387)
    assert breakdown["method"] == "vector-v2-lite-squared-l2"
    assert len(breakdown["factors"]) == 10
    assert breakdown["factors"][0] == {
        "factor": "event_structure",
        "current_value": "BoS",
        "historical_value": "BoS",
        "vector_distance": pytest.approx(0.0),
        "factor_similarity": pytest.approx(1.0),
        "distance_contribution": pytest.approx(0.0),
        "available": True,
    }
    range_factor = next(
        item for item in breakdown["factors"] if item["factor"] == "range_atr_ratio"
    )
    assert range_factor["current_value"] is None
    assert range_factor["historical_value"] == pytest.approx(1.31)
    assert range_factor["available"] is False
    assert result["top_matches"][0]["similarity_breakdown_rank"] == 1


def test_pattern_evidence_weights_executed_outcomes_and_summarizes_win_loss_groups():
    patterns = [
        {
            "id": "win-close",
            "outcome": "WIN",
            "similarity": 0.90,
            "net_profit": 80.0,
            "profit_pips": 50.0,
            "ema_distance": 12.0,
            "range_atr_ratio": 1.20,
            "session": "London",
            "timeframe": "M15",
        },
        {
            "id": "win-far",
            "outcome": "WIN",
            "similarity": 0.60,
            "net_profit": 20.0,
            "profit_pips": 15.0,
            "ema_distance": 8.0,
            "range_atr_ratio": 0.80,
            "session": "London",
            "timeframe": "M15",
        },
        {
            "id": "loss-close",
            "outcome": "LOSS",
            "similarity": 0.80,
            "net_profit": -30.0,
            "profit_pips": -20.0,
            "ema_distance": 3.0,
            "range_atr_ratio": 0.50,
            "session": "London",
            "timeframe": "M15",
        },
        {
            "id": "rejected",
            "outcome": "REJECTED",
            "similarity": 0.99,
            "net_profit": None,
            "profit_pips": 0.0,
            "session": "London",
            "timeframe": "M15",
        },
    ]

    result = PatternMatcher(db_manager=FakeLanceDB(patterns)).find_similar_patterns(
        event_type="BoS",
        direction="Bullish",
        price=3378.6,
        ema200=3358.2,
        session="London",
        timeframe="M15",
    )

    assert result["weighted_statistics"] == {
        "executed_similarity_weight": pytest.approx(2.30),
        "winning_similarity_weight": pytest.approx(1.50),
        "weighted_win_rate": pytest.approx(1.50 / 2.30),
        "average_executed_similarity": pytest.approx(2.30 / 3),
    }
    assert result["outcome_characteristics"]["wins"] == {
        "count": 2,
        "average_similarity": pytest.approx(0.75),
        "average_net_profit": pytest.approx(50.0),
        "average_ema_distance": pytest.approx(10.0),
        "average_range_atr_ratio": pytest.approx(1.0),
    }
    assert result["outcome_characteristics"]["losses"] == {
        "count": 1,
        "average_similarity": pytest.approx(0.80),
        "average_net_profit": pytest.approx(-30.0),
        "average_ema_distance": pytest.approx(3.0),
        "average_range_atr_ratio": pytest.approx(0.50),
    }