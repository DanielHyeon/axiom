"""Vision Transactional Outbox + Relay Worker (DDD-P3-01).

Vision 서비스에서 발행하는 도메인 이벤트를 PostgreSQL outbox 테이블에 기록하고,
Relay 워커가 Redis Streams(axiom:vision:events)로 발행한다.

DB 접속은 Vision이 이미 사용하는 psycopg2 + VISION_STATE_DATABASE_URL을 재활용한다.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import uuid
from typing import Any

from app.core.event_contract_registry import enforce_event_contract

logger = logging.getLogger("axiom.vision.outbox")

STREAM_KEY = "axiom:vision:events"
MAX_RETRY = 3
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


# ── psycopg2 lazy import ────────────────────────────────────────── #

def _import_psycopg2():
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        return psycopg2, RealDictCursor
    except Exception:
        for path in ("/usr/lib/python3/dist-packages",
                     os.path.expanduser("~/.local/lib/python3.12/site-packages")):
            if path not in sys.path:
                sys.path.insert(0, path)
        import psycopg2
        from psycopg2.extras import RealDictCursor
        return psycopg2, RealDictCursor


def _db_url() -> str:
    url = os.getenv(
        "VISION_STATE_DATABASE_URL",
        "postgresql://arkos:arkos@localhost:5432/insolvency_os",
    ).strip()
    if url.startswith("postgresql+asyncpg://"):
        return "postgresql://" + url[len("postgresql+asyncpg://"):]
    return url


# ── DDL: vision.event_outbox ────────────────────────────────────── #

_DDL = """\
CREATE SCHEMA IF NOT EXISTS vision;
CREATE TABLE IF NOT EXISTS vision.event_outbox (
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
CREATE INDEX IF NOT EXISTS idx_vision_outbox_pending
    ON vision.event_outbox (created_at) WHERE status = 'PENDING';
"""


def ensure_outbox_table() -> None:
    """서비스 시작 시 vision.event_outbox 테이블 보장."""
    psycopg2, _ = _import_psycopg2()
    try:
        with psycopg2.connect(_db_url()) as conn:
            cur = conn.cursor()
            cur.execute(_DDL)
            cur.close()
            conn.commit()
        logger.info("vision.event_outbox table ensured")
    except Exception:
        logger.warning("vision.event_outbox DDL failed (PG may be unavailable)", exc_info=True)


# ── EventPublisher ──────────────────────────────────────────────── #

class EventPublisher:
    """Outbox 테이블에 이벤트를 INSERT한다."""

    @staticmethod
    def publish(
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        payload: dict[str, Any],
        tenant_id: str = "",
        conn=None,
    ) -> str:
        safe_payload = enforce_event_contract(event_type, payload, aggregate_id)

        event_id = str(uuid.uuid4())
        psycopg2, _ = _import_psycopg2()
        own_conn = conn is None
        if own_conn:
            conn = psycopg2.connect(_db_url())

        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO vision.event_outbox
                    (id, event_type, aggregate_type, aggregate_id, payload, status, tenant_id)
                VALUES (%s, %s, %s, %s, %s, 'PENDING', %s)
                """,
                (event_id, event_type, aggregate_type, aggregate_id,
                 json.dumps(safe_payload, ensure_ascii=False), tenant_id),
            )
            cur.close()
            if own_conn:
                conn.commit()
        finally:
            if own_conn:
                conn.close()
        return event_id


# ── Relay Worker ────────────────────────────────────────────────── #

class VisionRelayWorker:
    """vision.event_outbox → axiom:vision:events Redis Stream 발행 워커."""

    def __init__(self, poll_interval: int = 5, max_batch: int = 100):
        self._poll = poll_interval
        self._batch = max_batch
        self._running = True

    async def run(self) -> None:
        logger.info("VisionRelayWorker started (poll=%ds, batch=%d)", self._poll, self._batch)
        while self._running:
            try:
                await self._publish_once()
            except Exception:
                logger.exception("VisionRelayWorker iteration failed")
            await asyncio.sleep(self._poll)

    async def _publish_once(self) -> dict[str, int]:
        import redis.asyncio as aioredis
        r = aioredis.from_url(REDIS_URL, decode_responses=True)

        psycopg2, RealDictCursor = _import_psycopg2()
        published = 0
        failed = 0

        try:
            with psycopg2.connect(_db_url()) as conn:
                cur = conn.cursor(cursor_factory=RealDictCursor)
                cur.execute(
                    """
                    SELECT * FROM vision.event_outbox
                    WHERE status = 'PENDING'
                    ORDER BY created_at ASC
                    LIMIT %s
                    FOR UPDATE SKIP LOCKED
                    """,
                    (self._batch,),
                )
                rows = cur.fetchall()

                for row in rows:
                    body = {
                        "event_id": row["id"],
                        "event_type": row["event_type"],
                        "aggregate_type": row["aggregate_type"],
                        "aggregate_id": row["aggregate_id"],
                        "tenant_id": row["tenant_id"] or "",
                        "payload": row["payload"] if isinstance(row["payload"], str) else json.dumps(row["payload"], ensure_ascii=True),
                    }
                    try:
                        await r.xadd(STREAM_KEY, body, maxlen=10000, approximate=True)
                        cur.execute(
                            "UPDATE vision.event_outbox SET status='PUBLISHED', published_at=now() WHERE id=%s",
                            (row["id"],),
                        )
                        published += 1
                    except Exception as err:
                        retry = (row["retry_count"] or 0) + 1
                        new_status = "DEAD_LETTER" if retry >= MAX_RETRY else "FAILED"
                        cur.execute(
                            "UPDATE vision.event_outbox SET status=%s, retry_count=%s, last_error=%s WHERE id=%s",
                            (new_status, retry, str(err)[:500], row["id"]),
                        )
                        failed += 1
                cur.close()
                conn.commit()
        finally:
            await r.aclose()

        return {"published": published, "failed": failed}

    def shutdown(self) -> None:
        self._running = False


event_publisher = EventPublisher()
