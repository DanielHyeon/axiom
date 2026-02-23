import time
import uuid

import pytest
import pytest_asyncio
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.core.auth import auth_service, CurrentUser
from app.core.config import settings
from app.core.sql_exec import sql_executor
from app.main import app


def _make_access_token(
    user_id: str,
    tenant_id: str,
    role: str,
    permissions: list[str] | None = None,
) -> str:
    """Build a Core-compatible access token for tests (JWT with sub, tenant_id, role, permissions)."""
    now = int(time.time())
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "role": role,
        "permissions": permissions or [],
        "iat": now,
        "exp": now + 900,
    }
    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


@pytest_asyncio.fixture
async def ac():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


def test_auth_service_decodes_tenant_and_roles_safely():
    uid = str(uuid.uuid4())
    tid = str(uuid.uuid4())
    token = _make_access_token(uid, tid, "admin")
    cfg = auth_service.verify_token(token)
    assert cfg.role == "admin"
    assert cfg.user_id == uuid.UUID(uid)
    assert cfg.tenant_id == uuid.UUID(tid)


def test_auth_service_viewer_disallowed():
    uid, tid = str(uuid.uuid4()), str(uuid.uuid4())
    user = auth_service.verify_token(_make_access_token(uid, tid, "viewer"))
    assert user.role == "viewer"
    with pytest.raises(HTTPException) as excinfo:
        auth_service.requires_role(user, ["admin"])
    assert excinfo.value.status_code == 403


@pytest.mark.asyncio
async def test_sql_execution_truncation_simulations():
    uid, tid = str(uuid.uuid4()), str(uuid.uuid4())
    user = auth_service.verify_token(_make_access_token(uid, tid, "admin"))
    res = await sql_executor.execute_sql("SELECT * FROM big", "db_1", user)
    # With mock backend, truncation is not simulated; with weaver, row cap and truncated apply
    assert res.row_count >= 0 and len(res.rows) <= 10000
    if res.backend != "mock":
        assert res.truncated is (res.row_count > 10000)


# Valid datasource_id from default ORACLE_DATASOURCES_JSON (config)
_VALID_DS = "ds_business_main"


@pytest.mark.asyncio
async def test_api_text2sql_unauthorized_token_role(ac: AsyncClient):
    uid, tid = str(uuid.uuid4()), str(uuid.uuid4())
    token = _make_access_token(uid, tid, "viewer")
    payload = {"sql": "SELECT *", "datasource_id": _VALID_DS}
    res = await ac.post(
        "/text2sql/direct-sql",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403
    detail = res.json().get("detail")
    msg = detail.get("message", detail) if isinstance(detail, dict) else detail
    assert "not permitted" in str(msg)


@pytest.mark.asyncio
async def test_api_text2sql_pass_roles(ac: AsyncClient):
    uid, tid = str(uuid.uuid4()), str(uuid.uuid4())
    token = _make_access_token(uid, tid, "admin")
    payload = {"sql": "SELECT *", "datasource_id": _VALID_DS}
    res = await ac.post(
        "/text2sql/direct-sql",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["success"] is True


@pytest.mark.asyncio
async def test_api_text2sql_401_when_no_bearer(ac: AsyncClient):
    payload = {"sql": "SELECT 1", "datasource_id": _VALID_DS}
    res = await ac.post("/text2sql/direct-sql", json=payload)
    assert res.status_code == 401
    detail = res.json().get("detail", "")
    msg = detail.get("message", detail) if isinstance(detail, dict) else detail
    assert "Authorization" in str(msg)
