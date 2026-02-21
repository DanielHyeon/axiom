import pytest
from unittest.mock import AsyncMock
from app.workers.base import BaseWorker

@pytest.mark.asyncio
async def test_idempotent_event_processing():
    worker = BaseWorker("test_worker")
    redis_mock = AsyncMock()
    
    handler_mock = AsyncMock()
    
    # Scenario 1: Key is new
    redis_mock.set.return_value = True
    await worker.process_event_idempotent(redis_mock, "evt-123", handler_mock)
    
    redis_mock.set.assert_called_once()
    handler_mock.assert_awaited_once()
    
    # Scenario 2: Key already exists (Duplicate)
    redis_mock.reset_mock()
    handler_mock.reset_mock()
    redis_mock.set.return_value = False
    
    await worker.process_event_idempotent(redis_mock, "evt-123", handler_mock)
    redis_mock.set.assert_called_once()
    handler_mock.assert_not_awaited() # Handler skipped!
