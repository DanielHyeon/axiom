"""
§3.3 품질 이벤트 발행 + §3.4 대시보드 API 테스트

테스트 항목:
  1. 스캔 완료 시 QUALITY_SCORE_UPDATED 이벤트 발행
  2. overall_score < 60 이면 QUALITY_THRESHOLD_BREACHED 이벤트 발행
  3. overall_score >= 60 이면 breach 이벤트 미발행
  4. breach 이벤트에 previous_score 포함
  5. 대시보드 요약 응답 구조
  6. 이력 시계열 응답 구조
  7. breach 목록 응답 구조
  8. 데이터 없을 때 대시보드 빈 응답
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.worker.quality_worker import QualityWorker, QUALITY_BREACH_THRESHOLD


# ── 공통 픽스처 ──


def _make_entity(entity_id: str = "ent-1", tenant_id: str = "t1",
                 source_ref: str = "public.orders", status: str = "approved"):
    """테스트용 Synapse 엔티티 딕셔너리 생성"""
    return {
        "entity_id": entity_id,
        "tenant_id": tenant_id,
        "physical_source_ref": source_ref,
        "status": status,
        "freshness_sla_minutes": 60,
        "owner_team": "data-team",
    }


def _make_scan_result(overall: float = 85.0, target_id: str = "ent-1:public.orders"):
    """collect_table_quality 반환 결과 모형"""
    return {
        "target_type": "table",
        "target_id": target_id,
        "overall_score": overall,
        "formula_version": 2,
        "scores": {
            "freshness": 90.0,
            "completeness": 80.0,
            "validity": 100.0,
            "uniqueness": 95.0,
            "referential_integrity": 88.0,
            "owner": 100.0,
            "lineage": 50.0,
            "test_coverage": 0.0,
            "incident_health": 80.0,
        },
        "sampled_at": "2026-03-23T10:00:00+00:00",
    }


def _make_low_scan_result(overall: float = 42.0):
    """임계값 미달 스캔 결과 — breach 이벤트 발행 대상"""
    result = _make_scan_result(overall=overall)
    # 낮은 차원 점수 설정 (breach 목록에 포함될 차원들)
    result["scores"]["freshness"] = 20.0
    result["scores"]["completeness"] = 30.0
    result["scores"]["lineage"] = 10.0
    result["scores"]["test_coverage"] = 0.0
    return result


# ── §3.3 이벤트 발행 테스트 ──


class TestQualityScoreUpdatedEvent:
    """스캔 완료 시 QUALITY_SCORE_UPDATED 이벤트 발행 검증"""

    @pytest.mark.asyncio
    async def test_score_updated_event_published_on_scan(self):
        """스캔 성공 후 QUALITY_SCORE_UPDATED 이벤트가 반드시 발행된다"""
        worker = QualityWorker(poll_interval=1)
        scan_result = _make_scan_result(overall=85.0)

        # 모킹: Synapse 엔티티 조회 → 엔티티 1개 반환
        worker._fetch_approved_entities = AsyncMock(return_value=[_make_entity()])
        # 모킹: 이전 점수 없음
        worker._collector.get_score_for_target = AsyncMock(return_value=None)
        # 모킹: 품질 스캔 → 정상 결과
        worker._collector.collect_table_quality = AsyncMock(return_value=scan_result)

        with patch("app.worker.quality_worker.EventPublisher") as mock_pub:
            mock_pub.publish = AsyncMock(return_value="evt-123")
            stats = await worker._collect_once()

        # 스캔 1건 성공
        assert stats["scanned"] == 1

        # QUALITY_SCORE_UPDATED 이벤트 발행 확인
        calls = mock_pub.publish.call_args_list
        updated_calls = [c for c in calls if c.kwargs.get("event_type") == "QUALITY_SCORE_UPDATED"
                         or (c.args and c.args[0] == "QUALITY_SCORE_UPDATED")]
        # 키워드 또는 위치 인자로 전달될 수 있음
        score_updated_found = any(
            "QUALITY_SCORE_UPDATED" in str(c) for c in calls
        )
        assert score_updated_found, f"QUALITY_SCORE_UPDATED 이벤트가 발행되지 않음. calls={calls}"

    @pytest.mark.asyncio
    async def test_score_updated_payload_structure(self):
        """QUALITY_SCORE_UPDATED 페이로드에 필수 필드가 포함된다"""
        worker = QualityWorker(poll_interval=1)
        scan_result = _make_scan_result(overall=75.0)

        worker._fetch_approved_entities = AsyncMock(return_value=[_make_entity()])
        worker._collector.get_score_for_target = AsyncMock(return_value=None)
        worker._collector.collect_table_quality = AsyncMock(return_value=scan_result)

        with patch("app.worker.quality_worker.EventPublisher") as mock_pub:
            mock_pub.publish = AsyncMock(return_value="evt-456")
            await worker._collect_once()

        # 첫 번째 publish 호출의 payload 검증
        first_call = mock_pub.publish.call_args_list[0]
        payload = first_call.kwargs.get("payload") or first_call[1].get("payload")
        assert payload is not None
        assert "target_id" in payload
        assert "overall_score" in payload
        assert "dimension_scores" in payload
        assert "scanned_at" in payload
        assert payload["overall_score"] == 75.0


class TestQualityThresholdBreachedEvent:
    """임계값 위반 시 QUALITY_THRESHOLD_BREACHED 이벤트 발행 검증"""

    @pytest.mark.asyncio
    async def test_threshold_breach_event_published_under_60(self):
        """overall_score < 60 이면 QUALITY_THRESHOLD_BREACHED 이벤트가 발행된다"""
        worker = QualityWorker(poll_interval=1)
        low_result = _make_low_scan_result(overall=42.0)

        worker._fetch_approved_entities = AsyncMock(return_value=[_make_entity()])
        worker._collector.get_score_for_target = AsyncMock(return_value=None)
        worker._collector.collect_table_quality = AsyncMock(return_value=low_result)

        with patch("app.worker.quality_worker.EventPublisher") as mock_pub:
            mock_pub.publish = AsyncMock(return_value="evt-789")
            await worker._collect_once()

        # 총 2번 호출: SCORE_UPDATED + THRESHOLD_BREACHED
        assert mock_pub.publish.call_count == 2
        breach_found = any(
            "QUALITY_THRESHOLD_BREACHED" in str(c) for c in mock_pub.publish.call_args_list
        )
        assert breach_found, "QUALITY_THRESHOLD_BREACHED 이벤트가 발행되지 않음"

    @pytest.mark.asyncio
    async def test_no_breach_event_above_60(self):
        """overall_score >= 60 이면 QUALITY_THRESHOLD_BREACHED 이벤트가 발행되지 않는다"""
        worker = QualityWorker(poll_interval=1)
        good_result = _make_scan_result(overall=85.0)

        worker._fetch_approved_entities = AsyncMock(return_value=[_make_entity()])
        worker._collector.get_score_for_target = AsyncMock(return_value=None)
        worker._collector.collect_table_quality = AsyncMock(return_value=good_result)

        with patch("app.worker.quality_worker.EventPublisher") as mock_pub:
            mock_pub.publish = AsyncMock(return_value="evt-ok")
            await worker._collect_once()

        # SCORE_UPDATED만 1번, THRESHOLD_BREACHED는 없어야 함
        assert mock_pub.publish.call_count == 1
        breach_found = any(
            "QUALITY_THRESHOLD_BREACHED" in str(c) for c in mock_pub.publish.call_args_list
        )
        assert not breach_found, "60점 이상인데 breach 이벤트가 발행됨"

    @pytest.mark.asyncio
    async def test_breach_event_includes_previous_score(self):
        """breach 이벤트의 payload에 previous_score가 포함된다"""
        worker = QualityWorker(poll_interval=1)
        low_result = _make_low_scan_result(overall=45.0)

        # 이전 점수가 있는 경우 (72점 → 45점으로 하락)
        prev_record = {"overall_score": 72.0, "target_type": "table", "target_id": "ent-1:public.orders"}
        worker._fetch_approved_entities = AsyncMock(return_value=[_make_entity()])
        worker._collector.get_score_for_target = AsyncMock(return_value=prev_record)
        worker._collector.collect_table_quality = AsyncMock(return_value=low_result)

        with patch("app.worker.quality_worker.EventPublisher") as mock_pub:
            mock_pub.publish = AsyncMock(return_value="evt-breach")
            await worker._collect_once()

        # THRESHOLD_BREACHED 호출 찾기 (두 번째 호출)
        breach_call = mock_pub.publish.call_args_list[1]
        payload = breach_call.kwargs.get("payload") or breach_call[1].get("payload")
        assert payload["previous_score"] == 72.0
        assert payload["overall_score"] == 45.0
        assert isinstance(payload["breached_dimensions"], list)
        assert len(payload["breached_dimensions"]) > 0

    @pytest.mark.asyncio
    async def test_breach_event_lists_breached_dimensions(self):
        """breach 이벤트의 breached_dimensions에 60 미만 차원이 포함된다"""
        worker = QualityWorker(poll_interval=1)
        low_result = _make_low_scan_result(overall=35.0)

        worker._fetch_approved_entities = AsyncMock(return_value=[_make_entity()])
        worker._collector.get_score_for_target = AsyncMock(return_value=None)
        worker._collector.collect_table_quality = AsyncMock(return_value=low_result)

        with patch("app.worker.quality_worker.EventPublisher") as mock_pub:
            mock_pub.publish = AsyncMock(return_value="evt-dims")
            await worker._collect_once()

        breach_call = mock_pub.publish.call_args_list[1]
        payload = breach_call.kwargs.get("payload") or breach_call[1].get("payload")
        dims = payload["breached_dimensions"]
        # _make_low_scan_result에서 freshness=20, completeness=30, lineage=10, test_coverage=0
        assert "freshness" in dims
        assert "completeness" in dims
        assert "lineage" in dims
        assert "test_coverage" in dims


# ── §3.4 대시보드 API 테스트 ──


class _FakePool:
    """asyncpg pool 모킹 — conn.fetch 결과를 주입할 수 있는 간이 구현"""

    def __init__(self, rows=None):
        self._rows = rows or []

    def acquire(self):
        return _FakeConn(self._rows)


class _FakeConn:
    def __init__(self, rows):
        self._rows = rows

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def fetch(self, query, *args):
        return self._rows


def _make_score_row(target_id: str, overall: float, target_type: str = "table",
                    sampled_at=None, created_at=None):
    """quality_scores 테이블 행 모형"""
    now = datetime.now(timezone.utc)
    return {
        "id": f"score-{target_id}",
        "tenant_id": "t1",
        "target_type": target_type,
        "target_id": target_id,
        "overall_score": overall,
        "freshness_score": overall * 0.9,
        "completeness_score": overall * 0.95,
        "uniqueness_score": overall,
        "validity_score": overall,
        "ri_score": overall,
        "owner_score": 100.0,
        "lineage_score": 50.0,
        "test_score": 0.0,
        "incident_score": 80.0,
        "formula_version": 2,
        "details": "{}",
        "sampled_at": sampled_at or now,
        "created_at": created_at or now,
    }


@pytest.fixture
def fake_request():
    """tenant_id가 설정된 가짜 Request 객체"""
    req = MagicMock()
    req.state = MagicMock()
    req.state.tenant_id = "t1"
    return req


class TestDashboardAPI:
    """GET /api/quality/dashboard 테스트"""

    @pytest.mark.asyncio
    async def test_dashboard_returns_summary(self, fake_request):
        """대시보드가 평균 점수, 등급별 건수, 하위 대상을 반환한다"""
        rows = [
            _make_score_row("tbl-a", 92.0),   # green
            _make_score_row("tbl-b", 75.0),   # yellow
            _make_score_row("tbl-c", 45.0),   # red
            _make_score_row("tbl-d", 88.0),   # green
        ]
        fake_pool = _FakePool(rows)

        with patch("app.api.quality.insight_store") as mock_store:
            mock_store.get_pool = AsyncMock(return_value=fake_pool)
            from app.api.quality import quality_dashboard
            resp = await quality_dashboard(fake_request)

        assert resp["success"] is True
        data = resp["data"]
        assert data["total_targets"] == 4
        assert data["tier_counts"]["green"] == 2
        assert data["tier_counts"]["yellow"] == 1
        assert data["tier_counts"]["red"] == 1
        # 평균: (92 + 75 + 45 + 88) / 4 = 75.0
        assert data["average_score"] == 75.0
        # 하위 10% (최소 1건) → tbl-c(45점)가 포함
        assert len(data["worst_targets"]) >= 1
        assert data["worst_targets"][0]["overall_score"] == 45.0

    @pytest.mark.asyncio
    async def test_dashboard_empty_data(self, fake_request):
        """데이터가 없으면 빈 요약을 반환한다"""
        fake_pool = _FakePool(rows=[])

        with patch("app.api.quality.insight_store") as mock_store:
            mock_store.get_pool = AsyncMock(return_value=fake_pool)
            from app.api.quality import quality_dashboard
            resp = await quality_dashboard(fake_request)

        assert resp["success"] is True
        data = resp["data"]
        assert data["total_targets"] == 0
        assert data["average_score"] == 0
        assert data["tier_counts"] == {"green": 0, "yellow": 0, "red": 0}
        assert data["worst_targets"] == []


class TestHistoryAPI:
    """GET /api/quality/history/{type}/{id} 테스트"""

    @pytest.mark.asyncio
    async def test_history_returns_timeseries(self, fake_request):
        """이력 API가 시계열 데이터를 반환한다"""
        rows = [
            _make_score_row("ds1:tbl1", 80.0),
            _make_score_row("ds1:tbl1", 75.0),
            _make_score_row("ds1:tbl1", 70.0),
        ]
        fake_pool = _FakePool(rows)

        with patch("app.api.quality.insight_store") as mock_store:
            mock_store.get_pool = AsyncMock(return_value=fake_pool)
            from app.api.quality import quality_history
            resp = await quality_history(fake_request, "table", "ds1:tbl1", days=30, limit=100)

        assert resp["success"] is True
        assert resp["count"] == 3
        # 각 항목에 필수 필드 존재
        for item in resp["data"]:
            assert "overall_score" in item
            assert "formula_version" in item
            assert "sampled_at" in item


class TestBreachesAPI:
    """GET /api/quality/breaches 테스트"""

    @pytest.mark.asyncio
    async def test_breaches_returns_low_scores(self, fake_request):
        """breach API가 60점 미만 기록만 반환한다"""
        # DB 쿼리에서 이미 < 60 필터링되므로 모킹 결과도 60 미만만 포함
        rows = [
            _make_score_row("tbl-bad1", 35.0),
            _make_score_row("tbl-bad2", 48.0),
        ]
        fake_pool = _FakePool(rows)

        with patch("app.api.quality.insight_store") as mock_store:
            mock_store.get_pool = AsyncMock(return_value=fake_pool)
            from app.api.quality import quality_breaches
            resp = await quality_breaches(fake_request, limit=50)

        assert resp["success"] is True
        assert resp["count"] == 2
        # 모든 항목이 60 미만
        for item in resp["data"]:
            assert item["overall_score"] < 60
            assert "target_id" in item
            assert "target_type" in item
