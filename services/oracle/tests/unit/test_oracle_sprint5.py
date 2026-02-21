import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_liveness_probe():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_health_readiness_probe():
    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "synapse_api" in data["checks"]
    assert "target_db" in data["checks"]
    assert "llm" in data["checks"]

def test_feedback_submit_endpoint():
    payload = {
        "query_id": "mock_123_uuid",
        "rating": "positive",
        "comment": "Nice output"
    }
    response = client.post("/feedback", json=payload)
    assert response.status_code == 200
    assert response.json() == {"success": True}
        
@pytest.mark.asyncio
async def test_query_history_repository_uuid_generation():
    from app.core.query_history import query_history_repo
    record = {"question": "Test", "datasource_id": "mock_ds"}
    
    # Save returns a generated UUID string mock
    rec_id = await query_history_repo.save_query_history(record)
    assert type(rec_id) == str
    assert len(rec_id) > 10 # Check uuid length
