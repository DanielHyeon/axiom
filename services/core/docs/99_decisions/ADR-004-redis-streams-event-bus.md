# ADR-004: Redis Streams 이벤트 버스 도입

## 상태

Accepted

## 배경

K-AIR/Process-GPT 시스템은 **메시지 큐가 없다**. 서비스 간 통신은 모두 동기 HTTP 호출이며, 비동기 작업은 Supabase 테이블 폴링으로 처리한다.

**K-AIR 현행 비동기 패턴**:

| 서비스 | 비동기 방식 | 폴링 간격 | 문제 |
|--------|-----------|:---------:|------|
| agent-feedback | Supabase 테이블 폴링 | 7초 | 불필요한 DB 부하 |
| crewai-action | A2A SDK + Supabase 폴링 | 5초 | 이벤트 유실 가능 |
| a2a-orch | HTTP Webhook | - | 별도 Receiver Pod 필요 |
| text2sql/events | SimpleCEP 내부 스케줄러 | 60초 | 지연 시간 과다 |
| completion | 동기 HTTP 호출 | - | 장애 전파 |

**문제**:
1. 폴링 기반 비동기는 DB 부하를 유발하고 실시간성이 떨어진다.
2. 서비스 간 동기 호출은 장애가 전파된다 (A 서비스 장애 → B 서비스 타임아웃).
3. 이벤트 유실 시 재시도 메커니즘이 없다.
4. Watch Agent(실시간 알림)는 5초 이내 응답이 필요한데 60초 폴링으로는 불가능하다.
5. 비즈니스 프로세스 도메인에서 이벤트 순서 보장이 중요하다 (기한 도래 알림 순서).

## 검토한 옵션

### 옵션 1: Apache Kafka

**장점**:
- 업계 표준 이벤트 스트리밍 플랫폼
- 파티션 기반 병렬 처리
- 장기 보존 (컴팩션)
- 정확히 한 번(exactly-once) 의미론 지원

**단점**:
- 운영 복잡도 높음 (ZooKeeper/KRaft + Broker + Schema Registry)
- 최소 3대 브로커 권장 (리소스 비용)
- 소규모 팀에서 운영 부담 과도
- Python 클라이언트(confluent-kafka)의 C 바인딩 의존성

### 옵션 2: RabbitMQ

**장점**:
- 성숙한 메시지 브로커
- AMQP 프로토콜 표준
- 라우팅 패턴 풍부 (Exchange/Queue/Binding)
- 관리 UI 내장

**단점**:
- 별도 인프라 서비스 운영 필요
- Consumer Group 패턴이 Kafka/Redis Streams보다 복잡
- 메시지 순서 보장이 단일 큐에서만 가능
- Axiom이 이미 Redis를 캐시용으로 사용 → 별도 브로커는 인프라 중복

### 옵션 3: Redis Streams (선택)

**장점**:
- Axiom이 이미 Redis를 캐시/세션/Rate Limiting에 사용 → 추가 인프라 불필요
- Consumer Group 지원 (Kafka와 유사한 소비자 그룹)
- XACK/XPENDING으로 메시지 처리 확인 + 재시도
- 메시지 순서 보장 (append-only log)
- 밀리초 단위 지연 (Watch Agent 실시간 요구 충족)
- 운영이 단순 (Redis 하나로 캐시 + 이벤트 버스)

**단점**:
- 메모리 기반이므로 대용량 메시지 보존에 부적합 → MAXLEN으로 관리
- exactly-once 의미론 미지원 → at-least-once + 멱등성으로 대응
- Kafka 대비 기능 세트가 제한적 (스키마 레지스트리, 파티션 리밸런싱 없음)
- 클러스터 모드에서 Stream 크로스 노드 제약

### 옵션 4: PostgreSQL LISTEN/NOTIFY

**장점**:
- 추가 인프라 불필요 (DB만으로)
- 트랜잭션과 이벤트 발행의 원자적 결합

**단점**:
- 페이로드 크기 8KB 제한
- 연결이 끊기면 메시지 유실 (영속성 없음)
- Consumer Group 패턴 미지원
- 대량 이벤트 처리 시 DB 성능 영향

## 선택한 결정

**옵션 3: Redis Streams 이벤트 버스 + Event Outbox 패턴**

## 근거

### 1. Event Outbox + Redis Streams 아키텍처

```
[서비스 코드]
    │
    ├─ 비즈니스 로직 실행
    ├─ DB 트랜잭션 내에서 event_outbox 테이블에 이벤트 삽입
    │   (비즈니스 데이터 변경과 이벤트 삽입이 같은 트랜잭션)
    └─ 커밋

[Sync Worker] (5초 간격 폴링)
    │
    ├─ event_outbox에서 status='PENDING' 이벤트 조회
    ├─ Redis Streams에 XADD
    ├─ event_outbox status → 'SENT' 업데이트
    └─ 실패 시 재시도 (max_retries=5)

[Consumer Workers]
    │
    ├─ XREADGROUP으로 Consumer Group 소비
    ├─ 이벤트 처리
    ├─ XACK로 처리 완료 확인
    └─ 실패 시 XPENDING에서 재처리
```

이 아키텍처가 K-AIR의 폴링 패턴보다 우월한 이유:

| 비교 항목 | K-AIR (테이블 폴링) | Axiom (Outbox + Redis Streams) |
|----------|-------------------|-------------------------------|
| 지연 시간 | 5~60초 (폴링 간격) | 밀리초 (XREADGROUP BLOCK) |
| DB 부하 | 폴링마다 SELECT | 이벤트 INSERT 1회 |
| 이벤트 유실 | 가능 (폴링 사이) | 불가 (Outbox 영속성) |
| 순서 보장 | 보장 안됨 | 보장 (append-only) |
| 소비자 확장 | 중복 처리 위험 | Consumer Group으로 안전 |
| 재시도 | 수동 구현 필요 | XPENDING 내장 |

### 2. 왜 Event Outbox가 필요한가

Redis Streams에 직접 XADD하면 DB 트랜잭션과 메시지 발행이 분리된다:

```
[위험한 패턴]
BEGIN TRANSACTION;
  UPDATE cases SET status = 'APPROVED';  -- DB 변경
COMMIT;
await redis.xadd("events", event);       -- 서버 크래시 시 이벤트 유실!

[안전한 패턴 - Event Outbox]
BEGIN TRANSACTION;
  UPDATE cases SET status = 'APPROVED';  -- DB 변경
  INSERT INTO event_outbox (event_type, payload, status)
    VALUES ('case.approved', {...}, 'PENDING');  -- 같은 트랜잭션
COMMIT;
-- Sync Worker가 비동기로 Redis Streams에 전달 (at-least-once)
```

Event Outbox는 비즈니스 데이터 변경과 이벤트 발행의 원자성을 보장한다.

### 3. Consumer Group 설계

```
Redis Stream: events:core

Consumer Group: sync-workers
  ├─ sync-worker-1  → event_outbox 상태 업데이트
  └─ sync-worker-2  → (스케일 아웃 시)

Consumer Group: watch-cep
  ├─ cep-worker-1   → CEP 룰 평가 + 알림 생성
  └─ cep-worker-2   → (스케일 아웃 시)

Consumer Group: bpm-engine
  ├─ bpm-worker-1   → 프로세스 전이 + 워크아이템 생성
  └─ bpm-worker-2   → (스케일 아웃 시)
```

각 Consumer Group은 동일 Stream의 메시지를 독립적으로 소비한다. 같은 그룹 내 Consumer 간에는 메시지가 분배된다 (병렬 처리).

### 4. 이벤트 타입 카탈로그

```python
# 이벤트 타입 분류

# 프로세스 이벤트 (BPM 엔진)
"process.initiated"       # 프로세스 시작
"process.completed"       # 프로세스 완료
"process.terminated"      # 프로세스 종료
"workitem.created"        # 워크아이템 생성
"workitem.submitted"      # 워크아이템 제출
"workitem.approved"       # HITL 승인

# 케이스 이벤트
"case.created"           # 사건 등록
"case.status_changed"    # 사건 상태 변경
"case.assigned"          # 사건 담당자 할당

# 문서 이벤트
"document.uploaded"      # 문서 업로드
"document.ocr_completed" # OCR 완료
"document.extracted"     # 데이터 추출 완료

# 에이전트 이벤트
"agent.feedback_received" # 피드백 수신
"agent.knowledge_updated" # 지식 업데이트

# 알림 이벤트 (Watch)
"watch.alert_triggered"  # 알림 발생
"watch.alert_escalated"  # 에스컬레이션
```

### 5. 멱등성 보장

Redis Streams는 at-least-once 전달을 보장하므로, 동일 이벤트가 중복 전달될 수 있다. 멱등성 키로 중복 처리를 방지한다:

```python
# 멱등성 래퍼

async def process_with_idempotency(event: dict, handler):
    """이벤트 처리 멱등성 보장"""
    event_id = event["event_id"]
    idempotency_key = f"processed:{event_id}"

    # Redis SET NX로 원자적 중복 검사
    already_processed = not await redis.set(
        idempotency_key, "1", nx=True, ex=86400  # 24시간 TTL
    )

    if already_processed:
        logger.info(f"Event {event_id} already processed, skipping")
        return

    try:
        await handler(event)
    except Exception:
        # 실패 시 멱등성 키 삭제 (재시도 허용)
        await redis.delete(idempotency_key)
        raise
```

### 6. Redis가 이미 인프라에 포함

Axiom은 Redis를 다음 용도로 이미 사용한다:

| 용도 | Redis 기능 | 비고 |
|------|-----------|------|
| 캐시 | GET/SET/DEL | API 응답 캐시, LLM 응답 캐시 |
| 세션 | SET + TTL | Refresh Token 블랙리스트 |
| Rate Limiting | INCR + EXPIRE | 슬라이딩 윈도우 속도 제한 |
| **이벤트 버스** | **XADD/XREADGROUP** | **Outbox → Consumer** |

별도 메시지 브로커(Kafka, RabbitMQ) 없이 Redis 하나로 4가지 역할을 수행한다.

### 7. Watch Agent 실시간 요구 충족

비즈니스 프로세스 도메인에서 기한 도래 알림은 핵심 요구사항이다. XREADGROUP의 BLOCK 옵션으로 밀리초 단위 응답이 가능하다:

```python
# Watch CEP Worker

async def watch_cep_loop(self):
    while self.running:
        # 최대 5초 대기 후 새 이벤트 반환 (실시간)
        messages = await self.redis.xreadgroup(
            groupname="watch-cep",
            consumername=self.worker_id,
            streams={"events:core": ">"},
            count=10,
            block=5000,  # 5초 블로킹 대기
        )

        for stream, events in messages:
            for event_id, event_data in events:
                await self.evaluate_cep_rules(event_data)
                await self.redis.xack("events:core", "watch-cep", event_id)
```

K-AIR의 60초 폴링 대비 10,000배 이상 빠른 응답이 가능하다.

## 결과

### 긍정적 영향
- 추가 인프라 없이 이벤트 기반 아키텍처 구현 (Redis 재활용)
- Event Outbox로 이벤트 유실 방지 (at-least-once 보장)
- Consumer Group으로 Worker 수평 확장 가능
- Watch Agent의 실시간 알림 요구 충족 (밀리초 지연)
- 서비스 간 느슨한 결합 (동기 HTTP 의존 제거)

### 부정적 영향
- Redis 메모리에 이벤트 보관 → MAXLEN으로 보존 기간 제한 필요
- at-least-once 의미론 → 멱등성 구현 필수
- Redis 장애 시 이벤트 처리 중단 → Event Outbox에 보존되므로 Redis 복구 후 재전송
- Kafka 대비 기능 제한 (스키마 레지스트리, 트랜잭션 메시지 미지원)

### Stream 운영 설정

```python
# Redis Streams 설정

STREAM_CONFIG = {
    "events:core": {
        "maxlen": 100_000,          # 최대 10만 메시지 보존
        "consumer_groups": [
            "sync-workers",         # Outbox 상태 업데이트
            "watch-cep",            # CEP 룰 평가
            "bpm-engine",           # BPM 이벤트 처리
        ],
    },
    "events:documents": {
        "maxlen": 50_000,
        "consumer_groups": [
            "ocr-workers",          # OCR 처리
            "extract-workers",      # 데이터 추출
            "generate-workers",     # 문서 생성
        ],
    },
}
```

### Pending 메시지 복구

```python
# 장애 복구: 미확인 메시지 재처리

async def recover_pending_messages(self):
    """5분 이상 미확인 메시지를 자동 재할당"""
    pending = await self.redis.xpending_range(
        "events:core",
        "watch-cep",
        min="-",
        max="+",
        count=100,
    )

    for msg in pending:
        if msg["time_since_delivered"] > 300_000:  # 5분 초과
            await self.redis.xclaim(
                "events:core",
                "watch-cep",
                self.worker_id,
                min_idle_time=300_000,
                message_ids=[msg["message_id"]],
            )
```

## 재평가 조건

- 이벤트 처리량이 100,000 msg/sec를 초과하는 경우 → Apache Kafka 도입 검토
- Redis 메모리가 10GB를 초과하여 이벤트 보존에 부담이 되는 경우 → Kafka + Log Compaction 검토
- exactly-once 의미론이 규정상 요구되는 경우 → Kafka Transactions 검토
- 크로스 리전 이벤트 복제가 필요한 경우 → Kafka MirrorMaker 또는 MSK 검토
- Redis Cluster 모드 전환 시 Stream 크로스 슬롯 문제가 발생하는 경우 → 스트림별 해시태그 전략 검토
