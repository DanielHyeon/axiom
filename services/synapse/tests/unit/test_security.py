import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest_asyncio.fixture
async def ac():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_missing_auth_header(ac: AsyncClient):
    response = await ac.post("/api/v3/synapse/graph/search", json={"query": "test"})
    assert response.status_code == 401
    assert "Missing Authorization" in response.json()["detail"]


@pytest.mark.asyncio
async def test_health_check_bypasses_auth(ac: AsyncClient):
    response = await ac.get("/health/live")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_service_token_auth(ac: AsyncClient):
    response = await ac.post(
        "/api/v3/synapse/graph/search",
        json={"query": "test"},
        headers={"Authorization": "Bearer local-oracle-token"},
    )
    assert response.status_code == 200
    assert response.json()["success"] is True
