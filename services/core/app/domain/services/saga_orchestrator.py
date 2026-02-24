"""DDD-P3-04: Saga Orchestrator — 정방향 실행 + 실패 시 자동 보상.

Forward Execution:
  Step 1 → Step 2 → … → Step N → SagaResult(success=True)

Failure + Compensation:
  Step 1 → Step 2(fail) → Compensate Step 1 → SagaResult(success=False)

Compensation Failure:
  → 로깅 + Watch 알림 (수동 개입 필요)

Saga 실행 이력은 DB(saga_execution_log)에 영속화된다.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("axiom.saga")


# ── Step / Result Value Objects ──────────────────────────

class StepStatus(str, Enum):
    PENDING = "PENDING"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    COMPENSATING = "COMPENSATING"
    COMPENSATED = "COMPENSATED"
    COMPENSATION_FAILED = "COMPENSATION_FAILED"


@dataclass
class SagaStep:
    """Saga 단계 정의.

    execute:    context → dict (결과를 context에 merge)
    compensate: context → None (보상 로직)
    """
    name: str
    execute: Callable[[dict], Coroutine[Any, Any, dict | None]]
    compensate: Callable[[dict], Coroutine[Any, Any, None]]
    status: StepStatus = StepStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None


@dataclass
class SagaResult:
    success: bool
    context: dict = field(default_factory=dict)
    failed_step: str | None = None
    reason: str | None = None
    steps: list[dict] = field(default_factory=list)


# ── Saga Execution Log (DB persistence helper) ────────

@dataclass
class SagaExecutionRecord:
    """Saga 실행 이력 (DB row)."""
    id: str
    saga_name: str
    tenant_id: str
    status: str  # RUNNING, COMPLETED, COMPENSATING, COMPENSATED, COMPENSATION_FAILED
    context_snapshot: dict
    steps_log: list[dict]
    started_at: datetime
    completed_at: datetime | None = None
    error: str | None = None


class SagaExecutionLogger:
    """Saga 실행 이력을 saga_execution_log 테이블에 영속화."""

    TABLE = "saga_execution_log"

    @staticmethod
    async def create(db: AsyncSession, record: SagaExecutionRecord) -> None:
        """INSERT saga execution record."""
        from sqlalchemy import text
        await db.execute(
            text(f"""
                INSERT INTO {SagaExecutionLogger.TABLE}
                    (id, saga_name, tenant_id, status, context_snapshot, steps_log, started_at)
                VALUES (:id, :saga_name, :tenant_id, :status, :context_snapshot::jsonb, :steps_log::jsonb, :started_at)
            """),
            {
                "id": record.id,
                "saga_name": record.saga_name,
                "tenant_id": record.tenant_id,
                "status": record.status,
                "context_snapshot": _json_dumps(record.context_snapshot),
                "steps_log": _json_dumps(record.steps_log),
                "started_at": record.started_at,
            },
        )

    @staticmethod
    async def update(db: AsyncSession, record: SagaExecutionRecord) -> None:
        """UPDATE saga execution record."""
        from sqlalchemy import text
        await db.execute(
            text(f"""
                UPDATE {SagaExecutionLogger.TABLE}
                SET status = :status,
                    context_snapshot = :context_snapshot::jsonb,
                    steps_log = :steps_log::jsonb,
                    completed_at = :completed_at,
                    error = :error
                WHERE id = :id
            """),
            {
                "id": record.id,
                "status": record.status,
                "context_snapshot": _json_dumps(record.context_snapshot),
                "steps_log": _json_dumps(record.steps_log),
                "completed_at": record.completed_at,
                "error": record.error,
            },
        )


def _json_dumps(obj: Any) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False, default=str)


# ── DDL: Saga Execution Log ─────────────────────────────

SAGA_EXECUTION_LOG_DDL = """\
CREATE TABLE IF NOT EXISTS saga_execution_log (
    id VARCHAR PRIMARY KEY,
    saga_name VARCHAR NOT NULL,
    tenant_id VARCHAR NOT NULL,
    status VARCHAR NOT NULL DEFAULT 'RUNNING',
    context_snapshot JSONB NOT NULL DEFAULT '{}',
    steps_log JSONB NOT NULL DEFAULT '[]',
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    error TEXT
);
CREATE INDEX IF NOT EXISTS idx_saga_execution_log_tenant_status
    ON saga_execution_log (tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_saga_execution_log_saga_name
    ON saga_execution_log (saga_name, started_at DESC);
"""


async def ensure_saga_log_table(db: AsyncSession) -> None:
    """saga_execution_log 테이블이 없으면 생성."""
    from sqlalchemy import text
    for stmt in SAGA_EXECUTION_LOG_DDL.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            await db.execute(text(stmt))
    await db.commit()


# ── SagaOrchestrator ────────────────────────────────────

class SagaOrchestrator:
    """정방향 + 보상 양방향 Saga 관리자.

    Usage::

        saga = SagaOrchestrator(
            name="start_process",
            steps=[
                SagaStep(name="create_instance", execute=..., compensate=...),
                SagaStep(name="create_workitem", execute=..., compensate=...),
                SagaStep(name="publish_event",   execute=..., compensate=noop),
            ],
        )
        result = await saga.execute(db, context={"tenant_id": "t1", ...})
    """

    def __init__(self, name: str, steps: list[SagaStep]):
        self._name = name
        self._steps = steps
        self._completed_steps: list[SagaStep] = []

    @property
    def name(self) -> str:
        return self._name

    async def execute(self, db: AsyncSession, context: dict) -> SagaResult:
        """정방향 실행. 실패 시 완료된 단계를 역순으로 자동 보상."""
        saga_id = str(uuid.uuid4())
        tenant_id = context.get("tenant_id", "default")
        now = datetime.now(timezone.utc)

        record = SagaExecutionRecord(
            id=saga_id,
            saga_name=self._name,
            tenant_id=tenant_id,
            status="RUNNING",
            context_snapshot=dict(context),
            steps_log=[],
            started_at=now,
        )

        # Persist initial record (best-effort; table may not exist in tests)
        try:
            await SagaExecutionLogger.create(db, record)
            await db.flush()
        except Exception:
            logger.debug("saga_execution_log table not available, skipping persistence")

        # ── Forward execution ──
        for step in self._steps:
            step_log: dict[str, Any] = {"name": step.name}
            try:
                step.status = StepStatus.EXECUTING
                step.started_at = datetime.now(timezone.utc)
                step_log["started_at"] = step.started_at.isoformat()

                result = await step.execute(context)
                if result:
                    context.update(result)

                step.status = StepStatus.COMPLETED
                step.completed_at = datetime.now(timezone.utc)
                step_log["status"] = StepStatus.COMPLETED.value
                step_log["completed_at"] = step.completed_at.isoformat()
                self._completed_steps.append(step)
                record.steps_log.append(step_log)

            except Exception as e:
                step.status = StepStatus.FAILED
                step.error = str(e)
                step_log["status"] = StepStatus.FAILED.value
                step_log["error"] = str(e)
                record.steps_log.append(step_log)

                logger.warning(
                    "Saga '%s' step '%s' failed: %s — starting compensation",
                    self._name, step.name, e,
                )

                # ── Compensation ──
                record.status = "COMPENSATING"
                compensation_ok = await self._compensate(context, record)

                record.status = "COMPENSATED" if compensation_ok else "COMPENSATION_FAILED"
                record.completed_at = datetime.now(timezone.utc)
                record.error = str(e)
                record.context_snapshot = dict(context)

                try:
                    await SagaExecutionLogger.update(db, record)
                    await db.flush()
                except Exception:
                    pass

                return SagaResult(
                    success=False,
                    context=context,
                    failed_step=step.name,
                    reason=str(e),
                    steps=record.steps_log,
                )

        # ── All steps completed ──
        record.status = "COMPLETED"
        record.completed_at = datetime.now(timezone.utc)
        record.context_snapshot = dict(context)

        try:
            await SagaExecutionLogger.update(db, record)
            await db.flush()
        except Exception:
            pass

        return SagaResult(
            success=True,
            context=context,
            steps=record.steps_log,
        )

    async def _compensate(self, context: dict, record: SagaExecutionRecord) -> bool:
        """완료된 단계를 역순으로 보상 실행. 전부 성공하면 True, 하나라도 실패하면 False."""
        all_ok = True
        for step in reversed(self._completed_steps):
            comp_log: dict[str, Any] = {"name": f"compensate_{step.name}"}
            try:
                step.status = StepStatus.COMPENSATING
                await step.compensate(context)
                step.status = StepStatus.COMPENSATED
                comp_log["status"] = StepStatus.COMPENSATED.value
            except Exception as e:
                step.status = StepStatus.COMPENSATION_FAILED
                step.error = str(e)
                comp_log["status"] = StepStatus.COMPENSATION_FAILED.value
                comp_log["error"] = str(e)
                all_ok = False
                logger.error(
                    "Saga '%s' compensation failed for step '%s': %s",
                    self._name, step.name, e,
                )
                # Notify for manual intervention
                await self._notify_compensation_failure(context, step, str(e))
            record.steps_log.append(comp_log)
        return all_ok

    async def _notify_compensation_failure(
        self, context: dict, step: SagaStep, error: str
    ) -> None:
        """보상 실패 시 Watch 알림 발행 (best-effort)."""
        try:
            from app.core.events import EventPublisher
            # Use the saga's DB session from context if available
            db = context.get("_db")
            if db is None:
                logger.warning(
                    "Saga compensation failure for '%s' step '%s': %s (no DB session for Watch alert)",
                    self._name, step.name, error,
                )
                return

            await EventPublisher.publish(
                session=db,
                event_type="WATCH_ALERT_TRIGGERED",
                aggregate_type="saga",
                aggregate_id=context.get("proc_inst_id", "unknown"),
                payload={
                    "watch_id": f"saga_compensation_failure_{self._name}",
                    "alert_id": str(uuid.uuid4()),
                    "severity": "CRITICAL",
                    "message": f"Saga '{self._name}' compensation failed at step '{step.name}': {error}",
                    "saga_name": self._name,
                    "failed_step": step.name,
                    "error": error,
                },
                tenant_id=context.get("tenant_id"),
            )
        except Exception as notify_err:
            logger.error("Failed to publish Watch alert for compensation failure: %s", notify_err)
