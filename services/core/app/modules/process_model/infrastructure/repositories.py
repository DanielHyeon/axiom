"""
프로세스 모델 인프라 — 비동기 Repository.

모든 쿼리에 tenant_id + is_deleted=false 강제.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.process_model.domain.models import (
    InterfaceContract, KpiDefinition, ProcessDefinition,
    ProcessDomain, ProcessRelationEdge, ProcessVersion,
    RuleDefinition, StepDefinition, StepTransitionEdge,
)


class ProcessDomainRepository:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def find_by_workspace(self, tenant_id: str, workspace_id: UUID) -> list[ProcessDomain]:
        r = await self.s.execute(
            select(ProcessDomain).where(
                ProcessDomain.tenant_id == tenant_id,
                ProcessDomain.workspace_id == workspace_id,
                ProcessDomain.is_deleted == False,
            ).order_by(ProcessDomain.name)
        )
        return list(r.scalars().all())

    def add(self, entity: ProcessDomain) -> None:
        self.s.add(entity)


class ProcessDefinitionRepository:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def find_by_id(self, tenant_id: str, def_id: UUID) -> ProcessDefinition | None:
        r = await self.s.execute(
            select(ProcessDefinition).where(
                ProcessDefinition.tenant_id == tenant_id,
                ProcessDefinition.id == def_id,
                ProcessDefinition.is_deleted == False,
            )
        )
        return r.scalar_one_or_none()

    async def find_list(
        self, tenant_id: str, *, domain_id: UUID | None = None,
        status: str | None = None, page: int = 1, page_size: int = 50,
    ) -> tuple[list[ProcessDefinition], int]:
        base = select(ProcessDefinition).where(
            ProcessDefinition.tenant_id == tenant_id,
            ProcessDefinition.is_deleted == False,
        )
        if domain_id:
            base = base.where(ProcessDefinition.domain_id == domain_id)
        if status:
            base = base.where(ProcessDefinition.lifecycle_status == status)

        count = (await self.s.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
        rows = (await self.s.execute(
            base.order_by(ProcessDefinition.created_at.desc())
            .offset((page - 1) * page_size).limit(page_size)
        )).scalars().all()
        return list(rows), count

    async def exists_namespace(self, tenant_id: str, namespace: str) -> bool:
        r = await self.s.execute(
            select(func.count()).select_from(ProcessDefinition).where(
                ProcessDefinition.tenant_id == tenant_id,
                ProcessDefinition.namespace == namespace,
                ProcessDefinition.is_deleted == False,
            )
        )
        return r.scalar_one() > 0

    async def cas_update(self, def_id: UUID, expected_version: int, **values) -> int:
        """CAS 패턴: version이 expected와 일치할 때만 업데이트. 반환값은 affected rows."""
        r = await self.s.execute(
            update(ProcessDefinition)
            .where(
                ProcessDefinition.id == def_id,
                ProcessDefinition.version == expected_version,
                ProcessDefinition.is_deleted == False,
            )
            .values(version=ProcessDefinition.version + 1, **values)
        )
        return r.rowcount

    def add(self, entity: ProcessDefinition) -> None:
        self.s.add(entity)


class ProcessVersionRepository:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def find_by_id(self, tenant_id: str, ver_id: UUID) -> ProcessVersion | None:
        r = await self.s.execute(
            select(ProcessVersion).where(
                ProcessVersion.tenant_id == tenant_id,
                ProcessVersion.id == ver_id,
                ProcessVersion.is_deleted == False,
            )
        )
        return r.scalar_one_or_none()

    async def find_by_definition(self, tenant_id: str, def_id: UUID) -> list[ProcessVersion]:
        r = await self.s.execute(
            select(ProcessVersion).where(
                ProcessVersion.tenant_id == tenant_id,
                ProcessVersion.process_definition_id == def_id,
                ProcessVersion.is_deleted == False,
            ).order_by(ProcessVersion.version_no.desc())
        )
        return list(r.scalars().all())

    async def max_version_no(self, tenant_id: str, def_id: UUID) -> int:
        r = await self.s.execute(
            select(func.max(ProcessVersion.version_no)).where(
                ProcessVersion.tenant_id == tenant_id,
                ProcessVersion.process_definition_id == def_id,
                ProcessVersion.is_deleted == False,
            )
        )
        return r.scalar_one() or 0

    def add(self, entity: ProcessVersion) -> None:
        self.s.add(entity)


class StepDefinitionRepository:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def find_by_version(self, tenant_id: str, version_id: UUID) -> list[StepDefinition]:
        r = await self.s.execute(
            select(StepDefinition).where(
                StepDefinition.tenant_id == tenant_id,
                StepDefinition.process_version_id == version_id,
                StepDefinition.is_deleted == False,
            ).order_by(StepDefinition.display_order)
        )
        return list(r.scalars().all())

    def add(self, entity: StepDefinition) -> None:
        self.s.add(entity)


class ProcessRelationRepository:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def find_by_source(self, tenant_id: str, source_id: UUID) -> list[ProcessRelationEdge]:
        r = await self.s.execute(
            select(ProcessRelationEdge).where(
                ProcessRelationEdge.tenant_id == tenant_id,
                ProcessRelationEdge.source_entity_id == source_id,
                ProcessRelationEdge.is_deleted == False,
            )
        )
        return list(r.scalars().all())

    async def find_by_id(self, tenant_id: str, edge_id: UUID) -> ProcessRelationEdge | None:
        r = await self.s.execute(
            select(ProcessRelationEdge).where(
                ProcessRelationEdge.tenant_id == tenant_id,
                ProcessRelationEdge.id == edge_id,
                ProcessRelationEdge.is_deleted == False,
            )
        )
        return r.scalar_one_or_none()

    def add(self, entity: ProcessRelationEdge) -> None:
        self.s.add(entity)
