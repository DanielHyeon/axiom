from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from app.core.neo4j_client import neo4j_client
from app.services.ontology_service import OntologyService
from app.services.ontology_exporter import OntologyExporter
from app.services.quality_service import OntologyQualityService
from app.services.hitl_service import HITLService
from app.services.snapshot_service import SnapshotService

router = APIRouter(prefix="/api/v3/synapse/ontology", tags=["Ontology"])
ontology_service = OntologyService(neo4j_client)
ontology_exporter = OntologyExporter(ontology_service)
quality_service = OntologyQualityService(ontology_service)
hitl_service = HITLService(ontology_service=ontology_service)
snapshot_service = SnapshotService(neo4j_client, ontology_service)


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


# -- O5-1: OWL/RDF Export -----------------------------------------------------


@router.get("/cases/{case_id}/export")
async def export_ontology(case_id: str, format: str = "turtle", request: Request = None):
    tenant_id = _tenant(request) if request else "unknown"
    try:
        if format == "turtle":
            content = await ontology_exporter.export_turtle(case_id, tenant_id)
            return Response(
                content,
                media_type="text/turtle",
                headers={"Content-Disposition": f'attachment; filename="ontology-{case_id}.ttl"'},
            )
        elif format == "jsonld":
            content = await ontology_exporter.export_jsonld(case_id, tenant_id)
            return Response(
                content,
                media_type="application/ld+json",
                headers={"Content-Disposition": f'attachment; filename="ontology-{case_id}.jsonld"'},
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported format: {format}. Use 'turtle' or 'jsonld'.")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Export failed: {exc}") from exc


# -- O5-2: Quality Dashboard --------------------------------------------------


@router.get("/cases/{case_id}/quality")
async def get_quality_report(case_id: str):
    report = await quality_service.generate_report(case_id)
    return {"success": True, "data": report}


# -- O5-3: HITL Review Queue --------------------------------------------------


@router.get("/cases/{case_id}/hitl")
async def list_hitl_items(case_id: str, status: str = "pending", limit: int = 50, offset: int = 0):
    data = hitl_service.list_items(case_id=case_id, status=status, limit=limit, offset=offset)
    return {"success": True, "data": data}


@router.post("/hitl/submit")
async def submit_hitl(request: Request, body: dict[str, Any]):
    node_id = str(body.get("node_id") or "").strip()
    case_id = str(body.get("case_id") or "").strip()
    if not node_id or not case_id:
        raise HTTPException(status_code=400, detail="node_id and case_id are required")
    data = hitl_service.submit_for_review(node_id=node_id, case_id=case_id, tenant_id=_tenant(request))
    return {"success": True, "data": data}


@router.post("/hitl/{item_id}/approve")
async def approve_hitl(item_id: str, request: Request, body: dict[str, Any] | None = None):
    body = body or {}
    reviewer_id = str(body.get("reviewer_id") or _tenant(request))
    comment = str(body.get("comment") or "")
    try:
        data = await hitl_service.approve(item_id=item_id, reviewer_id=reviewer_id, comment=comment)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.post("/hitl/{item_id}/reject")
async def reject_hitl(item_id: str, request: Request, body: dict[str, Any] | None = None):
    body = body or {}
    reviewer_id = str(body.get("reviewer_id") or _tenant(request))
    comment = str(body.get("comment") or "")
    try:
        data = await hitl_service.reject(item_id=item_id, reviewer_id=reviewer_id, comment=comment)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "data": data}


# -- O5-4: Version Management (Snapshots) -------------------------------------


@router.post("/cases/{case_id}/snapshots")
async def create_snapshot(case_id: str, request: Request):
    data = await snapshot_service.create_snapshot(case_id=case_id, tenant_id=_tenant(request))
    return {"success": True, "data": data}


@router.get("/cases/{case_id}/snapshots")
async def list_snapshots(case_id: str):
    data = await snapshot_service.list_snapshots(case_id=case_id)
    return {"success": True, "data": data}


@router.get("/snapshots/diff")
async def diff_snapshots(snapshot_a: str, snapshot_b: str):
    try:
        data = await snapshot_service.diff_snapshots(snapshot_a=snapshot_a, snapshot_b=snapshot_b)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "data": data}


# -- O5-5: GlossaryTerm ↔ Ontology Bridge ------------------------------------


@router.get("/cases/{case_id}/glossary-suggest")
async def suggest_glossary(case_id: str, term: str):
    if not term.strip():
        raise HTTPException(status_code=400, detail="term is required")
    data = await ontology_service.suggest_glossary_matches(term_name=term, case_id=case_id)
    return {"success": True, "data": data}


@router.post("/cases/{case_id}/glossary-link")
async def create_glossary_link(case_id: str, body: dict[str, Any]):
    term_id = str(body.get("term_id") or "").strip()
    node_id = str(body.get("node_id") or "").strip()
    if not term_id or not node_id:
        raise HTTPException(status_code=400, detail="term_id and node_id are required")
    try:
        data = await ontology_service.create_glossary_link(term_id=term_id, node_id=node_id, case_id=case_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Link creation failed: {exc}") from exc
    return {"success": True, "data": data}
