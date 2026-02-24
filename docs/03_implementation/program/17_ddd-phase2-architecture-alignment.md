# DDD Phase 2: 아키텍처 정비 — BC 독립성 확보

> **Phase**: P2 (Architecture Alignment)
> **기간**: 6~12주
> **선행조건**: Phase 1 (Gate DDD-1) 통과
> **Gate**: DDD-2 — **PASS**
> **상태**: **전체 완료**
> **관련 Anti-pattern**: A5 (HIGH), A7 (MEDIUM), A9 (MEDIUM), A10 (LOW)

---

## 1. 목표

Bounded Context 간 독립성을 확보하고, Anti-Corruption Layer를 구축하며,
Core 서비스를 모듈러 모놀리스로 재구성한다. Vision 서비스에 CQRS 패턴을 도입하여
Core 이벤트 기반의 독립 읽기 모델을 구축한다.

---

## 2. 티켓 목록 및 완료 현황

| 티켓 ID | 제목 | 상태 | 핵심 산출물 |
|:-------:|------|:----:|----------|
| DDD-P2-01 | Anti-Corruption Layer 구현 | **DONE** | `synapse_acl.py` (Core 299줄, Oracle 431줄), `weaver_acl.py` (Oracle 119줄) |
| DDD-P2-02 | Core 서비스 모듈러 모놀리스 전환 | **DONE** | `modules/{process,agent,case,watch}/` 4개 모듈 |
| DDD-P2-03 | Vision CQRS 도입 | **DONE** | `analytics_service.py` CQRS_MODE + CoreClient ACL |
| DDD-P2-04 | Synapse God Class 분할 | **DONE** | ProcessMiningService Facade + 전문 서비스 분할 |
| DDD-P2-05 | Neo4j 소유권 명확화 | **DONE** | Synapse Primary Owner, Weaver API 전용 접근 |

---

## 3. DDD-P2-01: Anti-Corruption Layer 구현

### 3.1 현황 (AS-IS)

3개 지점에서 ACL이 필요하나 0개 구현:

| 지점 | 현재 상태 | 위험 |
|------|----------|:----:|
| Core → Synapse | `SynapseGatewayService` — 단순 프록시, 응답 변환 없음 (`services/core/app/services/synapse_gateway_service.py`) | HIGH |
| Oracle → Synapse | `synapse_client.search_graph()` — 응답 직접 사용 | MEDIUM |
| Oracle → Weaver | `WEAVER_QUERY_API_URL` — HTTP 직접 호출, 응답 직접 사용 | MEDIUM |

### 3.2 목표 (TO-BE)

외부 BC의 응답을 내부 도메인 모델로 변환하는 ACL을 각 지점에 구현한다.

```
External BC Response → [ACL: Translator/Mapper] → Internal Domain Model
```

### 3.3 구현 명세

#### 3.3.1 Core → Synapse ACL

```python
# services/core/app/infrastructure/external/synapse_acl.py

from dataclasses import dataclass
from typing import Any
import httpx


@dataclass(frozen=True)
class OntologySearchResult:
    """Core 도메인 내부의 온톨로지 검색 결과 모델.
    Synapse API 응답 형식에 의존하지 않는다."""
    entity_id: str
    entity_type: str
    label: str
    relevance_score: float
    properties: dict[str, Any]


class SynapseACL:
    """Anti-Corruption Layer: Synapse BC의 응답을 Core 도메인 모델로 변환한다."""

    def __init__(self, base_url: str):
        self._base_url = base_url

    async def search_ontology(self, query: str, tenant_id: str) -> list[OntologySearchResult]:
        """Synapse 그래프 검색 결과를 Core 내부 모델로 변환."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/api/v1/graph/search",
                json={"query": query},
                headers={"X-Tenant-ID": tenant_id},
                timeout=10.0,
            )
            resp.raise_for_status()
            raw = resp.json()

        # Synapse 응답 형식 → Core 내부 모델로 변환 (ACL 핵심)
        return [
            OntologySearchResult(
                entity_id=item.get("id", ""),
                entity_type=item.get("type", "unknown"),
                label=item.get("name", item.get("label", "")),
                relevance_score=float(item.get("score", 0.0)),
                properties={
                    k: v for k, v in item.items()
                    if k not in ("id", "type", "name", "label", "score")
                },
            )
            for item in raw.get("results", raw.get("nodes", []))
        ]

    async def get_process_model(self, process_id: str, tenant_id: str) -> dict | None:
        """Synapse의 프로세스 모델을 Core 내부 형식으로 변환."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._base_url}/api/v1/mining/models/{process_id}",
                headers={"X-Tenant-ID": tenant_id},
                timeout=10.0,
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            raw = resp.json()

        # 변환: Synapse의 mining 모델 형식 → Core가 이해하는 형식
        return {
            "model_id": raw.get("id"),
            "activities": raw.get("activities", []),
            "transitions": [
                {"from": t.get("source"), "to": t.get("target"), "frequency": t.get("count", 0)}
                for t in raw.get("transitions", raw.get("edges", []))
            ],
        }
```

#### 3.3.2 Oracle → Synapse/Weaver ACL

```python
# services/oracle/app/infrastructure/acl/synapse_acl.py

@dataclass(frozen=True)
class SchemaContext:
    """Oracle 도메인 내부의 스키마 컨텍스트 모델."""
    tables: list[TableInfo]
    relationships: list[Relationship]
    glossary_terms: list[GlossaryTerm]

@dataclass(frozen=True)
class TableInfo:
    name: str
    columns: list[ColumnInfo]
    description: str | None

@dataclass(frozen=True)
class ColumnInfo:
    name: str
    data_type: str
    description: str | None
    is_key: bool

class OracleSynapseACL:
    """Oracle의 Synapse ACL. 그래프 검색 결과를 NL2SQL 파이프라인용 스키마 컨텍스트로 변환."""

    async def get_schema_context(self, query: str, datasource_id: str) -> SchemaContext:
        # Synapse + Weaver 양쪽에서 정보 수집 후 통합 변환
        graph_results = await self._synapse_client.search_graph(query)
        metadata = await self._weaver_client.get_metadata(datasource_id)

        tables = self._merge_to_table_info(graph_results, metadata)
        relationships = self._extract_relationships(graph_results)
        glossary = self._extract_glossary(metadata)

        return SchemaContext(
            tables=tables,
            relationships=relationships,
            glossary_terms=glossary,
        )
```

### 3.4 기존 코드 마이그레이션

| 기존 파일 | 변경 내용 |
|----------|----------|
| `services/core/app/services/synapse_gateway_service.py` | → `infrastructure/external/synapse_acl.py`로 교체. 단순 프록시 → 변환 로직 추가 |
| `services/oracle/app/clients/synapse_client.py` | → `infrastructure/acl/synapse_acl.py`로 교체. 응답 직접 사용 → 내부 모델 변환 |

### 3.5 완료 기준

- [x] Core에 `SynapseACL` 클래스 존재 (`infrastructure/external/synapse_acl.py`, 299줄)
- [x] Oracle에 `OracleSynapseACL` 클래스 존재 (`infrastructure/acl/synapse_acl.py`, 431줄)
- [x] Oracle에 `OracleWeaverACL` 클래스 존재 (`infrastructure/acl/weaver_acl.py`, 119줄)
- [x] ACL 내부 모델: `SchemaSearchResult`, `TableInfo`, `ColumnInfo`, `QueryExecutionResult` 등 dataclass 정의
- [x] 기존 기능 회귀 테스트 통과

---

## 4. DDD-P2-02: Core 서비스 모듈러 모놀리스 전환

### 4.1 현황 (AS-IS)

Core 서비스에 최소 4개 BC가 공존:
1. **Process Orchestration** (BPM Engine, WorkItem, Saga)
2. **Agent Framework** (Agent Service, MCP Client, Knowledge Store)
3. **Case Management** (Case, CaseActivity, DocumentReview)
4. **Watch & Alerting** (WatchSubscription, WatchRule, WatchAlert, CEP Worker)

모든 BC가 단일 `services/`, `models/`, `api/` 디렉토리에 혼재.

### 4.2 목표 (TO-BE)

```
services/core/app/
├── modules/
│   ├── process/              ← BC1: Process Orchestration
│   │   ├── domain/
│   │   │   ├── aggregates/
│   │   │   │   ├── work_item.py
│   │   │   │   └── process_definition.py
│   │   │   ├── events.py
│   │   │   ├── repositories/
│   │   │   └── services/
│   │   │       └── bpm_engine.py
│   │   ├── application/
│   │   │   ├── work_item_service.py
│   │   │   ├── process_definition_service.py
│   │   │   └── process_instance_service.py
│   │   ├── infrastructure/
│   │   │   ├── repositories/
│   │   │   ├── mappers/
│   │   │   └── saga_manager.py
│   │   └── api/
│   │       └── routes.py
│   │
│   ├── agent/                ← BC2: Agent Framework
│   │   ├── domain/
│   │   ├── application/
│   │   ├── infrastructure/
│   │   └── api/
│   │
│   ├── case/                 ← BC3: Case Management
│   │   ├── domain/
│   │   ├── application/
│   │   ├── infrastructure/
│   │   └── api/
│   │
│   └── watch/                ← BC4: Watch & Alerting
│       ├── domain/
│       ├── application/
│       ├── infrastructure/
│       └── api/
│
├── shared/                   ← 공유 커널 (인증, 미들웨어, 설정)
│   ├── auth/
│   ├── middleware/
│   ├── config/
│   └── database.py
│
└── main.py                   ← 라우터 통합, startup
```

### 4.3 모듈 간 통신 규칙

| 규칙 | 설명 |
|------|------|
| 직접 import 금지 | 모듈 A가 모듈 B의 `domain/` 또는 `infrastructure/`를 직접 import할 수 없음 |
| 공개 인터페이스 | 모듈 간 통신은 `application/` 레이어의 공개 메서드 또는 도메인 이벤트를 통해서만 |
| 공유 커널 | `shared/`는 인증, DB 세션, 설정 등 기술 인프라만 포함. 도메인 개념 없음 |
| 이벤트 기반 | 모듈 간 비동기 통신은 인메모리 이벤트 버스 사용 (프로세스 내) |

#### 모듈 간 이벤트 버스

```python
# services/core/app/shared/event_bus.py

from collections import defaultdict
from typing import Any, Callable, Coroutine

EventHandler = Callable[..., Coroutine[Any, Any, None]]

class InternalEventBus:
    """프로세스 내 모듈 간 이벤트 전달. 외부 Redis Streams와 별개."""

    def __init__(self):
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    async def publish(self, event_type: str, payload: dict) -> None:
        for handler in self._handlers.get(event_type, []):
            await handler(payload)

# 싱글턴
internal_event_bus = InternalEventBus()
```

### 4.4 마이그레이션 순서

1. `modules/process/` 골격 생성 (P1 산출물 이전)
2. `modules/watch/` 분리 (기존 `watch_service.py`, `watch_cep.py` 이전)
3. `modules/agent/` 분리 (기존 `agent_service.py`, `mcp_client.py` 이전)
4. `modules/case/` 분리 (기존 Case 관련 코드 이전)
5. `shared/` 구성 (공통 인프라 추출)
6. `main.py` 라우터 통합 수정
7. 모듈 간 직접 import 제거, 이벤트 버스/공개 인터페이스로 전환

### 4.5 완료 기준

- [x] Core 서비스 내 4개 모듈 디렉토리 존재 (`modules/process/`, `modules/agent/`, `modules/case/`, `modules/watch/`)
- [x] 각 모듈 내부에 `domain/`, `application/`, `infrastructure/`, `api/` 계층 분리
- [x] 각 모듈이 독립적으로 테스트 가능
- [x] `main.py`에서 모듈별 라우터 통합
- [x] `shared/event_bus/bus.py` — InternalEventBus로 모듈 간 이벤트 통신 (65줄)

---

## 5. DDD-P2-03: Vision CQRS 도입

### 5.1 현황 (AS-IS)

Vision은 분석 전용 서비스이지만 Core DB를 직접 접근하고 있었다.
P0에서 Core API 호출로 전환했으나, 여전히 동기 HTTP 의존이 남아있어
Core 장애 시 Vision도 동작 불가.

### 5.2 목표 (TO-BE)

Vision이 Core 이벤트를 소비하여 독립적 **읽기 모델(Materialized View)**을 유지한다.

```
Core (Write) → [Event Outbox] → [Relay] → Redis Streams
                                              ↓
Vision (Read Model) ← [Event Consumer] ← Redis Streams
                    ↓
                vision.analytics_case_summary (독립 테이블)
```

### 5.3 구현 명세

#### 5.3.1 Vision 읽기 모델 테이블

```sql
-- Vision 전용 읽기 모델 (비정규화)
CREATE TABLE vision.case_summary (
    tenant_id VARCHAR NOT NULL,
    total_cases INTEGER DEFAULT 0,
    active_cases INTEGER DEFAULT 0,
    completed_cases INTEGER DEFAULT 0,
    cancelled_cases INTEGER DEFAULT 0,
    avg_completion_days FLOAT,
    last_updated_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (tenant_id)
);
```

#### 5.3.2 Vision Event Consumer

```python
# services/vision/app/workers/case_event_consumer.py

class CaseEventConsumer:
    """Core BC의 케이스/프로세스 이벤트를 소비하여 Vision 읽기 모델을 갱신한다."""

    STREAM = "axiom:events"
    GROUP = "vision_analytics_group"

    async def run(self):
        while True:
            messages = await self._redis.xreadgroup(
                groupname=self.GROUP,
                consumername="vision-1",
                streams={self.STREAM: ">"},
                count=10,
                block=5000,
            )
            for stream, entries in messages:
                for msg_id, data in entries:
                    await self._handle_event(data)
                    await self._redis.xack(self.STREAM, self.GROUP, msg_id)

    async def _handle_event(self, data: dict):
        event_type = data.get("event_type")
        tenant_id = data.get("tenant_id")

        if event_type == "PROCESS_INITIATED":
            await self._increment_total(tenant_id)
        elif event_type == "WORKITEM_COMPLETED":
            await self._update_completion_stats(tenant_id, data)
        elif event_type == "SAGA_COMPENSATION_COMPLETED":
            await self._increment_cancelled(tenant_id)

    async def _increment_total(self, tenant_id: str):
        """UPSERT: total_cases += 1, active_cases += 1"""
        await self._db.execute("""
            INSERT INTO vision.case_summary (tenant_id, total_cases, active_cases, last_updated_at)
            VALUES (%s, 1, 1, now())
            ON CONFLICT (tenant_id) DO UPDATE SET
                total_cases = vision.case_summary.total_cases + 1,
                active_cases = vision.case_summary.active_cases + 1,
                last_updated_at = now()
        """, (tenant_id,))
```

#### 5.3.3 analytics_service.py 수정

```python
# AS-IS (P0 이후): Core API HTTP 호출
stats = await core_client.get_case_stats(tenant_id)

# TO-BE: 로컬 읽기 모델 조회 (우선), Fallback으로 Core API
async def _get_case_stats(self, tenant_id: str) -> dict:
    # 1차: Vision 독립 읽기 모델 조회
    row = await self._query_local_summary(tenant_id)
    if row:
        return row

    # Fallback: Core API (읽기 모델 미구축 시)
    return await self._core_client.get_case_stats(tenant_id)
```

### 5.4 Dual-Read 전환 전략

| 단계 | 기간 | 동작 |
|:----:|:----:|------|
| 1 | 1주 | Event Consumer 배포, 읽기 모델 빌드 시작. 여전히 Core API 우선 |
| 2 | 1주 | 읽기 모델 ↔ Core API 결과 비교 로깅 (Shadow Mode) |
| 3 | 안정화 후 | 읽기 모델 우선, Core API를 Fallback으로 전환 |
| 4 | 최종 | Core API Fallback 제거, 완전 독립 |

### 5.5 완료 기준

- [x] Vision CQRS Read Model 구현 (`analytics_service.py`, 560줄)
- [x] `VISION_CQRS_MODE` 환경변수로 shadow/primary/standalone 전환 가능
- [x] CoreClient ACL (`clients/core_client.py`, 164줄) — Core API fallback 패턴
- [x] Vision 독립 읽기 모델 조회 가능 (standalone 모드)

---

## 6. DDD-P2-04: Synapse God Class 분할

### 6.1 현황 (AS-IS)

| 클래스 | 줄 수 | 책임 |
|--------|:-----:|------|
| `ProcessMiningService` | 770줄 | discover, conformance, bottleneck, performance, variants, BPMN export/import, task lifecycle |
| `EventLogService` | 638줄 | CSV/XES/DB 파싱, 검증, 통계, CRUD, 이벤트 집계 |

### 6.2 목표 (TO-BE)

```
synapse/services/
├── process_discovery_service.py    ← 프로세스 발견 (alpha, heuristic)
├── conformance_service.py          ← 적합도 검증
├── bottleneck_service.py           ← 병목 분석
├── variant_service.py              ← 프로세스 변형 분석
├── event_log_parser.py             ← CSV/XES/DB 파싱 전담
├── event_log_repository.py         ← 이벤트 로그 CRUD
├── event_log_statistics.py         ← 이벤트 로그 통계 계산
└── mining_task_coordinator.py      ← 마이닝 태스크 라이프사이클 관리
```

### 6.3 분할 기준

1. **Single Responsibility**: 각 클래스는 하나의 분석 유형 또는 하나의 데이터 처리 책임만
2. **300줄 이하**: 각 클래스 최대 300줄
3. **독립 테스트**: 각 클래스가 다른 분석 서비스 없이 테스트 가능

### 6.4 마이그레이션 전략

1. 기존 `ProcessMiningService`의 public 메서드 시그니처 유지
2. 내부를 새 클래스들에 위임 (Facade 패턴)
3. API Router에서 점진적으로 새 클래스 직접 호출로 전환
4. 안정화 후 Facade 제거

```python
# Step 1: Facade로 기존 인터페이스 유지
class ProcessMiningService:
    """기존 인터페이스 유지하는 Facade. 내부를 전문 서비스에 위임."""

    def __init__(self, db_session_factory):
        self._discovery = ProcessDiscoveryService(db_session_factory)
        self._conformance = ConformanceService(db_session_factory)
        self._bottleneck = BottleneckService(db_session_factory)
        self._variant = VariantService(db_session_factory)
        self._coordinator = MiningTaskCoordinator(db_session_factory)

    async def discover_process(self, log_id, params):
        return await self._discovery.discover(log_id, params)

    async def check_conformance(self, log_id, model_id, params):
        return await self._conformance.check(log_id, model_id, params)
```

### 6.5 완료 기준

- [x] `ProcessMiningService` God Class → Facade 패턴 적용, 전문 서비스에 위임
- [x] `EventLogService` 분할 (Parser, Repository, Statistics 책임 분리)
- [x] 기존 API 응답 형식 불변 (Facade 유지)
- [x] 각 클래스 독립 단위 테스트 존재

---

## 7. DDD-P2-05: Neo4j 소유권 명확화

### 7.1 현황 (AS-IS)

Synapse와 Weaver가 동일 Neo4j 인스턴스(`neo4j-db`)를 공유:
- Synapse: 온톨로지 노드/관계, 이벤트 로그 그래프
- Weaver: 메타데이터 카탈로그, 데이터소스 스키마 그래프

### 7.2 목표 (TO-BE)

- **Synapse**: Neo4j Primary Owner (읽기/쓰기 모두)
- **Weaver**: Synapse API를 통해 그래프 접근 (직접 Neo4j 접속 금지)

### 7.3 구현 명세

#### Step 1: Weaver의 Neo4j 직접 접근 식별

```bash
grep -rn "neo4j\|bolt://" services/weaver/
```

#### Step 2: Synapse에 메타데이터 그래프 API 추가

```python
# services/synapse/app/api/metadata/routes.py (신규)
@router.post("/metadata/graph/upsert")
async def upsert_metadata_node(request: MetadataNodeRequest):
    """Weaver가 메타데이터를 그래프에 반영할 때 사용하는 API."""
    ...

@router.get("/metadata/graph/search")
async def search_metadata_graph(query: str, tenant_id: str):
    """Weaver가 그래프 기반 메타데이터 검색 시 사용."""
    ...
```

#### Step 3: Weaver에서 Neo4j 직접 접근 제거

```python
# AS-IS: services/weaver에서 Neo4j bolt:// 직접 접속
# TO-BE: Synapse API 호출

class SynapseMetadataClient:
    """Weaver → Synapse 메타데이터 그래프 접근 클라이언트."""

    async def upsert_node(self, node_type: str, properties: dict):
        await self._http_client.post(
            f"{self._synapse_url}/api/v1/metadata/graph/upsert",
            json={"type": node_type, "properties": properties},
        )
```

#### Step 4: docker-compose.yml 변경

```yaml
weaver-svc:
  environment:
    # AS-IS: NEO4J_URI=bolt://neo4j-db:7687  ← 제거
    # TO-BE:
    - SYNAPSE_BASE_URL=http://synapse-svc:8003
  depends_on:
    # AS-IS: neo4j-db  ← 제거
    # TO-BE:
    - synapse-svc
```

### 7.4 완료 기준

- [x] Neo4j 소유권: Synapse Primary Owner로 확정
- [x] Weaver → Synapse API를 통한 그래프 접근 패턴 수립
- [x] Synapse 메타데이터 그래프 API 존재
- [x] 기존 Weaver 메타데이터 기능 회귀 테스트 통과

---

## 8. Phase 2 타임라인

```
Week 1-2:   [DDD-P2-01 ACL 설계 + Core/Synapse ACL 구현]
Week 2-3:   [DDD-P2-01 Oracle ACL 구현]
Week 3-5:   [DDD-P2-02 Core 모듈러 모놀리스 전환]
Week 5-7:   [DDD-P2-03 Vision CQRS (Consumer + 읽기 모델)]
Week 7-9:   [DDD-P2-04 Synapse God Class 분할]
Week 9-10:  [DDD-P2-05 Neo4j 소유권 명확화]
Week 10-11: [통합 테스트 + Shadow Mode 검증]
Week 12:    [Gate DDD-2 검증]
```

---

## 9. Gate DDD-2 통과 결과 — **PASS**

- [x] ACL 3개 지점 구현: Core→Synapse (`synapse_acl.py` 299줄), Oracle→Synapse (`synapse_acl.py` 431줄), Oracle→Weaver (`weaver_acl.py` 119줄)
- [x] Core 모듈러 분리: 4개 모듈 (process, agent, case, watch), InternalEventBus 연동
- [x] Vision CQRS 읽기 모델: `VISION_CQRS_MODE` 환경변수, CoreClient fallback 패턴
- [x] Synapse God Class 분할: Facade 패턴 + 전문 서비스 위임
- [x] Neo4j 소유권: Synapse Primary Owner 확정
- [x] 전 서비스 API 회귀 테스트 통과 (Docker 환경 검증)
