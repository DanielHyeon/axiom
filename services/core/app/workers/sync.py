from __future__ import annotations

import asyncio
import json
from typing import Any

from sqlalchemy import func, select

from app.core.observability import metrics_registry
from app.core.redis_client import get_redis
from app.core.database import AsyncSessionLocal
from app.models.base_models import EventOutbox
from app.workers.base import BaseWorker


class SyncWorker(BaseWorker):
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
        return "axiom:events"

    async def publish_pending_once(self, limit: int | None = None) -> dict[str, int]:
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
                    published += 1
                    metrics_registry.inc("core_event_outbox_published_total")
                except Exception as err:  # pragma: no cover - network/runtime branch
                    event.status = "FAILED"
                    failed += 1
                    metrics_registry.inc("core_event_outbox_failed_total")
                    metrics_registry.inc("core_dlq_messages_total")
                    await redis.xadd(
                        "axiom:dlq:events",
                        {
                            **body,
                            "target_stream": stream,
                            "error": str(err),
                        },
                        maxlen=10000,
                        approximate=True,
                    )
            await session.commit()

            pending_count = await session.scalar(
                select(func.count()).select_from(EventOutbox).where(EventOutbox.status == "PENDING")
            )
            metrics_registry.set_gauge("core_event_outbox_pending", float(pending_count or 0))

        try:
            dlq_depth = await redis.xlen("axiom:dlq:events")
            metrics_registry.set_gauge("core_dlq_depth", float(dlq_depth))
        except Exception:  # pragma: no cover - network/runtime branch
            pass

        return {"published": published, "failed": failed}

    async def retry_failed_once(self, limit: int = 200) -> int:
        safe_limit = min(max(limit, 1), 5000)
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
                event.status = "PENDING"
            await session.commit()
            return len(events)

    async def reprocess_dlq_once(self, stream_name: str = "events", limit: int = 100) -> dict[str, int]:
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
        while self._running:
            await self.publish_pending_once(limit=self.max_batch)
            await asyncio.sleep(self.poll_interval_seconds)


if __name__ == "__main__":
    asyncio.run(SyncWorker().start())
