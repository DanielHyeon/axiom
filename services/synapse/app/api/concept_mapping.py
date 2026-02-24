"""Concept Mapping API — OntologyNode ↔ Table 매핑 (O2-A)."""
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.services.metadata_graph_service import metadata_graph_service

router = APIRouter(prefix="/api/v3/synapse/ontology/concept-mappings", tags=["Concept Mapping"])


def _tenant(request: Request) -> str:
    return getattr(request.state, "tenant_id", "") or ""


@router.post("/")
async def create_mapping(body: dict[str, Any], request: Request):
    result = await metadata_graph_service.create_concept_mapping(
        source_id=body["source_id"],
        target_id=body["target_id"],
        rel_type=body.get("rel_type", "MAPS_TO"),
        tenant_id=_tenant(request),
    )
    if not result:
        raise HTTPException(400, detail="Failed to create mapping. Source or target not found.")
    return {"success": True, "data": result}


@router.get("/")
async def list_mappings(case_id: str, request: Request):
    data = await metadata_graph_service.list_concept_mappings(case_id, _tenant(request))
    return {"success": True, "data": data}


@router.delete("/{rel_id}")
async def delete_mapping(rel_id: str):
    deleted = await metadata_graph_service.delete_concept_mapping(rel_id)
    if not deleted:
        raise HTTPException(404, detail="Mapping not found")
    return {"success": True, "deleted": True}


@router.get("/suggest")
async def suggest(q: str, request: Request):
    suggestions = await metadata_graph_service.suggest_mappings(q, _tenant(request))
    return {"success": True, "data": suggestions}


@router.get("/schema-entities")
async def schema_entities(request: Request, datasource: str | None = None):
    data = await metadata_graph_service.list_schema_entities(_tenant(request), datasource)
    return {"success": True, "data": data}
