"""탐색형 NL2SQL API -- 큐브 컨텍스트 기반 자연어 질의."""
from __future__ import annotations

import json
import time

from fastapi import APIRouter, Request, HTTPException

from app.core.context import get_request_context, require_capability
from app.core.database import execute_query, execute_command
from app.core.rate_limiter import check_rate_limit, NL2SQL_LIMIT
from app.models.query import NaturalQuery, QueryResult
from app.services.nl2sql_workflow import run_nl2sql, generate_sql_only
from app.services.llm_client import LLM_AVAILABLE

router = APIRouter(prefix="/nl2sql", tags=["NL2SQL"])


async def _load_cube_schema(cube_name: str, tenant_id: str, project_id: str) -> str:
    """큐브 이름으로 스키마 설명을 로드한다.

    큐브의 XML 정의에서 테이블/컬럼 구조를 추출하여
    LLM에 전달할 컨텍스트를 구성한다.
    """
    rows = await execute_query(
        """SELECT name, xml_definition, description
        FROM olap.cubes
        WHERE name = $1 AND tenant_id = $2 AND project_id = $3""",
        [cube_name, tenant_id, project_id],
    )
    if not rows:
        return ""

    cube = rows[0]
    parts = [f"Cube: {cube['name']}"]
    if cube.get("description"):
        parts.append(f"Description: {cube['description']}")
    if cube.get("xml_definition"):
        parts.append(f"Mondrian XML:\n{cube['xml_definition']}")
    return "\n".join(parts)


@router.post("/execute")
async def execute_nl2sql(body: NaturalQuery, request: Request):
    """자연어 질의 실행 -- LLM으로 SQL 생성 -> 검증 -> 실행.

    4단계 파이프라인:
      1. 큐브 스키마 로드
      2. LLM SQL 생성
      3. 안전성 검증 (SELECT만 허용, 금지 키워드 차단)
      4. asyncpg 실행
    """
    # 레이트 리밋 검사 -- NL2SQL은 분당 20회 제한
    await check_rate_limit(request, NL2SQL_LIMIT)

    ctx = get_request_context(request)
    require_capability(ctx, "nl2sql:use")

    # 큐브 스키마 로드 -- LLM에 컨텍스트 제공
    schema_desc = await _load_cube_schema(
        body.cube_name, ctx.tenant_id, ctx.project_id
    )

    # NL2SQL 파이프라인 실행
    result = await run_nl2sql(
        question=body.question,
        cube_name=body.cube_name,
        schema_description=schema_desc,
        max_rows=body.max_rows,
    )

    # 질의 이력 기록 -- 성공/실패 모두 저장
    status = "COMPLETED" if result["error"] is None else "FAILED"
    try:
        await execute_command(
            """INSERT INTO olap.query_history
            (tenant_id, project_id, query_type, input_text, generated_sql,
             execution_ms, result_row_count, status, error_message, created_by)
            VALUES ($1, $2, 'NL2SQL', $3, $4, $5, $6, $7, $8, $9)""",
            [
                ctx.tenant_id,
                ctx.project_id,
                body.question,
                result["sql"],
                result["execution_time_ms"],
                result["row_count"],
                status,
                result.get("error"),
                ctx.user_id,
            ],
        )
    except Exception:
        # 이력 저장 실패는 메인 응답에 영향을 주지 않는다
        pass

    return {"success": result["error"] is None, "data": result}


@router.post("/preview")
async def preview_nl2sql(body: NaturalQuery, request: Request):
    """SQL 미리보기 -- 실행하지 않고 SQL만 생성.

    사용자가 실행 전에 생성된 SQL을 확인할 수 있도록 한다.
    """
    # 레이트 리밋 검사 -- NL2SQL은 분당 20회 제한
    await check_rate_limit(request, NL2SQL_LIMIT)

    ctx = get_request_context(request)
    require_capability(ctx, "nl2sql:use")  # 미리보기도 NL2SQL 사용 권한 필요

    # 큐브 스키마 로드
    schema_desc = await _load_cube_schema(
        body.cube_name, ctx.tenant_id, ctx.project_id
    )

    # SQL만 생성 (실행 안 함)
    preview = await generate_sql_only(
        question=body.question,
        cube_name=body.cube_name,
        schema_description=schema_desc,
        max_rows=body.max_rows,
    )

    return {"success": preview["error"] is None, "data": {
        "sql": preview["sql"],
        "error": preview.get("error"),
        "llm_available": LLM_AVAILABLE,
    }}


@router.get("/history")
async def get_history(request: Request):
    """NL2SQL 질의 이력 조회."""
    ctx = get_request_context(request)
    rows = await execute_query(
        """SELECT id, input_text, generated_sql, execution_ms, result_row_count, status, error_message, created_at
        FROM olap.query_history
        WHERE tenant_id = $1 AND project_id = $2 AND query_type = 'NL2SQL'
        ORDER BY created_at DESC LIMIT 50""",
        [ctx.tenant_id, ctx.project_id],
    )
    return {"success": True, "data": rows}
