from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from app.core.auth import CurrentUser, auth_service
from app.core.config import settings
from app.core.error_codes import external_service_http_exception
from app.services.audit_log import audit_log_service
from app.services.synapse_metadata_client import SynapseMetadataClientError, synapse_metadata_client
from app.services.postgres_metadata_store import PostgresStoreUnavailableError, postgres_metadata_store
from app.services.request_guard import idempotency_store, rate_limiter
from app.services.weaver_runtime import weaver_runtime

router = APIRouter(prefix="/api/v1/metadata", tags=["Metadata Catalog"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def get_current_user(authorization: str | None = Header(default=None, alias="Authorization")) -> CurrentUser:
    return auth_service.verify_token(authorization)


def _ensure_reader(user: CurrentUser) -> None:
    auth_service.requires_permission(user, "metadata:read")


def _ensure_writer(user: CurrentUser) -> None:
    auth_service.requires_permission(user, "metadata:write")


def _ensure_admin(user: CurrentUser) -> None:
    auth_service.requires_permission(user, "metadata:admin")


def _tenant_id(user: CurrentUser) -> str:
    return str(user.tenant_id)


def _ds_key(user: CurrentUser, ds_name: str) -> str:
    return f"{_tenant_id(user)}:{ds_name}"


def _snapshot_bucket(user: CurrentUser, case_id: str, ds_name: str) -> dict[str, dict[str, Any]]:
    return weaver_runtime.snapshots.setdefault((_tenant_id(user), case_id, ds_name), {})


def _require_datasource_catalog(user: CurrentUser, ds_name: str) -> dict[str, Any]:
    ds = weaver_runtime.datasources.get(_ds_key(user, ds_name))
    if not ds:
        raise HTTPException(status_code=404, detail="DATASOURCE_NOT_FOUND")
    catalog = ds.get("catalog")
    if not isinstance(catalog, dict) or not catalog:
        catalog = {
            "public": {
                "processes": [
                    {"name": "id", "data_type": "uuid", "nullable": False},
                    {"name": "name", "data_type": "varchar", "nullable": True},
                ]
            }
        }
        ds["catalog"] = catalog
    return catalog


def _snapshot_schema_map(item: dict[str, Any]) -> dict[str, dict[str, dict[str, dict[str, Any]]]]:
    result: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}
    graph_data = item.get("graph_data")
    if not isinstance(graph_data, dict):
        return result
    schemas = graph_data.get("schemas")
    if not isinstance(schemas, list):
        return result
    for schema in schemas:
        if not isinstance(schema, dict):
            continue
        schema_name = str(schema.get("name") or "").strip()
        if not schema_name:
            continue
        table_map: dict[str, dict[str, dict[str, Any]]] = {}
        tables = schema.get("tables")
        if isinstance(tables, list):
            for table in tables:
                if isinstance(table, str):
                    table_name = table.strip()
                    if table_name:
                        table_map[table_name] = {}
                    continue
                if not isinstance(table, dict):
                    continue
                table_name = str(table.get("name") or "").strip()
                if not table_name:
                    continue
                col_map: dict[str, dict[str, Any]] = {}
                columns = table.get("columns")
                if isinstance(columns, list):
                    for col in columns:
                        if not isinstance(col, dict):
                            continue
                        col_name = str(col.get("name") or "").strip()
                        if not col_name:
                            continue
                        col_map[col_name] = {
                            "dtype": str(col.get("dtype") or col.get("data_type") or "unknown"),
                            "nullable": bool(col.get("nullable", True)),
                            "default_value": col.get("default_value"),
                        }
                table_map[table_name] = col_map
        result[schema_name] = table_map
    return result


def _flatten_tables(schema_map: dict[str, dict[str, dict[str, dict[str, Any]]]]) -> dict[str, int]:
    rows: dict[str, int] = {}
    for schema_name, tables in schema_map.items():
        for table_name, columns in tables.items():
            rows[f"{schema_name}.{table_name}"] = len(columns)
    return rows


def _catalog_to_graph_data(catalog: dict[str, Any]) -> dict[str, Any]:
    schemas: list[dict[str, Any]] = []
    for schema_name in sorted(catalog.keys()):
        tables_obj = catalog.get(schema_name)
        if not isinstance(tables_obj, dict):
            continue
        tables: list[dict[str, Any]] = []
        for table_name in sorted(tables_obj.keys()):
            cols_obj = tables_obj.get(table_name)
            columns: list[dict[str, Any]] = []
            if isinstance(cols_obj, list):
                for col in cols_obj:
                    if not isinstance(col, dict):
                        continue
                    col_name = str(col.get("name") or "").strip()
                    if not col_name:
                        continue
                    columns.append(
                        {
                            "name": col_name,
                            "dtype": str(col.get("dtype") or col.get("data_type") or "unknown"),
                            "nullable": bool(col.get("nullable", True)),
                            "default_value": col.get("default_value"),
                        }
                    )
            tables.append({"name": table_name, "columns": columns})
        schemas.append({"name": schema_name, "tables_count": len(tables), "tables": tables})
    return {"schemas": schemas}


def _summary_from_graph_data(graph_data: dict[str, Any]) -> dict[str, int]:
    schemas_obj = graph_data.get("schemas")
    if not isinstance(schemas_obj, list):
        return {"schemas": 0, "tables": 0, "columns": 0, "fk_relations": 0}
    schema_count = 0
    table_count = 0
    column_count = 0
    for schema in schemas_obj:
        if not isinstance(schema, dict):
            continue
        schema_count += 1
        tables = schema.get("tables")
        if not isinstance(tables, list):
            continue
        table_count += len(tables)
        for table in tables:
            if not isinstance(table, dict):
                continue
            columns = table.get("columns")
            if isinstance(columns, list):
                column_count += len(columns)
    return {"schemas": schema_count, "tables": table_count, "columns": column_count, "fk_relations": 0}


def _graph_data_to_catalog(graph_data: dict[str, Any]) -> dict[str, dict[str, list[dict[str, Any]]]]:
    catalog: dict[str, dict[str, list[dict[str, Any]]]] = {}
    schemas = graph_data.get("schemas")
    if not isinstance(schemas, list):
        return catalog
    for schema in schemas:
        if not isinstance(schema, dict):
            continue
        schema_name = str(schema.get("name") or "").strip()
        if not schema_name:
            continue
        tables_out: dict[str, list[dict[str, Any]]] = {}
        tables = schema.get("tables")
        if isinstance(tables, list):
            for table in tables:
                if not isinstance(table, dict):
                    continue
                table_name = str(table.get("name") or "").strip()
                if not table_name:
                    continue
                columns_out: list[dict[str, Any]] = []
                columns = table.get("columns")
                if isinstance(columns, list):
                    for col in columns:
                        if not isinstance(col, dict):
                            continue
                        col_name = str(col.get("name") or "").strip()
                        if not col_name:
                            continue
                        columns_out.append(
                            {
                                "name": col_name,
                                "data_type": str(col.get("dtype") or col.get("data_type") or "unknown"),
                                "nullable": bool(col.get("nullable", True)),
                                "default_value": col.get("default_value"),
                            }
                        )
                tables_out[table_name] = columns_out
        catalog[schema_name] = tables_out
    return catalog


def _table_entity_key(user: CurrentUser, case_id: str, ds_name: str, table_name: str) -> str:
    return f"table:{_tenant_id(user)}:{case_id}:{ds_name}:{table_name}"


def _column_entity_key(user: CurrentUser, case_id: str, ds_name: str, table_name: str, column_name: str) -> str:
    return f"column:{_tenant_id(user)}:{case_id}:{ds_name}:{table_name}:{column_name}"


def _request_id(request: Request, header_request_id: str | None) -> str | None:
    return header_request_id or getattr(request.state, "request_id", None)


def _idem_key(user: CurrentUser, endpoint: str, key: str | None) -> str | None:
    if not key:
        return None
    return f"{_tenant_id(user)}:{endpoint}:{key}"


def _svc_error(service: str, code: str, exc: Exception) -> HTTPException:
    return external_service_http_exception(service=service, code=code, message=str(exc))


class SnapshotCreateRequest(BaseModel):
    description: str | None = Field(default=None, max_length=500)


class GlossaryCreateRequest(BaseModel):
    term: str = Field(..., min_length=1, max_length=120)
    definition: str = Field(..., min_length=1, max_length=2000)
    synonyms: list[str] = Field(default_factory=list)


class GlossaryUpdateRequest(BaseModel):
    term: str | None = Field(default=None, min_length=1, max_length=120)
    definition: str | None = Field(default=None, min_length=1, max_length=2000)
    synonyms: list[str] | None = None


class TagRequest(BaseModel):
    tag: str = Field(..., min_length=1, max_length=64)


async def _finalize_snapshot(tenant_id: str, case_id: str, ds_name: str, item: dict[str, Any]) -> None:
    item["status"] = "ready"
    item["completed_at"] = _now()
    if settings.metadata_pg_mode:
        await postgres_metadata_store.save_snapshot(item, tenant_id=tenant_id)
        return
    if settings.metadata_external_mode:
        await synapse_metadata_client.save_snapshot(item, tenant_id=tenant_id)
        return
    bucket = weaver_runtime.snapshots.setdefault((tenant_id, case_id, ds_name), {})
    bucket[item["id"]] = item


@router.post("/cases/{case_id}/datasources/{ds_name}/snapshots", status_code=status.HTTP_202_ACCEPTED)
async def create_snapshot(
    case_id: str,
    ds_name: str,
    payload: SnapshotCreateRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(get_current_user),
    request_id: str | None = Header(default=None, alias="X-Request-Id"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    started = time.perf_counter()
    rate_limiter.check(f"{user.user_id}:{request.url.path}:write", limit=60)
    idem_key = _idem_key(user, request.url.path, idempotency_key)
    cached = idempotency_store.ensure(key=idem_key, payload={"case_id": case_id, "ds_name": ds_name, **payload.model_dump()})
    if cached:
        return cached["response"]
    _ensure_writer(user)
    if _ds_key(user, ds_name) not in weaver_runtime.datasources:
        raise HTTPException(status_code=404, detail="DATASOURCE_NOT_FOUND")
    bucket = _snapshot_bucket(user, case_id, ds_name)
    version = len(bucket) + 1
    if settings.metadata_pg_mode:
        try:
            version = await postgres_metadata_store.next_snapshot_version(case_id, ds_name, tenant_id=_tenant_id(user))
        except PostgresStoreUnavailableError as exc:
            raise _svc_error("postgres", "POSTGRES_UNAVAILABLE", exc) from exc
    catalog = _require_datasource_catalog(user, ds_name)
    graph_data = _catalog_to_graph_data(catalog)
    summary = _summary_from_graph_data(graph_data)
    snapshot_id = weaver_runtime.new_id("snap-")
    item = {
        "id": snapshot_id,
        "tenant_id": _tenant_id(user),
        "datasource": ds_name,
        "case_id": case_id,
        "version": version,
        "status": "creating",
        "description": payload.description,
        "created_by": str(user.user_id),
        "created_at": _now(),
        "completed_at": None,
        "summary": summary,
        "graph_data": graph_data,
    }
    if settings.metadata_pg_mode:
        try:
            await postgres_metadata_store.save_snapshot(item, tenant_id=_tenant_id(user))
            if background_tasks:
                background_tasks.add_task(_finalize_snapshot, _tenant_id(user), case_id, ds_name, dict(item))
            audit_log_service.emit(
                action="metadata.snapshot.create",
                actor_id=str(user.user_id),
                tenant_id=str(user.tenant_id),
                resource_type="snapshot",
                resource_id=item["id"],
                request_id=_request_id(request, request_id),
                duration_ms=int((time.perf_counter() - started) * 1000),
                metadata={"case_id": case_id, "datasource": ds_name},
            )
            idempotency_store.set(
                idem_key or "",
                fingerprint=idempotency_store.fingerprint({"case_id": case_id, "ds_name": ds_name, **payload.model_dump()}),
                status_code=202,
                response=item,
            ) if idem_key else None
            return item
        except PostgresStoreUnavailableError as exc:
            raise _svc_error("postgres", "POSTGRES_UNAVAILABLE", exc) from exc
    if settings.metadata_external_mode:
        try:
            await synapse_metadata_client.save_snapshot(item, tenant_id=_tenant_id(user))
            if background_tasks:
                background_tasks.add_task(_finalize_snapshot, _tenant_id(user), case_id, ds_name, dict(item))
            audit_log_service.emit(
                action="metadata.snapshot.create",
                actor_id=str(user.user_id),
                tenant_id=str(user.tenant_id),
                resource_type="snapshot",
                resource_id=item["id"],
                request_id=_request_id(request, request_id),
                duration_ms=int((time.perf_counter() - started) * 1000),
                metadata={"case_id": case_id, "datasource": ds_name},
            )
            idempotency_store.set(
                idem_key or "",
                fingerprint=idempotency_store.fingerprint({"case_id": case_id, "ds_name": ds_name, **payload.model_dump()}),
                status_code=202,
                response=item,
            ) if idem_key else None
            return item
        except SynapseMetadataClientError as exc:
            raise _svc_error("synapse", "SYNAPSE_UNAVAILABLE", exc) from exc
    bucket[snapshot_id] = item
    if background_tasks:
        background_tasks.add_task(_finalize_snapshot, _tenant_id(user), case_id, ds_name, dict(item))
    audit_log_service.emit(
        action="metadata.snapshot.create",
        actor_id=str(user.user_id),
        tenant_id=str(user.tenant_id),
        resource_type="snapshot",
        resource_id=item["id"],
        request_id=_request_id(request, request_id),
        duration_ms=int((time.perf_counter() - started) * 1000),
        metadata={"case_id": case_id, "datasource": ds_name},
    )
    idempotency_store.set(
        idem_key or "",
        fingerprint=idempotency_store.fingerprint({"case_id": case_id, "ds_name": ds_name, **payload.model_dump()}),
        status_code=202,
        response=item,
    ) if idem_key else None
    return item


@router.get("/cases/{case_id}/datasources/{ds_name}/snapshots")
async def list_snapshots(
    case_id: str,
    ds_name: str,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
):
    _ensure_reader(user)
    if settings.metadata_pg_mode:
        try:
            rows = await postgres_metadata_store.list_snapshots(case_id, ds_name, tenant_id=_tenant_id(user))
        except PostgresStoreUnavailableError as exc:
            raise _svc_error("postgres", "POSTGRES_UNAVAILABLE", exc) from exc
    elif settings.metadata_external_mode:
        try:
            rows = await synapse_metadata_client.list_snapshots(case_id, ds_name, tenant_id=_tenant_id(user))
        except SynapseMetadataClientError as exc:
            raise _svc_error("synapse", "SYNAPSE_UNAVAILABLE", exc) from exc
    else:
        rows = sorted(_snapshot_bucket(user, case_id, ds_name).values(), key=lambda x: x["version"], reverse=True)
    start = (page - 1) * size
    items = rows[start : start + size]
    pages = (len(rows) + size - 1) // size if rows else 0
    return {"items": items, "total": len(rows), "page": page, "size": size, "pages": pages}


@router.get("/cases/{case_id}/datasources/{ds_name}/snapshots/diff")
async def diff_snapshots(case_id: str, ds_name: str, from_version: int = Query(..., alias="from"), to_version: int = Query(..., alias="to"), user: CurrentUser = Depends(get_current_user)):
    _ensure_reader(user)
    if from_version >= to_version:
        raise HTTPException(status_code=400, detail="INVALID_VERSION_RANGE")
    if settings.metadata_pg_mode:
        try:
            rows = await postgres_metadata_store.list_snapshots(case_id, ds_name, tenant_id=_tenant_id(user))
        except PostgresStoreUnavailableError as exc:
            raise _svc_error("postgres", "POSTGRES_UNAVAILABLE", exc) from exc
    elif settings.metadata_external_mode:
        try:
            rows = await synapse_metadata_client.list_snapshots(case_id, ds_name, tenant_id=_tenant_id(user))
        except SynapseMetadataClientError as exc:
            raise _svc_error("synapse", "SYNAPSE_UNAVAILABLE", exc) from exc
    else:
        rows = list(_snapshot_bucket(user, case_id, ds_name).values())
    from_item = next((x for x in rows if x["version"] == from_version), None)
    to_item = next((x for x in rows if x["version"] == to_version), None)
    if not from_item or not to_item:
        raise HTTPException(status_code=404, detail="SNAPSHOT_VERSION_NOT_FOUND")

    from_map = _snapshot_schema_map(from_item)
    to_map = _snapshot_schema_map(to_item)

    from_schemas = set(from_map.keys())
    to_schemas = set(to_map.keys())

    from_tables = _flatten_tables(from_map)
    to_tables = _flatten_tables(to_map)

    tables_added = []
    columns_added = []
    columns_removed = []
    columns_modified = []

    for fqn in sorted(set(to_tables.keys()) - set(from_tables.keys())):
        schema_name, table_name = fqn.split(".", 1)
        tables_added.append({"schema": schema_name, "name": table_name, "columns_count": to_tables[fqn]})
        for col_name, col in to_map.get(schema_name, {}).get(table_name, {}).items():
            columns_added.append(
                {
                    "fqn": f"{schema_name}.{table_name}.{col_name}",
                    "dtype": col["dtype"],
                    "nullable": col["nullable"],
                }
            )

    tables_removed = []
    for fqn in sorted(set(from_tables.keys()) - set(to_tables.keys())):
        schema_name, table_name = fqn.split(".", 1)
        tables_removed.append({"schema": schema_name, "name": table_name, "columns_count": from_tables[fqn]})
        for col_name, col in from_map.get(schema_name, {}).get(table_name, {}).items():
            columns_removed.append(
                {
                    "fqn": f"{schema_name}.{table_name}.{col_name}",
                    "dtype": col["dtype"],
                }
            )

    for schema_name in sorted(from_schemas & to_schemas):
        left_tables = from_map[schema_name]
        right_tables = to_map[schema_name]
        for table_name in sorted(set(left_tables.keys()) & set(right_tables.keys())):
            left_cols = left_tables[table_name]
            right_cols = right_tables[table_name]
            for col_name in sorted(set(right_cols.keys()) - set(left_cols.keys())):
                col = right_cols[col_name]
                columns_added.append(
                    {
                        "fqn": f"{schema_name}.{table_name}.{col_name}",
                        "dtype": col["dtype"],
                        "nullable": col["nullable"],
                    }
                )
            for col_name in sorted(set(left_cols.keys()) - set(right_cols.keys())):
                col = left_cols[col_name]
                columns_removed.append(
                    {
                        "fqn": f"{schema_name}.{table_name}.{col_name}",
                        "dtype": col["dtype"],
                    }
                )
            for col_name in sorted(set(left_cols.keys()) & set(right_cols.keys())):
                left_col = left_cols[col_name]
                right_col = right_cols[col_name]
                changes: dict[str, dict[str, Any]] = {}
                for attr in ("dtype", "nullable", "default_value"):
                    if left_col.get(attr) != right_col.get(attr):
                        changes[attr] = {"from": left_col.get(attr), "to": right_col.get(attr)}
                if changes:
                    columns_modified.append({"fqn": f"{schema_name}.{table_name}.{col_name}", "changes": changes})

    diff = {
        "schemas_added": sorted(to_schemas - from_schemas),
        "schemas_removed": sorted(from_schemas - to_schemas),
        "tables_added": tables_added,
        "tables_removed": tables_removed,
        "columns_added": columns_added,
        "columns_removed": columns_removed,
        "columns_modified": columns_modified,
        "fk_added": [],
        "fk_removed": [],
        "tags_added": [],
        "tags_removed": [],
    }
    summary = {
        "tables_added": len(tables_added),
        "tables_removed": len(tables_removed),
        "columns_added": len(columns_added),
        "columns_removed": len(columns_removed),
        "columns_modified": len(columns_modified),
        "fk_added": 0,
        "fk_removed": 0,
        "total_changes": len(tables_added) + len(tables_removed) + len(columns_added) + len(columns_removed) + len(columns_modified),
    }

    return {
        "datasource": ds_name,
        "from_version": from_version,
        "to_version": to_version,
        "from_snapshot_id": from_item["id"],
        "to_snapshot_id": to_item["id"],
        "diff": diff,
        "summary": summary,
    }


@router.get("/cases/{case_id}/datasources/{ds_name}/snapshots/{snapshot_id}")
async def get_snapshot(case_id: str, ds_name: str, snapshot_id: str, user: CurrentUser = Depends(get_current_user)):
    _ensure_reader(user)
    if settings.metadata_pg_mode:
        try:
            item = await postgres_metadata_store.get_snapshot(case_id, ds_name, snapshot_id, tenant_id=_tenant_id(user))
        except PostgresStoreUnavailableError as exc:
            raise _svc_error("postgres", "POSTGRES_UNAVAILABLE", exc) from exc
    elif settings.metadata_external_mode:
        try:
            item = await synapse_metadata_client.get_snapshot(case_id, ds_name, snapshot_id, tenant_id=_tenant_id(user))
        except SynapseMetadataClientError as exc:
            raise _svc_error("synapse", "SYNAPSE_UNAVAILABLE", exc) from exc
    else:
        item = _snapshot_bucket(user, case_id, ds_name).get(snapshot_id)
    if not item:
        raise HTTPException(status_code=404, detail="SNAPSHOT_NOT_FOUND")
    return item


@router.post("/cases/{case_id}/datasources/{ds_name}/snapshots/{snapshot_id}/restore")
async def restore_snapshot(case_id: str, ds_name: str, snapshot_id: str, user: CurrentUser = Depends(get_current_user)):
    _ensure_admin(user)
    if settings.metadata_pg_mode:
        try:
            item = await postgres_metadata_store.get_snapshot(case_id, ds_name, snapshot_id, tenant_id=_tenant_id(user))
        except PostgresStoreUnavailableError as exc:
            raise _svc_error("postgres", "POSTGRES_UNAVAILABLE", exc) from exc
    elif settings.metadata_external_mode:
        try:
            item = await synapse_metadata_client.get_snapshot(case_id, ds_name, snapshot_id, tenant_id=_tenant_id(user))
        except SynapseMetadataClientError as exc:
            raise _svc_error("synapse", "SYNAPSE_UNAVAILABLE", exc) from exc
    else:
        item = _snapshot_bucket(user, case_id, ds_name).get(snapshot_id)
    if not item:
        raise HTTPException(status_code=404, detail="SNAPSHOT_NOT_FOUND")
    graph_data = item.get("graph_data")
    if isinstance(graph_data, dict):
        ds = weaver_runtime.datasources.get(_ds_key(user, ds_name))
        if ds is not None:
            catalog = _graph_data_to_catalog(graph_data)
            if catalog:
                ds["catalog"] = catalog
                ds["schemas_count"] = len(catalog)
                ds["tables_count"] = sum(len(v) for v in catalog.values())
    return {"restored": True, "snapshot_id": snapshot_id, "restored_at": _now()}


@router.delete("/cases/{case_id}/datasources/{ds_name}/snapshots/{snapshot_id}")
async def delete_snapshot(
    case_id: str,
    ds_name: str,
    snapshot_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    request_id: str | None = Header(default=None, alias="X-Request-Id"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    started = time.perf_counter()
    rate_limiter.check(f"{user.user_id}:{request.url.path}:write", limit=60)
    idem_key = _idem_key(user, request.url.path, idempotency_key)
    cached = idempotency_store.ensure(
        key=idem_key,
        payload={"op": "delete_snapshot", "case_id": case_id, "ds_name": ds_name, "snapshot_id": snapshot_id},
    )
    if cached:
        return cached["response"]
    _ensure_admin(user)
    if settings.metadata_pg_mode:
        try:
            ok = await postgres_metadata_store.delete_snapshot(case_id, ds_name, snapshot_id, tenant_id=_tenant_id(user))
        except PostgresStoreUnavailableError as exc:
            raise _svc_error("postgres", "POSTGRES_UNAVAILABLE", exc) from exc
        if not ok:
            raise HTTPException(status_code=404, detail="SNAPSHOT_NOT_FOUND")
    elif settings.metadata_external_mode:
        try:
            ok = await synapse_metadata_client.delete_snapshot(case_id, ds_name, snapshot_id, tenant_id=_tenant_id(user))
        except SynapseMetadataClientError as exc:
            raise _svc_error("synapse", "SYNAPSE_UNAVAILABLE", exc) from exc
        if not ok:
            raise HTTPException(status_code=404, detail="SNAPSHOT_NOT_FOUND")
    else:
        bucket = _snapshot_bucket(user, case_id, ds_name)
        if snapshot_id not in bucket:
            raise HTTPException(status_code=404, detail="SNAPSHOT_NOT_FOUND")
        del bucket[snapshot_id]
    response = {"deleted": True, "snapshot_id": snapshot_id}
    idempotency_store.set(
        idem_key or "",
        fingerprint=idempotency_store.fingerprint(
            {"op": "delete_snapshot", "case_id": case_id, "ds_name": ds_name, "snapshot_id": snapshot_id}
        ),
        status_code=200,
        response=response,
    ) if idem_key else None
    audit_log_service.emit(
        action="metadata.snapshot.delete",
        actor_id=str(user.user_id),
        tenant_id=str(user.tenant_id),
        resource_type="snapshot",
        resource_id=snapshot_id,
        request_id=_request_id(request, request_id),
        duration_ms=int((time.perf_counter() - started) * 1000),
        metadata={"case_id": case_id, "datasource": ds_name},
    )
    return response


@router.post("/glossary", status_code=status.HTTP_201_CREATED)
async def create_term(
    payload: GlossaryCreateRequest,
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
    term_id = weaver_runtime.new_id("term-")
    item = {
        "id": term_id,
        "tenant_id": _tenant_id(user),
        "term": payload.term,
        "definition": payload.definition,
        "synonyms": payload.synonyms,
        "created_at": _now(),
        "updated_at": _now(),
    }
    if settings.metadata_pg_mode:
        try:
            await postgres_metadata_store.save_glossary_term(item, tenant_id=_tenant_id(user))
            audit_log_service.emit(
                action="metadata.glossary.create",
                actor_id=str(user.user_id),
                tenant_id=str(user.tenant_id),
                resource_type="glossary_term",
                resource_id=term_id,
                request_id=_request_id(request, request_id),
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
            idempotency_store.set(
                idem_key or "",
                fingerprint=idempotency_store.fingerprint(payload.model_dump()),
                status_code=201,
                response=item,
            ) if idem_key else None
            return item
        except PostgresStoreUnavailableError as exc:
            raise _svc_error("postgres", "POSTGRES_UNAVAILABLE", exc) from exc
    if settings.metadata_external_mode:
        try:
            await synapse_metadata_client.save_glossary_term(item, tenant_id=_tenant_id(user))
            audit_log_service.emit(
                action="metadata.glossary.create",
                actor_id=str(user.user_id),
                tenant_id=str(user.tenant_id),
                resource_type="glossary_term",
                resource_id=term_id,
                request_id=_request_id(request, request_id),
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
            idempotency_store.set(
                idem_key or "",
                fingerprint=idempotency_store.fingerprint(payload.model_dump()),
                status_code=201,
                response=item,
            ) if idem_key else None
            return item
        except SynapseMetadataClientError as exc:
            raise _svc_error("synapse", "SYNAPSE_UNAVAILABLE", exc) from exc
    weaver_runtime.glossary[f"{_tenant_id(user)}:{term_id}"] = item
    audit_log_service.emit(
        action="metadata.glossary.create",
        actor_id=str(user.user_id),
        tenant_id=str(user.tenant_id),
        resource_type="glossary_term",
        resource_id=term_id,
        request_id=_request_id(request, request_id),
        duration_ms=int((time.perf_counter() - started) * 1000),
    )
    idempotency_store.set(
        idem_key or "",
        fingerprint=idempotency_store.fingerprint(payload.model_dump()),
        status_code=201,
        response=item,
    ) if idem_key else None
    return item


@router.get("/glossary")
async def list_terms(user: CurrentUser = Depends(get_current_user)):
    _ensure_reader(user)
    if settings.metadata_pg_mode:
        try:
            items = await postgres_metadata_store.list_glossary_terms(tenant_id=_tenant_id(user))
            return {"items": items, "total": len(items)}
        except PostgresStoreUnavailableError as exc:
            raise _svc_error("postgres", "POSTGRES_UNAVAILABLE", exc) from exc
    if settings.metadata_external_mode:
        try:
            items = await synapse_metadata_client.list_glossary_terms(tenant_id=_tenant_id(user))
            return {"items": items, "total": len(items)}
        except SynapseMetadataClientError as exc:
            raise _svc_error("synapse", "SYNAPSE_UNAVAILABLE", exc) from exc
    items = sorted(
        [x for x in weaver_runtime.glossary.values() if str(x.get("tenant_id") or "") == _tenant_id(user)],
        key=lambda x: x["created_at"],
        reverse=True,
    )
    return {"items": items, "total": len(items)}


@router.get("/glossary/search")
async def search_terms(q: str = Query(..., min_length=1), user: CurrentUser = Depends(get_current_user)):
    _ensure_reader(user)
    if settings.metadata_pg_mode:
        try:
            items = await postgres_metadata_store.search_glossary_terms(q, tenant_id=_tenant_id(user))
            return {"items": items, "total": len(items)}
        except PostgresStoreUnavailableError as exc:
            raise _svc_error("postgres", "POSTGRES_UNAVAILABLE", exc) from exc
    if settings.metadata_external_mode:
        try:
            items = await synapse_metadata_client.search_glossary_terms(q, tenant_id=_tenant_id(user))
            return {"items": items, "total": len(items)}
        except SynapseMetadataClientError as exc:
            raise _svc_error("synapse", "SYNAPSE_UNAVAILABLE", exc) from exc
    query = q.lower()
    items = [
        x
        for x in weaver_runtime.glossary.values()
        if str(x.get("tenant_id") or "") == _tenant_id(user)
        and (query in x["term"].lower() or query in x["definition"].lower())
    ]
    return {"items": items, "total": len(items)}


@router.get("/glossary/{term_id}")
async def get_term(term_id: str, user: CurrentUser = Depends(get_current_user)):
    _ensure_reader(user)
    if settings.metadata_pg_mode:
        try:
            item = await postgres_metadata_store.get_glossary_term(term_id, tenant_id=_tenant_id(user))
        except PostgresStoreUnavailableError as exc:
            raise _svc_error("postgres", "POSTGRES_UNAVAILABLE", exc) from exc
    elif settings.metadata_external_mode:
        try:
            item = await synapse_metadata_client.get_glossary_term(term_id, tenant_id=_tenant_id(user))
        except SynapseMetadataClientError as exc:
            raise _svc_error("synapse", "SYNAPSE_UNAVAILABLE", exc) from exc
    else:
        item = weaver_runtime.glossary.get(f"{_tenant_id(user)}:{term_id}")
    if not item:
        raise HTTPException(status_code=404, detail="TERM_NOT_FOUND")
    return item


@router.put("/glossary/{term_id}")
async def update_term(
    term_id: str,
    payload: GlossaryUpdateRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    request_id: str | None = Header(default=None, alias="X-Request-Id"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    started = time.perf_counter()
    rate_limiter.check(f"{user.user_id}:{request.url.path}:write", limit=60)
    idem_payload = {"term_id": term_id, **payload.model_dump(exclude_none=True)}
    idem_key = _idem_key(user, request.url.path, idempotency_key)
    cached = idempotency_store.ensure(key=idem_key, payload=idem_payload)
    if cached:
        return cached["response"]
    _ensure_writer(user)
    if settings.metadata_pg_mode:
        try:
            item = await postgres_metadata_store.get_glossary_term(term_id, tenant_id=_tenant_id(user))
        except PostgresStoreUnavailableError as exc:
            raise _svc_error("postgres", "POSTGRES_UNAVAILABLE", exc) from exc
    elif settings.metadata_external_mode:
        try:
            item = await synapse_metadata_client.get_glossary_term(term_id, tenant_id=_tenant_id(user))
        except SynapseMetadataClientError as exc:
            raise _svc_error("synapse", "SYNAPSE_UNAVAILABLE", exc) from exc
    else:
        item = weaver_runtime.glossary.get(f"{_tenant_id(user)}:{term_id}")
    if not item:
        raise HTTPException(status_code=404, detail="TERM_NOT_FOUND")
    for k, v in payload.model_dump(exclude_none=True).items():
        item[k] = v
    item["updated_at"] = _now()
    if settings.metadata_pg_mode:
        try:
            await postgres_metadata_store.save_glossary_term(item, tenant_id=_tenant_id(user))
            audit_log_service.emit(
                action="metadata.glossary.update",
                actor_id=str(user.user_id),
                tenant_id=str(user.tenant_id),
                resource_type="glossary_term",
                resource_id=term_id,
                request_id=_request_id(request, request_id),
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
            idempotency_store.set(
                idem_key or "",
                fingerprint=idempotency_store.fingerprint(idem_payload),
                status_code=200,
                response=item,
            ) if idem_key else None
            return item
        except PostgresStoreUnavailableError as exc:
            raise _svc_error("postgres", "POSTGRES_UNAVAILABLE", exc) from exc
    if settings.metadata_external_mode:
        try:
            await synapse_metadata_client.save_glossary_term(item, tenant_id=_tenant_id(user))
            audit_log_service.emit(
                action="metadata.glossary.update",
                actor_id=str(user.user_id),
                tenant_id=str(user.tenant_id),
                resource_type="glossary_term",
                resource_id=term_id,
                request_id=_request_id(request, request_id),
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
            idempotency_store.set(
                idem_key or "",
                fingerprint=idempotency_store.fingerprint(idem_payload),
                status_code=200,
                response=item,
            ) if idem_key else None
            return item
        except SynapseMetadataClientError as exc:
            raise _svc_error("synapse", "SYNAPSE_UNAVAILABLE", exc) from exc
    audit_log_service.emit(
        action="metadata.glossary.update",
        actor_id=str(user.user_id),
        tenant_id=str(user.tenant_id),
        resource_type="glossary_term",
        resource_id=term_id,
        request_id=_request_id(request, request_id),
        duration_ms=int((time.perf_counter() - started) * 1000),
    )
    idempotency_store.set(
        idem_key or "",
        fingerprint=idempotency_store.fingerprint(idem_payload),
        status_code=200,
        response=item,
    ) if idem_key else None
    return item


@router.delete("/glossary/{term_id}")
async def delete_term(
    term_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    request_id: str | None = Header(default=None, alias="X-Request-Id"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    started = time.perf_counter()
    rate_limiter.check(f"{user.user_id}:{request.url.path}:write", limit=60)
    idem_key = _idem_key(user, request.url.path, idempotency_key)
    cached = idempotency_store.ensure(key=idem_key, payload={"op": "delete_term", "term_id": term_id})
    if cached:
        return cached["response"]
    _ensure_writer(user)
    if settings.metadata_pg_mode:
        try:
            ok = await postgres_metadata_store.delete_glossary_term(term_id, tenant_id=_tenant_id(user))
        except PostgresStoreUnavailableError as exc:
            raise _svc_error("postgres", "POSTGRES_UNAVAILABLE", exc) from exc
        if not ok:
            raise HTTPException(status_code=404, detail="TERM_NOT_FOUND")
    elif settings.metadata_external_mode:
        try:
            ok = await synapse_metadata_client.delete_glossary_term(term_id, tenant_id=_tenant_id(user))
        except SynapseMetadataClientError as exc:
            raise _svc_error("synapse", "SYNAPSE_UNAVAILABLE", exc) from exc
        if not ok:
            raise HTTPException(status_code=404, detail="TERM_NOT_FOUND")
    else:
        key = f"{_tenant_id(user)}:{term_id}"
        if key not in weaver_runtime.glossary:
            raise HTTPException(status_code=404, detail="TERM_NOT_FOUND")
        del weaver_runtime.glossary[key]
    response = {"deleted": True, "term_id": term_id}
    idempotency_store.set(
        idem_key or "",
        fingerprint=idempotency_store.fingerprint({"op": "delete_term", "term_id": term_id}),
        status_code=200,
        response=response,
    ) if idem_key else None
    audit_log_service.emit(
        action="metadata.glossary.delete",
        actor_id=str(user.user_id),
        tenant_id=str(user.tenant_id),
        resource_type="glossary_term",
        resource_id=term_id,
        request_id=_request_id(request, request_id),
        duration_ms=int((time.perf_counter() - started) * 1000),
    )
    return response


@router.post("/cases/{case_id}/datasources/{ds_name}/tables/{table_name}/tags", status_code=status.HTTP_201_CREATED)
async def add_table_tag(case_id: str, ds_name: str, table_name: str, payload: TagRequest, user: CurrentUser = Depends(get_current_user)):
    _ensure_writer(user)
    if settings.metadata_external_mode:
        try:
            tags = await synapse_metadata_client.add_entity_tag(
                _table_entity_key(user, case_id, ds_name, table_name),
                "table",
                {"tenant_id": _tenant_id(user), "case_id": case_id, "datasource": ds_name, "table_name": table_name},
                payload.tag,
            )
            return {"table": table_name, "tags": tags}
        except SynapseMetadataClientError as exc:
            raise _svc_error("synapse", "SYNAPSE_UNAVAILABLE", exc) from exc
    key = (_tenant_id(user), case_id, ds_name, table_name, "table")
    weaver_runtime.table_tags.setdefault(key, set()).add(payload.tag)
    return {"table": table_name, "tags": sorted(weaver_runtime.table_tags[key])}


@router.get("/cases/{case_id}/datasources/{ds_name}/tables/{table_name}/tags")
async def list_table_tags(case_id: str, ds_name: str, table_name: str, user: CurrentUser = Depends(get_current_user)):
    _ensure_reader(user)
    if settings.metadata_external_mode:
        try:
            tags = await synapse_metadata_client.list_entity_tags(_table_entity_key(user, case_id, ds_name, table_name))
            return {"table": table_name, "tags": tags}
        except SynapseMetadataClientError as exc:
            raise _svc_error("synapse", "SYNAPSE_UNAVAILABLE", exc) from exc
    key = (_tenant_id(user), case_id, ds_name, table_name, "table")
    return {"table": table_name, "tags": sorted(weaver_runtime.table_tags.get(key, set()))}


@router.delete("/cases/{case_id}/datasources/{ds_name}/tables/{table_name}/tags/{tag}")
async def delete_table_tag(case_id: str, ds_name: str, table_name: str, tag: str, user: CurrentUser = Depends(get_current_user)):
    _ensure_writer(user)
    if settings.metadata_external_mode:
        try:
            await synapse_metadata_client.remove_entity_tag(_table_entity_key(user, case_id, ds_name, table_name), tag)
            return {"deleted": True, "tag": tag}
        except SynapseMetadataClientError as exc:
            raise _svc_error("synapse", "SYNAPSE_UNAVAILABLE", exc) from exc
    key = (_tenant_id(user), case_id, ds_name, table_name, "table")
    tags = weaver_runtime.table_tags.get(key, set())
    tags.discard(tag)
    return {"deleted": True, "tag": tag}


@router.post("/cases/{case_id}/datasources/{ds_name}/tables/{table_name}/columns/{column_name}/tags", status_code=status.HTTP_201_CREATED)
async def add_column_tag(case_id: str, ds_name: str, table_name: str, column_name: str, payload: TagRequest, user: CurrentUser = Depends(get_current_user)):
    _ensure_writer(user)
    if settings.metadata_external_mode:
        try:
            tags = await synapse_metadata_client.add_entity_tag(
                _column_entity_key(user, case_id, ds_name, table_name, column_name),
                "column",
                {
                    "tenant_id": _tenant_id(user),
                    "case_id": case_id,
                    "datasource": ds_name,
                    "table_name": table_name,
                    "column_name": column_name,
                },
                payload.tag,
            )
            return {"column": column_name, "tags": tags}
        except SynapseMetadataClientError as exc:
            raise _svc_error("synapse", "SYNAPSE_UNAVAILABLE", exc) from exc
    key = (_tenant_id(user), case_id, ds_name, table_name, column_name, "column")
    weaver_runtime.column_tags.setdefault(key, set()).add(payload.tag)
    return {"column": column_name, "tags": sorted(weaver_runtime.column_tags[key])}


@router.get("/cases/{case_id}/datasources/{ds_name}/tables/{table_name}/columns/{column_name}/tags")
async def list_column_tags(case_id: str, ds_name: str, table_name: str, column_name: str, user: CurrentUser = Depends(get_current_user)):
    _ensure_reader(user)
    if settings.metadata_external_mode:
        try:
            tags = await synapse_metadata_client.list_entity_tags(_column_entity_key(user, case_id, ds_name, table_name, column_name))
            return {"column": column_name, "tags": tags}
        except SynapseMetadataClientError as exc:
            raise _svc_error("synapse", "SYNAPSE_UNAVAILABLE", exc) from exc
    key = (_tenant_id(user), case_id, ds_name, table_name, column_name, "column")
    return {"column": column_name, "tags": sorted(weaver_runtime.column_tags.get(key, set()))}


@router.delete("/cases/{case_id}/datasources/{ds_name}/tables/{table_name}/columns/{column_name}/tags/{tag}")
async def delete_column_tag(case_id: str, ds_name: str, table_name: str, column_name: str, tag: str, user: CurrentUser = Depends(get_current_user)):
    _ensure_writer(user)
    if settings.metadata_external_mode:
        try:
            await synapse_metadata_client.remove_entity_tag(_column_entity_key(user, case_id, ds_name, table_name, column_name), tag)
            return {"deleted": True, "tag": tag}
        except SynapseMetadataClientError as exc:
            raise _svc_error("synapse", "SYNAPSE_UNAVAILABLE", exc) from exc
    key = (_tenant_id(user), case_id, ds_name, table_name, column_name, "column")
    tags = weaver_runtime.column_tags.get(key, set())
    tags.discard(tag)
    return {"deleted": True, "tag": tag}


@router.get("/tags/{tag}/entities")
async def entities_by_tag(tag: str, user: CurrentUser = Depends(get_current_user)):
    _ensure_reader(user)
    if settings.metadata_external_mode:
        try:
            entities = await synapse_metadata_client.entities_by_tag(tag, tenant_id=_tenant_id(user))
            return {"tag": tag, "entities": entities, "total": len(entities)}
        except SynapseMetadataClientError as exc:
            raise _svc_error("synapse", "SYNAPSE_UNAVAILABLE", exc) from exc
    entities = []
    for (tenant_id, case_id, ds_name, table_name, _), tags in weaver_runtime.table_tags.items():
        if tenant_id != _tenant_id(user):
            continue
        if tag in tags:
            entities.append({"entity_type": "table", "case_id": case_id, "datasource": ds_name, "table": table_name})
    for (tenant_id, case_id, ds_name, table_name, column_name, _), tags in weaver_runtime.column_tags.items():
        if tenant_id != _tenant_id(user):
            continue
        if tag in tags:
            entities.append(
                {"entity_type": "column", "case_id": case_id, "datasource": ds_name, "table": table_name, "column": column_name}
            )
    return {"tag": tag, "entities": entities, "total": len(entities)}


@router.get("/search")
async def metadata_search(q: str = Query(..., min_length=1), user: CurrentUser = Depends(get_current_user)):
    _ensure_reader(user)
    if settings.metadata_pg_mode:
        try:
            term_items = await postgres_metadata_store.search_glossary_terms(q, tenant_id=_tenant_id(user))
            results = [{"type": "term", "name": x["term"], "id": x["id"]} for x in term_items]
            return {"items": results, "total": len(results)}
        except PostgresStoreUnavailableError as exc:
            raise _svc_error("postgres", "POSTGRES_UNAVAILABLE", exc) from exc
    if settings.metadata_external_mode:
        try:
            term_items = await synapse_metadata_client.search_glossary_terms(q, tenant_id=_tenant_id(user))
            results = [{"type": "term", "name": x["term"], "id": x["id"]} for x in term_items]
            return {"items": results, "total": len(results)}
        except SynapseMetadataClientError as exc:
            raise _svc_error("synapse", "SYNAPSE_UNAVAILABLE", exc) from exc
    query = q.lower()
    results = []
    for ds in weaver_runtime.datasources.values():
        if str(ds.get("tenant_id") or "") != _tenant_id(user):
            continue
        if query in ds["name"].lower():
            results.append({"type": "datasource", "name": ds["name"]})
    for term in weaver_runtime.glossary.values():
        if str(term.get("tenant_id") or "") != _tenant_id(user):
            continue
        if query in term["term"].lower():
            results.append({"type": "term", "name": term["term"], "id": term["id"]})
    return {"items": results, "total": len(results)}


@router.get("/cases/{case_id}/datasources/{ds_name}/schemas")
async def list_metadata_schemas(case_id: str, ds_name: str, user: CurrentUser = Depends(get_current_user)):
    _ensure_reader(user)
    catalog = _require_datasource_catalog(user, ds_name)
    return {"case_id": case_id, "datasource": ds_name, "schemas": sorted(catalog.keys())}


@router.get("/cases/{case_id}/datasources/{ds_name}/schemas/{schema_name}/tables")
async def list_metadata_tables(case_id: str, ds_name: str, schema_name: str, user: CurrentUser = Depends(get_current_user)):
    _ensure_reader(user)
    catalog = _require_datasource_catalog(user, ds_name)
    tables = catalog.get(schema_name)
    if not isinstance(tables, dict):
        raise HTTPException(status_code=404, detail="SCHEMA_NOT_FOUND")
    return {"case_id": case_id, "datasource": ds_name, "schema": schema_name, "tables": sorted(tables.keys())}


@router.get("/cases/{case_id}/datasources/{ds_name}/schemas/{schema_name}/tables/{table_name}/columns")
async def list_metadata_columns(case_id: str, ds_name: str, schema_name: str, table_name: str, user: CurrentUser = Depends(get_current_user)):
    _ensure_reader(user)
    catalog = _require_datasource_catalog(user, ds_name)
    tables = catalog.get(schema_name)
    if not isinstance(tables, dict):
        raise HTTPException(status_code=404, detail="SCHEMA_NOT_FOUND")
    columns = tables.get(table_name)
    if not isinstance(columns, list):
        raise HTTPException(status_code=404, detail="TABLE_NOT_FOUND")
    return {
        "case_id": case_id,
        "datasource": ds_name,
        "schema": schema_name,
        "table": table_name,
        "columns": columns,
    }


@router.get("/cases/{case_id}/datasources/{ds_name}/stats")
async def datasource_stats(case_id: str, ds_name: str, user: CurrentUser = Depends(get_current_user)):
    _ensure_reader(user)
    catalog = _require_datasource_catalog(user, ds_name)
    schema_count = len(catalog)
    table_count = 0
    column_count = 0
    for tables in catalog.values():
        if not isinstance(tables, dict):
            continue
        table_count += len(tables)
        for cols in tables.values():
            if isinstance(cols, list):
                column_count += len(cols)

    if settings.metadata_pg_mode:
        try:
            snapshot_count = len(await postgres_metadata_store.list_snapshots(case_id, ds_name, tenant_id=_tenant_id(user)))
        except PostgresStoreUnavailableError as exc:
            raise _svc_error("postgres", "POSTGRES_UNAVAILABLE", exc) from exc
    elif settings.metadata_external_mode:
        try:
            snapshot_count = len(await synapse_metadata_client.list_snapshots(case_id, ds_name, tenant_id=_tenant_id(user)))
        except SynapseMetadataClientError as exc:
            raise _svc_error("synapse", "SYNAPSE_UNAVAILABLE", exc) from exc
    else:
        snapshot_count = len(_snapshot_bucket(user, case_id, ds_name))
    return {
        "case_id": case_id,
        "datasource": ds_name,
        "stats": {"schemas": schema_count, "tables": table_count, "columns": column_count, "snapshots": snapshot_count},
    }


@router.get("/stats")
async def tenant_stats(user: CurrentUser = Depends(get_current_user)):
    _ensure_reader(user)
    if settings.metadata_pg_mode:
        try:
            stats = await postgres_metadata_store.stats(tenant_id=_tenant_id(user))
            return {"tenant_id": str(user.tenant_id), "stats": stats}
        except PostgresStoreUnavailableError as exc:
            raise _svc_error("postgres", "POSTGRES_UNAVAILABLE", exc) from exc
    if settings.metadata_external_mode:
        try:
            stats = await synapse_metadata_client.stats(tenant_id=_tenant_id(user))
            return {"tenant_id": str(user.tenant_id), "stats": stats}
        except SynapseMetadataClientError as exc:
            raise _svc_error("synapse", "SYNAPSE_UNAVAILABLE", exc) from exc
    return {
        "tenant_id": str(user.tenant_id),
        "stats": {
            "datasources": len([x for x in weaver_runtime.datasources.values() if str(x.get("tenant_id") or "") == _tenant_id(user)]),
            "glossary_terms": len([x for x in weaver_runtime.glossary.values() if str(x.get("tenant_id") or "") == _tenant_id(user)]),
            "snapshots": sum(len(v) for k, v in weaver_runtime.snapshots.items() if k[0] == _tenant_id(user)),
        },
    }
