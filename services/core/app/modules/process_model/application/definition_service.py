"""
프로세스 정의 애플리케이션 서비스.

ProcessDefinition CRUD + 버전 관리 + 발행(Publish) + Step bulk-upsert.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.process_model.domain.errors import (
    NamespaceDuplicatedError, ProcessDefinitionNotFoundError,
    ProcessVersionNotFoundError, PublishValidationError,
    VersionConflictError, VersionNotEditableError,
)
from app.modules.process_model.domain.models import (
    ProcessDefinition, ProcessVersion, StepDefinition, StepTransitionEdge,
)
from app.modules.process_model.domain.schemas import (
    BulkUpsertStepsRequest, ProcessDefinitionCreate, ProcessDefinitionUpdate,
    StepDefinitionUpsert,
)
from app.modules.process_model.infrastructure.repositories import (
    ProcessDefinitionRepository, ProcessVersionRepository,
    StepDefinitionRepository,
)
from app.modules.process_model.infrastructure.event_publisher import publish_process_event
from app.modules.process_model.validation.publish_validator import validate_for_publish

logger = logging.getLogger("axiom.process_model")


class DefinitionService:
    """프로세스 정의 + 버전 + Step 관리."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.def_repo = ProcessDefinitionRepository(session)
        self.ver_repo = ProcessVersionRepository(session)
        self.step_repo = StepDefinitionRepository(session)

    # ── ProcessDefinition CRUD ─────────────────────────────

    async def create(self, tenant_id: str, user_id: str, dto: ProcessDefinitionCreate) -> ProcessDefinition:
        # namespace 중복 검사
        if await self.def_repo.exists_namespace(tenant_id, dto.namespace):
            raise NamespaceDuplicatedError(dto.namespace)

        proc_def = ProcessDefinition(
            tenant_id=tenant_id,
            workspace_id=dto.workspace_id,
            domain_id=dto.domain_id,
            group_id=dto.group_id,
            namespace=dto.namespace,
            code=dto.code,
            name=dto.name,
            description=dto.description,
            process_type=dto.process_type.value,
            is_template=dto.is_template,
            owner_org_unit_id=dto.owner_org_unit_id,
            primary_role_code=dto.primary_role_code,
            created_by=user_id,
            updated_by=user_id,
        )
        self.def_repo.add(proc_def)
        await self.session.flush()

        # DRAFT v1 자동 생성
        version = ProcessVersion(
            tenant_id=tenant_id,
            process_definition_id=proc_def.id,
            version_no=1,
            status="DRAFT",
            created_by=user_id,
        )
        self.ver_repo.add(version)
        await self.session.flush()

        proc_def.current_version_id = version.id
        await self.session.flush()

        # Outbox 이벤트 발행 — SyncWorker가 Redis Streams로 전송
        await publish_process_event(
            self.session,
            event_type="process.definition.created",
            aggregate_type="PROCESS_DEFINITION",
            aggregate_id=str(proc_def.id),
            tenant_id=tenant_id,
            payload={
                "id": str(proc_def.id), "namespace": proc_def.namespace,
                "code": proc_def.code, "name": proc_def.name,
                "processType": proc_def.process_type,
                "lifecycleStatus": proc_def.lifecycle_status,
                "workspaceId": str(proc_def.workspace_id),
                "updatedAt": datetime.now(timezone.utc).isoformat(),
            },
        )
        return proc_def

    async def get(self, tenant_id: str, def_id: UUID) -> ProcessDefinition:
        proc_def = await self.def_repo.find_by_id(tenant_id, def_id)
        if not proc_def:
            raise ProcessDefinitionNotFoundError(str(def_id))
        return proc_def

    async def list_definitions(
        self, tenant_id: str, domain_id: UUID | None = None,
        status: str | None = None, page: int = 1, page_size: int = 50,
    ) -> tuple[list[ProcessDefinition], int]:
        return await self.def_repo.find_list(
            tenant_id, domain_id=domain_id, status=status, page=page, page_size=page_size,
        )

    async def update(
        self, tenant_id: str, user_id: str, def_id: UUID, dto: ProcessDefinitionUpdate,
    ) -> ProcessDefinition:
        values = {"updated_by": user_id}
        if dto.name is not None:
            values["name"] = dto.name
        if dto.description is not None:
            values["description"] = dto.description
        if dto.owner_org_unit_id is not None:
            values["owner_org_unit_id"] = dto.owner_org_unit_id

        affected = await self.def_repo.cas_update(def_id, dto.expected_version, **values)
        if affected == 0:
            existing = await self.def_repo.find_by_id(tenant_id, def_id)
            if not existing:
                raise ProcessDefinitionNotFoundError(str(def_id))
            raise VersionConflictError(existing.version, dto.expected_version)

        return await self.def_repo.find_by_id(tenant_id, def_id)

    # ── Versions ───────────────────────────────────────────

    async def get_versions(self, tenant_id: str, def_id: UUID) -> list[ProcessVersion]:
        return await self.ver_repo.find_by_definition(tenant_id, def_id)

    # ── Publish ────────────────────────────────────────────

    async def publish(self, tenant_id: str, user_id: str, def_id: UUID) -> ProcessVersion:
        proc_def = await self.get(tenant_id, def_id)
        if not proc_def.current_version_id:
            raise ProcessVersionNotFoundError("no current version")

        version = await self.ver_repo.find_by_id(tenant_id, proc_def.current_version_id)
        if not version:
            raise ProcessVersionNotFoundError(str(proc_def.current_version_id))
        if version.status != "DRAFT":
            raise VersionNotEditableError(str(version.id), version.status)

        # Publish Validator — 12규칙 검증
        steps = await self.step_repo.find_by_version(tenant_id, version.id)
        transitions = await self._get_transitions(tenant_id, version.id)
        failures = validate_for_publish(steps, transitions)
        if failures:
            raise PublishValidationError(failures)

        # 원자적 발행: version 상태 전환 + valid_to/valid_from 설정
        now = datetime.now(timezone.utc)
        version.status = "PUBLISHED"
        version.published_at = now
        version.published_by = user_id
        version.valid_from = now

        # ProcessDefinition.lifecycle_status도 동기화
        proc_def.lifecycle_status = "PUBLISHED"
        proc_def.updated_by = user_id

        await self.session.flush()

        # Outbox 이벤트 발행
        await publish_process_event(
            self.session,
            event_type="process.version.published",
            aggregate_type="PROCESS_VERSION",
            aggregate_id=str(version.id),
            tenant_id=tenant_id,
            payload={
                "id": str(version.id),
                "processDefinitionId": str(proc_def.id),
                "versionNo": version.version_no,
                "status": "PUBLISHED",
                "workspaceId": str(proc_def.workspace_id),
                "updatedAt": now.isoformat(),
            },
        )
        return version

    async def _get_transitions(self, tenant_id: str, version_id: UUID) -> list[StepTransitionEdge]:
        from sqlalchemy import select
        r = await self.session.execute(
            select(StepTransitionEdge).where(
                StepTransitionEdge.tenant_id == tenant_id,
                StepTransitionEdge.process_version_id == version_id,
                StepTransitionEdge.is_deleted == False,
            )
        )
        return list(r.scalars().all())

    # ── Steps Bulk Upsert ──────────────────────────────────

    async def bulk_upsert_steps(
        self, tenant_id: str, user_id: str,
        def_id: UUID, version_no: int,
        dto: BulkUpsertStepsRequest,
    ) -> list[StepDefinition]:
        # 버전 찾기
        versions = await self.ver_repo.find_by_definition(tenant_id, def_id)
        version = next((v for v in versions if v.version_no == version_no), None)
        if not version:
            raise ProcessVersionNotFoundError(f"v{version_no}")
        if version.status != "DRAFT":
            raise VersionNotEditableError(str(version.id), version.status)

        # CAS 검증 — DB 레벨 atomic UPDATE (race window 제거)
        from sqlalchemy import update as sa_update
        cas_result = await self.session.execute(
            sa_update(ProcessVersion)
            .where(
                ProcessVersion.id == version.id,
                ProcessVersion.version == dto.expected_version,
            )
            .values(version=ProcessVersion.version + 1)
        )
        if cas_result.rowcount == 0:
            # 재조회하여 실제 version 확인
            await self.session.refresh(version)
            raise VersionConflictError(version.version, dto.expected_version)

        # 기존 step 로드
        existing = {s.id: s for s in await self.step_repo.find_by_version(tenant_id, version.id)}

        result = []
        for step_dto in dto.steps:
            if step_dto.id and step_dto.id in existing:
                # 업데이트 — model_fields_set으로 실제 전송된 필드만 적용 (False/0도 정상 처리)
                s = existing[step_dto.id]
                provided = step_dto.model_fields_set
                for field in ("code", "name", "step_type", "actor_type", "actor_ref",
                              "automation_level", "sla_minutes", "auto_executable",
                              "display_order", "parent_step_id", "ui_metadata_json",
                              "input_contract_id", "output_contract_id", "rule_set_id"):
                    if field in provided:
                        val = getattr(step_dto, field)
                        db_val = val.value if hasattr(val, "value") else val
                        setattr(s, field, db_val)
                s.updated_by = user_id
                result.append(s)
            else:
                # 신규
                s = StepDefinition(
                    tenant_id=tenant_id,
                    process_version_id=version.id,
                    code=step_dto.code,
                    name=step_dto.name,
                    step_type=step_dto.step_type.value,
                    actor_type=step_dto.actor_type.value,
                    actor_ref=step_dto.actor_ref,
                    automation_level=step_dto.automation_level.value,
                    input_contract_id=step_dto.input_contract_id,
                    output_contract_id=step_dto.output_contract_id,
                    rule_set_id=step_dto.rule_set_id,
                    sla_minutes=step_dto.sla_minutes,
                    auto_executable=step_dto.auto_executable,
                    display_order=step_dto.display_order,
                    parent_step_id=step_dto.parent_step_id,
                    path=f"/{step_dto.code}",
                    ui_metadata_json=step_dto.ui_metadata_json,
                    created_by=user_id,
                    updated_by=user_id,
                )
                self.step_repo.add(s)
                result.append(s)

        # version bump은 위의 atomic CAS에서 처리 완료
        await self.session.flush()

        # Outbox 이벤트 발행
        await publish_process_event(
            self.session,
            event_type="process.steps.bulk_upserted",
            aggregate_type="PROCESS_VERSION",
            aggregate_id=str(version.id),
            tenant_id=tenant_id,
            payload={
                "versionId": str(version.id),
                "processDefinitionId": str(def_id),
                "steps": [
                    {"id": str(s.id), "code": s.code, "name": s.name,
                     "stepType": s.step_type, "displayOrder": s.display_order}
                    for s in result
                ],
            },
        )
        return result
