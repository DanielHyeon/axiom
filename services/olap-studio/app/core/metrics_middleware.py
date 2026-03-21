"""요청 시간 측정 미들웨어 -- 엔드포인트별 응답 시간을 기록한다."""
from __future__ import annotations

import time

from starlette.types import ASGIApp, Receive, Scope, Send
import structlog

from app.core.telemetry import record_duration, increment_counter

logger = structlog.get_logger(__name__)


class MetricsMiddleware:
    """ASGI 미들웨어 -- 요청/응답 메트릭 수집.

    각 HTTP 요청의:
      - 응답 시간 (ms)
      - 상태 코드 카운터
      - 엔드포인트별 분류
    를 기록한다.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "GET")

        # 헬스체크는 메트릭에서 제외
        if path.startswith("/health"):
            await self.app(scope, receive, send)
            return

        start = time.monotonic()
        status_code = 500  # 기본값 (응답 전 에러 시)

        async def send_wrapper(message: dict) -> None:
            nonlocal status_code
            if message.get("type") == "http.response.start":
                status_code = message.get("status", 500)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = (time.monotonic() - start) * 1000
            labels = {"method": method, "path": path, "status": str(status_code)}

            record_duration("http_request", duration_ms, labels)
            increment_counter("http_requests_total", 1, labels)

            # 느린 요청 경고 (1초 이상)
            if duration_ms > 1000:
                logger.warning(
                    "slow_request",
                    method=method,
                    path=path,
                    status=status_code,
                    duration_ms=round(duration_ms, 1),
                )
