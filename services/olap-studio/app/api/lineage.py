"""리니지 API — 데이터 흐름 추적."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request, HTTPException

from app.core.context import get_request_context
from app.core.database import execute_query

router = APIRouter(prefix="/lineage", tags=["리니지"])


@router.get("/entities")
async def list_entities(request: Request, entity_type: str | None = None):
    """리니지 엔티티 목록 조회."""
    ctx = get_request_context(request)
    if entity_type:
        rows = await execute_query(
            """SELECT id, entity_type, entity_key, display_name, metadata
            FROM olap.lineage_entities
            WHERE tenant_id = $1 AND project_id = $2 AND entity_type = $3
            ORDER BY display_name""",
            [ctx.tenant_id, ctx.project_id, entity_type],
        )
    else:
        rows = await execute_query(
            """SELECT id, entity_type, entity_key, display_name
            FROM olap.lineage_entities
            WHERE tenant_id = $1 AND project_id = $2
            ORDER BY entity_type, display_name""",
            [ctx.tenant_id, ctx.project_id],
        )
    return {"success": True, "data": rows}


@router.get("/entities/{entity_id}")
async def get_entity(entity_id: UUID, request: Request):
    """엔티티 상세 조회."""
    ctx = get_request_context(request)
    rows = await execute_query(
        "SELECT * FROM olap.lineage_entities WHERE id = $1 AND tenant_id = $2 AND project_id = $3",
        [str(entity_id), ctx.tenant_id, ctx.project_id],
    )
    if not rows:
        raise HTTPException(status_code=404, detail="엔티티를 찾을 수 없습니다")
    return {"success": True, "data": rows[0]}


@router.get("/graph")
async def get_lineage_graph(request: Request):
    """전체 리니지 그래프 (엔티티 + 엣지) 조회."""
    ctx = get_request_context(request)
    entities = await execute_query(
        """SELECT id, entity_type, entity_key, display_name
        FROM olap.lineage_entities WHERE tenant_id = $1 AND project_id = $2""",
        [ctx.tenant_id, ctx.project_id],
    )
    edges = await execute_query(
        """SELECT e.id, e.from_entity_id, e.to_entity_id, e.edge_type, e.relation
        FROM olap.lineage_edges e
        JOIN olap.lineage_entities le ON le.id = e.from_entity_id
        WHERE le.tenant_id = $1 AND le.project_id = $2""",
        [ctx.tenant_id, ctx.project_id],
    )
    return {"success": True, "data": {"entities": entities, "edges": edges}}


@router.get("/impact/{entity_id}")
async def get_impact(entity_id: UUID, request: Request):
    """엔티티 영향 분석 — upstream/downstream 목록."""
    ctx = get_request_context(request)

    # 대상 엔티티 소유권 확인 — 테넌트 격리
    owner_check = await execute_query(
        "SELECT id FROM olap.lineage_entities WHERE id = $1 AND tenant_id = $2 AND project_id = $3",
        [str(entity_id), ctx.tenant_id, ctx.project_id],
    )
    if not owner_check:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="엔티티를 찾을 수 없습니다")

    # downstream (이 엔티티에서 나가는 방향) — 같은 테넌트 엔티티만 조회
    downstream = await execute_query(
        """SELECT le.id, le.entity_type, le.display_name, e.edge_type
        FROM olap.lineage_edges e JOIN olap.lineage_entities le ON le.id = e.to_entity_id
        WHERE e.from_entity_id = $1 AND le.tenant_id = $2 AND le.project_id = $3""",
        [str(entity_id), ctx.tenant_id, ctx.project_id],
    )
    # upstream (이 엔티티로 들어오는 방향) — 같은 테넌트 엔티티만 조회
    upstream = await execute_query(
        """SELECT le.id, le.entity_type, le.display_name, e.edge_type
        FROM olap.lineage_edges e JOIN olap.lineage_entities le ON le.id = e.from_entity_id
        WHERE e.to_entity_id = $1 AND le.tenant_id = $2 AND le.project_id = $3""",
        [str(entity_id), ctx.tenant_id, ctx.project_id],
    )
    return {"success": True, "data": {"upstream": upstream, "downstream": downstream}}
