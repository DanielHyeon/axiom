import pytest
import pytest_asyncio
from sqlalchemy import select
from app.models.base_models import Base, WorkItem, EventOutbox
from app.services.process_service import ProcessService
from app.core.middleware import _tenant_id
from app.core.database import engine, AsyncSessionLocal

@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_outbox_transactional_commit():
    """Verify that submitting a workitem writes BOTH the workitem update AND the outbox event."""
    token = _tenant_id.set("test-tenant")
    try:
        async with AsyncSessionLocal() as session:
            # Setup
            wi = WorkItem(id="wi-1", status="IN_PROGRESS", tenant_id="test-tenant")
            session.add(wi)
            await session.commit()
            
            # Action
            await ProcessService.submit_workitem(session, "wi-1", {"result_data": {"foo": "bar"}})
            await session.commit() # Simulating router dependency commit
            
            # Assert
            result = await session.execute(select(WorkItem).where(WorkItem.id == "wi-1"))
            updated_wi = result.scalar_one()
            assert updated_wi.status == "DONE"
            
            outbox_result = await session.execute(select(EventOutbox).where(EventOutbox.aggregate_id == "wi-1"))
            outbox_entry = outbox_result.scalar_one()
            
            assert outbox_entry.event_type == "WORKITEM_COMPLETED"
            assert outbox_entry.status == "PENDING"
            assert outbox_entry.payload["result"]["foo"] == "bar"
            
    finally:
        _tenant_id.reset(token)

@pytest.mark.asyncio
async def test_outbox_transactional_rollback():
    """Verify that rolling back the DB session discards BOTH workitem updates AND outbox writes."""
    token = _tenant_id.set("test-tenant")
    try:
        async with AsyncSessionLocal() as session:
            wi = WorkItem(id="wi-2", status="IN_PROGRESS", tenant_id="test-tenant")
            session.add(wi)
            await session.commit()
            
            # Action imitating a failure before commit
            await ProcessService.submit_workitem(session, "wi-2", {"result_data": {}})
            await session.rollback() # Forced failure constraint
            
            # Assert
            result = await session.execute(select(WorkItem).where(WorkItem.id == "wi-2"))
            same_wi = result.scalar_one()
            assert same_wi.status == "IN_PROGRESS" # Did not update to DONE
            
            outbox_result = await session.execute(select(EventOutbox).where(EventOutbox.aggregate_id == "wi-2"))
            assert outbox_result.scalar_one_or_none() is None # Did not write to outbox
            
    finally:
        _tenant_id.reset(token)
