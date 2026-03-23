"""
Twin 서비스 API — /api/v1/twin/* 라우터.

Phase 4: 9개 엔드포인트 (instances, events, states, dashboard, snapshots).
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import get_current_user
from app.models.twin_models import (
    ProcessInstance, StepInstance, TwinEvent, TwinSnapshot, TwinState,
)
from app.models.schemas import (
    CaptureSnapshotRequest, DashboardSummary, InstanceResponse,
    PublishEventRequest, SnapshotResponse, StartInstanceRequest,
    TwinStateResponse,
)

router = APIRouter(prefix="/api/v1/twin", tags=["twin"])


# ── Instances ──────────────────────────────────────────────

@router.post("/instances", response_model=InstanceResponse, status_code=201)
async def create_instance(
    body: StartInstanceRequest,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """프로세스 인스턴스 생성."""
    instance = ProcessInstance(
        tenant_id=user["tenant_id"],
        workspace_id=body.workspace_id,
        process_definition_id=body.process_definition_id,
        process_version_id=body.process_version_id,
        business_key=body.business_key,
        source_system=body.source_system,
        status="CREATED",
        priority=body.priority,
        due_at=body.due_at,
        started_at=datetime.now(timezone.utc),
        payload_json=body.payload,
    )
    session.add(instance)
    await session.commit()
    await session.refresh(instance)
    return instance


@router.get("/instances/{instance_id}", response_model=InstanceResponse)
async def get_instance(
    instance_id: UUID,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    r = await session.execute(
        select(ProcessInstance).where(
            ProcessInstance.id == instance_id,
            ProcessInstance.is_deleted == False,
        )
    )
    instance = r.scalar_one_or_none()
    if not instance:
        raise HTTPException(404, "Instance not found")
    return instance


@router.get("/instances")
async def list_instances(
    workspace_id: UUID = Query(...),
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    base = select(ProcessInstance).where(
        ProcessInstance.workspace_id == workspace_id,
        ProcessInstance.is_deleted == False,
    )
    if status:
        base = base.where(ProcessInstance.status == status)
    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (await session.execute(
        base.order_by(ProcessInstance.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return {"success": True, "data": {"items": [InstanceResponse.model_validate(r) for r in rows], "total": total, "page": page, "page_size": page_size}}


# ── Events ─────────────────────────────────────────────────

@router.post("/events", status_code=201)
async def publish_event(
    body: PublishEventRequest,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """트윈 이벤트 발행 (멱등성 보장 — aggregate 스코프)."""
    # aggregate_seq 원자적 발급
    from app.models.twin_models import AggregateSequence
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    seq_stmt = pg_insert(AggregateSequence).values(
        tenant_id=user["tenant_id"],
        aggregate_type=body.aggregate_type,
        aggregate_id=body.aggregate_id,
        last_seq=1,
    ).on_conflict_do_update(
        index_elements=["tenant_id", "aggregate_type", "aggregate_id"],
        set_={"last_seq": AggregateSequence.last_seq + 1},
    ).returning(AggregateSequence.last_seq)

    seq_result = await session.execute(seq_stmt)
    aggregate_seq = seq_result.scalar_one()

    event = TwinEvent(
        tenant_id=user["tenant_id"],
        workspace_id=body.workspace_id,
        event_type=body.event_type,
        aggregate_type=body.aggregate_type,
        aggregate_id=body.aggregate_id,
        ordering_key=f"{body.aggregate_type}:{body.aggregate_id}",
        aggregate_seq=aggregate_seq,
        idempotency_key=body.idempotency_key,
        occurred_at=body.occurred_at or datetime.now(timezone.utc),
        source_channel=body.source_channel,
        payload_json=body.payload,
        correlation_id=body.correlation_id,
        causation_id=body.causation_id,
    )
    session.add(event)
    await session.commit()
    return {"success": True, "data": {"event_id": str(event.id), "aggregate_seq": aggregate_seq}}


# ── States ─────────────────────────────────────────────────

@router.get("/states/{entity_type}/{entity_id}", response_model=TwinStateResponse)
async def get_state(
    entity_type: str,
    entity_id: UUID,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    r = await session.execute(
        select(TwinState).where(
            TwinState.entity_type == entity_type,
            TwinState.entity_id == entity_id,
            TwinState.is_deleted == False,
        )
    )
    state = r.scalar_one_or_none()
    if not state:
        raise HTTPException(404, "State not found")
    return state


# ── Dashboard ──────────────────────────────────────────────

@router.get("/dashboard/workspaces/{workspace_id}", response_model=DashboardSummary)
async def get_dashboard(
    workspace_id: UUID,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """워크스페이스 운영 요약 — 단일 쿼리 집계."""
    from sqlalchemy import case

    # 단일 쿼리로 전체 + 상태별 집계
    result = await session.execute(
        select(
            func.count().label("total"),
            func.count().filter(ProcessInstance.status == "RUNNING").label("running"),
            func.count().filter(ProcessInstance.status == "WAITING").label("waiting"),
            func.count().filter(ProcessInstance.status == "COMPLETED").label("completed"),
            func.count().filter(ProcessInstance.status == "FAILED").label("failed"),
        ).where(
            ProcessInstance.workspace_id == workspace_id,
            ProcessInstance.is_deleted == False,
        )
    )
    row = result.one()

    # SLA breach 수
    breach_count = (await session.execute(
        select(func.count()).select_from(
            select(TwinState).where(
                TwinState.workspace_id == workspace_id,
                TwinState.sla_status == "BREACHED",
                TwinState.is_deleted == False,
            ).subquery()
        )
    )).scalar_one()

    return DashboardSummary(
        total_instances=row.total,
        running=row.running,
        waiting=row.waiting,
        completed=row.completed,
        failed=row.failed,
        sla_breach_count=breach_count,
    )


@router.get("/dashboard/workspaces/{workspace_id}/processes")
async def get_process_health(
    workspace_id: UUID,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """프로세스별 건강도 목록."""
    r = await session.execute(
        select(TwinState).where(
            TwinState.workspace_id == workspace_id,
            TwinState.entity_type == "PROCESS",
            TwinState.is_deleted == False,
        ).order_by(TwinState.health_score.asc())
    )
    states = r.scalars().all()
    return {"success": True, "data": [TwinStateResponse.model_validate(s) for s in states]}


# ── Snapshots ──────────────────────────────────────────────

@router.post("/snapshots", response_model=SnapshotResponse, status_code=201)
async def capture_snapshot(
    body: CaptureSnapshotRequest,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """수동 스냅샷 캡처."""
    snapshot = TwinSnapshot(
        tenant_id=user["tenant_id"],
        workspace_id=body.workspace_id,
        snapshot_type="MANUAL",
        entity_scope_type=body.entity_scope_type,
        entity_scope_id=body.entity_scope_id,
        captured_at=datetime.now(timezone.utc),
        summary_json={},  # TODO: 실제 집계 데이터 수집
    )
    session.add(snapshot)
    await session.commit()
    await session.refresh(snapshot)
    return snapshot


@router.get("/snapshots")
async def list_snapshots(
    workspace_id: UUID = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    base = select(TwinSnapshot).where(
        TwinSnapshot.workspace_id == workspace_id,
        TwinSnapshot.is_deleted == False,
    )
    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (await session.execute(
        base.order_by(TwinSnapshot.captured_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return {"success": True, "data": {"items": [SnapshotResponse.model_validate(r) for r in rows], "total": total}}
