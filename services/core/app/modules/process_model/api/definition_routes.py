"""
프로세스 정의 API — /api/v1/process/definitions/* + domains, groups.

Phase 2: 프로세스 정의/버전/Step CRUD + 발행 (19개 엔드포인트 중 13개).
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import get_current_user
from app.modules.process_model.application.definition_service import DefinitionService
from app.modules.process_model.domain.errors import ProcessModelError
from app.modules.process_model.domain.models import ProcessDomain, InterfaceContract, RuleDefinition, KpiDefinition
from app.modules.process_model.domain.schemas import (
    BulkUpsertStepsRequest, InterfaceContractCreate, InterfaceContractResponse,
    KpiDefinitionCreate, KpiDefinitionResponse,
    ProcessDefinitionCreate, ProcessDefinitionResponse, ProcessDefinitionUpdate,
    ProcessDomainCreate, ProcessDomainResponse,
    ProcessVersionResponse, RuleDefinitionCreate, RuleDefinitionResponse,
    StepDefinitionResponse,
)
from app.modules.process_model.infrastructure.repositories import ProcessDomainRepository

router = APIRouter(prefix="/process", tags=["process-model"])


def _handle(e: ProcessModelError):
    raise HTTPException(status_code=e.status_code, detail={"code": e.code, "message": e.message, "failures": getattr(e, "failures", None)})


# ── Domains ────────────────────────────────────────────────

@router.post("/domains", response_model=ProcessDomainResponse, status_code=201)
async def create_domain(
    body: ProcessDomainCreate,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    domain = ProcessDomain(
        tenant_id=user["tenant_id"], workspace_id=body.workspace_id,
        code=body.code, name=body.name, domain_type=body.domain_type,
        description=body.description,
    )
    session.add(domain)
    await session.commit()
    await session.refresh(domain)
    return domain


@router.get("/domains")
async def list_domains(
    workspace_id: UUID = Query(...),
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    repo = ProcessDomainRepository(session)
    items = await repo.find_by_workspace(user["tenant_id"], workspace_id)
    return {"success": True, "data": [ProcessDomainResponse.model_validate(d) for d in items]}


# ── Definitions ────────────────────────────────────────────

@router.post("/definitions", response_model=ProcessDefinitionResponse, status_code=201)
async def create_definition(
    body: ProcessDefinitionCreate,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    svc = DefinitionService(session)
    try:
        proc_def = await svc.create(user["tenant_id"], user["user_id"], body)
        await session.commit()
        return proc_def
    except ProcessModelError as e:
        _handle(e)


@router.get("/definitions")
async def list_definitions(
    domain_id: UUID | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    svc = DefinitionService(session)
    items, total = await svc.list_definitions(user["tenant_id"], domain_id, status, page, page_size)
    return {
        "success": True,
        "data": {
            "items": [ProcessDefinitionResponse.model_validate(d) for d in items],
            "total": total, "page": page, "page_size": page_size,
        },
    }


@router.get("/definitions/{def_id}", response_model=ProcessDefinitionResponse)
async def get_definition(
    def_id: UUID,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    svc = DefinitionService(session)
    try:
        return await svc.get(user["tenant_id"], def_id)
    except ProcessModelError as e:
        _handle(e)


@router.patch("/definitions/{def_id}", response_model=ProcessDefinitionResponse)
async def update_definition(
    def_id: UUID,
    body: ProcessDefinitionUpdate,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    svc = DefinitionService(session)
    try:
        proc_def = await svc.update(user["tenant_id"], user["user_id"], def_id, body)
        await session.commit()
        return proc_def
    except ProcessModelError as e:
        _handle(e)


@router.post("/definitions/{def_id}/publish", response_model=ProcessVersionResponse)
async def publish_definition(
    def_id: UUID,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    svc = DefinitionService(session)
    try:
        version = await svc.publish(user["tenant_id"], user["user_id"], def_id)
        await session.commit()
        return version
    except ProcessModelError as e:
        _handle(e)


# ── Versions ───────────────────────────────────────────────

@router.get("/definitions/{def_id}/versions")
async def list_versions(
    def_id: UUID,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    svc = DefinitionService(session)
    versions = await svc.get_versions(user["tenant_id"], def_id)
    return {"success": True, "data": [ProcessVersionResponse.model_validate(v) for v in versions]}


# ── Steps ──────────────────────────────────────────────────

@router.post("/definitions/{def_id}/versions/{version_no}/steps:bulk-upsert")
async def bulk_upsert_steps(
    def_id: UUID,
    version_no: int,
    body: BulkUpsertStepsRequest,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    svc = DefinitionService(session)
    try:
        steps = await svc.bulk_upsert_steps(user["tenant_id"], user["user_id"], def_id, version_no, body)
        await session.commit()
        return {"success": True, "data": [StepDefinitionResponse.model_validate(s) for s in steps]}
    except ProcessModelError as e:
        _handle(e)


@router.get("/versions/{version_id}/steps")
async def list_steps(
    version_id: UUID,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    from app.modules.process_model.infrastructure.repositories import StepDefinitionRepository
    repo = StepDefinitionRepository(session)
    steps = await repo.find_by_version(user["tenant_id"], version_id)
    return {"success": True, "data": [StepDefinitionResponse.model_validate(s) for s in steps]}


# ── Interfaces / Rules / KPIs (간결 CRUD) ──────────────────

@router.post("/interfaces", response_model=InterfaceContractResponse, status_code=201)
async def create_interface(
    body: InterfaceContractCreate,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    entity = InterfaceContract(
        tenant_id=user["tenant_id"], workspace_id=body.workspace_id,
        code=body.code, name=body.name, contract_type=body.contract_type.value,
        schema_json=body.schema_json, semantic_type=body.semantic_type,
        version_label=body.version_label, created_by=user["user_id"],
    )
    session.add(entity)
    await session.commit()
    await session.refresh(entity)
    return entity


@router.post("/rules", response_model=RuleDefinitionResponse, status_code=201)
async def create_rule(
    body: RuleDefinitionCreate,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    entity = RuleDefinition(
        tenant_id=user["tenant_id"], workspace_id=body.workspace_id,
        code=body.code, name=body.name, rule_type=body.rule_type.value,
        expression_language=body.expression_language,
        expression_text=body.expression_text,
        severity=body.severity, description=body.description,
        created_by=user["user_id"],
    )
    session.add(entity)
    await session.commit()
    await session.refresh(entity)
    return entity


@router.post("/kpis", response_model=KpiDefinitionResponse, status_code=201)
async def create_kpi(
    body: KpiDefinitionCreate,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    entity = KpiDefinition(
        tenant_id=user["tenant_id"], workspace_id=body.workspace_id,
        code=body.code, name=body.name, unit=body.unit,
        target_direction=body.target_direction.value,
        aggregation_type=body.aggregation_type.value,
        formula_text=body.formula_text, created_by=user["user_id"],
    )
    session.add(entity)
    await session.commit()
    await session.refresh(entity)
    return entity
