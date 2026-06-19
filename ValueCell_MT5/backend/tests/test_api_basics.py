"""Basic API tests."""

def test_root_endpoint(client):
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_dashboard_stats_requires_mt5(client):
    """Test that dashboard stats endpoint exists."""
    response = client.get("/api/v1/dashboard/stats")
    # Will fail if MT5 not connected, but endpoint should exist
    assert response.status_code in [200, 503]


def test_trading_candles_validation(client):
    """Test candles endpoint validation."""
    # Invalid timeframe
    response = client.get("/api/v1/trading/candles?timeframe=INVALID")
    assert response.status_code == 422


def test_agents_consensus_endpoint(client):
    """Test agents consensus endpoint."""
    response = client.get("/api/v1/agents/consensus")
    # Should return data even without MT5
    assert response.status_code == 200
    data = response.json()
    assert "consensus" in data
    assert "agents" in data
