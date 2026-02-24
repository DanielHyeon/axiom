"""DDD-P3-02: Event Sourcing PoC — WorkItem Event Store.

WorkItem Aggregate의 모든 상태 변경을 이벤트로 순서대로 저장하고,
이벤트 리플레이로 현재 상태를 복원한다.

PoC 범위:
  - core.work_item_events 테이블에 순서(version)대로 이벤트 저장
  - 낙관적 동시성 제어 (expected_version)
  - 이벤트 리플레이로 WorkItem Aggregate 복원
  - Snapshot 없이 시작 (이벤트 수가 적으므로)
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.process.domain.aggregates.work_item import (
    AgentMode,
    WorkItem,
    WorkItemStatus,
)
from app.modules.process.domain.events import (
    DomainEvent,
    HitlApproved,
    HitlRejected,
    WorkItemCancelled,
    WorkItemCompleted,
    WorkItemCreated,
    WorkItemReworkRequested,
    WorkItemStarted,
    WorkItemSubmitted,
)

logger = logging.getLogger("axiom.event_store")


# ── DDL ──────────────────────────────────────────────────

WORK_ITEM_EVENTS_DDL = """\
CREATE TABLE IF NOT EXISTS work_item_events (
    id SERIAL PRIMARY KEY,
    aggregate_id VARCHAR NOT NULL,
    event_type VARCHAR NOT NULL,
    event_data JSONB NOT NULL,
    version INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (aggregate_id, version)
);
CREATE INDEX IF NOT EXISTS idx_work_item_events_aggregate
    ON work_item_events (aggregate_id, version);
"""


async def ensure_event_store_table(db: AsyncSession) -> None:
    """work_item_events 테이블이 없으면 생성."""
    for stmt in WORK_ITEM_EVENTS_DDL.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            await db.execute(text(stmt))
    await db.commit()


# ── Event Type Registry ──────────────────────────────────

_EVENT_TYPE_MAP: dict[str, type[DomainEvent]] = {
    "WorkItemCreated": WorkItemCreated,
    "WorkItemStarted": WorkItemStarted,
    "WorkItemSubmitted": WorkItemSubmitted,
    "WorkItemCompleted": WorkItemCompleted,
    "WorkItemCancelled": WorkItemCancelled,
    "WorkItemReworkRequested": WorkItemReworkRequested,
    "HitlApproved": HitlApproved,
    "HitlRejected": HitlRejected,
}

# Status mapping: event → resulting WorkItemStatus
_EVENT_STATUS_MAP: dict[str, WorkItemStatus] = {
    "WorkItemCreated": WorkItemStatus.TODO,
    "WorkItemStarted": WorkItemStatus.IN_PROGRESS,
    "WorkItemSubmitted": WorkItemStatus.SUBMITTED,
    "WorkItemCompleted": WorkItemStatus.DONE,
    "WorkItemCancelled": WorkItemStatus.CANCELLED,
    "WorkItemReworkRequested": WorkItemStatus.REWORK,
    "HitlApproved": WorkItemStatus.DONE,
    "HitlRejected": WorkItemStatus.REWORK,
}


# ── WorkItemEventStore ───────────────────────────────────

class WorkItemEventStore:
    """WorkItem Aggregate의 이벤트를 저장하고, 리플레이로 상태를 복원한다."""

    async def append(
        self,
        db: AsyncSession,
        aggregate_id: str,
        event: DomainEvent,
        expected_version: int,
    ) -> None:
        """낙관적 동시성 제어 + 이벤트 추가.

        Raises:
            ValueError: version 충돌 (concurrent modification)
        """
        event_type = type(event).__name__
        event_data = _serialize_event(event)

        try:
            await db.execute(
                text("""
                    INSERT INTO work_item_events
                        (aggregate_id, event_type, event_data, version, created_at)
                    VALUES (:aggregate_id, :event_type, :event_data::jsonb, :version, :created_at)
                """),
                {
                    "aggregate_id": aggregate_id,
                    "event_type": event_type,
                    "event_data": json.dumps(event_data, ensure_ascii=False, default=str),
                    "version": expected_version,
                    "created_at": event.occurred_at,
                },
            )
        except Exception as e:
            if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                raise ValueError(
                    f"Optimistic concurrency conflict: aggregate={aggregate_id}, "
                    f"expected_version={expected_version}"
                ) from e
            raise

    async def append_events(
        self,
        db: AsyncSession,
        aggregate_id: str,
        events: list[DomainEvent],
        starting_version: int,
    ) -> int:
        """여러 이벤트를 일괄 추가. 최종 version을 반환."""
        version = starting_version
        for event in events:
            await self.append(db, aggregate_id, event, version)
            version += 1
        return version

    async def load(self, db: AsyncSession, aggregate_id: str) -> WorkItem | None:
        """이벤트 리플레이로 WorkItem Aggregate 복원.

        Returns:
            WorkItem or None if no events found.
        """
        result = await db.execute(
            text("""
                SELECT event_type, event_data, version, created_at
                FROM work_item_events
                WHERE aggregate_id = :aggregate_id
                ORDER BY version
            """),
            {"aggregate_id": aggregate_id},
        )
        rows = result.fetchall()
        if not rows:
            return None

        return _replay_events(aggregate_id, rows)

    async def get_events(
        self,
        db: AsyncSession,
        aggregate_id: str,
        from_version: int = 0,
    ) -> list[dict[str, Any]]:
        """Aggregate의 이벤트 히스토리 조회."""
        result = await db.execute(
            text("""
                SELECT event_type, event_data, version, created_at
                FROM work_item_events
                WHERE aggregate_id = :aggregate_id AND version >= :from_version
                ORDER BY version
            """),
            {"aggregate_id": aggregate_id, "from_version": from_version},
        )
        return [
            {
                "event_type": row.event_type,
                "event_data": row.event_data if isinstance(row.event_data, dict) else json.loads(row.event_data),
                "version": row.version,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in result.fetchall()
        ]

    async def count_events(self, db: AsyncSession, aggregate_id: str) -> int:
        """Aggregate의 총 이벤트 수."""
        result = await db.execute(
            text("SELECT COUNT(*) FROM work_item_events WHERE aggregate_id = :aggregate_id"),
            {"aggregate_id": aggregate_id},
        )
        return result.scalar() or 0


# ── Helpers ──────────────────────────────────────────────

def _serialize_event(event: DomainEvent) -> dict[str, Any]:
    """DomainEvent를 JSON-serializable dict로 변환."""
    data = {}
    for k, v in asdict(event).items():
        if isinstance(v, datetime):
            data[k] = v.isoformat()
        else:
            data[k] = v
    return data


def _replay_events(aggregate_id: str, rows: list) -> WorkItem:
    """이벤트 목록을 리플레이하여 WorkItem Aggregate를 복원."""
    wi: WorkItem | None = None
    version = 0

    for row in rows:
        event_type = row.event_type
        event_data = row.event_data if isinstance(row.event_data, dict) else json.loads(row.event_data)
        version = row.version

        if event_type == "WorkItemCreated":
            wi = WorkItem(
                id=aggregate_id,
                proc_inst_id=event_data.get("proc_inst_id"),
                activity_name=event_data.get("activity_name"),
                activity_type=event_data.get("activity_type", "humanTask"),
                assignee_id=event_data.get("assignee_id"),
                agent_mode=AgentMode(event_data.get("agent_mode", "MANUAL")),
                status=WorkItemStatus.TODO,
                result_data=event_data.get("result_data"),
                tenant_id=event_data.get("tenant_id", ""),
                version=version,
            )
        elif wi is not None:
            new_status = _EVENT_STATUS_MAP.get(event_type)
            if new_status:
                wi.status = new_status
            wi.version = version

            # Apply event-specific data
            if event_type == "WorkItemCompleted":
                wi.result_data = event_data.get("result_data", wi.result_data)
            elif event_type == "WorkItemSubmitted":
                if event_data.get("verification"):
                    rd = wi.result_data or {}
                    rd["self_verification"] = event_data["verification"]
                    wi.result_data = rd
            elif event_type in ("HitlApproved", "HitlRejected"):
                rd = wi.result_data or {}
                rd["hitl_feedback"] = event_data.get("feedback", "")
                wi.result_data = rd
            elif event_type == "WorkItemReworkRequested":
                rd = wi.result_data or {}
                rd["rework_reason"] = event_data.get("reason", "")
                wi.result_data = rd

    if wi is None:
        raise ValueError(f"No WorkItemCreated event found for aggregate {aggregate_id}")

    return wi
