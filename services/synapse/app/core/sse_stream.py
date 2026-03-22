"""범용 SSE 스트리밍 유틸리티 — 장기 작업 진행률 전송.

asyncio.Queue 기반으로 이벤트를 발행하고,
StreamingResponse 에서 __aiter__ 로 소비하는 구조이다.
NDJSON 형식으로 한 줄씩 전송하여 프론트엔드가 실시간으로 파싱한다.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class SSEStream:
    """asyncio.Queue 기반 SSE 이벤트 스트림.

    사용법:
        stream = SSEStream()
        # 프로듀서: stream.emit({"type": "progress", "value": 50})
        # 소비자 (StreamingResponse): async for chunk in stream: ...
        # 완료 시: stream.complete()
    """

    def __init__(self, maxsize: int = 2000):
        # 큐 크기를 제한해서 메모리 과다 사용 방지
        self._queue: asyncio.Queue[str] = asyncio.Queue(maxsize=maxsize)
        # 스트림이 끝났는지 알려주는 신호
        self._done = asyncio.Event()

    def emit(self, event_data: dict[str, Any]) -> None:
        """이벤트를 큐에 추가한다 (논블로킹).

        큐가 가득 차면 이벤트를 버리고 경고를 남긴다.
        네트워크 지연으로 소비가 느려질 때 발생할 수 있다.
        """
        try:
            line = json.dumps(event_data, ensure_ascii=False, default=str) + "\n"
            self._queue.put_nowait(line)
        except asyncio.QueueFull:
            logger.warning(
                "sse_queue_full_event_dropped",
                event_type=event_data.get("type", "unknown"),
            )

    def complete(self) -> None:
        """스트림 종료 신호를 보낸다.

        이 메서드 호출 후 잔여 이벤트를 모두 소비한 뒤 이터레이션이 끝난다.
        """
        self._done.set()

    async def __aiter__(self):
        """비동기 이터레이터 — StreamingResponse 에서 사용.

        완료 신호를 받을 때까지 큐에서 이벤트를 꺼내 yield 한다.
        0.25초마다 타임아웃을 두어 완료 여부를 확인한다.
        """
        while not self._done.is_set():
            try:
                # 0.25초 대기 → 이벤트 없으면 done 플래그 재확인
                ev = await asyncio.wait_for(self._queue.get(), timeout=0.25)
                yield ev
            except asyncio.TimeoutError:
                # 타임아웃 = 새 이벤트가 없으니 done 확인 후 재시도
                pass

        # 완료 후 큐에 남은 이벤트를 모두 내보낸다 (drain)
        while not self._queue.empty():
            yield self._queue.get_nowait()
