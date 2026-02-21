import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_vision_health():
    response = client.get("/health")
    assert response.status_code == 200

def test_vision_analytics_execute_contract():
    payload = {
        "query": "SELECT * FROM sales",
        "datasource_id": "ds_01"
    }
    response = client.post("/analytics/execute", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"

def test_vision_what_if_scenario_contract():
    payload = {
        "base_query": "SELECT revenue FROM metrics",
        "datasource_id": "ds_02",
        "modifications": [{"metric": "price", "adjustment": "+10%"}]
    }
    response = client.post("/analytics/what-if", json=payload)
    assert response.status_code == 200
    assert "scenario_id" in response.json()
