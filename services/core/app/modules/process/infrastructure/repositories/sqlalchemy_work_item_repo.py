"""SQLAlchemy implementation of WorkItemRepository."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.process.domain.aggregates.work_item import WorkItem
from app.modules.process.domain.repositories.work_item_repository import WorkItemRepository
from app.modules.process.infrastructure.mappers.work_item_mapper import WorkItemMapper
from app.models.base_models import WorkItem as WorkItemORM


class SQLAlchemyWorkItemRepository(WorkItemRepository):
    """Concrete Repository backed by PostgreSQL via SQLAlchemy async."""

    def __init__(self, session: AsyncSession):
        self._session = session
        self._mapper = WorkItemMapper()

    async def find_by_id(self, workitem_id: str) -> WorkItem | None:
        result = await self._session.execute(
            select(WorkItemORM).where(WorkItemORM.id == workitem_id)
        )
        orm = result.scalar_one_or_none()
        return self._mapper.to_domain(orm) if orm else None

    async def find_by_proc_inst(
        self, proc_inst_id: str, *, tenant_id: str | None = None
    ) -> list[WorkItem]:
        stmt = select(WorkItemORM).where(WorkItemORM.proc_inst_id == proc_inst_id)
        if tenant_id:
            stmt = stmt.where(WorkItemORM.tenant_id == tenant_id)
        result = await self._session.execute(stmt)
        return [self._mapper.to_domain(orm) for orm in result.scalars()]

    async def find_by_tenant(
        self,
        tenant_id: str,
        *,
        status: str | None = None,
        assignee_id: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[WorkItem], int]:
        stmt = select(WorkItemORM).where(WorkItemORM.tenant_id == tenant_id)
        count_stmt = (
            select(func.count())
            .select_from(WorkItemORM)
            .where(WorkItemORM.tenant_id == tenant_id)
        )
        if status:
            stmt = stmt.where(WorkItemORM.status == status)
            count_stmt = count_stmt.where(WorkItemORM.status == status)
        if assignee_id:
            stmt = stmt.where(WorkItemORM.assignee_id == assignee_id)
            count_stmt = count_stmt.where(WorkItemORM.assignee_id == assignee_id)

        stmt = stmt.order_by(WorkItemORM.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        total = (await self._session.execute(count_stmt)).scalar() or 0
        items = [self._mapper.to_domain(orm) for orm in result.scalars()]
        return items, total

    async def save(self, workitem: WorkItem) -> None:
        result = await self._session.execute(
            select(WorkItemORM).where(WorkItemORM.id == workitem.id)
        )
        orm = result.scalar_one_or_none()
        if orm:
            self._mapper.to_orm(workitem, orm)
        else:
            orm = self._mapper.to_new_orm(workitem)
            self._session.add(orm)

    async def save_all(self, workitems: list[WorkItem]) -> None:
        for wi in workitems:
            await self.save(wi)
