from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select

from app.core.observability import metrics_registry
from app.core.redis_client import get_redis
from app.core.database import AsyncSessionLocal
from app.models.base_models import EventDeadLetter, EventOutbox
from app.workers.base import BaseWorker

logger = logging.getLogger("axiom.workers.sync")

# Outbox event lifecycle:
#   PENDING → PUBLISHED  (happy path)
#   PENDING → FAILED     (transient error, retry_count < MAX_RETRY)
#   FAILED  → PENDING    (via retry_failed_once)
#   FAILED  → DEAD_LETTER (retry_count >= MAX_RETRY)
MAX_RETRY = 3


class SyncWorker(BaseWorker):
    """
    Outbox Relay Worker: polls PENDING events from event_outbox and publishes
    to Redis Streams. Implements the Transactional Outbox pattern.

    Guarantees:
    1. Order: events processed in created_at ASC order
    2. At-least-once: PENDING → PUBLISHED only after successful XADD
    3. Failure isolation: individual event failure doesn't block batch
    4. Dead Letter: events exceeding MAX_RETRY move to DEAD_LETTER status
    5. Metrics: published/failed/dlq counters and gauges
    """

    def __init__(self, poll_interval_seconds: int = 5, max_batch: int = 100):
        super().__init__("sync")
        self.poll_interval_seconds = poll_interval_seconds
        self.max_batch = max_batch

    @staticmethod
    def _resolve_stream(event_type: str) -> str:
        if event_type.startswith("WATCH_"):
            return "axiom:watches"
        if event_type.startswith("WORKER_"):
            return "axiom:workers"
        return "axiom:core:events"

    async def publish_pending_once(self, limit: int | None = None) -> dict[str, int]:
        """Fetch PENDING events and publish to Redis Streams."""
        batch_size = min(max(limit or self.max_batch, 1), 1000)
        redis = get_redis()
        published = 0
        failed = 0

        async with AsyncSessionLocal() as session:
            rows = await session.execute(
                select(EventOutbox)
                .where(EventOutbox.status == "PENDING")
                .order_by(EventOutbox.created_at.asc())
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            )
            events = rows.scalars().all()

            for event in events:
                stream = self._resolve_stream(event.event_type)
                body = {
                    "event_id": event.id,
                    "event_type": event.event_type,
                    "aggregate_type": event.aggregate_type,
                    "aggregate_id": event.aggregate_id,
                    "tenant_id": event.tenant_id,
                    "payload": json.dumps(event.payload, ensure_ascii=True),
                }
                try:
                    await redis.xadd(stream, body, maxlen=10000, approximate=True)
                    event.status = "PUBLISHED"
                    now = datetime.now(timezone.utc)
                    event.published_at = now
                    # DDD-P3-05: Relay lag measurement
                    if event.created_at:
                        lag = (now - event.created_at).total_seconds()
                        metrics_registry.set_gauge("core_relay_lag_seconds", lag)
                    published += 1
                    metrics_registry.inc("core_event_outbox_published_total")
                except Exception as err:  # pragma: no cover - network/runtime branch
                    event.retry_count = (event.retry_count or 0) + 1
                    event.last_error = str(err)[:500]
                    if event.retry_count >= MAX_RETRY:
                        event.status = "DEAD_LETTER"
                        # DDD-P3-05: Persist to EventDeadLetter DB table
                        dl = EventDeadLetter(
                            original_event_id=event.id,
                            event_type=event.event_type,
                            aggregate_type=event.aggregate_type,
                            aggregate_id=event.aggregate_id,
                            payload=event.payload,
                            failure_reason=str(err)[:500],
                            retry_count=event.retry_count,
                            tenant_id=event.tenant_id,
                        )
                        session.add(dl)
                        logger.error(
                            "Event %s moved to DEAD_LETTER after %d retries: %s",
                            event.id, event.retry_count, err,
                        )
                    else:
                        event.status = "FAILED"
                    failed += 1
                    metrics_registry.inc("core_event_outbox_failed_total")
                    # Push to DLQ stream for external monitoring
                    try:
                        await redis.xadd(
                            "axiom:dlq:events",
                            {
                                **body,
                                "target_stream": stream,
                                "error": str(err),
                                "retry_count": str(event.retry_count),
                            },
                            maxlen=10000,
                            approximate=True,
                        )
                        metrics_registry.inc("core_dlq_messages_total")
                    except Exception:  # pragma: no cover
                        pass
            await session.commit()

            pending_count = await session.scalar(
                select(func.count()).select_from(EventOutbox).where(EventOutbox.status == "PENDING")
            )
            metrics_registry.set_gauge("core_event_outbox_pending", float(pending_count or 0))

            # DDD-P3-05: Track unresolved DLQ DB count
            dlq_db_count = await session.scalar(
                select(func.count()).select_from(EventDeadLetter).where(EventDeadLetter.resolved_at.is_(None))
            )
            metrics_registry.set_gauge("core_dlq_db_unresolved", float(dlq_db_count or 0))

        try:
            dlq_depth = await redis.xlen("axiom:dlq:events")
            metrics_registry.set_gauge("core_dlq_depth", float(dlq_depth))
        except Exception:  # pragma: no cover - network/runtime branch
            pass

        return {"published": published, "failed": failed}

    async def retry_failed_once(self, limit: int = 200) -> int:
        """Reset FAILED events to PENDING for re-processing.

        Events at or above MAX_RETRY are moved to DEAD_LETTER instead.
        """
        safe_limit = min(max(limit, 1), 5000)
        reset_count = 0
        dead_count = 0

        async with AsyncSessionLocal() as session:
            rows = await session.execute(
                select(EventOutbox)
                .where(EventOutbox.status == "FAILED")
                .order_by(EventOutbox.created_at.asc())
                .limit(safe_limit)
                .with_for_update(skip_locked=True)
            )
            events = rows.scalars().all()
            for event in events:
                if (event.retry_count or 0) >= MAX_RETRY:
                    event.status = "DEAD_LETTER"
                    dead_count += 1
                else:
                    event.status = "PENDING"
                    reset_count += 1
            await session.commit()

        if dead_count > 0:
            logger.warning("Moved %d events to DEAD_LETTER (exceeded MAX_RETRY=%d)", dead_count, MAX_RETRY)
        return reset_count

    async def reprocess_dlq_once(self, stream_name: str = "events", limit: int = 100) -> dict[str, int]:
        """Re-publish messages from the Dead Letter Queue stream."""
        safe_limit = min(max(limit, 1), 1000)
        redis = get_redis()
        dlq_key = f"axiom:dlq:{stream_name}"
        entries = await redis.xrange(dlq_key, min="-", max="+", count=safe_limit)

        success = 0
        failed = 0
        for entry_id, payload in entries:
            try:
                target_stream = payload.get("target_stream") or "axiom:events"
                msg = {
                    "event_id": payload.get("event_id", ""),
                    "event_type": payload.get("event_type", ""),
                    "aggregate_type": payload.get("aggregate_type", ""),
                    "aggregate_id": payload.get("aggregate_id", ""),
                    "tenant_id": payload.get("tenant_id", ""),
                    "payload": payload.get("payload", "{}"),
                }
                await redis.xadd(target_stream, msg, maxlen=10000, approximate=True)
                await redis.xdel(dlq_key, entry_id)
                success += 1
                metrics_registry.inc("core_dlq_reprocess_success_total")
            except Exception:  # pragma: no cover - network/runtime branch
                failed += 1
                metrics_registry.inc("core_dlq_reprocess_failed_total")

        depth = await redis.xlen(dlq_key)
        metrics_registry.set_gauge("core_dlq_depth", float(depth))
        return {"success": success, "failed": failed}

    async def run(self):
        logger.info(
            "Outbox Relay Worker started (poll=%ds, batch=%d, max_retry=%d)",
            self.poll_interval_seconds, self.max_batch, MAX_RETRY,
        )
        while self._running:
            try:
                await self.publish_pending_once(limit=self.max_batch)
            except Exception:  # pragma: no cover
                logger.exception("Outbox Relay Worker iteration failed")
            await asyncio.sleep(self.poll_interval_seconds)


if __name__ == "__main__":
    asyncio.run(SyncWorker().start())
