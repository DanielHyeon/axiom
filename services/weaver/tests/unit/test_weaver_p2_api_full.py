import pytest
import jwt
from httpx import ASGITransport, AsyncClient
from datetime import datetime, timedelta, timezone

from app.main import app
from app.core.config import settings
from app.services.audit_log import audit_log_service
from app.services.mindsdb_client import MindsDBUnavailableError
from app.services.postgres_metadata_store import PostgresStoreUnavailableError
from app.services.weaver_runtime import weaver_runtime


@pytest.fixture(autouse=True)
def clear_runtime() -> None:
    old_external = settings.external_mode
    old_pg = settings.metadata_pg_mode
    old_neo4j = settings.metadata_external_mode
    weaver_runtime.clear()
    audit_log_service.clear()
    try:
        yield
    finally:
        settings.external_mode = old_external
        settings.metadata_pg_mode = old_pg
        settings.metadata_external_mode = old_neo4j


def _auth_headers(role: str = "admin", permissions: list[str] | None = None, tenant_id: str = "tenant-1") -> dict[str, str]:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": f"user-{role}",
        "tenant_id": tenant_id,
        "role": role,
        "permissions": permissions,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=15)).timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return {"Authorization": f"Bearer {token}"}


def _admin_headers() -> dict[str, str]:
    return _auth_headers("admin")


@pytest.mark.asyncio
async def test_datasource_full_contract() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        types_res = await client.get("/api/datasources/types", headers=_admin_headers())
        assert types_res.status_code == 200
        assert len(types_res.json()["types"]) >= 3

        engines_res = await client.get("/api/datasources/supported-engines", headers=_admin_headers())
        assert engines_res.status_code == 200
        assert "postgresql" in engines_res.json()["supported_engines"]

        create_res = await client.post(
            "/api/datasources",
            json={
                "name": "erp_db",
                "engine": "postgresql",
                "connection": {"host": "db", "port": 5432, "database": "erp", "user": "reader", "password": "secret"},
                "description": "erp source",
            },
            headers=_admin_headers(),
        )
        assert create_res.status_code == 201
        assert "password" not in create_res.json()["connection"]

        dup_res = await client.post(
            "/api/datasources",
            json={
                "name": "erp_db",
                "engine": "postgresql",
                "connection": {"host": "db", "database": "erp", "user": "reader", "password": "secret"},
            },
            headers=_admin_headers(),
        )
        assert dup_res.status_code == 409

        list_res = await client.get("/api/datasources", headers=_admin_headers())
        assert list_res.status_code == 200
        assert list_res.json()["total"] == 1

        detail_res = await client.get("/api/datasources/erp_db", headers=_admin_headers())
        assert detail_res.status_code == 200
        assert detail_res.json()["name"] == "erp_db"

        update_res = await client.put(
            "/api/datasources/erp_db/connection",
            json={"host": "new-db", "password": "new-secret"},
            headers=_admin_headers(),
        )
        assert update_res.status_code == 200
        assert update_res.json()["connection"]["host"] == "new-db"
        assert "password" not in update_res.json()["connection"]

        health_res = await client.get("/api/datasources/erp_db/health", headers=_admin_headers())
        assert health_res.status_code == 200
        assert health_res.json()["status"] == "healthy"
        assert "response_time_ms" in health_res.json()
        assert "checked_at" in health_res.json()

        test_res = await client.post("/api/datasources/erp_db/test", headers=_admin_headers())
        assert test_res.status_code == 200
        assert test_res.json()["success"] is True
        assert "response_time_ms" in test_res.json()
        assert "checked_at" in test_res.json()

        schemas_res = await client.get("/api/datasources/erp_db/schemas", headers=_admin_headers())
        assert schemas_res.status_code == 200
        assert "public" in schemas_res.json()["schemas"]

        tables_res = await client.get("/api/datasources/erp_db/tables", params={"schema": "public"}, headers=_admin_headers())
        assert tables_res.status_code == 200
        assert "processes" in tables_res.json()["tables"]

        tables_missing_schema = await client.get(
            "/api/datasources/erp_db/tables",
            params={"schema": "missing"},
            headers=_admin_headers(),
        )
        assert tables_missing_schema.status_code == 404

        schema_res = await client.get("/api/datasources/erp_db/tables/processes/schema", headers=_admin_headers())
        assert schema_res.status_code == 200
        assert schema_res.json()["schema"] == "public"

        schema_missing_table = await client.get("/api/datasources/erp_db/tables/nope/schema", headers=_admin_headers())
        assert schema_missing_table.status_code == 404

        sample_res = await client.get("/api/datasources/erp_db/tables/processes/sample", params={"limit": 3}, headers=_admin_headers())
        assert sample_res.status_code == 200
        assert sample_res.json()["row_count"] == 3

        sample_missing_table = await client.get(
            "/api/datasources/erp_db/tables/nope/sample",
            params={"limit": 3},
            headers=_admin_headers(),
        )
        assert sample_missing_table.status_code == 404

        delete_res = await client.delete("/api/datasources/erp_db", headers=_admin_headers())
        assert delete_res.status_code == 200
        assert delete_res.json()["deleted_metadata"]["schemas"] == 2
        assert delete_res.json()["deleted_metadata"]["tables"] == 4
        assert delete_res.json()["deleted_metadata"]["columns"] == 11
        events = audit_log_service.list_events()
        actions = [e["action"] for e in events]
        assert "datasource.create" in actions
        assert "datasource.update_connection" in actions
        assert "datasource.delete" in actions


@pytest.mark.asyncio
async def test_request_id_middleware_and_audit_propagation() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        health_res = await client.get("/health")
        assert health_res.status_code == 200
        assert health_res.headers.get("X-Request-Id", "").startswith("req-")

        health_res2 = await client.get("/health", headers={"X-Request-Id": "rid-explicit"})
        assert health_res2.status_code == 200
        assert health_res2.headers.get("X-Request-Id") == "rid-explicit"

        create_auto_res = await client.post(
            "/api/datasources",
            json={
                "name": "rid_auto",
                "engine": "postgresql",
                "connection": {"host": "db", "database": "erp", "user": "reader", "password": "secret"},
            },
            headers=_admin_headers(),
        )
        assert create_auto_res.status_code == 201
        assert create_auto_res.headers.get("X-Request-Id", "").startswith("req-")

        create_explicit_res = await client.post(
            "/api/datasources",
            json={
                "name": "rid_explicit",
                "engine": "postgresql",
                "connection": {"host": "db", "database": "erp", "user": "reader", "password": "secret"},
            },
            headers={**_admin_headers(), "X-Request-Id": "rid-expected"},
        )
        assert create_explicit_res.status_code == 201
        assert create_explicit_res.headers.get("X-Request-Id") == "rid-expected"

        create_events = [e for e in audit_log_service.list_events() if e["action"] == "datasource.create"]
        assert len(create_events) == 2
        assert create_events[0]["request_id"].startswith("req-")
        assert create_events[1]["request_id"] == "rid-expected"


@pytest.mark.asyncio
async def test_permission_guard_for_datasource_write() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/datasources",
            json={
                "name": "blocked_for_viewer",
                "engine": "postgresql",
                "connection": {"host": "db", "database": "erp", "user": "reader", "password": "secret"},
            },
            headers=_auth_headers("viewer"),
        )
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_auth_guard_requires_bearer_jwt() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        missing = await client.get("/api/datasources")
        assert missing.status_code == 401
        assert "Authorization" in missing.json()["detail"]

        invalid_scheme = await client.get("/api/datasources", headers={"Authorization": "mock_token_admin"})
        assert invalid_scheme.status_code == 401


@pytest.mark.asyncio
async def test_auth_guard_rejects_invalid_signature() -> None:
    now = datetime.now(timezone.utc)
    wrong_token = jwt.encode(
        {
            "sub": "user-admin",
            "tenant_id": "tenant-1",
            "role": "admin",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=15)).timestamp()),
        },
        "wrong-secret",
        algorithm=settings.jwt_algorithm,
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/datasources", headers={"Authorization": f"Bearer {wrong_token}"})
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_tenant_isolation_for_datasource_and_glossary() -> None:
    tenant_a = _auth_headers("admin", tenant_id="tenant-a")
    tenant_b = _auth_headers("admin", tenant_id="tenant-b")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res_a_create = await client.post(
            "/api/datasources",
            json={
                "name": "shared_name",
                "engine": "postgresql",
                "connection": {"host": "db", "database": "erp", "user": "reader", "password": "secret"},
            },
            headers=tenant_a,
        )
        assert res_a_create.status_code == 201

        res_b_create = await client.post(
            "/api/datasources",
            json={
                "name": "shared_name",
                "engine": "postgresql",
                "connection": {"host": "db", "database": "erp", "user": "reader", "password": "secret"},
            },
            headers=tenant_b,
        )
        assert res_b_create.status_code == 201

        res_a_list = await client.get("/api/datasources", headers=tenant_a)
        res_b_list = await client.get("/api/datasources", headers=tenant_b)
        assert res_a_list.status_code == 200
        assert res_b_list.status_code == 200
        assert res_a_list.json()["total"] == 1
        assert res_b_list.json()["total"] == 1

        term_a = await client.post(
            "/api/v1/metadata/glossary",
            json={"term": "TENANT_A_TERM", "definition": "a", "synonyms": []},
            headers=tenant_a,
        )
        assert term_a.status_code == 201

        list_b = await client.get("/api/v1/metadata/glossary", headers=tenant_b)
        assert list_b.status_code == 200
        assert all(item["term"] != "TENANT_A_TERM" for item in list_b.json()["items"])


@pytest.mark.asyncio
async def test_query_full_contract() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        empty_res = await client.post("/api/query", json={"sql": "   "}, headers=_admin_headers())
        assert empty_res.status_code == 400

        ddl_res = await client.post("/api/query", json={"sql": "DROP TABLE x"}, headers=_admin_headers())
        assert ddl_res.status_code == 400

        ok_res = await client.post("/api/query", json={"sql": "SELECT * FROM x"}, headers=_admin_headers())
        assert ok_res.status_code == 200
        assert ok_res.json()["success"] is True

        status_res = await client.get("/api/query/status", headers=_admin_headers())
        assert status_res.status_code == 200
        assert status_res.json()["status"] == "healthy"
        assert status_res.json()["models_count"] >= 1

        mat_res = await client.post(
            "/api/query/materialized-table",
            json={"table_name": "mat_1", "sql": "SELECT * FROM x", "replace_if_exists": False},
            headers=_admin_headers(),
        )
        assert mat_res.status_code == 201

        conflict_res = await client.post(
            "/api/query/materialized-table",
            json={"table_name": "mat_1", "sql": "SELECT * FROM x", "replace_if_exists": False},
            headers=_admin_headers(),
        )
        assert conflict_res.status_code == 409

        models_res = await client.get("/api/query/models", headers=_admin_headers())
        assert models_res.status_code == 200
        assert any(m["name"] == "process_predictor" for m in models_res.json()["models"])

        jobs_res = await client.get("/api/query/jobs", headers=_admin_headers())
        assert jobs_res.status_code == 200
        assert any(j["name"] == "materialize_mat_1" for j in jobs_res.json()["jobs"])

        kb_res = await client.get("/api/query/knowledge-bases", headers=_admin_headers())
        assert kb_res.status_code == 200
        assert any(k["name"] == "business_process_kb" for k in kb_res.json()["knowledge_bases"])
        events = audit_log_service.list_events()
        actions = [e["action"] for e in events]
        assert "query.execute" in actions
        assert "query.materialize" in actions


@pytest.mark.asyncio
async def test_query_non_external_limit_clause_changes_row_count() -> None:
    settings.external_mode = False
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/api/query", json={"sql": "SELECT * FROM x LIMIT 7"}, headers=_admin_headers())
        assert res.status_code == 200
        body = res.json()
        assert body["row_count"] == 7
        assert len(body["data"]) == 7


@pytest.mark.asyncio
async def test_query_external_error_code_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    settings.external_mode = True

    async def _raise(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise MindsDBUnavailableError("boom")

    from app.services import mindsdb_client as mindsdb_module

    monkeypatch.setattr(mindsdb_module.mindsdb_client, "execute_query", _raise)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/api/query", json={"sql": "SELECT 1"}, headers=_admin_headers())
        assert res.status_code == 503
        detail = res.json()["detail"]
        assert detail["code"] == "MINDSDB_UNAVAILABLE"
        assert detail["service"] == "mindsdb"

    settings.external_mode = False


@pytest.mark.asyncio
async def test_datasource_health_external_unhealthy_is_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    settings.external_mode = True

    async def _health_down(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise MindsDBUnavailableError('connect failed password="db-secret" token=abc')

    from app.services import mindsdb_client as mindsdb_module

    monkeypatch.setattr(mindsdb_module.mindsdb_client, "health_check", _health_down)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_res = await client.post(
            "/api/datasources",
            json={
                "name": "erp_db",
                "engine": "postgresql",
                "connection": {"host": "db", "database": "erp", "user": "reader", "password": "secret"},
            },
            headers=_admin_headers(),
        )
        # external mode create can fail on MindsDB call; fallback registration for health contract
        if create_res.status_code != 201:
            weaver_runtime.create_datasource(
                {
                    "name": "erp_db",
                    "engine": "postgresql",
                    "connection": {"host": "db", "database": "erp", "user": "reader", "password": "secret"},
                },
                storage_key="tenant-1:erp_db",
                display_name="erp_db",
                tenant_id="tenant-1",
            )

        health_res = await client.get("/api/datasources/erp_db/health", headers=_admin_headers())
        assert health_res.status_code == 200
        body = health_res.json()
        assert body["status"] == "unhealthy"
        assert "db-secret" not in body["error"]
        assert "abc" not in body["error"]
        assert "***REDACTED***" in body["error"]

    settings.external_mode = False


@pytest.mark.asyncio
async def test_query_external_error_message_is_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    settings.external_mode = True

    async def _raise(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise MindsDBUnavailableError('upstream password="secret-pass" token=abc123')

    from app.services import mindsdb_client as mindsdb_module

    monkeypatch.setattr(mindsdb_module.mindsdb_client, "execute_query", _raise)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/api/query", json={"sql": "SELECT 1"}, headers=_admin_headers())
        assert res.status_code == 503
        detail = res.json()["detail"]
        assert detail["code"] == "MINDSDB_UNAVAILABLE"
        assert "secret-pass" not in detail["message"]
        assert "abc123" not in detail["message"]
        assert "***REDACTED***" in detail["message"]

    settings.external_mode = False


@pytest.mark.asyncio
async def test_metadata_external_error_message_is_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    settings.metadata_pg_mode = True
    settings.metadata_external_mode = False

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_ds = await client.post(
            "/api/datasources",
            json={
                "name": "erp_db",
                "engine": "postgresql",
                "connection": {"host": "db", "database": "erp", "user": "reader", "password": "secret"},
            },
            headers=_admin_headers(),
        )
        # datasource create may fail in pg mode depending on env; fallback to in-memory registration for this contract test
        if create_ds.status_code != 201:
            weaver_runtime.create_datasource(
                {
                    "name": "erp_db",
                    "engine": "postgresql",
                    "connection": {"host": "db", "database": "erp", "user": "reader", "password": "secret"},
                },
                storage_key="tenant-1:erp_db",
                display_name="erp_db",
                tenant_id="tenant-1",
            )

    async def _raise_pg(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise PostgresStoreUnavailableError("dsn=postgres://u:password=pg-secret@db token=meta-token")

    monkeypatch.setattr("app.api.metadata_catalog.postgres_metadata_store.next_snapshot_version", _raise_pg)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/v1/metadata/cases/case-1/datasources/erp_db/snapshots",
            json={"description": "baseline"},
            headers=_admin_headers(),
        )
        assert res.status_code == 503
        detail = res.json()["detail"]
        assert detail["code"] == "POSTGRES_UNAVAILABLE"
        assert detail["service"] == "postgres"
        assert "pg-secret" not in detail["message"]
        assert "meta-token" not in detail["message"]
        assert "***REDACTED***" in detail["message"]

    settings.metadata_pg_mode = False


@pytest.mark.asyncio
async def test_metadata_catalog_full_contract() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/datasources",
            json={
                "name": "erp_db",
                "engine": "postgresql",
                "connection": {"host": "db", "database": "erp", "user": "reader", "password": "secret"},
            },
            headers=_admin_headers(),
        )

        snap_res = await client.post(
            "/api/v1/metadata/cases/case-1/datasources/erp_db/snapshots",
            json={"description": "baseline"},
            headers={**_admin_headers(), "X-Request-Id": "rid-meta-snapshot"},
        )
        assert snap_res.status_code == 202
        snap_body = snap_res.json()
        assert snap_body["summary"]["schemas"] >= 1
        assert snap_body["summary"]["tables"] >= 1
        assert snap_body["summary"]["columns"] >= 1
        assert isinstance(snap_body["graph_data"]["schemas"], list)
        snapshot_id = snap_res.json()["id"]
        snap_res_2 = await client.post(
            "/api/v1/metadata/cases/case-1/datasources/erp_db/snapshots",
            json={"description": "baseline-2"},
            headers=_admin_headers(),
        )
        assert snap_res_2.status_code == 202

        snaps_res = await client.get("/api/v1/metadata/cases/case-1/datasources/erp_db/snapshots", headers=_admin_headers())
        assert snaps_res.status_code == 200
        assert snaps_res.json()["total"] == 2

        detail_res = await client.get(
            f"/api/v1/metadata/cases/case-1/datasources/erp_db/snapshots/{snapshot_id}", headers=_admin_headers()
        )
        assert detail_res.status_code == 200

        diff_res = await client.get(
            "/api/v1/metadata/cases/case-1/datasources/erp_db/snapshots/diff",
            params={"from": 1, "to": 2},
            headers=_admin_headers(),
        )
        assert diff_res.status_code == 200

        ds = weaver_runtime.datasources["tenant-1:erp_db"]
        ds["catalog"] = {"tmp": {"staging_only": [{"name": "x", "data_type": "varchar", "nullable": True}]}}
        restore_res = await client.post(
            f"/api/v1/metadata/cases/case-1/datasources/erp_db/snapshots/{snapshot_id}/restore", headers=_admin_headers()
        )
        assert restore_res.status_code == 200
        restored_catalog = weaver_runtime.datasources["tenant-1:erp_db"]["catalog"]
        assert "public" in restored_catalog
        assert "tmp" not in restored_catalog

        term_res = await client.post(
            "/api/v1/metadata/glossary",
            json={"term": "ARR", "definition": "annual recurring revenue", "synonyms": ["annual revenue"]},
            headers=_admin_headers(),
        )
        assert term_res.status_code == 201
        term_id = term_res.json()["id"]

        list_term_res = await client.get("/api/v1/metadata/glossary", headers=_admin_headers())
        assert list_term_res.status_code == 200
        assert list_term_res.json()["total"] == 1

        get_term_res = await client.get(f"/api/v1/metadata/glossary/{term_id}", headers=_admin_headers())
        assert get_term_res.status_code == 200

        update_term_res = await client.put(
            f"/api/v1/metadata/glossary/{term_id}", json={"definition": "updated"}, headers=_admin_headers()
        )
        assert update_term_res.status_code == 200

        search_term_res = await client.get("/api/v1/metadata/glossary/search", params={"q": "ARR"}, headers=_admin_headers())
        assert search_term_res.status_code == 200

        add_table_tag = await client.post(
            "/api/v1/metadata/cases/case-1/datasources/erp_db/tables/processes/tags",
            json={"tag": "core"},
            headers=_admin_headers(),
        )
        assert add_table_tag.status_code == 201

        list_table_tag = await client.get(
            "/api/v1/metadata/cases/case-1/datasources/erp_db/tables/processes/tags", headers=_admin_headers()
        )
        assert list_table_tag.status_code == 200

        add_column_tag = await client.post(
            "/api/v1/metadata/cases/case-1/datasources/erp_db/tables/processes/columns/id/tags",
            json={"tag": "pii"},
            headers=_admin_headers(),
        )
        assert add_column_tag.status_code == 201

        list_column_tag = await client.get(
            "/api/v1/metadata/cases/case-1/datasources/erp_db/tables/processes/columns/id/tags",
            headers=_admin_headers(),
        )
        assert list_column_tag.status_code == 200

        entities_by_tag = await client.get("/api/v1/metadata/tags/core/entities", headers=_admin_headers())
        assert entities_by_tag.status_code == 200

        search_res = await client.get("/api/v1/metadata/search", params={"q": "erp"}, headers=_admin_headers())
        assert search_res.status_code == 200

        schemas_res = await client.get("/api/v1/metadata/cases/case-1/datasources/erp_db/schemas", headers=_admin_headers())
        assert schemas_res.status_code == 200
        assert "public" in schemas_res.json()["schemas"]

        tables_res = await client.get(
            "/api/v1/metadata/cases/case-1/datasources/erp_db/schemas/public/tables", headers=_admin_headers()
        )
        assert tables_res.status_code == 200
        assert "processes" in tables_res.json()["tables"]

        tables_missing_schema = await client.get(
            "/api/v1/metadata/cases/case-1/datasources/erp_db/schemas/missing/tables",
            headers=_admin_headers(),
        )
        assert tables_missing_schema.status_code == 404

        cols_res = await client.get(
            "/api/v1/metadata/cases/case-1/datasources/erp_db/schemas/public/tables/processes/columns", headers=_admin_headers()
        )
        assert cols_res.status_code == 200
        assert any(c["name"] == "id" for c in cols_res.json()["columns"])

        cols_missing_table = await client.get(
            "/api/v1/metadata/cases/case-1/datasources/erp_db/schemas/public/tables/nope/columns",
            headers=_admin_headers(),
        )
        assert cols_missing_table.status_code == 404

        ds_stats_res = await client.get("/api/v1/metadata/cases/case-1/datasources/erp_db/stats", headers=_admin_headers())
        assert ds_stats_res.status_code == 200
        assert ds_stats_res.json()["stats"]["schemas"] >= 1
        assert ds_stats_res.json()["stats"]["tables"] >= 1
        assert ds_stats_res.json()["stats"]["columns"] >= 1

        tenant_stats_res = await client.get("/api/v1/metadata/stats", headers=_admin_headers())
        assert tenant_stats_res.status_code == 200

        delete_term_res = await client.delete(f"/api/v1/metadata/glossary/{term_id}", headers=_admin_headers())
        assert delete_term_res.status_code == 200

        del_col_tag = await client.delete(
            "/api/v1/metadata/cases/case-1/datasources/erp_db/tables/processes/columns/id/tags/pii", headers=_admin_headers()
        )
        assert del_col_tag.status_code == 200

        del_table_tag = await client.delete(
            "/api/v1/metadata/cases/case-1/datasources/erp_db/tables/processes/tags/core", headers=_admin_headers()
        )
        assert del_table_tag.status_code == 200

        delete_snapshot = await client.delete(
            f"/api/v1/metadata/cases/case-1/datasources/erp_db/snapshots/{snapshot_id}", headers=_admin_headers()
        )
        assert delete_snapshot.status_code == 200
        actions = [e["action"] for e in audit_log_service.list_events()]
        assert "metadata.snapshot.create" in actions
        assert "metadata.snapshot.delete" in actions
        assert "metadata.glossary.create" in actions
        assert "metadata.glossary.update" in actions
        assert "metadata.glossary.delete" in actions
        snapshot_events = [e for e in audit_log_service.list_events() if e["action"] == "metadata.snapshot.create"]
        assert snapshot_events
        assert snapshot_events[0]["request_id"] == "rid-meta-snapshot"


@pytest.mark.asyncio
async def test_snapshot_diff_dynamic_contract() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_ds = await client.post(
            "/api/datasources",
            json={
                "name": "erp_db",
                "engine": "postgresql",
                "connection": {"host": "db", "database": "erp", "user": "reader", "password": "secret"},
            },
            headers=_admin_headers(),
        )
        assert create_ds.status_code == 201

        snap_v1 = await client.post(
            "/api/v1/metadata/cases/case-1/datasources/erp_db/snapshots",
            json={"description": "v1"},
            headers=_admin_headers(),
        )
        assert snap_v1.status_code == 202

        snap_v2 = await client.post(
            "/api/v1/metadata/cases/case-1/datasources/erp_db/snapshots",
            json={"description": "v2"},
            headers=_admin_headers(),
        )
        assert snap_v2.status_code == 202

        bucket = weaver_runtime.snapshots[("tenant-1", "case-1", "erp_db")]
        v1_id = snap_v1.json()["id"]
        v2_id = snap_v2.json()["id"]
        bucket[v1_id]["graph_data"] = {
            "schemas": [
                {
                    "name": "public",
                    "tables": [
                        {
                            "name": "processes",
                            "columns": [
                                {"name": "id", "dtype": "uuid", "nullable": False},
                                {"name": "name", "dtype": "varchar", "nullable": True},
                            ],
                        },
                        {
                            "name": "legacy",
                            "columns": [
                                {"name": "legacy_code", "dtype": "varchar", "nullable": True},
                            ],
                        },
                    ],
                }
            ]
        }
        bucket[v2_id]["graph_data"] = {
            "schemas": [
                {
                    "name": "public",
                    "tables": [
                        {
                            "name": "processes",
                            "columns": [
                                {"name": "id", "dtype": "uuid", "nullable": False},
                                {"name": "name", "dtype": "text", "nullable": False},
                                {"name": "priority", "dtype": "varchar", "nullable": True},
                            ],
                        },
                        {
                            "name": "audit_logs",
                            "columns": [
                                {"name": "id", "dtype": "uuid", "nullable": False},
                            ],
                        },
                    ],
                }
            ]
        }

        diff_ok = await client.get(
            "/api/v1/metadata/cases/case-1/datasources/erp_db/snapshots/diff",
            params={"from": 1, "to": 2},
            headers=_admin_headers(),
        )
        assert diff_ok.status_code == 200
        body = diff_ok.json()
        assert body["summary"]["tables_added"] == 1
        assert body["summary"]["tables_removed"] == 1
        assert body["summary"]["columns_added"] == 2
        assert body["summary"]["columns_removed"] == 1
        assert body["summary"]["columns_modified"] == 1
        assert any(t["name"] == "audit_logs" for t in body["diff"]["tables_added"])
        assert any(t["name"] == "legacy" for t in body["diff"]["tables_removed"])
        assert any(c["fqn"] == "public.processes.priority" for c in body["diff"]["columns_added"])
        assert any(c["fqn"] == "public.legacy.legacy_code" for c in body["diff"]["columns_removed"])
        assert any(c["fqn"] == "public.processes.name" for c in body["diff"]["columns_modified"])

        diff_bad_range = await client.get(
            "/api/v1/metadata/cases/case-1/datasources/erp_db/snapshots/diff",
            params={"from": 2, "to": 1},
            headers=_admin_headers(),
        )
        assert diff_bad_range.status_code == 400
        assert diff_bad_range.json()["detail"] == "INVALID_VERSION_RANGE"

        diff_missing_ver = await client.get(
            "/api/v1/metadata/cases/case-1/datasources/erp_db/snapshots/diff",
            params={"from": 1, "to": 99},
            headers=_admin_headers(),
        )
        assert diff_missing_ver.status_code == 404
        assert diff_missing_ver.json()["detail"] == "SNAPSHOT_VERSION_NOT_FOUND"
