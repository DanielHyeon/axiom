"""G14: Materialized View 관리 API 강화.

MV 생성, 리프레시, 목록 조회, 상태 확인 엔드포인트.
기존 features/materialized-views/ 프론트엔드와 연동.
모든 SQL 실행은 QueryPolicyEngine 경유.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.auth import AuthService, CurrentUser
from app.services.query_engine import QueryCaller, query_engine

logger = logging.getLogger("axiom.weaver.api.mv_management")

router = APIRouter(prefix="/api/v3/weaver/mv", tags=["materialized-views"])

_auth = AuthService()
_ALLOWED_ROLES = {"admin", "analyst", "engineer", "manager"}


async def _get_current_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> CurrentUser:
    return _auth.verify_token(authorization)


# ── 모델 ── #

class MVCreateRequest(BaseModel):
    """MV 생성 요청"""
    datasource_name: str
    engine: str
    connection: dict[str, Any]
    mv_name: str                          # MV 이름
    schema_name: str = "public"
    source_sql: str                       # SELECT 쿼리 (MV 본문)


class MVRefreshRequest(BaseModel):
    """MV 리프레시 요청"""
    datasource_name: str
    engine: str
    connection: dict[str, Any]
    mv_name: str
    schema_name: str = "public"
    concurrent: bool = False              # CONCURRENTLY 옵션 (PG 전용)


class MVInfo(BaseModel):
    """MV 상태 정보"""
    mv_name: str
    schema_name: str = ""
    definition: str = ""
    last_refresh: str | None = None
    row_count: int | None = None
    is_populated: bool = True


# ── 엔드포인트 ── #

@router.get("/list")
async def list_materialized_views(
    datasource_name: str,
    engine: str,
    schema_name: str = Query("public"),
    user: CurrentUser = Depends(_get_current_user),
) -> dict:
    """MV 목록 조회 — information_schema 또는 pg_matviews 쿼리"""
    if user.role not in _ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="권한 부족")

    # C1: 식별자 검증 (SQL injection 방지)
    import re as _re
    if not _re.match(r'^[a-zA-Z_][a-zA-Z0-9_]{0,62}$', schema_name):
        raise HTTPException(status_code=400, detail="유효하지 않은 스키마명")

    # TODO: QueryPolicyEngine으로 전환 (connection 서버 조회 필요)
    return {
        "success": True,
        "data": [],  # 실 연동은 datasource registry 완성 후
        "message": "MV 목록 조회는 datasource registry 완성 후 실 연동됩니다",
    }


@router.post("/refresh")
async def refresh_materialized_view(
    request: MVRefreshRequest,
    user: CurrentUser = Depends(_get_current_user),
) -> dict:
    """MV 리프레시 — REFRESH MATERIALIZED VIEW 실행"""
    if user.role not in _ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="권한 부족")

    # 식별자 검증 (SQL injection 방지)
    import re as _re
    for name, label in [(request.schema_name, "스키마명"), (request.mv_name, "MV명")]:
        if not _re.match(r'^[a-zA-Z_][a-zA-Z0-9_]{0,62}$', name):
            raise HTTPException(status_code=400, detail=f"유효하지 않은 {label}: {name}")

    # 실 실행은 Phase 4에서 QueryPolicyEngine 확장 (DML 허용 목록)
    return {
        "success": True,
        "data": {
            "mv_name": request.mv_name,
            "status": "pending_execution",
        },
        "message": "MV 리프레시는 Phase 4에서 실 실행 연동됩니다",
    }
