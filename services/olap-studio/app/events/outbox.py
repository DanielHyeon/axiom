"""OLAP Studio Transactional Outbox + Relay Worker.

OLAP Studio 서비스에서 발행하는 도메인 이벤트를 PostgreSQL olap.outbox_events 테이블에
기록하고, Relay 워커가 Redis Streams(axiom:olap-studio:events)로 발행한다.

DB 접속은 OLAP Studio가 이미 사용하는 asyncpg 풀을 재활용한다.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog

logger = structlog.get_logger("axiom.olap_studio.outbox")

# Redis Stream 키 — 서비스별 고유 스트림
STREAM_KEY = "axiom:olap-studio:events"

# 최대 재시도 횟수 — 초과 시 DEAD_LETTER로 이동
MAX_RETRY = 3


# ── DDL: olap.outbox_events ─────────────────────────────────────── #

_DDL = """\
CREATE TABLE IF NOT EXISTS olap.outbox_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL,
    project_id      UUID NOT NULL,
    aggregate_type  VARCHAR(50) NOT NULL,
    aggregate_id    UUID NOT NULL,
    event_type      VARCHAR(100) NOT NULL,
    event_version   VARCHAR(10) NOT NULL DEFAULT '1.0',
    payload         JSONB NOT NULL,
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at    TIMESTAMPTZ,
    publish_status  VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    retry_count     INTEGER NOT NULL DEFAULT 0,
    last_error      TEXT
);
CREATE INDEX IF NOT EXISTS idx_olap_outbox_pending
    ON olap.outbox_events (publish_status, occurred_at) WHERE publish_status = 'PENDING';
"""


async def ensure_outbox_table() -> None:
    """서비스 시작 시 olap.outbox_events 테이블 존재를 보장한다.

    olap 스키마는 이미 존재한다고 가정한다 (다른 DDL에서 생성).
    테이블이 없으면 생성하고, 이미 있으면 무시한다.
    """
    from app.core.database import get_pool

    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            # olap 스키마가 없을 수도 있으니 먼저 보장
            await conn.execute("CREATE SCHEMA IF NOT EXISTS olap")
            await conn.execute(_DDL)
        logger.info("olap.outbox_events 테이블 보장 완료")
    except Exception:
        logger.warning(
            "olap.outbox_events DDL 실패 — PostgreSQL 연결 불가 가능성",
            exc_info=True,
        )


# ── publish_event — Outbox INSERT ─────────────────────────────── #

async def publish_event(
    tenant_id: str,
    project_id: str,
    aggregate_type: str,
    aggregate_id: str,
    event_type: str,
    payload: dict[str, Any],
    conn=None,
) -> str:
    """Outbox 테이블에 이벤트를 INSERT한다.

    conn이 전달되면 호출부의 트랜잭션에 포함되어 원자적으로 커밋된다.
    conn이 None이면 풀에서 독립 커넥션을 가져와 즉시 실행한다.

    반환값: 생성된 event_id (UUID 문자열)
    """
    from app.core.database import get_pool

    event_id = str(uuid.uuid4())
    payload_json = json.dumps(payload, ensure_ascii=False)

    sql = """
        INSERT INTO olap.outbox_events
            (id, event_type, aggregate_type, aggregate_id, tenant_id, project_id, payload, publish_status)
        VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, 'PENDING')
    """
    params = (event_id, event_type, aggregate_type, aggregate_id, tenant_id, project_id, payload_json)

    if conn is not None:
        # 외부 트랜잭션에 참여 — 커밋은 호출부 책임
        await conn.execute(sql, *params)
    else:
        # 독립 커넥션에서 즉시 실행
        pool = await get_pool()
        async with pool.acquire() as auto_conn:
            await auto_conn.execute(sql, *params)

    logger.info(
        "outbox_event_inserted",
        event_id=event_id,
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
    )
    return event_id


# ── Redis 클라이언트 헬퍼 ─────────────────────────────────────── #

_redis_client = None
_redis_init_attempted = False


async def _get_redis():
    """Redis 클라이언트를 lazy 초기화하여 반환한다.

    REDIS_URL이 비어있거나 연결 실패 시 None을 반환한다.
    서비스 장애로 이어지지 않도록 예외를 삼킨다.
    """
    global _redis_client, _redis_init_attempted

    if _redis_client is not None:
        return _redis_client
    if _redis_init_attempted:
        return None

    _redis_init_attempted = True
    from app.core.config import settings

    if not settings.REDIS_URL:
        logger.warning("REDIS_URL 미설정 — Relay Worker가 이벤트를 발행하지 못합니다")
        return None

    try:
        import redis.asyncio as aioredis

        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
        )
        # 연결 테스트
        await _redis_client.ping()
        logger.info("Redis 연결 성공", url=settings.REDIS_URL)
        return _redis_client
    except Exception:
        logger.warning("Redis 연결 실패 — Relay Worker 비활성화", exc_info=True)
        _redis_client = None
        return None


async def close_redis() -> None:
    """Redis 클라이언트를 정리한다."""
    global _redis_client, _redis_init_attempted
    if _redis_client is not None:
        try:
            await _redis_client.aclose()
        except Exception:
            pass
        _redis_client = None
    _redis_init_attempted = False


# ── OlapRelayWorker — Outbox → Redis Stream 발행 ──────────────── #

class OlapRelayWorker:
    """olap.outbox_events → axiom:olap-studio:events Redis Stream 발행 워커.

    주기적으로 PENDING 상태의 이벤트를 폴링하여 Redis Streams로 발행하고,
    성공 시 PUBLISHED, 실패 시 FAILED 또는 DEAD_LETTER로 상태를 갱신한다.

    SELECT ... FOR UPDATE SKIP LOCKED로 다중 인스턴스 환경에서
    동일 이벤트를 중복 처리하지 않도록 보장한다.
    """

    def __init__(self, poll_interval: int = 5, max_batch: int = 100):
        self._poll = poll_interval
        self._batch = max_batch
        self._running = True

    async def run(self) -> None:
        """워커 메인 루프 — shutdown() 호출 시까지 반복한다."""
        logger.info(
            "OlapRelayWorker 시작",
            poll_interval=self._poll,
            max_batch=self._batch,
        )
        while self._running:
            try:
                result = await self._publish_once()
                if result["published"] > 0 or result["failed"] > 0:
                    logger.info("relay_batch_complete", **result)
            except Exception:
                logger.exception("OlapRelayWorker 반복 실패")
            await asyncio.sleep(self._poll)

    async def _publish_once(self) -> dict[str, int]:
        """PENDING 이벤트를 한 배치 가져와 Redis Stream으로 발행한다."""
        redis = await _get_redis()
        if redis is None:
            return {"published": 0, "failed": 0}

        from app.core.database import get_pool

        pool = await get_pool()
        published = 0
        failed = 0

        async with pool.acquire() as conn:
            # 트랜잭션 내에서 FOR UPDATE SKIP LOCKED로 경합 방지
            async with conn.transaction():
                rows = await conn.fetch(
                    """
                    SELECT id, event_type, aggregate_type, aggregate_id,
                           tenant_id, project_id, payload, retry_count
                    FROM olap.outbox_events
                    WHERE publish_status = 'PENDING'
                    ORDER BY created_at ASC
                    LIMIT $1
                    FOR UPDATE SKIP LOCKED
                    """,
                    self._batch,
                )

                for row in rows:
                    # Redis Stream 메시지 본문 구성
                    body = {
                        "event_id": row["id"],
                        "event_type": row["event_type"],
                        "aggregate_type": row["aggregate_type"],
                        "aggregate_id": row["aggregate_id"],
                        "tenant_id": row["tenant_id"] or "",
                        "project_id": row["project_id"] or "",
                        "payload": (
                            row["payload"]
                            if isinstance(row["payload"], str)
                            else json.dumps(row["payload"], ensure_ascii=False)
                        ),
                    }
                    try:
                        # Redis Stream에 추가 — maxlen으로 무한 증가 방지
                        await redis.xadd(
                            STREAM_KEY, body, maxlen=10000, approximate=True,
                        )
                        # 발행 성공 → PUBLISHED 상태로 전환
                        await conn.execute(
                            """UPDATE olap.outbox_events
                            SET publish_status = 'PUBLISHED', published_at = now()
                            WHERE id = $1""",
                            row["id"],
                        )
                        published += 1
                    except Exception as err:
                        # 발행 실패 → 재시도 횟수 증가, 초과 시 DEAD_LETTER
                        retry = (row["retry_count"] or 0) + 1
                        new_status = "DEAD_LETTER" if retry >= MAX_RETRY else "FAILED"
                        await conn.execute(
                            """UPDATE olap.outbox_events
                            SET publish_status = $1, retry_count = $2, last_error = $3
                            WHERE id = $4""",
                            new_status,
                            retry,
                            str(err)[:500],
                            row["id"],
                        )
                        failed += 1
                        logger.warning(
                            "relay_publish_failed",
                            event_id=row["id"],
                            retry=retry,
                            error=str(err)[:200],
                        )

        return {"published": published, "failed": failed}

    def shutdown(self) -> None:
        """워커 종료 신호 — 다음 폴링 주기에서 루프가 멈춘다."""
        self._running = False
        logger.info("OlapRelayWorker 종료 신호 수신")
