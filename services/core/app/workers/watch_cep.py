"""
Watch CEP Worker (worker-system.md §3.2).
axiom:watches 스트림 소비, CEP 룰 평가 및 알림 생성·발송.
Consumer Group: watch_cep_group. CEP·알림 로직 구현.
"""
from __future__ import annotations

import asyncio
import json
import logging

from app.core.database import AsyncSessionLocal
from app.core.redis_client import get_redis
from app.services.watch_service import WatchService
from app.workers.base import BaseWorker

logger = logging.getLogger("axiom.workers")

STREAM_KEY = "axiom:watches"
CONSUMER_GROUP = "watch_cep_group"
CONSUMER_NAME = "watch_cep_worker_1"
BLOCK_MS = 5000
IDEMPOTENCY_TTL_SECONDS = 86400  # 24h


def _evaluate_rule(rule: dict, payload: dict) -> bool:
    """구독 룰을 payload에 대해 평가. deadline은 이벤트 수신 시 이미 충족으로 간주."""
    rule_type = (rule or {}).get("type")
    if not rule_type:
        return True
    if rule_type == "deadline":
        return True
    if rule_type == "threshold":
        field = (rule or {}).get("field")
        operator = (rule or {}).get("operator")
        threshold = (rule or {}).get("threshold")
        if field is None or operator is None or threshold is None:
            return True
        val = payload.get(field)
        if val is None:
            return False
        try:
            v = float(val) if isinstance(val, (int, float)) else float(val)
            t = float(threshold)
        except (TypeError, ValueError):
            return False
        if operator == "<":
            return v < t
        if operator == "<=":
            return v <= t
        if operator == ">":
            return v > t
        if operator == ">=":
            return v >= t
        if operator == "==":
            return v == t
        return False
    if rule_type == "pattern":
        # 패턴(윈도우 내 min_count)은 상태 저장 필요. 추후 구현 시 윈도우 카운트 조회.
        return True
    return True


def _severity_from_subscription(sub, payload: dict) -> str:
    if getattr(sub, "severity_override", None):
        return sub.severity_override
    return (payload or {}).get("severity", "MEDIUM")


def _message_from_payload(event_type: str, payload: dict) -> str:
    return (payload or {}).get("message") or f"Watch 이벤트: {event_type}"


def _action_url_from_payload(payload: dict) -> str | None:
    return (payload or {}).get("action_url")


class WatchCepWorker(BaseWorker):
    """axiom:watches 소비, CEP 평가·알림 DB 저장·채널 발송(인앱=DB, 이메일/SMS/Slack은 재시도 후 로깅)."""

    def __init__(self):
        super().__init__("watch_cep")

    async def run(self):
        redis = get_redis()
        try:
            await redis.xgroup_create(STREAM_KEY, CONSUMER_GROUP, id="0", mkstream=True)
        except Exception:
            pass

        while self._running:
            try:
                messages = await redis.xreadgroup(
                    groupname=CONSUMER_GROUP,
                    consumername=CONSUMER_NAME,
                    streams={STREAM_KEY: ">"},
                    count=10,
                    block=BLOCK_MS,
                )
                for _stream, entries in messages:
                    for entry_id, data in entries:
                        await self.process_with_retry(self._handle_message, entry_id, data)
                        await redis.xack(STREAM_KEY, CONSUMER_GROUP, entry_id)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("WatchCepWorker error: %s", e)
                await asyncio.sleep(1)

    async def _handle_message(self, entry_id: str, data: dict) -> None:
        """메시지 1건: CEP 룰 평가 → 알림 생성(멱등) → 채널 발송."""
        event_id = data.get("event_id") or entry_id
        event_type = data.get("event_type", "")
        aggregate_id = data.get("aggregate_id", "")
        tenant_id = (data.get("tenant_id") or "").strip() or None
        payload_raw = data.get("payload", "{}")
        try:
            payload = json.loads(payload_raw) if isinstance(payload_raw, str) else (payload_raw or {})
        except json.JSONDecodeError:
            payload = {}

        if not tenant_id:
            logger.debug("watch_cep skip event missing tenant_id: entry_id=%s", entry_id)
            return

        async with AsyncSessionLocal() as db:
            subs = await WatchService.list_subscriptions_for_event(
                db=db,
                tenant_id=tenant_id,
                event_type=event_type,
                case_id=aggregate_id or None,
            )
            if not subs:
                logger.debug(
                    "watch_cep no subscriptions event_type=%s tenant_id=%s",
                    event_type,
                    tenant_id,
                )
                return

            redis = get_redis()
            for sub in subs:
                if not _evaluate_rule(sub.rule or {}, payload):
                    continue
                idempotency_key = f"watch:alert:idempotency:{event_id}:{sub.id}"
                if await redis.set(idempotency_key, "1", nx=True, ex=IDEMPOTENCY_TTL_SECONDS) is not True:
                    continue

                severity = _severity_from_subscription(sub, payload)
                message = _message_from_payload(event_type, payload)
                action_url = _action_url_from_payload(payload)
                case_name = (payload or {}).get("case_name")

                await WatchService.create_alert(
                    db=db,
                    tenant_id=tenant_id,
                    subscription_id=sub.id,
                    event_type=event_type,
                    severity=severity,
                    message=message,
                    case_id=aggregate_id or None,
                    case_name=case_name,
                    action_url=action_url,
                    meta={"event_id": event_id, "aggregate_id": aggregate_id},
                )
                await self._send_alert_channels(sub, severity, message, payload)

            await db.commit()

        logger.info(
            "watch_cep consumed event_type=%s aggregate_id=%s entry_id=%s subscriptions=%d",
            event_type,
            aggregate_id,
            entry_id,
            len(subs),
        )

    async def _send_alert_channels(self, subscription, severity: str, message: str, payload: dict) -> None:
        """인앱은 DB 저장으로 이미 반영. 이메일/SMS/Slack은 재시도 후 실패 시 FAILED 로깅(worker-system §3.2)."""
        channels = getattr(subscription, "channels", None) or []
        if "in_app" in channels:
            pass  # already created WatchAlert
        for ch in channels:
            if ch == "in_app":
                continue
            if ch in ("email", "sms", "slack"):
                # 발송 어댑터 미구현 시 로깅만. 실패 시 3회 재시도는 process_with_retry가 담당.
                logger.info(
                    "watch_cep channel %s (adapter not implemented): severity=%s message=%s",
                    ch,
                    severity,
                    message[:80],
                )


if __name__ == "__main__":
    asyncio.run(WatchCepWorker().start())
