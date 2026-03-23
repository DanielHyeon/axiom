"""
프로세스 전이 애플리케이션 서비스.

Phase 2.5: step_transition_edges CRUD + 유효성 검증.
"""
from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.process_model.domain.errors import (
    ProcessVersionNotFoundError, VersionConflictError, VersionNotEditableError,
)
from app.modules.process_model.domain.models import StepDefinition, StepTransitionEdge
from app.modules.process_model.infrastructure.repositories import (
    ProcessVersionRepository, StepDefinitionRepository,
)
from app.modules.process_model.validation.transition_validator import validate_transitions

logger = logging.getLogger("axiom.process_model.transition")


class TransitionService:
    """step_transition_edges CRUD + 유효성 검증."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.ver_repo = ProcessVersionRepository(session)
        self.step_repo = StepDefinitionRepository(session)

    async def bulk_upsert(
        self, tenant_id: str, version_id: UUID, expected_version: int,
        transitions: list[dict],
    ) -> list[StepTransitionEdge]:
        """전이 일괄 저장 — CAS + 유효성 검증."""
        version = await self.ver_repo.find_by_id(tenant_id, version_id)
        if not version:
            raise ProcessVersionNotFoundError(str(version_id))
        if version.status != "DRAFT":
            raise VersionNotEditableError(str(version_id), version.status)
        # CAS — DB 레벨 atomic UPDATE (race window 제거)
        from sqlalchemy import update as sa_update
        from app.modules.process_model.domain.models import ProcessVersion as PV
        cas_result = await self.session.execute(
            sa_update(PV)
            .where(PV.id == version.id, PV.version == expected_version)
            .values(version=PV.version + 1)
        )
        if cas_result.rowcount == 0:
            await self.session.refresh(version)
            raise VersionConflictError(version.version, expected_version)

        # 해당 version의 모든 step 로드
        steps = await self.step_repo.find_by_version(tenant_id, version_id)

        # 유효성 검증
        failures = validate_transitions(steps, transitions, version_id)
        if failures:
            from app.modules.process_model.domain.errors import ProcessModelError
            err = ProcessModelError("TRANSITION_VALIDATION_FAILED", f"{len(failures)} transition validation failures", 422)
            err.failures = failures
            raise err

        # 기존 전이 soft delete
        existing = await self._find_by_version(tenant_id, version_id)
        for t in existing:
            t.is_deleted = True

        # 신규 전이 생성
        result = []
        for t_data in transitions:
            edge = StepTransitionEdge(
                tenant_id=tenant_id,
                process_version_id=version_id,
                from_step_id=t_data["from_step_id"],
                to_step_id=t_data["to_step_id"],
                transition_type=t_data["transition_type"],
                condition_expression=t_data.get("condition_expression"),
                is_default=t_data.get("is_default", False),
                display_order=t_data.get("display_order", 0),
                metadata_json=t_data.get("metadata_json"),
            )
            self.session.add(edge)
            result.append(edge)

        # version bump은 위의 atomic CAS에서 처리 완료
        await self.session.flush()
        return result

    async def list_transitions(self, tenant_id: str, version_id: UUID) -> list[StepTransitionEdge]:
        """version의 전이 목록 조회."""
        return await self._find_by_version(tenant_id, version_id)

    async def delete_transition(self, tenant_id: str, transition_id: UUID) -> None:
        """단일 전이 soft delete."""
        r = await self.session.execute(
            select(StepTransitionEdge).where(
                StepTransitionEdge.tenant_id == tenant_id,
                StepTransitionEdge.id == transition_id,
                StepTransitionEdge.is_deleted == False,
            )
        )
        edge = r.scalar_one_or_none()
        if edge:
            edge.is_deleted = True
            await self.session.flush()

    async def _find_by_version(self, tenant_id: str, version_id: UUID) -> list[StepTransitionEdge]:
        r = await self.session.execute(
            select(StepTransitionEdge).where(
                StepTransitionEdge.tenant_id == tenant_id,
                StepTransitionEdge.process_version_id == version_id,
                StepTransitionEdge.is_deleted == False,
            ).order_by(StepTransitionEdge.display_order)
        )
        return list(r.scalars().all())
