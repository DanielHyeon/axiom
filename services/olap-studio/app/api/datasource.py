"""데이터소스 API — OLAP용 원천 DB 연결 관리."""
from __future__ import annotations

import json
from uuid import UUID

import structlog
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field

from app.core.context import get_request_context, require_capability, RequestContext
from app.core.database import execute_query, execute_command

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/data-sources", tags=["데이터소스"])


# ─── 요청/응답 모델 ────────────────────────────────────────

class DataSourceCreate(BaseModel):
    """데이터소스 생성 요청."""
    name: str
    source_type: str = "POSTGRES"  # POSTGRES, MYSQL, ORACLE, CSV, PARQUET
    connection_config: dict = Field(default_factory=dict)
    credential_ref: str = ""


class DataSourceResponse(BaseModel):
    """데이터소스 응답."""
    id: UUID
    name: str
    source_type: str
    is_active: bool = True
    last_health_status: str | None = None


# ─── 엔드포인트 ────────────────────────────────────────────

@router.get("")
async def list_data_sources(request: Request):
    """프로젝트 내 데이터소스 목록 조회."""
    ctx = get_request_context(request)
    require_capability(ctx, "datasource:read")

    rows = await execute_query(
        """
        SELECT id, name, source_type, is_active, last_health_status
        FROM olap.data_sources
        WHERE tenant_id = $1 AND project_id = $2 AND deleted_at IS NULL
        ORDER BY name
        """,
        [ctx.tenant_id, ctx.project_id],
    )
    return {"success": True, "data": rows}


@router.post("")
async def create_data_source(body: DataSourceCreate, request: Request):
    """데이터소스 생성."""
    ctx = get_request_context(request)
    require_capability(ctx, "datasource:write")

    rows = await execute_query(
        """
        INSERT INTO olap.data_sources (tenant_id, project_id, name, source_type, connection_config, credential_ref, created_by, updated_by)
        VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, $7)
        RETURNING id, name, source_type, is_active
        """,
        [ctx.tenant_id, ctx.project_id, body.name, body.source_type,
         json.dumps(body.connection_config) if body.connection_config else "{}",
         body.credential_ref, ctx.user_id],
    )
    if not rows:
        raise HTTPException(status_code=500, detail="생성 실패")
    return {"success": True, "data": rows[0]}


@router.get("/{ds_id}")
async def get_data_source(ds_id: UUID, request: Request):
    """데이터소스 상세 조회."""
    ctx = get_request_context(request)
    require_capability(ctx, "datasource:read")

    rows = await execute_query(
        """
        SELECT id, name, source_type, connection_config, is_active, last_health_status, last_health_checked_at, created_at
        FROM olap.data_sources
        WHERE id = $1 AND tenant_id = $2 AND project_id = $3 AND deleted_at IS NULL
        """,
        [str(ds_id), ctx.tenant_id, ctx.project_id],
    )
    if not rows:
        raise HTTPException(status_code=404, detail="데이터소스를 찾을 수 없습니다")
    return {"success": True, "data": rows[0]}


@router.delete("/{ds_id}")
async def delete_data_source(ds_id: UUID, request: Request):
    """데이터소스 소프트 삭제."""
    ctx = get_request_context(request)
    require_capability(ctx, "datasource:write")

    await execute_command(
        """
        UPDATE olap.data_sources SET deleted_at = now(), updated_by = $4
        WHERE id = $1 AND tenant_id = $2 AND project_id = $3
        """,
        [str(ds_id), ctx.tenant_id, ctx.project_id, ctx.user_id],
    )
    return {"success": True}


@router.post("/{ds_id}/test")
async def test_connection(ds_id: UUID, request: Request):
    """데이터소스 연결 테스트."""
    ctx = get_request_context(request)
    require_capability(ctx, "datasource:read")
    # 기본 구현: 현재 DB에 SELECT 1 실행 (추후 외부 DB 연결 테스트로 확장)
    try:
        await execute_query("SELECT 1 AS ok")
        result = {"status": "OK", "message": "연결 성공"}
    except Exception as e:
        logger.error("datasource_connection_test_failed", ds_id=str(ds_id), error=str(e))
        result = {"status": "ERROR", "message": "연결 테스트에 실패했습니다"}

    return {"success": True, "data": result}
