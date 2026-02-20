# Axiom Core - 이벤트 드리븐 아키텍처

## 이 문서가 답하는 질문

- Event Outbox 패턴은 왜 필요하고, 어떻게 작동하는가?
- Redis Streams는 어떤 역할을 하며, 어떻게 구성되는가?
- Watch Agent(CEP 엔진)는 이벤트를 어떻게 감지하고 알림을 발송하는가?
- at-least-once 전달 보장은 어떻게 구현되는가?
- K-AIR에 없던 이벤트 버스를 왜 Axiom에서 도입하는가?

<!-- affects: api, backend, data -->
<!-- requires-update: 06_data/event-outbox.md, 02_api/watch-api.md -->

---

## 1. 이벤트 드리븐 아키텍처 개요

### 1.1 K-AIR의 한계와 Axiom의 해결

```
[사실] K-AIR는 모듈 간 통신이 모두 직접 HTTP 호출이다.
[문제] 서비스 A가 서비스 B를 호출할 때, B가 다운되면 A도 실패한다.
       장애가 전파되고, 재시도 로직이 모듈마다 제각각이다.

[결정] Axiom은 Redis Streams 기반 Event Outbox 패턴을 도입한다.
[근거] 1. DB 트랜잭션과 이벤트 발행의 원자성 보장
       2. at-least-once 전달로 이벤트 유실 방지
       3. 모듈 간 느슨한 결합 (decoupling)
       4. Watch Agent의 CEP 엔진 구동 기반
```

### 1.2 이벤트 흐름 전체도

```
[서비스 로직]
     |
     | (같은 DB 트랜잭션)
     v
+----+------------------------------------------+
| PostgreSQL                                     |
|  +------------------+  +-------------------+  |
|  | 비즈니스 테이블   |  | event_outbox      |  |
|  | (INSERT/UPDATE)  |  | (INSERT, PENDING) |  |
|  +------------------+  +---+---------------+  |
+--------------------------------------------+---+
                                              |
                                              | (Worker: 5초 간격 폴링)
                                              v
                                    +---------+----------+
                                    | sync_worker        |
                                    | (event_outbox ->   |
                                    |  Redis Streams)    |
                                    +---------+----------+
                                              |
                                              | XADD
                                              v
+---------------------------------------------+--------------------+
| Redis Streams                                                      |
|  +---------------+  +----------------+  +----------+  +----------+ |
|  | axiom:events  |  | axiom:watches  |  | axiom:   |  | axiom:   | |
|  | (범용 이벤트) |  | (Watch 전용)   |  | workers  |  | process_ | |
|  |               |  |                |  |          |  | mining   | |
|  +-------+-------+  +--------+-------+  +----+-----+  +----+-----+ |
+-----------+-----------+--------+----------+----+---------+----+----+
            |                    |               |              |
            v                    v               v              v
    +-------+------+   +--------+-------+  +----+-------+ +----+----------+
    | Vision       |   | watch_cep      |  | 기타       | | Synapse       |
    | Consumer     |   | Worker         |  | Workers    | | (프로세스     |
    | (분석 이벤트)|   | (CEP 룰 평가) |  | (OCR 등)   | |  마이닝)      |
    +--------------+   +--------+-------+  +------------+ +----+----------+
                                                               |
                                                               v
                                                         +-----+--------+
                                                         | Canvas       |
                                                         | (마이닝 결과 |
                                                         |  SSE 전달)   |
                                                         +--------------+
                                |
                                v
                       +--------+-------+
                       | Alert          |
                       | Dispatcher     |
                       | (알림 발송)    |
                       +--------+-------+
                                |
                    +-----------+-----------+
                    |           |           |
                    v           v           v
              +--------+  +--------+  +--------+
              | In-App |  | Email  |  | Slack  |
              | (SSE)  |  | (SES)  |  | (Hook) |
              +--------+  +--------+  +--------+
```

---

## 2. Event Outbox 패턴

### 2.1 event_outbox 테이블

```sql
-- DB 트랜잭션과 이벤트 발행의 원자성을 보장하는 Outbox 테이블
CREATE TABLE event_outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(100) NOT NULL,      -- 이벤트 유형
    aggregate_type VARCHAR(100) NOT NULL,  -- 집합체 유형 (case, workitem, document)
    aggregate_id UUID NOT NULL,            -- 집합체 ID
    payload JSONB NOT NULL,                -- 이벤트 데이터
    tenant_id UUID NOT NULL,               -- 테넌트 ID
    status VARCHAR(20) DEFAULT 'PENDING',  -- PENDING, PUBLISHED, FAILED
    created_at TIMESTAMPTZ DEFAULT now(),
    published_at TIMESTAMPTZ,
    retry_count INT DEFAULT 0,
    max_retries INT DEFAULT 3,
    error_message TEXT
);

-- 폴링 성능을 위한 인덱스
CREATE INDEX idx_outbox_pending ON event_outbox (status, created_at)
    WHERE status = 'PENDING';
CREATE INDEX idx_outbox_tenant ON event_outbox (tenant_id, created_at);
```

### 2.2 이벤트 발행 (서비스 레이어)

```python
# app/services/process_service.py

from app.core.database import get_session
from app.core.event_publisher import EventPublisher

class ProcessService:

    async def initiate_process(self, proc_def_id: str, initiator_id: str) -> str:
        """프로세스 시작 - 비즈니스 로직 + 이벤트 발행이 같은 트랜잭션"""
        async with get_session() as session:
            # 1. 프로세스 인스턴스 생성 (비즈니스 로직)
            proc_inst = ProcessInstance(
                proc_def_id=proc_def_id,
                initiator_id=initiator_id,
                status="RUNNING",
            )
            session.add(proc_inst)

            # 2. 첫 Workitem 생성 (비즈니스 로직)
            workitem = Workitem(
                proc_inst_id=proc_inst.id,
                activity_id=first_activity.id,
                status="TODO",
            )
            session.add(workitem)

            # 3. 이벤트 발행 (같은 트랜잭션!)
            await EventPublisher.publish(
                session=session,
                event_type="PROCESS_STARTED",
                aggregate_type="process_instance",
                aggregate_id=proc_inst.id,
                payload={
                    "proc_inst_id": str(proc_inst.id),
                    "proc_def_id": str(proc_def_id),
                    "initiator_id": str(initiator_id),
                    "first_workitem_id": str(workitem.id),
                },
            )

            # 4. 커밋 (비즈니스 + 이벤트 원자적 저장)
            await session.commit()

        return str(proc_inst.id)

# app/core/event_publisher.py

class EventPublisher:
    """Event Outbox에 이벤트를 INSERT하는 퍼블리셔"""

    @staticmethod
    async def publish(
        session,
        event_type: str,
        aggregate_type: str,
        aggregate_id,
        payload: dict,
    ):
        """같은 DB 세션(트랜잭션)에 이벤트를 INSERT"""
        from app.core.middleware import get_current_tenant_id

        outbox_event = EventOutbox(
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload=payload,
            tenant_id=get_current_tenant_id(),
            status="PENDING",
        )
        session.add(outbox_event)
        # 커밋은 호출자가 관리 (같은 트랜잭션)
```

### 2.3 Sync Worker (Outbox -> Redis Streams)

```python
# app/workers/sync.py

import asyncio
from app.core.database import get_session
from app.core.redis_client import get_redis

class SyncWorker:
    """event_outbox 테이블을 폴링하여 Redis Streams로 전달"""

    POLL_INTERVAL = 5  # seconds
    BATCH_SIZE = 100

    async def run(self):
        """메인 루프"""
        while True:
            try:
                published = await self._poll_and_publish()
                if published == 0:
                    await asyncio.sleep(self.POLL_INTERVAL)
            except Exception as e:
                logger.error(f"SyncWorker error: {e}")
                await asyncio.sleep(self.POLL_INTERVAL)

    async def _poll_and_publish(self) -> int:
        """PENDING 이벤트를 가져와서 Redis에 발행"""
        async with get_session() as session:
            # 1. PENDING 이벤트 조회 (FOR UPDATE SKIP LOCKED)
            events = await session.execute(
                select(EventOutbox)
                .where(EventOutbox.status == "PENDING")
                .order_by(EventOutbox.created_at)
                .limit(self.BATCH_SIZE)
                .with_for_update(skip_locked=True)
            )
            events = events.scalars().all()

            if not events:
                return 0

            redis = await get_redis()

            for event in events:
                try:
                    # 2. Redis Streams에 발행
                    stream_key = self._determine_stream(event.event_type)
                    await redis.xadd(stream_key, {
                        "id": str(event.id),
                        "event_type": event.event_type,
                        "aggregate_type": event.aggregate_type,
                        "aggregate_id": str(event.aggregate_id),
                        "payload": json.dumps(event.payload),
                        "tenant_id": str(event.tenant_id),
                        "created_at": event.created_at.isoformat(),
                    })

                    # 3. 상태 업데이트
                    event.status = "PUBLISHED"
                    event.published_at = datetime.utcnow()

                except Exception as e:
                    event.retry_count += 1
                    if event.retry_count >= event.max_retries:
                        event.status = "FAILED"
                        event.error_message = str(e)
                    logger.error(f"Failed to publish event {event.id}: {e}")

            await session.commit()
            return len(events)

    def _determine_stream(self, event_type: str) -> str:
        """이벤트 유형에 따라 Redis Stream 키 결정"""
        WATCH_EVENTS = {
            "DEADLINE_APPROACHING", "PAYMENT_DUE", "DATA_REGISTERED",
            "CASH_LOW", "REVIEW_SCHEDULED", "APPROVAL_DEADLINE_MISSED",
        }

        PROCESS_MINING_EVENTS = {
            "PROCESS_LOG_INGESTED", "PROCESS_DISCOVERED",
            "CONFORMANCE_CHECKED", "BOTTLENECK_DETECTED",
        }

        if event_type in WATCH_EVENTS:
            return "axiom:watches"
        elif event_type in PROCESS_MINING_EVENTS:
            return "axiom:process_mining"
        elif event_type.startswith("WORKER_"):
            return "axiom:workers"
        else:
            return "axiom:events"
```

---

## 3. 이벤트 유형 체계

### 3.1 이벤트 카탈로그

| 카테고리 | 이벤트 유형 | 설명 | Stream |
|---------|-----------|------|--------|
| **프로세스** | PROCESS_STARTED | 프로세스 인스턴스 시작 | axiom:events |
| | PROCESS_COMPLETED | 프로세스 완료 | axiom:events |
| | PROCESS_TERMINATED | 프로세스 중단 | axiom:events |
| | WORKITEM_CREATED | 워크아이템 생성 | axiom:events |
| | WORKITEM_COMPLETED | 워크아이템 완료 | axiom:events |
| **문서** | DOCUMENT_UPLOADED | 문서 업로드 | axiom:events |
| | DOCUMENT_EXTRACTED | 문서 추출 완료 | axiom:events |
| | DOCUMENT_GENERATED | 문서 생성 완료 | axiom:events |
| **케이스** | CASE_CREATED | 사건 생성 | axiom:events |
| | CASE_STATUS_CHANGED | 사건 상태 변경 | axiom:events |
| **Watch** | DEADLINE_APPROACHING | 기한 도래 (7일/3일/1일 전) | axiom:watches |
| | PAYMENT_DUE | 지급 기일 도래 | axiom:watches |
| | DATA_REGISTERED | 신규 데이터 등록 | axiom:watches |
| | CASH_LOW | 가용 현금 부족 | axiom:watches |
| | REVIEW_SCHEDULED | 이해관계자 리뷰 예정 | axiom:watches |
| | ISSUE_RATIO_HIGH | 이슈 데이터 비율 과다 | axiom:watches |
| | APPROVAL_DEADLINE_MISSED | 승인 기한 도과 | axiom:watches |
| | ANOMALY_INDICATOR | 이상 징후 감지 | axiom:watches |
| **Worker** | WORKER_OCR_STARTED | OCR 작업 시작 | axiom:workers |
| | WORKER_OCR_COMPLETED | OCR 작업 완료 | axiom:workers |
| | WORKER_EXTRACT_COMPLETED | 추출 작업 완료 | axiom:workers |
| **프로세스 마이닝** | PROCESS_LOG_INGESTED | 이벤트 로그 수집 완료 (XES/CSV 파싱 및 검증 성공) | axiom:process_mining |
| | PROCESS_DISCOVERED | 프로세스 모델 자동 발견 완료 (pm4py Alpha/Heuristic Miner) | axiom:process_mining |
| | CONFORMANCE_CHECKED | 적합성 검사 완료 (Token-based Replay / Alignment) | axiom:process_mining |
| | BOTTLENECK_DETECTED | 병목 구간 감지 (성능 분석 결과) | axiom:process_mining |

### 3.2 이벤트 페이로드 규약

```json
{
  "id": "uuid",
  "event_type": "WORKITEM_COMPLETED",
  "aggregate_type": "workitem",
  "aggregate_id": "uuid",
  "tenant_id": "uuid",
  "created_at": "2026-02-19T10:00:00Z",
  "payload": {
    "workitem_id": "uuid",
    "proc_inst_id": "uuid",
    "activity_name": "데이터 수치 검증",
    "result": { ... },
    "completed_by": "agent:gpt-4o",
    "confidence": 0.92
  }
}
```

### 3.3 프로세스 마이닝 이벤트 페이로드 예시

```json
// PROCESS_LOG_INGESTED
{
  "id": "uuid",
  "event_type": "PROCESS_LOG_INGESTED",
  "aggregate_type": "event_log",
  "aggregate_id": "uuid",
  "tenant_id": "uuid",
  "created_at": "2026-02-20T10:00:00Z",
  "payload": {
    "event_log_id": "uuid",
    "file_name": "purchase_order_log.xes",
    "format": "XES",
    "case_count": 1250,
    "event_count": 45000,
    "activity_count": 18,
    "date_range": {
      "start": "2025-01-01T00:00:00Z",
      "end": "2025-12-31T23:59:59Z"
    },
    "ingested_by": "EventLogWorker"
  }
}

// PROCESS_DISCOVERED
{
  "id": "uuid",
  "event_type": "PROCESS_DISCOVERED",
  "aggregate_type": "event_log",
  "aggregate_id": "uuid",
  "tenant_id": "uuid",
  "created_at": "2026-02-20T10:05:00Z",
  "payload": {
    "event_log_id": "uuid",
    "algorithm": "heuristic_miner",
    "bpmn_xml": "...",
    "fitness": 0.92,
    "precision": 0.87,
    "generalization": 0.85,
    "activities_discovered": 18,
    "variants_count": 42
  }
}

// CONFORMANCE_CHECKED
{
  "id": "uuid",
  "event_type": "CONFORMANCE_CHECKED",
  "aggregate_type": "event_log",
  "aggregate_id": "uuid",
  "tenant_id": "uuid",
  "created_at": "2026-02-20T10:10:00Z",
  "payload": {
    "event_log_id": "uuid",
    "reference_model_id": "uuid",
    "method": "token_replay",
    "fitness": 0.89,
    "deviations": [
      {
        "case_id": "case-1234",
        "activity": "승인 검토",
        "deviation_type": "skipped",
        "frequency": 45
      }
    ],
    "conformant_cases_ratio": 0.78
  }
}

// BOTTLENECK_DETECTED
{
  "id": "uuid",
  "event_type": "BOTTLENECK_DETECTED",
  "aggregate_type": "event_log",
  "aggregate_id": "uuid",
  "tenant_id": "uuid",
  "created_at": "2026-02-20T10:15:00Z",
  "payload": {
    "event_log_id": "uuid",
    "bottlenecks": [
      {
        "activity": "데이터 수치 검증",
        "avg_waiting_time_hours": 48.5,
        "avg_processing_time_hours": 2.3,
        "case_frequency": 890,
        "severity": "HIGH"
      }
    ],
    "total_cycle_time_hours": 168.0,
    "bottleneck_contribution_ratio": 0.29
  }
}
```

---

## 4. Watch Agent (CEP 엔진)

### 4.1 CEP(Complex Event Processing) 개요

```
[사실] K-AIR의 robo-data-text2sql-main에 SimpleCEP 엔진이 있다.
[결정] Axiom은 이를 Core의 Watch Worker로 이식한다.
[근거] CEP는 이벤트 스트림 처리이므로 Event Bus와 같은 인프라(Redis Streams) 위에 구축한다.
```

### 4.2 Watch CEP Worker

```python
# app/workers/watch_cep.py
# K-AIR text2sql/simple_cep.py에서 이식

import asyncio
from app.core.redis_client import get_redis

class WatchCEPWorker:
    """CEP 룰 평가 Worker - axiom:watches 스트림 소비"""

    CONSUMER_GROUP = "watch_cep_group"
    CONSUMER_NAME = "watch_cep_worker_1"

    async def run(self):
        redis = await get_redis()

        # Consumer Group 생성 (이미 존재하면 무시)
        try:
            await redis.xgroup_create(
                "axiom:watches", self.CONSUMER_GROUP, id="0", mkstream=True
            )
        except Exception:
            pass  # 이미 존재

        while True:
            try:
                # XREADGROUP으로 새 이벤트 소비
                messages = await redis.xreadgroup(
                    groupname=self.CONSUMER_GROUP,
                    consumername=self.CONSUMER_NAME,
                    streams={"axiom:watches": ">"},
                    count=10,
                    block=5000,  # 5초 대기
                )

                for stream, entries in messages:
                    for entry_id, data in entries:
                        await self._process_event(data)
                        # ACK (처리 완료 확인)
                        await redis.xack(
                            "axiom:watches", self.CONSUMER_GROUP, entry_id
                        )

            except Exception as e:
                logger.error(f"WatchCEP error: {e}")
                await asyncio.sleep(1)

    async def _process_event(self, event_data: dict):
        """이벤트에 대해 CEP 룰 평가"""
        event_type = event_data["event_type"]
        tenant_id = event_data["tenant_id"]
        payload = json.loads(event_data["payload"])

        # 1. 해당 테넌트의 활성 구독 조회
        subscriptions = await self._get_active_subscriptions(
            tenant_id, event_type
        )

        for sub in subscriptions:
            # 2. CEP 룰 평가
            if await self._evaluate_rule(sub, payload):
                # 3. 알림 생성
                alert = await self._create_alert(sub, event_data, payload)

                # 4. 알림 발송
                await self._dispatch_alert(alert, sub)

    async def _evaluate_rule(self, subscription: dict, payload: dict) -> bool:
        """CEP 룰 평가"""
        rule = subscription.get("rule", {})
        rule_type = rule.get("type")

        if rule_type == "deadline":
            # 기한 N일 전 알림
            days_before = rule.get("days_before", 7)
            deadline = payload.get("deadline")
            if deadline:
                remaining = (parse_date(deadline) - datetime.now()).days
                return remaining <= days_before

        elif rule_type == "threshold":
            # 임계값 초과/미만 알림
            field = rule.get("field")
            operator = rule.get("operator", ">")
            threshold = rule.get("threshold")
            value = payload.get(field)
            if value is not None and threshold is not None:
                if operator == ">": return value > threshold
                if operator == "<": return value < threshold
                if operator == ">=": return value >= threshold

        elif rule_type == "pattern":
            # 패턴 매칭 (N시간 내 M건)
            window = rule.get("window_hours", 1)
            min_count = rule.get("min_count", 3)
            actual_count = await self._count_events_in_window(
                subscription["tenant_id"],
                subscription["event_type"],
                window_hours=window,
            )
            return actual_count >= min_count

        return False
```

### 4.3 알림 발송 디스패처

```python
# app/workers/alert_dispatcher.py

class AlertDispatcher:
    """멀티채널 알림 발송"""

    SEVERITY_LEVELS = {
        "LOW": "정보",         # 파란색
        "MEDIUM": "경고",      # 노란색
        "HIGH": "긴급",        # 주황색
        "CRITICAL": "치명적",  # 빨간색
    }

    async def dispatch(self, alert: dict, subscription: dict):
        """구독 설정에 따라 알림 발송"""
        channels = subscription.get("channels", ["in_app"])

        for channel in channels:
            try:
                if channel == "in_app":
                    await self._send_in_app(alert)
                elif channel == "email":
                    await self._send_email(alert)
                elif channel == "sms":
                    await self._send_sms(alert)
                elif channel == "slack":
                    await self._send_slack(alert)

                # 발송 이력 기록
                await self._record_delivery(alert["id"], channel, "SENT")

            except Exception as e:
                await self._record_delivery(alert["id"], channel, "FAILED", str(e))

    async def _send_in_app(self, alert: dict):
        """인앱 알림 (SSE 스트림으로 Canvas에 전달)"""
        redis = await get_redis()
        await redis.xadd(f"axiom:notifications:{alert['tenant_id']}", {
            "alert_id": alert["id"],
            "type": alert["event_type"],
            "severity": alert["severity"],
            "message": alert["message"],
            "case_id": alert.get("case_id", ""),
        })

    async def _send_email(self, alert: dict):
        """이메일 알림 (AWS SES)"""
        # AWS SES를 사용한 이메일 발송
        pass

    async def _send_slack(self, alert: dict):
        """Slack 웹훅 알림"""
        # Slack Incoming Webhook으로 발송
        pass
```

### 4.4 역할별 기본 구독

사용자 생성 시 역할에 따라 기본 Watch 구독이 자동 시드된다. admin은 시스템/기한 알림, attorney는 리뷰/워크아이템, engineer는 데이터/시스템 오류 등 역할에 맞는 이벤트 유형이 설정된다. viewer는 읽기 전용이므로 기본 구독이 없다.

> 역할별 기본 구독의 전체 매핑은 `apps/canvas/docs/04_frontend/watch-alerts.md` §8을 참조한다.

### 4.5 중복 제거 & 에스컬레이션 정책

```
[결정] 동일 이벤트는 24시간 내 재알림하지 않는다.
[결정] CRITICAL 등급은 1시간 미확인 시 상위자에게 에스컬레이션한다.
[결정] 모든 알림에 고유 idempotency_key를 부여하여 중복 발송을 방지한다.

구현:
  idempotency_key = hash(tenant_id + event_type + aggregate_id + date)
  Redis SET에 TTL 24h로 저장
  발송 전 EXISTS 체크
```

에스컬레이션 흐름:
```
CRITICAL 알림 1시간 미확인 → 해당 케이스의 manager에게 이메일 + 인앱 에스컬레이션
manager 2시간 미확인 → admin에게 이메일 + Slack 긴급 에스컬레이션
```

> Watch CEP Worker의 주기적 스캔(5분 간격)으로 미확인 CRITICAL 알림을 탐지한다. 에스컬레이션 알림 자체도 idempotency_key로 중복 방지된다. 상세 정책은 `apps/canvas/docs/04_frontend/watch-alerts.md` §9를 참조한다.

### 4.6 Early Warning 폐루프 표준 (DB 연계)

```
[결정] Watch는 "탐지 -> RCA -> 팀 통보 -> 조치 완료"의 폐루프를 기본 운영 단위로 사용한다.
[근거] 경고 자체보다 조치 완료까지의 리드타임이 운영 품질을 결정한다.
```

알림 등급 표준:
- `CRITICAL`: 즉시 대응, 1시간 내 1차 조치
- `HIGH`: 당일 조치
- `MEDIUM`: 영업일 기준 모니터링 강화
- `LOW`: 추세 관찰

폐루프 SLA:
- 감지 시간(`detected_at`)부터 최초 확인(`acknowledged_at`)까지 `p95 <= 15분`
- 감지 시간부터 조치 완료(`resolved_at`)까지 `p95 <= 24시간`
- 오탐률(`false_positive`) 월간 `<= 10%`

DB 추적 원칙:
- `watch_alerts`는 상태(`unread/acknowledged/dismissed`)와 시각 필드를 필수 기록한다.
- RCA/대응 조치 이력은 감사 가능한 별도 히스토리 테이블로 누적한다.
- 집계 지표는 운영 대시보드(`performance-monitoring.md`)로 노출한다.

---

## 5. Consumer Group 설계

### 5.1 Redis Streams Consumer Group

| Stream | Consumer Group | 소비자 | 목적 |
|--------|---------------|--------|------|
| `axiom:events` | `vision_group` | Vision 서비스 | 분석 이벤트 반응 |
| `axiom:events` | `synapse_group` | Synapse 서비스 | 온톨로지 갱신 |
| `axiom:watches` | `watch_cep_group` | Watch CEP Worker | CEP 룰 평가 |
| `axiom:workers` | `worker_group` | OCR/Extract/Generate Workers | 비동기 작업 처리 |
| `axiom:process_mining` | `synapse_mining_group` | Synapse 서비스 | 프로세스 마이닝 실행 (발견, 적합성, 성능) |
| `axiom:process_mining` | `canvas_mining_group` | Canvas 프론트엔드 | 마이닝 결과 실시간 SSE/WebSocket 전달 |
| `axiom:notifications:{tenant_id}` | (없음 - SSE) | Canvas 프론트엔드 | 실시간 알림 |

### 5.2 at-least-once 보장

```
[사실] Redis Streams + Consumer Group은 at-least-once 전달을 보장한다.
[결정] 소비자는 멱등성(idempotency)을 보장해야 한다.

구현:
  1. 이벤트 ID 기반 중복 체크 (processed_events SET, TTL 7일)
  2. DB 연산은 UPSERT 사용 (INSERT ON CONFLICT UPDATE)
  3. XACK은 처리 완료 후에만 호출 (실패 시 재전달)
  4. Pending 메시지 자동 복구 (XPENDING + XCLAIM, 5분 타임아웃)
  5. 영구 실패 메시지는 DLQ로 이동 (resilience-patterns.md §5 참조)
```

---

## 6. 재평가 조건

| 조건 | 재평가 대상 |
|------|-----------|
| 이벤트 처리 지연 > 30초 빈발 | 폴링 간격 감소 또는 LISTEN/NOTIFY 전환 |
| Redis 메모리 사용 > 80% | 이벤트 보존 정책 (MAXLEN) 조정 |
| Consumer 장애 복구 시간 > 5분 | Consumer Group 모니터링 강화 |
| Watch 알림 오탐률 > 10% | CEP 룰 최적화, 임계값 재조정 |

---

## 관련 문서

| 문서 | 관계 |
|------|------|
| `apps/canvas/docs/04_frontend/watch-alerts.md` | 프론트엔드 알림 UI — 역할별 알림 관련성(§8), 생명주기 & 에스컬레이션(§9), 실시간 채널 아키텍처(§10) |
| `02_api/watch-api.md` | Watch 구독/알림 REST API, SSE 스트림, 역할별 기본 구독 시드(§2.5) |
| [08_operations/performance-monitoring.md](../08_operations/performance-monitoring.md) | 이벤트 처리 지연, Pending 메시지 메트릭, Workers & Events 대시보드 |
| `docs/domain-contract-registry.md` | 이벤트 계약 버전/브레이킹 변경 승인 기준 |

---

## 근거

- K-AIR 역설계 보고서 섹션 4.7.5 (Watch Agent)
- robo-data-text2sql-main/app/core/simple_cep.py 소스코드
- robo-data-text2sql-main/app/routers/events.py 소스코드 (46KB)
- ADR-004: Redis Streams 이벤트 버스
