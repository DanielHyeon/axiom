"""Role Binding Application Service — manage process role assignments."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base_models import ProcessRoleBinding


class ProcessDomainError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class RoleBindingService:
    """Application service for process role bindings."""

    @staticmethod
    async def bind(
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
