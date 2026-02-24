from dataclasses import asdict

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.text2sql import get_current_user
from app.core.auth import CurrentUser, auth_service
from app.infrastructure.acl.synapse_acl import oracle_synapse_acl, DatasourceInfo

router = APIRouter(prefix="/text2sql/meta", tags=["Meta"])


class DescriptionUpdateRequest(BaseModel):
    datasource_id: str
    description: str = Field(..., min_length=1, max_length=500)


def _resolve_datasource(datasource_id: str) -> DatasourceInfo:
    """ACL을 통해 데이터소스 조회."""
    for ds in oracle_synapse_acl.list_datasources():
        if ds.id == datasource_id:
            return ds
    raise HTTPException(status_code=404, detail="datasource not found")


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
        table_infos = await oracle_synapse_acl.list_tables(str(user.tenant_id))
    except Exception:
        table_infos = []

    if not table_infos:
        raise HTTPException(
            status_code=503,
            detail="스키마 메타데이터를 불러올 수 없습니다. Synapse 연결을 확인하세요.",
        )

    rows = [
        {
            "name": t.name,
            "schema": datasource.schema,
            "db": datasource.database,
            "description": t.description,
            "column_count": len(t.columns),
            "is_valid": t.has_embedding,
            "has_vector": t.has_embedding,
        }
        for t in table_infos
    ]

    items = []
    for table in rows:
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
        table_info = await oracle_synapse_acl.get_table_detail(str(user.tenant_id), name)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 400:
            raise HTTPException(status_code=404, detail="table not found")
        raise HTTPException(status_code=503, detail="meta provider unavailable")
    except Exception:
        raise HTTPException(status_code=503, detail="meta provider unavailable")

    if not table_info:
        raise HTTPException(status_code=404, detail="table not found")

    columns = [
        {
            "name": col.name,
            "fqn": f"{datasource.schema}.{name}.{col.name}",
            "data_type": col.data_type,
            "nullable": True,
            "is_primary_key": col.is_key,
            "description": col.description,
            "has_vector": table_info.has_embedding,
            "foreign_keys": [],
        }
        for col in table_info.columns
    ]

    return {
        "success": True,
        "data": {
            "table": {
                "name": name,
                "schema": datasource.schema,
                "description": table_info.description,
            },
            "columns": columns,
            "value_mappings": [],
        },
    }


@router.get("/datasources")
async def list_datasources(user: CurrentUser = Depends(get_current_user)):
    auth_service.requires_role(user, ["admin", "manager", "attorney", "analyst", "engineer"])
    ds_list = oracle_synapse_acl.list_datasources()
    return {"success": True, "data": {"datasources": [asdict(ds) for ds in ds_list]}}


@router.put("/tables/{name}/description")
async def update_table_description(
    name: str,
    payload: DescriptionUpdateRequest,
    user: CurrentUser = Depends(get_current_user),
):
    auth_service.requires_role(user, ["admin"])
    _resolve_datasource(payload.datasource_id)
    try:
        result = await oracle_synapse_acl.update_table_description(
            str(user.tenant_id), name, payload.description
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 400:
            raise HTTPException(status_code=400, detail="invalid table or payload")
        raise HTTPException(status_code=503, detail="meta provider unavailable")
    except Exception:
        raise HTTPException(status_code=503, detail="meta provider unavailable")
    return {
        "success": True,
        "data": {
            "table": result.name,
            "description": result.description,
            "vector_updated": result.vector_updated,
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
        result = await oracle_synapse_acl.update_column_description(
            str(user.tenant_id),
            table_name=table_name,
            column_name=column_name,
            description=payload.description,
        )
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
            "description": result.description,
            "vector_updated": result.vector_updated,
        },
    }
