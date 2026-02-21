import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest_asyncio.fixture
async def ac():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_health_live(ac: AsyncClient):
    response = await ac.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"


@pytest.mark.asyncio
async def test_health_check_endpoint(ac: AsyncClient):
    response = await ac.get("/health")
    assert response.status_code == 200
    json_data = response.json()
    assert "status" in json_data
    assert "checks" in json_data
    assert "neo4j" in json_data["checks"]
