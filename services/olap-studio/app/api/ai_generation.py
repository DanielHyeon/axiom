"""AI 생성 API -- LLM 기반 큐브/DDL/샘플 데이터 생성."""
from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field

from app.core.context import get_request_context, require_capability
from app.core.database import execute_query
from app.core.rate_limiter import check_rate_limit, AI_GENERATION_LIMIT
from app.services.ai_cube_service import generate_cube_xml, generate_ddl
from app.services.llm_client import LLM_AVAILABLE

router = APIRouter(prefix="/ai", tags=["AI 생성"])


class AICubeGenerateRequest(BaseModel):
    prompt: str = Field(max_length=5000)  # 프롬프트 최대 길이 제한
    model_id: UUID | None = None


class AIDDLGenerateRequest(BaseModel):
    cube_id: UUID
    include_sample_data: bool = True
    sample_row_count: int = Field(default=100, ge=1, le=1000)  # 샘플 행 수 범위 제한


@router.post("/cubes/generate")
async def generate_cube(body: AICubeGenerateRequest, request: Request):
    """AI로 큐브 메타데이터(Mondrian XML) 생성.

    LLM이 사용자의 자연어 설명을 Mondrian XML로 변환한다.
    생성 결과는 ai_generations 테이블에 기록된다.
    """
    # 레이트 리밋 검사 -- AI 생성은 분당 10회 제한
    await check_rate_limit(request, AI_GENERATION_LIMIT)

    ctx = get_request_context(request)
    require_capability(ctx, "ai:use")

    # LLM으로 Mondrian XML 생성
    llm_result = await generate_cube_xml(body.prompt)

    # 생성 상태 결정 -- LLM 성공 시 COMPLETED, 실패 시 FAILED
    status = "COMPLETED" if llm_result["success"] else "FAILED"
    result_json = json.dumps({
        "xml": llm_result.get("xml", ""),
        "message": llm_result["message"],
    })

    # 생성 이력 기록
    rows = await execute_query(
        """INSERT INTO olap.ai_generations
        (tenant_id, project_id, generation_type, input_context, result, status, created_by)
        VALUES ($1, $2, 'CUBE', $3::jsonb, $4::jsonb, $5, $6)
        RETURNING id, generation_type, status, created_at""",
        [
            ctx.tenant_id,
            ctx.project_id,
            json.dumps({
                "prompt": body.prompt,
                "model_id": str(body.model_id) if body.model_id else None,
            }),
            result_json,
            status,
            ctx.user_id,
        ],
    )

    return {"success": True, "data": {
        "generation": rows[0] if rows else None,
        "xml": llm_result.get("xml", ""),
        "message": llm_result["message"],
        "llm_available": LLM_AVAILABLE,
    }}


@router.post("/ddl/generate")
async def generate_ddl_endpoint(body: AIDDLGenerateRequest, request: Request):
    """AI로 DDL + 샘플 데이터 SQL 생성.

    큐브 메타데이터를 기반으로 PostgreSQL DDL과 샘플 INSERT문을 생성한다.
    """
    # 레이트 리밋 검사 -- AI 생성은 분당 10회 제한
    await check_rate_limit(request, AI_GENERATION_LIMIT)

    ctx = get_request_context(request)
    require_capability(ctx, "ai:use")

    # 큐브 정보 조회 -- DDL 생성에 필요한 컨텍스트
    cube_rows = await execute_query(
        """SELECT name, xml_definition FROM olap.cubes
        WHERE id = $1 AND tenant_id = $2 AND project_id = $3""",
        [str(body.cube_id), ctx.tenant_id, ctx.project_id],
    )
    if not cube_rows:
        raise HTTPException(status_code=404, detail="큐브를 찾을 수 없습니다")

    cube = cube_rows[0]
    cube_description = (
        f"Cube name: {cube['name']}\n"
        f"XML definition:\n{cube.get('xml_definition', '(없음)')}"
    )

    # LLM으로 DDL 생성
    llm_result = await generate_ddl(
        cube_description,
        include_sample=body.include_sample_data,
        sample_rows=body.sample_row_count,
    )

    # 생성 상태 결정
    status = "COMPLETED" if llm_result["success"] else "FAILED"
    result_json = json.dumps({
        "sql": llm_result.get("sql", ""),
        "message": llm_result["message"],
    })

    # 생성 이력 기록
    rows = await execute_query(
        """INSERT INTO olap.ai_generations
        (tenant_id, project_id, generation_type, input_context, result, status, created_by)
        VALUES ($1, $2, 'DDL', $3::jsonb, $4::jsonb, $5, $6)
        RETURNING id, generation_type, status, created_at""",
        [
            ctx.tenant_id,
            ctx.project_id,
            json.dumps({
                "cube_id": str(body.cube_id),
                "include_sample": body.include_sample_data,
                "rows": body.sample_row_count,
            }),
            result_json,
            status,
            ctx.user_id,
        ],
    )

    return {"success": True, "data": {
        "generation": rows[0] if rows else None,
        "sql": llm_result.get("sql", ""),
        "message": llm_result["message"],
        "llm_available": LLM_AVAILABLE,
    }}


@router.get("/generations")
async def list_generations(request: Request):
    """AI 생성 이력 목록."""
    ctx = get_request_context(request)
    rows = await execute_query(
        """SELECT id, generation_type, status, approved_by, approved_at, created_at
        FROM olap.ai_generations
        WHERE tenant_id = $1 AND project_id = $2
        ORDER BY created_at DESC LIMIT 50""",
        [ctx.tenant_id, ctx.project_id],
    )
    return {"success": True, "data": rows}


@router.post("/generations/{gen_id}/approve")
async def approve_generation(gen_id: UUID, request: Request):
    """AI 생성 결과 승인."""
    ctx = get_request_context(request)
    require_capability(ctx, "cube:publish")
    from app.core.database import execute_command
    # 테넌트+프로젝트 범위 제한 -- 다른 테넌트의 생성 결과 변경 방지
    await execute_command(
        "UPDATE olap.ai_generations SET status = 'APPROVED', approved_by = $2, approved_at = now() WHERE id = $1 AND tenant_id = $3 AND project_id = $4",
        [str(gen_id), ctx.user_id, ctx.tenant_id, ctx.project_id],
    )
    return {"success": True}


@router.post("/generations/{gen_id}/reject")
async def reject_generation(gen_id: UUID, request: Request):
    """AI 생성 결과 반려."""
    ctx = get_request_context(request)
    require_capability(ctx, "cube:publish")
    from app.core.database import execute_command
    # 테넌트+프로젝트 범위 제한 -- 다른 테넌트의 생성 결과 변경 방지
    await execute_command(
        "UPDATE olap.ai_generations SET status = 'REJECTED', approved_by = $2, approved_at = now() WHERE id = $1 AND tenant_id = $3 AND project_id = $4",
        [str(gen_id), ctx.user_id, ctx.tenant_id, ctx.project_id],
    )
    return {"success": True}
