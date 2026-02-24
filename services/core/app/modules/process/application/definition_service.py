"""Process Definition Application Service — CRUD operations for process definitions."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base_models import ProcessDefinition
from app.modules.process.domain.errors import DomainError


class ProcessDomainError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class DefinitionService:
    """Application service for ProcessDefinition CRUD."""

    @staticmethod
    async def create(
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
    async def list(
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
    async def get(db: AsyncSession, tenant_id: str, proc_def_id: str) -> dict:
        result = await db.execute(
            select(ProcessDefinition).where(
                ProcessDefinition.id == proc_def_id,
                ProcessDefinition.tenant_id == tenant_id,
            )
        )
        row = result.scalar_one_or_none()
        if not row:
            raise ProcessDomainError(404, "DEFINITION_NOT_FOUND", "Process definition not found")
        return {
            "proc_def_id": row.id,
            "name": row.name,
            "description": row.description,
            "version": row.version,
            "type": row.type,
            "source": row.source,
            "definition": row.definition,
            "bpmn_xml": row.bpmn_xml,
            "confidence": row.confidence,
            "needs_review": row.needs_review,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
