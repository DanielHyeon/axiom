import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_live():
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"

def test_health_check_endpoint():
    # Calling the endpoint without auth
    response = client.get("/health")
    assert response.status_code == 200
    # status could be degraded if neo4j is not running locally, but it should return 200 OK.
    json_data = response.json()
    assert "status" in json_data
    assert "checks" in json_data
    assert "neo4j" in json_data["checks"]
