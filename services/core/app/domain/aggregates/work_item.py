"""Backward compatibility shim — re-exports from modules/process/domain/aggregates/work_item.

신규 코드는 app.modules.process.domain.aggregates.work_item을 직접 import해야 한다.
"""
from app.modules.process.domain.aggregates.work_item import (  # noqa: F401
    WorkItemStatus,
    AgentMode,
    WorkItem,
)
