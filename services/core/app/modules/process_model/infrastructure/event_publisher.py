"""
프로세스 모델 이벤트 발행 — Transactional Outbox 패턴.

같은 트랜잭션 안에서 EventOutbox에 INSERT하고,
SyncWorker(기존 Outbox Relay)가 Redis Streams로 전달한다.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base_models import EventOutbox


async def publish_process_event(
    session: AsyncSession,
    *,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    tenant_id: str,
    payload: dict[str, Any],
) -> str:
    """프로세스 모델 이벤트를 Outbox에 기록한다.

    같은 DB 트랜잭션 안에서 호출되어야 하며,
    SyncWorker가 PENDING 상태 이벤트를 Redis Streams로 전송한다.
    """
    event_id = str(uuid4())
    outbox_entry = EventOutbox(
        id=event_id,
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=str(aggregate_id),
        tenant_id=tenant_id,
        payload=payload,
        status="PENDING",
    )
    session.add(outbox_entry)
    return event_id
