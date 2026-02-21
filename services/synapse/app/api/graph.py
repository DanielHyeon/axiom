from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.api.ontology import ontology_service
from app.services.graph_search_service import graph_search_service

router = APIRouter(prefix="/api/v3/synapse/graph", tags=["Graph Search"])


async def verify_case_access(case_id: str, request: Request) -> str:
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=401, detail="tenant not resolved")
    return case_id


@router.post("/search")
async def search_graph(query_req: dict[str, Any], request: Request):
    case_id = query_req.get("case_id")
    if case_id:
        await verify_case_access(case_id, request)
    try:
        return {"success": True, "data": graph_search_service.search(query_req)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/vector-search")
async def vector_search(query_req: dict[str, Any], request: Request):
    _ = request
    query = str(query_req.get("query") or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="query is required")
    return {
        "success": True,
        "data": graph_search_service.vector_search(
            query=query,
            target=str(query_req.get("target") or "all"),
            top_k=int(query_req.get("top_k", 5)),
            min_score=float(query_req.get("min_score", 0.7)),
        ),
    }


@router.post("/fk-path")
async def fk_path_search(query_req: dict[str, Any], request: Request):
    _ = request
    start_table = str(query_req.get("start_table") or "").strip()
    if not start_table:
        raise HTTPException(status_code=400, detail="start_table is required")
    try:
        data = graph_search_service.fk_path(
            start_table=start_table,
            max_hops=int(query_req.get("max_hops", 3)),
            direction=str(query_req.get("direction") or "both"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.post("/ontology-path")
async def ontology_path_search(query_req: dict[str, Any], request: Request):
    case_id = query_req.get("case_id")
    if case_id:
        await verify_case_access(case_id, request)
    if not case_id:
        raise HTTPException(status_code=400, detail="case_id is required")

    ont = await ontology_service.get_case_ontology(case_id=case_id, limit=500)
    data = graph_search_service.ontology_path(query_req, ontology_nodes=ont["nodes"])
    return {"success": True, "data": data}


@router.get("/tables/{table_name}/related")
async def related_tables(table_name: str, max_hops: int = 2):
    try:
        return {"success": True, "data": graph_search_service.tables_related(table_name, max_hops=max_hops)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/stats")
async def graph_stats():
    return {"success": True, "data": graph_search_service.stats()}
