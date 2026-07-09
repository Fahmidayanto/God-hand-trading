"""Pytest configuration and fixtures."""

import pytest

def pytest_ignore_collect(collection_path, config):
    # Ignore the special 'nul' device file that confuses pytest on Windows
    return getattr(collection_path, "name", None) == "nul"
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_mt5_manager(monkeypatch):
    """Mock MT5Manager for testing."""
    
    class MockMT5Manager:
        """Mock MT5 manager."""
        
        def connect(self):
            return True
        
        def disconnect(self):
            pass
        
        def is_connected(self):
            return True
        
        def get_account_info(self):
            return {
                "login": 12345,
                "server": "Test-Server",
                "name": "Test Account",
                "balance": 10000.0,
                "equity": 10000.0,
                "margin": 0.0,
                "free_margin": 10000.0,
                "margin_level": 0.0,
                "leverage": 100,
                "profit": 0.0,
                "currency": "USD",
            }
        
        def get_candles(self, symbol, timeframe, count):
            return [
                {
                    "time": 1702310400,
                    "open": 4100.0,
                    "high": 4105.0,
                    "low": 4095.0,
                    "close": 4102.0,
                    "volume": 100,
                }
                for _ in range(count)
            ]
        
        def get_positions(self):
            return []
        
        def get_history_deals(self, days):
            return []
    
    from app.core import mt5_manager
    monkeypatch.setattr(mt5_manager, "MT5Manager", MockMT5Manager)
    
    return MockMT5Manager()
