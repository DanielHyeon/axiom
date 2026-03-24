"""Fail-Silent 이벤트 발행 — 실패해도 API 응답을 차단하지 않는다.

왜 필요한가?
    이벤트 버스(Redis Streams)가 잠깐 죽어도 사용자 요청은 정상 처리되어야 한다.
    Outbox 테이블에 이미 기록되었으므로 Relay Worker가 나중에 재발행한다.

사용법:
    from shared.events import safe_publish

    # 이 호출이 실패해도 API 응답에 영향 없음
    ok = await safe_publish(
        topic="quality.score.updated",
        event_data={"table_id": 123, "score": 0.85},
        timeout=3.0,
    )
    if not ok:
        # 실패 로그는 이미 찍혔으니, 필요하면 추가 처리만
        pass
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger("axiom.events")

# --- Redis 클라이언트 (서비스 시작 시 set_redis_client()로 주입) ---
_redis_client: Any | None = None


def set_redis_client(client: Any) -> None:
    """Redis 클라이언트를 주입한다.

    서비스 시작(lifespan) 시 한 번만 호출하면 된다.
    예: set_redis_client(aioredis.from_url("redis://redis-bus:6379"))
    """
    global _redis_client
    _redis_client = client
    logger.info("이벤트 발행용 Redis 클라이언트 설정 완료")


def get_redis_client() -> Any | None:
    """현재 설정된 Redis 클라이언트를 반환한다."""
    return _redis_client


async def safe_publish(
    topic: str,
    event_data: dict,
    timeout: float = 3.0,
) -> bool:
    """이벤트 발행 — 실패해도 API 응답을 차단하지 않는다.

    3초 타임아웃 + try/except로 감싸서 발행 실패가 핵심 로직에 영향 없도록 한다.
    Outbox 테이블에 이미 기록되었으므로 Relay Worker가 나중에 재발행한다.

    Args:
        topic: Redis Stream 토픽 이름 (예: "quality.score.updated")
        event_data: 발행할 이벤트 데이터 (딕셔너리)
        timeout: 최대 대기 시간 (초, 기본 3초)

    Returns:
        True면 발행 성공, False면 실패 (로그만 남기고 넘어간다)
    """
    if _redis_client is None:
        logger.warning(
            "Redis 클라이언트가 설정되지 않음 — 이벤트 발행 건너뜀: topic=%s",
            topic,
        )
        return False

    try:
        # 타임아웃 안에 Redis XADD 완료해야 한다
        message = {"data": json.dumps(event_data, ensure_ascii=False, default=str)}
        await asyncio.wait_for(
            _redis_client.xadd(topic, message),
            timeout=timeout,
        )
        logger.debug("이벤트 발행 성공: topic=%s", topic)
        return True

    except asyncio.TimeoutError:
        # 3초 안에 Redis가 응답하지 않았다
        logger.error(
            "이벤트 발행 타임아웃 (%.1f초): topic=%s — "
            "Outbox Relay가 나중에 재발행할 것이다",
            timeout,
            topic,
        )
        return False

    except Exception:
        # Redis 연결 끊김, 네트워크 오류 등 모든 예외를 잡는다
        logger.exception(
            "이벤트 발행 실패: topic=%s — "
            "Outbox Relay가 나중에 재발행할 것이다",
            topic,
        )
        return False
