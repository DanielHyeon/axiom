"""
GWT Consumer Worker — Redis Stream 이벤트를 GWT Engine으로 전달

Redis Stream에서 모든 서비스 이벤트를 소비하여 GWT Engine의
Given-When-Then 룰 매칭/실행을 트리거한다.

처리 흐름:
  1. 4개 서비스 스트림에서 이벤트 읽기 (consumer group: gwt-engine)
  2. 필터링: source_worker="gwt-engine" 이벤트 스킵 (자가 소비 방지)
  3. 필터링: case_id 없는 이벤트 스킵 (GWT는 케이스 컨텍스트 필수)
  4. GWTEngine.handle_event() 호출
  5. 처리 완료 후 메시지 ACK

설계 원칙:
  - GraphProjector와 동일 스트림을 소비하되 별도 consumer group 사용
  - 멱등성으로 실행 순서 문제를 해결 (GWT Engine이 항상 Neo4j 최신 상태 조회)
  - GWT Engine이 발행한 이벤트에는 source_worker="gwt-engine"이 포함되어
    자기 자신이 발행한 이벤트를 재소비하지 않는다
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.services.gwt_engine import GWTEngine

logger = logging.getLogger(__name__)

# 이벤트를 수신할 Redis Stream 목록 (4개 서비스)
STREAMS = [
    "axiom:core:events",
    "axiom:synapse:events",
    "axiom:vision:events",
    "axiom:weaver:events",
]

# 자가 소비 방지를 위한 소스 워커 식별자
SELF_SOURCE_WORKER = "gwt-engine"


class GWTConsumerWorker:
    """모든 서비스 이벤트를 소비하여 GWT 룰 매칭/실행을 수행하는 워커.

    GWT(Given-When-Then) Engine과 연동하여:
      - Given: 온톨로지 상태 + 관련 링크 조건 (Neo4j에서 실시간 조회)
      - When: 인입 이벤트/커맨드 (이 워커가 전달)
      - Then: 상태 변경 + 새로운 이벤트 발행 (Engine이 실행)
    """

    def __init__(
        self,
        redis_client,
        gwt_engine: GWTEngine,
        consumer_group: str = "gwt-engine",
        consumer_name: str = "gwt-worker-1",
        poll_interval: float = 1.0,
    ):
        """
        Args:
            redis_client: redis.asyncio.Redis 인스턴스
            gwt_engine: GWTEngine 인스턴스 (handle_event 메서드 필수)
            consumer_group: Redis consumer group 이름
            consumer_name: 이 워커 인스턴스의 고유 이름
            poll_interval: 메시지 없을 때 대기 시간 (초)
        """
        self._redis = redis_client
        self._engine = gwt_engine
        self._group = consumer_group
        self._consumer = consumer_name
        self._poll_interval = poll_interval
        self._running = False

        # 통계 카운터: 모니터링 및 디버깅 용도
        self._stats: dict[str, int] = {
            "processed": 0,     # GWT Engine에 전달된 이벤트 수
            "skipped_self": 0,  # 자가 소비 방지로 스킵된 이벤트 수
            "skipped_no_case": 0,  # case_id 없어서 스킵된 이벤트 수
            "failed": 0,        # GWT Engine 처리 실패 수
        }

    # ── 라이프사이클 ──────────────────────────────────────────

    async def start(self) -> None:
        """워커를 시작한다.

        1. 각 스트림에 consumer group을 생성한다 (이미 존재하면 무시).
        2. 폴링 루프를 시작하여 새 메시지를 처리한다.
        3. stop()이 호출되거나 CancelledError가 발생하면 종료한다.
        """
        self._running = True

        # Consumer group 생성 — mkstream=True로 스트림이 없으면 자동 생성
        for stream in STREAMS:
            try:
                await self._redis.xgroup_create(
                    stream, self._group, id="0", mkstream=True
                )
            except Exception:
                pass  # BUSYGROUP: 이미 존재하는 그룹이면 무시

        logger.info("GWT Consumer Worker 시작: streams=%s", STREAMS)

        while self._running:
            try:
                # 모든 스트림에서 미처리 메시지를 한 번에 읽는다
                messages = await self._redis.xreadgroup(
                    groupname=self._group,
                    consumername=self._consumer,
                    streams={s: ">" for s in STREAMS},
                    count=50,
                    block=int(self._poll_interval * 1000),
                )

                for stream_name, entries in messages:
                    for msg_id, data in entries:
                        await self._process_message(stream_name, msg_id, data)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("GWT Consumer 폴링 오류: %s", e, exc_info=True)
                await asyncio.sleep(self._poll_interval)

        logger.info("GWT Consumer Worker 종료: stats=%s", self._stats)

    async def stop(self) -> None:
        """워커를 정상 종료한다. 현재 처리 중인 메시지 완료 후 루프가 중단된다."""
        self._running = False
        logger.info("GWT Consumer Worker 종료 요청됨")

    @property
    def stats(self) -> dict[str, int]:
        """현재 통계 카운터를 반환한다 (읽기 전용 복사본)."""
        return dict(self._stats)

    # ── 메시지 처리 ──────────────────────────────────────────

    async def _process_message(
        self, stream: str, msg_id: str, data: dict[str, Any]
    ) -> None:
        """단일 이벤트 메시지를 필터링하고 GWT Engine에 전달한다.

        필터링 조건 (순서대로):
          1. source_worker가 "gwt-engine"이면 스킵 (자가 소비 방지)
          2. payload에 case_id가 없으면 스킵 (GWT는 케이스 컨텍스트 필수)
        """
        event_type = data.get("event_type", "")

        # ── 필터 1: 자가 소비 방지 ──
        # GWT Engine이 발행한 이벤트를 다시 소비하면 무한 루프가 발생한다.
        # source_worker 필드로 발행 주체를 확인하여 자신이 만든 이벤트를 건너뛴다.
        source_worker = data.get("source_worker", "")
        if source_worker == SELF_SOURCE_WORKER:
            self._stats["skipped_self"] += 1
            await self._redis.xack(stream, self._group, msg_id)
            return

        # payload 파싱 — 문자열이면 JSON 디코딩
        payload = data.get("payload", "{}")
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                logger.warning(
                    "GWT Consumer: payload JSON 파싱 실패, event=%s, msg_id=%s",
                    event_type, msg_id,
                )
                payload = {}

        # ── 필터 2: case_id 필수 체크 ──
        # GWT 룰은 케이스 컨텍스트 안에서만 동작한다.
        # case_id가 없는 시스템 이벤트(메타데이터 변경 등)는 GWT 대상이 아니다.
        case_id = payload.get("case_id", data.get("case_id", ""))
        if not case_id:
            self._stats["skipped_no_case"] += 1
            await self._redis.xack(stream, self._group, msg_id)
            return

        # 공통 필드 추출
        aggregate_id = data.get("aggregate_id", "")
        tenant_id = data.get("tenant_id", "")

        try:
            # GWT Engine에 이벤트 전달 — 매칭되는 모든 룰을 실행
            results = await self._engine.handle_event(
                event_type=event_type,
                aggregate_id=aggregate_id,
                payload=payload,
                case_id=case_id,
                tenant_id=tenant_id,
            )

            # 실행 결과 로깅 — 매칭된 룰만 INFO 레벨로 기록
            for r in results:
                if r.matched:
                    logger.info(
                        "GWT 룰 실행: rule=%s, state_changes=%d, emitted_events=%d",
                        r.rule_name,
                        len(r.state_changes),
                        len(r.emitted_events),
                    )

            self._stats["processed"] += 1

            # 처리 완료 후 ACK
            await self._redis.xack(stream, self._group, msg_id)

        except Exception as e:
            logger.error(
                "GWT 이벤트 처리 실패: event=%s, case_id=%s, error=%s",
                event_type, case_id, e,
                exc_info=True,
            )
            self._stats["failed"] += 1
            # 처리 실패 시 ACK하지 않는다 — pending list에 남아서 재시도 대상이 된다.
            # 운영 환경에서는 XCLAIM으로 일정 시간 후 다른 워커가 인수할 수 있다.
