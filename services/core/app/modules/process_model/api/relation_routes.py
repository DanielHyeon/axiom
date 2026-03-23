"""
프로세스 관계 API — /api/v1/process/relations/*.

Phase 2: 관계 엣지 CRUD (3개 엔드포인트).
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import get_current_user
from app.modules.process_model.domain.errors import ProcessModelError, RelationTypeInvalidError
from app.modules.process_model.domain.models import ProcessRelationEdge
from app.modules.process_model.domain.schemas import ProcessRelationCreate, ProcessRelationResponse
from app.modules.process_model.infrastructure.event_publisher import publish_process_event
from app.modules.process_model.infrastructure.repositories import ProcessRelationRepository

router = APIRouter(prefix="/process", tags=["process-relations"])


@router.post("/relations", response_model=ProcessRelationResponse, status_code=201)
async def create_relation(
    body: ProcessRelationCreate,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """프로세스 관계 엣지 생성."""
    # relation_type 화이트리스트 검증은 enum으로 자동 처리 (Pydantic)
    edge = ProcessRelationEdge(
        tenant_id=user["tenant_id"],
        workspace_id=body.workspace_id,
        source_entity_type=body.source_entity_type,
        source_entity_id=body.source_entity_id,
        target_entity_type=body.target_entity_type,
        target_entity_id=body.target_entity_id,
        relation_type=body.relation_type.value,
        criticality=body.criticality.value,
        propagation_mode=body.propagation_mode,
        weight=body.weight,
        created_by=user["user_id"],
    )
    session.add(edge)
    await session.flush()
    # Outbox 이벤트 발행
    await publish_process_event(
        session,
        event_type="process.relation.created",
        aggregate_type="PROCESS_RELATION",
        aggregate_id=str(edge.id),
        tenant_id=user["tenant_id"],
        payload={
            "edgeId": str(edge.id),
            "sourceId": str(edge.source_entity_id), "targetId": str(edge.target_entity_id),
            "relationType": edge.relation_type, "criticality": edge.criticality,
            "weight": float(edge.weight) if edge.weight else None,
            "workspaceId": str(edge.workspace_id),
            "updatedAt": edge.created_at.isoformat() if edge.created_at else None,
        },
    )
    await session.commit()
    await session.refresh(edge)
    return edge


@router.delete("/relations/{relation_id}", status_code=204)
async def delete_relation(
    relation_id: UUID,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """프로세스 관계 엣지 삭제 (soft delete)."""
    repo = ProcessRelationRepository(session)
    edge = await repo.find_by_id(user["tenant_id"], relation_id)
    if not edge:
        raise HTTPException(status_code=404, detail="Relation not found")
    edge.is_deleted = True
    await publish_process_event(
        session,
        event_type="process.relation.deleted",
        aggregate_type="PROCESS_RELATION",
        aggregate_id=str(relation_id),
        tenant_id=user["tenant_id"],
        payload={"edgeId": str(relation_id)},
    )
    await session.commit()


@router.get("/definitions/{def_id}/relations")
async def list_relations(
    def_id: UUID,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """프로세스의 관계 엣지 목록."""
    repo = ProcessRelationRepository(session)
    edges = await repo.find_by_source(user["tenant_id"], def_id)
    return {"success": True, "data": [ProcessRelationResponse.model_validate(e) for e in edges]}
