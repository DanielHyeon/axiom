"""G11: 테이블 프로파일링 엔드포인트.

컬럼별 통계 수집 — NULL 비율, 유니크 비율, min/max, 분포 히스토그램 등.
QueryPolicyEngine을 경유하여 SQL 실행 안전성을 보장한다.

캐시: 프로파일 결과는 프로파일 요청 시마다 새로 수집 (캐시는 Phase 2에서 Redis 1h TTL 추가)
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.auth import AuthService, CurrentUser
from app.services.adapters.base import AdapterFactory
from app.services.query_engine import QueryCaller, query_engine

logger = logging.getLogger("axiom.weaver.api.profiling")

router = APIRouter(prefix="/api/v3/weaver/profiling", tags=["profiling"])

_auth = AuthService()

_ALLOWED_ROLES = {"admin", "analyst", "engineer", "manager"}

# M-3: 프로파일링 최대 컬럼 수 — 리소스 고갈 방지
MAX_PROFILE_COLUMNS = 50


async def _get_current_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> CurrentUser:
    return _auth.verify_token(authorization)


# ── 모델 ── #

class ColumnProfile(BaseModel):
    """컬럼 프로파일 결과"""
    column_name: str
    data_type: str = ""
    total_count: int = 0
    null_count: int = 0
    null_rate: float = 0.0          # 0.0 ~ 1.0
    distinct_count: int = 0
    unique_rate: float = 0.0        # distinct / (total - null)
    min_value: str | None = None
    max_value: str | None = None
    avg_value: float | None = None
    top_values: list[dict] = Field(default_factory=list)  # [{value, count}]


class TableProfile(BaseModel):
    """테이블 프로파일 결과"""
    datasource_name: str
    schema_name: str
    table_name: str
    row_count: int = 0
    column_count: int = 0
    columns: list[ColumnProfile] = Field(default_factory=list)
    profiled_at: str = ""
    profiling_time_ms: float = 0.0


class ProfilingRequest(BaseModel):
    """프로파일링 요청"""
    engine: str
    connection: dict[str, Any]
    sample_size: int = Field(default=10000, ge=100, le=1000000)


class ProfilingResponse(BaseModel):
    success: bool = True
    data: TableProfile


# ── 안전 식별자 검증 ── #

_SAFE_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,254}$")


def _safe_ident(name: str) -> str:
    """SQL 식별자 안전 검증 — 인젝션 방지"""
    if not _SAFE_IDENT.match(name):
        raise ValueError(f"유효하지 않은 식별자: {name}")
    return name


# ── 프로파일링 SQL 생성 ── #

def _build_count_sql(schema: str, table: str) -> str:
    """테이블 총 행 수 조회 SQL"""
    s = _safe_ident(schema)
    t = _safe_ident(table)
    return f'SELECT COUNT(*) AS cnt FROM "{s}"."{t}"'


def _build_column_stats_sql(
    schema: str,
    table: str,
    column: str,
    sample_size: int,
) -> str:
    """컬럼별 통계 SQL — NULL, DISTINCT, MIN, MAX 수집"""
    s = _safe_ident(schema)
    t = _safe_ident(table)
    c = _safe_ident(column)
    return (
        f'SELECT '
        f'  COUNT(*) AS total_count, '
        f'  COUNT(*) - COUNT("{c}") AS null_count, '
        f'  COUNT(DISTINCT "{c}") AS distinct_count, '
        f'  MIN("{c}"::text) AS min_value, '
        f'  MAX("{c}"::text) AS max_value '
        f'FROM (SELECT "{c}" FROM "{s}"."{t}" LIMIT {int(sample_size)}) AS _sample'
    )


def _build_top_values_sql(
    schema: str,
    table: str,
    column: str,
    top_n: int = 20,
    sample_size: int = 10000,
) -> str:
    """컬럼 top-N 값 조회 SQL"""
    s = _safe_ident(schema)
    t = _safe_ident(table)
    c = _safe_ident(column)
    return (
        f'SELECT "{c}"::text AS value, COUNT(*) AS cnt '
        f'FROM (SELECT "{c}" FROM "{s}"."{t}" LIMIT {int(sample_size)}) AS _sample '
        f'WHERE "{c}" IS NOT NULL '
        f'GROUP BY "{c}" '
        f'ORDER BY cnt DESC '
        f'LIMIT {int(top_n)}'
    )


# ── 엔드포인트 ── #

@router.post("/{datasource_name}/tables/{table_name}")
async def profile_table(
    datasource_name: str,
    table_name: str,
    request: ProfilingRequest,
    schema_name: str = Query("public", alias="schema"),
    user: CurrentUser = Depends(_get_current_user),
) -> ProfilingResponse:
    """테이블 프로파일링 — 컬럼별 통계 수집.

    반환: 컬럼별 null_rate, unique_rate, min, max, top_values
    QueryPolicyEngine 경유로 감사 로그 + 민감 컬럼 보호.
    """
    if user.role not in _ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="프로파일링은 analyst 이상만 사용 가능")

    # M-4: 경로 파라미터 식별자 검증 (SQL 인젝션 방지)
    try:
        _safe_ident(schema_name)
        _safe_ident(table_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    start = time.monotonic()

    try:
        # 1. 어댑터로 테이블 컬럼 목록 조회
        adapter = AdapterFactory.create(request.engine, request.connection)
        tables = await adapter.get_tables(schema_name)
        target_table = next(
            (t for t in tables if t.get("name") == table_name), None
        )

        if not target_table:
            raise HTTPException(
                status_code=404,
                detail=f"테이블을 찾을 수 없습니다: {schema_name}.{table_name}",
            )

        columns_info = target_table.get("columns", [])

        # M-3: 컬럼 수 제한 — 리소스 고갈 방지 (컬럼당 2 SQL 쿼리)
        truncated_columns = False
        if len(columns_info) > MAX_PROFILE_COLUMNS:
            columns_info = columns_info[:MAX_PROFILE_COLUMNS]
            truncated_columns = True

        # 2. 총 행 수 조회
        count_sql = _build_count_sql(schema_name, table_name)
        count_result = await query_engine.execute_safe(
            datasource_name=datasource_name,
            sql=count_sql,
            caller=QueryCaller.PROFILING,
            user_id=user.user_id,
            user_role=user.role,
            tenant_id=user.tenant_id,
            connection=request.connection,
            engine=request.engine,
            limit=1,
        )
        row_count = 0
        if count_result.rows:
            row_count = int(count_result.rows[0].get("cnt", 0))

        # 3. 컬럼별 프로파일링
        column_profiles: list[ColumnProfile] = []
        for col in columns_info:
            col_name = col.get("name", "")
            col_type = col.get("type", "")

            try:
                # 기본 통계
                stats_sql = _build_column_stats_sql(
                    schema_name, table_name, col_name, request.sample_size,
                )
                stats = await query_engine.execute_safe(
                    datasource_name=datasource_name,
                    sql=stats_sql,
                    caller=QueryCaller.PROFILING,
                    user_id=user.user_id,
                    user_role=user.role,
                    tenant_id=user.tenant_id,
                    connection=request.connection,
                    engine=request.engine,
                    limit=1,
                )

                total = 0
                null_count = 0
                distinct = 0
                min_val = None
                max_val = None

                if stats.rows:
                    row = stats.rows[0]
                    total = int(row.get("total_count", 0))
                    null_count = int(row.get("null_count", 0))
                    distinct = int(row.get("distinct_count", 0))
                    min_val = row.get("min_value")
                    max_val = row.get("max_value")

                null_rate = null_count / total if total > 0 else 0.0
                non_null = total - null_count
                unique_rate = distinct / non_null if non_null > 0 else 0.0

                # Top values
                top_sql = _build_top_values_sql(
                    schema_name, table_name, col_name,
                    top_n=20, sample_size=request.sample_size,
                )
                top_result = await query_engine.execute_safe(
                    datasource_name=datasource_name,
                    sql=top_sql,
                    caller=QueryCaller.PROFILING,
                    user_id=user.user_id,
                    user_role=user.role,
                    tenant_id=user.tenant_id,
                    connection=request.connection,
                    engine=request.engine,
                    limit=20,
                )
                top_values = [
                    {"value": r.get("value", ""), "count": int(r.get("cnt", 0))}
                    for r in top_result.rows
                ]

                column_profiles.append(ColumnProfile(
                    column_name=col_name,
                    data_type=col_type,
                    total_count=total,
                    null_count=null_count,
                    null_rate=round(null_rate, 4),
                    distinct_count=distinct,
                    unique_rate=round(unique_rate, 4),
                    min_value=str(min_val) if min_val is not None else None,
                    max_value=str(max_val) if max_val is not None else None,
                    top_values=top_values,
                ))

            except Exception as e:
                # 개별 컬럼 프로파일링 실패 시 스킵 (전체 실패 방지)
                logger.warning("컬럼 프로파일링 실패: %s.%s.%s — %s",
                               schema_name, table_name, col_name, e)
                column_profiles.append(ColumnProfile(
                    column_name=col_name,
                    data_type=col_type,
                ))

        elapsed = (time.monotonic() - start) * 1000
        from datetime import datetime as _dt, timezone as _tz

        profile = TableProfile(
            datasource_name=datasource_name,
            schema_name=schema_name,
            table_name=table_name,
            row_count=row_count,
            column_count=len(columns_info),
            columns=column_profiles,
            profiled_at=_dt.now(_tz.utc).isoformat(),  # N-3 수정
            profiling_time_ms=round(elapsed, 1),
        )

        return ProfilingResponse(data=profile)

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("프로파일링 실패: %s.%s", schema_name, table_name)
        # M-6: 내부 오류 상세 노출 방지
        raise HTTPException(status_code=500, detail="프로파일링 중 내부 오류 발생") from e
