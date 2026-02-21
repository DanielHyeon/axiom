import pytest
import jwt
from httpx import ASGITransport, AsyncClient
from datetime import datetime, timedelta, timezone
from app.main import app
from app.core.config import settings


def _auth(role: str) -> dict[str, str]:
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": f"user-{role}",
            "tenant_id": "tenant-1",
            "role": role,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=15)).timestamp()),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_weaver_query_endpoint_success():
    payload = {
        "datasource_id": "pg_prod",
        "target_node": "remote.db.server",
        "execution_parameters": {}
    }
    
    headers = _auth("viewer")
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/query", json=payload, headers=headers)
        assert res.status_code == 200
        assert res.json()["status"] == "executed"
        assert res.json()["records_returned"] == 5
        assert len(res.json()["records_preview"]) == 5


@pytest.mark.asyncio
async def test_weaver_query_drops_unsafe_blocklist_targets():
    payload = {
        "datasource_id": "pg_local",
        "target_node": "localhost:5432", # Violates internal mappings
        "execution_parameters": {}
    }
    
    headers = _auth("admin")
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/query", json=payload, headers=headers)
        assert res.status_code == 400
        assert "violates connection blocklist policies" in res.json()["detail"]


@pytest.mark.asyncio
async def test_weaver_query_respects_limit_and_validates_range():
    headers = _auth("admin")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ok = await client.post(
            "/query",
            json={
                "datasource_id": "pg_prod",
                "target_node": "remote.db.server",
                "execution_parameters": {"limit": 3},
            },
            headers=headers,
        )
        assert ok.status_code == 200
        assert ok.json()["records_returned"] == 3
        assert len(ok.json()["records_preview"]) == 3

        bad = await client.post(
            "/query",
            json={
                "datasource_id": "pg_prod",
                "target_node": "remote.db.server",
                "execution_parameters": {"limit": 0},
            },
            headers=headers,
        )
        assert bad.status_code == 422
