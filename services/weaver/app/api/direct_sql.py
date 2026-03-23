"""G05: Direct SQL 실행 엔드포인트.

사용자가 임의 SELECT 쿼리를 실행할 수 있는 엔드포인트.
모든 실행은 QueryPolicyEngine.execute_safe()를 경유한다.

보안:
- SELECT만 허용 (DML/DDL 차단)
- 결과 1000행 제한 (기본 100)
- 쿼리 타임아웃 30초
- 민감 컬럼 자동 마스킹 (MinimumSecurityGuardrail)
- analyst 이상 역할만 사용 가능
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.auth import AuthService, CurrentUser
from app.services.query_engine import QueryCaller, QueryResult, query_engine

logger = logging.getLogger("axiom.weaver.api.direct_sql")

router = APIRouter(prefix="/api/v3/weaver", tags=["direct-sql"])

_auth = AuthService()

# analyst 이상 역할만 Direct SQL 사용 가능
_ALLOWED_ROLES = {"admin", "analyst", "engineer", "manager"}


async def _get_current_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> CurrentUser:
    """JWT 토큰에서 현재 사용자 추출"""
    return _auth.verify_token(authorization)


# ── 요청/응답 스키마 ── #

class DirectSqlRequest(BaseModel):
    """Direct SQL 실행 요청.

    TODO (C-2 Phase 2): connection/engine을 클라이언트가 직접 보내는 대신
    datasource_name + tenant_id로 서버 측 datasource_registry에서 조회해야 함.
    현재는 datasource registry 서버 측 통합이 미완성이므로 클라이언트 제공 방식 유지.
    Phase 2에서 Weaver datasource registry 완성 후 반드시 교체할 것.
    """
    datasource_name: str         # 데이터소스 식별자
    engine: str                  # 어댑터 엔진 타입 (postgresql, mysql 등)
    connection: dict[str, Any]   # 연결 정보 — TODO: 서버 측 조회로 교체
    sql: str                     # 실행할 SQL (SELECT만)
    limit: int = Field(default=100, ge=1, le=1000)  # 최대 반환 행 수
    timeout_seconds: int = Field(default=30, ge=1, le=120)


class DirectSqlResponse(BaseModel):
    """Direct SQL 실행 응답"""
    success: bool = True
    data: QueryResult
    audit_id: str = ""  # 감사 로그 ID (추적용)


# ── 엔드포인트 ── #

@router.post("/direct-sql")
async def execute_direct_sql(
    request: DirectSqlRequest,
    user: CurrentUser = Depends(_get_current_user),
) -> DirectSqlResponse:
    """임의 SELECT 쿼리 실행 (READ-ONLY 강제).

    QueryPolicyEngine 경유:
    1. SQL 파싱 → SELECT만 허용
    2. 민감 컬럼 자동 마스킹
    3. 감사 로그 기록
    4. row limit + timeout 적용
    """
    # 역할 검증
    if user.role not in _ALLOWED_ROLES:
        raise HTTPException(
            status_code=403,
            detail=f"Direct SQL은 analyst 이상 역할만 사용 가능합니다 (현재: {user.role})",
        )

    try:
        result = await query_engine.execute_safe(
            datasource_name=request.datasource_name,
            sql=request.sql,
            caller=QueryCaller.DIRECT_SQL,
            user_id=user.user_id,
            user_role=user.role,
            tenant_id=user.tenant_id,
            connection=request.connection,
            engine=request.engine,
            limit=request.limit,
            timeout_seconds=request.timeout_seconds,
        )
        return DirectSqlResponse(data=result)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except Exception as e:
        logger.exception("Direct SQL 실행 실패: %s", e)
        # M-6: 내부 오류 상세 노출 방지
        raise HTTPException(status_code=500, detail="쿼리 실행 중 내부 오류 발생") from e


@router.get("/query-audit")
async def list_query_audit(
    user: CurrentUser = Depends(_get_current_user),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    """쿼리 감사 로그 조회 (테넌트 격리)"""
    if user.role not in {"admin", "manager"}:
        raise HTTPException(status_code=403, detail="감사 로그는 admin/manager만 조회 가능합니다")

    logs = query_engine.get_audit_logs(user.tenant_id, limit)
    return {
        "success": True,
        "data": [log.model_dump(mode="json") for log in logs],
        "total": len(logs),
    }
