"""Instance Fetcher API 라우터 — 온톨로지 노드 바인딩 데이터 프리뷰.

KAIR robo-data-domain-layer/ontology_instances.py를 Axiom Weaver 패턴으로 이식.
온톨로지 노드에 바인딩된 실제 테이블 데이터를 프리뷰한다.

엔드포인트:
  - GET  /nodes/{node_id}/sample-data — 샘플 데이터 + 건수 조회
  - GET  /nodes/{node_id}/instances — 인스턴스 프리뷰 + 컬럼 타입 정보
"""
from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

import logging

from app.services.instance_fetcher_service import InstanceFetcherService

logger = logging.getLogger("axiom.weaver.instance_fetcher")

router = APIRouter(prefix="/api/v3/weaver/nodes", tags=["instance-fetcher"])

_fetcher = InstanceFetcherService()

# SQL Identifier 검증 — injection 방지
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]{0,62}$")


# ── 응답 모델 ──

class SampleDataResponse(BaseModel):
    """샘플 데이터 응답."""
    success: bool = True
    node_id: str
    total_count: int = 0
    columns: list[str] = Field(default_factory=list)
    column_types: dict[str, str] = Field(default_factory=dict)
    preview: list[dict[str, Any]] = Field(default_factory=list)
    table_name: str = ""
    schema_name: str = ""


# ── 엔드포인트 ──

@router.get("/{node_id}/sample-data")
async def get_sample_data(
    node_id: str,
    limit: int = Query(default=50, ge=1, le=1000),
    schema: str = Query(default="", description="바인딩 스키마 (빈값이면 자동 감지)"),
    table: str = Query(default="", description="바인딩 테이블 (빈값이면 노드에서 추론)"),
) -> SampleDataResponse:
    """온톨로지 노드에 바인딩된 테이블의 샘플 데이터를 조회한다.

    노드의 dataSourceSchema 속성에서 스키마/테이블 정보를 추출하거나,
    query parameter로 직접 지정할 수 있다.

    응답:
    - total_count: 전체 행 수
    - columns: 컬럼명 리스트
    - column_types: 컬럼별 타입 (text, number, date 등)
    - preview: 샘플 행 리스트 (dict)
    """
    # 테이블명 직접 지정 시 검증
    if table and not _SAFE_IDENTIFIER.match(table):
        raise HTTPException(status_code=400, detail="유효하지 않은 테이블명입니다.")
    if schema and not _SAFE_IDENTIFIER.match(schema):
        raise HTTPException(status_code=400, detail="유효하지 않은 스키마명입니다.")

    try:
        result = await _fetcher.fetch_sample_data(
            node_id=node_id,
            limit=limit,
            schema_name=schema,
            table_name=table,
        )
        return SampleDataResponse(
            node_id=node_id,
            **result,
        )
    except Exception as e:
        logger.error("sample_data_error", node_id=node_id, exc_info=True)
        raise HTTPException(status_code=500, detail=f"데이터 프리뷰 오류: {e}") from e


@router.get("/{node_id}/instances")
async def get_instances(
    node_id: str,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """온톨로지 노드의 인스턴스 데이터를 페이지네이션으로 조회한다.

    sample-data와 동일한 데이터를 반환하되, offset/limit 페이지네이션을 지원한다.
    """
    try:
        result = await _fetcher.fetch_instances(
            node_id=node_id,
            limit=limit,
            offset=offset,
        )
        return {"success": True, "node_id": node_id, **result}
    except Exception as e:
        logger.error("instances_fetch_error", node_id=node_id, exc_info=True)
        raise HTTPException(status_code=500, detail=f"인스턴스 조회 오류: {e}") from e
