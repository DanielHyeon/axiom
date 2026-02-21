from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_missing_auth_header():
    # Should be rejected by TenantMiddleware
    response = client.post("/api/v3/synapse/graph/search", json={"query": "test"})
    assert response.status_code == 401
    assert "Missing Authorization" in response.json()["detail"]

def test_health_check_bypasses_auth():
    response = client.get("/health/live")
    assert response.status_code == 200

def test_service_token_auth():
    # Service tokens should bypass JWT tenant check
    response = client.post(
        "/api/v3/synapse/graph/search",
        json={"query": "test"},
        headers={"Authorization": "Bearer local-oracle-token"}
    )
    assert response.status_code == 200
    assert response.json()["success"] == True
