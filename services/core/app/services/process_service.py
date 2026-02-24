"""Backward compatibility shim.

신규 코드는 app.modules.process.application.process_service_facade를 직접 import해야 한다.
"""
from app.modules.process.application.process_service_facade import (  # noqa: F401
    ProcessDomainError,
    ProcessService,
    WorkItemUpdateModel,
)
from app.modules.process.domain.aggregates.work_item import (  # noqa: F401
    AgentMode,
    WorkItemStatus,
)
