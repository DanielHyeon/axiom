"""
EventLog Worker (worker-system.md §3.6).
axiom:workers 스트림에서 WORKER_EVENT_LOG_REQUEST 소비, 파싱/검증 후 Synapse 전달.
Consumer Group: event_log_group. 현재: 소비·ACK 및 스텁 처리 로직.
"""
from __future__ import annotations

import asyncio
import logging

from app.core.redis_client import get_redis
from app.workers.base import BaseWorker

logger = logging.getLogger("axiom.workers")

STREAM_KEY = "axiom:workers"
CONSUMER_GROUP = "event_log_group"
CONSUMER_NAME = "event_log_worker_1"
BLOCK_MS = 5000
EVENT_TYPE_REQUEST = "WORKER_EVENT_LOG_REQUEST"


class EventLogWorker(BaseWorker):
    """이벤트 로그 파싱/검증/스트리밍 Worker. MinIO·Synapse 연동은 추후 구현."""

    def __init__(self):
        super().__init__("event_log")

    async def run(self):
        redis = get_redis()
        try:
            await redis.xgroup_create(STREAM_KEY, CONSUMER_GROUP, id="0", mkstream=True)
        except Exception:
            pass

        while self._running:
            try:
                messages = await redis.xreadgroup(
                    groupname=CONSUMER_GROUP,
                    consumername=CONSUMER_NAME,
                    streams={STREAM_KEY: ">"},
                    count=1,
                    block=BLOCK_MS,
                )
                for _stream, entries in messages:
                    for entry_id, data in entries:
                        if data.get("event_type") == EVENT_TYPE_REQUEST:
                            await self.process_with_retry(self._process_event_log_request, entry_id, data)
                        await redis.xack(STREAM_KEY, CONSUMER_GROUP, entry_id)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("EventLogWorker error: %s", e)
                await asyncio.sleep(1)

    async def _process_event_log_request(self, entry_id: str, data: dict) -> None:
        """WORKER_EVENT_LOG_REQUEST 처리 (MinIO 다운로드·파싱·Synapse 전달은 추후 구현)."""
        aggregate_id = data.get("aggregate_id", "")
        logger.info(
            "event_log processed WORKER_EVENT_LOG_REQUEST aggregate_id=%s entry_id=%s",
            aggregate_id,
            entry_id,
        )


if __name__ == "__main__":
    asyncio.run(EventLogWorker().start())
