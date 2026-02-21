import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest_asyncio.fixture
async def ac():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_health_liveness_probe(ac: AsyncClient):
    response = await ac.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

@pytest.mark.asyncio
async def test_health_readiness_probe(ac: AsyncClient):
    response = await ac.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "synapse_api" in data["checks"]
    assert "target_db" in data["checks"]
    assert "llm" in data["checks"]

@pytest.mark.asyncio
async def test_feedback_submit_endpoint(ac: AsyncClient):
    ask_payload = {
        "question": "Show me everything",
        "datasource_id": "test",
        "options": {"row_limit": 1000},
    }
    ask_res = await ac.post("/text2sql/ask", json=ask_payload)
    query_id = ask_res.json()["data"]["metadata"]["query_id"]
    response = await ac.post(
        "/feedback",
        json={
            "query_id": query_id,
            "rating": "positive",
            "comment": "Nice output",
        },
    )
    assert response.status_code == 200
    assert response.json() == {"success": True}
        
@pytest.mark.asyncio
async def test_query_history_repository_uuid_generation():
    from app.core.query_history import query_history_repo
    record = {
        "tenant_id": "12345678-1234-5678-1234-567812345678",
        "question": "Test",
        "sql": "SELECT 1",
        "datasource_id": "mock_ds",
    }
    
    # Save returns a generated UUID string mock
    rec_id = await query_history_repo.save_query_history(record)
    assert type(rec_id) == str
    assert len(rec_id) > 10 # Check uuid length
