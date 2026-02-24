"""Backward compatibility shim — re-exports from modules/process/domain/events.

신규 코드는 app.modules.process.domain.events를 직접 import해야 한다.
"""
from app.modules.process.domain.events import (  # noqa: F401
    DomainEvent,
    WorkItemCreated,
    WorkItemStarted,
    WorkItemSubmitted,
    WorkItemCompleted,
    WorkItemCancelled,
    WorkItemReworkRequested,
    HitlApproved,
    HitlRejected,
)
