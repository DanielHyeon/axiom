from __future__ import annotations

import os

import pytest
import jwt
from httpx import ASGITransport, AsyncClient
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.main import app


def _enabled(value: str | None) -> bool:
    if not value:
        return False
    return value.lower() in {"1", "true", "yes", "on"}


def _jwt_headers(*, tenant_id: str, role: str = "admin", sub: str = "user-admin") -> dict[str, str]:
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": sub,
            "tenant_id": tenant_id,
            "role": role,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=30)).timestamp()),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_weaver_external_modes_e2e() -> None:
    if not _enabled(os.getenv("WEAVER_RUN_E2E")):
        pytest.skip("set WEAVER_RUN_E2E=1 to run external integration test")

    required = ["MINDSDB_URL", "POSTGRES_DSN", "NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        pytest.skip(f"missing env for e2e: {', '.join(missing)}")

    # Explicitly enable all external modes for end-to-end verification.
    settings.external_mode = True
    settings.metadata_external_mode = True
    settings.metadata_pg_mode = True
    settings.mindsdb_url = os.environ["MINDSDB_URL"].rstrip("/")
    settings.postgres_dsn = os.environ["POSTGRES_DSN"]
    settings.neo4j_uri = os.environ["NEO4J_URI"]
    settings.neo4j_user = os.environ["NEO4J_USER"]
    settings.neo4j_password = os.environ["NEO4J_PASSWORD"]

    headers = _jwt_headers(tenant_id="tenant-e2e-a", sub="user-admin-a")
    headers_tenant_b = _jwt_headers(tenant_id="tenant-e2e-b", sub="user-admin-b")
    ds_host = os.getenv("WEAVER_E2E_DS_HOST", "sample_pg")
    ds_port = int(os.getenv("WEAVER_E2E_DS_PORT", "5432"))
    ds_database = os.getenv("WEAVER_E2E_DS_DATABASE", "sample_enterprise")
    ds_user = os.getenv("WEAVER_E2E_DS_USER", "sample_user")
    ds_password = os.getenv("WEAVER_E2E_DS_PASSWORD", "sample_password")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1) MindsDB health + datasource create
        status_res = await client.get("/api/query/status", headers=headers)
        assert status_res.status_code == 200
        assert status_res.json()["status"] == "healthy"

        ds_res = await client.post(
            "/api/datasources",
            json={
                "name": "e2e_pg_ds",
                "engine": "postgresql",
                "connection": {
                    "host": ds_host,
                    "port": ds_port,
                    "database": ds_database,
                    "user": ds_user,
                    "password": ds_password,
                },
                "description": "e2e datasource",
            },
            headers=headers,
        )
        assert ds_res.status_code == 201, ds_res.text

        # 2) Query execution through MindsDB
        q_res = await client.post("/api/query", json={"sql": "SELECT 1 as x"}, headers=headers)
        assert q_res.status_code == 200, q_res.text
        assert q_res.json()["success"] is True

        # 3) Snapshot + glossary persistence (PG mode)
        snap_res = await client.post(
            "/api/v1/metadata/cases/case-e2e/datasources/e2e_pg_ds/snapshots",
            json={"description": "e2e snapshot"},
            headers=headers,
        )
        assert snap_res.status_code == 202, snap_res.text
        snapshot_id = snap_res.json()["id"]

        list_snap_res = await client.get(
            "/api/v1/metadata/cases/case-e2e/datasources/e2e_pg_ds/snapshots",
            headers=headers,
        )
        assert list_snap_res.status_code == 200
        assert list_snap_res.json()["total"] >= 1

        term_res = await client.post(
            "/api/v1/metadata/glossary",
            json={"term": "E2E_TERM", "definition": "external mode test", "synonyms": []},
            headers=headers,
        )
        assert term_res.status_code == 201
        term_id = term_res.json()["id"]

        get_term = await client.get(f"/api/v1/metadata/glossary/{term_id}", headers=headers)
        assert get_term.status_code == 200

        # 3-a) tenant isolation checks (cross-tenant read denied / hidden)
        cross_ds_detail = await client.get("/api/datasources/e2e_pg_ds", headers=headers_tenant_b)
        assert cross_ds_detail.status_code == 404

        cross_snap_list = await client.get(
            "/api/v1/metadata/cases/case-e2e/datasources/e2e_pg_ds/snapshots",
            headers=headers_tenant_b,
        )
        assert cross_snap_list.status_code == 200
        assert cross_snap_list.json()["total"] == 0

        cross_term_get = await client.get(f"/api/v1/metadata/glossary/{term_id}", headers=headers_tenant_b)
        assert cross_term_get.status_code == 404

        cross_term_list = await client.get("/api/v1/metadata/glossary", headers=headers_tenant_b)
        assert cross_term_list.status_code == 200
        assert all(item["id"] != term_id for item in cross_term_list.json()["items"])

        stats_res = await client.get("/api/v1/metadata/stats", headers=headers)
        assert stats_res.status_code == 200
        assert stats_res.json()["stats"]["snapshots"] >= 1
        assert stats_res.json()["stats"]["glossary_terms"] >= 1

        stats_res_b = await client.get("/api/v1/metadata/stats", headers=headers_tenant_b)
        assert stats_res_b.status_code == 200
        assert stats_res_b.json()["stats"]["datasources"] == 0
        assert stats_res_b.json()["stats"]["glossary_terms"] == 0

        # 4) Cleanup
        await client.delete(
            f"/api/v1/metadata/cases/case-e2e/datasources/e2e_pg_ds/snapshots/{snapshot_id}",
            headers=headers,
        )
        await client.delete(f"/api/v1/metadata/glossary/{term_id}", headers=headers)
        await client.delete("/api/datasources/e2e_pg_ds", headers=headers)
