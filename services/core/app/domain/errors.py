"""Backward compatibility shim — re-exports from modules/process/domain/errors.

신규 코드는 app.modules.process.domain.errors를 직접 import해야 한다.
"""
from app.modules.process.domain.errors import (  # noqa: F401
    DomainError,
    InvalidStateTransition,
    WorkItemNotFound,
    ProcessNotFound,
    AlreadyCompleted,
    ProcessCompleted,
)
