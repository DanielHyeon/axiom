"""Airflow 연동 API — DAG 생성/트리거/상태 조회.

엔드포인트:
  POST /airflow/dag/generate     — ETL 파이프라인에서 DAG 코드 생성
  POST /airflow/dag/{dag_id}/trigger — DAG 수동 트리거
  GET  /airflow/dag/{dag_id}/status  — DAG 상태 + 최근 실행 이력
  GET  /airflow/dags              — OLAP Studio DAG 목록 조회
"""
from __future__ import annotations

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from app.core.context import get_request_context, require_capability
from app.core.database import execute_query, execute_command
from app.core.rate_limiter import check_rate_limit, AIRFLOW_TRIGGER_LIMIT
from app.services.airflow_service import (
    generate_dag_code,
    trigger_dag,
    get_dag_status,
    list_dags,
)

router = APIRouter(prefix="/airflow", tags=["Airflow"])


# ─── 요청 모델 ────────────────────────────────────────────

class GenerateDagRequest(BaseModel):
    """DAG 생성 요청 — 파이프라인 ID만 필요하다."""
    pipeline_id: str


# ─── 엔드포인트 ───────────────────────────────────────────

@router.post("/dag/generate")
async def api_generate_dag(body: GenerateDagRequest, request: Request):
    """ETL 파이프라인에서 Airflow DAG 코드를 생성한다.

    파이프라인 설정을 읽어 Python DAG 코드를 문자열로 반환하고,
    파이프라인 상태를 DEPLOYED로 변경한다.
    """
    ctx = get_request_context(request)
    require_capability(ctx, "etl:edit")

    # 파이프라인 조회 — 테넌트/프로젝트 격리
    rows = await execute_query(
        """SELECT id, name, pipeline_type, source_config, target_config,
                  transform_spec, schedule_cron
        FROM olap.etl_pipelines
        WHERE id = $1 AND tenant_id = $2 AND project_id = $3
              AND deleted_at IS NULL""",
        [body.pipeline_id, ctx.tenant_id, ctx.project_id],
    )
    if not rows:
        raise HTTPException(status_code=404, detail="파이프라인을 찾을 수 없습니다")

    pipe = rows[0]

    # JSONB 컬럼이 문자열로 올 수 있으므로 안전하게 dict로 변환
    source_cfg = pipe["source_config"] if isinstance(pipe["source_config"], dict) else {}
    target_cfg = pipe["target_config"] if isinstance(pipe["target_config"], dict) else {}
    transform_cfg = pipe["transform_spec"] if isinstance(pipe["transform_spec"], dict) else {}

    code, dag_id = generate_dag_code(
        pipeline_id=str(pipe["id"]),
        pipeline_name=pipe["name"],
        pipeline_type=pipe["pipeline_type"],
        source_config=source_cfg,
        target_config=target_cfg,
        transform_spec=transform_cfg,
        schedule=pipe.get("schedule_cron"),
    )

    # DAG ID를 파이프라인에 저장하고 상태를 DEPLOYED로 전환
    await execute_command(
        """UPDATE olap.etl_pipelines
        SET airflow_dag_id = $2, status = 'DEPLOYED', updated_at = now()
        WHERE id = $1""",
        [body.pipeline_id, dag_id],
    )

    return {
        "success": True,
        "data": {
            "dag_id": dag_id,
            "dag_code": code,
            "pipeline_id": body.pipeline_id,
        },
    }


@router.post("/dag/{dag_id}/trigger")
async def api_trigger_dag(dag_id: str, request: Request):
    """Airflow DAG를 트리거한다.

    Airflow REST API POST /api/v1/dags/{dag_id}/dagRuns 를 호출한다.
    Airflow 연결 실패 시 502 에러를 반환한다.
    """
    # 레이트 리밋 검사 -- Airflow 트리거는 분당 5회 제한
    await check_rate_limit(request, AIRFLOW_TRIGGER_LIMIT)

    ctx = get_request_context(request)
    require_capability(ctx, "etl:run")

    # 테넌트 소유권 검증 -- 다른 테넌트의 DAG 트리거 방지
    rows = await execute_query(
        "SELECT 1 FROM olap.etl_pipelines WHERE airflow_dag_id = $1 AND tenant_id = $2 AND project_id = $3 AND deleted_at IS NULL",
        [dag_id, ctx.tenant_id, ctx.project_id],
    )
    if not rows:
        raise HTTPException(status_code=404, detail="DAG를 찾을 수 없습니다")

    result = await trigger_dag(dag_id)
    if not result.get("success"):
        raise HTTPException(
            status_code=502,
            detail=result.get("error", "Airflow 트리거 실패"),
        )
    return {"success": True, "data": result.get("data")}


@router.get("/dag/{dag_id}/status")
async def api_dag_status(dag_id: str, request: Request):
    """DAG 상태 + 최근 실행 이력 조회.

    Airflow 미설정 시에도 에러 메시지를 포함한 응답을 반환한다.
    """
    ctx = get_request_context(request)

    # 테넌트 소유권 검증 — 다른 테넌트의 DAG 상태 조회 방지
    rows = await execute_query(
        "SELECT 1 FROM olap.etl_pipelines WHERE airflow_dag_id = $1 AND tenant_id = $2 AND project_id = $3 AND deleted_at IS NULL",
        [dag_id, ctx.tenant_id, ctx.project_id],
    )
    if not rows:
        raise HTTPException(status_code=404, detail="DAG를 찾을 수 없습니다")

    result = await get_dag_status(dag_id)
    return {"success": True, "data": result}


@router.get("/dags")
async def api_list_dags(request: Request):
    """OLAP Studio 태그가 달린 DAG 목록을 조회한다.

    테넌트 소유 파이프라인의 DAG만 필터링하여 반환한다.
    Airflow 미설정 시 빈 리스트를 반환한다.
    """
    ctx = get_request_context(request)

    # 테넌트 소유 파이프라인의 DAG ID만 조회
    pipe_rows = await execute_query(
        "SELECT airflow_dag_id FROM olap.etl_pipelines WHERE tenant_id = $1 AND project_id = $2 AND airflow_dag_id IS NOT NULL AND deleted_at IS NULL",
        [ctx.tenant_id, ctx.project_id],
    )
    tenant_dag_ids = {r["airflow_dag_id"] for r in pipe_rows}

    # Airflow에서 전체 목록을 가져온 뒤 테넌트 소유분만 필터링
    all_dags = await list_dags()
    filtered = [d for d in all_dags if d["dag_id"] in tenant_dag_ids]
    return {"success": True, "data": filtered}
