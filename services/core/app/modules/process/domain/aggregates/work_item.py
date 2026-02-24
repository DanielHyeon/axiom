"""WorkItem Aggregate Root — encapsulates all business rules for work items.

Invariants:
1. State transitions follow _TRANSITIONS map (state machine)
2. DONE/CANCELLED are terminal — no further transitions allowed
3. version increments on every state change (optimistic locking)
4. SUBMITTED → DONE requires force=True (HITL approval gate)
5. Domain events are collected and drained by the application layer
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.modules.process.domain.errors import AlreadyCompleted, InvalidStateTransition
from app.modules.process.domain.events import (
    DomainEvent,
    HitlApproved,
    HitlRejected,
    WorkItemCancelled,
    WorkItemCompleted,
    WorkItemCreated,
    WorkItemReworkRequested,
    WorkItemStarted,
    WorkItemSubmitted,
)


class WorkItemStatus(str, Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    SUBMITTED = "SUBMITTED"
    DONE = "DONE"
    REWORK = "REWORK"
    CANCELLED = "CANCELLED"


class AgentMode(str, Enum):
    MANUAL = "MANUAL"
    SUPERVISED = "SUPERVISED"
    AUTONOMOUS = "AUTONOMOUS"
    SELF_VERIFY = "SELF_VERIFY"


# Allowed state transitions (state machine)
_TRANSITIONS: dict[WorkItemStatus, set[WorkItemStatus]] = {
    WorkItemStatus.TODO: {WorkItemStatus.IN_PROGRESS, WorkItemStatus.CANCELLED},
    WorkItemStatus.IN_PROGRESS: {
        WorkItemStatus.SUBMITTED,
        WorkItemStatus.DONE,
        WorkItemStatus.CANCELLED,
    },
    WorkItemStatus.SUBMITTED: {WorkItemStatus.DONE, WorkItemStatus.REWORK},
    WorkItemStatus.REWORK: {WorkItemStatus.TODO, WorkItemStatus.IN_PROGRESS, WorkItemStatus.CANCELLED},
    WorkItemStatus.DONE: set(),
    WorkItemStatus.CANCELLED: set(),
}


@dataclass
class WorkItem:
    """WorkItem Aggregate Root.

    All state-mutating operations go through explicit command methods
    that enforce invariants and record domain events.
    """

    id: str
    proc_inst_id: str | None
    activity_name: str | None
    activity_type: str
    assignee_id: str | None
    agent_mode: AgentMode
    status: WorkItemStatus
    result_data: dict[str, Any] | None
    tenant_id: str
    version: int

    _events: list[DomainEvent] = field(default_factory=list, repr=False)

    # ── Factory ──────────────────────────────────────────

    @classmethod
    def create(
        cls,
        *,
        id: str,
        proc_inst_id: str | None,
        activity_name: str | None,
        activity_type: str = "humanTask",
        assignee_id: str | None = None,
        agent_mode: AgentMode = AgentMode.MANUAL,
        tenant_id: str,
        result_data: dict[str, Any] | None = None,
    ) -> WorkItem:
        wi = cls(
            id=id,
            proc_inst_id=proc_inst_id,
            activity_name=activity_name,
            activity_type=activity_type,
            assignee_id=assignee_id,
            agent_mode=agent_mode,
            status=WorkItemStatus.TODO,
            result_data=result_data,
            tenant_id=tenant_id,
            version=1,
        )
        wi._record(WorkItemCreated(
            workitem_id=id,
            tenant_id=tenant_id,
            activity_name=activity_name or "",
            agent_mode=agent_mode.value,
        ))
        return wi

    # ── Commands ─────────────────────────────────────────

    def start(self) -> None:
        """TODO → IN_PROGRESS."""
        self._transition_to(WorkItemStatus.IN_PROGRESS)
        self._record(WorkItemStarted(workitem_id=self.id, tenant_id=self.tenant_id))

    def submit(
        self,
        result_data: dict[str, Any],
        verification_outcome: dict[str, Any] | None = None,
    ) -> None:
        """IN_PROGRESS → SUBMITTED (self-verification fail route)."""
        self._transition_to(WorkItemStatus.SUBMITTED)
        if not isinstance(result_data, dict):
            result_data = {"value": result_data}
        if verification_outcome:
            result_data["self_verification"] = verification_outcome
        self.result_data = result_data
        self._record(WorkItemSubmitted(
            workitem_id=self.id,
            tenant_id=self.tenant_id,
            verification=verification_outcome,
        ))

    def complete(
        self,
        result_data: dict[str, Any],
        *,
        force: bool = False,
        verification_outcome: dict[str, Any] | None = None,
    ) -> None:
        """IN_PROGRESS → DONE, or SUBMITTED → DONE (force=True only)."""
        if self.status == WorkItemStatus.SUBMITTED and not force:
            raise InvalidStateTransition(self.status.value, WorkItemStatus.DONE.value)
        self._transition_to(WorkItemStatus.DONE)
        if not isinstance(result_data, dict):
            result_data = {"value": result_data}
        if verification_outcome and verification_outcome.get("decision") == "PASS":
            result_data["self_verification"] = verification_outcome
        self.result_data = result_data
        self._record(WorkItemCompleted(
            workitem_id=self.id,
            proc_inst_id=self.proc_inst_id,
            tenant_id=self.tenant_id,
            result_data=result_data,
        ))

    def cancel(self, reason: str = "") -> None:
        """TODO/IN_PROGRESS/REWORK → CANCELLED."""
        self._transition_to(WorkItemStatus.CANCELLED)
        self._record(WorkItemCancelled(
            workitem_id=self.id,
            tenant_id=self.tenant_id,
            reason=reason,
        ))

    def request_rework(self, reason: str) -> None:
        """SUBMITTED → REWORK."""
        self._transition_to(WorkItemStatus.REWORK)
        self._record(WorkItemReworkRequested(
            workitem_id=self.id,
            tenant_id=self.tenant_id,
            reason=reason,
        ))

    def approve_hitl(self, feedback: str = "") -> None:
        """SUBMITTED → DONE via human-in-the-loop approval."""
        self._transition_to(WorkItemStatus.DONE)
        existing = self.result_data or {}
        existing["hitl_feedback"] = feedback
        self.result_data = existing
        self._record(HitlApproved(
            workitem_id=self.id,
            tenant_id=self.tenant_id,
            feedback=feedback,
        ))

    def reject_hitl(self, feedback: str) -> None:
        """SUBMITTED → REWORK via human-in-the-loop rejection."""
        self._transition_to(WorkItemStatus.REWORK)
        existing = self.result_data or {}
        existing["hitl_feedback"] = feedback
        self.result_data = existing
        self._record(HitlRejected(
            workitem_id=self.id,
            tenant_id=self.tenant_id,
            feedback=feedback,
        ))

    def reset_to_todo(self, reason: str, revert_to_activity_id: str | None = None) -> None:
        """REWORK → TODO (saga compensation reset)."""
        self._transition_to(WorkItemStatus.TODO)
        payload = self.result_data or {}
        payload["rework_reason"] = reason
        payload["revert_to_activity_id"] = revert_to_activity_id
        self.result_data = payload

    def mark_rework(self) -> None:
        """DONE/SUBMITTED → REWORK (saga compensation for sibling items)."""
        if self.status not in (WorkItemStatus.DONE, WorkItemStatus.SUBMITTED):
            raise InvalidStateTransition(self.status.value, WorkItemStatus.REWORK.value)
        self.status = WorkItemStatus.REWORK
        self.version += 1

    def force_cancel(self) -> None:
        """Force cancel from any non-terminal state (saga compensation)."""
        if self.status in (WorkItemStatus.DONE, WorkItemStatus.CANCELLED):
            return  # idempotent
        self.status = WorkItemStatus.CANCELLED
        self.version += 1

    # ── Queries ──────────────────────────────────────────

    @property
    def is_terminal(self) -> bool:
        return self.status in (WorkItemStatus.DONE, WorkItemStatus.CANCELLED)

    @property
    def proc_def_id(self) -> str | None:
        """Extract proc_def_id from result_data if present."""
        if self.result_data:
            return self.result_data.get("proc_def_id")
        return None

    # ── Event Collection ─────────────────────────────────

    def collect_events(self) -> list[DomainEvent]:
        """Drain and return all pending domain events."""
        events = list(self._events)
        self._events.clear()
        return events

    # ── Private ──────────────────────────────────────────

    def _transition_to(self, target: WorkItemStatus) -> None:
        if self.status in (WorkItemStatus.DONE, WorkItemStatus.CANCELLED):
            raise AlreadyCompleted(self.status.value)
        allowed = _TRANSITIONS.get(self.status, set())
        if target not in allowed:
            raise InvalidStateTransition(self.status.value, target.value)
        self.status = target
        self.version += 1

    def _record(self, event: DomainEvent) -> None:
        self._events.append(event)
