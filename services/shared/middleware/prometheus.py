"""Prometheus 자동 계측 미들웨어.

기존 서비스별 메트릭 코드를 감사하고,
prometheus-fastapi-instrumentator 패턴을 공통 설정으로 제공한다.

기존 메트릭 현황 (감사 결과):
- Core:  MetricsRegistry    — outbox/DLQ/relay 카운터+게이지 (render_prometheus)
- Weaver: MetricsService    — rate_limit/idempotency 레이블 카운터 (render_prometheus)
- Vision: OperationalMetricsCollector — RCA 호출/지연/실패율 (render_prometheus)
- Oracle: /metrics 엔드포인트는 cache 모듈에서 제공 (시멘틱 캐시 히트/미스)

이 공통 모듈은 기존 서비스별 메트릭을 대체하지 않고,
HTTP 요청 수/지연 계측을 서비스 공통으로 추가한다.
기존 /metrics 엔드포인트에 공통 메트릭 텍스트를 병합(append)하는 방식.

Note: prometheus-fastapi-instrumentator 패키지가 없으면
기본 수동 계측으로 폴백한다 (의존성 추가 전까지).
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger("axiom.shared.prometheus")

# ── 경로 정규화: 경로 파라미터를 제거하여 카디널리티 폭발을 방지한다 ──

# 메트릭 수집에서 제외할 경로 (헬스체크/메트릭 자체)
_SKIP_PATHS = frozenset({
    "/health", "/healthz", "/metrics",
    "/health/live", "/health/ready", "/health/startup",
})

# UUID 패턴을 {id}로 치환 — 카디널리티 제한
import re
_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
# 순수 숫자 경로 세그먼트도 치환
_NUMERIC_RE = re.compile(r"/\d+(?=/|$)")


def _normalize_path(path: str) -> str:
    """경로에서 UUID와 숫자 ID를 치환하여 메트릭 카디널리티를 제한한다.

    예: /api/v1/cases/550e8400-.../documents → /api/v1/cases/{id}/documents
        /api/v1/users/42 → /api/v1/users/{id}
    """
    path = _UUID_RE.sub("{id}", path)
    path = _NUMERIC_RE.sub("/{id}", path)
    return path


class SimpleMetricsCollector:
    """기본 요청 메트릭 수집기 — 외부 의존성 없이 동작.

    수집 항목:
    - 엔드포인트별 요청 수 (method + path + status_code)
    - 엔드포인트별 응답 지연 (P50, P95, P99 계산용 히스토그램)

    /metrics 엔드포인트에서 Prometheus text format으로 노출한다.
    """

    # 히스토그램 버킷당 최대 샘플 수 — 메모리 제한
    MAX_SAMPLES = 1000

    def __init__(self, service_name: str = "unknown"):
        self.service_name = service_name
        # 카운터: "METHOD:path:status" → 누적 횟수
        self._request_count: dict[str, int] = defaultdict(int)
        # 지연 히스토그램: "METHOD:path:status" → 최근 N건 지연(ms)
        self._request_durations: dict[str, list[float]] = defaultdict(list)

    def record(self, method: str, path: str, status_code: int, duration_ms: float) -> None:
        """HTTP 요청 1건의 메트릭을 기록한다.

        Args:
            method: HTTP 메서드 (GET, POST 등)
            path: 정규화된 경로 (/api/v1/cases/{id})
            status_code: HTTP 응답 상태 코드
            duration_ms: 응답 지연 (밀리초)
        """
        key = f"{method}:{path}:{status_code}"
        self._request_count[key] += 1

        durations = self._request_durations[key]
        durations.append(duration_ms)
        # 메모리 제한: 최근 MAX_SAMPLES건만 유지
        if len(durations) > self.MAX_SAMPLES:
            self._request_durations[key] = durations[-self.MAX_SAMPLES:]

    def get_request_count(self) -> int:
        """전체 요청 수를 반환한다."""
        return sum(self._request_count.values())

    def reset(self) -> None:
        """모든 메트릭을 초기화한다 (테스트용)."""
        self._request_count.clear()
        self._request_durations.clear()

    def to_prometheus_text(self) -> str:
        """Prometheus exposition format 텍스트를 생성한다.

        생성하는 메트릭:
        - axiom_http_requests_total (counter): 엔드포인트별 요청 수
        - axiom_http_request_duration_ms (summary): 엔드포인트별 P50/P95/P99 지연
        """
        lines: list[str] = []

        # ── 요청 카운터 ──
        lines.append("# HELP axiom_http_requests_total Total HTTP requests")
        lines.append("# TYPE axiom_http_requests_total counter")
        for key, count in sorted(self._request_count.items()):
            method, path, status = key.split(":", 2)
            lines.append(
                f'axiom_http_requests_total{{service="{self.service_name}",'
                f'method="{method}",path="{path}",status="{status}"}} {count}'
            )

        # ── 지연 서머리 (P50/P95/P99) ──
        lines.append("# HELP axiom_http_request_duration_ms HTTP request duration in ms")
        lines.append("# TYPE axiom_http_request_duration_ms summary")
        for key, durations in sorted(self._request_durations.items()):
            if not durations:
                continue
            method, path, _status = key.split(":", 2)
            sorted_d = sorted(durations)
            n = len(sorted_d)
            p50 = sorted_d[n // 2]
            p95 = sorted_d[int(n * 0.95)] if n >= 2 else sorted_d[-1]
            p99 = sorted_d[int(n * 0.99)] if n >= 2 else sorted_d[-1]
            base = f'service="{self.service_name}",method="{method}",path="{path}"'
            lines.append(f'axiom_http_request_duration_ms{{{base},quantile="0.5"}} {p50:.1f}')
            lines.append(f'axiom_http_request_duration_ms{{{base},quantile="0.95"}} {p95:.1f}')
            lines.append(f'axiom_http_request_duration_ms{{{base},quantile="0.99"}} {p99:.1f}')
            lines.append(f'axiom_http_request_duration_ms{{{base},quantile="count"}} {n}')

        return "\n".join(lines) + "\n"


class PrometheusMiddleware:
    """ASGI 미들웨어 — 모든 HTTP 요청의 수와 지연을 자동 계측한다.

    AccessLogMiddleware와 동일한 raw ASGI 방식으로 구현한다.
    (BaseHTTPMiddleware는 body 읽기 데드락 위험이 있어 사용하지 않는다.)

    설계 결정:
    - /health, /metrics 경로는 계측에서 제외 (자기 참조 방지)
    - UUID/숫자 경로 파라미터를 정규화하여 카디널리티 폭발 방지
    - 기존 서비스별 /metrics 엔드포인트를 훼손하지 않음
    - collector 인스턴스를 외부에서 주입받아 /metrics에서 텍스트를 가져갈 수 있음

    사용법:
        from shared.middleware.prometheus import PrometheusMiddleware, SimpleMetricsCollector

        collector = SimpleMetricsCollector(service_name="weaver")
        app.add_middleware(PrometheusMiddleware, collector=collector)

        # 기존 /metrics 엔드포인트에서 collector.to_prometheus_text()를 병합
    """

    def __init__(self, app, collector: SimpleMetricsCollector | None = None):
        self.app = app
        self.collector = collector or SimpleMetricsCollector()

    async def __call__(self, scope, receive, send):
        # HTTP가 아닌 요청 (websocket, lifespan 등)은 그냥 통과
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        path: str = scope.get("path", "")

        # 헬스체크/메트릭 경로는 계측하지 않는다
        if path in _SKIP_PATHS:
            await self.app(scope, receive, send)
            return

        method: str = scope.get("method", "?")
        normalized_path = _normalize_path(path)
        status_code = 500  # 기본값: 예외 발생 시 500
        start = time.monotonic()

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 500)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = round((time.monotonic() - start) * 1000, 2)
            self.collector.record(method, normalized_path, status_code, duration_ms)


def setup_prometheus(
    app,
    service_name: str = "unknown",
) -> SimpleMetricsCollector:
    """FastAPI 앱에 Prometheus 자동 계측을 설정하는 헬퍼 함수.

    1. SimpleMetricsCollector 인스턴스를 생성한다
    2. PrometheusMiddleware를 등록한다
    3. collector를 반환하여 /metrics 엔드포인트에서 사용할 수 있게 한다

    기존 /metrics 엔드포인트가 있는 서비스에서의 사용 예:

        collector = setup_prometheus(app, service_name="weaver")

        @app.get("/metrics", response_class=PlainTextResponse)
        async def metrics():
            # 기존 서비스별 메트릭
            text = metrics_service.render_prometheus()
            # 공통 HTTP 요청 메트릭 병합
            text += collector.to_prometheus_text()
            return text

    Returns:
        SimpleMetricsCollector 인스턴스 (to_prometheus_text()로 텍스트 추출)
    """
    collector = SimpleMetricsCollector(service_name=service_name)
    app.add_middleware(PrometheusMiddleware, collector=collector)
    logger.info(
        "Prometheus 자동 계측 설정 완료: service=%s", service_name,
    )
    return collector
