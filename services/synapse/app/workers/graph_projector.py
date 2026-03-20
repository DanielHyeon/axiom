"""
Graph Projector Worker — 이벤트→Neo4j 그래프 실시간 동기화

BusinessOS의 "Ontology Updater" 패턴을 구현한다.
Redis Stream에서 모든 서비스 이벤트를 소비하고,
PROJECTION_RULES에 정의된 Cypher 쿼리를 실행하여
온톨로지 그래프를 "살아있는 디지털 트윈"으로 유지한다.

처리 흐름:
  1. 4개 서비스 스트림에서 이벤트 읽기 (consumer group: graph-projector)
  2. event_type으로 PROJECTION_RULES 조회
  3. params_map에 따라 payload에서 Cypher 파라미터 추출
  4. neo4j_client.execute_write로 그래프 업데이트
  5. 모든 규칙 실행 후 메시지 ACK (실패한 규칙이 있어도 ACK)

설계 원칙:
  - Graph Projector는 GWT Consumer보다 먼저 실행되어야 한다 (멱등성으로 보장)
  - 매핑에 없는 이벤트는 조용히 스킵한다 (skipped 카운트만 증가)
  - 개별 규칙 실패는 로깅하되 나머지 규칙과 ACK는 계속 진행한다
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

from app.workers.projection_rules import PROJECTION_RULES

logger = logging.getLogger(__name__)

# 이벤트를 수신할 Redis Stream 목록 (4개 서비스)
STREAMS = [
    "axiom:core:events",
    "axiom:synapse:events",
    "axiom:vision:events",
    "axiom:weaver:events",
]


class GraphProjectorWorker:
    """이벤트→Neo4j 그래프 프로젝션 워커.

    Redis Stream Consumer Group 패턴으로 동작하며,
    이벤트 타입별 선언적 Cypher 매핑(PROJECTION_RULES)을 기반으로
    온톨로지 그래프를 실시간 갱신한다.
    """

    def __init__(
        self,
        redis_client,
        neo4j_client,
        projection_rules: dict[str, list[dict]] | None = None,
        consumer_group: str = "graph-projector",
        consumer_name: str = "projector-1",
        poll_interval: float = 1.0,
    ):
        """
        Args:
            redis_client: redis.asyncio.Redis 인스턴스
            neo4j_client: Neo4jClient 인스턴스 (execute_write 메서드 필수)
            projection_rules: 이벤트→Cypher 매핑 딕셔너리 (기본: PROJECTION_RULES)
            consumer_group: Redis consumer group 이름
            consumer_name: 이 워커 인스턴스의 고유 이름
            poll_interval: 메시지 없을 때 대기 시간 (초)
        """
        self._redis = redis_client
        self._neo4j = neo4j_client
        self._rules = projection_rules if projection_rules is not None else PROJECTION_RULES
        self._group = consumer_group
        self._consumer = consumer_name
        self._poll_interval = poll_interval
        self._running = False

        # 통계 카운터: 모니터링 및 디버깅 용도
        self._stats: dict[str, int] = {
            "projected": 0,  # Cypher 실행 성공 횟수
            "skipped": 0,    # 매핑 없어서 스킵한 이벤트 수
            "failed": 0,     # Cypher 실행 실패 횟수
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

        logger.info(
            "Graph Projector 시작: rules=%d개 이벤트 타입 매핑, streams=%s",
            len(self._rules),
            STREAMS,
        )

        while self._running:
            try:
                # 모든 스트림에서 미처리 메시지를 한 번에 읽는다
                messages = await self._redis.xreadgroup(
                    groupname=self._group,
                    consumername=self._consumer,
                    streams={s: ">" for s in STREAMS},
                    count=100,
                    block=int(self._poll_interval * 1000),
                )

                for stream_name, entries in messages:
                    for msg_id, data in entries:
                        await self._project(stream_name, msg_id, data)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Graph Projector 폴링 오류: %s", e, exc_info=True)
                await asyncio.sleep(self._poll_interval)

        logger.info("Graph Projector 종료: stats=%s", self._stats)

    async def stop(self) -> None:
        """워커를 정상 종료한다. 현재 처리 중인 메시지 완료 후 루프가 중단된다."""
        self._running = False
        logger.info("Graph Projector 종료 요청됨")

    @property
    def stats(self) -> dict[str, int]:
        """현재 통계 카운터를 반환한다 (읽기 전용 복사본)."""
        return dict(self._stats)

    # ── 프로젝션 처리 ────────────────────────────────────────

    async def _project(self, stream: str, msg_id: str, data: dict) -> None:
        """단일 이벤트 메시지를 프로젝션 규칙에 따라 처리한다.

        1. event_type으로 규칙 목록을 조회한다 (없으면 스킵).
        2. payload를 파싱하고 각 규칙의 params_map을 해석한다.
        3. 모든 규칙의 Cypher를 순서대로 실행한다.
        4. 실패한 규칙이 있더라도 나머지 규칙을 계속 실행하고, 마지막에 ACK한다.
        """
        event_type = data.get("event_type", "")

        # 매핑 테이블에 없는 이벤트는 조용히 스킵
        rules = self._rules.get(event_type)
        if not rules:
            self._stats["skipped"] += 1
            await self._redis.xack(stream, self._group, msg_id)
            return

        # payload 파싱 — 문자열이면 JSON 디코딩
        payload = data.get("payload", "{}")
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                logger.warning(
                    "Graph Projector: payload JSON 파싱 실패, event=%s, msg_id=%s",
                    event_type, msg_id,
                )
                payload = {}

        # 공통 파라미터 추출
        case_id = payload.get("case_id", data.get("case_id", ""))
        event_id = data.get("event_id", str(uuid.uuid4()))

        # 각 규칙을 순서대로 실행
        rule_success = 0
        rule_fail = 0

        for rule in rules:
            try:
                # params_map에 따라 Cypher 파라미터를 해석
                params = self._resolve_params(
                    rule["params_map"],
                    payload=payload,
                    case_id=case_id,
                    event_id=event_id,
                    full_payload=json.dumps(payload, ensure_ascii=False),
                )

                # Neo4j 쓰기 트랜잭션으로 Cypher 실행
                await self._neo4j.execute_write(rule["cypher"], params)

                logger.debug(
                    "Graph Projection 완료: event=%s, rule='%s'",
                    event_type, rule["description"],
                )
                rule_success += 1
                self._stats["projected"] += 1

            except Exception as e:
                logger.error(
                    "Graph Projection 실패: event=%s, rule='%s', error=%s",
                    event_type, rule["description"], e,
                    exc_info=True,
                )
                rule_fail += 1
                self._stats["failed"] += 1

        # 실패 여부와 관계없이 ACK — pending list에 무한히 쌓이는 것을 방지
        # 실패한 규칙은 로그로 추적하고, 필요 시 수동 재처리한다
        if rule_fail > 0:
            logger.warning(
                "Graph Projector: 부분 실패 후 ACK, event=%s, "
                "성공=%d, 실패=%d, msg_id=%s",
                event_type, rule_success, rule_fail, msg_id,
            )

        await self._redis.xack(stream, self._group, msg_id)

    # ── 파라미터 해석 ────────────────────────────────────────

    def _resolve_params(
        self,
        params_map: dict[str, str],
        *,
        payload: dict[str, Any],
        case_id: str,
        event_id: str,
        full_payload: str,
    ) -> dict[str, Any]:
        """params_map 정의에 따라 Cypher 쿼리 파라미터를 해석한다.

        해석 규칙:
          - "$event_id"     → event_id 값
          - "$full_payload" → payload 전체 JSON 문자열
          - "payload.xxx"   → payload["xxx"] (없으면 None)
          - 그 외            → 리터럴 문자열 값

        case_id는 항상 자동으로 포함된다.
        """
        resolved: dict[str, Any] = {"case_id": case_id}

        for param_name, source in params_map.items():
            if source == "$event_id":
                resolved[param_name] = event_id
            elif source == "$full_payload":
                resolved[param_name] = full_payload
            elif source.startswith("payload."):
                # payload에서 중첩 없이 1단계 키만 지원
                key = source[len("payload."):]
                resolved[param_name] = payload.get(key)
            else:
                # 리터럴 값 그대로 사용
                resolved[param_name] = source

        return resolved
