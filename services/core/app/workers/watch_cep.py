"""
Watch CEP Worker (worker-system.md §3.2).
axiom:watches 스트림 소비, CEP 룰 평가 및 알림 생성·발송.
Consumer Group: watch_cep_group. 현재: 소비·ACK 및 스텁 처리 로직.
"""
from __future__ import annotations

import asyncio
import logging

from app.core.redis_client import get_redis
from app.workers.base import BaseWorker

logger = logging.getLogger("axiom.workers")

STREAM_KEY = "axiom:watches"
CONSUMER_GROUP = "watch_cep_group"
CONSUMER_NAME = "watch_cep_worker_1"
BLOCK_MS = 5000


class WatchCepWorker(BaseWorker):
    """axiom:watches 소비, CEP 평가·알림 발송(실제 발송은 추후 연동)."""

    def __init__(self):
        super().__init__("watch_cep")

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
                    count=10,
                    block=BLOCK_MS,
                )
                for _stream, entries in messages:
                    for entry_id, data in entries:
                        await self.process_with_retry(self._handle_message, entry_id, data)
                        await redis.xack(STREAM_KEY, CONSUMER_GROUP, entry_id)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("WatchCepWorker error: %s", e)
                await asyncio.sleep(1)

    async def _handle_message(self, entry_id: str, data: dict) -> None:
        """메시지 1건 처리 (CEP 평가·알림 로직은 추후 구현)."""
        event_type = data.get("event_type", "")
        aggregate_id = data.get("aggregate_id", "")
        logger.info(
            "watch_cep consumed event_type=%s aggregate_id=%s entry_id=%s",
            event_type,
            aggregate_id,
            entry_id,
        )


if __name__ == "__main__":
    asyncio.run(WatchCepWorker().start())
