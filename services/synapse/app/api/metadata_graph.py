"""Metadata Graph API — Weaver 전용 그래프 접근 (DDD-P2-05).

Weaver가 Neo4j에 직접 접속하지 않고 이 API를 통해 메타데이터 그래프에 접근한다.
Synapse가 Neo4j Primary Owner로서 모든 그래프 접근을 중개한다.
"""
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.services.metadata_graph_service import metadata_graph_service

router = APIRouter(prefix="/api/v1/metadata/graph", tags=["Metadata Graph"])


def _tenant(request: Request) -> str:
    return getattr(request.state, "tenant_id", "") or ""


# ──── Snapshot ──── #

@router.post("/snapshots")
async def save_snapshot(body: dict[str, Any], request: Request):
    try:
        await metadata_graph_service.save_snapshot(body, _tenant(request))
        return {"success": True}
    except Exception as exc:
        raise HTTPException(500, detail=str(exc)) from exc


@router.get("/snapshots")
async def list_snapshots(case_id: str, datasource: str, request: Request):
    items = await metadata_graph_service.list_snapshots(case_id, datasource, _tenant(request))
    return {"success": True, "data": items}


@router.get("/snapshots/{snapshot_id}")
async def get_snapshot(snapshot_id: str, case_id: str, datasource: str, request: Request):
    item = await metadata_graph_service.get_snapshot(case_id, datasource, snapshot_id, _tenant(request))
    if item is None:
        raise HTTPException(404, detail="snapshot not found")
    return {"success": True, "data": item}


@router.delete("/snapshots/{snapshot_id}")
async def delete_snapshot(snapshot_id: str, case_id: str, datasource: str, request: Request):
    deleted = await metadata_graph_service.delete_snapshot(case_id, datasource, snapshot_id, _tenant(request))
    return {"success": True, "deleted": deleted}


# ──── Glossary ──── #

@router.post("/glossary")
async def save_glossary_term(body: dict[str, Any], request: Request):
    await metadata_graph_service.save_glossary_term(body, _tenant(request))
    return {"success": True}


@router.get("/glossary")
async def list_glossary_terms(request: Request, q: str | None = None):
    tid = _tenant(request)
    if q:
        items = await metadata_graph_service.search_glossary_terms(q, tid)
    else:
        items = await metadata_graph_service.list_glossary_terms(tid)
    return {"success": True, "data": items}


@router.get("/glossary/{term_id}")
async def get_glossary_term(term_id: str, request: Request):
    item = await metadata_graph_service.get_glossary_term(term_id, _tenant(request))
    if item is None:
        raise HTTPException(404, detail="glossary term not found")
    return {"success": True, "data": item}


@router.delete("/glossary/{term_id}")
async def delete_glossary_term(term_id: str, request: Request):
    deleted = await metadata_graph_service.delete_glossary_term(term_id, _tenant(request))
    return {"success": True, "deleted": deleted}


# ──── Entity Tags ──── #

@router.post("/tags")
async def add_entity_tag(body: dict[str, Any], request: Request):
    tags = await metadata_graph_service.add_entity_tag(
        entity_key=body["entity_key"], entity_type=body["entity_type"],
        metadata=body.get("metadata", {}), tag=body["tag"],
    )
    return {"success": True, "tags": tags}


@router.get("/tags")
async def list_entity_tags(entity_key: str):
    tags = await metadata_graph_service.list_entity_tags(entity_key)
    return {"success": True, "tags": tags}


@router.delete("/tags")
async def remove_entity_tag(entity_key: str, tag: str):
    removed = await metadata_graph_service.remove_entity_tag(entity_key, tag)
    return {"success": True, "removed": removed}


@router.get("/tags/entities")
async def entities_by_tag(tag: str, request: Request):
    entities = await metadata_graph_service.entities_by_tag(tag, _tenant(request))
    return {"success": True, "data": entities}


# ──── Datasource ──── #

@router.post("/datasources/upsert")
async def upsert_datasource(body: dict[str, Any], request: Request):
    await metadata_graph_service.upsert_datasource(body["name"], body["engine"], _tenant(request))
    return {"success": True}


@router.delete("/datasources/{name}")
async def delete_datasource(name: str, request: Request):
    await metadata_graph_service.delete_datasource(name, _tenant(request))
    return {"success": True}


@router.post("/datasources/catalog")
async def save_extracted_catalog(body: dict[str, Any], request: Request):
    result = await metadata_graph_service.save_extracted_catalog(
        tenant_id=_tenant(request), datasource_name=body["datasource_name"],
        catalog=body["catalog"], engine=body.get("engine", "postgresql"),
        foreign_keys=body.get("foreign_keys"),
    )
    return {"success": True, "data": result}


# ──── Stats ──── #

@router.get("/stats")
async def metadata_stats(request: Request):
    stats = await metadata_graph_service.stats(_tenant(request))
    return {"success": True, "data": stats}
