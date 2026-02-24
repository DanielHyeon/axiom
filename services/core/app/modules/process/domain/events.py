"""Domain Events — immutable records of things that happened in the domain."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class DomainEvent:
    """Base class for all domain events."""
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ── WorkItem Events ──────────────────────────────────────

@dataclass(frozen=True)
class WorkItemCreated(DomainEvent):
    workitem_id: str = ""
    tenant_id: str = ""
    activity_name: str = ""
    agent_mode: str = ""


@dataclass(frozen=True)
class WorkItemStarted(DomainEvent):
    workitem_id: str = ""
    tenant_id: str = ""


@dataclass(frozen=True)
class WorkItemSubmitted(DomainEvent):
    workitem_id: str = ""
    tenant_id: str = ""
    verification: dict[str, Any] | None = None


@dataclass(frozen=True)
class WorkItemCompleted(DomainEvent):
    workitem_id: str = ""
    proc_inst_id: str | None = None
    tenant_id: str = ""
    result_data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkItemCancelled(DomainEvent):
    workitem_id: str = ""
    tenant_id: str = ""
    reason: str = ""


@dataclass(frozen=True)
class WorkItemReworkRequested(DomainEvent):
    workitem_id: str = ""
    tenant_id: str = ""
    reason: str = ""


@dataclass(frozen=True)
class HitlApproved(DomainEvent):
    workitem_id: str = ""
    tenant_id: str = ""
    feedback: str = ""


@dataclass(frozen=True)
class HitlRejected(DomainEvent):
    workitem_id: str = ""
    tenant_id: str = ""
    feedback: str = ""
