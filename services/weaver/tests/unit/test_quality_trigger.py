"""
P2 §4.5: 이벤트 기반 품질 스캔 트리거 단위 테스트

- SEMANTIC_ENTITY_PUBLISHED 수신 시 즉시 스캔 트리거
- 5분 이내 중복 스캔 방지 (dedup)
- 스캔 이력 없을 때 즉시 스캔
- 관심 없는 이벤트 무시
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.worker.quality_worker import QualityWorker, EVENT_DEDUP_MINUTES


# ── 픽스처: QualityWorker + 모의 collector ──

@pytest.fixture
def mock_collector():
    """QualityCollector 모의 객체"""
    collector = AsyncMock()
    collector.get_score_for_target = AsyncMock(return_value=None)
    collector.collect_table_quality = AsyncMock(return_value={
        "target_type": "table",
        "target_id": "ent-1:public.orders",
        "scores": {"freshness": 90, "completeness": 85},
        "overall_score": 87.5,
        "details": {},
        "formula_version": 2,
        "sampled_at": datetime.now(timezone.utc).isoformat(),
    })
    return collector


@pytest.fixture
def worker(mock_collector):
    """모의 collector가 주입된 QualityWorker + EventPublisher 모킹"""
    with patch("app.worker.quality_worker.EventPublisher") as mock_pub:
        mock_pub.publish = AsyncMock()
        w = QualityWorker(poll_interval=900)
        w._collector = mock_collector
        yield w


# ── 테스트 1: 엔티티 발행 이벤트 수신 시 즉시 스캔 트리거 ──

@pytest.mark.asyncio
async def test_trigger_on_entity_published(worker, mock_collector):
    """SEMANTIC_ENTITY_PUBLISHED 수신 → collect_table_quality 호출 확인"""
    result = await worker.handle_entity_published(
        tenant_id="t-001",
        entity_id="ent-1",
        physical_source_ref="public.orders",
    )

    # 스캔이 실행되었는지 확인
    assert result["action"] == "scanned"
    assert result["target_id"] == "ent-1:public.orders"
    assert "overall_score" in result

    # collector.collect_table_quality가 올바른 인자로 호출되었는지 확인
    mock_collector.collect_table_quality.assert_awaited_once_with(
        tenant_id="t-001",
        datasource_id="ent-1",
        table_name="public.orders",
    )


# ── 테스트 2: 5분 이내 스캔 이력이 있으면 스킵 ──

@pytest.mark.asyncio
async def test_skip_recent_scan(worker, mock_collector):
    """최근 5분 이내 스캔됨 → 스캔 스킵 (dedup)"""
    # 2분 전 스캔 이력 반환
    recent_time = datetime.now(timezone.utc) - timedelta(minutes=2)
    mock_collector.get_score_for_target.return_value = {
        "created_at": recent_time,
        "overall_score": 85.0,
    }

    result = await worker.handle_entity_published(
        tenant_id="t-001",
        entity_id="ent-1",
        physical_source_ref="public.orders",
    )

    # 스킵되었는지 확인
    assert result["action"] == "skipped"
    assert result["reason"] == "recent_scan_exists"

    # collect_table_quality가 호출되지 않았는지 확인
    mock_collector.collect_table_quality.assert_not_awaited()


# ── 테스트 3: 이전 스캔 이력 없으면 즉시 스캔 ──

@pytest.mark.asyncio
async def test_trigger_no_previous_scan(worker, mock_collector):
    """스캔 이력 없음(None) → 즉시 스캔 진행"""
    mock_collector.get_score_for_target.return_value = None

    result = await worker.handle_entity_published(
        tenant_id="t-002",
        entity_id="ent-2",
        physical_source_ref="public.products",
    )

    assert result["action"] == "scanned"
    mock_collector.collect_table_quality.assert_awaited_once()


# ── 테스트 4: _should_scan — 5분 초과 이력은 스캔 허용 ──

@pytest.mark.asyncio
async def test_should_scan_old_record(worker, mock_collector):
    """6분 전 스캔 이력 → 스캔 허용 (dedup 시간 초과)"""
    old_time = datetime.now(timezone.utc) - timedelta(minutes=6)
    mock_collector.get_score_for_target.return_value = {
        "created_at": old_time,
        "overall_score": 70.0,
    }

    should = await worker._should_scan("t-001", "ent-1", "public.orders")
    assert should is True


# ── 테스트 5: _should_scan — 문자열 타임스탬프 처리 ──

@pytest.mark.asyncio
async def test_should_scan_string_timestamp(worker, mock_collector):
    """created_at이 ISO 문자열일 때도 정상 파싱"""
    recent_time = datetime.now(timezone.utc) - timedelta(minutes=1)
    mock_collector.get_score_for_target.return_value = {
        "created_at": recent_time.isoformat(),
        "overall_score": 90.0,
    }

    should = await worker._should_scan("t-001", "ent-1", "public.orders")
    assert should is False


# ── 테스트 6: main.py 이벤트 핸들러 — 관심 없는 이벤트 무시 ──

@pytest.mark.asyncio
async def test_event_listener_ignores_other_events():
    """SEMANTIC_ENTITY_PUBLISHED 외 이벤트 → ACK만 하고 스캔 안 함"""
    from app.main import _handle_synapse_event

    mock_rd = AsyncMock()

    # SEMANTIC_MEASURE_PUBLISHED (관심 대상 아님)
    await _handle_synapse_event(
        rd=mock_rd,
        msg_id="1-0",
        data={"event_type": "SEMANTIC_MEASURE_PUBLISHED", "tenant_id": "t-001"},
    )

    # ACK만 호출되고 QualityWorker 호출은 없어야 함
    mock_rd.xack.assert_awaited_once()


# ── 테스트 7: main.py 이벤트 핸들러 — 불완전한 데이터 스킵 ──

@pytest.mark.asyncio
async def test_event_handler_skips_incomplete_data():
    """필수 필드(tenant_id, entity_id, physical_source_ref) 누락 → 스킵"""
    from app.main import _handle_synapse_event

    mock_rd = AsyncMock()

    # entity_id 누락
    await _handle_synapse_event(
        rd=mock_rd,
        msg_id="2-0",
        data={
            "event_type": "SEMANTIC_ENTITY_PUBLISHED",
            "tenant_id": "t-001",
            "payload": json.dumps({"physical_source_ref": "public.orders"}),
        },
    )

    # ACK는 호출되지만 스캔은 실행 안 됨
    mock_rd.xack.assert_awaited_once()


# ── 테스트 8: _should_scan — DB 조회 실패 시 안전하게 스캔 진행 ──

@pytest.mark.asyncio
async def test_should_scan_db_error_fallback(worker, mock_collector):
    """get_score_for_target 예외 → True (안전하게 스캔 진행)"""
    mock_collector.get_score_for_target.side_effect = Exception("DB connection error")

    should = await worker._should_scan("t-001", "ent-1", "public.orders")
    assert should is True
