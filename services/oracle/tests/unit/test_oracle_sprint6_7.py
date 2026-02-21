import pytest
from app.core.auth import auth_service, CurrentUser
from app.core.sql_exec import sql_executor
from fastapi.testclient import TestClient
from app.main import app
import uuid

client = TestClient(app)

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

def test_api_text2sql_unauthorized_token_role():
    # If the REST API endpoint denies role directly
    payload = {
        "sql": "SELECT *",
        "datasource_id": "mock"
    }
    # Direct-sql demands 'admin' role, supplying viewer token causes 403 Forbidden
    res = client.post("/text2sql/direct-sql", json=payload, headers={"Authorization": "viewer_1"})
    assert res.status_code == 403
    assert "not permitted" in res.json()["detail"]
    
def test_api_text2sql_pass_roles():
    payload = {
        "sql": "SELECT *",
        "datasource_id": "mock"
    }
    res = client.post("/text2sql/direct-sql", json=payload, headers={"Authorization": "mock_admin"})
    assert res.status_code == 200
    assert res.json()["success"] is True
