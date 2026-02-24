"""Backward compatibility shim — re-exports from modules/process/domain/repositories.

신규 코드는 app.modules.process.domain.repositories.work_item_repository를 직접 import해야 한다.
"""
from app.modules.process.domain.repositories.work_item_repository import (  # noqa: F401
    WorkItemRepository,
)
