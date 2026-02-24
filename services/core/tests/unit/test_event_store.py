"""DDD-P3-02: Unit tests for WorkItemEventStore PoC.

Tests event replay logic without actual DB — uses mocked query results.
"""
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.process.domain.aggregates.work_item import (
    AgentMode,
    WorkItem,
    WorkItemStatus,
)
from app.modules.process.domain.events import (
    WorkItemCancelled,
    WorkItemCompleted,
    WorkItemCreated,
    WorkItemStarted,
    WorkItemSubmitted,
)
from app.modules.process.infrastructure.event_store import (
    WorkItemEventStore,
    _replay_events,
    _serialize_event,
)


class TestSerializeEvent:
    def test_serialize_created_event(self):
        event = WorkItemCreated(
            workitem_id="wi-1",
            tenant_id="t-1",
            activity_name="Review",
            agent_mode="MANUAL",
        )
        data = _serialize_event(event)
        assert data["workitem_id"] == "wi-1"
        assert data["tenant_id"] == "t-1"
        assert data["activity_name"] == "Review"
        assert data["agent_mode"] == "MANUAL"
        assert "occurred_at" in data

    def test_serialize_completed_event(self):
        event = WorkItemCompleted(
            workitem_id="wi-1",
            proc_inst_id="p-1",
            tenant_id="t-1",
            result_data={"answer": 42},
        )
        data = _serialize_event(event)
        assert data["result_data"] == {"answer": 42}
        assert data["proc_inst_id"] == "p-1"


class TestReplayEvents:
    def _make_row(self, event_type: str, event_data: dict, version: int):
        row = MagicMock()
        row.event_type = event_type
        row.event_data = event_data
        row.version = version
        row.created_at = datetime.now(timezone.utc)
        return row

    def test_replay_created_only(self):
        rows = [
            self._make_row("WorkItemCreated", {
                "workitem_id": "wi-1",
                "tenant_id": "t-1",
                "activity_name": "Review",
                "agent_mode": "MANUAL",
            }, 1),
        ]
        wi = _replay_events("wi-1", rows)
        assert wi.id == "wi-1"
        assert wi.status == WorkItemStatus.TODO
        assert wi.version == 1
        assert wi.tenant_id == "t-1"

    def test_replay_created_then_started(self):
        rows = [
            self._make_row("WorkItemCreated", {
                "workitem_id": "wi-1",
                "tenant_id": "t-1",
                "activity_name": "Review",
                "agent_mode": "MANUAL",
            }, 1),
            self._make_row("WorkItemStarted", {
                "workitem_id": "wi-1",
                "tenant_id": "t-1",
            }, 2),
        ]
        wi = _replay_events("wi-1", rows)
        assert wi.status == WorkItemStatus.IN_PROGRESS
        assert wi.version == 2

    def test_replay_full_happy_path(self):
        rows = [
            self._make_row("WorkItemCreated", {
                "workitem_id": "wi-1",
                "tenant_id": "t-1",
                "activity_name": "Check",
                "agent_mode": "SUPERVISED",
            }, 1),
            self._make_row("WorkItemStarted", {
                "workitem_id": "wi-1",
                "tenant_id": "t-1",
            }, 2),
            self._make_row("WorkItemCompleted", {
                "workitem_id": "wi-1",
                "tenant_id": "t-1",
                "result_data": {"output": "success"},
            }, 3),
        ]
        wi = _replay_events("wi-1", rows)
        assert wi.status == WorkItemStatus.DONE
        assert wi.version == 3
        assert wi.result_data == {"output": "success"}
        assert wi.agent_mode == AgentMode.SUPERVISED

    def test_replay_submitted_then_rework(self):
        rows = [
            self._make_row("WorkItemCreated", {
                "workitem_id": "wi-1",
                "tenant_id": "t-1",
                "activity_name": "Verify",
                "agent_mode": "SELF_VERIFY",
            }, 1),
            self._make_row("WorkItemStarted", {}, 2),
            self._make_row("WorkItemSubmitted", {
                "verification": {"decision": "FAIL_ROUTE"},
            }, 3),
            self._make_row("WorkItemReworkRequested", {
                "reason": "Need more data",
            }, 4),
        ]
        wi = _replay_events("wi-1", rows)
        assert wi.status == WorkItemStatus.REWORK
        assert wi.version == 4
        assert wi.result_data.get("rework_reason") == "Need more data"

    def test_replay_cancelled(self):
        rows = [
            self._make_row("WorkItemCreated", {
                "workitem_id": "wi-1",
                "tenant_id": "t-1",
                "activity_name": "Task",
                "agent_mode": "MANUAL",
            }, 1),
            self._make_row("WorkItemCancelled", {
                "reason": "Aborted",
            }, 2),
        ]
        wi = _replay_events("wi-1", rows)
        assert wi.status == WorkItemStatus.CANCELLED
        assert wi.version == 2

    def test_replay_hitl_approved(self):
        rows = [
            self._make_row("WorkItemCreated", {
                "workitem_id": "wi-1",
                "tenant_id": "t-1",
                "activity_name": "Task",
                "agent_mode": "MANUAL",
            }, 1),
            self._make_row("WorkItemStarted", {}, 2),
            self._make_row("WorkItemSubmitted", {}, 3),
            self._make_row("HitlApproved", {"feedback": "Looks good"}, 4),
        ]
        wi = _replay_events("wi-1", rows)
        assert wi.status == WorkItemStatus.DONE
        assert wi.result_data.get("hitl_feedback") == "Looks good"

    def test_replay_no_created_event_raises(self):
        rows = [
            self._make_row("WorkItemStarted", {}, 1),
        ]
        with pytest.raises(ValueError, match="No WorkItemCreated event found"):
            _replay_events("wi-1", rows)

    def test_replay_empty_rows_raises(self):
        with pytest.raises(ValueError, match="No WorkItemCreated"):
            _replay_events("wi-1", [])


class TestWorkItemEventStoreLoad:
    @pytest.mark.asyncio
    async def test_load_returns_none_for_unknown_aggregate(self):
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.fetchall.return_value = []
        db.execute = AsyncMock(return_value=result_mock)

        store = WorkItemEventStore()
        wi = await store.load(db, "nonexistent-id")
        assert wi is None

    @pytest.mark.asyncio
    async def test_count_events(self):
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar.return_value = 5
        db.execute = AsyncMock(return_value=result_mock)

        store = WorkItemEventStore()
        count = await store.count_events(db, "wi-1")
        assert count == 5
