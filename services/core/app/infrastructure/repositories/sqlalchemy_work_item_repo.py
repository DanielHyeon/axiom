"""Backward compatibility shim — re-exports from modules/process/infrastructure/repositories.

신규 코드는 app.modules.process.infrastructure.repositories.sqlalchemy_work_item_repo를 직접 import해야 한다.
"""
from app.modules.process.infrastructure.repositories.sqlalchemy_work_item_repo import (  # noqa: F401
    SQLAlchemyWorkItemRepository,
)
