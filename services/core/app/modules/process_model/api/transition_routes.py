"""
프로세스 전이 API — /api/v1/process/transitions/*.

Phase 2.5: step_transition_edges CRUD 3개 엔드포인트.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import get_current_user
from app.modules.process_model.application.transition_service import TransitionService
from app.modules.process_model.domain.errors import ProcessModelError

router = APIRouter(prefix="/process", tags=["process-transitions"])


class TransitionItem(BaseModel):
    from_step_id: UUID
    to_step_id: UUID
    transition_type: str
    condition_expression: str | None = None
    is_default: bool = False
    display_order: int = 0
    metadata_json: dict | None = None


class BulkUpsertTransitionsRequest(BaseModel):
    expected_version: int  # CAS — 클라이언트가 본 process_version.version
    transitions: list[TransitionItem]


class TransitionResponse(BaseModel):
    id: UUID
    process_version_id: UUID
    from_step_id: UUID
    to_step_id: UUID
    transition_type: str
    condition_expression: str | None
    is_default: bool
    display_order: int
    created_at: datetime
    model_config = {"from_attributes": True}


@router.post("/versions/{version_id}/transitions:bulk-upsert")
async def bulk_upsert_transitions(
    version_id: UUID,
    body: BulkUpsertTransitionsRequest,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """전이 일괄 저장 — 기존 전이를 soft delete 후 새로 생성."""
    svc = TransitionService(session)
    try:
        transitions_data = [t.model_dump() for t in body.transitions]
        edges = await svc.bulk_upsert(
            user["tenant_id"], version_id, body.expected_version, transitions_data,
        )
        await session.commit()
        return {"success": True, "data": [TransitionResponse.model_validate(e) for e in edges]}
    except ProcessModelError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail={"code": e.code, "message": e.message, "failures": getattr(e, "failures", None)},
        )


@router.get("/versions/{version_id}/transitions")
async def list_transitions(
    version_id: UUID,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """version의 전이 목록."""
    svc = TransitionService(session)
    edges = await svc.list_transitions(user["tenant_id"], version_id)
    return {"success": True, "data": [TransitionResponse.model_validate(e) for e in edges]}


@router.delete("/transitions/{transition_id}", status_code=204)
async def delete_transition(
    transition_id: UUID,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """전이 삭제 (soft delete)."""
    svc = TransitionService(session)
    await svc.delete_transition(user["tenant_id"], transition_id)
    await session.commit()
