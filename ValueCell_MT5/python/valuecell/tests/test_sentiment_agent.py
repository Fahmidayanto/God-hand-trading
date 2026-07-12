import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
import os
from valuecell.agents.sentiment_agent import SentimentAgent, SentimentType

class MockAgentRunResponse:
    def __init__(self, content):
        self.content = content

def test_sentiment_agent_llm_glm_success():
    """Test that SentimentAgent uses AgentRouter GLM-5.2 successfully on first try."""
    agent = SentimentAgent(use_llm=True)
    
    glm_response = '{"sentiment": "bullish", "score": 0.90, "reasoning": "Strong gold demand on inflation (GLM-5.2)"}'
    
    with patch("agno.agent.Agent.run") as mock_run:
        mock_run.return_value = MockAgentRunResponse(glm_response)
        
        result = agent.analyze(
            signal="BUY",
            confidence=0.70,
            current_time=datetime.now(),
            news_headlines=["Gold rallies on inflation fears"],
            upcoming_events=[]
        )
        
        assert result["sentiment"]["type"] == "bullish"
        assert result["sentiment"]["score"] == 0.90
        assert "GLM-5.2" in result["reasoning"]
        mock_run.assert_called_once()

def test_sentiment_agent_llm_qwen397_fallback():
    """Test fallback from GLM-5.2 to Qwen 397B."""
    agent = SentimentAgent(use_llm=True)
    
    qwen397_response = '{"sentiment": "bullish", "score": 0.88, "reasoning": "Qwen 397B sentiment"}'
    
    run_mock = MagicMock()
    run_mock.side_effect = [Exception("GLM-5.2 offline"), MockAgentRunResponse(qwen397_response)]
    
    with patch("agno.agent.Agent.run", run_mock):
        result = agent.analyze(
            signal="BUY",
            confidence=0.70,
            current_time=datetime.now(),
            news_headlines=["Gold rallies on inflation fears"],
            upcoming_events=[]
        )
        
        assert result["sentiment"]["type"] == "bullish"
        assert result["sentiment"]["score"] == 0.88
        assert "Qwen 397B" in result["reasoning"]
        assert run_mock.call_count == 2

def test_sentiment_agent_llm_qwen122_fallback():
    """Test fallback from GLM-5.2, Qwen 397B to Qwen 122B."""
    agent = SentimentAgent(use_llm=True)
    
    qwen122_response = '{"sentiment": "bullish", "score": 0.85, "reasoning": "Qwen 122B sentiment"}'
    
    run_mock = MagicMock()
    run_mock.side_effect = [Exception("GLM-5.2 offline"), Exception("Qwen 397B offline"), MockAgentRunResponse(qwen122_response)]
    
    with patch("agno.agent.Agent.run", run_mock):
        result = agent.analyze(
            signal="BUY",
            confidence=0.70,
            current_time=datetime.now(),
            news_headlines=["Gold rallies on inflation fears"],
            upcoming_events=[]
        )
        
        assert result["sentiment"]["type"] == "bullish"
        assert result["sentiment"]["score"] == 0.85
        assert "Qwen 122B" in result["reasoning"]
        assert run_mock.call_count == 3

def test_sentiment_agent_llm_gemini_fallback():
    """Test fallback from GLM-5.2, Qwen 397B, Qwen 122B to Gemini."""
    agent = SentimentAgent(use_llm=True)
    
    gemini_response = '{"sentiment": "bearish", "score": -0.6, "reasoning": "Strong US dollar pressures gold (Gemini)"}'
    
    run_mock = MagicMock()
    run_mock.side_effect = [
        Exception("GLM-5.2 offline"), 
        Exception("Qwen 397B offline"), 
        Exception("Qwen 122B offline"), 
        MockAgentRunResponse(gemini_response)
    ]
    
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "mock_key"}):
        with patch("agno.agent.Agent.run", run_mock):
            result = agent.analyze(
                signal="BUY",
                confidence=0.70,
                current_time=datetime.now(),
                news_headlines=["Strong economy pressures gold"],
                upcoming_events=[]
            )
            
            assert result["sentiment"]["type"] == "bearish"
            assert result["sentiment"]["score"] == -0.6
            assert "Gemini" in result["reasoning"]
            assert run_mock.call_count == 4

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

