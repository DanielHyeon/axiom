"""공통 헬스 체크 모듈.

Liveness / Readiness 프로브 엔드포인트를 제공한다.
각 서비스는 readiness 체크에 DB, Redis 등 의존성을 추가할 수 있다.
/metrics 통합 엔드포인트 팩토리도 제공한다.
"""

from .endpoints import create_health_router, create_metrics_endpoint  # noqa: F401

__all__ = ["create_health_router", "create_metrics_endpoint"]
