from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.api.ontology import ontology_service
from app.core.config import settings
from app.services.graph_search_service import graph_search_service
from app.services.impact_analysis_service import impact_analysis_service

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
        return {"success": True, "data": await graph_search_service.search(query_req)}
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
        "data": await graph_search_service.vector_search(
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
        data = await graph_search_service.fk_path(
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
        return {"success": True, "data": await graph_search_service.tables_related(table_name, max_hops=max_hops)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/stats")
async def graph_stats():
    return {"success": True, "data": await graph_search_service.stats()}


@router.post("/query-cache")
async def reflect_query_cache(body: dict[str, Any], request: Request):
    """Oracle 품질 게이트 통과 쿼리 반영 (O4). question, sql, confidence, datasource_id 수신 후 Query 노드/캐시에 반영."""
    _ = request
    question = str(body.get("question") or "").strip()
    sql = str(body.get("sql") or "").strip()
    confidence = float(body.get("confidence") or 0.0)
    datasource_id = str(body.get("datasource_id") or "").strip()
    if not question or not sql:
        raise HTTPException(status_code=400, detail="question and sql are required")
    await graph_search_service.add_query_cache(question, sql, confidence, datasource_id)
    return {"success": True}


# -- O3: Ontology Context v2 -----------------------------------------------


class ContextRequest(BaseModel):
    case_id: str
    query: str


@router.post("/ontology/context")
async def ontology_context(body: ContextRequest, request: Request):
    """Neo4j fulltext 기반 ontology context. FEATURE_SEARCH_V2 flag로 제어."""
    if not settings.FEATURE_SEARCH_V2:
        return {"success": True, "data": None}
    await verify_case_access(body.case_id, request)
    result = await graph_search_service.context_v2(body.case_id, body.query)
    return {"success": True, "data": asdict(result)}


# -- O4: Impact Analysis -----------------------------------------------------


class ImpactAnalysisRequest(BaseModel):
    node_id: str
    case_id: str
    max_depth: int = Field(default=3, ge=1, le=5)


@router.post("/impact-analysis")
async def impact_analysis(body: ImpactAnalysisRequest, request: Request):
    """O4: Cross-domain impact analysis via multi-hop BFS."""
    await verify_case_access(body.case_id, request)
    try:
        result = await impact_analysis_service.impact_analysis(
            start_node_id=body.node_id,
            case_id=body.case_id,
            max_depth=body.max_depth,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Impact analysis failed: {exc}"
        ) from exc

    return {
        "success": True,
        "data": {
            "root": {
                "id": result.root_id,
                "label": result.root_label,
                "layer": result.root_layer,
            },
            "affected_nodes": [
                {
                    "id": n.id,
                    "label": n.label,
                    "labels": n.labels,
                    "layer": n.layer,
                    "depth": n.depth,
                    "path": [
                        {"node_id": s.node_id, "node_label": s.node_label, "rel_type": s.rel_type}
                        for s in n.path
                    ],
                }
                for n in result.affected_nodes
            ],
            "total_affected": result.total_affected,
            "max_depth_reached": result.max_depth_reached,
            "analysis_time_ms": result.analysis_time_ms,
        },
    }
