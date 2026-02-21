import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_weaver_query_endpoint_success():
    payload = {
        "datasource_id": "pg_prod",
        "target_node": "remote.db.server",
        "execution_parameters": {}
    }
    
    headers = {"Authorization": "mock_token_viewer"}
    
    res = client.post("/query", json=payload, headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "executed"

def test_weaver_query_drops_unsafe_blocklist_targets():
    payload = {
        "datasource_id": "pg_local",
        "target_node": "localhost:5432", # Violates internal mappings
        "execution_parameters": {}
    }
    
    headers = {"Authorization": "mock_token_admin"}
    
    res = client.post("/query", json=payload, headers=headers)
    assert res.status_code == 400
    assert "violates connection blocklist policies" in res.json()["detail"]
