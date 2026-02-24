"""Unit tests for the enhanced Outbox Relay Worker (SyncWorker).

Tests cover:
- published_at timestamp on successful publish
- retry_count increment and DEAD_LETTER transition
- last_error recording
- retry_failed_once respects MAX_RETRY

NOTE: Integration test — requires live PostgreSQL.
      Run with Docker: docker exec axiom-core-svc-1 python -m pytest tests/unit/test_outbox_relay.py
"""
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

from app.core.database import DATABASE_URL, DATABASE_SCHEMA
from app.models.base_models import Base, EventOutbox
from app.workers.sync import SyncWorker, MAX_RETRY


def _make_session_factory():
    """매 호출마다 fresh engine 생성 (NullPool로 connection 공유 방지)."""
    eng = create_async_engine(DATABASE_URL, echo=False, poolclass=NullPool)
    return eng, async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture()
async def db_session():
    """테스트별 fresh engine/session — connection pool 오염 없음."""
    eng, SessionFactory = _make_session_factory()
    async with eng.begin() as conn:
        await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {DATABASE_SCHEMA}"))
        await conn.run_sync(Base.metadata.create_all)
    yield eng, SessionFactory
    async with eng.begin() as conn:
        await conn.execute(text("DELETE FROM core.event_outbox"))
    await eng.dispose()


def _make_event(event_id: str, status: str = "PENDING", retry_count: int = 0, **kwargs) -> EventOutbox:
    return EventOutbox(
        id=event_id,
        event_type=kwargs.get("event_type", "PROCESS_INITIATED"),
        aggregate_type="WorkItem",
        aggregate_id=f"wi-{event_id}",
        payload={"test": True, "idempotency_key": f"key-{event_id}"},
        status=status,
        tenant_id="test-tenant",
        retry_count=retry_count,
        last_error=kwargs.get("last_error"),
    )


class TestPublishPendingOnce:
    @pytest.mark.asyncio
    async def test_successful_publish_sets_published_at(self, db_session):
        """PENDING event should transition to PUBLISHED with published_at timestamp."""
        eng, Session = db_session
        async with Session() as session:
            session.add(_make_event("evt-1"))
            await session.commit()

        mock_redis = AsyncMock()
        mock_redis.xadd = AsyncMock()
        mock_redis.xlen = AsyncMock(return_value=0)

        with patch("app.workers.sync.get_redis", return_value=mock_redis), \
             patch("app.workers.sync.AsyncSessionLocal", Session):
            worker = SyncWorker()
            result = await worker.publish_pending_once(limit=10)

        assert result["published"] == 1
        assert result["failed"] == 0

        async with Session() as session:
            row = await session.execute(select(EventOutbox).where(EventOutbox.id == "evt-1"))
            event = row.scalar_one()
            assert event.status == "PUBLISHED"
            assert event.published_at is not None
            assert event.retry_count == 0

    @pytest.mark.asyncio
    async def test_failed_publish_increments_retry_count(self, db_session):
        """Failed publish should increment retry_count and record last_error."""
        eng, Session = db_session
        async with Session() as session:
            session.add(_make_event("evt-2"))
            await session.commit()

        mock_redis = AsyncMock()
        mock_redis.xadd = AsyncMock(side_effect=ConnectionError("Redis down"))
        mock_redis.xlen = AsyncMock(return_value=0)

        with patch("app.workers.sync.get_redis", return_value=mock_redis), \
             patch("app.workers.sync.AsyncSessionLocal", Session):
            worker = SyncWorker()
            result = await worker.publish_pending_once(limit=10)

        assert result["published"] == 0
        assert result["failed"] == 1

        async with Session() as session:
            row = await session.execute(select(EventOutbox).where(EventOutbox.id == "evt-2"))
            event = row.scalar_one()
            assert event.status == "FAILED"
            assert event.retry_count == 1
            assert "Redis down" in event.last_error

    @pytest.mark.asyncio
    async def test_dead_letter_after_max_retry(self, db_session):
        """Event at MAX_RETRY-1 should transition to DEAD_LETTER on next failure."""
        eng, Session = db_session
        async with Session() as session:
            session.add(_make_event("evt-3", retry_count=MAX_RETRY - 1))
            await session.commit()

        mock_redis = AsyncMock()
        mock_redis.xadd = AsyncMock(side_effect=ConnectionError("Redis down"))
        mock_redis.xlen = AsyncMock(return_value=0)

        with patch("app.workers.sync.get_redis", return_value=mock_redis), \
             patch("app.workers.sync.AsyncSessionLocal", Session):
            worker = SyncWorker()
            await worker.publish_pending_once(limit=10)

        async with Session() as session:
            row = await session.execute(select(EventOutbox).where(EventOutbox.id == "evt-3"))
            event = row.scalar_one()
            assert event.status == "DEAD_LETTER"
            assert event.retry_count == MAX_RETRY

    @pytest.mark.asyncio
    async def test_stream_routing(self, db_session):
        """Events should be routed to correct Redis Streams based on event_type prefix."""
        eng, Session = db_session
        async with Session() as session:
            session.add(_make_event("evt-w", event_type="WATCH_CASE_STATUS"))
            session.add(_make_event("evt-k", event_type="WORKER_TASK_DONE"))
            session.add(_make_event("evt-e", event_type="PROCESS_INITIATED"))
            await session.commit()

        mock_redis = AsyncMock()
        mock_redis.xadd = AsyncMock()
        mock_redis.xlen = AsyncMock(return_value=0)

        with patch("app.workers.sync.get_redis", return_value=mock_redis), \
             patch("app.workers.sync.AsyncSessionLocal", Session):
            worker = SyncWorker()
            result = await worker.publish_pending_once(limit=10)

        assert result["published"] == 3
        streams_called = [call.args[0] for call in mock_redis.xadd.call_args_list]
        assert "axiom:watches" in streams_called
        assert "axiom:workers" in streams_called
        assert "axiom:core:events" in streams_called


class TestRetryFailedOnce:
    @pytest.mark.asyncio
    async def test_resets_failed_to_pending(self, db_session):
        """FAILED events below MAX_RETRY should be reset to PENDING."""
        eng, Session = db_session
        async with Session() as session:
            session.add(_make_event("evt-r1", status="FAILED", retry_count=1))
            await session.commit()

        with patch("app.workers.sync.AsyncSessionLocal", Session):
            worker = SyncWorker()
            count = await worker.retry_failed_once(limit=10)
        assert count == 1

        async with Session() as session:
            row = await session.execute(select(EventOutbox).where(EventOutbox.id == "evt-r1"))
            event = row.scalar_one()
            assert event.status == "PENDING"

    @pytest.mark.asyncio
    async def test_moves_exhausted_to_dead_letter(self, db_session):
        """FAILED events at MAX_RETRY should be moved to DEAD_LETTER."""
        eng, Session = db_session
        async with Session() as session:
            session.add(_make_event("evt-r2", status="FAILED", retry_count=MAX_RETRY))
            await session.commit()

        with patch("app.workers.sync.AsyncSessionLocal", Session):
            worker = SyncWorker()
            count = await worker.retry_failed_once(limit=10)
        assert count == 0  # not reset, moved to DEAD_LETTER

        async with Session() as session:
            row = await session.execute(select(EventOutbox).where(EventOutbox.id == "evt-r2"))
            event = row.scalar_one()
            assert event.status == "DEAD_LETTER"
