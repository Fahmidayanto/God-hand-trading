import pandas as pd
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from valuecell.agents.orchestrator_agent import OrchestratorAgent
from valuecell.knowledge.lance_db import VECTOR_VERSION


def structured_analysis_fields():
    return {
        "facts": ["The deterministic MSA setup is still pending."],
        "interpretation": "Historical evidence must be confirmed by deterministic structure.",
        "recommended_action": "WAIT",
        "win_pattern_characteristics": ["Winning patterns preserved the setup structure."],
        "loss_pattern_characteristics": ["Losing patterns invalidated the setup structure."],
        "current_pattern_comparison": "The current setup remains unconfirmed.",
        "confirmation_conditions": ["A valid BoS confirms the pending direction."],
        "invalidation_conditions": ["The pending structure reference breaks."],
        "counter_scenario": "A failed BoS would weaken or invalidate the setup.",
        "user_explanation": "Wait for deterministic BoS confirmation before action.",
    }


def test_warmup_skipped_on_normal_hold():
    """Test that ML & Sentiment agents are NOT called when MSA returns HOLD without pre_signal."""
    # Initialize Orchestrator
    orchestrator = OrchestratorAgent(
        enable_market_structure=True,
        enable_ml_prediction=True,
        enable_risk_management=True,
        enable_sentiment=True,
        consensus_threshold=0.60
    )

    # Mock agents
    orchestrator.agents["market_structure"].analyze = MagicMock(return_value={
        "signal": "HOLD",
        "confidence": 0.30,
        "reasoning": "Normal neutral state",
        "pre_signal": None
    })
    orchestrator.agents["ml_prediction"].analyze = MagicMock()
    orchestrator.agents["sentiment"].analyze = MagicMock()
    orchestrator.agents["risk_management"].analyze = MagicMock()

    # Dummy market data
    market_data = {
        "df": None,
        "current_bar": {"time": 123456789, "close": 2300.0},
        "session": "London"
    }

    # Run analysis
    result = orchestrator.analyze(market_data, symbol="XAUUSD", timeframe="M15")

    # Assertions
    assert result["final_signal"] == "HOLD"
    assert result["approved"] is False
    orchestrator.agents["ml_prediction"].analyze.assert_not_called()
    orchestrator.agents["sentiment"].analyze.assert_not_called()
    orchestrator.agents["risk_management"].analyze.assert_not_called()


def test_warmup_triggered_on_pending_setup():
    """Test that ML & Sentiment agents ARE called for warmup when MSA returns HOLD with pre_signal."""
    # Initialize Orchestrator
    orchestrator = OrchestratorAgent(
        enable_market_structure=True,
        enable_ml_prediction=True,
        enable_risk_management=True,
        enable_sentiment=True,
        consensus_threshold=0.60
    )

    # Mock agents
    orchestrator.agents["market_structure"].analyze = MagicMock(return_value={
        "signal": "HOLD",
        "confidence": 0.40,
        "reasoning": "CHoCH + HH formed, pending setup",
        "pre_signal": {
            "direction": "Bullish",
            "initial_confidence": 0.40,
            "status": "PENDING_SETUP - menunggu BoS"
        }
    })
    
    # ML prediction mock
    orchestrator.agents["ml_prediction"].analyze = MagicMock(return_value={
        "signal": "BUY",
        "confidence": 0.75,
        "probability": 0.75,
        "reasoning": "ML matches historical structures"
    })
    
    # Sentiment mock
    orchestrator.agents["sentiment"].analyze = MagicMock(return_value={
        "final_signal": "BUY",
        "final_confidence": 0.80,
        "confidence_adjustment": 0.05,
        "filtered": False
    })
    
    orchestrator.agents["risk_management"].analyze = MagicMock()

    # Dummy market data
    market_data = {
        "df": None,
        "current_bar": {"time": 123456789, "close": 2300.0},
        "session": "London"
    }

    # Run analysis
    result = orchestrator.analyze(market_data, symbol="XAUUSD", timeframe="M15")

    # Assertions
    # Final signal must still be HOLD (no real trigger yet)
    assert result["final_signal"] == "HOLD"
    assert result["approved"] is False
    
    # ML & Sentiment should be called for warmup
    orchestrator.agents["ml_prediction"].analyze.assert_called_once()
    # Check that warmup signal is translated to "BUY" (Bullish -> BUY)
    args, kwargs = orchestrator.agents["ml_prediction"].analyze.call_args
    assert kwargs.get("structure_signal") == "BUY"
    
    # Sentiment should be called with warmup info
    orchestrator.agents["sentiment"].analyze.assert_called_once()
    args_sent, kwargs_sent = orchestrator.agents["sentiment"].analyze.call_args
    assert kwargs_sent.get("signal") == "BUY"
    assert kwargs_sent.get("confidence") == 0.40  # from pre_signal initial_confidence in parallel execution
    
    # Risk management should not be called since consensus is HOLD/not approved
    orchestrator.agents["risk_management"].analyze.assert_not_called()


def test_warmup_results_caching_and_reuse():
    """Test that ML & Sentiment results are cached during warmup and reused in subsequent analyses until reset."""
    orchestrator = OrchestratorAgent(
        enable_market_structure=True,
        enable_ml_prediction=True,
        enable_risk_management=True,
        enable_sentiment=True,
        consensus_threshold=0.60
    )

    # Mock agents
    orchestrator.agents["market_structure"].analyze = MagicMock(side_effect=[
        # 1. Warmup initial event (HH)
        {
            "signal": "HOLD",
            "confidence": 0.40,
            "phase": "PENDING_SETUP",
            "pre_signal": {
                "direction": "Bullish",
                "initial_confidence": 0.40,
                "status": "PENDING_SETUP - menunggu BoS"
            }
        },
        # 2. Intermediate event (LL) - still in warmup
        {
            "signal": "HOLD",
            "confidence": 0.40,
            "phase": "PENDING_SETUP",
            "pre_signal": {
                "direction": "Bullish",
                "initial_confidence": 0.40,
                "status": "PENDING_SETUP - menunggu BoS"
            }
        },
        # 3. Reset event - setup invalidated
        {
            "signal": "HOLD",
            "confidence": 0.30,
            "phase": "IDLE",
            "pre_signal": None
        }
    ])

    orchestrator.agents["ml_prediction"].analyze = MagicMock(return_value={
        "signal": "BUY",
        "confidence": 0.75,
        "probability": 0.75,
        "reasoning": "ML matches historical structures"
    })
    orchestrator.agents["sentiment"].analyze = MagicMock(return_value={
        "final_signal": "BUY",
        "final_confidence": 0.80,
        "confidence_adjustment": 0.05,
        "filtered": False
    })
    orchestrator.agents["risk_management"].analyze = MagicMock()

    market_data = {
        "df": None,
        "current_bar": {"time": 123456789, "close": 2300.0},
        "session": "London"
    }

    # First run (HH) - should run ML and Sentiment analysis once
    result1 = orchestrator.analyze(market_data, symbol="XAUUSD", timeframe="M15")
    assert orchestrator._latest_warmup_results is not None
    orchestrator.agents["ml_prediction"].analyze.assert_called_once()
    orchestrator.agents["sentiment"].analyze.assert_called_once()

    # Second run (LL) - should reuse cache, NOT run ML and Sentiment again
    result2 = orchestrator.analyze(market_data, symbol="XAUUSD", timeframe="M15")
    assert orchestrator._latest_warmup_results is not None
    # Call count should still be 1 (meaning it was not called again)
    assert orchestrator.agents["ml_prediction"].analyze.call_count == 1
    assert orchestrator.agents["sentiment"].analyze.call_count == 1

    # Third run (Reset) - should clear the cache
    result3 = orchestrator.analyze(market_data, symbol="XAUUSD", timeframe="M15")
    assert orchestrator._latest_warmup_results is None


def test_llm_msa_shadow_result_is_reported_but_not_counted_in_consensus():
    orchestrator = OrchestratorAgent(
        enable_market_structure=True,
        enable_ml_prediction=False,
        enable_risk_management=False,
        enable_sentiment=False,
        enable_llm_msa=True,
    )
    orchestrator.agents["market_structure"].analyze = MagicMock(return_value={
        "signal": "HOLD",
        "confidence": 0.40,
        "phase": "PENDING_SETUP",
        "is_new_setup": True,
        "pre_signal": {
            "setup_id": "msa-shadow-1",
            "direction": "Bullish",
            "initial_confidence": 0.40,
        },
        "evidence_snapshot": {
            "schema_version": "msa-evidence-v1",
            "setup_id": "msa-shadow-1",
        },
    })
    orchestrator.agents["llm_msa"].analyze = MagicMock(return_value={
        "status": "pending",
        "mode": "SHADOW",
        "setup_id": "msa-shadow-1",
        "verdict": "PENDING",
        "can_affect_consensus": False,
        "can_create_trade_signal": False,
    })

    result = orchestrator.analyze({
        "df": None,
        "current_bar": {"time": 123456789, "close": 2300.0},
        "session": "London",
    })

    assert result["final_signal"] == "HOLD"
    assert result["vote_scores"] == {"BUY": 0.0, "SELL": 0.0, "HOLD": 0.1}
    assert result["agent_results"]["llm_msa"]["status"] == "pending"
    orchestrator.agents["llm_msa"].analyze.assert_called_once_with(
        orchestrator.agents["market_structure"].analyze.return_value["evidence_snapshot"]
    )


def test_llm_msa_completed_cache_is_exposed_on_next_same_setup_analysis():
    orchestrator = OrchestratorAgent(
        enable_market_structure=True,
        enable_ml_prediction=False,
        enable_risk_management=False,
        enable_sentiment=False,
        enable_llm_msa=True,
        llm_msa={
            "evaluator": lambda _evidence: {
                "verdict": "SUPPORT",
                "confidence": 0.81,
                "risk_flags": [],
                "supporting_factors": ["Historical execution edge"],
                "contradicting_factors": [],
                "historical_read": "Supportive",
                "reasoning": "Executed analogs support the pending direction.",
                **structured_analysis_fields(),
            }
        },
    )
    msa_result = {
        "signal": "HOLD",
        "confidence": 0.40,
        "phase": "PENDING_SETUP",
        "is_new_setup": False,
        "pre_signal": {"setup_id": "msa-cache-1", "direction": "Bullish"},
        "evidence_snapshot": {
            "schema_version": "msa-evidence-v1",
            "setup_id": "msa-cache-1",
        },
    }
    orchestrator.agents["market_structure"].analyze = MagicMock(return_value=msa_result)
    market_data = {
        "df": None,
        "current_bar": {"time": 123456789, "close": 2300.0},
        "session": "London",
    }

    first = orchestrator.analyze(market_data)
    assert first["agent_results"]["llm_msa"]["status"] in {"pending", "completed"}

    completed = orchestrator.agents["llm_msa"].wait_for_result("msa-cache-1", timeout=1)
    assert completed["status"] == "completed"

    second = orchestrator.analyze(market_data)
    assert second["agent_results"]["llm_msa"]["status"] == "completed"
    assert second["agent_results"]["llm_msa"]["verdict"] == "SUPPORT"
    assert second["final_signal"] == "HOLD"


def test_replay_pending_setup_reaches_preliminary_judge_with_full_evidence():
    captured_evidence = []

    def evaluator(evidence):
        captured_evidence.append(evidence)
        return {
            "vote": "BUY",
            "verdict": "OPPOSE",
            "confidence": 0.88,
            "data_quality": 0.95,
            "risk_flags": ["Close rejected historical analog"],
            "supporting_factors": ["Bullish structure sequence"],
            "contradicting_factors": ["H4 EMA rejection analog"],
            "historical_read": "A close rejected analog carries H4 EMA risk.",
            "reasoning": "Keep the setup pending until BoS and deterministic filters confirm it.",
            **structured_analysis_fields(),
        }

    orchestrator = OrchestratorAgent(
        enable_market_structure=True,
        enable_ml_prediction=False,
        enable_risk_management=True,
        enable_sentiment=False,
        enable_llm_msa=True,
        market_structure={"use_patterns": False},
        llm_msa={"evaluator": evaluator, "timeout_seconds": 1.0},
    )
    msa = orchestrator.agents["market_structure"]
    msa.use_patterns = True
    msa.pattern_matcher = MagicMock()
    msa.pattern_matcher.find_similar_patterns.return_value = {
        "vector_version": VECTOR_VERSION,
        "patterns": [],
        "win_rate": 1.0,
        "avg_profit": 38.0,
        "total_count": 2,
        "completed_count": 1,
        "recommendation": "NEUTRAL",
        "confidence": 0.5,
        "reasoning": "Mixed executed and rejected evidence.",
        "outcome_distribution": {
            "matches": 2,
            "executed": 1,
            "wins": 1,
            "losses": 0,
            "rejected": 1,
            "pending": 0,
            "executed_win_rate": 1.0,
            "rejection_rate": 0.5,
            "completion_rate": 0.5,
        },
        "net_profit_statistics": {"total": 24.5, "average": 24.5},
        "rejection_analysis": {
            "total_rejected": 1,
            "reason_distribution": [{
                "reason_code": "H4_EMA_FILTER",
                "reason_raw": "H4 EMA Filter",
                "count": 1,
                "share_of_rejections": 1.0,
                "average_similarity": 0.94,
                "max_similarity": 0.94,
            }],
        },
        "top_matches": [
            {
                "id": "executed-win",
                "outcome": "WIN",
                "similarity": 0.96,
                "net_profit": 24.5,
                "reject_reason_code": "NONE",
            },
            {
                "id": "rejected-h4",
                "outcome": "REJECTED",
                "similarity": 0.94,
                "net_profit": None,
                "reject_reason_code": "H4_EMA_FILTER",
                "reject_reason_raw": "H4 EMA Filter",
            },
        ],
    }
    orchestrator.agents["risk_management"].analyze = MagicMock()

    df_m15 = pd.DataFrame({
        "open": [3360.0],
        "high": [3385.0],
        "low": [3355.0],
        "close": [3380.0],
        "ema200": [3350.0],
        "atr": [24.0],
    })
    market_data = {
        "df": df_m15,
        "h1_data": pd.DataFrame({"close": [3380.0], "ema200": [3320.0]}),
        "h4_data": pd.DataFrame({"close": [3380.0], "ema200": [3290.0]}),
        "structure_events": [
            {"time": 1, "type": "LL", "direction": "Update", "price": 3300.0, "timeframe": "M15", "status": "Confirmed"},
            {"time": 2, "type": "CHoCH", "direction": "Bullish", "price": 3340.0, "timeframe": "M15", "status": "Confirmed"},
            {"time": 3, "type": "HH", "direction": "Update", "price": 3378.6, "timeframe": "M15", "status": "Confirmed"},
        ],
        "current_bar": {"time": 3, "close": 3380.0},
        "session": "London",
        "price_ratio": 0.751111,
    }

    first = orchestrator.analyze(market_data)
    setup_id = first["agent_results"]["market_structure"]["pre_signal"]["setup_id"]
    preliminary = orchestrator.agents["llm_msa"].wait_for_result(setup_id, timeout=1)

    assert first["agent_results"]["market_structure"]["phase"] == "PENDING_SETUP"
    assert first["final_signal"] == "HOLD"
    assert first["approved"] is False
    assert preliminary["status"] == "completed"
    assert preliminary["verdict"] == "OPPOSE"
    assert preliminary["can_affect_consensus"] is False
    assert preliminary["can_create_trade_signal"] is False
    assert captured_evidence[0]["vector_version"] == VECTOR_VERSION
    historical = captured_evidence[0]["historical_evidence"]
    assert [match["outcome"] for match in historical["top_matches"]] == ["WIN", "REJECTED"]
    assert historical["top_matches"][0]["net_profit"] == pytest.approx(24.5)
    assert historical["top_matches"][1]["net_profit"] is None
    assert historical["top_matches"][1]["reject_reason_code"] == "H4_EMA_FILTER"
    orchestrator.agents["risk_management"].analyze.assert_not_called()


def test_january_2026_real_choch_hh_reaches_llm_msa_and_reports_to_orchestrator():
    workspace_root = Path(__file__).resolve().parents[4]
    backtest_dir = workspace_root / "Backtest_result"
    captured_evidence = []

    def evaluator(evidence):
        captured_evidence.append(evidence)
        return {
            "vote": "BUY",
            "verdict": "CAUTION",
            "confidence": 0.76,
            "data_quality": 0.82,
            "risk_flags": ["ATR unavailable in exported market data"],
            "supporting_factors": ["Confirmed bullish CHoCH followed by accepted HH"],
            "contradicting_factors": ["Historical evidence unavailable"],
            "historical_read": "No comparable historical pattern was supplied.",
            "reasoning": "Keep the setup pending until deterministic BoS confirmation.",
            **structured_analysis_fields(),
        }

    events = pd.read_csv(
        backtest_dir / "LLHHBOSData_XAUUSD_2026-08-28.csv",
        skiprows=1,
    )
    events = events.loc[
        events["Time"].isin([
            "2025.12.31 08:00:00",
            "2026.01.02 20:30:00",
            "2026.01.05 04:45:00",
            "2026.01.05 17:00:00",
        ])
    ]
    structure_events = [
        {
            "type": row["Type"],
            "direction": row["Direction/Action"],
            "price": row["Price"],
            "time": row["Time"],
            "timeframe": row["Timeframe"],
            "status": row["Status"],
        }
        for _, row in events.iterrows()
    ]

    def market_row(file_name, timestamp):
        frame = pd.read_csv(backtest_dir / file_name)
        row = frame.loc[frame["Time"] == timestamp].copy()
        return row.rename(columns=str.lower).drop(columns=["time"])

    df_m15 = market_row("MarketData_XAUUSD_M15_2026-08-28.csv", "2026.01.05 17:00:00")
    df_h1 = market_row("MarketData_XAUUSD_H1_2026-08-28.csv", "2026.01.05 17:00:00")
    df_h4 = market_row("MarketData_XAUUSD_H4_2026-08-28.csv", "2026.01.05 16:00:00")

    orchestrator = OrchestratorAgent(
        enable_market_structure=True,
        enable_ml_prediction=False,
        enable_risk_management=True,
        enable_sentiment=False,
        enable_llm_msa=True,
        market_structure={"use_patterns": False},
        llm_msa={"evaluator": evaluator, "timeout_seconds": 1.0},
    )
    orchestrator.agents["risk_management"].analyze = MagicMock()
    market_data = {
        "df": df_m15,
        "h1_data": df_h1,
        "h4_data": df_h4,
        "structure_events": structure_events,
        "current_bar": {
            "time": "2026.01.05 17:00:00",
            "close": float(df_m15["close"].iloc[-1]),
        },
        "session": "London",
    }

    first = orchestrator.analyze(market_data)
    setup_id = first["agent_results"]["market_structure"]["pre_signal"]["setup_id"]
    llm_report = orchestrator.agents["llm_msa"].wait_for_result(setup_id, timeout=1)
    reported = orchestrator.analyze(market_data)

    assert first["agent_results"]["market_structure"]["phase"] == "PENDING_SETUP"
    assert first["agent_results"]["market_structure"]["signal"] == "HOLD"
    assert captured_evidence[0]["setup"]["direction"] == "Bullish"
    assert captured_evidence[0]["structure_context"]["trigger_price"] == pytest.approx(4455.65)
    assert captured_evidence[0]["structure_context"]["current_price"] == pytest.approx(4449.25)
    assert captured_evidence[0]["market_context"]["ema200"] == {
        "M15": pytest.approx(4383.81),
        "H1": pytest.approx(4385.56),
        "H4": pytest.approx(4278.88),
    }
    assert llm_report["status"] == "completed"
    assert llm_report["verdict"] == "CAUTION"
    assert llm_report["can_affect_consensus"] is False
    assert llm_report["can_create_trade_signal"] is False
    assert reported["agent_results"]["llm_msa"] == llm_report
    assert reported["final_signal"] == "HOLD"
    assert reported["approved"] is False
    orchestrator.agents["risk_management"].analyze.assert_not_called()

