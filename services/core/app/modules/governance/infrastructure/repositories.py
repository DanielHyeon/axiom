"""
거버넌스 인프라 — 비동기 Repository.

tenant_id 필수 WHERE 조건 + soft delete 필터를 모든 쿼리에 강제한다.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.governance.domain.models import Membership, OrgUnit, Workspace


# ── OrgUnit Repository ─────────────────────────────────────

class OrgUnitRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def find_by_id(self, tenant_id: str, org_unit_id: UUID) -> OrgUnit | None:
        result = await self.session.execute(
            select(OrgUnit).where(
                OrgUnit.tenant_id == tenant_id,
                OrgUnit.id == org_unit_id,
                OrgUnit.is_deleted == False,
            )
        )
        return result.scalar_one_or_none()

    async def find_all_by_tenant(self, tenant_id: str) -> list[OrgUnit]:
        """트리 구성용 — 테넌트의 모든 조직 단위 조회."""
        result = await self.session.execute(
            select(OrgUnit).where(
                OrgUnit.tenant_id == tenant_id,
                OrgUnit.is_deleted == False,
            ).order_by(OrgUnit.path)
        )
        return list(result.scalars().all())

    async def exists_code(self, tenant_id: str, code: str) -> bool:
        result = await self.session.execute(
            select(func.count()).select_from(OrgUnit).where(
                OrgUnit.tenant_id == tenant_id,
                OrgUnit.code == code,
                OrgUnit.is_deleted == False,
            )
        )
        return result.scalar_one() > 0

    def add(self, org_unit: OrgUnit) -> None:
        self.session.add(org_unit)


# ── Workspace Repository ───────────────────────────────────

class WorkspaceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def find_by_id(self, tenant_id: str, workspace_id: UUID) -> Workspace | None:
        result = await self.session.execute(
            select(Workspace).where(
                Workspace.tenant_id == tenant_id,
                Workspace.id == workspace_id,
                Workspace.is_deleted == False,
            )
        )
        return result.scalar_one_or_none()

    async def find_all_by_tenant(
        self, tenant_id: str, page: int = 1, page_size: int = 50,
    ) -> tuple[list[Workspace], int]:
        # 건수 조회
        count_q = select(func.count()).select_from(Workspace).where(
            Workspace.tenant_id == tenant_id,
            Workspace.is_deleted == False,
        )
        total = (await self.session.execute(count_q)).scalar_one()

        # 데이터 조회
        data_q = (
            select(Workspace)
            .where(Workspace.tenant_id == tenant_id, Workspace.is_deleted == False)
            .order_by(Workspace.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self.session.execute(data_q)).scalars().all()
        return list(rows), total

    async def exists_code(self, tenant_id: str, code: str) -> bool:
        result = await self.session.execute(
            select(func.count()).select_from(Workspace).where(
                Workspace.tenant_id == tenant_id,
                Workspace.code == code,
                Workspace.is_deleted == False,
            )
        )
        return result.scalar_one() > 0

    def add(self, workspace: Workspace) -> None:
        self.session.add(workspace)


# ── Membership Repository ──────────────────────────────────

class MembershipRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def find_by_workspace(
        self, tenant_id: str, workspace_id: UUID,
    ) -> list[Membership]:
        result = await self.session.execute(
            select(Membership).where(
                Membership.tenant_id == tenant_id,
                Membership.workspace_id == workspace_id,
                Membership.is_deleted == False,
                Membership.status == "ACTIVE",
            ).order_by(Membership.created_at.desc())
        )
        return list(result.scalars().all())

    async def has_workspace_access(
        self, tenant_id: str, user_id: str, workspace_id: UUID,
    ) -> bool:
        """사용자가 특정 워크스페이스에 활성 멤버십을 보유하는지 확인."""
        result = await self.session.execute(
            select(func.count()).select_from(Membership).where(
                Membership.tenant_id == tenant_id,
                Membership.user_id == user_id,
                Membership.workspace_id == workspace_id,
                Membership.is_deleted == False,
                Membership.status == "ACTIVE",
            )
        )
        return result.scalar_one() > 0

    def add(self, membership: Membership) -> None:
        self.session.add(membership)
