"""ORM ↔ Domain mapper for WorkItem Aggregate."""
from __future__ import annotations

from app.modules.process.domain.aggregates.work_item import AgentMode, WorkItem, WorkItemStatus
from app.models.base_models import WorkItem as WorkItemORM


class WorkItemMapper:
    """Bidirectional mapper between WorkItem domain aggregate and SQLAlchemy ORM."""

    @staticmethod
    def to_domain(orm: WorkItemORM) -> WorkItem:
        return WorkItem(
            id=orm.id,
            proc_inst_id=orm.proc_inst_id,
            activity_name=orm.activity_name,
            activity_type=orm.activity_type or "humanTask",
            assignee_id=orm.assignee_id,
            agent_mode=AgentMode(orm.agent_mode or "MANUAL"),
            status=WorkItemStatus(orm.status),
            result_data=orm.result_data,
            tenant_id=orm.tenant_id,
            version=orm.version or 1,
        )

    @staticmethod
    def to_orm(domain: WorkItem, orm: WorkItemORM) -> None:
        """Update an existing ORM instance from domain state."""
        orm.status = domain.status.value
        orm.result_data = domain.result_data
        orm.version = domain.version
        orm.agent_mode = domain.agent_mode.value
        orm.assignee_id = domain.assignee_id

    @staticmethod
    def to_new_orm(domain: WorkItem) -> WorkItemORM:
        """Create a new ORM instance from domain state."""
        return WorkItemORM(
            id=domain.id,
            proc_inst_id=domain.proc_inst_id,
            activity_name=domain.activity_name,
            activity_type=domain.activity_type,
            assignee_id=domain.assignee_id,
            agent_mode=domain.agent_mode.value,
            status=domain.status.value,
            result_data=domain.result_data,
            tenant_id=domain.tenant_id,
            version=domain.version,
        )
