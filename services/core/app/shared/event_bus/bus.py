"""프로세스 내 모듈 간 이벤트 전달.

외부 Redis Streams(Transactional Outbox)와 별개로,
Core 내부 4개 모듈(process, agent, case, watch) 간 비동기 통신을 담당한다.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable, Coroutine

import logging

logger = logging.getLogger(__name__)

EventHandler = Callable[..., Coroutine[Any, Any, None]]


class InternalEventBus:
    """프로세스 내 모듈 간 이벤트 버스.

    사용 예:
        # 발행자 모듈 (process)
        await internal_event_bus.publish("WORKITEM_COMPLETED", {"workitem_id": "..."})

        # 구독자 모듈 (watch)
        internal_event_bus.subscribe("WORKITEM_COMPLETED", watch_handler)
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """이벤트 타입에 핸들러를 등록한다."""
        self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """핸들러를 제거한다."""
        handlers = self._handlers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    async def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        """이벤트를 모든 등록된 핸들러에 전달한다.

        각 핸들러는 독립적으로 실행되며, 하나의 핸들러 실패가 다른 핸들러에 영향을 주지 않는다.
        """
        handlers = self._handlers.get(event_type, [])
        for handler in handlers:
            try:
                await handler(payload)
            except Exception:
                logger.exception(
                    "internal_event_bus handler failed: event_type=%s handler=%s",
                    event_type,
                    getattr(handler, "__qualname__", str(handler)),
                )

    def clear(self) -> None:
        """모든 구독을 해제한다. 테스트용."""
        self._handlers.clear()


# Singleton
internal_event_bus = InternalEventBus()
