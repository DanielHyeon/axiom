import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_vision_what_if_drops_viewer_roles():
    payload = {
        "base_query": "SELECT *",
        "datasource_id": "ds_1",
        "modifications": []
    }

    # Simulate Viewer token
    headers = {"Authorization": "mock_token_viewer"}
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/analytics/what-if", json=payload, headers=headers)
        assert res.status_code == 403
        assert "not permitted" in res.json()["detail"]


@pytest.mark.asyncio
async def test_vision_what_if_allows_admin_roles():
    payload = {
        "base_query": "SELECT *",
        "datasource_id": "ds_1",
        "modifications": []
    }

    # Simulate Admin token
    headers = {"Authorization": "mock_token_admin"}
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/analytics/what-if", json=payload, headers=headers)
        assert res.status_code == 200
        assert res.json()["status"] == "success"
