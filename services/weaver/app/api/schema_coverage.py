"""G24: 스키마 가용성 검사 API.

Weaver 인트로스펙션 결과 vs 실제 DB 스키마를 비교하여
커버리지(발견율)를 산출한다. 데이터소스 상세 페이지의 Coverage 섹션에 표시.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import AuthService, CurrentUser
from app.services.adapters.base import AdapterFactory

logger = logging.getLogger("axiom.weaver.api.schema_coverage")

router = APIRouter(prefix="/api/v3/weaver/schema-coverage", tags=["schema-coverage"])

_auth = AuthService()


async def _get_current_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> CurrentUser:
    return _auth.verify_token(authorization)


# ── 모델 ── #

class CoverageRequest(BaseModel):
    """스키마 커버리지 검사 요청"""
    datasource_name: str
    engine: str
    connection: dict[str, Any]
    schema_name: str = "public"
    known_tables: list[str] = Field(default_factory=list)  # Weaver에 이미 등록된 테이블명


class CoverageResult(BaseModel):
    """스키마 커버리지 검사 결과"""
    total_db_tables: int = 0              # 실제 DB 테이블 수
    known_tables: int = 0                 # Weaver에 등록된 테이블 수
    coverage_rate: float = 0.0            # 0.0 ~ 1.0
    missing_tables: list[str] = Field(default_factory=list)  # DB에 있지만 Weaver에 없는 테이블
    extra_tables: list[str] = Field(default_factory=list)    # Weaver에 있지만 DB에 없는 테이블 (삭제됨)


# ── 엔드포인트 ── #

@router.post("/check")
async def check_schema_coverage(
    request: CoverageRequest,
    user: CurrentUser = Depends(_get_current_user),
) -> dict:
    """인트로스펙션 결과 vs 실제 DB 스키마 커버리지 비교"""
    try:
        adapter = AdapterFactory.create(request.engine, request.connection)
        tables = await adapter.get_tables(request.schema_name)
        db_table_names = {t.get("name", "") for t in tables}

        known_set = set(request.known_tables)

        missing = sorted(db_table_names - known_set)
        extra = sorted(known_set - db_table_names)

        total = len(db_table_names)
        covered = len(known_set & db_table_names)
        rate = covered / total if total > 0 else 1.0

        result = CoverageResult(
            total_db_tables=total,
            known_tables=len(known_set),
            coverage_rate=round(rate, 4),
            missing_tables=missing[:100],  # 최대 100개
            extra_tables=extra[:100],
        )

        return {"success": True, "data": result.model_dump()}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("스키마 커버리지 검사 실패: %s", e)
        raise HTTPException(status_code=500, detail="스키마 커버리지 검사 중 내부 오류 발생") from e
