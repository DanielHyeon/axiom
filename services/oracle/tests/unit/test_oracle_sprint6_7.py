import pytest
from app.core.auth import auth_service, CurrentUser
from app.core.sql_exec import sql_executor
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from app.main import app
import uuid


@pytest_asyncio.fixture
async def ac():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

def test_auth_service_decodes_tenant_and_roles_safely():
    # Token extraction resolving valid objects
    cfg = auth_service.verify_token("mock_admin_token")
    assert cfg.role == "admin"
    assert type(cfg.tenant_id) == uuid.UUID

def test_auth_service_viewer_disallowed():
    user = auth_service.verify_token("viewer_123")
    assert user.role == "viewer"
    
    from fastapi import HTTPException
    # Asserting error thrown directly by python role manager
    with pytest.raises(HTTPException) as excinfo:
        auth_service.requires_role(user, ["admin"])
    assert excinfo.value.status_code == 403

@pytest.mark.asyncio
async def test_sql_execution_truncation_simulations():
    user = auth_service.verify_token("mock")
    # Execute query hitting local max 10,000 caps natively
    res = await sql_executor.execute_sql("SELECT * FROM big", "db_1", user)
    
    assert res.truncated is True
    assert res.row_count > 10000 
    assert len(res.rows) == 10000 # Formally clamped locally 

@pytest.mark.asyncio
async def test_api_text2sql_unauthorized_token_role(ac: AsyncClient):
    # If the REST API endpoint denies role directly
    payload = {
        "sql": "SELECT *",
        "datasource_id": "mock"
    }
    # Direct-sql demands 'admin' role, supplying viewer token causes 403 Forbidden
    res = await ac.post("/text2sql/direct-sql", json=payload, headers={"Authorization": "viewer_1"})
    assert res.status_code == 403
    assert "not permitted" in res.json()["detail"]
    
@pytest.mark.asyncio
async def test_api_text2sql_pass_roles(ac: AsyncClient):
    payload = {
        "sql": "SELECT *",
        "datasource_id": "mock"
    }
    res = await ac.post("/text2sql/direct-sql", json=payload, headers={"Authorization": "mock_admin"})
    assert res.status_code == 200
    assert res.json()["success"] is True
