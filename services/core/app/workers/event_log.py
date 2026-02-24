"""
EventLog Worker (worker-system.md §3.6).
axiom:workers 스트림에서 WORKER_EVENT_LOG_REQUEST 소비, MinIO 다운로드·검증·Synapse 전달·진행률 발행.
Consumer Group: event_log_group.
"""
from __future__ import annotations

import asyncio
import json
import logging
from minio import Minio

from app.core.config import settings
from app.core.redis_client import get_redis
from app.infrastructure.external.synapse_acl import SynapseACLError, synapse_acl
from app.workers.base import BaseWorker
from app.workers.event_log_parsers import (
    validate_csv,
    validate_xes,
    parse_csv_chunks,
    parse_xes_chunks,
    ValidationResult,
)

logger = logging.getLogger("axiom.workers")

STREAM_KEY = "axiom:workers"
CONSUMER_GROUP = "event_log_group"
CONSUMER_NAME = "event_log_worker_1"
BLOCK_MS = 5000
EVENT_TYPE_REQUEST = "WORKER_EVENT_LOG_REQUEST"
STREAM_PROGRESS = "axiom:process_mining"
CHUNK_SIZE = 10_000


def _minio_client() -> Minio:
    return Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
    )


async def _download_from_minio(file_path: str) -> bytes:
    """MinIO에서 객체 다운로드. file_path는 버킷 내 객체 키."""
    client = _minio_client()
    bucket = settings.MINIO_BUCKET
    # file_path가 "bucket/key" 형태면 분리
    if "/" in file_path and not file_path.startswith("/"):
        parts = file_path.split("/", 1)
        if len(parts) == 2 and parts[0] and parts[1]:
            bucket, file_path = parts[0], parts[1]
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: client.get_object(bucket, file_path),
    )
    try:
        data = await loop.run_in_executor(None, response.read)
        return data
    finally:
        response.close()
        response.release_conn()


class EventLogWorker(BaseWorker):
    """이벤트 로그 파싱/검증 후 Synapse ingest API로 전달, 진행률·완료 이벤트 발행."""

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
                            await self.process_with_retry(
                                self._process_event_log_request, entry_id, data
                            )
                        await redis.xack(STREAM_KEY, CONSUMER_GROUP, entry_id)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("EventLogWorker error: %s", e)
                await asyncio.sleep(1)

    async def _process_event_log_request(self, entry_id: str, data: dict) -> None:
        """WORKER_EVENT_LOG_REQUEST: MinIO 다운로드 → 검증 → Synapse 전달 → 진행률/완료 발행."""
        event_log_id = data.get("aggregate_id", "")
        tenant_id = (data.get("tenant_id") or "default").strip()
        payload_raw = data.get("payload", "{}")
        try:
            payload = json.loads(payload_raw) if isinstance(payload_raw, str) else (payload_raw or {})
        except json.JSONDecodeError:
            payload = {}

        file_path = payload.get("file_path")
        file_format = (payload.get("format") or "CSV").upper()
        case_id = payload.get("case_id") or ""
        name = payload.get("name") or f"event-log-{event_log_id}"
        estimated_total = payload.get("estimated_total")
        column_mapping = payload.get("column_mapping") or {}

        if not file_path:
            logger.warning("event_log missing file_path aggregate_id=%s", event_log_id)
            return

        # 1. MinIO 다운로드
        try:
            file_bytes = await _download_from_minio(file_path)
        except Exception as e:
            logger.exception("event_log MinIO download failed path=%s: %s", file_path, e)
            await self._report_failure(event_log_id, [f"MinIO download failed: {e}"])
            return

        # 2. 형식 검증
        if file_format == "XES":
            validation = validate_xes(file_bytes)
        else:
            validation = validate_csv(file_bytes)

        if not validation.is_valid:
            await self._report_failure(event_log_id, validation.errors)
            return

        # 3. Synapse ingest (multipart: metadata + file)
        ingest_metadata = {
            "source_type": "csv" if file_format == "CSV" else "xes",
            "case_id": case_id,
            "name": name,
            "column_mapping": column_mapping,
        }
        try:
            await self._report_progress(event_log_id, 0, estimated_total)
            # Synapse API: multipart/form-data with "metadata" (JSON) and "file" (bytes)
            boundary = "----CoreEventLogBoundary"
            body = (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="metadata"\r\n\r\n'
                f"{json.dumps(ingest_metadata, ensure_ascii=False)}\r\n"
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="file"; filename="upload"\r\n\r\n'
            ).encode("utf-8") + file_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")
            # ACL을 통한 Synapse 호출 (tenant 헤더)
            await synapse_acl.ingest_event_log(
                tenant_id=tenant_id,
                raw_body=body,
                content_type=f"multipart/form-data; boundary={boundary}",
                timeout=300.0,
            )
        except SynapseACLError as e:
            logger.exception("event_log Synapse ingest failed: %s", e.detail)
            await self._report_failure(event_log_id, [f"Synapse ingest failed: {e.status_code}"])
            return

        # 4. 진행률·완료 발행
        total_events = _count_events_for_format(file_bytes, file_format, column_mapping)
        await self._report_progress(event_log_id, total_events, estimated_total)
        await self._publish_completion(event_log_id, total_events)

        logger.info(
            "event_log processed WORKER_EVENT_LOG_REQUEST aggregate_id=%s entry_id=%s",
            event_log_id,
            entry_id,
        )

    async def _report_failure(self, event_log_id: str, errors: list[str]) -> None:
        redis = get_redis()
        await redis.xadd(
            STREAM_PROGRESS,
            {
                "event_type": "MINING_ERROR",
                "event_log_id": event_log_id,
                "error": "| ".join(errors[:5]),
            },
            maxlen=10000,
            approximate=True,
        )

    async def _report_progress(
        self, event_log_id: str, processed: int, total: int | None
    ) -> None:
        redis = get_redis()
        progress = (processed / total * 100) if total else (100 if processed else 0)
        await redis.xadd(
            STREAM_PROGRESS,
            {
                "event_type": "MINING_PROGRESS",
                "event_log_id": event_log_id,
                "processed_events": str(processed),
                "progress_percent": f"{progress:.1f}",
            },
            maxlen=10000,
            approximate=True,
        )

    async def _publish_completion(self, event_log_id: str, total_events: int) -> None:
        redis = get_redis()
        await redis.xadd(
            STREAM_PROGRESS,
            {
                "event_type": "PROCESS_LOG_INGESTED",
                "event_log_id": event_log_id,
                "total_events": str(total_events),
            },
            maxlen=10000,
            approximate=True,
        )


def _count_events_for_format(
    content: bytes, file_format: str, column_mapping: dict
) -> int:
    """대략적 이벤트 수 (진행률/완료 메시지용)."""
    if file_format == "XES":
        return sum(len(c) for c in parse_xes_chunks(content, CHUNK_SIZE))
    return sum(
        len(chunk)
        for chunk in parse_csv_chunks(content, CHUNK_SIZE, column_mapping)
    )
