from datetime import datetime

import pytest

from valuecell.knowledge.lance_db import LanceDBManager, normalize_reject_reason
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