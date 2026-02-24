"""Unit tests for WorkItem Aggregate Root.

Tests pure domain logic — no database, no I/O.
Covers: invariants, state machine, event collection, factory, edge cases.
"""
import pytest

from app.domain.aggregates.work_item import AgentMode, WorkItem, WorkItemStatus
from app.domain.errors import AlreadyCompleted, InvalidStateTransition
from app.domain.events import (
    HitlApproved,
    HitlRejected,
    WorkItemCancelled,
    WorkItemCompleted,
    WorkItemCreated,
    WorkItemReworkRequested,
    WorkItemStarted,
    WorkItemSubmitted,
)


def _make(
    *,
    status: WorkItemStatus = WorkItemStatus.TODO,
    version: int = 1,
    agent_mode: AgentMode = AgentMode.MANUAL,
    result_data: dict | None = None,
) -> WorkItem:
    """Shortcut to create a WorkItem in a specific state (bypassing factory events)."""
    return WorkItem(
        id="wi-1",
        proc_inst_id="proc-1",
        activity_name="Review",
        activity_type="humanTask",
        assignee_id="user-1",
        agent_mode=agent_mode,
        status=status,
        result_data=result_data,
        tenant_id="t-1",
        version=version,
    )


# ── Factory Tests ────────────────────────────────────────

class TestFactory:
    def test_create_sets_todo_status(self):
        wi = WorkItem.create(
            id="wi-1", proc_inst_id="proc-1", activity_name="Review", tenant_id="t-1"
        )
        assert wi.status == WorkItemStatus.TODO
        assert wi.version == 1

    def test_create_records_created_event(self):
        wi = WorkItem.create(
            id="wi-1", proc_inst_id="proc-1", activity_name="Review", tenant_id="t-1"
        )
        events = wi.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], WorkItemCreated)
        assert events[0].workitem_id == "wi-1"
        assert events[0].tenant_id == "t-1"

    def test_create_with_agent_mode(self):
        wi = WorkItem.create(
            id="wi-1",
            proc_inst_id="proc-1",
            activity_name="Check",
            agent_mode=AgentMode.SELF_VERIFY,
            tenant_id="t-1",
        )
        assert wi.agent_mode == AgentMode.SELF_VERIFY

    def test_create_with_result_data(self):
        wi = WorkItem.create(
            id="wi-1",
            proc_inst_id="proc-1",
            activity_name="Review",
            tenant_id="t-1",
            result_data={"proc_def_id": "pd-1"},
        )
        assert wi.result_data == {"proc_def_id": "pd-1"}


# ── State Transition Tests ───────────────────────────────

class TestStateTransitions:
    def test_todo_to_in_progress(self):
        wi = _make(status=WorkItemStatus.TODO)
        wi.start()
        assert wi.status == WorkItemStatus.IN_PROGRESS
        assert wi.version == 2

    def test_in_progress_to_submitted(self):
        wi = _make(status=WorkItemStatus.IN_PROGRESS)
        wi.submit(result_data={"value": "pending"})
        assert wi.status == WorkItemStatus.SUBMITTED

    def test_in_progress_to_done(self):
        wi = _make(status=WorkItemStatus.IN_PROGRESS)
        wi.complete(result_data={"value": "ok"})
        assert wi.status == WorkItemStatus.DONE

    def test_submitted_to_done_requires_force(self):
        wi = _make(status=WorkItemStatus.SUBMITTED)
        with pytest.raises(InvalidStateTransition):
            wi.complete(result_data={"value": "done"})

    def test_submitted_to_done_with_force(self):
        wi = _make(status=WorkItemStatus.SUBMITTED)
        wi.complete(result_data={"value": "approved"}, force=True)
        assert wi.status == WorkItemStatus.DONE

    def test_submitted_to_rework(self):
        wi = _make(status=WorkItemStatus.SUBMITTED)
        wi.request_rework(reason="Need more details")
        assert wi.status == WorkItemStatus.REWORK

    def test_rework_to_todo(self):
        wi = _make(status=WorkItemStatus.REWORK)
        wi.reset_to_todo(reason="Reset for redo")
        assert wi.status == WorkItemStatus.TODO

    def test_rework_to_in_progress(self):
        wi = _make(status=WorkItemStatus.REWORK)
        wi.start()
        assert wi.status == WorkItemStatus.IN_PROGRESS

    def test_rework_to_cancelled(self):
        wi = _make(status=WorkItemStatus.REWORK)
        wi.cancel(reason="No longer needed")
        assert wi.status == WorkItemStatus.CANCELLED

    def test_todo_to_cancelled(self):
        wi = _make(status=WorkItemStatus.TODO)
        wi.cancel()
        assert wi.status == WorkItemStatus.CANCELLED

    def test_in_progress_to_cancelled(self):
        wi = _make(status=WorkItemStatus.IN_PROGRESS)
        wi.cancel(reason="Abort")
        assert wi.status == WorkItemStatus.CANCELLED


# ── Invalid Transition Tests ─────────────────────────────

class TestInvalidTransitions:
    def test_cannot_start_done_item(self):
        wi = _make(status=WorkItemStatus.DONE)
        with pytest.raises(AlreadyCompleted):
            wi.start()

    def test_cannot_complete_done_item(self):
        wi = _make(status=WorkItemStatus.DONE)
        with pytest.raises(AlreadyCompleted):
            wi.complete(result_data={"value": "again"})

    def test_cannot_cancel_done_item(self):
        wi = _make(status=WorkItemStatus.DONE)
        with pytest.raises(AlreadyCompleted):
            wi.cancel()

    def test_cannot_cancel_cancelled_item(self):
        wi = _make(status=WorkItemStatus.CANCELLED)
        with pytest.raises(AlreadyCompleted):
            wi.cancel()

    def test_cannot_submit_from_todo(self):
        wi = _make(status=WorkItemStatus.TODO)
        with pytest.raises(InvalidStateTransition):
            wi.submit(result_data={"value": "nope"})

    def test_cannot_complete_from_todo(self):
        wi = _make(status=WorkItemStatus.TODO)
        with pytest.raises(InvalidStateTransition):
            wi.complete(result_data={"value": "nope"})

    def test_cannot_start_from_submitted(self):
        wi = _make(status=WorkItemStatus.SUBMITTED)
        with pytest.raises(InvalidStateTransition):
            wi.start()

    def test_cannot_submit_from_done(self):
        wi = _make(status=WorkItemStatus.DONE)
        with pytest.raises(AlreadyCompleted):
            wi.submit(result_data={"value": "nope"})


# ── Version Tracking Tests ───────────────────────────────

class TestVersionTracking:
    def test_version_increments_on_each_transition(self):
        wi = _make(status=WorkItemStatus.TODO, version=1)
        wi.start()
        assert wi.version == 2
        wi.complete(result_data={"value": "ok"})
        assert wi.version == 3

    def test_version_increments_through_full_path(self):
        wi = _make(status=WorkItemStatus.TODO, version=1)
        wi.start()  # v2
        wi.submit(result_data={"value": "pending"})  # v3
        wi.request_rework(reason="redo")  # v4
        wi.start()  # v5
        wi.complete(result_data={"value": "final"})  # v6
        assert wi.version == 6


# ── Event Collection Tests ───────────────────────────────

class TestEventCollection:
    def test_events_collected_and_cleared(self):
        wi = WorkItem.create(
            id="wi-1", proc_inst_id="proc-1", activity_name="Review", tenant_id="t-1"
        )
        wi.start()
        wi.complete(result_data={"value": "ok"})
        events = wi.collect_events()
        assert len(events) == 3  # Created + Started + Completed
        assert isinstance(events[0], WorkItemCreated)
        assert isinstance(events[1], WorkItemStarted)
        assert isinstance(events[2], WorkItemCompleted)
        # Second collect should be empty
        assert wi.collect_events() == []

    def test_submit_records_submitted_event(self):
        wi = _make(status=WorkItemStatus.IN_PROGRESS)
        wi.submit(result_data={"v": 1}, verification_outcome={"decision": "FAIL_ROUTE"})
        events = wi.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], WorkItemSubmitted)
        assert events[0].verification == {"decision": "FAIL_ROUTE"}

    def test_cancel_records_cancelled_event(self):
        wi = _make(status=WorkItemStatus.TODO)
        wi.cancel(reason="Not needed")
        events = wi.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], WorkItemCancelled)
        assert events[0].reason == "Not needed"

    def test_rework_records_event(self):
        wi = _make(status=WorkItemStatus.SUBMITTED)
        wi.request_rework(reason="Needs revision")
        events = wi.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], WorkItemReworkRequested)


# ── HITL Tests ───────────────────────────────────────────

class TestHitl:
    def test_approve_hitl(self):
        wi = _make(status=WorkItemStatus.SUBMITTED)
        wi.approve_hitl(feedback="Looks good")
        assert wi.status == WorkItemStatus.DONE
        assert wi.result_data["hitl_feedback"] == "Looks good"
        events = wi.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], HitlApproved)

    def test_reject_hitl(self):
        wi = _make(status=WorkItemStatus.SUBMITTED)
        wi.reject_hitl(feedback="Missing data")
        assert wi.status == WorkItemStatus.REWORK
        assert wi.result_data["hitl_feedback"] == "Missing data"
        events = wi.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], HitlRejected)


# ── Saga Compensation Tests ──────────────────────────────

class TestSagaCompensation:
    def test_mark_rework_from_done(self):
        wi = _make(status=WorkItemStatus.DONE, version=3)
        wi.mark_rework()
        assert wi.status == WorkItemStatus.REWORK
        assert wi.version == 4

    def test_mark_rework_from_submitted(self):
        wi = _make(status=WorkItemStatus.SUBMITTED, version=2)
        wi.mark_rework()
        assert wi.status == WorkItemStatus.REWORK

    def test_mark_rework_from_invalid_raises(self):
        wi = _make(status=WorkItemStatus.TODO)
        with pytest.raises(InvalidStateTransition):
            wi.mark_rework()

    def test_force_cancel_from_in_progress(self):
        wi = _make(status=WorkItemStatus.IN_PROGRESS)
        wi.force_cancel()
        assert wi.status == WorkItemStatus.CANCELLED

    def test_force_cancel_idempotent_on_done(self):
        wi = _make(status=WorkItemStatus.DONE, version=3)
        wi.force_cancel()
        assert wi.status == WorkItemStatus.DONE  # no change
        assert wi.version == 3  # no version bump

    def test_force_cancel_idempotent_on_cancelled(self):
        wi = _make(status=WorkItemStatus.CANCELLED, version=2)
        wi.force_cancel()
        assert wi.status == WorkItemStatus.CANCELLED


# ── Properties Tests ─────────────────────────────────────

class TestProperties:
    def test_is_terminal_done(self):
        assert _make(status=WorkItemStatus.DONE).is_terminal is True

    def test_is_terminal_cancelled(self):
        assert _make(status=WorkItemStatus.CANCELLED).is_terminal is True

    def test_is_terminal_in_progress(self):
        assert _make(status=WorkItemStatus.IN_PROGRESS).is_terminal is False

    def test_proc_def_id_from_result_data(self):
        wi = _make(result_data={"proc_def_id": "pd-1"})
        assert wi.proc_def_id == "pd-1"

    def test_proc_def_id_none_when_no_data(self):
        wi = _make(result_data=None)
        assert wi.proc_def_id is None


# ── Full Path Tests ──────────────────────────────────────

class TestFullPaths:
    def test_happy_path_manual(self):
        """TODO → IN_PROGRESS → DONE"""
        wi = WorkItem.create(id="w", proc_inst_id="p", activity_name="R", tenant_id="t")
        wi.start()
        wi.complete(result_data={"answer": 42})
        assert wi.status == WorkItemStatus.DONE
        events = wi.collect_events()
        assert len(events) == 3
        types = [type(e).__name__ for e in events]
        assert types == ["WorkItemCreated", "WorkItemStarted", "WorkItemCompleted"]

    def test_self_verify_fail_then_hitl_approve(self):
        """TODO → IN_PROGRESS → SUBMITTED → DONE (via HITL)"""
        wi = WorkItem.create(id="w", proc_inst_id="p", activity_name="R", tenant_id="t")
        wi.start()
        wi.submit(result_data={"v": 1}, verification_outcome={"decision": "FAIL_ROUTE"})
        wi.approve_hitl(feedback="OK")
        assert wi.status == WorkItemStatus.DONE

    def test_self_verify_fail_then_hitl_reject_then_redo(self):
        """TODO → IN_PROGRESS → SUBMITTED → REWORK → IN_PROGRESS → DONE"""
        wi = WorkItem.create(id="w", proc_inst_id="p", activity_name="R", tenant_id="t")
        wi.start()
        wi.submit(result_data={"v": 1}, verification_outcome={"decision": "FAIL_ROUTE"})
        wi.reject_hitl(feedback="Redo it")
        wi.start()
        wi.complete(result_data={"v": 2})
        assert wi.status == WorkItemStatus.DONE

    def test_cancel_from_todo(self):
        """TODO → CANCELLED"""
        wi = WorkItem.create(id="w", proc_inst_id="p", activity_name="R", tenant_id="t")
        wi.cancel(reason="No longer needed")
        assert wi.status == WorkItemStatus.CANCELLED

    def test_rework_reset_cycle(self):
        """REWORK → TODO → IN_PROGRESS → DONE"""
        wi = _make(status=WorkItemStatus.REWORK, version=4)
        wi.reset_to_todo(reason="Redo from scratch")
        assert wi.status == WorkItemStatus.TODO
        wi.start()
        wi.complete(result_data={"final": True})
        assert wi.status == WorkItemStatus.DONE
        assert wi.version == 7
