import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.core.adapters import PostgresAdapter
from app.core.schema import GraphSchema, NodeDefinition, PropertyDefinition


@pytest.mark.asyncio
async def test_weaver_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        response_live = await client.get("/health/live")
        assert response_live.status_code == 200


@pytest.mark.asyncio
async def test_api_datasource_create():
    payload = {
        "name": "primary_db",
        "type": "postgres",
        "connection_config": {"host": "localhost", "port": 5432}
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/datasource", json=payload)
        assert response.status_code == 200
        assert response.json()["status"] == "created"
        assert response.json()["id"].startswith("ds-")
        assert response.json()["engine"] == "postgresql"


@pytest.mark.asyncio
async def test_api_datasource_sync():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/datasource/mock_ds_1/sync")
        assert response.status_code == 200
        assert response.json()["status"] == "sync_started"
        assert response.json()["datasource_id"] == "mock_ds_1"
        assert response.json()["job_id"].startswith("job-")


@pytest.mark.asyncio
async def test_api_datasource_create_legacy_validation():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        missing_name = await client.post("/datasource", json={"type": "postgres"})
        assert missing_name.status_code == 422
        bad_connection = await client.post("/datasource", json={"name": "x", "connection_config": "bad"})
        assert bad_connection.status_code == 422

@pytest.mark.asyncio
async def test_postgres_adapter_mock():
    # Adapter extracts local bindings correctly
    adapter = PostgresAdapter("mock_dsn")
    alive = await adapter.test_connection()
    assert alive is True
    
    schema = await adapter.extract_schema()
    assert schema["engine"] == "postgresql"
    assert any(table["name"] == "users" for table in schema["tables"])
    users = next(table for table in schema["tables"] if table["name"] == "users")
    assert any(col["name"] == "email" for col in users["columns"])
    
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
