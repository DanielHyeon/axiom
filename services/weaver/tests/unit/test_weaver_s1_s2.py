import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.adapters import PostgresAdapter
from app.core.schema import GraphSchema, NodeDefinition, PropertyDefinition

client = TestClient(app)

def test_weaver_health():
    response = client.get("/health")
    assert response.status_code == 200

def test_api_datasource_create():
    payload = {
        "name": "primary_db",
        "type": "postgres",
        "connection_config": {"host": "localhost", "port": 5432}
    }
    response = client.post("/datasource", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "created"

def test_api_datasource_sync():
    response = client.post("/datasource/mock_ds_1/sync")
    assert response.status_code == 200
    assert response.json()["status"] == "sync_started"

@pytest.mark.asyncio
async def test_postgres_adapter_mock():
    # Adapter extracts local bindings correctly
    adapter = PostgresAdapter("mock_dsn")
    alive = await adapter.test_connection()
    assert alive is True
    
    schema = await adapter.extract_schema()
    assert "users" in schema["tables"]
    
def test_schema_v2_ownership_models():
    # Validate Pydantic constructs match graph models
    node = NodeDefinition(
        label="User",
        properties=[PropertyDefinition(name="id", type="string")],
        source_table="users_table"
    )
    graph = GraphSchema(nodes=[node], edges=[])
    
    assert graph.version == "2.0"
    assert graph.nodes[0].label == "User"
