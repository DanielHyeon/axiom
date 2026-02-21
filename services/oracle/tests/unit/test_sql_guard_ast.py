import pytest
import pytest_asyncio
from app.core.sql_guard import sql_guard, GuardConfig
from app.main import app
from httpx import ASGITransport, AsyncClient


@pytest_asyncio.fixture
async def ac():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

def test_sql_guard_ast_auto_limit():
    sql = "SELECT * FROM sales_records"
    cfg = GuardConfig(row_limit=50)
    res = sql_guard.guard_sql(sql, cfg)
    assert res.status == "FIX"
    assert "LIMIT 50" in res.sql
    assert len(res.fixes) == 1

def test_sql_guard_ast_deep_joins():
    sql = "SELECT * FROM a JOIN b ON a.x=b.x JOIN c ON b.x=c.x JOIN d ON c.x=d.x JOIN e ON d.x=e.x JOIN f ON e.x=f.x JOIN g ON f.x=g.x"
    res = sql_guard.guard_sql(sql)
    assert res.status == "REJECT"
    assert any("JOIN 깊이 초과" in v for v in res.violations)

def test_sql_guard_ast_deep_subqueries():
    sql = "SELECT * FROM (SELECT * FROM (SELECT * FROM (SELECT * FROM (SELECT * FROM t))))"
    res = sql_guard.guard_sql(sql)
    assert res.status == "REJECT"
    assert any("서브쿼리" in v for v in res.violations)

@pytest.mark.asyncio
async def test_text2sql_api_pydantic_validation(ac: AsyncClient):
    payload = {
        "question": "A", # Too short, requires 2+ chars
        "datasource_id": "test"
    }
    res = await ac.post("/text2sql/ask", json=payload)
    # FastApi pydantic validation should return 422 Unprocessable Entity
    assert res.status_code == 422

@pytest.mark.asyncio
async def test_text2sql_api_valid_payload(ac: AsyncClient):
    payload = {
        "question": "Show me everything",
        "datasource_id": "test",
        "options": {
            "row_limit": 50
        }
    }
    res = await ac.post("/text2sql/ask", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] == True
    assert data["data"]["metadata"]["guard_status"] == "FIX"
    assert "LIMIT 50" in " ".join(data["data"]["metadata"]["guard_fixes"])
