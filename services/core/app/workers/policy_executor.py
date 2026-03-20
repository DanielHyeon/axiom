"""
Policy Executor Worker — 이벤트 반응형 정책 자동 실행 워커

GWT Engine과의 차이:
- GWT: 온톨로지 노드 상태를 직접 변경 (Synapse 내부, Neo4j SET)
- Policy: 다른 서비스에 커맨드를 발행 (서비스 간 오케스트레이션)

실행 흐름:
  Redis Stream 이벤트 수신
  → Neo4j에서 매칭 Policy 조회 (case_id + trigger_event)
  → 트리거 조건 평가 (field/op/value 비교)
  → 쿨다운 확인 (Redis SETEX 기반)
  → 커맨드 페이로드 구성 ($trigger.payload.xxx 변수 치환)
  → POLICY_COMMAND 이벤트를 Core EventOutbox에 발행

설계 문서: docs/03_implementation/businessos-kinetic-layer-design.md §8.3
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone, date

from app.workers.base import BaseWorker

logger = logging.getLogger("axiom.workers.policy_executor")

# 소비할 Redis Stream 목록 — 3개 서비스의 이벤트를 모두 감시한다
STREAMS = [
    "axiom:core:events",
    "axiom:synapse:events",
    "axiom:vision:events",
]

# Consumer Group 이름 — 수평 확장 시 동일 그룹 내에서 이벤트가 분배된다
CONSUMER_GROUP = "policy-executor"
CONSUMER_NAME = "policy-executor-1"

# 이벤트 읽기 설정
BLOCK_MS = 1000       # xreadgroup 블로킹 대기 시간 (밀리초)
BATCH_SIZE = 50       # 한 번에 읽는 이벤트 수


class PolicyExecutorWorker(BaseWorker):
    """서비스 간 이벤트 반응형 오케스트레이션 워커

    Redis Stream에서 이벤트를 소비하고, Neo4j의 Policy 노드를 조회하여
    매칭되는 정책의 커맨드를 Core EventOutbox에 발행한다.

    쿨다운은 Redis SETEX로 관리하여 워커 재시작이나 수평 확장 시에도
    안전하게 동작한다.
    """

    def __init__(self, neo4j_driver=None):
        """
        Args:
            neo4j_driver: Neo4j AsyncDriver 인스턴스.
                          None이면 환경 변수에서 연결 정보를 읽어 자동 생성한다.
        """
        super().__init__("policy_executor")
        self._neo4j_driver = neo4j_driver

    async def run(self):
        """메인 루프 — Redis Stream에서 이벤트를 읽고 정책을 실행한다"""
        from app.core.redis_client import get_redis

        redis = get_redis()
        if redis is None:
            logger.error("Redis 연결 없음 — PolicyExecutorWorker 시작 불가")
            return

        # Neo4j 드라이버 초기화 — Core 서비스에는 neo4j_client가 없을 수 있으므로
        # 환경 변수에서 직접 연결한다
        neo4j_driver = await self._ensure_neo4j_driver()
        if neo4j_driver is None:
            logger.error("Neo4j 연결 없음 — PolicyExecutorWorker 시작 불가")
            return

        # Consumer Group 생성 (이미 존재하면 무시)
        for stream in STREAMS:
            try:
                await redis.xgroup_create(
                    stream, CONSUMER_GROUP, id="0", mkstream=True,
                )
            except Exception:
                # BUSYGROUP: Consumer Group already exists — 정상
                pass

        logger.info("PolicyExecutorWorker 시작 (streams=%s)", STREAMS)

        while self._running:
            try:
                # 3개 스트림에서 동시에 이벤트 읽기
                messages = await redis.xreadgroup(
                    groupname=CONSUMER_GROUP,
                    consumername=CONSUMER_NAME,
                    streams={s: ">" for s in STREAMS},
                    count=BATCH_SIZE,
                    block=BLOCK_MS,
                )

                for stream_name, entries in messages:
                    for msg_id, data in entries:
                        await self.process_with_retry(
                            self._process_event,
                            redis, neo4j_driver, stream_name, msg_id, data,
                        )

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("PolicyExecutorWorker 이벤트 루프 오류: %s", exc, exc_info=True)
                await asyncio.sleep(1)

        # 종료 시 Neo4j 드라이버 정리 (자체 생성한 경우만)
        if self._neo4j_driver is None and neo4j_driver is not None:
            try:
                await neo4j_driver.close()
            except Exception:
                pass

    async def _ensure_neo4j_driver(self):
        """Neo4j AsyncDriver를 확보한다 — 주입된 것이 있으면 그것을, 없으면 새로 생성한다"""
        if self._neo4j_driver is not None:
            return self._neo4j_driver

        try:
            import os
            from neo4j import AsyncGraphDatabase

            uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
            user = os.getenv("NEO4J_USER", "neo4j")
            password = os.getenv("NEO4J_PASSWORD", "password")

            driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
            logger.info("PolicyExecutorWorker Neo4j 연결 생성: %s", uri)
            return driver
        except Exception as exc:
            logger.error("Neo4j 드라이버 생성 실패: %s", exc, exc_info=True)
            return None

    async def _process_event(
        self,
        redis,
        neo4j_driver,
        stream_name: str,
        msg_id: str,
        data: dict,
    ):
        """이벤트 1건 처리 — 정책 매칭 → 조건 평가 → 커맨드 발행 → ACK"""
        event_type = data.get("event_type", "")
        tenant_id = (data.get("tenant_id") or "").strip()

        # 페이로드 파싱 — JSON 문자열 또는 dict
        payload_raw = data.get("payload", "{}")
        try:
            payload = json.loads(payload_raw) if isinstance(payload_raw, str) else (payload_raw or {})
        except json.JSONDecodeError:
            payload = {}

        case_id = payload.get("case_id", "")

        # case_id 없는 이벤트는 정책 매칭 불가 — ACK하고 건너뜀
        if not case_id:
            await redis.xack(stream_name, CONSUMER_GROUP, msg_id)
            return

        # tenant_id 없는 이벤트는 테넌트 격리 불가 — ACK하고 건너뜀
        if not tenant_id:
            await redis.xack(stream_name, CONSUMER_GROUP, msg_id)
            return

        # Neo4j에서 매칭되는 활성 Policy 조회 (tenant_id 격리 포함)
        policies = await self._find_matching_policies(neo4j_driver, case_id, tenant_id, event_type)

        for policy in policies:
            policy_id = policy.get("id", "")
            cooldown_seconds = policy.get("cooldown_seconds", 0)

            # 1. 쿨다운 확인 (Redis 기반)
            if not await self._check_cooldown(redis, policy_id, cooldown_seconds):
                logger.debug("Policy %s 쿨다운 중, 건너뜀", policy_id)
                continue

            # 1.5. 일일 실행 횟수 제한 확인 (Redis INCR 기반)
            max_per_day = policy.get("max_executions_per_day", 0)
            if max_per_day and max_per_day > 0:
                if not await self._check_daily_limit(redis, policy_id, max_per_day):
                    logger.warning(
                        "Policy %s 일일 실행 한도(%d) 초과, 건너뜀",
                        policy_id, max_per_day,
                    )
                    continue

            # 2. 트리거 조건 평가
            trigger_condition_raw = policy.get("trigger_condition", "{}")
            try:
                condition = json.loads(trigger_condition_raw) if isinstance(trigger_condition_raw, str) else trigger_condition_raw
            except json.JSONDecodeError:
                condition = {}

            if condition and not self._eval_condition(condition, payload):
                continue

            # 3. 커맨드 페이로드 구성 ($trigger.payload.xxx 변수 치환)
            template_raw = policy.get("command_payload_template", "{}")
            try:
                template = json.loads(template_raw) if isinstance(template_raw, str) else template_raw
            except json.JSONDecodeError:
                template = {}

            command_payload = self._resolve_template(template, payload, case_id, tenant_id)

            # 4. POLICY_COMMAND 이벤트를 Core EventOutbox에 발행
            target_service = policy.get("target_service", "core")
            target_command = policy.get("target_command", "")

            await self._publish_policy_command(
                event_type="POLICY_COMMAND",
                aggregate_id=policy_id,
                case_id=case_id,
                tenant_id=tenant_id,
                command=target_command,
                target_service=target_service,
                command_payload=command_payload,
                triggered_by_event=event_type,
                triggered_by_policy=policy_id,
            )

            # 5. 쿨다운 설정
            effective_cooldown = cooldown_seconds if cooldown_seconds > 0 else 3600
            await self._set_cooldown(redis, policy_id, effective_cooldown)

            logger.info(
                "Policy 실행 완료: %s → %s.%s (case=%s)",
                policy.get("name", policy_id),
                target_service,
                target_command,
                case_id,
            )

        # 모든 정책 처리 완료 — ACK
        await redis.xack(stream_name, CONSUMER_GROUP, msg_id)

    async def _find_matching_policies(
        self,
        neo4j_driver,
        case_id: str,
        tenant_id: str,
        event_type: str,
    ) -> list[dict]:
        """Neo4j에서 매칭되는 활성 Policy 노드 조회

        case_id, tenant_id, trigger_event가 일치하고 enabled=true인 정책만 반환한다.
        tenant_id 필터로 크로스 테넌트 정책 실행을 방지한다.
        """
        query = """
        MATCH (p:Policy {case_id: $case_id, tenant_id: $tenant_id, enabled: true})
        WHERE p.trigger_event = $event_type
        RETURN p
        ORDER BY p.name
        """
        try:
            async with neo4j_driver.session() as session:
                result = await session.run(
                    query,
                    case_id=case_id,
                    tenant_id=tenant_id,
                    event_type=event_type,
                )
                records = [dict(record["p"]) async for record in result]
                return records
        except Exception as exc:
            logger.error(
                "Policy 조회 실패: case_id=%s, event_type=%s, error=%s",
                case_id, event_type, exc,
            )
            return []

    @staticmethod
    def _eval_condition(condition: dict, payload: dict) -> bool:
        """트리거 조건 평가 — field/op/value 비교

        condition 형식: {"field": "temperature", "op": ">", "value": 85.0}
        payload에서 field 값을 추출하여 op로 비교한다.
        """
        field_name = condition.get("field", "")
        op = condition.get("op", "==")
        expected = condition.get("value")
        actual = payload.get(field_name)

        # 필드가 payload에 없으면 조건 불일치
        if actual is None:
            return False

        try:
            if op == "==":
                return actual == expected
            if op == "!=":
                return actual != expected
            # 숫자 비교 — 안전한 형변환
            if op == ">":
                return float(actual) > float(expected)
            if op == "<":
                return float(actual) < float(expected)
            if op == ">=":
                return float(actual) >= float(expected)
            if op == "<=":
                return float(actual) <= float(expected)
        except (TypeError, ValueError):
            logger.warning(
                "Policy 조건 비교 실패: field=%s, actual=%s, op=%s, expected=%s",
                field_name, actual, op, expected,
            )
            return False

        return False

    @staticmethod
    async def _check_cooldown(redis, policy_id: str, cooldown_seconds: int) -> bool:
        """쿨다운 확인 — Redis 기반 (워커 재시작/수평 확장 안전)

        쿨다운 키가 존재하면 마지막 실행 시각을 확인하여
        cooldown_seconds가 경과했는지 판단한다.
        쿨다운이 0 이하이면 항상 실행 허용한다.
        """
        if cooldown_seconds <= 0:
            return True

        cooldown_key = f"axiom:policy:cooldown:{policy_id}"
        last_raw = await redis.get(cooldown_key)

        if not last_raw:
            # 쿨다운 키 없음 — 첫 실행 허용
            return True

        try:
            # decode_responses=True 설정이면 이미 str
            last_str = last_raw if isinstance(last_raw, str) else last_raw.decode()
            last = datetime.fromisoformat(last_str)
            elapsed = (datetime.now(timezone.utc) - last).total_seconds()
            return elapsed >= cooldown_seconds
        except (ValueError, AttributeError) as exc:
            logger.warning("쿨다운 시간 파싱 실패 (policy_id=%s): %s", policy_id, exc)
            # 파싱 실패 시 안전하게 실행 허용
            return True

    @staticmethod
    async def _set_cooldown(redis, policy_id: str, cooldown_seconds: int) -> None:
        """쿨다운 설정 — Redis SETEX

        키: axiom:policy:cooldown:{policy_id}
        값: ISO 타임스탬프
        TTL: cooldown_seconds (자동 만료)
        """
        cooldown_key = f"axiom:policy:cooldown:{policy_id}"
        await redis.setex(
            cooldown_key,
            cooldown_seconds,
            datetime.now(timezone.utc).isoformat(),
        )

    @staticmethod
    async def _check_daily_limit(
        redis,
        policy_id: str,
        max_executions_per_day: int,
    ) -> bool:
        """일일 실행 횟수 제한 확인 — Redis INCR 기반

        키: axiom:policy:daily:{policy_id}:{YYYY-MM-DD}
        INCR로 카운터를 증가시키고, 첫 증가 시 EXPIRE 86400초를 설정한다.
        카운터가 max_executions_per_day를 초과하면 False를 반환하여 실행을 차단한다.
        """
        today_str = date.today().isoformat()
        daily_key = f"axiom:policy:daily:{policy_id}:{today_str}"

        try:
            current_count = await redis.incr(daily_key)
            # 첫 번째 증가(1)이면 TTL 설정 — 자정 이후 자동 만료
            if current_count == 1:
                await redis.expire(daily_key, 86400)

            if current_count > max_executions_per_day:
                # 한도 초과 — INCR은 이미 실행되었으나 실제 커맨드 발행은 차단
                return False

            return True
        except Exception as exc:
            logger.warning(
                "일일 실행 한도 확인 실패 (policy_id=%s): %s — 안전하게 실행 허용",
                policy_id, exc,
            )
            # Redis 오류 시 안전하게 실행 허용 (가용성 우선)
            return True

    @staticmethod
    def _resolve_template(
        template: dict,
        payload: dict,
        case_id: str,
        tenant_id: str,
    ) -> dict:
        """커맨드 페이로드 템플릿의 $trigger 변수 해석

        지원 패턴:
        - "$trigger.payload.xxx" → payload["xxx"]
        - 중첩 dict → 재귀적으로 처리
        - 그 외 값 → 그대로 유지
        - case_id, tenant_id는 자동 추가 (없는 경우)
        """
        resolved: dict = {}
        for k, v in template.items():
            if isinstance(v, str) and v.startswith("$trigger.payload."):
                # $trigger.payload.sensor_id → payload["sensor_id"]
                payload_key = v[len("$trigger.payload."):]
                resolved[k] = payload.get(payload_key, v)
            elif isinstance(v, dict):
                # 중첩 dict — 재귀 처리
                resolved[k] = PolicyExecutorWorker._resolve_template(
                    v, payload, case_id, tenant_id,
                )
            else:
                resolved[k] = v

        # case_id, tenant_id 자동 보장
        resolved.setdefault("case_id", case_id)
        resolved.setdefault("tenant_id", tenant_id)
        return resolved

    async def _publish_policy_command(
        self,
        event_type: str,
        aggregate_id: str,
        case_id: str,
        tenant_id: str,
        command: str,
        target_service: str,
        command_payload: dict,
        triggered_by_event: str,
        triggered_by_policy: str,
    ) -> None:
        """POLICY_COMMAND 이벤트를 Core EventOutbox에 발행

        Core의 EventPublisher는 AsyncSession을 첫 인자로 요구하므로,
        자체 DB 세션을 생성하여 호출한다.
        """
        from app.core.database import AsyncSessionLocal
        from app.core.events import EventPublisher

        payload = {
            "case_id": case_id,
            "command": command,
            "target_service": target_service,
            "command_payload": command_payload,
            "triggered_by_event": triggered_by_event,
            "triggered_by_policy": triggered_by_policy,
        }

        try:
            async with AsyncSessionLocal() as session:
                await EventPublisher.publish(
                    session=session,
                    event_type=event_type,
                    aggregate_type="Policy",
                    aggregate_id=aggregate_id,
                    payload=payload,
                    tenant_id=tenant_id,
                )
                await session.commit()

            logger.debug(
                "POLICY_COMMAND 발행 완료: event_type=%s, aggregate_id=%s",
                event_type, aggregate_id,
            )
        except Exception as exc:
            logger.error(
                "POLICY_COMMAND 발행 실패: event_type=%s, error=%s",
                event_type, exc,
                exc_info=True,
            )
            raise


# ── 직접 실행용 엔트리포인트 ──────────────────────────────────

if __name__ == "__main__":
    asyncio.run(PolicyExecutorWorker().start())
