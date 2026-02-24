"""Process Service — Backward-compatible facade delegating to split application services.

This file exists for backward compatibility. New code should import directly from:
- app.application.definition_service.DefinitionService
- app.application.workitem_lifecycle_service.WorkItemLifecycleService
- app.application.process_instance_service.ProcessInstanceService
- app.application.role_binding_service.RoleBindingService
"""
from __future__ import annotations

from typing import Optional, Dict

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.process.application.definition_service import DefinitionService
from app.modules.process.application.workitem_lifecycle_service import WorkItemLifecycleService
from app.modules.process.application.process_instance_service import ProcessInstanceService
from app.modules.process.application.role_binding_service import RoleBindingService

# Re-export domain types for backward compatibility
from app.modules.process.domain.aggregates.work_item import AgentMode, WorkItemStatus


class ProcessDomainError(Exception):
    """Backward-compatible error class. Identical to application service errors."""
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class WorkItemUpdateModel(BaseModel):
    workitem_id: str
    result_data: Optional[Dict] = None


class ProcessService:
    """Facade that delegates to focused application services.

    Each @staticmethod maps 1:1 to the split services.
    Catches their ProcessDomainError and re-raises as this module's ProcessDomainError
    to maintain import compatibility for existing routes and tests.
    """

    # ── Definition CRUD ──────────────────────────────────

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
        try:
            return await DefinitionService.create(
                db, tenant_id, name, source, definition_type, description, activities_hint, bpmn_xml
            )
        except Exception as e:
            _reraise_if_domain_error(e)
            raise

    @staticmethod
    async def list_definitions(db: AsyncSession, tenant_id: str, cursor: str | None, limit: int, sort: str) -> dict:
        try:
            return await DefinitionService.list(db, tenant_id, cursor, limit, sort)
        except Exception as e:
            _reraise_if_domain_error(e)
            raise

    @staticmethod
    async def get_definition(db: AsyncSession, tenant_id: str, proc_def_id: str) -> dict:
        try:
            return await DefinitionService.get(db, tenant_id, proc_def_id)
        except Exception as e:
            _reraise_if_domain_error(e)
            raise

    # ── Process Instance ─────────────────────────────────

    @staticmethod
    async def initiate_process(
        db: AsyncSession,
        proc_def_id: str,
        input_data: Optional[dict] = None,
        role_bindings: Optional[list[dict]] = None,
    ) -> dict:
        try:
            return await ProcessInstanceService.initiate(db, proc_def_id, input_data, role_bindings)
        except Exception as e:
            _reraise_if_domain_error(e)
            raise

    @staticmethod
    async def get_process_status(db: AsyncSession, proc_inst_id: str) -> dict:
        try:
            return await ProcessInstanceService.get_status(db, proc_inst_id)
        except Exception as e:
            _reraise_if_domain_error(e)
            raise

    @staticmethod
    async def get_workitems(
        db: AsyncSession,
        proc_inst_id: str,
        status: Optional[str] = None,
        agent_mode: Optional[str] = None,
    ) -> list[dict]:
        try:
            return await ProcessInstanceService.get_workitems(db, proc_inst_id, status, agent_mode)
        except Exception as e:
            _reraise_if_domain_error(e)
            raise

    @staticmethod
    async def terminate_process_instance(db: AsyncSession, proc_inst_id: str) -> None:
        try:
            return await ProcessInstanceService.terminate(db, proc_inst_id)
        except Exception as e:
            _reraise_if_domain_error(e)
            raise

    @staticmethod
    async def get_completed_workitems_for_compensation(
        db: AsyncSession, proc_inst_id: str, before_workitem_id: str
    ):
        return await ProcessInstanceService.get_completed_for_compensation(
            db, proc_inst_id, before_workitem_id
        )

    # ── WorkItem Lifecycle ───────────────────────────────

    @staticmethod
    async def submit_workitem(
        db: AsyncSession,
        item_id: str,
        submit_data: dict,
        force_complete: bool = False,
    ) -> dict:
        try:
            return await WorkItemLifecycleService.submit(db, item_id, submit_data, force_complete)
        except Exception as e:
            _reraise_if_domain_error(e)
            raise

    @staticmethod
    async def approve_hitl(db: AsyncSession, item_id: str, approved: bool, feedback: str = "") -> dict:
        try:
            return await WorkItemLifecycleService.approve_hitl(db, item_id, approved, feedback)
        except Exception as e:
            _reraise_if_domain_error(e)
            raise

    @staticmethod
    async def get_feedback(db: AsyncSession, workitem_id: str) -> dict:
        try:
            return await WorkItemLifecycleService.get_feedback(db, workitem_id)
        except Exception as e:
            _reraise_if_domain_error(e)
            raise

    @staticmethod
    async def list_workitems(
        db: AsyncSession,
        tenant_id: str,
        status: Optional[str] = None,
        assignee_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict:
        try:
            return await WorkItemLifecycleService.list(db, tenant_id, status, assignee_id, limit, offset)
        except Exception as e:
            _reraise_if_domain_error(e)
            raise

    @staticmethod
    async def rework_workitem(
        db: AsyncSession, item_id: str, reason: str, revert_to_activity_id: Optional[str] = None
    ) -> dict:
        try:
            return await WorkItemLifecycleService.rework(db, item_id, reason, revert_to_activity_id)
        except Exception as e:
            _reraise_if_domain_error(e)
            raise

    # ── Role Binding ─────────────────────────────────────

    @staticmethod
    async def bind_roles(
        db: AsyncSession,
        proc_inst_id: str,
        role_bindings: list[dict],
        tenant_id: str,
    ) -> dict:
        try:
            return await RoleBindingService.bind(db, proc_inst_id, role_bindings, tenant_id)
        except Exception as e:
            _reraise_if_domain_error(e)
            raise


def _reraise_if_domain_error(exc: Exception) -> None:
    """Convert application-layer ProcessDomainError to this module's ProcessDomainError."""
    if hasattr(exc, "status_code") and hasattr(exc, "code") and hasattr(exc, "message"):
        raise ProcessDomainError(exc.status_code, exc.code, exc.message) from exc
