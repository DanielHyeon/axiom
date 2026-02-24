"""Domain Errors — business rule violation exceptions."""
from __future__ import annotations


class DomainError(Exception):
    """Base class for all domain-level errors."""
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class InvalidStateTransition(DomainError):
    """Raised when an aggregate state transition violates the state machine."""
    def __init__(self, current: str, target: str):
        super().__init__(
            code="INVALID_STATE_TRANSITION",
            message=f"Cannot transition from {current} to {target}",
        )
        self.current = current
        self.target = target


class WorkItemNotFound(DomainError):
    def __init__(self, workitem_id: str = ""):
        super().__init__(code="WORKITEM_NOT_FOUND", message=f"WorkItem not found: {workitem_id}")


class ProcessNotFound(DomainError):
    def __init__(self, proc_id: str = ""):
        super().__init__(code="PROCESS_NOT_FOUND", message=f"Process not found: {proc_id}")


class AlreadyCompleted(DomainError):
    def __init__(self, status: str):
        super().__init__(code="ALREADY_COMPLETED", message=f"Cannot submit in state {status}")


class ProcessCompleted(DomainError):
    def __init__(self):
        super().__init__(code="PROCESS_COMPLETED", message="Completed process cannot be reworked")
