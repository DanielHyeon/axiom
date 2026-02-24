"""WorkItem Repository interface — defined in domain layer, implemented in infrastructure."""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.modules.process.domain.aggregates.work_item import WorkItem


class WorkItemRepository(ABC):
    """Persistence abstraction for WorkItem Aggregate Root.

    The domain layer defines this interface; infrastructure provides
    the concrete implementation (e.g. SQLAlchemy).
    """

    @abstractmethod
    async def find_by_id(self, workitem_id: str) -> WorkItem | None:
        """Load a single WorkItem by its ID."""
        ...

    @abstractmethod
    async def find_by_proc_inst(
        self, proc_inst_id: str, *, tenant_id: str | None = None
    ) -> list[WorkItem]:
        """Load all WorkItems belonging to a process instance."""
        ...

    @abstractmethod
    async def find_by_tenant(
        self,
        tenant_id: str,
        *,
        status: str | None = None,
        assignee_id: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[WorkItem], int]:
        """Tenant-scoped workitem listing with filters. Returns (items, total_count)."""
        ...

    @abstractmethod
    async def save(self, workitem: WorkItem) -> None:
        """Persist a new or modified WorkItem."""
        ...

    @abstractmethod
    async def save_all(self, workitems: list[WorkItem]) -> None:
        """Persist multiple WorkItems in one batch."""
        ...
