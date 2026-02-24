import pytest
from app.services.process_service import ProcessDomainError, ProcessService, WorkItemStatus

from unittest.mock import AsyncMock, MagicMock

def _make_mock_workitem(**overrides):
    """Create a mock ORM WorkItem with all fields the mapper expects."""
    defaults = dict(
        id="uuid-123",
        proc_inst_id="proc-inst-1",
        activity_name="Initial Review",
        activity_type="humanTask",
        assignee_id=None,
        agent_mode="MANUAL",
        status=WorkItemStatus.IN_PROGRESS.value,
        result_data={},
        tenant_id="test-tenant",
        version=1,
        created_at=None,
    )
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


@pytest.mark.asyncio
async def test_submit_workitem_transitions():
    db_mock = AsyncMock()
    db_mock.add = MagicMock()

    class MockResult:
        def scalar_one_or_none(self):
            return _make_mock_workitem()

    db_mock.execute.return_value = MockResult()
    
    result = await ProcessService.submit_workitem(
        db=db_mock,
        item_id="uuid-123",
        submit_data={},
        force_complete=True,
    )
    # By default, mock mode was MANUAL, so transition is TO DONE
    assert result["status"] == WorkItemStatus.DONE
    assert result["workitem_id"] == "uuid-123"
    assert result["is_process_completed"] is True

@pytest.mark.asyncio
async def test_approve_hitl():
    db_mock = AsyncMock()

    class MockResult:
        def scalar_one_or_none(self):
            return _make_mock_workitem(status=WorkItemStatus.SUBMITTED.value)

    db_mock.execute.return_value = MockResult()

    # Test rejection requires feedback
    with pytest.raises(ProcessDomainError, match="Feedback is required"):
        await ProcessService.approve_hitl(db=db_mock, item_id="uuid-456", approved=False, feedback="")
        
    # Test valid rejection
    result = await ProcessService.approve_hitl(db=db_mock, item_id="uuid-456", approved=False, feedback="Bad data")
    assert result["status"] == WorkItemStatus.REWORK
    assert result["approved"] is False
    
    # Test valid approval
    result = await ProcessService.approve_hitl(db=db_mock, item_id="uuid-789", approved=True)
    assert result["status"] == WorkItemStatus.DONE
    assert result["approved"] is True


@pytest.mark.asyncio
async def test_initiate_requires_role_bindings():
    db_mock = AsyncMock()
    with pytest.raises(ProcessDomainError, match="role_bindings is required"):
        await ProcessService.initiate_process(
            db=db_mock,
            proc_def_id="proc-1",
            input_data={"tenant_id": "t1"},
            role_bindings=[],
        )
