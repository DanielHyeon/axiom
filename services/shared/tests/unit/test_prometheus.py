"""Prometheus 자동 계측 미들웨어 단위 테스트.

SimpleMetricsCollector, 경로 정규화, PrometheusMiddleware를 검증한다.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from shared.middleware.prometheus import (
    PrometheusMiddleware,
    SimpleMetricsCollector,
    _normalize_path,
    setup_prometheus,
)


# ── 경로 정규화 테스트 ── #


class TestNormalizePath:
    """UUID, 숫자 ID를 {id}로 치환하여 카디널리티를 제한한다."""

    def test_uuid_치환(self):
        path = "/api/v1/cases/550e8400-e29b-41d4-a716-446655440000/documents"
        assert _normalize_path(path) == "/api/v1/cases/{id}/documents"

    def test_숫자_id_치환(self):
        path = "/api/v1/users/42"
        assert _normalize_path(path) == "/api/v1/users/{id}"

    def test_여러_uuid_동시_치환(self):
        path = "/api/v1/tenants/550e8400-e29b-41d4-a716-446655440000/cases/660f9511-f30c-52e5-b827-557766551111"
        result = _normalize_path(path)
        assert result == "/api/v1/tenants/{id}/cases/{id}"

    def test_일반_경로_변경_없음(self):
        path = "/api/v1/health/live"
        assert _normalize_path(path) == "/api/v1/health/live"

    def test_빈_경로(self):
        assert _normalize_path("") == ""

    def test_루트_경로(self):
        assert _normalize_path("/") == "/"


# ── SimpleMetricsCollector 테스트 ── #


class TestSimpleMetricsCollector:
    """기본 메트릭 수집기 동작 검증."""

    def test_record_후_카운터_증가(self):
        c = SimpleMetricsCollector(service_name="test")
        c.record("GET", "/api/test", 200, 12.5)
        c.record("GET", "/api/test", 200, 8.3)
        assert c.get_request_count() == 2

    def test_prometheus_텍스트_포맷_생성(self):
        c = SimpleMetricsCollector(service_name="weaver")
        c.record("GET", "/api/v1/tables", 200, 15.0)
        c.record("POST", "/api/v1/tables", 201, 25.0)

        text = c.to_prometheus_text()
        # 카운터 헤더 확인
        assert "# TYPE axiom_http_requests_total counter" in text
        # 서비스 레이블 확인
        assert 'service="weaver"' in text
        # 메서드/경로/상태 레이블 확인
        assert 'method="GET"' in text
        assert 'path="/api/v1/tables"' in text
        assert 'status="200"' in text
        # P50 서머리 확인
        assert 'quantile="0.5"' in text

    def test_빈_수집기_텍스트(self):
        c = SimpleMetricsCollector(service_name="empty")
        text = c.to_prometheus_text()
        # 빈 상태에서도 헤더는 출력됨
        assert "axiom_http_requests_total" in text

    def test_reset_초기화(self):
        c = SimpleMetricsCollector(service_name="test")
        c.record("GET", "/test", 200, 10.0)
        assert c.get_request_count() == 1
        c.reset()
        assert c.get_request_count() == 0

    def test_메모리_제한_1000건(self):
        """히스토그램 버킷당 최대 MAX_SAMPLES건만 유지한다."""
        c = SimpleMetricsCollector(service_name="test")
        for i in range(1500):
            c.record("GET", "/api/test", 200, float(i))
        # 내부 리스트는 1000건 이하
        durations = c._request_durations["GET:/api/test:200"]
        assert len(durations) <= c.MAX_SAMPLES

    def test_다양한_상태_코드_분리(self):
        c = SimpleMetricsCollector(service_name="test")
        c.record("GET", "/api/test", 200, 10.0)
        c.record("GET", "/api/test", 404, 5.0)
        c.record("GET", "/api/test", 500, 100.0)

        text = c.to_prometheus_text()
        assert 'status="200"' in text
        assert 'status="404"' in text
        assert 'status="500"' in text

    def test_quantile_count_포함(self):
        """서머리에 count quantile이 포함되어야 한다."""
        c = SimpleMetricsCollector(service_name="test")
        for _ in range(10):
            c.record("GET", "/api/test", 200, 10.0)

        text = c.to_prometheus_text()
        assert 'quantile="count"' in text
        assert "} 10" in text  # 10건


# ── PrometheusMiddleware 테스트 ── #


class TestPrometheusMiddleware:
    """ASGI 미들웨어 동작 검증."""

    @pytest.mark.asyncio
    async def test_http_요청_계측(self):
        """일반 HTTP 요청이 collector에 기록된다."""
        collector = SimpleMetricsCollector(service_name="test")

        # 가짜 ASGI 앱: 200 응답
        async def fake_app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200})
            await send({"type": "http.response.body", "body": b"ok"})

        middleware = PrometheusMiddleware(fake_app, collector=collector)

        scope = {"type": "http", "method": "GET", "path": "/api/v1/test"}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        assert collector.get_request_count() == 1
        text = collector.to_prometheus_text()
        assert 'path="/api/v1/test"' in text

    @pytest.mark.asyncio
    async def test_health_경로_제외(self):
        """헬스체크 경로는 계측하지 않는다."""
        collector = SimpleMetricsCollector(service_name="test")

        async def fake_app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200})

        middleware = PrometheusMiddleware(fake_app, collector=collector)

        for path in ["/health", "/health/live", "/health/ready", "/metrics"]:
            scope = {"type": "http", "method": "GET", "path": path}
            await middleware(scope, AsyncMock(), AsyncMock())

        assert collector.get_request_count() == 0

    @pytest.mark.asyncio
    async def test_websocket_통과(self):
        """WebSocket 요청은 계측 없이 통과한다."""
        collector = SimpleMetricsCollector(service_name="test")
        called = {"count": 0}

        async def fake_app(scope, receive, send):
            called["count"] += 1

        middleware = PrometheusMiddleware(fake_app, collector=collector)

        scope = {"type": "websocket", "path": "/ws"}
        await middleware(scope, AsyncMock(), AsyncMock())

        assert called["count"] == 1
        assert collector.get_request_count() == 0

    @pytest.mark.asyncio
    async def test_uuid_경로_정규화(self):
        """UUID가 포함된 경로가 {id}로 치환되어 기록된다."""
        collector = SimpleMetricsCollector(service_name="test")

        async def fake_app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200})

        middleware = PrometheusMiddleware(fake_app, collector=collector)

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/cases/550e8400-e29b-41d4-a716-446655440000",
        }
        await middleware(scope, AsyncMock(), AsyncMock())

        text = collector.to_prometheus_text()
        assert "/api/v1/cases/{id}" in text

    @pytest.mark.asyncio
    async def test_예외_발생_시에도_기록(self):
        """앱에서 예외가 발생해도 status=500으로 기록된다."""
        collector = SimpleMetricsCollector(service_name="test")

        async def failing_app(scope, receive, send):
            raise RuntimeError("boom")

        middleware = PrometheusMiddleware(failing_app, collector=collector)

        scope = {"type": "http", "method": "POST", "path": "/api/v1/fail"}

        with pytest.raises(RuntimeError, match="boom"):
            await middleware(scope, AsyncMock(), AsyncMock())

        assert collector.get_request_count() == 1
        text = collector.to_prometheus_text()
        assert 'status="500"' in text


# ── setup_prometheus 헬퍼 테스트 ── #


class TestSetupPrometheus:
    """setup_prometheus 헬퍼 함수 검증."""

    def test_collector_반환(self):
        """setup_prometheus가 collector를 반환한다."""

        class FakeApp:
            def add_middleware(self, cls, **kwargs):
                self._middleware = (cls, kwargs)

        app = FakeApp()
        collector = setup_prometheus(app, service_name="my-svc")

        assert isinstance(collector, SimpleMetricsCollector)
        assert collector.service_name == "my-svc"
        # 미들웨어가 등록되었는지 확인
        assert app._middleware[0] == PrometheusMiddleware
