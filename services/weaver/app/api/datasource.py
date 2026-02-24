from __future__ import annotations

import json
from datetime import datetime, timezone
import re
import time
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.auth import CurrentUser, auth_service
from app.core.config import settings
from app.core.error_codes import external_service_http_exception, public_error_message
from app.services.audit_log import audit_log_service
from app.services.introspection_service import extract_metadata_stream
from app.services.mindsdb_client import MindsDBUnavailableError, mindsdb_client
from app.services.synapse_metadata_client import SynapseMetadataClientError, synapse_metadata_client
from app.services.postgres_metadata_store import PostgresStoreUnavailableError, postgres_metadata_store
from app.services.request_guard import idempotency_store, rate_limiter
from app.services.weaver_runtime import weaver_runtime

router = APIRouter(tags=["DataSource"])

_ENGINE_TYPES: dict[str, dict[str, Any]] = {
    "postgresql": {"label": "PostgreSQL", "icon": "postgresql", "default_port": 5432, "supports_metadata_extraction": True},
    "mysql": {"label": "MySQL", "icon": "mysql", "default_port": 3306, "supports_metadata_extraction": True},
    "mongodb": {"label": "MongoDB", "icon": "mongodb", "default_port": 27017, "supports_metadata_extraction": False},
    "oracle": {"label": "Oracle", "icon": "oracle", "default_port": 1521, "supports_metadata_extraction": True},
    "neo4j": {"label": "Neo4j", "icon": "neo4j", "default_port": 7687, "supports_metadata_extraction": False},
}
_SUPPORTED_ENGINES = ["postgresql", "mysql", "oracle"]
_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")


async def get_current_user(authorization: str | None = Header(default=None, alias="Authorization")) -> CurrentUser:
    return auth_service.verify_token(authorization)


def _ensure_reader(user: CurrentUser) -> None:
    auth_service.requires_permission(user, "datasource:read")


def _ensure_writer(user: CurrentUser) -> None:
    auth_service.requires_permission(user, "datasource:write")


def _sanitize_connection(connection: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in connection.items() if k.lower() != "password"}


def _tenant_id(user: CurrentUser) -> str:
    return str(user.tenant_id)


def _ds_key(user: CurrentUser, name: str) -> str:
    return f"{_tenant_id(user)}:{name}"


def _external_ds_name(user: CurrentUser, name: str) -> str:
    tenant_token = _tenant_id(user).replace("-", "_")
    return f"{tenant_token}__{name}"


def _tenant_datasources(user: CurrentUser) -> list[dict[str, Any]]:
    tenant = _tenant_id(user)
    return [x for x in weaver_runtime.datasources.values() if str(x.get("tenant_id") or "") == tenant]


def _ensure_datasource(user: CurrentUser, name: str) -> dict[str, Any]:
    ds = weaver_runtime.datasources.get(_ds_key(user, name))
    if not ds:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    return ds


def _default_catalog(ds_name: str) -> dict[str, Any]:
    return {
        "public": {
            "processes": [
                {"name": "id", "data_type": "uuid", "nullable": False},
                {"name": "name", "data_type": "varchar", "nullable": True},
                {"name": "created_at", "data_type": "timestamptz", "nullable": False},
            ],
            "organizations": [
                {"name": "id", "data_type": "uuid", "nullable": False},
                {"name": "org_name", "data_type": "varchar", "nullable": False},
            ],
            "events": [
                {"name": "id", "data_type": "uuid", "nullable": False},
                {"name": "event_type", "data_type": "varchar", "nullable": False},
                {"name": "process_id", "data_type": "uuid", "nullable": False},
            ],
        },
        "analytics": {
            f"{ds_name}_daily_snapshot": [
                {"name": "snapshot_date", "data_type": "date", "nullable": False},
                {"name": "metric_name", "data_type": "varchar", "nullable": False},
                {"name": "metric_value", "data_type": "numeric", "nullable": False},
            ]
        },
    }


def _ensure_catalog(ds: dict[str, Any]) -> dict[str, Any]:
    catalog = ds.get("catalog")
    if isinstance(catalog, dict) and catalog:
        return catalog
    generated = _default_catalog(str(ds.get("name") or "datasource"))
    ds["catalog"] = generated
    ds["schemas_count"] = len(generated)
    ds["tables_count"] = sum(len(tables) for tables in generated.values())
    return generated


def _catalog_counts(catalog: dict[str, Any]) -> tuple[int, int, int]:
    schemas = 0
    tables = 0
    columns = 0
    for _, tables_obj in catalog.items():
        if not isinstance(tables_obj, dict):
            continue
        schemas += 1
        tables += len(tables_obj)
        for cols_obj in tables_obj.values():
            if isinstance(cols_obj, list):
                columns += len(cols_obj)
    return schemas, tables, columns


def _svc_error(service: str, code: str, exc: Exception) -> HTTPException:
    return external_service_http_exception(service=service, code=code, message=str(exc))


def _request_id(request: Request, header_request_id: str | None) -> str | None:
    return header_request_id or getattr(request.state, "request_id", None)


def _idem_key(user: CurrentUser, endpoint: str, key: str | None) -> str | None:
    if not key:
        return None
    return f"{_tenant_id(user)}:{endpoint}:{key}"


class DataSourceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    engine: str
    connection: dict[str, Any]
    description: str | None = None


class ConnectionUpdate(BaseModel):
    host: str | None = None
    port: int | None = None
    database: str | None = None
    user: str | None = None
    password: str | None = None
    sslmode: str | None = None


class ExtractMetadataRequest(BaseModel):
    schemas: list[str] | None = None
    include_sample_data: bool = False
    sample_limit: int = Field(default=5, ge=1, le=100)
    include_row_counts: bool = True


@router.get("/api/datasources/types")
async def datasource_types(user: CurrentUser = Depends(get_current_user)):
    _ensure_reader(user)
    types = []
    for engine, meta in _ENGINE_TYPES.items():
        types.append(
            {
                "engine": engine,
                "label": meta["label"],
                "icon": meta["icon"],
                "connection_schema": {
                    "host": {"type": "string", "required": True},
                    "port": {"type": "integer", "required": False, "default": meta["default_port"]},
                    "database": {"type": "string", "required": True},
                    "user": {"type": "string", "required": True},
                    "password": {"type": "string", "required": True, "secret": True},
                },
                "supports_metadata_extraction": meta["supports_metadata_extraction"],
            }
        )
    return {"types": types}


@router.get("/api/datasources/supported-engines")
async def supported_engines(user: CurrentUser = Depends(get_current_user)):
    _ensure_reader(user)
    return {"supported_engines": _SUPPORTED_ENGINES}


@router.get("/api/datasources")
async def list_datasources(user: CurrentUser = Depends(get_current_user)):
    _ensure_reader(user)
    items = []
    live_names: set[str] = set()
    if settings.external_mode:
        try:
            live_names = set(await mindsdb_client.show_databases())
        except MindsDBUnavailableError:
            live_names = set()
    for ds in sorted(_tenant_datasources(user), key=lambda x: x["name"]):
        status_value = ds["status"]
        if settings.external_mode:
            status_value = "connected" if _external_ds_name(user, ds["name"]) in live_names else "error"
        items.append(
            {
                "name": ds["name"],
                "engine": ds["engine"],
                "status": status_value,
                "description": ds.get("description"),
                "tables_count": ds.get("tables_count"),
                "metadata_extracted": ds.get("metadata_extracted", False),
            }
        )
    return {"datasources": items, "total": len(items)}


@router.post("/api/datasources", status_code=status.HTTP_201_CREATED)
async def create_datasource(
    payload: DataSourceCreate,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    request_id: str | None = Header(default=None, alias="X-Request-Id"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    started = time.perf_counter()
    rate_limiter.check(f"{user.user_id}:{request.url.path}:write", limit=60)
    idem_key = _idem_key(user, request.url.path, idempotency_key)
    cached = idempotency_store.ensure(key=idem_key, payload=payload.model_dump())
    if cached:
        return cached["response"]
    _ensure_writer(user)
    if payload.engine not in _ENGINE_TYPES:
        raise HTTPException(status_code=400, detail="INVALID_ENGINE")
    if not _NAME_PATTERN.match(payload.name):
        raise HTTPException(status_code=400, detail="INVALID_NAME")
    ds_key = _ds_key(user, payload.name)
    if ds_key in weaver_runtime.datasources:
        raise HTTPException(status_code=409, detail="DUPLICATE_NAME")
    for required in ("host", "database", "user", "password"):
        if required not in payload.connection:
            raise HTTPException(status_code=422, detail=f"MISSING_PARAM:{required}")
    if settings.external_mode:
        try:
            await mindsdb_client.create_database(_external_ds_name(user, payload.name), payload.engine, payload.connection)
        except MindsDBUnavailableError as exc:
            raise _svc_error("mindsdb", "MINDSDB_UNAVAILABLE", exc) from exc
    ds = weaver_runtime.create_datasource(
        payload.model_dump(),
        storage_key=ds_key,
        display_name=payload.name,
        tenant_id=_tenant_id(user),
    )
    if settings.metadata_pg_mode:
        try:
            await postgres_metadata_store.upsert_datasource(_external_ds_name(user, ds["name"]), ds["engine"], tenant_id=_tenant_id(user))
        except PostgresStoreUnavailableError as exc:
            raise _svc_error("postgres", "POSTGRES_UNAVAILABLE", exc) from exc
    if settings.metadata_external_mode:
        try:
            await synapse_metadata_client.upsert_datasource(ds["name"], ds["engine"], tenant_id=_tenant_id(user))
        except SynapseMetadataClientError as exc:
            raise _svc_error("synapse", "SYNAPSE_UNAVAILABLE", exc) from exc
    response = {
        **ds,
        "connection": _sanitize_connection(ds["connection"]),
    }
    idempotency_store.set(
        idem_key or "",
        fingerprint=idempotency_store.fingerprint(payload.model_dump()),
        status_code=201,
        response=response,
    ) if idem_key else None
    audit_log_service.emit(
        action="datasource.create",
        actor_id=str(user.user_id),
        tenant_id=str(user.tenant_id),
        resource_type="datasource",
        resource_id=ds["name"],
        request_id=_request_id(request, request_id),
        duration_ms=int((time.perf_counter() - started) * 1000),
        metadata={"engine": ds["engine"]},
    )
    return response


@router.get("/api/datasources/{name}")
async def get_datasource(name: str, user: CurrentUser = Depends(get_current_user)):
    _ensure_reader(user)
    ds = _ensure_datasource(user, name)
    return {**ds, "connection": _sanitize_connection(ds["connection"])}


@router.delete("/api/datasources/{name}")
async def delete_datasource(
    name: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    request_id: str | None = Header(default=None, alias="X-Request-Id"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    started = time.perf_counter()
    rate_limiter.check(f"{user.user_id}:{request.url.path}:write", limit=60)
    idem_key = _idem_key(user, request.url.path, idempotency_key)
    cached = idempotency_store.ensure(key=idem_key, payload={"name": name, "op": "delete"})
    if cached:
        return cached["response"]
    _ensure_writer(user)
    ds = _ensure_datasource(user, name)
    if settings.external_mode:
        try:
            await mindsdb_client.drop_database(_external_ds_name(user, name))
        except MindsDBUnavailableError as exc:
            raise _svc_error("mindsdb", "MINDSDB_UNAVAILABLE", exc) from exc
    weaver_runtime.datasources.pop(_ds_key(user, name), None)
    if settings.metadata_pg_mode:
        try:
            await postgres_metadata_store.delete_datasource(_external_ds_name(user, name), tenant_id=_tenant_id(user))
        except PostgresStoreUnavailableError as exc:
            raise _svc_error("postgres", "POSTGRES_UNAVAILABLE", exc) from exc
    if settings.metadata_external_mode:
        try:
            await synapse_metadata_client.delete_datasource(name, tenant_id=_tenant_id(user))
        except SynapseMetadataClientError as exc:
            raise _svc_error("synapse", "SYNAPSE_UNAVAILABLE", exc) from exc
    schemas, tables, columns = _catalog_counts(_ensure_catalog(ds))
    response = {
        "message": f"DataSource '{name}' deleted successfully",
        "deleted_metadata": {
            "schemas": schemas,
            "tables": tables,
            "columns": columns,
        },
    }
    idempotency_store.set(
        idem_key or "",
        fingerprint=idempotency_store.fingerprint({"name": name, "op": "delete"}),
        status_code=200,
        response=response,
    ) if idem_key else None
    audit_log_service.emit(
        action="datasource.delete",
        actor_id=str(user.user_id),
        tenant_id=str(user.tenant_id),
        resource_type="datasource",
        resource_id=name,
        request_id=_request_id(request, request_id),
        duration_ms=int((time.perf_counter() - started) * 1000),
    )
    return response


@router.put("/api/datasources/{name}/connection")
async def update_connection(
    name: str,
    payload: ConnectionUpdate,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    request_id: str | None = Header(default=None, alias="X-Request-Id"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    started = time.perf_counter()
    rate_limiter.check(f"{user.user_id}:{request.url.path}:write", limit=60)
    idem_key = _idem_key(user, request.url.path, idempotency_key)
    cached = idempotency_store.ensure(key=idem_key, payload={"name": name, **payload.model_dump(exclude_none=True)})
    if cached:
        return cached["response"]
    _ensure_writer(user)
    ds = _ensure_datasource(user, name)
    changed = payload.model_dump(exclude_none=True)
    ds["connection"].update(changed)
    ds["status"] = "connected"
    response = {"name": name, "connection": _sanitize_connection(ds["connection"]), "status": ds["status"]}
    idempotency_store.set(
        idem_key or "",
        fingerprint=idempotency_store.fingerprint({"name": name, **payload.model_dump(exclude_none=True)}),
        status_code=200,
        response=response,
    ) if idem_key else None
    audit_log_service.emit(
        action="datasource.update_connection",
        actor_id=str(user.user_id),
        tenant_id=str(user.tenant_id),
        resource_type="datasource",
        resource_id=name,
        request_id=_request_id(request, request_id),
        duration_ms=int((time.perf_counter() - started) * 1000),
        metadata={"changed_fields": sorted(payload.model_dump(exclude_none=True).keys())},
    )
    return response


@router.get("/api/datasources/{name}/health")
async def datasource_health(name: str, user: CurrentUser = Depends(get_current_user)):
    _ensure_reader(user)
    started = time.perf_counter()
    ds = _ensure_datasource(user, name)
    if settings.external_mode:
        try:
            await mindsdb_client.health_check()
            databases = await mindsdb_client.show_databases()
            exists = _external_ds_name(user, name) in set(databases)
            if not exists:
                return {
                    "name": name,
                    "status": "unhealthy",
                    "error": "Datasource is not synchronized in MindsDB",
                    "response_time_ms": int((time.perf_counter() - started) * 1000),
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                }
        except MindsDBUnavailableError as exc:
            return {
                "name": name,
                "status": "unhealthy",
                "error": public_error_message(exc),
                "response_time_ms": int((time.perf_counter() - started) * 1000),
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }
    return {
        "name": name,
        "status": "healthy" if ds["status"] == "connected" else str(ds["status"]),
        "response_time_ms": int((time.perf_counter() - started) * 1000),
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/api/datasources/{name}/test")
async def datasource_test(name: str, user: CurrentUser = Depends(get_current_user)):
    _ensure_reader(user)
    started = time.perf_counter()
    _ensure_datasource(user, name)
    if settings.external_mode:
        try:
            await mindsdb_client.show_databases()
        except MindsDBUnavailableError as exc:
            raise _svc_error("mindsdb", "MINDSDB_UNAVAILABLE", exc) from exc
    return {
        "name": name,
        "success": True,
        "response_time_ms": int((time.perf_counter() - started) * 1000),
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/api/datasources/{name}/extract-metadata")
async def extract_metadata(
    name: str,
    payload: ExtractMetadataRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
):
    """메타데이터 추출 SSE 스트리밍. metadata-api.md §2. 지원 엔진: postgresql, mysql, oracle."""
    _ensure_writer(user)
    ds = _ensure_datasource(user, name)
    engine = (ds.get("engine") or "").strip().lower()
    if engine not in _SUPPORTED_ENGINES:
        raise HTTPException(status_code=400, detail="INVALID_ENGINE")
    connection = ds.get("connection") or {}
    ds_key = _ds_key(user, name)

    async def generate():
        async for event in extract_metadata_stream(
            name,
            engine,
            connection,
            target_schemas=payload.schemas,
            include_sample_data=payload.include_sample_data,
            sample_limit=payload.sample_limit,
            include_row_counts=payload.include_row_counts,
        ):
            data = dict(event.get("data", {}))
            catalog = data.pop("_catalog", None)
            foreign_keys = data.pop("_foreign_keys", None)
            if event.get("event") == "complete" and catalog is not None:
                if settings.metadata_external_mode:
                    try:
                        graph_stats = await synapse_metadata_client.save_extracted_catalog(
                            _tenant_id(user), name, catalog, engine, foreign_keys=foreign_keys or []
                        )
                        yield f"event: graph_saved\ndata: {json.dumps(graph_stats, ensure_ascii=False)}\n\n"
                    except SynapseMetadataClientError as exc:
                        err_data = {"message": public_error_message(exc), "code": "NEO4J_UNAVAILABLE"}
                        yield f"event: error\ndata: {json.dumps(err_data, ensure_ascii=False)}\n\n"
                        raise _svc_error("synapse", "SYNAPSE_UNAVAILABLE", exc) from exc
                yield f"event: complete\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
                ds_ref = weaver_runtime.datasources.get(ds_key)
                if ds_ref is not None:
                    ds_ref["catalog"] = catalog
                    ds_ref["metadata_extracted"] = True
                    ds_ref["tables_count"] = sum(len(t) for t in catalog.values())
                    ds_ref["schemas_count"] = len(catalog)
                continue
            # 그 외 이벤트는 그대로 전달
            line = f"event: {event.get('event', '')}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
            yield line

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/api/datasources/{name}/schemas")
async def datasource_schemas(name: str, user: CurrentUser = Depends(get_current_user)):
    _ensure_reader(user)
    ds = _ensure_datasource(user, name)
    catalog = _ensure_catalog(ds)
    return {"datasource": name, "schemas": sorted(catalog.keys())}


@router.get("/api/datasources/{name}/tables")
async def datasource_tables(
    name: str,
    schema: str = Query(default="public"),
    user: CurrentUser = Depends(get_current_user),
):
    _ensure_reader(user)
    ds = _ensure_datasource(user, name)
    catalog = _ensure_catalog(ds)
    tables = catalog.get(schema)
    if tables is None:
        raise HTTPException(status_code=404, detail="SCHEMA_NOT_FOUND")
    return {"datasource": name, "schema": schema, "tables": sorted(tables.keys())}


@router.get("/api/datasources/{name}/tables/{table}/schema")
async def datasource_table_schema(name: str, table: str, user: CurrentUser = Depends(get_current_user)):
    _ensure_reader(user)
    ds = _ensure_datasource(user, name)
    catalog = _ensure_catalog(ds)
    for schema_name, tables in catalog.items():
        if table in tables:
            return {
                "datasource": name,
                "schema": schema_name,
                "table": table,
                "columns": tables[table],
            }
    raise HTTPException(status_code=404, detail="TABLE_NOT_FOUND")


@router.get("/api/datasources/{name}/tables/{table}/sample")
async def datasource_table_sample(name: str, table: str, limit: int = Query(default=5, ge=1, le=100), user: CurrentUser = Depends(get_current_user)):
    _ensure_reader(user)
    ds = _ensure_datasource(user, name)
    catalog = _ensure_catalog(ds)
    columns: list[dict[str, Any]] | None = None
    for tables in catalog.values():
        if table in tables:
            columns = tables[table]
            break
    if columns is None:
        raise HTTPException(status_code=404, detail="TABLE_NOT_FOUND")

    def _sample_value(data_type: str, idx: int, col_name: str) -> Any:
        if data_type in {"uuid"}:
            return f"{table}-{idx:04d}"
        if data_type in {"numeric", "integer", "bigint"}:
            return idx
        if data_type in {"date"}:
            return "2026-02-21"
        if data_type in {"timestamptz", "timestamp"}:
            return "2026-02-21T00:00:00Z"
        return f"{col_name}-{idx}"

    rows = [
        {col["name"]: _sample_value(str(col["data_type"]), i, str(col["name"])) for col in columns}
        for i in range(limit)
    ]
    return {"datasource": name, "table": table, "rows": rows, "row_count": len(rows)}


# Backward-compatible legacy routes
@router.post("/datasource")
async def legacy_create_datasource(payload: dict[str, Any]):
    name = str(payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="MISSING_NAME")
    engine = str(payload.get("engine") or payload.get("type") or "postgresql").strip().lower()
    if engine == "postgres":
        engine = "postgresql"
    connection = payload.get("connection") or payload.get("connection_config") or {}
    if not isinstance(connection, dict):
        raise HTTPException(status_code=422, detail="INVALID_CONNECTION")

    ds_id = weaver_runtime.new_id("ds-")
    storage_key = f"legacy:{name}"
    created = weaver_runtime.create_datasource(
        {
            "name": name,
            "engine": engine,
            "connection": dict(connection),
            "description": payload.get("description"),
        },
        storage_key=storage_key,
        display_name=name,
        tenant_id="legacy",
    )
    created["id"] = ds_id
    return {"status": "created", "id": ds_id, "name": created["name"], "engine": created["engine"]}


@router.post("/datasource/{ds_id}/sync")
async def legacy_sync_schema(ds_id: str):
    if not str(ds_id).strip():
        raise HTTPException(status_code=422, detail="INVALID_DATASOURCE_ID")
    job_id = weaver_runtime.new_id("job-")
    weaver_runtime.query_jobs[job_id] = {
        "id": job_id,
        "datasource_id": ds_id,
        "status": "running",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "type": "schema_sync",
    }
    return {"status": "sync_started", "job_id": job_id, "datasource_id": ds_id}
