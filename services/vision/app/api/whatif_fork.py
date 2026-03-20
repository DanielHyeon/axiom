"""
What-if Fork REST API — 이벤트소싱 기반 브랜칭 시뮬레이션
==========================================================

Event Fork Engine을 FastAPI 엔드포인트로 노출한다.
기존 DAG 기반 /whatif-dag 라우터와 **완전히 분리된** 라우터.

엔드포인트:
- POST   /api/v3/cases/{case_id}/whatif-fork/branches              — 브랜치 생성
- POST   /api/v3/cases/{case_id}/whatif-fork/branches/{id}/simulate — 시뮬레이션 실행
- GET    /api/v3/cases/{case_id}/whatif-fork/branches/{id}          — 브랜치 상세 조회
- GET    /api/v3/cases/{case_id}/whatif-fork/branches/{id}/events   — 이벤트 로그 조회
- POST   /api/v3/cases/{case_id}/whatif-fork/compare                — 시나리오 비교
- DELETE /api/v3/cases/{case_id}/whatif-fork/branches/{id}          — 브랜치 삭제
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api._auth import get_current_user
from app.core.auth import CurrentUser, auth_service
from app.db.pg_utils import _db_url, get_conn_from_pool
from app.events.outbox import EventPublisher

logger = logging.getLogger(__name__)


# ── 라우터 ─────────────────────────────────────────────────────── #

router = APIRouter(
    prefix="/api/v3/cases/{case_id}/whatif-fork",
    tags=["What-If Fork"],
)


# ── Neo4j 드라이버 lazy 초기화 ────────────────────────────────── #

_neo4j_driver = None
_fork_engine = None


def _get_neo4j_driver():
    """Neo4j AsyncDriver를 지연 초기화한다."""
    global _neo4j_driver
    if _neo4j_driver is None:
        try:
            from neo4j import AsyncGraphDatabase
            neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
            neo4j_user = os.getenv("NEO4J_USER", "neo4j")
            neo4j_password = os.getenv("NEO4J_PASSWORD", "password")
            _neo4j_driver = AsyncGraphDatabase.driver(
                neo4j_uri, auth=(neo4j_user, neo4j_password),
            )
            logger.info("Neo4j AsyncDriver 초기화 완료: %s", neo4j_uri)
        except Exception:
            logger.warning("Neo4j 드라이버 초기화 실패", exc_info=True)
            _neo4j_driver = None
    return _neo4j_driver


def _get_fork_engine():
    """EventForkEngine 싱글톤을 반환한다."""
    global _fork_engine
    if _fork_engine is None:
        from app.engines.event_fork_engine import EventForkEngine
        driver = _get_neo4j_driver()
        if driver is None:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "NEO4J_UNAVAILABLE",
                    "message": "Neo4j 연결을 사용할 수 없습니다.",
                },
            )
        _fork_engine = EventForkEngine(neo4j_driver=driver, db_url=_db_url())
    return _fork_engine


# ── 인증 헬퍼 ──────────────────────────────────────────────────── #

def _ensure_auth(user: CurrentUser) -> None:
    """admin 또는 staff 역할만 허용."""
    auth_service.requires_role(user, ["admin", "staff"])


# ── Pydantic 요청/응답 모델 ────────────────────────────────────── #

class InterventionRequest(BaseModel):
    """개입 정의 (요청용)."""
    node_id: str = Field(..., alias="nodeId", description="온톨로지 노드 ID")
    field: str = Field(..., description="변경할 필드명")
    value: float = Field(..., description="개입 값")
    description: str = Field(default="", description="설명")

    model_config = {"populate_by_name": True}


class CreateBranchRequest(BaseModel):
    """브랜치 생성 요청."""
    name: str = Field(
        ..., min_length=1, max_length=200, description="시나리오 이름",
    )
    description: str = Field(default="", description="시나리오 설명")
    interventions: list[InterventionRequest] = Field(
        ..., min_length=1, description="개입 목록 (1개 이상)",
    )
    base_timestamp: datetime | None = Field(
        default=None, description="포크 기준 시점 (생략 시 현재 시각)",
    )
    max_cascade_depth: int = Field(
        default=20, ge=1, le=100, description="GWT 체이닝 최대 깊이",
    )
    gwt_overrides: dict = Field(
        default_factory=dict, description="GWT 룰 오버라이드",
    )


class CompareRequest(BaseModel):
    """시나리오 비교 요청."""
    branch_ids: list[str] = Field(
        ..., min_length=2, description="비교할 브랜치 ID 목록 (2개 이상)",
    )


class BranchResponse(BaseModel):
    """브랜치 상세 응답."""
    id: str
    case_id: str
    tenant_id: str
    name: str
    description: str | None = None
    base_timestamp: str
    status: str
    interventions: Any = None
    gwt_overrides: Any = None
    result_summary: Any = None
    event_count: int = 0
    created_by: str | None = None
    created_at: str | None = None
    completed_at: str | None = None


class SimulationEventResponse(BaseModel):
    """시뮬레이션 이벤트 응답."""
    id: str
    branch_id: str
    sequence_number: int
    event_type: str
    aggregate_type: str | None = None
    aggregate_id: str | None = None
    payload: Any = None
    source: str
    source_rule_id: str | None = None
    state_snapshot: Any = None
    created_at: str | None = None


# ── API 엔드포인트 ─────────────────────────────────────────────── #

@router.post("/branches", status_code=status.HTTP_201_CREATED)
async def create_branch(
    case_id: str,
    payload: CreateBranchRequest,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """시뮬레이션 브랜치를 생성한다.

    포크 기준 시점(base_timestamp)에서 온톨로지 상태를 복제하여
    가상 이벤트 스트림을 시작할 준비를 한다.
    """
    _ensure_auth(user)

    from app.engines.event_fork_engine import ForkConfig, InterventionSpec

    engine = _get_fork_engine()

    # InterventionRequest → InterventionSpec 변환
    interventions = [
        InterventionSpec(
            node_id=iv.node_id,
            field=iv.field,
            value=iv.value,
            description=iv.description,
        )
        for iv in payload.interventions
    ]

    config = ForkConfig(
        branch_name=payload.name,
        case_id=case_id,
        tenant_id=str(user.tenant_id),
        base_timestamp=payload.base_timestamp or datetime.now(timezone.utc),
        interventions=interventions,
        description=payload.description,
        max_cascade_depth=payload.max_cascade_depth,
        gwt_overrides=payload.gwt_overrides,
        created_by=str(user.user_id),
    )

    try:
        branch_id = await engine.create_fork(config)
    except Exception as e:
        error_msg = str(e)
        # 중복 이름 에러 처리
        if "uq_sim_branch_case_name" in error_msg or "duplicate" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "BRANCH_NAME_DUPLICATE",
                    "message": f"동일 케이스 내 브랜치 이름 중복: '{payload.name}'",
                },
            )
        raise HTTPException(
            status_code=500,
            detail={"code": "BRANCH_CREATE_FAILED", "message": error_msg},
        )

    return {
        "success": True,
        "branch_id": branch_id,
        "message": f"시뮬레이션 브랜치 '{payload.name}' 생성 완료",
    }


@router.post("/branches/{branch_id}/simulate")
async def run_simulation(
    case_id: str,
    branch_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """시뮬레이션을 실행하고 결과를 반환한다.

    1. 기준 시점 온톨로지 스냅샷 로드
    2. intervention 적용
    3. GWT 룰 체인 시뮬레이션 (dry_run)
    4. KPI 델타 계산 + 이벤트 로그 저장
    """
    _ensure_auth(user)
    engine = _get_fork_engine()

    # 브랜치 존재 + 소유권 확인
    branch = await _get_branch_or_404(branch_id, case_id, str(user.tenant_id))

    # 이미 완료/실행 중인 브랜치는 재실행 불가
    if branch["status"] in ("running", "completed"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "BRANCH_ALREADY_PROCESSED",
                "message": f"브랜치 상태가 '{branch['status']}'이므로 재실행할 수 없습니다.",
            },
        )

    try:
        result = await engine.run_simulation(branch_id)
    except Exception as e:
        logger.exception("시뮬레이션 실행 실패: branch=%s", branch_id)
        raise HTTPException(
            status_code=500,
            detail={"code": "SIMULATION_FAILED", "message": str(e)},
        )

    # 시뮬레이션 완료 이벤트 발행 (Outbox 패턴)
    try:
        EventPublisher.publish(
            event_type="WHATIF_FORK_COMPLETED",
            aggregate_type="SimulationBranch",
            aggregate_id=branch_id,
            payload={
                "branch_id": branch_id,
                "case_id": case_id,
                "event_count": result.event_count,
                "kpi_delta_count": len(result.kpi_deltas),
                "cascade_depth": result.cascade_depth,
                "converged": result.converged,
            },
            tenant_id=str(user.tenant_id),
        )
    except Exception:
        # 이벤트 발행 실패는 시뮬레이션 결과에 영향 주지 않음
        logger.warning("WHATIF_FORK_COMPLETED 이벤트 발행 실패", exc_info=True)

    return {"success": True, **result.to_dict()}


@router.get("/branches/{branch_id}")
async def get_branch(
    case_id: str,
    branch_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """브랜치 상세 정보와 결과 요약을 조회한다."""
    _ensure_auth(user)
    branch = await _get_branch_or_404(branch_id, case_id, str(user.tenant_id))

    # JSONB 필드를 파싱
    for json_field in ("interventions", "gwt_overrides", "result_summary"):
        val = branch.get(json_field)
        if isinstance(val, str):
            try:
                branch[json_field] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                pass

    # datetime 필드를 ISO 문자열로 변환
    for dt_field in ("base_timestamp", "created_at", "completed_at"):
        val = branch.get(dt_field)
        if isinstance(val, datetime):
            branch[dt_field] = val.isoformat()
        elif val is None:
            branch[dt_field] = None

    return {"success": True, "branch": branch}


@router.get("/branches/{branch_id}/events")
async def get_branch_events(
    case_id: str,
    branch_id: str,
    limit: int = Query(default=100, ge=1, le=1000, description="최대 반환 건수"),
    offset: int = Query(default=0, ge=0, description="건너뛸 건수"),
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """브랜치의 시뮬레이션 이벤트 로그를 시퀀스 순으로 조회한다."""
    _ensure_auth(user)

    # 브랜치 존재 + 소유권 확인
    await _get_branch_or_404(branch_id, case_id, str(user.tenant_id))

    def _query_events():
        from psycopg2.extras import RealDictCursor
        with get_conn_from_pool() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            # 총 건수 조회
            cur.execute(
                "SELECT count(*) AS cnt FROM vision.simulation_events WHERE branch_id = %s",
                (branch_id,),
            )
            total = cur.fetchone()["cnt"]

            # 이벤트 목록 조회
            cur.execute(
                """
                SELECT * FROM vision.simulation_events
                WHERE branch_id = %s
                ORDER BY sequence_number ASC
                LIMIT %s OFFSET %s
                """,
                (branch_id, limit, offset),
            )
            rows = cur.fetchall()
            cur.close()
            return total, [dict(r) for r in rows]

    total, events = await asyncio.to_thread(_query_events)

    # datetime/JSONB 직렬화
    for evt in events:
        for json_field in ("payload", "state_snapshot"):
            val = evt.get(json_field)
            if isinstance(val, str):
                try:
                    evt[json_field] = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    pass
        for dt_field in ("created_at",):
            val = evt.get(dt_field)
            if isinstance(val, datetime):
                evt[dt_field] = val.isoformat()

    return {
        "success": True,
        "branch_id": branch_id,
        "total": total,
        "limit": limit,
        "offset": offset,
        "events": events,
    }


@router.post("/compare")
async def compare_scenarios(
    case_id: str,
    payload: CompareRequest,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """여러 브랜치의 시뮬레이션 결과를 비교한다.

    각 KPI에 대해 브랜치별 delta 값을 매트릭스로 반환.
    """
    _ensure_auth(user)
    engine = _get_fork_engine()

    # 모든 브랜치가 현재 case에 속하는지 확인
    for bid in payload.branch_ids:
        await _get_branch_or_404(bid, case_id, str(user.tenant_id))

    try:
        comparison = await engine.compare_scenarios(payload.branch_ids)
    except Exception as e:
        logger.exception("시나리오 비교 실패")
        raise HTTPException(
            status_code=500,
            detail={"code": "COMPARE_FAILED", "message": str(e)},
        )

    return {"success": True, **comparison}


@router.delete("/branches/{branch_id}", status_code=status.HTTP_200_OK)
async def delete_branch(
    case_id: str,
    branch_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """브랜치와 관련 이벤트를 삭제한다.

    simulation_events는 ON DELETE CASCADE로 자동 삭제된다.
    """
    _ensure_auth(user)

    # 브랜치 존재 + 소유권 확인
    await _get_branch_or_404(branch_id, case_id, str(user.tenant_id))

    def _delete():
        with get_conn_from_pool() as conn:
            cur = conn.cursor()
            # FK CASCADE로 simulation_events도 자동 삭제
            cur.execute(
                "DELETE FROM vision.simulation_branches WHERE id = %s AND case_id = %s",
                (branch_id, case_id),
            )
            deleted = cur.rowcount
            cur.close()
            conn.commit()
            return deleted

    deleted = await asyncio.to_thread(_delete)

    if deleted == 0:
        raise HTTPException(
            status_code=404,
            detail={"code": "BRANCH_NOT_FOUND", "message": f"브랜치를 찾을 수 없음: {branch_id}"},
        )

    return {
        "success": True,
        "message": f"브랜치 '{branch_id}' 삭제 완료",
    }


# ── 내부 헬퍼 ─────────────────────────────────────────────────── #

async def _get_branch_or_404(
    branch_id: str, case_id: str, tenant_id: str,
) -> dict:
    """브랜치를 조회하고, 없거나 권한이 없으면 404/403을 반환한다."""
    def _query():
        from psycopg2.extras import RealDictCursor
        with get_conn_from_pool() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                "SELECT * FROM vision.simulation_branches WHERE id = %s",
                (branch_id,),
            )
            row = cur.fetchone()
            cur.close()
            return dict(row) if row else None

    branch = await asyncio.to_thread(_query)

    if branch is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "BRANCH_NOT_FOUND",
                "message": f"시뮬레이션 브랜치를 찾을 수 없음: {branch_id}",
            },
        )

    # 테넌트 격리 확인
    if branch["tenant_id"] != tenant_id:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "TENANT_MISMATCH",
                "message": "이 브랜치에 접근할 권한이 없습니다.",
            },
        )

    # 케이스 소속 확인
    if branch["case_id"] != case_id:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "BRANCH_NOT_IN_CASE",
                "message": f"브랜치 '{branch_id}'는 케이스 '{case_id}'에 속하지 않습니다.",
            },
        )

    return branch
