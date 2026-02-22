import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.core.sql_guard import sql_guard


@pytest_asyncio.fixture
async def ac():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_health_live(ac: AsyncClient):
    res = await ac.get("/health/live")
    assert res.status_code == 200
    assert res.json()["status"] == "alive"

def test_sql_guard_blocks_destructive_keywords():
    assert sql_guard.guard_sql("SELECT * FROM foo").status in ["PASS", "FIX"]
    assert sql_guard.guard_sql("DELETE FROM foo").status == "REJECT"
    assert sql_guard.guard_sql("DROP TABLE foo").status == "REJECT"
    assert sql_guard.guard_sql("UPDATE foo SET bar=1").status == "REJECT"

@pytest.mark.asyncio
async def test_text2sql_ask_endpoint(ac: AsyncClient):
    payload = {
        "question": "Show me everything",
        "datasource_id": "ds_business_main",
        "options": {"row_limit": 1000}
    }
    res = await ac.post("/text2sql/ask", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] == True
    assert "data" in data
    assert data["data"]["sql"].startswith("SELECT ")
    assert " FROM " in data["data"]["sql"]
    assert data["data"]["metadata"]["execution_backend"] in ["mock", "weaver"]

@pytest.mark.asyncio
async def test_nl2sql_pipeline_failure_route():
    assert sql_guard.guard_sql("INSERT into foo values (1)").status == "REJECT"
