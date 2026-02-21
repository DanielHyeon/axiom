import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_vision_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_vision_analytics_execute_contract():
    payload = {
        "query": "SELECT * FROM sales",
        "datasource_id": "ds_01"
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/analytics/execute", json=payload)
        assert response.status_code == 200
        assert response.json()["status"] == "success"


@pytest.mark.asyncio
async def test_vision_what_if_scenario_contract():
    payload = {
        "base_query": "SELECT revenue FROM metrics",
        "datasource_id": "ds_02",
        "modifications": [{"metric": "price", "adjustment": "+10%"}]
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/analytics/what-if", json=payload)
        assert response.status_code == 200
        assert "scenario_id" in response.json()
