"""텔레메트리 계측 -- OpenTelemetry 기반 분산 추적 + 메트릭.

opentelemetry 패키지가 설치되어 있을 때만 활성화된다.
미설치 시 모든 함수가 no-op으로 동작한다.
"""
from __future__ import annotations

import functools
import time
from typing import Any, Callable

import structlog

logger = structlog.get_logger(__name__)

# OpenTelemetry 사용 가능 여부
_OTEL_AVAILABLE = False
_tracer = None
_meter = None

try:
    from opentelemetry import trace, metrics
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter

    _OTEL_AVAILABLE = True
except ImportError:
    pass


def setup_telemetry(service_name: str = "olap-studio") -> None:
    """OpenTelemetry를 초기화한다.

    패키지 미설치 시 경고 로그만 남기고 무시한다.
    """
    global _tracer, _meter

    if not _OTEL_AVAILABLE:
        logger.info("telemetry_disabled", reason="opentelemetry 패키지 미설치")
        return

    try:
        # Tracer 설정
        provider = TracerProvider()
        # 개발 환경: 콘솔 출력 (프로덕션에서는 OTLP Exporter로 교체)
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer(service_name)

        # Meter 설정
        _meter = metrics.get_meter(service_name)

        logger.info("telemetry_initialized", service=service_name)
    except Exception as e:
        logger.warning("telemetry_init_failed", error=str(e))


def trace_span(name: str) -> Callable:
    """함수에 OpenTelemetry 스팬을 추가하는 데코레이터.

    패키지 미설치 시 원래 함수를 그대로 반환한다.

    사용 예:
        @trace_span("pivot.execute")
        async def execute_pivot(...):
    """

    def decorator(func: Callable) -> Callable:
        if not _OTEL_AVAILABLE or _tracer is None:
            return func

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            with _tracer.start_as_current_span(name) as span:
                try:
                    result = await func(*args, **kwargs)
                    span.set_status(trace.StatusCode.OK)
                    return result
                except Exception as e:
                    span.set_status(trace.StatusCode.ERROR, str(e))
                    span.record_exception(e)
                    raise

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            with _tracer.start_as_current_span(name) as span:
                try:
                    result = func(*args, **kwargs)
                    span.set_status(trace.StatusCode.OK)
                    return result
                except Exception as e:
                    span.set_status(trace.StatusCode.ERROR, str(e))
                    span.record_exception(e)
                    raise

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# --- 메트릭 카운터 ---

_counters: dict[str, Any] = {}


def increment_counter(
    name: str, value: int = 1, labels: dict[str, str] | None = None
) -> None:
    """메트릭 카운터를 증가시킨다. OTel 미설치 시 no-op."""
    if not _OTEL_AVAILABLE or _meter is None:
        return

    if name not in _counters:
        _counters[name] = _meter.create_counter(name)

    _counters[name].add(value, labels or {})


def record_duration(
    name: str, duration_ms: float, labels: dict[str, str] | None = None
) -> None:
    """실행 시간 히스토그램을 기록한다. OTel 미설치 시 no-op."""
    if not _OTEL_AVAILABLE or _meter is None:
        return

    hist_name = f"{name}_duration_ms"
    if hist_name not in _counters:
        _counters[hist_name] = _meter.create_histogram(hist_name, unit="ms")

    _counters[hist_name].record(duration_ms, labels or {})
