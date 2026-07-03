from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_get_stats():
    response = client.get("/api/v1/database/stats")
    assert response.status_code == 200
    data = response.json()
    assert "neon_stats" in data
    assert "lancedb_active" in data

def test_preview_table_invalid():
    response = client.get("/api/v1/database/neon/preview?table=nonexistent")
    assert response.status_code == 400
