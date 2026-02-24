"""Process Instance Application Service — initiation, status, termination."""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base_models import ProcessDefinition, ProcessRoleBinding
from app.models.base_models import WorkItem as WorkItemORM
from app.core.events import EventPublisher
from app.core.event_contract_registry import EventContractError
from app.modules.process.infrastructure.bpm.engine import get_initial_activity
from app.modules.process.domain.aggregates.work_item import (
    AgentMode,
    WorkItem as WorkItemAggregate,
    WorkItemStatus,
)
from app.modules.process.infrastructure.mappers.work_item_mapper import WorkItemMapper
from app.modules.process.application.role_binding_service import RoleBindingService

_mapper = WorkItemMapper()


class ProcessDomainError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class ProcessInstanceService:
    """Application service for process instance lifecycle."""

    @staticmethod
    async def initiate(
        db: AsyncSession,
        proc_def_id: str,
        input_data: Optional[dict] = None,
        role_bindings: Optional[list[dict]] = None,
    ) -> dict:
        if not proc_def_id:
            raise ProcessDomainError(404, "PROCESS_DEFINITION_NOT_FOUND", "proc_def_id is required")
        if not role_bindings:
            raise ProcessDomainError(400, "MISSING_ROLE_BINDINGS", "role_bindings is required")

        tenant_id = (input_data or {}).get("tenant_id", "default")
        result = await db.execute(
            select(ProcessDefinition).where(
                ProcessDefinition.id == proc_def_id,
                ProcessDefinition.tenant_id == tenant_id,
            )
        )
        proc_def_row = result.scalar_one_or_none()
        if not proc_def_row:
            raise ProcessDomainError(404, "PROCESS_DEFINITION_NOT_FOUND", "process definition not found")

        definition = getattr(proc_def_row, "definition", None) or {}
        initial_spec = get_initial_activity(definition)
        seed_activity = (input_data or {}).get("initial_activity_name") or initial_spec["activity_name"]
        assignee_id = next((item.get("user_id") for item in role_bindings if item.get("user_id")), None)

        proc_inst_id = str(uuid.uuid4())
        workitem_id = str(uuid.uuid4())

        await RoleBindingService.bind(
            db=db, proc_inst_id=proc_inst_id, role_bindings=role_bindings, tenant_id=tenant_id
        )

        wi = WorkItemAggregate.create(
            id=workitem_id,
            proc_inst_id=proc_inst_id,
            activity_name=seed_activity,
            activity_type=initial_spec["activity_type"],
            assignee_id=assignee_id,
            agent_mode=AgentMode(initial_spec["agent_mode"]),
            tenant_id=tenant_id,
            result_data={"proc_def_id": proc_def_id, "input": input_data or {}},
        )
        orm = _mapper.to_new_orm(wi)
        db.add(orm)

        try:
            await EventPublisher.publish(
                session=db,
                event_type="PROCESS_INITIATED",
                aggregate_type="process",
                aggregate_id=proc_inst_id,
                payload={"proc_def_id": proc_def_id, "workitem_id": workitem_id},
            )
        except EventContractError as err:
            raise ProcessDomainError(422, err.code, err.message)

        # Drain WorkItem domain events
        for event in wi.collect_events():
            pass  # silently consume creation events

        return {
            "proc_inst_id": proc_inst_id,
            "status": "RUNNING",
            "current_workitems": [
                {
                    "workitem_id": workitem_id,
                    "activity_name": seed_activity,
                    "activity_type": "humanTask",
                    "assignee_id": assignee_id,
                    "agent_mode": "MANUAL",
                    "status": WorkItemStatus.TODO,
                    "created_at": orm.created_at.isoformat() if orm.created_at else None,
                }
            ],
        }

    @staticmethod
    async def get_status(db: AsyncSession, proc_inst_id: str) -> dict:
        result = await db.execute(
            select(WorkItemORM).where(WorkItemORM.proc_inst_id == proc_inst_id)
        )
        workitems = result.scalars().all()
        if not workitems:
            raise ProcessDomainError(404, "PROCESS_INSTANCE_NOT_FOUND", "Process instance not found")

        states = {w.status for w in workitems}
        if WorkItemStatus.REWORK.value in states:
            status = "REWORK"
        elif states == {WorkItemStatus.DONE.value}:
            status = "COMPLETED"
        else:
            status = "RUNNING"

        return {
            "proc_inst_id": proc_inst_id,
            "status": status,
            "workitem_count": len(workitems),
        }

    @staticmethod
    async def get_workitems(
        db: AsyncSession,
        proc_inst_id: str,
        status: Optional[str] = None,
        agent_mode: Optional[str] = None,
    ) -> list[dict]:
        stmt = select(WorkItemORM).where(WorkItemORM.proc_inst_id == proc_inst_id)
        if status:
            stmt = stmt.where(WorkItemORM.status == status)
        if agent_mode:
            stmt = stmt.where(WorkItemORM.agent_mode == agent_mode)

        result = await db.execute(stmt)
        workitems = result.scalars().all()
        if not workitems:
            raise ProcessDomainError(404, "PROCESS_INSTANCE_NOT_FOUND", "Process instance not found")

        return [
            {
                "workitem_id": item.id,
                "activity_name": item.activity_name,
                "activity_type": item.activity_type,
                "assignee_id": item.assignee_id,
                "agent_mode": item.agent_mode,
                "status": item.status,
                "result_data": item.result_data,
            }
            for item in workitems
        ]

    @staticmethod
    async def terminate(db: AsyncSession, proc_inst_id: str) -> None:
        result = await db.execute(
            select(WorkItemORM).where(
                WorkItemORM.proc_inst_id == proc_inst_id,
                WorkItemORM.status.in_([
                    WorkItemStatus.TODO.value,
                    WorkItemStatus.IN_PROGRESS.value,
                    WorkItemStatus.SUBMITTED.value,
                ]),
            )
        )
        for orm in result.scalars().all():
            wi = _mapper.to_domain(orm)
            wi.force_cancel()
            _mapper.to_orm(wi, orm)
        await db.flush()

    @staticmethod
    async def get_completed_for_compensation(
        db: AsyncSession,
        proc_inst_id: str,
        before_workitem_id: str,
    ) -> list[WorkItemORM]:
        result = await db.execute(
            select(WorkItemORM).where(WorkItemORM.id == before_workitem_id)
        )
        before_item = result.scalar_one_or_none()
        if not before_item or before_item.proc_inst_id != proc_inst_id:
            return []
        result = await db.execute(
            select(WorkItemORM)
            .where(
                WorkItemORM.proc_inst_id == proc_inst_id,
                WorkItemORM.status == WorkItemStatus.DONE.value,
                WorkItemORM.created_at < before_item.created_at,
            )
            .order_by(WorkItemORM.created_at.asc())
        )
        return list(result.scalars().all())
