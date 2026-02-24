"""DDD-P3-05: Dead Letter Queue 관리 API.

- GET  /admin/events/dead-letter          — DLQ 이벤트 목록 조회
- POST /admin/events/dead-letter/{id}/retry   — DLQ 이벤트 수동 재시도
- POST /admin/events/dead-letter/{id}/discard — DLQ 이벤트 폐기
- GET  /admin/events/metrics               — 이벤트 파이프라인 메트릭
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.observability import metrics_registry
from app.models.base_models import EventDeadLetter, EventOutbox

logger = logging.getLogger("axiom.admin.events")

router = APIRouter(prefix="/admin/events", tags=["admin-events"])


# ── Response models ─────────────────────────────────────

class DeadLetterItem(BaseModel):
    id: str
    original_event_id: str
    event_type: str
    aggregate_type: str | None
    aggregate_id: str | None
    failure_reason: str | None
    retry_count: int
    first_failed_at: datetime | None
    last_failed_at: datetime | None
    resolved_at: datetime | None
    resolution: str | None
    tenant_id: str

    model_config = {"from_attributes": True}


class DeadLetterListResponse(BaseModel):
    items: list[DeadLetterItem]
    total: int


class DiscardRequest(BaseModel):
    reason: str


class RetryResponse(BaseModel):
    event_id: str
    status: str
    message: str


class PipelineMetricsResponse(BaseModel):
    outbox_pending_count: int
    outbox_published_total: float
    outbox_failed_total: float
    outbox_dead_letter_total: float
    dlq_depth: float
    dlq_reprocess_success_total: float
    dlq_reprocess_failed_total: float
    dlq_db_unresolved_count: int


# ── Endpoints ───────────────────────────────────────────

@router.get("/dead-letter", response_model=DeadLetterListResponse)
async def list_dead_letters(
    tenant_id: str = Query(..., description="Tenant ID"),
    resolved: Optional[bool] = Query(None, description="Filter by resolved status"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_session),
):
    """DLQ에 적재된 이벤트 목록 조회."""
    stmt = select(EventDeadLetter).where(EventDeadLetter.tenant_id == tenant_id)

    if resolved is True:
        stmt = stmt.where(EventDeadLetter.resolved_at.is_not(None))
    elif resolved is False:
        stmt = stmt.where(EventDeadLetter.resolved_at.is_(None))

    if event_type:
        stmt = stmt.where(EventDeadLetter.event_type == event_type)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = await db.scalar(count_stmt) or 0

    stmt = stmt.order_by(EventDeadLetter.last_failed_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    items = [DeadLetterItem.model_validate(row) for row in result.scalars().all()]

    return DeadLetterListResponse(items=items, total=total)


@router.post("/dead-letter/{event_id}/retry", response_model=RetryResponse)
async def retry_dead_letter(
    event_id: str,
    db: AsyncSession = Depends(get_session),
):
    """DLQ 이벤트를 수동 재시도 — Outbox PENDING으로 재삽입."""
    result = await db.execute(
        select(EventDeadLetter).where(EventDeadLetter.id == event_id)
    )
    dl = result.scalar_one_or_none()
    if not dl:
        raise HTTPException(status_code=404, detail="Dead letter event not found")
    if dl.resolved_at is not None:
        raise HTTPException(status_code=409, detail=f"Already resolved: {dl.resolution}")

    # Re-insert into outbox as PENDING
    new_outbox = EventOutbox(
        id=str(uuid.uuid4()),
        event_type=dl.event_type,
        aggregate_type=dl.aggregate_type or "unknown",
        aggregate_id=dl.aggregate_id or "unknown",
        payload=dl.payload,
        status="PENDING",
        tenant_id=dl.tenant_id,
        retry_count=0,
    )
    db.add(new_outbox)

    # Mark dead letter as resolved
    dl.resolved_at = datetime.now(timezone.utc)
    dl.resolution = "RETRIED"
    await db.commit()

    metrics_registry.inc("core_dlq_retry_total")
    logger.info("Dead letter %s retried → outbox %s", event_id, new_outbox.id)

    return RetryResponse(
        event_id=event_id,
        status="RETRIED",
        message=f"Re-inserted as outbox entry {new_outbox.id}",
    )


@router.post("/dead-letter/{event_id}/discard", response_model=RetryResponse)
async def discard_dead_letter(
    event_id: str,
    body: DiscardRequest,
    db: AsyncSession = Depends(get_session),
):
    """DLQ 이벤트를 폐기 (사유 기록)."""
    result = await db.execute(
        select(EventDeadLetter).where(EventDeadLetter.id == event_id)
    )
    dl = result.scalar_one_or_none()
    if not dl:
        raise HTTPException(status_code=404, detail="Dead letter event not found")
    if dl.resolved_at is not None:
        raise HTTPException(status_code=409, detail=f"Already resolved: {dl.resolution}")

    dl.resolved_at = datetime.now(timezone.utc)
    dl.resolution = "DISCARDED"
    dl.failure_reason = f"{dl.failure_reason or ''} | DISCARDED: {body.reason}"
    await db.commit()

    metrics_registry.inc("core_dlq_discard_total")
    logger.info("Dead letter %s discarded: %s", event_id, body.reason)

    return RetryResponse(
        event_id=event_id,
        status="DISCARDED",
        message=f"Discarded with reason: {body.reason}",
    )


@router.get("/metrics", response_model=PipelineMetricsResponse)
async def pipeline_metrics(
    db: AsyncSession = Depends(get_session),
):
    """이벤트 파이프라인 메트릭 (JSON)."""
    # DB-based counts
    pending_count = await db.scalar(
        select(func.count()).select_from(EventOutbox).where(EventOutbox.status == "PENDING")
    ) or 0

    dlq_unresolved = await db.scalar(
        select(func.count()).select_from(EventDeadLetter).where(EventDeadLetter.resolved_at.is_(None))
    ) or 0

    return PipelineMetricsResponse(
        outbox_pending_count=pending_count,
        outbox_published_total=metrics_registry.get_counter("core_event_outbox_published_total"),
        outbox_failed_total=metrics_registry.get_counter("core_event_outbox_failed_total"),
        outbox_dead_letter_total=metrics_registry.get_counter("core_dlq_messages_total"),
        dlq_depth=metrics_registry.get_gauge("core_dlq_depth"),
        dlq_reprocess_success_total=metrics_registry.get_counter("core_dlq_reprocess_success_total"),
        dlq_reprocess_failed_total=metrics_registry.get_counter("core_dlq_reprocess_failed_total"),
        dlq_db_unresolved_count=dlq_unresolved,
    )
