import inspect
import os

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from valuecell.agents.sentiment_agent import SentimentAgent, SentimentType

class MockAgentRunResponse:
    def __init__(self, content):
        self.content = content

def test_removed_sentiment_providers_are_not_constructor_options():
    parameters = inspect.signature(SentimentAgent).parameters

    for removed in (
        "nineinference_api_key",
        "agentrouter_api_key",
        "iamhc_api_key",
        "nvidia_397b_api_key",
        "nvidia_inkling_api_key",
        "nvidia_glm_api_key",
    ):
        assert removed not in parameters

    for replacement in (
        "nvidia_kimi_k3_api_key",
        "nvidia_deepseek_v4_pro_api_key",
        "nvidia_deepseek_v4_flash_api_key",
    ):
        assert replacement in parameters


@pytest.mark.parametrize(
    ("tier", "model_name"),
    [
        (1, "Groq Qwen 3.6 27B"),
        (2, "NVIDIA Nemotron 120B"),
        (3, "NVIDIA Nemotron 550B"),
        (4, "NVIDIA MiniMax M3"),
        (5, "NVIDIA Kimi K3"),
        (6, "NVIDIA Laguna"),
        (7, "NVIDIA DeepSeek V4 Pro"),
        (8, "NVIDIA DeepSeek V4 Flash"),
        (9, "Gemini 2.5 Flash"),
    ],
)
def test_sentiment_agent_llm_fallback_tiers(tier, model_name):
    agent = SentimentAgent(use_llm=True)

    response = (
        '{"sentiment": "bullish", "score": 0.82, '
        f'"strength": "strong", "reasoning": "{model_name} sentiment"}}'
    )
    run_mock = MagicMock()
    run_mock.side_effect = [Exception("provider offline")] * (tier - 1) + [
        MockAgentRunResponse(response)
    ]

    with patch.dict(os.environ, {"GOOGLE_API_KEY": "mock_key"}):
        with patch("agno.agent.Agent.run", run_mock):
            result = agent.analyze(
                signal="BUY",
                confidence=0.70,
                current_time=datetime.now(),
                news_headlines=["Gold rallies on inflation fears"],
                upcoming_events=[]
            )

    assert result["sentiment"]["type"] == "bullish"
    assert result["sentiment"]["score"] == pytest.approx(0.82)
    assert model_name in result["reasoning"]
    assert run_mock.call_count == tier

def test_sentiment_agent_llm_all_failed_keyword_fallback():
    """Test fallback to keyword-based analysis if all LLMs fail."""
    agent = SentimentAgent(use_llm=True)
    
    run_mock = MagicMock()
    run_mock.side_effect = Exception("All LLM APIs offline")
    
    with patch("agno.agent.Agent.run", run_mock):
        result = agent.analyze(
            signal="BUY",
            confidence=0.70,
            current_time=datetime.now(),
            # "inflation" is bullish in keywords
            news_headlines=["Gold rallies on inflation fears"],
            upcoming_events=[]
        )
        
        # Keyword-based fallback should result in bullish (since 'inflation' matches)
        assert result["sentiment"]["type"] == "bullish"
        assert result["sentiment"]["score"] > 0
        assert "neutral" not in result["sentiment"]["type"]


def test_lancedb_news_cache():
    """Test reading and writing news sentiment cache in LanceDBManager."""
    from valuecell.knowledge.lance_db import LanceDBManager
    import tempfile
    import shutil
    
    # Use a temp directory for LanceDB to avoid modifying production data
    temp_dir = tempfile.mkdtemp()
    try:
        db = LanceDBManager(db_path=temp_dir)
        
        timestamp = "2026-01-23 15:30:00"
        headlines = [{"headline": "Gold spikes to high", "timestamp": "2026-01-23 14:00:00"}]
        events = [{"event": "CPI", "impact": "high", "time": "2026-01-23 16:30:00"}]
        
        # Test write
        success = db.write_news_cache(
            timestamp=timestamp,
            event_type="TEST_HH",
            news_headlines=headlines,
            upcoming_events=events
        )
        assert success is True
        
        # Test read (exact match)
        cached = db.read_news_cache(timestamp)
        assert cached is not None
        assert cached["event_type"] == "TEST_HH"
        assert cached["news_headlines"][0]["headline"] == "Gold spikes to high"
        assert cached["upcoming_events"][0]["event"] == "CPI"
        
        # Test read (date-only fallback match)
        cached_date = db.read_news_cache("2026-01-23 18:45:00")
        assert cached_date is not None
        assert cached_date["event_type"] == "TEST_HH"
        
    finally:
        shutil.rmtree(temp_dir)

