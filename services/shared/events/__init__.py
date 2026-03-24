"""이벤트 발행/구독 공통 모듈.

Redis Streams 기반 이벤트 버스와 Transactional Outbox 패턴을 지원한다.
safe_publish()로 발행하면 실패해도 핵심 API에 영향을 주지 않는다.
"""

from .schema import EventEnvelope  # noqa: F401
from .safe_publish import safe_publish  # noqa: F401

__all__ = ["EventEnvelope", "safe_publish"]
