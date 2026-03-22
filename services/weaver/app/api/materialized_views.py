"""Materialized View 관리 API 엔드포인트.

PostgreSQL Materialized View의 생성, 목록 조회, 새로고침, 삭제를 위한 REST API.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.auth import CurrentUser, auth_service
from app.services.materialized_view_service import MaterializedViewError, mv_service
from app.services.mindsdb_client import MindsDBUnavailableError

logger = logging.getLogger("axiom.weaver.mv.api")

router = APIRouter(
    prefix="/api/v3/weaver/materialized-views",
    tags=["MaterializedView"],
)


# ── 인증 헬퍼 ── #

async def _get_user(authorization: str | None = Header(default=None, alias="Authorization")) -> CurrentUser:
    """JWT 토큰에서 현재 사용자를 추출한다."""
    return auth_service.verify_token(authorization)


def _ensure_writer(user: CurrentUser) -> None:
    """데이터소스 쓰기 권한을 확인한다."""
    auth_service.requires_permission(user, "datasource:write")


def _ensure_reader(user: CurrentUser) -> None:
    """데이터소스 읽기 권한을 확인한다."""
    auth_service.requires_permission(user, "datasource:read")


# ── 요청/응답 모델 ── #

class CreateMVRequest(BaseModel):
    """Materialized View 생성 요청."""
    name: str = Field(..., min_length=1, max_length=63, description="MV 이름")
    source_table: str = Field(
        default="",
        max_length=63,
        description="원본 테이블 이름 (select_query 미지정 시 필수)",
    )
    schema_name: str = Field(default="public", max_length=63, description="스키마 이름")
    select_query: str | None = Field(
        default=None,
        max_length=10000,
        description="커스텀 SELECT 쿼리 (지정 시 source_table 대신 사용)",
    )
    database: str | None = Field(default=None, description="MindsDB 데이터베이스 이름")


class RefreshMVRequest(BaseModel):
    """Materialized View 새로고침 요청."""
    concurrently: bool = Field(default=False, description="CONCURRENTLY 옵션 (유니크 인덱스 필요)")
    database: str | None = Field(default=None, description="MindsDB 데이터베이스 이름")


class MVResponse(BaseModel):
    """Materialized View 작업 응답."""
    status: str = Field(..., description="작업 결과 상태")
    name: str = Field(..., description="MV 이름")
    schema_name: str = Field(default="public", alias="schema", description="스키마 이름")

    model_config = {"populate_by_name": True}


class MVListItem(BaseModel):
    """Materialized View 목록 항목."""
    schemaname: str | None = Field(default=None, description="스키마 이름")
    matviewname: str | None = Field(default=None, description="MV 이름")
    matviewowner: str | None = Field(default=None, description="소유자")
    ispopulated: bool | None = Field(default=None, description="데이터 적재 여부")
    definition: str | None = Field(default=None, description="뷰 정의 쿼리")


class MVListResponse(BaseModel):
    """Materialized View 목록 응답."""
    items: list[dict[str, Any]] = Field(default_factory=list, description="MV 목록")
    count: int = Field(default=0, description="총 개수")


# ── 엔드포인트 ── #

@router.post(
    "/",
    response_model=MVResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Materialized View 생성",
)
async def create_materialized_view(
    body: CreateMVRequest,
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    """새로운 Materialized View를 생성한다.

    source_table 또는 select_query 중 하나를 반드시 지정해야 한다.
    """
    user = await _get_user(authorization)
    _ensure_writer(user)

    # source_table과 select_query 둘 다 없으면 에러
    if not body.select_query and not body.source_table:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="source_table 또는 select_query 중 하나를 지정해야 합니다",
        )

    try:
        result = await mv_service.create_mv(
            name=body.name,
            source_table=body.source_table,
            schema_name=body.schema_name,
            select_query=body.select_query,
            database=body.database,
        )
        return result
    except MaterializedViewError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except MindsDBUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"데이터소스 연결 실패: {exc}",
        )


@router.get(
    "/",
    response_model=MVListResponse,
    summary="Materialized View 목록 조회",
)
async def list_materialized_views(
    schema_name: str = Query(default="public", max_length=63, description="스키마 이름"),
    database: str | None = Query(default=None, description="MindsDB 데이터베이스 이름"),
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    """지정된 스키마의 모든 Materialized View 목록을 조회한다."""
    user = await _get_user(authorization)
    _ensure_reader(user)

    try:
        items = await mv_service.list_mvs(schema_name=schema_name, database=database)
        return {"items": items, "count": len(items)}
    except MaterializedViewError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except MindsDBUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"데이터소스 연결 실패: {exc}",
        )


@router.post(
    "/{name}/refresh",
    response_model=MVResponse,
    summary="Materialized View 새로고침",
)
async def refresh_materialized_view(
    name: str,
    body: RefreshMVRequest | None = None,
    schema_name: str = Query(default="public", max_length=63, description="스키마 이름"),
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    """Materialized View의 데이터를 새로고침(갱신)한다."""
    user = await _get_user(authorization)
    _ensure_writer(user)

    req = body or RefreshMVRequest()

    try:
        result = await mv_service.refresh_mv(
            name=name,
            schema_name=schema_name,
            concurrently=req.concurrently,
            database=req.database,
        )
        return result
    except MaterializedViewError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except MindsDBUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"데이터소스 연결 실패: {exc}",
        )


@router.delete(
    "/{name}",
    response_model=MVResponse,
    summary="Materialized View 삭제",
)
async def drop_materialized_view(
    name: str,
    schema_name: str = Query(default="public", max_length=63, description="스키마 이름"),
    database: str | None = Query(default=None, description="MindsDB 데이터베이스 이름"),
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    """Materialized View를 삭제한다."""
    user = await _get_user(authorization)
    _ensure_writer(user)

    try:
        result = await mv_service.drop_mv(
            name=name,
            schema_name=schema_name,
            database=database,
        )
        return result
    except MaterializedViewError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except MindsDBUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"데이터소스 연결 실패: {exc}",
        )
