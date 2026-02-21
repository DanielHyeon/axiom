from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.text2sql import get_current_user
from app.core.auth import CurrentUser, auth_service
from app.core.synapse_client import synapse_client

router = APIRouter(prefix="/text2sql/meta", tags=["Meta"])


class DescriptionUpdateRequest(BaseModel):
    datasource_id: str
    description: str = Field(..., min_length=1, max_length=500)


def _resolve_datasource(datasource_id: str) -> dict[str, Any]:
    for item in synapse_client.list_datasources():
        if item.get("id") == datasource_id:
            return item
    raise HTTPException(status_code=404, detail="datasource not found")


def _fallback_tables() -> list[dict[str, Any]]:
    return [
        {
            "name": "processes",
            "description": "프로세스 실행 내역",
            "row_count": 1250,
            "column_count": 4,
            "has_embedding": True,
        },
        {
            "name": "organizations",
            "description": "이해관계자 정보",
            "row_count": 320,
            "column_count": 2,
            "has_embedding": True,
        },
    ]


@router.get("/tables")
async def list_tables(
    datasource_id: str = Query(...),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    valid_only: bool = Query(default=True),
    user: CurrentUser = Depends(get_current_user),
):
    auth_service.requires_role(user, ["admin", "manager", "attorney", "analyst", "engineer"])
    datasource = _resolve_datasource(datasource_id)

    try:
        payload = await synapse_client.list_schema_tables(str(user.tenant_id))
        rows = payload.get("data", {}).get("tables", [])
    except Exception:
        rows = _fallback_tables()

    items = []
    for row in rows:
        table = {
            "name": row.get("name"),
            "schema": datasource.get("schema", "public"),
            "db": datasource.get("database", ""),
            "description": row.get("description"),
            "column_count": int(row.get("column_count", 0)),
            "is_valid": bool(row.get("has_embedding", True)),
            "has_vector": bool(row.get("has_embedding", False)),
        }
        if valid_only and not table["is_valid"]:
            continue
        if search:
            keyword = search.lower().strip()
            name = str(table.get("name") or "").lower()
            desc = str(table.get("description") or "").lower()
            if keyword not in name and keyword not in desc:
                continue
        items.append(table)

    total_count = len(items)
    offset = (page - 1) * page_size
    page_items = items[offset : offset + page_size]
    total_pages = (total_count + page_size - 1) // page_size
    return {
        "success": True,
        "data": {
            "tables": page_items,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_count": total_count,
                "total_pages": total_pages,
            },
        },
    }


@router.get("/tables/{name}/columns")
async def get_table_columns(
    name: str,
    datasource_id: str = Query(...),
    user: CurrentUser = Depends(get_current_user),
):
    auth_service.requires_role(user, ["admin", "manager", "attorney", "analyst", "engineer"])
    datasource = _resolve_datasource(datasource_id)

    try:
        payload = await synapse_client.get_schema_table(str(user.tenant_id), name)
        table = payload.get("data", {})
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 400:
            raise HTTPException(status_code=404, detail="table not found")
        raise HTTPException(status_code=503, detail="meta provider unavailable")
    except Exception:
        raise HTTPException(status_code=503, detail="meta provider unavailable")

    columns = []
    for col in table.get("columns", []):
        col_name = str(col.get("name") or "")
        columns.append(
            {
                "name": col_name,
                "fqn": f"{datasource.get('schema', 'public')}.{name}.{col_name}",
                "data_type": col.get("data_type"),
                "nullable": True,
                "is_primary_key": col_name == "id",
                "description": col.get("description"),
                "has_vector": bool(table.get("has_embedding", False)),
                "foreign_keys": [],
            }
        )

    return {
        "success": True,
        "data": {
            "table": {
                "name": name,
                "schema": datasource.get("schema", "public"),
                "description": table.get("description"),
            },
            "columns": columns,
            "value_mappings": [],
        },
    }


@router.get("/datasources")
async def list_datasources(user: CurrentUser = Depends(get_current_user)):
    auth_service.requires_role(user, ["admin", "manager", "attorney", "analyst", "engineer"])
    rows = synapse_client.list_datasources()
    return {"success": True, "data": {"datasources": rows}}


@router.put("/tables/{name}/description")
async def update_table_description(
    name: str,
    payload: DescriptionUpdateRequest,
    user: CurrentUser = Depends(get_current_user),
):
    auth_service.requires_role(user, ["admin"])
    _resolve_datasource(payload.datasource_id)
    try:
        response = await synapse_client.update_table_description(str(user.tenant_id), name, payload.description)
        data = response.get("data", {})
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 400:
            raise HTTPException(status_code=400, detail="invalid table or payload")
        raise HTTPException(status_code=503, detail="meta provider unavailable")
    except Exception:
        raise HTTPException(status_code=503, detail="meta provider unavailable")
    return {
        "success": True,
        "data": {
            "table": data.get("table_name", name),
            "description": data.get("description", payload.description),
            "vector_updated": bool(data.get("embedding_updated", False)),
        },
    }


@router.put("/columns/{fqn}/description")
async def update_column_description(
    fqn: str,
    payload: DescriptionUpdateRequest,
    user: CurrentUser = Depends(get_current_user),
):
    auth_service.requires_role(user, ["admin"])
    _resolve_datasource(payload.datasource_id)
    parts = fqn.split(".")
    if len(parts) != 3:
        raise HTTPException(status_code=400, detail="fqn must be schema.table.column")
    _, table_name, column_name = parts
    try:
        response = await synapse_client.update_column_description(
            str(user.tenant_id),
            table_name=table_name,
            column_name=column_name,
            description=payload.description,
        )
        data = response.get("data", {})
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 400:
            raise HTTPException(status_code=400, detail="invalid table/column or payload")
        raise HTTPException(status_code=503, detail="meta provider unavailable")
    except Exception:
        raise HTTPException(status_code=503, detail="meta provider unavailable")
    return {
        "success": True,
        "data": {
            "column_fqn": fqn,
            "description": data.get("description", payload.description),
            "vector_updated": bool(data.get("embedding_updated", False)),
        },
    }
