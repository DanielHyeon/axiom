import pytest
import pytest_asyncio
from sqlalchemy import select

from app.core.database import AsyncSessionLocal, engine, ensure_schema
from app.core.events import EventPublisher
from app.core.middleware import _tenant_id
from app.core.observability import metrics_registry
from app.models.base_models import Base, EventOutbox
from app.workers.sync import SyncWorker


class FakeRedis:
    def __init__(self, fail_main: bool = False):
        self.fail_main = fail_main
        self.streams: dict[str, list[tuple[str, dict]]] = {}
        self.seq = 0

    async def xadd(self, stream: str, payload: dict, maxlen: int = 10000, approximate: bool = True):
        if self.fail_main and stream != "axiom:dlq:events":
            raise RuntimeError("forced xadd failure")
        self.seq += 1
        entry_id = f"{self.seq}-0"
        self.streams.setdefault(stream, []).append((entry_id, payload))
        return entry_id

    async def xlen(self, stream: str):
        return len(self.streams.get(stream, []))

    async def xrange(self, stream: str, min: str = "-", max: str = "+", count: int = 100):
        return self.streams.get(stream, [])[:count]

    async def xdel(self, stream: str, entry_id: str):
        self.streams[stream] = [item for item in self.streams.get(stream, []) if item[0] != entry_id]


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    metrics_registry.reset()
    async with engine.begin() as conn:
        await ensure_schema(conn)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.mark.asyncio
async def test_legacy_write_violation_metric_and_payload():
    token = _tenant_id.set("acme-corp")
    try:
        async with AsyncSessionLocal() as session:
            await EventPublisher.publish(
                session=session,
                event_type="PROCESS_INITIATED",
                aggregate_type="legacy_table",
                aggregate_id="proc-1",
                payload={"legacy_write": True, "proc_def_id": "d-1", "workitem_id": "w-1"},
            )
            await session.commit()

            row = await session.execute(select(EventOutbox).where(EventOutbox.aggregate_id == "proc-1"))
            outbox = row.scalar_one()
            assert outbox.payload["legacy_policy"]["violation_detected"] is True
            assert metrics_registry.get_counter("core_legacy_write_violations_total") == 1
    finally:
        _tenant_id.reset(token)


@pytest.mark.asyncio
async def test_sync_worker_publishes_pending(monkeypatch):
    token = _tenant_id.set("acme-corp")
    fake_redis = FakeRedis()
    monkeypatch.setattr("app.workers.sync.get_redis", lambda: fake_redis)
    try:
        async with AsyncSessionLocal() as session:
            await EventPublisher.publish(
                session=session,
                event_type="WORKITEM_COMPLETED",
                aggregate_type="workitem",
                aggregate_id="wi-100",
                payload={"result": {"ok": True}},
            )
            await session.commit()

        worker = SyncWorker()
        result = await worker.publish_pending_once(limit=10)
        assert result["published"] == 1
        assert result["failed"] == 0
        assert len(fake_redis.streams.get("axiom:events", [])) == 1

        async with AsyncSessionLocal() as session:
            row = await session.execute(select(EventOutbox).where(EventOutbox.aggregate_id == "wi-100"))
            outbox = row.scalar_one()
            assert outbox.status == "PUBLISHED"
    finally:
        _tenant_id.reset(token)


@pytest.mark.asyncio
async def test_sync_worker_moves_failed_publish_to_dlq(monkeypatch):
    token = _tenant_id.set("acme-corp")
    fake_redis = FakeRedis(fail_main=True)
    monkeypatch.setattr("app.workers.sync.get_redis", lambda: fake_redis)
    try:
        async with AsyncSessionLocal() as session:
            await EventPublisher.publish(
                session=session,
                event_type="WORKITEM_COMPLETED",
                aggregate_type="workitem",
                aggregate_id="wi-200",
                payload={"result": {"ok": True}},
            )
            await session.commit()

        worker = SyncWorker()
        result = await worker.publish_pending_once(limit=10)
        assert result["published"] == 0
        assert result["failed"] == 1
        assert len(fake_redis.streams.get("axiom:dlq:events", [])) == 1

        async with AsyncSessionLocal() as session:
            row = await session.execute(select(EventOutbox).where(EventOutbox.aggregate_id == "wi-200"))
            outbox = row.scalar_one()
            assert outbox.status == "FAILED"
    finally:
        _tenant_id.reset(token)
