import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_vision_what_if_drops_viewer_roles():
    payload = {
        "base_query": "SELECT *",
        "datasource_id": "ds_1",
        "modifications": []
    }

    # Simulate Viewer token
    headers = {"Authorization": "mock_token_viewer"}
    
    res = client.post("/analytics/what-if", json=payload, headers=headers)
    assert res.status_code == 403
    assert "not permitted" in res.json()["detail"]

def test_vision_what_if_allows_admin_roles():
    payload = {
        "base_query": "SELECT *",
        "datasource_id": "ds_1",
        "modifications": []
    }

    # Simulate Admin token
    headers = {"Authorization": "mock_token_admin"}
    
    res = client.post("/analytics/what-if", json=payload, headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "success"
