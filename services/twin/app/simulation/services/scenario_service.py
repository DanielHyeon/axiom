"""
시나리오 애플리케이션 서비스.

Phase 5: 시나리오 CRUD + 실행 트리거 + 결과 diff.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.simulation.engine.change_applier import apply_change_sets
from app.simulation.engine.coefficient_loader import load_coefficients
from app.simulation.engine.diff_calculator import calculate_diff
from app.simulation.models.scenario import (
    ScenarioChangeSet, ScenarioDefinition, ScenarioRun, SimulationCoefficient,
)
from app.models.twin_models import TwinSnapshot, TwinState

logger = logging.getLogger("axiom.simulation")

ENGINE_VERSION = "1.0.0-rule-based"


class ScenarioService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, tenant_id: str, dto) -> ScenarioDefinition:
        scenario = ScenarioDefinition(
            tenant_id=tenant_id,
            workspace_id=dto.workspace_id,
            code=dto.code,
            name=dto.name,
            base_snapshot_id=dto.base_snapshot_id,
            scenario_type=dto.scenario_type,
            description=dto.description,
        )
        self.session.add(scenario)
        await self.session.flush()

        # change_sets 저장
        for i, cs in enumerate(dto.changes):
            change = ScenarioChangeSet(
                tenant_id=tenant_id,
                scenario_definition_id=scenario.id,
                change_type=cs.change_type,
                target_entity_type=cs.target_entity_type,
                target_entity_id=cs.target_entity_id,
                patch_json=cs.patch_json,
                display_order=cs.display_order or i,
            )
            self.session.add(change)

        await self.session.flush()
        return scenario

    async def list_scenarios(self, tenant_id: str, workspace_id: UUID):
        r = await self.session.execute(
            select(ScenarioDefinition).where(
                ScenarioDefinition.tenant_id == tenant_id,
                ScenarioDefinition.workspace_id == workspace_id,
                ScenarioDefinition.is_deleted == False,
            ).order_by(ScenarioDefinition.created_at.desc())
        )
        return list(r.scalars().all())

    async def get(self, tenant_id: str, scenario_id: UUID) -> ScenarioDefinition | None:
        r = await self.session.execute(
            select(ScenarioDefinition).where(
                ScenarioDefinition.tenant_id == tenant_id,
                ScenarioDefinition.id == scenario_id,
                ScenarioDefinition.is_deleted == False,
            )
        )
        return r.scalar_one_or_none()

    async def run_scenario(
        self, tenant_id: str, scenario_id: UUID, random_seed: int | None = None,
    ) -> ScenarioRun:
        """시나리오 실행 — 규칙 기반 근사 시뮬레이션."""
        scenario = await self.get(tenant_id, scenario_id)
        if not scenario:
            raise ValueError(f"Scenario '{scenario_id}' not found")

        # run_number 결정
        max_run = (await self.session.execute(
            select(func.max(ScenarioRun.run_number)).where(
                ScenarioRun.tenant_id == tenant_id,
                ScenarioRun.scenario_definition_id == scenario_id,
                ScenarioRun.is_deleted == False,
            )
        )).scalar_one() or 0

        # baseline snapshot 로드
        snapshot = (await self.session.execute(
            select(TwinSnapshot).where(TwinSnapshot.id == scenario.base_snapshot_id)
        )).scalar_one_or_none()

        baseline_metrics = (snapshot.summary_json or {}).get("metrics", {}) if snapshot else {}

        # change_sets 로드
        changes_r = await self.session.execute(
            select(ScenarioChangeSet).where(
                ScenarioChangeSet.scenario_definition_id == scenario_id,
                ScenarioChangeSet.is_deleted == False,
            ).order_by(ScenarioChangeSet.display_order)
        )
        change_sets = [
            {"change_type": c.change_type, "patch_json": c.patch_json}
            for c in changes_r.scalars().all()
        ]

        # 보정계수 로드
        coefficients = await load_coefficients(self.session, tenant_id, scenario.workspace_id)

        # baseline snapshot hash
        snapshot_hash = hashlib.sha256(
            json.dumps(baseline_metrics, sort_keys=True).encode()
        ).hexdigest()[:32]

        # 시뮬레이션 실행
        now = datetime.now(timezone.utc)
        run = ScenarioRun(
            tenant_id=tenant_id,
            workspace_id=scenario.workspace_id,
            scenario_definition_id=scenario_id,
            base_snapshot_id=scenario.base_snapshot_id,
            run_number=max_run + 1,
            status="RUNNING",
            started_at=now,
            engine_version=ENGINE_VERSION,
            baseline_snapshot_hash=snapshot_hash,
            assumption_set_version=1,
            started_by=tenant_id,
            random_seed=random_seed,
            input_manifest_json={"coefficients": {k: v for k, v in coefficients.items()}, "change_sets": change_sets},
        )
        self.session.add(run)

        try:
            # ChangeSet 적용
            scenario_metrics = apply_change_sets(baseline_metrics, change_sets, coefficients)
            comparison = calculate_diff(baseline_metrics, scenario_metrics)

            run.status = "COMPLETED"
            run.completed_at = datetime.now(timezone.utc)
            run.result_summary_json = {"scenario_metrics": scenario_metrics}
            run.comparison_json = comparison
        except Exception as e:
            run.status = "FAILED"
            run.completed_at = datetime.now(timezone.utc)
            run.error_message = str(e)
            logger.error("시나리오 실행 실패: %s", e, exc_info=True)

        await self.session.flush()
        return run

    async def get_run(self, tenant_id: str, run_id: UUID) -> ScenarioRun | None:
        r = await self.session.execute(
            select(ScenarioRun).where(
                ScenarioRun.tenant_id == tenant_id,
                ScenarioRun.id == run_id,
                ScenarioRun.is_deleted == False,
            )
        )
        return r.scalar_one_or_none()
