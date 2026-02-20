# Axiom Core - Event Outbox 패턴 상세

## 이 문서가 답하는 질문

- Event Outbox 패턴은 왜 필요한가?
- Redis Streams의 구체적인 설정과 운영은 어떻게 하는가?
- Consumer Group의 장애 복구는 어떻게 처리하는가?

<!-- affects: backend -->
<!-- requires-update: 01_architecture/event-driven.md -->

---

## 1. 패턴 설명

### 1.1 문제

```
위험한 패턴 (Outbox 없이):
  BEGIN TRANSACTION
    INSERT INTO cases (...)           -- 성공
  COMMIT
  await redis.publish("CASE_CREATED") -- 실패하면 이벤트 유실!

안전한 패턴 (Outbox 사용):
  BEGIN TRANSACTION
    INSERT INTO cases (...)           -- 비즈니스 로직
    INSERT INTO event_outbox (...)    -- 이벤트 (같은 트랜잭션!)
  COMMIT                              -- 원자적: 둘 다 성공하거나 둘 다 실패

  [Worker가 비동기로 Redis에 발행]     -- 실패해도 재시도 가능
```

### 1.2 보장 수준

```
[사실] at-least-once 전달을 보장한다. (이벤트가 1번 이상 전달됨)
[사실] exactly-once는 보장하지 않는다. (소비자가 멱등성을 보장해야 함)
[사실] 순서 보장은 aggregate_id 단위로만 보장한다. (같은 집합체 내)
```

---

## 2. Redis Streams 설정

### 2.1 스트림 구성

```python
# Redis Streams 키 구조
STREAMS = {
    "axiom:events":         # 범용 이벤트 (프로세스, 케이스, 문서)
    "axiom:watches":        # Watch Agent 전용 (기한, 알림 트리거)
    "axiom:workers":        # Worker 작업 요청 (OCR, 추출, 생성)
}

# Consumer Group 구성
CONSUMER_GROUPS = {
    "axiom:events": [
        "vision_group",     # Vision 서비스 (분석 이벤트 반응)
        "synapse_group",    # Synapse 서비스 (온톨로지 갱신)
    ],
    "axiom:watches": [
        "watch_cep_group",  # Watch CEP Worker
    ],
    "axiom:workers": [
        "worker_group",     # OCR/Extract/Generate Workers
    ],
}

# 스트림 설정
STREAM_CONFIG = {
    "maxlen": 10000,          # 스트림 최대 길이 (초과 시 오래된 메시지 삭제)
    "approximate": True,      # ~10000 (정확한 제한보다 성능 우선)
}
```

### 2.2 장애 복구

```python
# Pending 메시지 자동 복구 (5분 이상 ACK되지 않은 메시지)

async def recover_pending_messages(stream_key: str, group: str):
    """처리되지 않은 메시지를 다른 Consumer에게 재할당"""
    redis = await get_redis()

    # Pending 메시지 조회
    pending = await redis.xpending_range(
        stream_key, group,
        min="-", max="+", count=100,
    )

    for msg in pending:
        idle_time_ms = msg["time_since_delivered"]
        if idle_time_ms > 300_000:  # 5분 초과
            # 다른 Consumer에게 재할당 (XCLAIM)
            await redis.xclaim(
                stream_key, group,
                consumer="recovery_worker",
                min_idle_time=300_000,
                message_ids=[msg["message_id"]],
            )
            logger.warning(
                f"Reclaimed pending message {msg['message_id']} "
                f"(idle {idle_time_ms}ms)"
            )
```

> **DLQ 참조**: XCLAIM으로도 복구되지 않는 영구 실패 메시지의 Dead Letter Queue 처리는 [resilience-patterns.md](../01_architecture/resilience-patterns.md) §5를 참조한다.

---

## 3. 소비자 멱등성 구현

```python
# 모든 소비자의 멱등성 보장 패턴

async def process_event_idempotent(event_id: str, handler):
    """멱등성 래퍼"""
    redis = await get_redis()
    dedup_key = f"event:processed:{event_id}"

    # SETNX로 원자적 중복 체크
    is_new = await redis.set(dedup_key, "1", nx=True, ex=7 * 86400)
    if not is_new:
        logger.debug(f"Skipping duplicate event: {event_id}")
        return

    try:
        await handler()
    except Exception:
        # 실패 시 중복 체크 키 삭제 (재처리 허용)
        await redis.delete(dedup_key)
        raise
```

---

## 근거

- ADR-004: Redis Streams 이벤트 버스
- 01_architecture/event-driven.md (이벤트 흐름 전체)
- [06_data/database-operations.md](./database-operations.md) (Outbox 정리 pg_cron, Redis Streams 유지보수, 백업 전략)
