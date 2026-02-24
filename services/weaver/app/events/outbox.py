"""Weaver Transactional Outbox + Relay Worker (DDD-P3-01).

Weaver 서비스에서 발행하는 도메인 이벤트를 PostgreSQL outbox 테이블에 기록하고,
Relay 워커가 Redis Streams(axiom:weaver:events)로 발행한다.

DB 접속은 Weaver가 이미 사용하는 asyncpg + POSTGRES_DSN을 재활용한다.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

from app.core.config import settings
from app.core.event_contract_registry import enforce_event_contract

logger = logging.getLogger("axiom.weaver.outbox")

STREAM_KEY = "axiom:weaver:events"
MAX_RETRY = 3


# ── DDL: weaver.event_outbox ────────────────────────────────────── #

_DDL = """\
CREATE SCHEMA IF NOT EXISTS weaver;
CREATE TABLE IF NOT EXISTS weaver.event_outbox (
    id              VARCHAR PRIMARY KEY,
    event_type      VARCHAR NOT NULL,
    aggregate_type  VARCHAR NOT NULL,
    aggregate_id    VARCHAR NOT NULL,
    payload         JSONB   NOT NULL,
    status          VARCHAR NOT NULL DEFAULT 'PENDING',
    tenant_id       VARCHAR NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at    TIMESTAMPTZ,
    retry_count     INTEGER NOT NULL DEFAULT 0,
    last_error      TEXT
);
CREATE INDEX IF NOT EXISTS idx_weaver_outbox_pending
    ON weaver.event_outbox (created_at) WHERE status = 'PENDING';
"""

_pool = None


async def _get_pool():
    global _pool
    if _pool is not None:
        return _pool
    dsn = settings.postgres_dsn
    if not dsn:
        raise RuntimeError("POSTGRES_DSN is required for Weaver outbox")
    import asyncpg
    _pool = await asyncpg.create_pool(
        dsn=dsn, min_size=1, max_size=3,
        server_settings={"search_path": "weaver,public"},
    )
    return _pool


async def ensure_outbox_table() -> None:
    """서비스 시작 시 weaver.event_outbox 테이블 보장."""
    try:
        pool = await _get_pool()
        async with pool.acquire() as conn:
            await conn.execute(_DDL)
        logger.info("weaver.event_outbox table ensured")
    except Exception:
        logger.warning("weaver.event_outbox DDL failed (PG may be unavailable)", exc_info=True)


# ── EventPublisher (async — asyncpg) ───────────────────────────── #

class EventPublisher:
    """Outbox 테이블에 이벤트를 INSERT한다."""

    @staticmethod
    async def publish(
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        payload: dict[str, Any],
        tenant_id: str = "",
        conn=None,
    ) -> str:
        safe_payload = enforce_event_contract(event_type, payload, aggregate_id)

        event_id = str(uuid.uuid4())
        own_conn = conn is None
        pool = await _get_pool()
        if own_conn:
            conn = await pool.acquire()

        try:
            await conn.execute(
                """
                INSERT INTO weaver.event_outbox
                    (id, event_type, aggregate_type, aggregate_id, payload, status, tenant_id)
                VALUES ($1, $2, $3, $4, $5::jsonb, 'PENDING', $6)
                """,
                event_id, event_type, aggregate_type, aggregate_id,
                json.dumps(safe_payload, ensure_ascii=False), tenant_id,
            )
        finally:
            if own_conn:
                await pool.release(conn)
        return event_id


# ── Relay Worker ────────────────────────────────────────────────── #

class WeaverRelayWorker:
    """weaver.event_outbox → axiom:weaver:events Redis Stream 발행 워커."""

    def __init__(self, poll_interval: int = 5, max_batch: int = 100):
        self._poll = poll_interval
        self._batch = max_batch
        self._running = True

    async def run(self) -> None:
        logger.info("WeaverRelayWorker started (poll=%ds, batch=%d)", self._poll, self._batch)
        while self._running:
            try:
                await self._publish_once()
            except Exception:
                logger.exception("WeaverRelayWorker iteration failed")
            await asyncio.sleep(self._poll)

    async def _publish_once(self) -> dict[str, int]:
        import redis.asyncio as aioredis
        redis_url = settings.redis_url
        if not redis_url:
            return {"published": 0, "failed": 0}
        r = aioredis.from_url(redis_url, decode_responses=True)

        pool = await _get_pool()
        published = 0
        failed = 0

        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT * FROM weaver.event_outbox
                    WHERE status = 'PENDING'
                    ORDER BY created_at ASC
                    LIMIT $1
                    FOR UPDATE SKIP LOCKED
                    """,
                    self._batch,
                )

                for row in rows:
                    payload_val = row["payload"]
                    if not isinstance(payload_val, str):
                        payload_val = json.dumps(payload_val, ensure_ascii=True)
                    body = {
                        "event_id": row["id"],
                        "event_type": row["event_type"],
                        "aggregate_type": row["aggregate_type"],
                        "aggregate_id": row["aggregate_id"],
                        "tenant_id": row["tenant_id"] or "",
                        "payload": payload_val,
                    }
                    try:
                        await r.xadd(STREAM_KEY, body, maxlen=10000, approximate=True)
                        await conn.execute(
                            "UPDATE weaver.event_outbox SET status='PUBLISHED', published_at=now() WHERE id=$1",
                            row["id"],
                        )
                        published += 1
                    except Exception as err:
                        retry = (row["retry_count"] or 0) + 1
                        new_status = "DEAD_LETTER" if retry >= MAX_RETRY else "FAILED"
                        await conn.execute(
                            "UPDATE weaver.event_outbox SET status=$1, retry_count=$2, last_error=$3 WHERE id=$4",
                            new_status, retry, str(err)[:500], row["id"],
                        )
                        failed += 1
        finally:
            await r.aclose()

        return {"published": published, "failed": failed}

    def shutdown(self) -> None:
        self._running = False


event_publisher = EventPublisher()
