"""
거버넌스 애플리케이션 서비스.

OrgUnit/Workspace/Membership CRUD + 비즈니스 규칙 적용.
모든 조작은 tenant_id 범위 내에서만 수행된다.
"""
from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.governance.domain.errors import (
    DuplicateCodeError, GovernanceError, OrgUnitNotFoundError, WorkspaceNotFoundError,
)

# 허용되는 역할 코드 목록
VALID_ROLE_CODES: frozenset[str] = frozenset({
    "PLATFORM_ADMIN", "TENANT_ADMIN", "DOMAIN_OWNER",
    "PROCESS_ARCHITECT", "PROCESS_ANALYST", "TWIN_OPERATOR",
    "SCENARIO_ANALYST", "VIEWER",
})
from app.modules.governance.domain.models import Membership, OrgUnit, Workspace
from app.modules.governance.domain.schemas import (
    MembershipCreate, OrgUnitCreate, OrgUnitUpdate,
    WorkspaceCreate, WorkspaceUpdate,
)
from app.modules.governance.infrastructure.repositories import (
    MembershipRepository, OrgUnitRepository, WorkspaceRepository,
)

logger = logging.getLogger("axiom.governance")


class GovernanceService:
    """거버넌스 도메인 애플리케이션 서비스."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.org_repo = OrgUnitRepository(session)
        self.ws_repo = WorkspaceRepository(session)
        self.member_repo = MembershipRepository(session)

    # ── OrgUnit ────────────────────────────────────────────

    async def create_org_unit(self, tenant_id: str, dto: OrgUnitCreate) -> OrgUnit:
        # 코드 중복 검사
        if await self.org_repo.exists_code(tenant_id, dto.code):
            raise DuplicateCodeError("OrgUnit", dto.code)

        # 부모 존재 확인 + path 계산
        if dto.parent_org_unit_id:
            parent = await self.org_repo.find_by_id(tenant_id, dto.parent_org_unit_id)
            if not parent:
                raise OrgUnitNotFoundError(str(dto.parent_org_unit_id))
            path = f"{parent.path}/{dto.code}"
        else:
            path = f"/{dto.code}"

        org_unit = OrgUnit(
            tenant_id=tenant_id,
            parent_org_unit_id=dto.parent_org_unit_id,
            code=dto.code,
            name=dto.name,
            org_type=dto.org_type.value,
            owner_user_id=dto.owner_user_id,
            path=path,
        )
        self.org_repo.add(org_unit)
        await self.session.flush()
        return org_unit

    async def get_org_unit_tree(self, tenant_id: str) -> list[OrgUnit]:
        """플랫 목록 반환 — 트리 조립은 API 레이어에서 처리."""
        return await self.org_repo.find_all_by_tenant(tenant_id)

    async def update_org_unit(
        self, tenant_id: str, org_unit_id: UUID, dto: OrgUnitUpdate,
    ) -> OrgUnit:
        org_unit = await self.org_repo.find_by_id(tenant_id, org_unit_id)
        if not org_unit:
            raise OrgUnitNotFoundError(str(org_unit_id))

        if dto.name is not None:
            org_unit.name = dto.name
        if dto.org_type is not None:
            org_unit.org_type = dto.org_type.value
        if dto.owner_user_id is not None:
            org_unit.owner_user_id = dto.owner_user_id

        await self.session.flush()
        return org_unit

    # ── Workspace ──────────────────────────────────────────

    async def create_workspace(self, tenant_id: str, dto: WorkspaceCreate) -> Workspace:
        # org_unit 존재 확인
        org_unit = await self.org_repo.find_by_id(tenant_id, dto.org_unit_id)
        if not org_unit:
            raise OrgUnitNotFoundError(str(dto.org_unit_id))

        # 코드 중복 검사
        if await self.ws_repo.exists_code(tenant_id, dto.code):
            raise DuplicateCodeError("Workspace", dto.code)

        workspace = Workspace(
            tenant_id=tenant_id,
            org_unit_id=dto.org_unit_id,
            code=dto.code,
            name=dto.name,
            workspace_type=dto.workspace_type.value,
            visibility_policy=dto.visibility_policy.value,
        )
        self.ws_repo.add(workspace)
        await self.session.flush()
        return workspace

    async def get_workspaces(
        self, tenant_id: str, page: int = 1, page_size: int = 50,
    ) -> tuple[list[Workspace], int]:
        return await self.ws_repo.find_all_by_tenant(tenant_id, page, page_size)

    async def get_workspace(self, tenant_id: str, workspace_id: UUID) -> Workspace:
        ws = await self.ws_repo.find_by_id(tenant_id, workspace_id)
        if not ws:
            raise WorkspaceNotFoundError(str(workspace_id))
        return ws

    async def update_workspace(
        self, tenant_id: str, workspace_id: UUID, dto: WorkspaceUpdate,
    ) -> Workspace:
        ws = await self.ws_repo.find_by_id(tenant_id, workspace_id)
        if not ws:
            raise WorkspaceNotFoundError(str(workspace_id))

        if dto.name is not None:
            ws.name = dto.name
        if dto.visibility_policy is not None:
            ws.visibility_policy = dto.visibility_policy.value

        await self.session.flush()
        return ws

    # ── Membership ─────────────────────────────────────────

    async def create_membership(self, tenant_id: str, dto: MembershipCreate) -> Membership:
        # role_code 유효성 검증 — 권한 상승 방지
        if dto.role_code not in VALID_ROLE_CODES:
            raise GovernanceError("INVALID_ROLE", f"Unknown role_code '{dto.role_code}'", 400)

        membership = Membership(
            tenant_id=tenant_id,
            user_id=dto.user_id,
            role_code=dto.role_code,
            scope_type=dto.scope_type.value,
            org_unit_id=dto.org_unit_id,
            workspace_id=dto.workspace_id,
            effective_from=dto.effective_from,
            effective_to=dto.effective_to,
        )
        self.member_repo.add(membership)
        await self.session.flush()
        return membership

    async def get_workspace_members(
        self, tenant_id: str, workspace_id: UUID,
    ) -> list[Membership]:
        return await self.member_repo.find_by_workspace(tenant_id, workspace_id)

    async def validate_workspace_access(
        self, tenant_id: str, user_id: str, workspace_id: UUID,
    ) -> bool:
        """사용자의 워크스페이스 접근 권한 검증."""
        return await self.member_repo.has_workspace_access(
            tenant_id, user_id, workspace_id,
        )
