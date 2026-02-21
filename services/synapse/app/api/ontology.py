from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.core.neo4j_client import neo4j_client
from app.services.ontology_service import OntologyService

router = APIRouter(prefix="/api/v3/synapse/ontology", tags=["Ontology"])
ontology_service = OntologyService(neo4j_client)


def _tenant(request: Request) -> str:
    return getattr(request.state, "tenant_id", "unknown")


@router.get("/")
async def get_ontology(request: Request, case_id: str | None = None, limit: int = 200):
    if not case_id:
        raise HTTPException(status_code=400, detail="case_id is required")
    data = await ontology_service.get_case_ontology(case_id=case_id, limit=limit)
    return {"success": True, "data": data, "tenant_id": _tenant(request)}


@router.post("/extract-ontology")
async def extract_ontology(request: Request, payload: dict[str, Any]):
    try:
        result = await ontology_service.extract_ontology(tenant_id=_tenant(request), payload=payload or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": result}


@router.get("/cases/{case_id}/ontology")
async def get_case_ontology(
    case_id: str,
    layer: str = "all",
    include_relations: bool = True,
    verified_only: bool = False,
    limit: int = 500,
    offset: int = 0,
):
    data = await ontology_service.get_case_ontology(
        case_id=case_id,
        layer=layer,
        include_relations=include_relations,
        verified_only=verified_only,
        limit=limit,
        offset=offset,
    )
    return {"success": True, "data": data, "pagination": data["pagination"]}


@router.get("/cases/{case_id}/ontology/summary")
async def get_case_ontology_summary(case_id: str):
    return {"success": True, "data": await ontology_service.get_case_summary(case_id)}


@router.get("/cases/{case_id}/ontology/{layer}")
async def get_case_ontology_by_layer(case_id: str, layer: str, limit: int = 500, offset: int = 0):
    data = await ontology_service.get_case_ontology(case_id=case_id, layer=layer, limit=limit, offset=offset)
    return {"success": True, "data": data, "pagination": data["pagination"]}


@router.post("/nodes")
async def create_node(request: Request, payload: dict[str, Any]):
    try:
        data = await ontology_service.create_node(tenant_id=_tenant(request), payload=payload or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.get("/nodes/{node_id}")
async def get_node(node_id: str):
    data = ontology_service.get_node(node_id)
    if not data:
        raise HTTPException(status_code=404, detail="node not found")
    return {"success": True, "data": data}


@router.put("/nodes/{node_id}")
async def update_node(node_id: str, request: Request, payload: dict[str, Any]):
    try:
        data = await ontology_service.update_node(tenant_id=_tenant(request), node_id=node_id, payload=payload or {})
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.delete("/nodes/{node_id}")
async def delete_node(node_id: str):
    try:
        data = await ontology_service.delete_node(node_id=node_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.post("/relations")
async def create_relation(request: Request, payload: dict[str, Any]):
    try:
        data = await ontology_service.create_relation(tenant_id=_tenant(request), payload=payload or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.delete("/relations/{relation_id}")
async def delete_relation(relation_id: str):
    try:
        data = await ontology_service.delete_relation(relation_id=relation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.get("/nodes/{node_id}/neighbors")
async def get_neighbors(node_id: str, limit: int = 100):
    try:
        data = await ontology_service.get_neighbors(node_id=node_id, limit=limit)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.get("/nodes/{node_id}/path-to/{target_id}")
async def get_path(node_id: str, target_id: str, max_depth: int = 6):
    try:
        data = await ontology_service.path_to(source_id=node_id, target_id=target_id, max_depth=max_depth)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "data": data}
