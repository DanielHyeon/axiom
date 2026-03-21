"""스키마 네비게이션 API — 통합 related-tables + availability

robo 모드와 text2sql 모드의 스키마 캔버스를 하나의 API로 통합한다.
:Table 노드의 datasource_name 프로퍼티 유무로 모드를 구분한다:
  - ROBO: datasource_name 없음 (코드 분석 결과)
  - TEXT2SQL: datasource_name 있음 (DB 메타데이터)
"""

from fastapi import APIRouter, HTTPException, Query, Request

import structlog

from app.services.related_tables_service import (
    RelatedTableRequest,
    fetch_related_tables_unified,
    fetch_schema_availability,
)

logger = structlog.get_logger()

router = APIRouter(
    prefix="/api/v3/synapse/schema-nav",
    tags=["Schema Navigation"],
)


def _require_tenant(request: Request) -> str:
    """테넌트 ID가 없으면 401 에러를 발생시킨다."""
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=401, detail="tenant not resolved")
    return tenant_id


# ──── 스키마 가용성 조회 ──── #

@router.get("/availability")
async def get_availability(
    request: Request,
    datasource_name: str | None = Query(None, alias="datasourceName"),
):
    """데이터소스별 스키마 가용성(테이블·컬럼 수 등)을 반환한다."""
    tenant_id = _require_tenant(request)
    try:
        result = await fetch_schema_availability(datasource_name, tenant_id=tenant_id)
        return {"success": True, "data": result.model_dump(by_alias=True)}
    except Exception as exc:
        logger.error(
            "schema_availability_error",
            datasource_name=datasource_name,
            error=str(exc),
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Internal server error") from exc


# ──── 관련 테이블 탐색 ──── #

@router.post("/related-tables")
async def post_related_tables(request_body: RelatedTableRequest, request: Request):
    """선택된 테이블의 관련 테이블(FK, 시맨틱 유사도 등)을 통합 조회한다."""
    tenant_id = _require_tenant(request)
    try:
        logger.info(
            "related_tables_request",
            mode=request_body.mode,
            table_name=request_body.table_name,
            schema_name=request_body.schema_name,
            datasource_name=request_body.datasource_name,
            depth=request_body.depth,
        )
        result = await fetch_related_tables_unified(request_body, tenant_id=tenant_id)
        return {"success": True, "data": result.model_dump(by_alias=True)}
    except Exception as exc:
        logger.error(
            "related_tables_error",
            table_name=getattr(request_body, "table_name", None),
            error=str(exc),
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Internal server error") from exc
