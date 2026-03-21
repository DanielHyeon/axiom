"""피벗 API — OLAP 피벗 질의 실행 + 저장된 뷰 관리."""
from __future__ import annotations

import time
from uuid import UUID

import structlog
from fastapi import APIRouter, Request, HTTPException

from app.core.context import get_request_context, require_capability
from app.core.database import execute_query, execute_command
from app.core.rate_limiter import check_rate_limit, PIVOT_LIMIT
from app.models.query import PivotQuery, QueryResult
from app.services.sql_generator import generate_pivot_sql

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/pivot", tags=["피벗"])


@router.post("/execute")
async def execute_pivot(body: PivotQuery, request: Request):
    """피벗 질의 실행 — SQL 생성 → 실행 → 결과 반환."""
    # 레이트 리밋 검사 -- 피벗은 분당 60회 제한
    await check_rate_limit(request, PIVOT_LIMIT)

    ctx = get_request_context(request)
    require_capability(ctx, "pivot:read")

    # SQL 생성 -- 연산자 검증 실패 시 400 반환
    try:
        sql, params = generate_pivot_sql(body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not sql:
        raise HTTPException(status_code=400, detail="SQL 생성 실패 — 큐브 메타데이터를 확인하세요")

    # 실행 — 파라미터 바인딩으로 SQL 인젝션 방지
    start = time.monotonic()
    try:
        rows = await execute_query(sql, params)
        elapsed_ms = int((time.monotonic() - start) * 1000)
    except Exception as e:
        logger.error("pivot_query_execution_failed", error=str(e), cube=body.cube_name)
        raise HTTPException(status_code=500, detail="쿼리 실행 중 오류가 발생했습니다")

    columns = list(rows[0].keys()) if rows else []
    result = QueryResult(
        sql=sql,
        columns=columns,
        rows=[list(r.values()) for r in rows],
        row_count=len(rows),
        execution_time_ms=elapsed_ms,
    )

    # 이력 저장
    await execute_command(
        """INSERT INTO olap.query_history (tenant_id, project_id, query_type, cube_id, generated_sql, execution_ms, result_row_count, status, executed_by)
        VALUES ($1, $2, 'PIVOT', NULL, $3, $4, $5, 'SUCCESS', $6)""",
        [ctx.tenant_id, ctx.project_id, sql, elapsed_ms, len(rows), ctx.user_id],
    )

    return {"success": True, "data": result.model_dump()}


@router.post("/preview-sql")
async def preview_pivot_sql(body: PivotQuery, request: Request):
    """피벗 SQL 미리보기 — 실행하지 않고 SQL만 반환."""
    ctx = get_request_context(request)
    try:
        sql, _params = generate_pivot_sql(body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"success": True, "data": {"sql": sql}}
