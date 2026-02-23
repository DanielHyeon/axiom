"""
OCR Worker (worker-system.md §3.3).
axiom:workers 스트림에서 WORKER_OCR_REQUEST 소비.
MinIO 다운로드 → Textract/GPT-4o Vision → documents 업데이트 → WORKER_OCR_COMPLETED.
현재: 소비·ACK 및 스텁 처리. 파이프라인 연동은 추후 구현.
"""
from __future__ import annotations

import asyncio
import json
import logging

from app.core.redis_client import get_redis
from app.workers.base import BaseWorker

logger = logging.getLogger("axiom.workers")

STREAM_KEY = "axiom:workers"
CONSUMER_GROUP = "ocr_group"
CONSUMER_NAME = "ocr_worker_1"
BLOCK_MS = 5000
EVENT_TYPE_REQUEST = "WORKER_OCR_REQUEST"
EVENT_TYPE_COMPLETED = "WORKER_OCR_COMPLETED"


class OcrWorker(BaseWorker):
    """WORKER_OCR_REQUEST 처리. MinIO·Vision·DB 연동은 추후 구현."""

    def __init__(self):
        super().__init__("ocr")

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
                        if data.get("event_type") == EVENT_TYPE_REQUEST:
                            await self.process_with_retry(
                                self._handle_request, entry_id, data
                            )
                        await redis.xack(STREAM_KEY, CONSUMER_GROUP, entry_id)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("OcrWorker error: %s", e)
                await asyncio.sleep(1)

    async def _handle_request(self, entry_id: str, data: dict) -> None:
        """WORKER_OCR_REQUEST 1건 처리. MinIO·Vision·DB 연동은 추후 구현."""
        payload_raw = data.get("payload", "{}")
        try:
            payload = json.loads(payload_raw) if isinstance(payload_raw, str) else (payload_raw or {})
        except json.JSONDecodeError:
            payload = {}
        doc_id = data.get("aggregate_id", "")
        # TODO: MinIO 다운로드 → Textract/GPT-4o Vision → documents 업데이트 → WORKER_OCR_COMPLETED 발행
        logger.info(
            "ocr_worker received WORKER_OCR_REQUEST aggregate_id=%s entry_id=%s (pipeline not yet implemented)",
            doc_id,
            entry_id,
        )


if __name__ == "__main__":
    asyncio.run(OcrWorker().start())
