"""DDD-P3-04: Unit tests for SagaOrchestrator.

Tests pure orchestration logic — forward execution, compensation, failure scenarios.
Uses mock steps with no real DB/Redis dependencies.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.services.saga_orchestrator import (
    SagaOrchestrator,
    SagaResult,
    SagaStep,
    StepStatus,
)


def _mock_session():
    """Create a mock AsyncSession."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    return session


# ── Forward Execution Tests ──────────────────────────────

class TestForwardExecution:
    @pytest.mark.asyncio
    async def test_all_steps_succeed(self):
        step1 = SagaStep(
            name="step_1",
            execute=AsyncMock(return_value={"key1": "val1"}),
            compensate=AsyncMock(),
        )
        step2 = SagaStep(
            name="step_2",
            execute=AsyncMock(return_value={"key2": "val2"}),
            compensate=AsyncMock(),
        )

        saga = SagaOrchestrator(name="test_saga", steps=[step1, step2])
        db = _mock_session()
        result = await saga.execute(db, context={"tenant_id": "t1"})

        assert result.success is True
        assert result.context["key1"] == "val1"
        assert result.context["key2"] == "val2"
        assert result.failed_step is None
        step1.compensate.assert_not_called()
        step2.compensate.assert_not_called()

    @pytest.mark.asyncio
    async def test_step_status_set_to_completed(self):
        step = SagaStep(
            name="step_1",
            execute=AsyncMock(return_value=None),
            compensate=AsyncMock(),
        )

        saga = SagaOrchestrator(name="test", steps=[step])
        db = _mock_session()
        result = await saga.execute(db, context={"tenant_id": "t1"})

        assert result.success is True
        assert step.status == StepStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_context_is_updated_by_steps(self):
        async def step1_exec(ctx):
            return {"proc_inst_id": "pi-123"}

        async def step2_exec(ctx):
            assert ctx["proc_inst_id"] == "pi-123"
            return {"workitem_id": "wi-456"}

        saga = SagaOrchestrator(
            name="test",
            steps=[
                SagaStep(name="s1", execute=step1_exec, compensate=AsyncMock()),
                SagaStep(name="s2", execute=step2_exec, compensate=AsyncMock()),
            ],
        )
        db = _mock_session()
        result = await saga.execute(db, context={"tenant_id": "t1"})

        assert result.success is True
        assert result.context["proc_inst_id"] == "pi-123"
        assert result.context["workitem_id"] == "wi-456"

    @pytest.mark.asyncio
    async def test_empty_steps_succeed(self):
        saga = SagaOrchestrator(name="empty", steps=[])
        db = _mock_session()
        result = await saga.execute(db, context={"tenant_id": "t1"})
        assert result.success is True

    @pytest.mark.asyncio
    async def test_result_includes_steps_log(self):
        saga = SagaOrchestrator(
            name="test",
            steps=[
                SagaStep(name="a", execute=AsyncMock(return_value=None), compensate=AsyncMock()),
                SagaStep(name="b", execute=AsyncMock(return_value=None), compensate=AsyncMock()),
            ],
        )
        db = _mock_session()
        result = await saga.execute(db, context={"tenant_id": "t1"})

        assert len(result.steps) == 2
        assert result.steps[0]["name"] == "a"
        assert result.steps[0]["status"] == "COMPLETED"
        assert result.steps[1]["name"] == "b"


# ── Compensation Tests ───────────────────────────────────

class TestCompensation:
    @pytest.mark.asyncio
    async def test_failure_triggers_compensation(self):
        step1 = SagaStep(
            name="step_1",
            execute=AsyncMock(return_value={"key": "val"}),
            compensate=AsyncMock(),
        )
        step2 = SagaStep(
            name="step_2",
            execute=AsyncMock(side_effect=ValueError("step2 failed")),
            compensate=AsyncMock(),
        )

        saga = SagaOrchestrator(name="test", steps=[step1, step2])
        db = _mock_session()
        result = await saga.execute(db, context={"tenant_id": "t1"})

        assert result.success is False
        assert result.failed_step == "step_2"
        assert "step2 failed" in result.reason
        # Only step1 was completed, so only step1 compensate should be called
        step1.compensate.assert_called_once()
        step2.compensate.assert_not_called()

    @pytest.mark.asyncio
    async def test_compensation_runs_in_reverse_order(self):
        call_order = []

        async def comp1(ctx):
            call_order.append("comp_1")

        async def comp2(ctx):
            call_order.append("comp_2")

        async def comp3(ctx):
            call_order.append("comp_3")

        step1 = SagaStep(name="s1", execute=AsyncMock(return_value=None), compensate=comp1)
        step2 = SagaStep(name="s2", execute=AsyncMock(return_value=None), compensate=comp2)
        step3 = SagaStep(name="s3", execute=AsyncMock(return_value=None), compensate=comp3)
        step4 = SagaStep(
            name="s4",
            execute=AsyncMock(side_effect=RuntimeError("boom")),
            compensate=AsyncMock(),
        )

        saga = SagaOrchestrator(name="test", steps=[step1, step2, step3, step4])
        db = _mock_session()
        await saga.execute(db, context={"tenant_id": "t1"})

        assert call_order == ["comp_3", "comp_2", "comp_1"]

    @pytest.mark.asyncio
    async def test_first_step_failure_no_compensation(self):
        step = SagaStep(
            name="step_1",
            execute=AsyncMock(side_effect=ValueError("fail")),
            compensate=AsyncMock(),
        )

        saga = SagaOrchestrator(name="test", steps=[step])
        db = _mock_session()
        result = await saga.execute(db, context={"tenant_id": "t1"})

        assert result.success is False
        assert result.failed_step == "step_1"
        step.compensate.assert_not_called()

    @pytest.mark.asyncio
    async def test_step_status_after_compensation(self):
        step1 = SagaStep(
            name="s1",
            execute=AsyncMock(return_value=None),
            compensate=AsyncMock(),
        )
        step2 = SagaStep(
            name="s2",
            execute=AsyncMock(side_effect=RuntimeError("fail")),
            compensate=AsyncMock(),
        )

        saga = SagaOrchestrator(name="test", steps=[step1, step2])
        db = _mock_session()
        await saga.execute(db, context={"tenant_id": "t1"})

        assert step1.status == StepStatus.COMPENSATED
        assert step2.status == StepStatus.FAILED


# ── Compensation Failure Tests ───────────────────────────

class TestCompensationFailure:
    @pytest.mark.asyncio
    async def test_compensation_failure_is_logged(self):
        step1 = SagaStep(
            name="s1",
            execute=AsyncMock(return_value=None),
            compensate=AsyncMock(side_effect=RuntimeError("comp failed")),
        )
        step2 = SagaStep(
            name="s2",
            execute=AsyncMock(side_effect=ValueError("exec failed")),
            compensate=AsyncMock(),
        )

        saga = SagaOrchestrator(name="test", steps=[step1, step2])
        db = _mock_session()
        result = await saga.execute(db, context={"tenant_id": "t1"})

        assert result.success is False
        assert step1.status == StepStatus.COMPENSATION_FAILED

    @pytest.mark.asyncio
    async def test_compensation_continues_after_partial_failure(self):
        """Even if one compensation fails, others should still run."""
        call_log = []

        async def comp1(ctx):
            call_log.append("comp1")
            raise RuntimeError("comp1 failed")

        async def comp2(ctx):
            call_log.append("comp2")

        step1 = SagaStep(name="s1", execute=AsyncMock(return_value=None), compensate=comp2)
        step2 = SagaStep(name="s2", execute=AsyncMock(return_value=None), compensate=comp1)
        step3 = SagaStep(
            name="s3",
            execute=AsyncMock(side_effect=ValueError("fail")),
            compensate=AsyncMock(),
        )

        saga = SagaOrchestrator(name="test", steps=[step1, step2, step3])
        db = _mock_session()
        await saga.execute(db, context={"tenant_id": "t1"})

        # Both compensations should run (comp1 first since s2 completed last)
        assert "comp1" in call_log
        assert "comp2" in call_log


# ── Saga Name Property Test ─────────────────────────────

class TestSagaProperties:
    def test_saga_name(self):
        saga = SagaOrchestrator(name="my_saga", steps=[])
        assert saga.name == "my_saga"
