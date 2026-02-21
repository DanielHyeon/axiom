import pytest
import asyncio
from fastapi.testclient import TestClient
from app.main import app
from app.core.sql_guard import sql_guard
from app.pipelines.nl2sql_pipeline import nl2sql_pipeline

client = TestClient(app)

def test_health_live():
    res = client.get("/health/live")
    assert res.status_code == 200
    assert res.json()["status"] == "alive"

def test_sql_guard_blocks_destructive_keywords():
    assert sql_guard.guard_sql("SELECT * FROM foo").status in ["PASS", "FIX"]
    assert sql_guard.guard_sql("DELETE FROM foo").status == "REJECT"
    assert sql_guard.guard_sql("DROP TABLE foo").status == "REJECT"
    assert sql_guard.guard_sql("UPDATE foo SET bar=1").status == "REJECT"

def test_text2sql_ask_endpoint():
    payload = {
        "question": "Show me everything",
        "datasource_id": "test",
        "options": {"row_limit": 1000}
    }
    res = client.post("/text2sql/ask", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] == True
    assert "data" in data
    assert data["data"]["sql"] == "SELECT * FROM sales_records LIMIT 1000"

@pytest.mark.asyncio
async def test_nl2sql_pipeline_failure_route():
    assert sql_guard.guard_sql("INSERT into foo values (1)").status == "REJECT"
