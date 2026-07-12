import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
import os
from valuecell.agents.sentiment_agent import SentimentAgent, SentimentType

class MockAgentRunResponse:
    def __init__(self, content):
        self.content = content

def test_sentiment_agent_llm_deepseek_success():
    """Test that SentimentAgent uses DeepSeek V4 Pro successfully on first try."""
    agent = SentimentAgent(use_llm=True)
    
    ds_response = '{"sentiment": "bullish", "score": 0.90, "reasoning": "Strong gold demand on inflation (DeepSeek)"}'
    
    with patch("agno.agent.Agent.run") as mock_run:
        mock_run.return_value = MockAgentRunResponse(ds_response)
        
        result = agent.analyze(
            signal="BUY",
            confidence=0.70,
            current_time=datetime.now(),
            news_headlines=["Gold rallies on inflation fears"],
            upcoming_events=[]
        )
        
        assert result["sentiment"]["type"] == "bullish"
        assert result["sentiment"]["score"] == 0.90
        assert "DeepSeek" in result["reasoning"]
        mock_run.assert_called_once()

def test_sentiment_agent_llm_qwen397_fallback():
    """Test fallback from DeepSeek to Qwen 397B."""
    agent = SentimentAgent(use_llm=True)
    
    qwen397_response = '{"sentiment": "bullish", "score": 0.88, "reasoning": "Qwen 397B sentiment"}'
    
    run_mock = MagicMock()
    run_mock.side_effect = [Exception("DeepSeek offline"), MockAgentRunResponse(qwen397_response)]
    
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
    """Test fallback from DeepSeek, Qwen 397B to Qwen 122B."""
    agent = SentimentAgent(use_llm=True)
    
    qwen122_response = '{"sentiment": "bullish", "score": 0.85, "reasoning": "Qwen 122B sentiment"}'
    
    run_mock = MagicMock()
    run_mock.side_effect = [Exception("DeepSeek offline"), Exception("Qwen 397B offline"), MockAgentRunResponse(qwen122_response)]
    
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
    """Test fallback from DeepSeek, Qwen 397B, Qwen 122B to Gemini."""
    agent = SentimentAgent(use_llm=True)
    
    gemini_response = '{"sentiment": "bearish", "score": -0.6, "reasoning": "Strong US dollar pressures gold (Gemini)"}'
    
    run_mock = MagicMock()
    run_mock.side_effect = [
        Exception("DeepSeek offline"), 
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
