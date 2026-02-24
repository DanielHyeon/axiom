"""DDD-P3-04: 프로세스 시작 Saga — 3단계 정방향 오케스트레이션.

Steps:
  1. create_process_instance  — ProcessInstance 및 RoleBinding 생성
  2. create_initial_workitem  — 초기 WorkItem 생성
  3. publish_process_initiated — PROCESS_INITIATED 이벤트 Outbox 기록

실패 시 완료된 단계를 역순으로 자동 보상한다.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import EventPublisher
from app.core.event_contract_registry import EventContractError
from app.domain.services.saga_orchestrator import SagaOrchestrator, SagaResult, SagaStep
from app.models.base_models import ProcessDefinition, WorkItem as WorkItemORM
from app.modules.process.domain.aggregates.work_item import (
    AgentMode,
    WorkItem as WorkItemAggregate,
    WorkItemStatus,
)
from app.modules.process.infrastructure.bpm.engine import get_initial_activity
from app.modules.process.infrastructure.mappers.work_item_mapper import WorkItemMapper
from app.modules.process.application.role_binding_service import RoleBindingService

logger = logging.getLogger("axiom.saga")
_mapper = WorkItemMapper()


async def _noop(ctx: dict) -> None:
    """이벤트 발행 보상은 no-op (멱등)."""
    pass


async def create_start_process_saga(
    db: AsyncSession,
    proc_def_id: str,
    tenant_id: str,
    role_bindings: list[dict] | None = None,
    input_data: dict | None = None,
) -> SagaResult:
    """프로세스 시작 Saga를 구성하고 실행한다.

    Returns:
        SagaResult with context containing:
            - proc_inst_id
            - workitem_id
            - activity_name
    """

    # ── Step 1: Create Process Instance ──────────────

    async def _create_instance(ctx: dict) -> dict[str, Any]:
        """ProcessInstance(proc_inst_id) 및 RoleBinding 생성."""
        result = await db.execute(
            select(ProcessDefinition).where(
                ProcessDefinition.id == proc_def_id,
                ProcessDefinition.tenant_id == tenant_id,
            )
        )
        proc_def = result.scalar_one_or_none()
        if not proc_def:
            raise ValueError(f"ProcessDefinition not found: {proc_def_id}")

        proc_inst_id = str(uuid.uuid4())
        ctx["proc_def"] = proc_def

        if role_bindings:
            await RoleBindingService.bind(
                db=db,
                proc_inst_id=proc_inst_id,
                role_bindings=role_bindings,
                tenant_id=tenant_id,
            )

        return {"proc_inst_id": proc_inst_id}

    async def _compensate_instance(ctx: dict) -> None:
        """인스턴스 보상: RoleBinding 삭제 (WorkItem은 아직 없음)."""
        from app.models.base_models import ProcessRoleBinding
        proc_inst_id = ctx.get("proc_inst_id")
        if not proc_inst_id:
            return
        result = await db.execute(
            select(ProcessRoleBinding).where(ProcessRoleBinding.proc_inst_id == proc_inst_id)
        )
        for rb in result.scalars().all():
            await db.delete(rb)
        await db.flush()

    # ── Step 2: Create Initial WorkItem ──────────────

    async def _create_workitem(ctx: dict) -> dict[str, Any]:
        """초기 WorkItem 생성."""
        proc_def = ctx.get("proc_def")
        definition = (proc_def.definition or {}) if proc_def else {}
        initial_spec = get_initial_activity(definition)

        seed_activity = (input_data or {}).get("initial_activity_name") or initial_spec["activity_name"]
        assignee_id = None
        if role_bindings:
            assignee_id = next((item.get("user_id") for item in role_bindings if item.get("user_id")), None)

        workitem_id = str(uuid.uuid4())
        wi = WorkItemAggregate.create(
            id=workitem_id,
            proc_inst_id=ctx["proc_inst_id"],
            activity_name=seed_activity,
            activity_type=initial_spec["activity_type"],
            assignee_id=assignee_id,
            agent_mode=AgentMode(initial_spec["agent_mode"]),
            tenant_id=tenant_id,
            result_data={"proc_def_id": proc_def_id, "input": input_data or {}},
        )
        orm = _mapper.to_new_orm(wi)
        db.add(orm)
        await db.flush()

        # Drain domain events
        for _ in wi.collect_events():
            pass

        return {
            "workitem_id": workitem_id,
            "activity_name": seed_activity,
            "assignee_id": assignee_id,
        }

    async def _compensate_workitem(ctx: dict) -> None:
        """WorkItem 보상: CANCELLED 처리."""
        workitem_id = ctx.get("workitem_id")
        if not workitem_id:
            return
        result = await db.execute(
            select(WorkItemORM).where(WorkItemORM.id == workitem_id)
        )
        orm = result.scalar_one_or_none()
        if orm and orm.status != WorkItemStatus.CANCELLED.value:
            wi = _mapper.to_domain(orm)
            wi.force_cancel()
            _mapper.to_orm(wi, orm)
            await db.flush()

    # ── Step 3: Publish PROCESS_INITIATED Event ──────

    async def _publish_event(ctx: dict) -> dict[str, Any] | None:
        """PROCESS_INITIATED 이벤트를 Outbox에 기록."""
        await EventPublisher.publish(
            session=db,
            event_type="PROCESS_INITIATED",
            aggregate_type="process",
            aggregate_id=ctx["proc_inst_id"],
            payload={
                "proc_def_id": proc_def_id,
                "workitem_id": ctx["workitem_id"],
            },
            tenant_id=tenant_id,
        )
        return None

    # ── Orchestrate ──────────────────────────────────

    saga = SagaOrchestrator(
        name="start_process",
        steps=[
            SagaStep(
                name="create_process_instance",
                execute=_create_instance,
                compensate=_compensate_instance,
            ),
            SagaStep(
                name="create_initial_workitem",
                execute=_create_workitem,
                compensate=_compensate_workitem,
            ),
            SagaStep(
                name="publish_process_initiated",
                execute=_publish_event,
                compensate=_noop,
            ),
        ],
    )

    # DB session을 context에 포함 (보상 실패 시 Watch 알림용)
    context = {
        "tenant_id": tenant_id,
        "proc_def_id": proc_def_id,
        "_db": db,
    }

    result = await saga.execute(db, context)

    # _db는 외부 노출하지 않음
    result.context.pop("_db", None)
    result.context.pop("proc_def", None)

    return result
