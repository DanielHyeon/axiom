# DDD Phase 0: 즉시 수정 — 운영 위험 해소

> **Phase**: P0 (Immediate Fixes)
> **기간**: 1~2주
> **선행조건**: 없음
> **Gate**: DDD-0 — **PASS**
> **상태**: **전체 완료**
> **관련 Anti-pattern**: A2 (CRITICAL), A3 (HIGH), A6 (HIGH)

---

## 1. 목표

운영 데이터 유실, 이벤트 적체, BC 경계 침범 등 **즉각적 위험**을 해소한다.
기능 변경 없이 인프라/통합 레벨의 수정만 수행하며, 기존 API 계약은 변경하지 않는다.

---

## 2. 티켓 목록 및 완료 현황

| 티켓 ID | 제목 | 상태 | 구현 파일 |
|:-------:|------|:----:|----------|
| DDD-P0-01 | Outbox Relay Worker 구현 | **DONE** | `services/core/app/workers/sync.py` (SyncWorker, 230줄) |
| DDD-P0-02 | Vision BC 경계 침범 제거 | **DONE** | `services/vision/app/clients/core_client.py` (164줄) |
| DDD-P0-03 | 인메모리 상태 영속화 | **DONE** | Synapse/Weaver 각 스키마 영속화 완료 |
| DDD-P0-04 | Domain Vision Statement 문서화 | **DONE** | `docs/00_project/domain-vision-statement.md` (159줄) |

---

## 3. DDD-P0-01: Outbox Relay Worker 구현

### 3.1 현황 (AS-IS)

- `EventPublisher.publish()` (`services/core/app/core/events.py:20-55`)가 `event_outbox` 테이블에 `PENDING` 상태로 이벤트를 INSERT한다.
- **Relay Worker가 존재하지 않아**, PENDING 이벤트가 Redis Streams로 전달되지 않는다.
- Consumer 측 (`services/core/app/workers/watch_cep.py`, `services/synapse/app/events/consumer.py`)은 이미 Redis Streams 구독 준비가 되어 있다.
- `EventContractRegistry` (`services/core/app/core/event_contract_registry.py:23-52`)에 4개 이벤트가 등록되어 있다.

### 3.2 목표 (TO-BE)

```
event_outbox (PENDING) → [Outbox Relay Worker] → Redis Streams → Consumer Groups
```

### 3.3 구현 명세

#### 3.3.1 파일 생성

| 파일 | 역할 |
|------|------|
| `services/core/app/workers/outbox_relay.py` | Outbox Relay Worker 본체 |
| `services/core/tests/unit/test_outbox_relay.py` | 단위 테스트 |
| `services/core/tests/integration/test_outbox_relay_integration.py` | 통합 테스트 |

#### 3.3.2 Outbox Relay Worker 설계

```python
# services/core/app/workers/outbox_relay.py (의사코드)

class OutboxRelayWorker:
    """
    PENDING 이벤트를 event_outbox에서 읽어 Redis Streams로 발행하고
    상태를 PUBLISHED로 갱신한다.

    핵심 원칙:
    1. 순서 보장: created_at ASC 순서로 처리
    2. 멱등성: idempotency_key로 중복 발행 방지
    3. 배치 처리: BATCH_SIZE(기본 50)씩 처리
    4. 실패 격리: 개별 이벤트 실패 시 FAILED 마킹 후 계속 진행
    5. Dead Letter: MAX_RETRY(3) 초과 시 DEAD_LETTER 상태로 전환
    """

    BATCH_SIZE = 50
    POLL_INTERVAL_SECONDS = 1.0
    MAX_RETRY = 3
    STREAM_NAME = "axiom:events"

    async def run(self):
        """메인 루프: PENDING 이벤트 폴링 → Redis 발행 → 상태 갱신"""
        while self._running:
            batch = await self._fetch_pending_batch()
            if not batch:
                await asyncio.sleep(self.POLL_INTERVAL_SECONDS)
                continue
            for event in batch:
                try:
                    await self._publish_to_stream(event)
                    await self._mark_published(event.id)
                except Exception as e:
                    await self._handle_failure(event, e)

    async def _fetch_pending_batch(self) -> list[EventOutbox]:
        """SELECT * FROM event_outbox
           WHERE status = 'PENDING'
           ORDER BY created_at ASC
           LIMIT :batch_size
           FOR UPDATE SKIP LOCKED"""
        ...

    async def _publish_to_stream(self, event: EventOutbox):
        """redis.xadd(STREAM_NAME, {
            'event_type': event.event_type,
            'aggregate_type': event.aggregate_type,
            'aggregate_id': event.aggregate_id,
            'payload': json.dumps(event.payload),
            'tenant_id': event.tenant_id,
            'idempotency_key': event.payload.get('idempotency_key'),
        })"""
        ...

    async def _mark_published(self, event_id: str):
        """UPDATE event_outbox SET status = 'PUBLISHED', published_at = now()
           WHERE id = :event_id"""
        ...

    async def _handle_failure(self, event: EventOutbox, error: Exception):
        """retry_count 증가. MAX_RETRY 초과 시 DEAD_LETTER로 전환"""
        ...
```

#### 3.3.3 DB 스키마 변경

```sql
-- event_outbox 테이블에 컬럼 추가
ALTER TABLE event_outbox ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ;
ALTER TABLE event_outbox ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0;
ALTER TABLE event_outbox ADD COLUMN IF NOT EXISTS last_error TEXT;

-- 상태값 확장: PENDING → PUBLISHED | FAILED | DEAD_LETTER
-- status 컬럼은 이미 String이므로 값만 확장
```

#### 3.3.4 Redis Streams 설정

```python
# Consumer Group 생성 (startup 시)
await redis.xgroup_create("axiom:events", "synapse_group", mkstream=True)
await redis.xgroup_create("axiom:events", "watch_cep_group", mkstream=True)
```

#### 3.3.5 Startup 등록

```python
# services/core/app/main.py 에 추가
from app.workers.outbox_relay import OutboxRelayWorker

@app.on_event("startup")
async def start_outbox_relay():
    relay = OutboxRelayWorker(redis=redis_pool, db_url=DATABASE_URL)
    asyncio.create_task(relay.run())
```

### 3.4 테스트 전략

| 테스트 유형 | 검증 항목 | 기대 결과 |
|-----------|----------|----------|
| 단위 | `_fetch_pending_batch` 정렬 순서 | `created_at ASC` 순서 |
| 단위 | `_handle_failure` retry_count 증가 | 3회 초과 시 DEAD_LETTER |
| 단위 | 멱등성 키 중복 발행 방지 | 동일 키 재발행 시 skip |
| 통합 | PENDING → PUBLISHED 전체 흐름 | Redis Stream에 메시지 도착 확인 |
| 통합 | Consumer Group 수신 확인 | watch_cep, synapse 그룹에서 메시지 수신 |

### 3.5 완료 기준

- [x] `event_outbox`의 PENDING 이벤트가 60초 이내에 Redis Streams로 전달됨
- [x] PUBLISHED 상태의 이벤트가 `published_at` 타임스탬프를 가짐
- [x] 3회 실패 시 DEAD_LETTER로 전환되고 `last_error`에 사유 기록
- [x] 기존 `watch_cep.py`, `consumer.py` Consumer가 메시지를 정상 수신
- [x] 단위 테스트 + 통합 테스트 통과 (6 passed — `test_outbox_relay.py`)

#### 구현 상세 (코드 기준)

- **SyncWorker** (`services/core/app/workers/sync.py:27-230`): BaseWorker 상속, `publish_pending_once()` 메서드가 PENDING 이벤트를 `created_at ASC` + `FOR UPDATE SKIP LOCKED`로 폴링
- **스트림 라우팅**: `_resolve_stream()` — `WATCH_*` → `axiom:watches`, `WORKER_*` → `axiom:workers`, 기타 → `axiom:core:events`
- **실패 처리**: `retry_count` 증가, `MAX_RETRY=3` 초과 시 `DEAD_LETTER` + `EventDeadLetter` DB 테이블에 영속화 + `axiom:dlq:events` 스트림에 DLQ 메시지 발행
- **메트릭**: `core_event_outbox_published_total`, `core_event_outbox_failed_total`, `core_event_outbox_pending`, `core_relay_lag_seconds`, `core_dlq_depth`

---

## 4. DDD-P0-02: Vision BC 경계 침범 제거

### 4.1 현황 (AS-IS)

`services/vision/app/services/analytics_service.py` (line 169-178)에서 Core BC 소유의 `core_case` 테이블을 직접 SQL로 조회한다:

```python
cur.execute("""
    SELECT
        count(*) AS total_cases,
        count(*) FILTER (WHERE status = 'IN_PROGRESS') AS active_cases
    FROM core_case
    WHERE tenant_id = %s
""", (tenant_id,))
```

이는 **BC 자율성 파괴**, **데이터 소유권 위반**, **스키마 커플링**을 유발한다.

### 4.2 목표 (TO-BE)

Vision은 Core API를 통해서만 케이스 통계를 조회한다.

```
Vision → [HTTP] → Core API /api/v1/cases/stats → Core DB (core_case)
```

### 4.3 구현 명세

#### 4.3.1 Step 1: Core API에 통계 엔드포인트 추가

```python
# services/core/app/api/case/routes.py — 신규 엔드포인트
@router.get("/cases/stats")
async def get_case_stats(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """케이스 집계 통계를 반환한다. Vision 등 외부 BC용."""
    result = await db.execute(
        select(
            func.count(Case.id).label("total_cases"),
            func.count(Case.id).filter(Case.status == "IN_PROGRESS").label("active_cases"),
        ).where(Case.tenant_id == tenant_id)
    )
    row = result.one()
    return {
        "total_cases": row.total_cases or 0,
        "active_cases": row.active_cases or 0,
    }
```

#### 4.3.2 Step 2: Vision에 Core HTTP 클라이언트 추가

```python
# services/vision/app/clients/core_client.py — 신규 파일
import httpx
import os

CORE_BASE_URL = os.getenv("CORE_BASE_URL", "http://core-svc:8002")

class CoreClient:
    """Core 서비스와의 통신을 담당하는 Anti-Corruption Layer."""

    async def get_case_stats(self, tenant_id: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{CORE_BASE_URL}/api/v1/cases/stats",
                headers={"X-Tenant-ID": tenant_id},
                timeout=5.0,
            )
            resp.raise_for_status()
            return resp.json()
```

#### 4.3.3 Step 3: analytics_service.py에서 직접 SQL 제거

```python
# services/vision/app/services/analytics_service.py — 변경
# AS-IS: cur.execute("SELECT ... FROM core_case ...")
# TO-BE:
from app.clients.core_client import CoreClient

core_client = CoreClient()
stats = await core_client.get_case_stats(tenant_id)
total = stats.get("total_cases", 0)
active = stats.get("active_cases", 0)
```

#### 4.3.4 Step 4: docker-compose.yml에 환경변수 추가

```yaml
# vision-svc 환경변수 추가
- CORE_BASE_URL=http://core-svc:8002
```

### 4.4 테스트 전략

| 테스트 유형 | 검증 항목 | 기대 결과 |
|-----------|----------|----------|
| 단위 | `CoreClient.get_case_stats()` mock 응답 | 정상 파싱 |
| 단위 | Core API `/cases/stats` 응답 형식 | `total_cases`, `active_cases` 필드 존재 |
| 통합 | Vision → Core API 통한 통계 조회 | DB 직접 접근 없이 동일 결과 |
| 회귀 | Vision KPI 대시보드 기존 동작 | 기존 API 응답 형식 불변 |

### 4.5 완료 기준

- [x] `analytics_service.py`에서 `core_case` 테이블 직접 참조 코드 0건
- [x] Vision이 `CORE_BASE_URL` 환경변수를 통해 Core API만 호출
- [x] Core에 `/api/v1/cases/stats` 엔드포인트 정상 작동
- [x] 기존 Vision KPI 대시보드 응답 불변 (회귀 테스트 통과)
- [x] `grep -r "core_case" services/vision/` 결과 0건

#### 구현 상세 (코드 기준)

- **CoreClient** (`services/vision/app/clients/core_client.py`, 164줄): Core BC ACL, REST 기반 case 통계 조회 + fallback 패턴
- **CQRS 모드**: `analytics_service.py`에 `VISION_CQRS_MODE` (shadow/primary/standalone) 환경변수로 점진적 전환 지원

---

## 5. DDD-P0-03: 인메모리 상태 영속화

### 5.1 현황 (AS-IS)

#### Synapse

| 클래스 | 인메모리 상태 | 파일 | 위험 |
|--------|------------|------|:----:|
| `ProcessMiningService` | `_tasks`, `_results`, `_models` | `services/synapse/app/services/process_mining_service.py` | CRITICAL |
| `OntologyService` | `_case_nodes`, `_role_nodes`, `_relationships` | `services/synapse/app/services/ontology_service.py` | HIGH |

#### Weaver

| 클래스 | 인메모리 상태 | 파일 | 위험 |
|--------|------------|------|:----:|
| `WeaverRuntime` | 9개 딕셔너리 (`datasources`, `materialized_tables`, `query_jobs` 등) | `services/weaver/app/services/weaver_runtime.py:13-24` | CRITICAL |

### 5.2 목표 (TO-BE)

- **Synapse**: Mining 결과/모델을 PostgreSQL에 영속화. Ontology 캐시는 Redis로 이전.
- **Weaver**: `datasources`, `glossary` 등 핵심 레지스트리를 PostgreSQL에 영속화. 임시 데이터(`query_jobs`)는 Redis TTL.

### 5.3 구현 명세

#### 5.3.1 Synapse — ProcessMiningService 영속화

```python
# Step 1: 마이닝 결과 테이블 추가 (synapse 전용 스키마)
# services/synapse/app/models/mining_models.py

class MiningTask(Base):
    __tablename__ = "synapse_mining_task"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, index=True)
    task_type = Column(String, nullable=False)     # discover, conformance, bottleneck 등
    status = Column(String, default="PENDING")      # PENDING, RUNNING, COMPLETED, FAILED
    input_params = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))

class MiningResult(Base):
    __tablename__ = "synapse_mining_result"
    id = Column(String, primary_key=True)
    task_id = Column(String, ForeignKey("synapse_mining_task.id"), index=True)
    result_type = Column(String, nullable=False)    # model, stats, conformance 등
    result_data = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

```python
# Step 2: ProcessMiningService 수정
# AS-IS: self._tasks = {}  (인메모리)
# TO-BE:
class ProcessMiningService:
    def __init__(self, db_session_factory):
        self._db = db_session_factory
        self._max_active_tasks = 8

    async def start_discovery(self, tenant_id, params):
        task = MiningTask(id=str(uuid4()), tenant_id=tenant_id, ...)
        async with self._db() as session:
            session.add(task)
            await session.commit()
        # 백그라운드 실행
        asyncio.create_task(self._run_discovery(task.id, params))
```

#### 5.3.2 Weaver — WeaverRuntime 영속화

```python
# Step 1: 핵심 레지스트리 테이블
# services/weaver/app/models/registry_models.py

class DataSourceRegistry(Base):
    __tablename__ = "weaver_datasource"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    ds_type = Column(String, nullable=False)        # postgres, mysql, oracle
    connection_config = Column(JSON, nullable=False) # 암호화 필요
    status = Column(String, default="ACTIVE")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class GlossaryEntry(Base):
    __tablename__ = "weaver_glossary"
    id = Column(String, primary_key=True)
    term = Column(String, nullable=False, index=True)
    definition = Column(String)
    source_table = Column(String)
    source_column = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

```python
# Step 2: WeaverRuntime → WeaverRepository로 전환
class WeaverRepository:
    """영속화된 레지스트리에 접근하는 Repository."""

    def __init__(self, db_session_factory, redis):
        self._db = db_session_factory
        self._redis = redis  # 임시 데이터 (query_jobs) 용

    async def get_datasource(self, ds_id: str) -> dict | None:
        async with self._db() as session:
            result = await session.execute(
                select(DataSourceRegistry).where(DataSourceRegistry.id == ds_id)
            )
            row = result.scalar_one_or_none()
            return row.__dict__ if row else None

    async def save_query_job(self, job_id: str, data: dict, ttl: int = 3600):
        """임시 쿼리 작업은 Redis에 TTL과 함께 저장."""
        await self._redis.setex(f"weaver:job:{job_id}", ttl, json.dumps(data))
```

#### 5.3.3 마이그레이션 전략

1. **DB 마이그레이션**: Alembic으로 새 테이블 생성 (기존 테이블 변경 없음)
2. **이중 쓰기 기간**: 2~3일간 인메모리 + DB 동시 쓰기, 불일치 로깅
3. **인메모리 제거**: 이중 쓰기 기간 후 인메모리 딕셔너리 코드 제거

### 5.4 완료 기준

- [x] Synapse 재시작 후 Mining Task/Result 유지 확인
- [x] Weaver 재시작 후 DataSource 레지스트리 유지 확인
- [x] 인메모리 딕셔너리 참조 코드 0건
- [x] DB 테이블 자동 생성 (startup 시 `CREATE TABLE IF NOT EXISTS`)
- [x] 기존 API 엔드포인트 응답 불변 (회귀 테스트)

---

## 6. DDD-P0-04: Domain Vision Statement 문서화

### 6.1 목적

Core Domain (Core + Synapse) 의 도메인 비전을 명시적으로 문서화하여, 전체 팀이 DDD 투자 방향을 공유한다.

### 6.2 산출물

`docs/00_project/domain-vision-statement.md` 파일 생성:

```markdown
# Axiom Domain Vision Statement

## Core Domain: Business Process Intelligence Engine
Axiom의 핵심 차별화 요소는 **레거시 시스템의 비정형 프로세스를 AI 기반으로
구조화하고 최적화하는 역량**이다.

### Core Service — Process Orchestration
- BPM 엔진을 통한 프로세스 라이프사이클 관리
- AI Agent 오케스트레이션과 Human-in-the-Loop 협업
- Saga 기반 보상 트랜잭션으로 장기 프로세스 안정성 보장

### Synapse Service — Process Intelligence
- 프로세스 마이닝을 통한 실제 프로세스 발견/적합도 검증
- 지식 그래프 기반 도메인 온톨로지 자동 구축
- NER 기반 비정형 데이터 의미 추출

## Supporting Domains
- **Vision**: 분석/시뮬레이션을 통한 의사결정 지원
- **Oracle**: 자연어 → SQL 변환을 통한 데이터 접근 민주화
- **Weaver**: 다중 데이터소스 메타데이터 통합 패브릭

## Generic Domains
- **Canvas**: 표현 계층 (React UI)
- **인증/인가**: 표준 JWT 기반 (Core 내 Generic)
```

### 6.3 완료 기준

- [x] `docs/00_project/domain-vision-statement.md` 파일 존재 (159줄)
- [x] 서브도메인 분류 (Core/Supporting/Generic) 명시
- [x] DDD 투자 수준 가이드 포함
- [x] Bounded Context Map 포함
- [x] Ubiquitous Language 핵심 용어 정의

---

## 7. Phase 0 타임라인

```
Day 1-2:  [DDD-P0-04 Vision Statement] [DDD-P0-01 Outbox Relay 설계/구현]
Day 3-4:  [DDD-P0-01 Outbox Relay 테스트] [DDD-P0-02 Vision BC Fix]
Day 5-7:  [DDD-P0-03 Synapse 영속화] [DDD-P0-03 Weaver 영속화]
Day 8:    [Gate DDD-0 검증]
```

## 8. Gate DDD-0 통과 결과 — **PASS**

- [x] Outbox Relay Worker 작동: PENDING 이벤트 → Redis Streams 전달 (SyncWorker 5초 폴링)
- [x] Vision에서 `core_case` 직접 SQL 접근 코드 0건 (CoreClient ACL로 전환)
- [x] Synapse 재시작 후 Mining 결과 유지 (PostgreSQL synapse 스키마)
- [x] Weaver 재시작 후 DataSource 레지스트리 유지 (PostgreSQL weaver 스키마)
- [x] Domain Vision Statement 문서 존재 (`docs/00_project/domain-vision-statement.md`)
- [x] 전 서비스 기존 API 회귀 테스트 통과 (Docker 환경 검증 완료)
