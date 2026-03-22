"""Object Explorer API 라우터 — FK 기반 드릴다운 + 텍스트 검색.

KAIR robo-data-domain-layer/ontology_explorer.py를 Axiom Weaver 패턴으로 이식.
온톨로지 ObjectType에 바인딩된 실제 데이터를 검색하고 FK 관계로 드릴다운한다.

엔드포인트:
  - POST /object-explorer/search — 전체 텍스트 검색 (다형성 컬럼 감지)
  - POST /object-explorer/children — FK 기반 자식 노드 드릴다운
  - GET  /object-explorer/relationships/{name} — 관계 메타데이터 조회
"""
from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import logging

from app.services.object_explorer_service import ObjectExplorerService

logger = logging.getLogger("axiom.weaver.object_explorer")

router = APIRouter(prefix="/api/v3/weaver/object-explorer", tags=["object-explorer"])

_explorer = ObjectExplorerService()


# ── 요청/응답 모델 ──

class ObjectSearchRequest(BaseModel):
    """전체 텍스트 검색 요청."""
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=100, ge=1, le=1000)
    datasource: str = ""


class ObjectSearchItem(BaseModel):
    """검색 결과 항목."""
    object_type: str
    id_value: str = ""
    name_value: str = ""
    properties: dict[str, Any] = Field(default_factory=dict)


class ChildNodesRequest(BaseModel):
    """FK 기반 자식 드릴다운 요청."""
    parent_type: str
    parent_id: str
    parent_properties: dict[str, Any] = Field(default_factory=dict)
    limit: int = Field(default=50, ge=1, le=500)


class ChildNodeItem(BaseModel):
    """자식 노드 항목."""
    object_type: str
    items: list[dict[str, Any]] = Field(default_factory=list)
    count: int = 0


# ── 엔드포인트 ──

@router.post("/search")
async def search_objects(body: ObjectSearchRequest) -> dict[str, Any]:
    """전체 텍스트 검색 — 모든 ObjectType의 데이터를 ILIKE로 검색한다.

    각 ObjectType의 바인딩된 테이블에서 텍스트 컬럼을 자동 감지하고,
    검색어에 매칭되는 행을 반환한다.

    컬럼 분류 휴리스틱:
    - ID 컬럼: id, code, no, key, 번호
    - 텍스트 컬럼: name, title, desc, label, nm, 명, 이름
    """
    try:
        results = await _explorer.search(
            query=body.query,
            limit=body.limit,
            datasource=body.datasource,
        )
        return {"success": True, "results": results, "query": body.query}
    except Exception as e:
        logger.error("object_search_error", exc_info=True)
        raise HTTPException(status_code=500, detail=f"검색 오류: {e}") from e


@router.post("/children")
async def get_children(body: ChildNodesRequest) -> dict[str, Any]:
    """FK 기반 자식 노드 드릴다운.

    부모 ObjectType의 FK 관계를 조회하여 자식 테이블에서
    부모 ID에 매칭되는 행을 반환한다.

    Match Strategy:
    - EXACT_MATCH: 정확 일치
    - CONTAINS: 포함
    - STARTS_WITH: 접두사
    - ENDS_WITH: 접미사
    """
    try:
        children = await _explorer.get_children(
            parent_type=body.parent_type,
            parent_id=body.parent_id,
            parent_properties=body.parent_properties,
            limit=body.limit,
        )
        return {"success": True, "children": children, "parent_type": body.parent_type}
    except Exception as e:
        logger.error("children_fetch_error", exc_info=True)
        raise HTTPException(status_code=500, detail=f"드릴다운 오류: {e}") from e


@router.get("/relationships/{object_type_name}")
async def get_relationships(object_type_name: str) -> dict[str, Any]:
    """ObjectType의 관계 메타데이터를 조회한다.

    outgoing (부모→자식) 및 incoming (자식→부모) FK 관계를 반환한다.
    """
    try:
        rels = await _explorer.get_relationships(object_type_name)
        return {"success": True, "object_type": object_type_name, **rels}
    except Exception as e:
        logger.error("relationships_fetch_error", exc_info=True)
        raise HTTPException(status_code=500, detail=f"관계 조회 오류: {e}") from e
