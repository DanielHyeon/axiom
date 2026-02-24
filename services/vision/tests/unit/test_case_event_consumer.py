"""
CaseEventConsumer 단위 테스트 (DDD-P2-03).

DB/Redis 없이 순수 로직 검증:
1. _handle_event → 올바른 mutation 메서드 호출 여부
2. CQRS 모드별 get_summary 분기 (AnalyticsService)
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ──────────────── CaseEventConsumer event dispatch ──────────────── #


@pytest.fixture
def consumer():
    """DB/Redis 연결 없이 CaseEventConsumer 인스턴스 생성."""
    from app.workers.case_event_consumer import CaseEventConsumer

    c = CaseEventConsumer(
        redis_url="redis://fake:6379/0",
        database_url="postgresql://fake:5432/fake",
    )
    # DB mutation 메서드를 mock
    c._increment_total = MagicMock()
    c._update_completion_stats = MagicMock()
    c._increment_cancelled = MagicMock()
    return c


@pytest.mark.asyncio
async def test_process_initiated(consumer):
    data = {"event_type": "PROCESS_INITIATED", "tenant_id": "t1"}
    await consumer._handle_event(data)
    consumer._increment_total.assert_called_once_with("t1")
    consumer._update_completion_stats.assert_not_called()
    consumer._increment_cancelled.assert_not_called()


@pytest.mark.asyncio
async def test_workitem_completed(consumer):
    data = {
        "event_type": "WORKITEM_COMPLETED",
        "tenant_id": "t1",
        "payload": json.dumps({"completion_days": 30}),
    }
    await consumer._handle_event(data)
    consumer._update_completion_stats.assert_called_once_with("t1", data)
    consumer._increment_total.assert_not_called()
    consumer._increment_cancelled.assert_not_called()


@pytest.mark.asyncio
async def test_saga_compensation_completed(consumer):
    data = {"event_type": "SAGA_COMPENSATION_COMPLETED", "tenant_id": "t1"}
    await consumer._handle_event(data)
    consumer._increment_cancelled.assert_called_once_with("t1")
    consumer._increment_total.assert_not_called()
    consumer._update_completion_stats.assert_not_called()


@pytest.mark.asyncio
async def test_unknown_event_ignored(consumer):
    data = {"event_type": "SOME_OTHER_EVENT", "tenant_id": "t1"}
    await consumer._handle_event(data)
    consumer._increment_total.assert_not_called()
    consumer._update_completion_stats.assert_not_called()
    consumer._increment_cancelled.assert_not_called()


@pytest.mark.asyncio
async def test_missing_tenant_id_skipped(consumer):
    data = {"event_type": "PROCESS_INITIATED", "tenant_id": ""}
    await consumer._handle_event(data)
    consumer._increment_total.assert_not_called()


# ──────────────── AnalyticsService CQRS mode ──────────────── #


@pytest.fixture
def analytics_svc():
    """AnalyticsService stub — DB 연결 없이 CQRS 분기 검증."""
    from app.services.analytics_service import AnalyticsService

    svc = AnalyticsService.__new__(AnalyticsService)
    svc.database_url = "postgresql://fake:5432/fake"
    svc._postgres = True
    svc._cqrs_mode = "primary"
    return svc


def _stub_kpi_result(total: int, active: int) -> dict:
    return {
        "period": "ALL",
        "period_label": "전체",
        "kpis": {
            "total_cases": {"value": total},
            "active_cases": {"value": active},
        },
    }


class TestCQRSModePrimary:
    """primary 모드: 읽기 모델 우선 → Core API Fallback."""

    def test_local_available(self, analytics_svc):
        analytics_svc._cqrs_mode = "primary"
        local_row = {"total_cases": 5, "active_cases": 3}

        with patch.object(analytics_svc, "ensure_schema"), \
             patch.object(analytics_svc, "_conn") as mock_conn, \
             patch.object(analytics_svc, "_query_local_summary", return_value=local_row), \
             patch.object(analytics_svc, "_core_api_case_stats") as mock_core:

            # _conn을 통한 kpi 테이블 조회 결과가 없어야 CQRS 분기 진입
            ctx = MagicMock()
            cur = MagicMock()
            cur.fetchone.return_value = None
            ctx.__enter__ = MagicMock(return_value=ctx)
            ctx.__exit__ = MagicMock(return_value=False)
            ctx.cursor.return_value = cur
            mock_conn.return_value = ctx

            result = analytics_svc.get_summary("t1", "ALL", None)
            mock_core.assert_not_called()
            assert result["kpis"]["total_cases"]["value"] == 5

    def test_local_empty_fallback_to_core(self, analytics_svc):
        analytics_svc._cqrs_mode = "primary"
        core_stats = {"total_cases": 10, "active_cases": 7}

        with patch.object(analytics_svc, "ensure_schema"), \
             patch.object(analytics_svc, "_conn") as mock_conn, \
             patch.object(analytics_svc, "_query_local_summary", return_value=None), \
             patch.object(analytics_svc, "_core_api_case_stats", return_value=core_stats):

            ctx = MagicMock()
            cur = MagicMock()
            cur.fetchone.return_value = None
            ctx.__enter__ = MagicMock(return_value=ctx)
            ctx.__exit__ = MagicMock(return_value=False)
            ctx.cursor.return_value = cur
            mock_conn.return_value = ctx

            result = analytics_svc.get_summary("t1", "ALL", None)
            assert result["kpis"]["total_cases"]["value"] == 10


class TestCQRSModeShadow:
    """shadow 모드: Core API 우선 + 비교 로깅."""

    def test_shadow_uses_core(self, analytics_svc):
        analytics_svc._cqrs_mode = "shadow"
        core_stats = {"total_cases": 10, "active_cases": 7}
        local_row = {"total_cases": 10, "active_cases": 7}

        with patch.object(analytics_svc, "ensure_schema"), \
             patch.object(analytics_svc, "_conn") as mock_conn, \
             patch.object(analytics_svc, "_query_local_summary", return_value=local_row), \
             patch.object(analytics_svc, "_core_api_case_stats", return_value=core_stats), \
             patch.object(analytics_svc, "_shadow_compare") as mock_compare:

            ctx = MagicMock()
            cur = MagicMock()
            cur.fetchone.return_value = None
            ctx.__enter__ = MagicMock(return_value=ctx)
            ctx.__exit__ = MagicMock(return_value=False)
            ctx.cursor.return_value = cur
            mock_conn.return_value = ctx

            result = analytics_svc.get_summary("t1", "ALL", None)
            mock_compare.assert_called_once_with(local_row, core_stats, "t1")
            assert result["kpis"]["total_cases"]["value"] == 10


class TestCQRSModeStandalone:
    """standalone 모드: 읽기 모델 전용."""

    def test_standalone_no_core_call(self, analytics_svc):
        analytics_svc._cqrs_mode = "standalone"
        local_row = {"total_cases": 3, "active_cases": 1}

        with patch.object(analytics_svc, "ensure_schema"), \
             patch.object(analytics_svc, "_conn") as mock_conn, \
             patch.object(analytics_svc, "_query_local_summary", return_value=local_row), \
             patch.object(analytics_svc, "_core_api_case_stats") as mock_core:

            ctx = MagicMock()
            cur = MagicMock()
            cur.fetchone.return_value = None
            ctx.__enter__ = MagicMock(return_value=ctx)
            ctx.__exit__ = MagicMock(return_value=False)
            ctx.cursor.return_value = cur
            mock_conn.return_value = ctx

            result = analytics_svc.get_summary("t1", "ALL", None)
            mock_core.assert_not_called()
            assert result["kpis"]["total_cases"]["value"] == 3

    def test_standalone_empty_returns_zero(self, analytics_svc):
        analytics_svc._cqrs_mode = "standalone"

        with patch.object(analytics_svc, "ensure_schema"), \
             patch.object(analytics_svc, "_conn") as mock_conn, \
             patch.object(analytics_svc, "_query_local_summary", return_value=None), \
             patch.object(analytics_svc, "_core_api_case_stats") as mock_core:

            ctx = MagicMock()
            cur = MagicMock()
            cur.fetchone.return_value = None
            ctx.__enter__ = MagicMock(return_value=ctx)
            ctx.__exit__ = MagicMock(return_value=False)
            ctx.cursor.return_value = cur
            mock_conn.return_value = ctx

            result = analytics_svc.get_summary("t1", "ALL", None)
            mock_core.assert_not_called()
            assert result["kpis"]["total_cases"]["value"] == 0
