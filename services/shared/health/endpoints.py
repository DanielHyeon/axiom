"""Liveness / Readiness 분리 헬스 체크 엔드포인트.

- /health/live  : 프로세스 이벤트 루프가 살아있고 HTTP 응답이 가능한지 확인
- /health/ready : DB, Redis, Neo4j 등 외부 의존 서비스 연결까지 확인

Kubernetes 등 오케스트레이터가 두 프로브를 분리하여 사용한다:
- livenessProbe  → /health/live  (실패 시 컨테이너 재시작)
- readinessProbe → /health/ready (실패 시 트래픽 차단)

사용법:
    from shared.health import create_health_router

    # 기본 (의존성 체크 없음)
    app.include_router(create_health_router(service_name="weaver"))

    # 커스텀 의존성 체크 추가
    async def check_pg():
        # DB 핑 로직
        return True

    app.include_router(
        create_health_router(
            service_name="weaver",
            dependency_checks={"postgres": check_pg},
        )
    )
"""

from __future__ import annotations

import time
from typing import Awaitable, Callable

from fastapi import APIRouter
from fastapi.responses import JSONResponse

# (start_time은 라우터 생성 시점에 캡처 — 아래 factory 참조)

# 의존성 체크 함수 타입: 이름 없이 True/False만 반환
DependencyCheck = Callable[[], Awaitable[bool]]


def create_health_router(
    service_name: str = "unknown",
    dependency_checks: dict[str, DependencyCheck] | None = None,
) -> APIRouter:
    """서비스별 헬스 체크 라우터를 생성한다.

    Args:
        service_name: 서비스 식별 이름 (예: "weaver", "oracle")
        dependency_checks: 의존성 이름 → 체크 함수 딕셔너리
            체크 함수는 async 함수로, 정상이면 True, 비정상이면 False를 반환한다.
            예: {"postgres": check_pg, "redis": check_redis}

    Returns:
        FastAPI APIRouter (tags=["health"])
    """
    router = APIRouter(tags=["health"])
    checks = dependency_checks or {}
    # 라우터 생성 시점에 시작 시각 캡처 (모듈 레벨보다 정확)
    state = {"start_time": time.monotonic()}

    @router.get("/health/live")
    async def liveness():
        """라이브니스 프로브 — 프로세스가 살아있는지 확인한다.

        이벤트 루프가 동작하고 HTTP 응답을 보낼 수 있으면 성공이다.
        외부 서비스 상태는 확인하지 않는다.
        """
        uptime_seconds = round(time.monotonic() - state["start_time"], 1)
        return {
            "status": "alive",
            "service": service_name,
            "uptime_seconds": uptime_seconds,
        }

    @router.get("/health/ready")
    async def readiness():
        """레디니스 프로브 — 외부 의존 서비스 연결을 확인한다.

        등록된 모든 의존성 체크가 성공해야 ready 상태가 된다.
        하나라도 실패하면 503을 반환하여 트래픽을 차단한다.
        """
        results: dict[str, str] = {}
        all_ok = True

        for name, check_fn in checks.items():
            try:
                ok = await check_fn()
                results[name] = "ok" if ok else "fail"
                if not ok:
                    all_ok = False
            except Exception as exc:
                # 체크 함수 자체가 예외를 던지면 fail + 에러 메시지 기록
                results[name] = "fail"
                # 에러 상세 (자격증명 누출 방지를 위해 200자로 자름)
                results[f"{name}_error"] = str(exc)[:200]
                all_ok = False

        status_code = 200 if all_ok else 503
        status_text = "ready" if all_ok else "not_ready"

        return JSONResponse(
            status_code=status_code,
            content={
                "status": status_text,
                "service": service_name,
                "checks": results,
            },
        )

    return router


def create_metrics_endpoint(
    app,
    collectors: list | None = None,
    extra_renderers: list | None = None,
) -> None:
    """공통 /metrics 엔드포인트를 FastAPI 앱에 등록한다.

    기존 서비스별 /metrics가 이미 있는 경우, 이 함수를 사용하지 않고
    기존 엔드포인트에서 collector.to_prometheus_text()를 병합해도 된다.

    새 서비스이거나 /metrics가 아직 없는 경우 이 헬퍼로 한 번에 등록한다.

    Args:
        app: FastAPI 인스턴스
        collectors: SimpleMetricsCollector 리스트 — to_prometheus_text() 호출
        extra_renderers: render_prometheus() 메서드를 가진 기존 메트릭 객체 리스트
            (예: MetricsRegistry, MetricsService, OperationalMetricsCollector)

    사용법:
        from shared.health import create_metrics_endpoint
        from shared.middleware.prometheus import setup_prometheus

        collector = setup_prometheus(app, service_name="my-service")
        create_metrics_endpoint(app, collectors=[collector])

        # 기존 서비스별 메트릭도 함께 노출:
        create_metrics_endpoint(
            app,
            collectors=[collector],
            extra_renderers=[metrics_registry],
        )
    """
    from fastapi.responses import PlainTextResponse

    _collectors = collectors or []
    _renderers = extra_renderers or []

    @app.get("/metrics", response_class=PlainTextResponse)
    async def metrics():
        """통합 Prometheus 메트릭 엔드포인트.

        공통 HTTP 요청 메트릭 + 서비스별 커스텀 메트릭을 합산하여 반환한다.
        """
        parts: list[str] = []

        # 기존 서비스별 메트릭 (render_prometheus 인터페이스)
        for renderer in _renderers:
            try:
                text = renderer.render_prometheus()
                if text:
                    parts.append(text)
            except Exception:
                pass

        # 공통 HTTP 요청 메트릭 (SimpleMetricsCollector)
        for collector in _collectors:
            try:
                text = collector.to_prometheus_text()
                if text:
                    parts.append(text)
            except Exception:
                pass

        return "\n".join(parts)
