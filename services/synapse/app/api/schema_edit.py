from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from app.services.schema_edit_service import SchemaEditDomainError, schema_edit_service

router = APIRouter(prefix="/api/v3/synapse/schema-edit", tags=["Schema Edit"])


def _tenant(request: Request) -> str:
    return getattr(request.state, "tenant_id", "default")


def _raise(e: SchemaEditDomainError) -> None:
    raise HTTPException(status_code=e.status_code, detail={"code": e.code, "message": e.message})


@router.get("/tables")
async def list_tables(request: Request):
    try:
        return {"success": True, "data": schema_edit_service.list_tables(_tenant(request))}
    except SchemaEditDomainError as e:
        _raise(e)


@router.get("/tables/{table_name}")
async def get_table(table_name: str, request: Request):
    try:
        return {"success": True, "data": schema_edit_service.get_table(_tenant(request), table_name)}
    except SchemaEditDomainError as e:
        _raise(e)


@router.put("/tables/{table_name}/description")
async def update_table_description(table_name: str, payload: dict[str, Any], request: Request):
    try:
        desc = str((payload or {}).get("description") or "")
        return {"success": True, "data": schema_edit_service.update_table_description(_tenant(request), table_name, desc)}
    except SchemaEditDomainError as e:
        _raise(e)


@router.put("/columns/{table_name}/{column_name}/description")
async def update_column_description(table_name: str, column_name: str, payload: dict[str, Any], request: Request):
    try:
        desc = str((payload or {}).get("description") or "")
        return {
            "success": True,
            "data": schema_edit_service.update_column_description(_tenant(request), table_name, column_name, desc),
        }
    except SchemaEditDomainError as e:
        _raise(e)


@router.get("/relationships")
async def list_relationships(request: Request):
    try:
        return {"success": True, "data": schema_edit_service.list_relationships(_tenant(request))}
    except SchemaEditDomainError as e:
        _raise(e)


@router.post("/relationships", status_code=status.HTTP_201_CREATED)
async def create_relationship(payload: dict[str, Any], request: Request):
    try:
        return {"success": True, "data": schema_edit_service.create_relationship(_tenant(request), payload or {})}
    except SchemaEditDomainError as e:
        _raise(e)


@router.delete("/relationships/{rel_id}")
async def delete_relationship(rel_id: str, request: Request):
    try:
        return {"success": True, "data": schema_edit_service.delete_relationship(_tenant(request), rel_id)}
    except SchemaEditDomainError as e:
        _raise(e)


@router.post("/tables/{table_name}/embedding")
async def rebuild_table_embedding(table_name: str, request: Request):
    try:
        return {"success": True, "data": schema_edit_service.rebuild_table_embedding(_tenant(request), table_name)}
    except SchemaEditDomainError as e:
        _raise(e)


@router.post("/batch-update-embeddings", status_code=status.HTTP_202_ACCEPTED)
async def batch_update_embeddings(payload: dict[str, Any], request: Request):
    try:
        target = str((payload or {}).get("target") or "all")
        force = bool((payload or {}).get("force", False))
        return {"success": True, "data": schema_edit_service.batch_update_embeddings(_tenant(request), target, force)}
    except SchemaEditDomainError as e:
        _raise(e)
