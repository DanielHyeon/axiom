"""ETL API — 파이프라인 CRUD + 실행 + Airflow 연동."""
from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Request, HTTPException

from app.core.context import get_request_context, require_capability
from app.core.database import execute_query, execute_command
from app.models.etl import ETLPipelineCreate

router = APIRouter(prefix="/etl", tags=["ETL"])


@router.get("/pipelines")
async def list_pipelines(request: Request):
    """ETL 파이프라인 목록 조회."""
    ctx = get_request_context(request)
    rows = await execute_query(
        """SELECT id, name, description, pipeline_type, status, airflow_dag_id, created_at, version_no
        FROM olap.etl_pipelines
        WHERE tenant_id = $1 AND project_id = $2 AND deleted_at IS NULL
        ORDER BY created_at DESC""",
        [ctx.tenant_id, ctx.project_id],
    )
    return {"success": True, "data": rows}


@router.post("/pipelines")
async def create_pipeline(body: ETLPipelineCreate, request: Request):
    """ETL 파이프라인 생성."""
    ctx = get_request_context(request)
    require_capability(ctx, "etl:edit")
    rows = await execute_query(
        """INSERT INTO olap.etl_pipelines
        (tenant_id, project_id, name, description, pipeline_type, source_config, target_config, transform_spec, schedule_cron, created_by, updated_by)
        VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, $8::jsonb, $9, $10, $10)
        RETURNING id, name, pipeline_type, status, created_at""",
        [ctx.tenant_id, ctx.project_id, body.name, body.description, body.pipeline_type,
         json.dumps(body.source_config), json.dumps(body.target_config),
         json.dumps([m.model_dump() for m in body.mappings]),
         body.schedule_cron, ctx.user_id],
    )
    return {"success": True, "data": rows[0] if rows else None}


@router.get("/pipelines/{pipeline_id}")
async def get_pipeline(pipeline_id: UUID, request: Request):
    """파이프라인 상세 조회."""
    ctx = get_request_context(request)
    rows = await execute_query(
        """SELECT id, name, description, pipeline_type, source_config, target_config, transform_spec,
                  schedule_cron, airflow_dag_id, status, created_at, version_no
        FROM olap.etl_pipelines
        WHERE id = $1 AND tenant_id = $2 AND project_id = $3 AND deleted_at IS NULL""",
        [str(pipeline_id), ctx.tenant_id, ctx.project_id],
    )
    if not rows:
        raise HTTPException(status_code=404, detail="파이프라인을 찾을 수 없습니다")
    return {"success": True, "data": rows[0]}


@router.post("/pipelines/{pipeline_id}/run")
async def run_pipeline(pipeline_id: UUID, request: Request):
    """ETL 파이프라인 수동 실행."""
    ctx = get_request_context(request)
    require_capability(ctx, "etl:run")

    # 파이프라인 존재 확인
    pipe = await execute_query(
        "SELECT id, status FROM olap.etl_pipelines WHERE id = $1 AND tenant_id = $2 AND project_id = $3",
        [str(pipeline_id), ctx.tenant_id, ctx.project_id],
    )
    if not pipe:
        raise HTTPException(status_code=404, detail="파이프라인을 찾을 수 없습니다")

    # 실행 레코드 생성
    run_rows = await execute_query(
        """INSERT INTO olap.etl_runs (pipeline_id, run_status, trigger_type, started_at, triggered_by)
        VALUES ($1, 'QUEUED', 'MANUAL', now(), $2)
        RETURNING id, run_status, trigger_type, started_at""",
        [str(pipeline_id), ctx.user_id],
    )
    return {"success": True, "data": run_rows[0] if run_rows else None}


@router.get("/pipelines/{pipeline_id}/runs")
async def list_runs(pipeline_id: UUID, request: Request):
    """파이프라인 실행 이력 조회."""
    ctx = get_request_context(request)
    # 파이프라인 JOIN으로 테넌트 격리 — 다른 테넌트의 실행 이력 조회 방지
    rows = await execute_query(
        """SELECT r.id, r.run_status, r.trigger_type, r.started_at, r.ended_at, r.rows_read, r.rows_written, r.error_message
        FROM olap.etl_runs r
        JOIN olap.etl_pipelines p ON r.pipeline_id = p.id
        WHERE r.pipeline_id = $1 AND p.tenant_id = $2 AND p.project_id = $3
        ORDER BY r.started_at DESC LIMIT 50""",
        [str(pipeline_id), ctx.tenant_id, ctx.project_id],
    )
    return {"success": True, "data": rows}


@router.get("/runs/{run_id}")
async def get_run(run_id: UUID, request: Request):
    """실행 상세 + 스텝 목록 조회."""
    ctx = get_request_context(request)
    # 파이프라인 JOIN으로 테넌트 격리 — 다른 테넌트의 실행 기록 조회 방지
    run_rows = await execute_query(
        """SELECT r.* FROM olap.etl_runs r
        JOIN olap.etl_pipelines p ON r.pipeline_id = p.id
        WHERE r.id = $1 AND p.tenant_id = $2 AND p.project_id = $3""",
        [str(run_id), ctx.tenant_id, ctx.project_id],
    )
    if not run_rows:
        raise HTTPException(status_code=404, detail="실행 기록을 찾을 수 없습니다")
    steps = await execute_query(
        "SELECT * FROM olap.etl_run_steps WHERE run_id = $1 ORDER BY step_order", [str(run_id)],
    )
    return {"success": True, "data": {**run_rows[0], "steps": steps}}
