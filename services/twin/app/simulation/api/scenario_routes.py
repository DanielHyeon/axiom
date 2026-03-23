"""
시나리오 API — /api/v1/simulation/*.

Phase 5: 시나리오 CRUD + 실행 + diff + 보정계수 (8개 엔드포인트).
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import get_current_user
from app.simulation.models.scenario import SimulationCoefficient
from app.simulation.models.schemas import (
    CoefficientResponse, CoefficientUpdateRequest,
    CreateScenarioRequest, RunScenarioRequest,
    ScenarioResponse, ScenarioRunResponse,
)
from app.simulation.services.scenario_service import ScenarioService

router = APIRouter(prefix="/api/v1/simulation", tags=["simulation"])


@router.post("/scenarios", response_model=ScenarioResponse, status_code=201)
async def create_scenario(
    body: CreateScenarioRequest,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    svc = ScenarioService(session)
    scenario = await svc.create(user["tenant_id"], body)
    await session.commit()
    return scenario


@router.get("/scenarios")
async def list_scenarios(
    workspace_id: UUID = Query(...),
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    svc = ScenarioService(session)
    items = await svc.list_scenarios(user["tenant_id"], workspace_id)
    return {"success": True, "data": [ScenarioResponse.model_validate(s) for s in items]}


@router.get("/scenarios/{scenario_id}", response_model=ScenarioResponse)
async def get_scenario(
    scenario_id: UUID,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    svc = ScenarioService(session)
    scenario = await svc.get(user["tenant_id"], scenario_id)
    if not scenario:
        raise HTTPException(404, "Scenario not found")
    return scenario


@router.post("/scenarios/{scenario_id}/runs", response_model=ScenarioRunResponse, status_code=201)
async def run_scenario(
    scenario_id: UUID,
    body: RunScenarioRequest | None = None,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """시나리오 실행 — 규칙 기반 근사 시뮬레이션."""
    svc = ScenarioService(session)
    try:
        run = await svc.run_scenario(
            user["tenant_id"], scenario_id,
            random_seed=body.random_seed if body else None,
        )
        await session.commit()
        return run
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/runs/{run_id}", response_model=ScenarioRunResponse)
async def get_run(
    run_id: UUID,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    svc = ScenarioService(session)
    run = await svc.get_run(user["tenant_id"], run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return run


@router.get("/runs/{run_id}/diff")
async def get_run_diff(
    run_id: UUID,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """baseline vs scenario diff."""
    svc = ScenarioService(session)
    run = await svc.get_run(user["tenant_id"], run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return {"success": True, "data": run.comparison_json or {}}


# ── 보정계수 ───────────────────────────────────────────────

@router.get("/coefficients")
async def list_coefficients(
    workspace_id: UUID = Query(...),
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    r = await session.execute(
        select(SimulationCoefficient).where(
            SimulationCoefficient.workspace_id == workspace_id,
            SimulationCoefficient.is_deleted == False,
        ).order_by(SimulationCoefficient.change_type, SimulationCoefficient.effect_metric)
    )
    return {"success": True, "data": [CoefficientResponse.model_validate(c) for c in r.scalars().all()]}


@router.put("/coefficients")
async def update_coefficients(
    workspace_id: UUID = Query(...),
    body: CoefficientUpdateRequest = ...,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """보정계수 일괄 수정."""
    for item in body.coefficients:
        coeff = SimulationCoefficient(
            tenant_id=user["tenant_id"],
            workspace_id=workspace_id,
            target_entity_type=item.target_entity_type,
            target_entity_id=item.target_entity_id,
            change_type=item.change_type,
            effect_metric=item.effect_metric,
            coefficient=item.coefficient,
            confidence=item.confidence,
            source=item.source,
        )
        session.add(coeff)
    await session.commit()
    return {"success": True, "message": f"{len(body.coefficients)} coefficients updated"}
