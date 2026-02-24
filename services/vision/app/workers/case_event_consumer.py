"""
CaseEventConsumer — Vision CQRS 읽기 모델 갱신 워커 (DDD-P2-03).

Core BC가 Outbox Relay를 통해 ``axiom:events`` Redis Stream에 발행하는
케이스/프로세스 도메인 이벤트를 소비하여 ``vision.case_summary`` 읽기 모델을
갱신한다.

Consumer Group: vision_analytics_group
Handled events:
    - PROCESS_INITIATED → total_cases += 1, active_cases += 1
    - WORKITEM_COMPLETED → active_cases -= 1, completed_cases += 1, 평균 완료일 갱신
    - SAGA_COMPENSATION_COMPLETED → active_cases -= 1, cancelled_cases += 1
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

logger = logging.getLogger("axiom.vision.case_event_consumer")

STREAM_KEY = "axiom:core:events"
CONSUMER_GROUP = "vision_analytics_group"
CONSUMER_NAME = os.getenv("VISION_CONSUMER_NAME", "vision-1")
BLOCK_MS = 5000
BATCH_SIZE = 10

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


def _import_redis():
    """redis.asyncio lazy import (선택 의존성)."""
    import redis.asyncio as aioredis
    return aioredis


def _import_psycopg2():
    """psycopg2 lazy import (Vision 표준 패턴)."""
    import sys
    try:
        import psycopg2
        return psycopg2
    except ImportError:
        for _path in ("/usr/lib/python3/dist-packages",
                       os.path.expanduser("~/.local/lib/python3.12/site-packages")):
            if _path not in sys.path:
                sys.path.insert(0, _path)
        import psycopg2
        return psycopg2


def _database_url() -> str:
    url = os.getenv(
        "VISION_STATE_DATABASE_URL",
        "postgresql://arkos:arkos@localhost:5432/insolvency_os",
    ).strip()
    if url.startswith("postgresql+asyncpg://"):
        return "postgresql://" + url[len("postgresql+asyncpg://"):]
    return url


class CaseEventConsumer:
    """Core BC의 케이스/프로세스 이벤트를 소비하여 Vision 읽기 모델을 갱신한다."""

    STREAM = STREAM_KEY
    GROUP = CONSUMER_GROUP

    def __init__(
        self,
        redis_url: str | None = None,
        database_url: str | None = None,
    ) -> None:
        self._redis_url = redis_url or REDIS_URL
        self._database_url = database_url or _database_url()
        self._redis = None
        self._running = True

    # ──────────────── lifecycle ──────────────── #

    async def start(self) -> None:
        """Redis 연결 + Consumer Group 생성 후 이벤트 루프 진입."""
        aioredis = _import_redis()
        self._redis = aioredis.from_url(self._redis_url, decode_responses=True)

        # Consumer Group이 없으면 생성 (이미 존재하면 무시)
        try:
            await self._redis.xgroup_create(
                self.STREAM, self.GROUP, id="0", mkstream=True,
            )
            logger.info("Created consumer group %s on %s", self.GROUP, self.STREAM)
        except Exception:
            # BUSYGROUP — 이미 존재
            pass

        # 읽기 모델 테이블 보장
        self._ensure_table()

        logger.info(
            "CaseEventConsumer started (stream=%s, group=%s, consumer=%s)",
            self.STREAM, self.GROUP, CONSUMER_NAME,
        )
        await self.run()

    def shutdown(self) -> None:
        self._running = False

    async def run(self) -> None:
        """메인 이벤트 소비 루프."""
        while self._running:
            try:
                messages = await self._redis.xreadgroup(
                    groupname=self.GROUP,
                    consumername=CONSUMER_NAME,
                    streams={self.STREAM: ">"},
                    count=BATCH_SIZE,
                    block=BLOCK_MS,
                )
                for _stream, entries in messages:
                    for msg_id, data in entries:
                        try:
                            await self._handle_event(data)
                        except Exception:
                            logger.exception(
                                "Failed to handle event %s: %s", msg_id, data,
                            )
                        await self._redis.xack(self.STREAM, self.GROUP, msg_id)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("CaseEventConsumer iteration error")
                await asyncio.sleep(1)

    # ──────────────── event handling ──────────────── #

    async def _handle_event(self, data: dict[str, Any]) -> None:
        event_type = data.get("event_type", "")
        tenant_id = data.get("tenant_id", "")

        if not tenant_id:
            return

        if event_type == "PROCESS_INITIATED":
            self._increment_total(tenant_id)
        elif event_type == "WORKITEM_COMPLETED":
            self._update_completion_stats(tenant_id, data)
        elif event_type == "SAGA_COMPENSATION_COMPLETED":
            self._increment_cancelled(tenant_id)

    # ──────────────── DB mutations (sync psycopg2) ──────────────── #

    def _conn(self):
        psycopg2 = _import_psycopg2()
        conn = psycopg2.connect(self._database_url)
        cur = conn.cursor()
        cur.execute("SET search_path TO vision, public")
        cur.close()
        return conn

    def _ensure_table(self) -> None:
        """case_summary 테이블이 없으면 생성."""
        try:
            with self._conn() as conn:
                cur = conn.cursor()
                cur.execute("CREATE SCHEMA IF NOT EXISTS vision")
                conn.commit()
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS case_summary (
                        tenant_id VARCHAR NOT NULL,
                        total_cases INTEGER NOT NULL DEFAULT 0,
                        active_cases INTEGER NOT NULL DEFAULT 0,
                        completed_cases INTEGER NOT NULL DEFAULT 0,
                        cancelled_cases INTEGER NOT NULL DEFAULT 0,
                        avg_completion_days FLOAT,
                        last_updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        PRIMARY KEY (tenant_id)
                    )
                """)
                cur.close()
                conn.commit()
        except Exception:
            logger.warning("case_summary table ensure failed (may not have PG)", exc_info=True)

    def _increment_total(self, tenant_id: str) -> None:
        """PROCESS_INITIATED: total_cases += 1, active_cases += 1."""
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO case_summary (tenant_id, total_cases, active_cases, last_updated_at)
                VALUES (%s, 1, 1, now())
                ON CONFLICT (tenant_id) DO UPDATE SET
                    total_cases = case_summary.total_cases + 1,
                    active_cases = case_summary.active_cases + 1,
                    last_updated_at = now()
                """,
                (tenant_id,),
            )
            cur.close()
            conn.commit()

    def _update_completion_stats(self, tenant_id: str, data: dict[str, Any]) -> None:
        """WORKITEM_COMPLETED: active_cases -= 1, completed_cases += 1, 평균 완료일 갱신."""
        # payload에서 completion_days 추출 (있으면)
        payload_raw = data.get("payload", "{}")
        try:
            payload = json.loads(payload_raw) if isinstance(payload_raw, str) else (payload_raw or {})
        except (json.JSONDecodeError, TypeError):
            payload = {}

        completion_days = payload.get("completion_days")

        with self._conn() as conn:
            cur = conn.cursor()
            if completion_days is not None:
                # 이동평균: new_avg = (old_avg * completed + new_days) / (completed + 1)
                cur.execute(
                    """
                    INSERT INTO case_summary
                        (tenant_id, total_cases, active_cases, completed_cases, avg_completion_days, last_updated_at)
                    VALUES (%s, 0, 0, 1, %s, now())
                    ON CONFLICT (tenant_id) DO UPDATE SET
                        active_cases = GREATEST(case_summary.active_cases - 1, 0),
                        completed_cases = case_summary.completed_cases + 1,
                        avg_completion_days = CASE
                            WHEN case_summary.completed_cases = 0 THEN %s
                            ELSE (COALESCE(case_summary.avg_completion_days, 0) * case_summary.completed_cases + %s)
                                 / (case_summary.completed_cases + 1)
                        END,
                        last_updated_at = now()
                    """,
                    (tenant_id, completion_days, completion_days, completion_days),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO case_summary (tenant_id, total_cases, active_cases, completed_cases, last_updated_at)
                    VALUES (%s, 0, 0, 1, now())
                    ON CONFLICT (tenant_id) DO UPDATE SET
                        active_cases = GREATEST(case_summary.active_cases - 1, 0),
                        completed_cases = case_summary.completed_cases + 1,
                        last_updated_at = now()
                    """,
                    (tenant_id,),
                )
            cur.close()
            conn.commit()

    def _increment_cancelled(self, tenant_id: str) -> None:
        """SAGA_COMPENSATION_COMPLETED: active_cases -= 1, cancelled_cases += 1."""
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO case_summary (tenant_id, total_cases, active_cases, cancelled_cases, last_updated_at)
                VALUES (%s, 0, 0, 1, now())
                ON CONFLICT (tenant_id) DO UPDATE SET
                    active_cases = GREATEST(case_summary.active_cases - 1, 0),
                    cancelled_cases = case_summary.cancelled_cases + 1,
                    last_updated_at = now()
                """,
                (tenant_id,),
            )
            cur.close()
            conn.commit()

    # ──────────────── query (read model) ──────────────── #

    def query_summary(self, tenant_id: str) -> dict[str, Any] | None:
        """읽기 모델에서 tenant_id별 case_summary 조회."""
        psycopg2 = _import_psycopg2()
        from psycopg2.extras import RealDictCursor
        try:
            with self._conn() as conn:
                cur = conn.cursor(cursor_factory=RealDictCursor)
                cur.execute(
                    "SELECT * FROM case_summary WHERE tenant_id = %s",
                    (tenant_id,),
                )
                row = cur.fetchone()
                cur.close()
                return dict(row) if row else None
        except Exception:
            logger.warning("case_summary query failed", exc_info=True)
            return None
