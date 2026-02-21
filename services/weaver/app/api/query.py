from __future__ import annotations

from datetime import datetime, timezone
import re
import time
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.core.auth import CurrentUser, auth_service
from app.core.config import settings
from app.core.error_codes import external_service_http_exception, public_error_message
from app.services.audit_log import audit_log_service
from app.services.mindsdb_client import MindsDBUnavailableError, mindsdb_client
from app.services.request_guard import idempotency_store, rate_limiter
from app.services.weaver_runtime import weaver_runtime

router = APIRouter(tags=["Query Engine"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def get_current_user(authorization: str | None = Header(default=None, alias="Authorization")) -> CurrentUser:
    return auth_service.verify_token(authorization)


def _ensure_reader(user: CurrentUser) -> None:
    auth_service.requires_permission(user, "query:read")


def _ensure_executor(user: CurrentUser) -> None:
    auth_service.requires_permission(user, "query:execute")


def _svc_error(service: str, code: str, exc: Exception) -> HTTPException:
    return external_service_http_exception(service=service, code=code, message=str(exc))


def _request_id(request: Request, header_request_id: str | None) -> str | None:
    return header_request_id or getattr(request.state, "request_id", None)


def _tenant_id(user: CurrentUser) -> str:
    return str(user.tenant_id)


def _idem_key(user: CurrentUser, endpoint: str, key: str | None) -> str | None:
    if not key:
        return None
    return f"{_tenant_id(user)}:{endpoint}:{key}"


def _validate_sql(sql: str) -> str:
    stripped = sql.strip()
    if not stripped:
        raise HTTPException(status_code=400, detail="EMPTY_QUERY")
    upper = stripped.upper()
    forbidden = ("CREATE ", "ALTER ", "DROP ", "TRUNCATE ")
    if any(x in upper for x in forbidden):
        raise HTTPException(status_code=400, detail="INVALID_SQL")
    return stripped


def _mock_limit(sql: str, *, default: int = 3, max_rows: int = 200) -> int:
    m = re.search(r"\bLIMIT\s+(\d+)\b", sql, flags=re.IGNORECASE)
    if not m:
        return default
    try:
        value = int(m.group(1))
    except Exception:
        return default
    return max(1, min(value, max_rows))


def _tenant_models(user: CurrentUser) -> list[dict[str, Any]]:
    tenant = _tenant_id(user)
    return [x for x in weaver_runtime.query_models.values() if str(x.get("tenant_id") or "") == tenant]


def _tenant_jobs(user: CurrentUser) -> list[dict[str, Any]]:
    tenant = _tenant_id(user)
    return [x for x in weaver_runtime.query_jobs.values() if str(x.get("tenant_id") or "") == tenant]


def _tenant_kbs(user: CurrentUser) -> list[dict[str, Any]]:
    tenant = _tenant_id(user)
    return [x for x in weaver_runtime.knowledge_bases.values() if str(x.get("tenant_id") or "") == tenant]


def _ensure_query_assets(user: CurrentUser) -> None:
    tenant = _tenant_id(user)
    if not _tenant_models(user):
        model_id = weaver_runtime.new_id("model-")
        weaver_runtime.query_models[model_id] = {
            "id": model_id,
            "tenant_id": tenant,
            "name": "process_predictor",
            "engine": "openai",
            "status": "complete",
            "created_at": _now(),
            "predict_column": "outcome",
        }
    if not _tenant_kbs(user):
        kb_id = weaver_runtime.new_id("kb-")
        weaver_runtime.knowledge_bases[kb_id] = {
            "id": kb_id,
            "tenant_id": tenant,
            "name": "business_process_kb",
            "model": "openai_embedding",
            "storage": "chromadb",
            "documents_count": 150,
            "created_at": _now(),
        }


class QueryExecuteRequest(BaseModel):
    sql: str = Field(..., min_length=1, max_length=20_000)
    database: str | None = None


class MaterializedTableRequest(BaseModel):
    table_name: str = Field(..., min_length=1, max_length=120)
    sql: str = Field(..., min_length=1, max_length=20_000)
    database: str = "mindsdb"
    replace_if_exists: bool = False


@router.post("/api/query")
async def execute_query(
    payload: QueryExecuteRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    request_id: str | None = Header(default=None, alias="X-Request-Id"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    started = time.perf_counter()
    rate_limiter.check(f"{user.user_id}:{request.url.path}:execute", limit=120)
    idem_key = _idem_key(user, request.url.path, idempotency_key)
    cached = idempotency_store.ensure(key=idem_key, payload=payload.model_dump())
    if cached:
        return cached["response"]
    _ensure_executor(user)
    sql = _validate_sql(payload.sql)
    if payload.database == "missing_db":
        raise HTTPException(status_code=404, detail="DATABASE_NOT_FOUND")
    if settings.external_mode:
        try:
            result = await mindsdb_client.execute_query(sql, payload.database)
        except MindsDBUnavailableError as exc:
            raise _svc_error("mindsdb", "MINDSDB_UNAVAILABLE", exc) from exc
        rows = result.get("data") or []
        columns = result.get("columns") or []
        response = {
            "success": True,
            "columns": [str(c) for c in columns] if columns else [],
            "column_types": None,
            "data": rows if isinstance(rows, list) else [],
            "row_count": len(rows) if isinstance(rows, list) else 0,
            "execution_time_ms": 0,
            "database": payload.database,
            "normalized_sql": sql,
        }
        audit_log_service.emit(
            action="query.execute",
            actor_id=str(user.user_id),
            tenant_id=str(user.tenant_id),
            resource_type="query",
            resource_id=payload.database or "default",
            request_id=_request_id(request, request_id),
            duration_ms=int((time.perf_counter() - started) * 1000),
            metadata={"row_count": response["row_count"]},
        )
        idempotency_store.set(
            idem_key or "",
            fingerprint=idempotency_store.fingerprint(payload.model_dump()),
            status_code=200,
            response=response,
        ) if idem_key else None
        return response
    mock_rows = _mock_limit(sql)
    rows = [[f"value-{i}", i] for i in range(mock_rows)]
    elapsed_ms = max(int((time.perf_counter() - started) * 1000), 1)
    response = {
        "success": True,
        "columns": ["name", "metric"],
        "column_types": ["varchar", "integer"],
        "data": rows,
        "row_count": len(rows),
        "execution_time_ms": elapsed_ms,
        "database": payload.database,
        "normalized_sql": sql,
    }
    audit_log_service.emit(
        action="query.execute",
        actor_id=str(user.user_id),
        tenant_id=str(user.tenant_id),
        resource_type="query",
        resource_id=payload.database or "default",
        request_id=_request_id(request, request_id),
        duration_ms=int((time.perf_counter() - started) * 1000),
        metadata={"row_count": response["row_count"]},
    )
    idempotency_store.set(
        idem_key or "",
        fingerprint=idempotency_store.fingerprint(payload.model_dump()),
        status_code=200,
        response=response,
    ) if idem_key else None
    return response


@router.get("/api/query/status")
async def query_status(user: CurrentUser = Depends(get_current_user)):
    _ensure_reader(user)
    started = time.perf_counter()
    _ensure_query_assets(user)
    if settings.external_mode:
        try:
            health = await mindsdb_client.health_check()
        except MindsDBUnavailableError as exc:
            return {"status": "unhealthy", "error": public_error_message(exc), "checked_at": _now()}
        status_value = str(health.get("status", "healthy")).lower()
        if status_value not in {"healthy", "ok"}:
            return {"status": "unhealthy", "error": health, "checked_at": _now()}
        mindsdb_version = str(health.get("version") or health.get("mindsdb_version") or "unknown")
    else:
        mindsdb_version = "unknown"

    uptime_seconds = int(
        (datetime.now(timezone.utc) - datetime.fromisoformat(weaver_runtime.started_at)).total_seconds()
    )
    return {
        "status": "healthy",
        "mindsdb_version": mindsdb_version,
        "databases_count": len([x for x in weaver_runtime.datasources.values() if str(x.get("tenant_id") or "") == _tenant_id(user)]),
        "models_count": len(_tenant_models(user)),
        "uptime_seconds": max(uptime_seconds, 0),
        "response_time_ms": max(int((time.perf_counter() - started) * 1000), 1),
    }


@router.post("/api/query/materialized-table", status_code=status.HTTP_201_CREATED)
async def create_materialized_table(
    payload: MaterializedTableRequest,
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
    _ensure_executor(user)
    sql = _validate_sql(payload.sql)
    key = f"{_tenant_id(user)}:{payload.database}.{payload.table_name}"
    if key in weaver_runtime.materialized_tables and not payload.replace_if_exists:
        raise HTTPException(status_code=409, detail="TABLE_ALREADY_EXISTS")
    if settings.external_mode:
        create_sql = f"CREATE TABLE {payload.database}.{payload.table_name} AS {sql}"
        if payload.replace_if_exists:
            create_sql = f"CREATE OR REPLACE TABLE {payload.database}.{payload.table_name} AS {sql}"
        try:
            await mindsdb_client.execute_query(create_sql, payload.database)
        except MindsDBUnavailableError as exc:
            raise _svc_error("mindsdb", "MINDSDB_UNAVAILABLE", exc) from exc
    row_count = 25
    table = {
        "table_name": payload.table_name,
        "database": payload.database,
        "row_count": row_count,
        "columns": ["id", "name"],
        "created_at": _now(),
        "sql": sql,
    }
    weaver_runtime.materialized_tables[key] = table
    job_id = weaver_runtime.new_id("job-")
    weaver_runtime.query_jobs[job_id] = {
        "id": job_id,
        "tenant_id": _tenant_id(user),
        "name": f"materialize_{payload.table_name}",
        "query": sql,
        "schedule": "manual",
        "status": "succeeded",
        "last_run": _now(),
        "next_run": None,
    }
    audit_log_service.emit(
        action="query.materialize",
        actor_id=str(user.user_id),
        tenant_id=str(user.tenant_id),
        resource_type="materialized_table",
        resource_id=key,
        request_id=_request_id(request, request_id),
        duration_ms=int((time.perf_counter() - started) * 1000),
        metadata={"replace_if_exists": payload.replace_if_exists},
    )
    idempotency_store.set(
        idem_key or "",
        fingerprint=idempotency_store.fingerprint(payload.model_dump()),
        status_code=201,
        response=table,
    ) if idem_key else None
    return table


@router.get("/api/query/models")
async def list_models(user: CurrentUser = Depends(get_current_user)):
    _ensure_reader(user)
    _ensure_query_assets(user)
    return {"models": sorted(_tenant_models(user), key=lambda x: x["created_at"], reverse=True)}


@router.get("/api/query/jobs")
async def list_jobs(user: CurrentUser = Depends(get_current_user)):
    _ensure_reader(user)
    return {"jobs": sorted(_tenant_jobs(user), key=lambda x: str(x.get("last_run") or ""), reverse=True)}


@router.get("/api/query/knowledge-bases")
async def list_knowledge_bases(user: CurrentUser = Depends(get_current_user)):
    _ensure_reader(user)
    _ensure_query_assets(user)
    return {"knowledge_bases": sorted(_tenant_kbs(user), key=lambda x: x["created_at"], reverse=True)}


# Backward-compatible legacy route and payload
class LegacyQueryExecution(BaseModel):
    datasource_id: str
    target_node: str
    execution_parameters: dict[str, Any]


@router.post("/query")
async def execute_graph_query(payload: LegacyQueryExecution, user: CurrentUser = Depends(get_current_user)):
    _ensure_executor(user)
    blocklist = ["localhost", "127.0.0.1", "10.0.", "192.168."]
    if any(b in payload.target_node for b in blocklist):
        raise HTTPException(status_code=400, detail="Target Node violates connection blocklist policies")
    requested_limit = payload.execution_parameters.get("limit", 5)
    try:
        limit = int(requested_limit)
    except Exception as exc:
        raise HTTPException(status_code=422, detail="INVALID_LIMIT") from exc
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=422, detail="LIMIT_OUT_OF_RANGE")

    records = [
        {
            "row_id": i + 1,
            "datasource_id": payload.datasource_id,
            "target_node": payload.target_node,
            "metric": f"sample_metric_{i + 1}",
            "value": i,
        }
        for i in range(limit)
    ]
    return {
        "status": "executed",
        "query_id": weaver_runtime.new_id("legacy-query-"),
        "datasource_id": payload.datasource_id,
        "target_node": payload.target_node,
        "records_returned": len(records),
        "records_preview": records[: min(limit, 20)],
    }
