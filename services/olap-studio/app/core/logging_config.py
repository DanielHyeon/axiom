"""구조화 로깅 설정 — structlog 표준화.

모든 OLAP Studio 모듈에서 일관된 로깅 패턴을 사용하도록 설정한다.
JSON 포맷 + 요청 ID/테넌트 ID 자동 바인딩.
"""
from __future__ import annotations

import structlog


def configure_logging(json_format: bool = False) -> None:
    """structlog을 설정한다.

    Args:
        json_format: True면 JSON 출력 (프로덕션), False면 콘솔 출력 (개발)
    """
    processors: list[structlog.types.Processor] = [
        # contextvars에 바인딩된 값 (request_id, tenant_id 등) 자동 병합
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if json_format:
        # 프로덕션: JSON 라인 포맷 — 로그 수집기(Loki, ELK 등)에 최적
        processors.append(structlog.processors.JSONRenderer())
    else:
        # 개발: 컬러 콘솔 출력 — 가독성 우선
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = __name__) -> structlog.stdlib.BoundLogger:
    """모듈별 로거를 가져온다.

    사용 예시:
        from app.core.logging_config import get_logger
        logger = get_logger(__name__)
        logger.info("event_name", key="value")
    """
    return structlog.get_logger(name)
