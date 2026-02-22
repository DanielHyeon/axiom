import enum
import uuid
from typing import Optional, Dict
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import asc, desc, func, select
from app.models.base_models import ProcessDefinition, ProcessRoleBinding, WorkItem
from app.core.events import EventPublisher
from app.core.event_contract_registry import EventContractError
from app.core.self_verification import self_verification_harness


class ProcessDomainError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class WorkItemStatus(str, enum.Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    SUBMITTED = "SUBMITTED"
    DONE = "DONE"
    REWORK = "REWORK"
    CANCELLED = "CANCELLED"

class AgentMode(str, enum.Enum):
    MANUAL = "MANUAL"
    SUPERVISED = "SUPERVISED"
    AUTONOMOUS = "AUTONOMOUS"
    SELF_VERIFY = "SELF_VERIFY"

class WorkItemUpdateModel(BaseModel):
    workitem_id: str
    result_data: Optional[Dict] = None

class ProcessService:
    @staticmethod
    async def bind_roles(
        db: AsyncSession,
        proc_inst_id: str,
        role_bindings: list[dict],
        tenant_id: str,
    ) -> dict:
        if not proc_inst_id:
            raise ProcessDomainError(400, "MISSING_PROC_INST_ID", "proc_inst_id is required")
        if not role_bindings:
            raise ProcessDomainError(400, "MISSING_ROLE_BINDINGS", "role_bindings is required")

        deleted = await db.execute(
            select(ProcessRoleBinding).where(
                ProcessRoleBinding.proc_inst_id == proc_inst_id,
                ProcessRoleBinding.tenant_id == tenant_id,
            )
        )
        for item in deleted.scalars().all():
            await db.delete(item)

        created = []
        for binding in role_bindings:
            role_name = (binding or {}).get("role_name")
            if not role_name:
                raise ProcessDomainError(400, "MISSING_ROLE_NAME", "role_name is required")
            entry = ProcessRoleBinding(
                proc_inst_id=proc_inst_id,
                role_name=role_name,
                user_id=(binding or {}).get("user_id"),
                tenant_id=tenant_id,
            )
            db.add(entry)
            created.append(entry)
        await db.flush()
        return {
            "proc_inst_id": proc_inst_id,
            "role_bindings": [
                {"role_name": item.role_name, "user_id": item.user_id}
                for item in created
            ],
        }

    @staticmethod
    async def get_feedback(db: AsyncSession, workitem_id: str) -> dict:
        result = await db.execute(select(WorkItem).where(WorkItem.id == workitem_id))
        workitem = result.scalar_one_or_none()
        if not workitem:
            raise ProcessDomainError(404, "WORKITEM_NOT_FOUND", "WorkItem not found")

        feedback = (workitem.result_data or {}).get("hitl_feedback")
        if not feedback:
            raise ProcessDomainError(404, "FEEDBACK_NOT_FOUND", "Feedback not found")

        return {
            "workitem_id": workitem.id,
            "feedback": feedback,
            "status": workitem.status,
        }

    @staticmethod
    async def create_definition(
        db: AsyncSession,
        tenant_id: str,
        name: str,
        source: str,
        definition_type: str = "base",
        description: Optional[str] = None,
        activities_hint: Optional[list[str]] = None,
        bpmn_xml: Optional[str] = None,
    ) -> dict:
        if source not in {"natural_language", "bpmn_upload"}:
            raise ProcessDomainError(400, "INVALID_SOURCE", "source must be natural_language|bpmn_upload")
        if source == "natural_language" and not description:
            raise ProcessDomainError(400, "MISSING_DESCRIPTION", "description is required for natural_language")
        if source == "bpmn_upload" and not bpmn_xml:
            raise ProcessDomainError(400, "MISSING_BPMN_XML", "bpmn_xml is required for bpmn_upload")

        activities_count = len(activities_hint or [])
        if source == "natural_language" and activities_count == 0:
            activities_count = max(1, description.count(",") + 1) if description else 1
        gateways_count = 1 if source == "natural_language" else 0
        confidence = 0.87 if source == "natural_language" else 1.0
        needs_review = source == "natural_language"

        normalized_definition = {
            "name": name,
            "source": source,
            "description": description,
            "activities_hint": activities_hint or [],
            "activities_count": activities_count,
            "gateways_count": gateways_count,
        }
        saved_bpmn_xml = bpmn_xml or "<bpmn:definitions/>"

        definition = ProcessDefinition(
            name=name,
            description=description,
            version=1,
            type=definition_type,
            source=source,
            definition=normalized_definition,
            bpmn_xml=saved_bpmn_xml,
            confidence=confidence,
            needs_review=needs_review,
            tenant_id=tenant_id,
        )
        db.add(definition)
        await db.flush()

        return {
            "proc_def_id": definition.id,
            "name": definition.name,
            "version": definition.version,
            "activities_count": activities_count,
            "gateways_count": gateways_count,
            "definition": definition.definition,
            "bpmn_xml": definition.bpmn_xml,
            "confidence": definition.confidence,
            "needs_review": definition.needs_review,
        }

    @staticmethod
    async def list_definitions(
        db: AsyncSession,
        tenant_id: str,
        cursor: str | None,
        limit: int,
        sort: str,
    ) -> dict:
        safe_limit = min(max(limit, 1), 100)
        sort_field, sort_order = ("created_at", "desc")
        if ":" in sort:
            sort_field, sort_order = sort.split(":", 1)
        if sort_field not in {"created_at", "name"}:
            raise ProcessDomainError(400, "INVALID_SORT", "sort field must be created_at|name")
        if sort_order not in {"asc", "desc"}:
            raise ProcessDomainError(400, "INVALID_SORT_ORDER", "sort order must be asc|desc")

        order_column = ProcessDefinition.created_at if sort_field == "created_at" else ProcessDefinition.name
        order_expr = desc(order_column) if sort_order == "desc" else asc(order_column)

        stmt = select(ProcessDefinition).where(ProcessDefinition.tenant_id == tenant_id)
        if cursor:
            cursor_row = await db.execute(
                select(ProcessDefinition).where(
                    ProcessDefinition.id == cursor,
                    ProcessDefinition.tenant_id == tenant_id,
                )
            )
            item = cursor_row.scalar_one_or_none()
            if item:
                cursor_value = item.created_at if sort_field == "created_at" else item.name
                if sort_order == "desc":
                    stmt = stmt.where(order_column < cursor_value)
                else:
                    stmt = stmt.where(order_column > cursor_value)

        stmt = stmt.order_by(order_expr, ProcessDefinition.id).limit(safe_limit + 1)
        result = await db.execute(stmt)
        rows = result.scalars().all()
        has_more = len(rows) > safe_limit
        page = rows[:safe_limit]
        next_cursor = page[-1].id if has_more and page else None

        total_result = await db.execute(
            select(func.count()).select_from(ProcessDefinition).where(ProcessDefinition.tenant_id == tenant_id)
        )
        total_count = total_result.scalar_one() or 0

        return {
            "data": [
                {
                    "proc_def_id": row.id,
                    "name": row.name,
                    "version": row.version,
                    "type": row.type,
                    "source": row.source,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in page
            ],
            "cursor": {"next": next_cursor, "has_more": has_more},
            "total_count": total_count,
        }

    @staticmethod
    async def initiate_process(
        db: AsyncSession,
        proc_def_id: str,
        input_data: Optional[dict] = None,
        role_bindings: Optional[list[dict]] = None,
    ) -> dict:
        if not proc_def_id:
            raise ProcessDomainError(404, "PROCESS_DEFINITION_NOT_FOUND", "proc_def_id is required")
        if not role_bindings:
            raise ProcessDomainError(400, "MISSING_ROLE_BINDINGS", "role_bindings is required")

        proc_def = await db.execute(
            select(ProcessDefinition).where(
                ProcessDefinition.id == proc_def_id,
                ProcessDefinition.tenant_id == (input_data or {}).get("tenant_id", "default"),
            )
        )
        if not proc_def.scalar_one_or_none():
            raise ProcessDomainError(404, "PROCESS_DEFINITION_NOT_FOUND", "process definition not found")

        proc_inst_id = str(uuid.uuid4())
        workitem_id = str(uuid.uuid4())
        seed_activity = (input_data or {}).get("initial_activity_name", "Initial Review")
        tenant_id = (input_data or {}).get("tenant_id", "default")
        assignee_id = next((item.get("user_id") for item in role_bindings if item.get("user_id")), None)
        await ProcessService.bind_roles(db=db, proc_inst_id=proc_inst_id, role_bindings=role_bindings, tenant_id=tenant_id)

        workitem = WorkItem(
            id=workitem_id,
            proc_inst_id=proc_inst_id,
            activity_name=seed_activity,
            activity_type="humanTask",
            assignee_id=assignee_id,
            agent_mode="MANUAL",
            status=WorkItemStatus.TODO,
            tenant_id=tenant_id,
            result_data={"proc_def_id": proc_def_id, "input": input_data or {}},
            version=1,
        )
        db.add(workitem)
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
                    "created_at": workitem.created_at.isoformat() if workitem.created_at else None,
                }
            ],
        }

    @staticmethod
    async def submit_workitem(
        db: AsyncSession,
        item_id: str,
        submit_data: dict,
        force_complete: bool = False,
    ) -> dict:
        """
        Submits a workitem, advancing its state depending on the agent_mode.
        For MANUAL mode: TODO -> IN_PROGRESS -> DONE
        For SUPERVISED mode: IN_PROGRESS -> SUBMITTED
        """
        result = await db.execute(select(WorkItem).where(WorkItem.id == item_id))
        workitem = result.scalar_one_or_none()

        if not workitem:
            raise ProcessDomainError(404, "WORKITEM_NOT_FOUND", "WorkItem not found")

        if workitem.status in [WorkItemStatus.DONE, WorkItemStatus.CANCELLED]:
            raise ProcessDomainError(409, "ALREADY_COMPLETED", f"Cannot submit in state {workitem.status}")

        if workitem.status == WorkItemStatus.SUBMITTED and not force_complete:
            raise ProcessDomainError(422, "INVALID_STATE_TRANSITION", "SUBMITTED requires approve-hitl")

        verification_outcome = self_verification_harness.evaluate(
            workitem_id=item_id,
            payload=submit_data if isinstance(submit_data, dict) else {},
            agent_mode=workitem.agent_mode,
        )
        if verification_outcome.decision == "FAIL_ROUTE":
            workitem.status = WorkItemStatus.SUBMITTED
            body = submit_data.get("result_data", submit_data)
            if not isinstance(body, dict):
                body = {"value": body}
            body["self_verification"] = verification_outcome.as_dict()
            workitem.result_data = body
            workitem.version += 1
            try:
                await EventPublisher.publish(
                    session=db,
                    event_type="WORKITEM_SELF_VERIFICATION_FAILED",
                    aggregate_type="workitem",
                    aggregate_id=item_id,
                    payload={"reason": verification_outcome.reason, "result": body},
                )
            except EventContractError as err:
                raise ProcessDomainError(422, err.code, err.message)
            return {
                "workitem_id": item_id,
                "status": WorkItemStatus.SUBMITTED,
                "next_workitems": [],
                "process_status": "RUNNING",
                "is_process_completed": False,
                "self_verification": verification_outcome.as_dict(),
            }

        # Basic state transition logic
        next_status = WorkItemStatus.DONE
        workitem.status = next_status
        body = submit_data.get("result_data", submit_data)
        if not isinstance(body, dict):
            body = {"value": body}
        if verification_outcome.decision == "PASS":
            body["self_verification"] = verification_outcome.as_dict()
        workitem.result_data = body
        workitem.version += 1
        next_workitems: list[dict] = []
        process_status = "COMPLETED"
        is_process_completed = True

        if not force_complete:
            next_item = WorkItem(
                id=str(uuid.uuid4()),
                proc_inst_id=workitem.proc_inst_id,
                activity_name="데이터 수치 검증",
                activity_type="serviceTask",
                assignee_id=None,
                agent_mode="SUPERVISED",
                status=WorkItemStatus.TODO,
                tenant_id=workitem.tenant_id,
                result_data={},
                version=1,
            )
            db.add(next_item)
            next_workitems = [
                {
                    "workitem_id": next_item.id,
                    "activity_name": next_item.activity_name,
                    "activity_type": next_item.activity_type,
                    "agent_mode": next_item.agent_mode,
                    "status": next_item.status,
                }
            ]
            process_status = "RUNNING"
            is_process_completed = False

        # Insert event into outbox atomically
        try:
            await EventPublisher.publish(
                session=db,
                event_type="WORKITEM_COMPLETED",
                aggregate_type="workitem",
                aggregate_id=item_id,
                payload={"result": workitem.result_data}
            )
        except EventContractError as err:
            raise ProcessDomainError(422, err.code, err.message)
        
        # Explicit commit expected to be handled by caller/router
        
        return {
            "workitem_id": item_id,
            "status": next_status,
            "next_workitems": next_workitems,
            "process_status": process_status,
            "is_process_completed": is_process_completed,
        }

    @staticmethod
    async def approve_hitl(db: AsyncSession, item_id: str, approved: bool, feedback: str = "") -> dict:
        if not approved and not feedback:
            raise ProcessDomainError(400, "MISSING_FEEDBACK", "Feedback is required when rejecting")

        result = await db.execute(select(WorkItem).where(WorkItem.id == item_id))
        workitem = result.scalar_one_or_none()
        if not workitem:
            raise ProcessDomainError(404, "WORKITEM_NOT_FOUND", "WorkItem not found")

        next_status = WorkItemStatus.DONE if approved else WorkItemStatus.REWORK
        workitem.status = next_status
        existing = workitem.result_data or {}
        existing["hitl_feedback"] = feedback
        workitem.result_data = existing
        workitem.version += 1
        return {
            "workitem_id": item_id,
            "status": next_status,
            "approved": approved,
            "feedback_captured": bool(feedback),
            "next_workitems": [],
        }

    @staticmethod
    async def get_process_status(db: AsyncSession, proc_inst_id: str) -> dict:
        result = await db.execute(select(WorkItem).where(WorkItem.proc_inst_id == proc_inst_id))
        workitems = result.scalars().all()
        if not workitems:
            raise ProcessDomainError(404, "PROCESS_INSTANCE_NOT_FOUND", "Process instance not found")

        states = {w.status for w in workitems}
        if WorkItemStatus.REWORK in states:
            status = "REWORK"
        elif states == {WorkItemStatus.DONE}:
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
        stmt = select(WorkItem).where(WorkItem.proc_inst_id == proc_inst_id)
        if status:
            stmt = stmt.where(WorkItem.status == status)
        if agent_mode:
            stmt = stmt.where(WorkItem.agent_mode == agent_mode)

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
    async def rework_workitem(
        db: AsyncSession, item_id: str, reason: str, revert_to_activity_id: Optional[str] = None
    ) -> dict:
        result = await db.execute(select(WorkItem).where(WorkItem.id == item_id))
        workitem = result.scalar_one_or_none()
        if not workitem:
            raise ProcessDomainError(404, "WORKITEM_NOT_FOUND", "WorkItem not found")

        branch_result = await db.execute(select(WorkItem).where(WorkItem.proc_inst_id == workitem.proc_inst_id))
        process_items = branch_result.scalars().all()
        if process_items and all(item.status in [WorkItemStatus.DONE, WorkItemStatus.CANCELLED] for item in process_items):
            raise ProcessDomainError(409, "PROCESS_COMPLETED", "Completed process cannot be reworked")

        workitem.status = WorkItemStatus.TODO
        payload = workitem.result_data or {}
        payload["rework_reason"] = reason
        payload["revert_to_activity_id"] = revert_to_activity_id
        workitem.result_data = payload
        workitem.version += 1
        saga_compensations = []
        for item in process_items:
            if item.id == item_id:
                continue
            if item.status in [WorkItemStatus.DONE, WorkItemStatus.SUBMITTED]:
                item.status = WorkItemStatus.REWORK
                saga_compensations.append(
                    {
                        "activity": item.activity_name or "unknown",
                        "status": "COMPENSATED",
                        "action": "결과 롤백",
                    }
                )
            elif item.status in [WorkItemStatus.TODO, WorkItemStatus.IN_PROGRESS]:
                item.status = WorkItemStatus.CANCELLED
                saga_compensations.append(
                    {
                        "activity": item.activity_name or "unknown",
                        "status": "CANCELLED",
                        "action": "진행 중 작업 취소",
                    }
                )

        return {
            "workitem_id": item_id,
            "status": WorkItemStatus.TODO,
            "reason": reason,
            "reworked_from": revert_to_activity_id or item_id,
            "saga_compensations": saga_compensations,
        }
