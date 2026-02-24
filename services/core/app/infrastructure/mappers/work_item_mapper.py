"""Backward compatibility shim — re-exports from modules/process/infrastructure/mappers.

신규 코드는 app.modules.process.infrastructure.mappers.work_item_mapper를 직접 import해야 한다.
"""
from app.modules.process.infrastructure.mappers.work_item_mapper import (  # noqa: F401
    WorkItemMapper,
)
