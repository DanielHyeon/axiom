# Oracle 아키텍처 개요

## 이 문서가 답하는 질문

- Oracle 모듈의 전체 아키텍처는 어떤 구조인가?
- 데이터는 어떤 경로로 흐르는가?
- 각 계층 간 경계는 왜 이렇게 나뉘었는가?
- 외부 시스템과의 통합 지점은 어디인가?

<!-- affects: 02_api, 03_backend, 05_llm, 06_data -->
<!-- requires-update: 00_overview/system-overview.md -->

---

## 1. 전체 아키텍처

> 엔드포인트/포트 기준은 전사 SSOT [`docs/service-endpoints-ssot.md`](../../../../docs/service-endpoints-ssot.md)를 따른다.

### 1.1 논리 아키텍처

Oracle은 **4개의 논리 계층**으로 구성된다.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        API 계층 (Routers)                           │
│                                                                     │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌──────────┐ ┌────────────┐ │
│  │  /ask   │ │ /react  │ │ /meta   │ │/feedback │ │ /events    │ │
│  │ NL2SQL  │ │ ReAct   │ │ 메타    │ │ 피드백   │ │ 이벤트룰   │ │
│  │ 단일응답│ │ 스트림  │ │ 탐색    │ │ 수집     │ │ CRUD       │ │
│  └────┬────┘ └────┬────┘ └────┬────┘ └─────┬────┘ └─────┬──────┘ │
│       │           │           │             │             │         │
├───────┼───────────┼───────────┼─────────────┼─────────────┼─────────┤
│       ▼           ▼           ▼             ▼             ▼         │
│                    파이프라인 계층 (Pipelines)                       │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                  NL2SQL Pipeline                              │  │
│  │  Embedding → GraphSearch → SchemaFormat → SQLGen → Guard     │  │
│  │  → Execute → Visualize → Cache                               │  │
│  └──────────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                  ReAct Pipeline                               │  │
│  │  Select → Generate → Validate → Fix → QualityCheck → Triage │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                    코어 계층 (Core Modules)                         │
│                                                                     │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────────────┐  │
│  │GraphSearch│ │ LLMFactory│ │ SQLGuard  │ │ CachePostprocess  │  │
│  │ 벡터검색  │ │ LLM추상화 │ │ SQL검증   │ │ 품질게이트+영속화 │  │
│  └───────────┘ └───────────┘ └───────────┘ └───────────────────┘  │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────────────┐  │
│  │ Embedding │ │  Prompt   │ │ SQLExec   │ │   Visualize       │  │
│  │ 벡터화    │ │ 프롬프트  │ │ SQL실행   │ │   시각화 추천     │  │
│  └───────────┘ └───────────┘ └───────────┘ └───────────────────┘  │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                    데이터 계층 (Data Layer)                          │
│                                                                     │
│  ┌──────────┐  ┌──────────────────┐  ┌──────────────┐  ┌────────┐  │
│  │ Synapse  │  │ Target DB        │  │ PostgreSQL   │  │ Redis  │  │
│  │ API      │  │ (PostgreSQL/     │  │ (query 이력) │  │ (캐시) │  │
│  │ (Graph)  │  │  MySQL)          │  │              │  │        │  │
│  └──────────┘  └──────────────────┘  └──────────────┘  └────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 물리 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│  Kubernetes Cluster                                      │
│                                                          │
│  ┌──────────────────────────────────────────┐           │
│  │  Oracle Service Pod                       │           │
│  │  ┌─────────────────────────────────────┐ │           │
│  │  │  FastAPI (uvicorn)                   │ │           │
│  │  │  - /text2sql/* 라우트               │ │           │
│  │  │  - 비동기 I/O (asyncio)             │ │           │
│  │  │  - 커넥션 풀 (asyncpg/aiomysql)     │ │           │
│  │  └─────────────┬───────────────────────┘ │           │
│  │                │                          │           │
│  │  ┌─────────────▼───────────────────────┐ │           │
│  │  │  Background Workers                  │ │           │
│  │  │  - CachePostprocess (품질 게이트)    │ │           │
│  │  │  - EnumCacheBootstrap (Enum 캐싱)    │ │           │
│  │  │  - EventScheduler (이벤트 감시)      │ │           │
│  │  └─────────────────────────────────────┘ │           │
│  └──────────────────┬───────────────────────┘           │
│                     │                                    │
│  ┌──────────────────▼───────────────────────┐           │
│  │  External Services                        │           │
│  │  ┌────────┐ ┌──────────┐ ┌───────────────┐ │          │
│  │  │Synapse │ │PostgreSQL│ │ OpenAI API    │ │          │
│  │  │:8003   │ │:5432     │ │ GPT-4o        │ │          │
│  │  └────────┘ └──────────┘ └───────────────┘ │          │
│  └──────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────┘
```

---

## 2. 계층 간 경계와 설계 근거

### 2.1 API 계층 <- -> 파이프라인 계층

**경계 규칙**: API 라우터는 HTTP 요청/응답만 처리하고, 비즈니스 로직은 파이프라인에 위임한다.

**근거**: K-AIR 원본에서 `ask.py` 라우터에 파이프라인 로직이 혼재되어 있었으나, Axiom에서는 파이프라인을 독립 모듈로 분리하여 ReAct와 단일 Ask에서 코어 로직을 공유할 수 있게 한다.

```python
# Forbidden: 라우터에서 직접 외부 저장소/서비스 접근
@router.post("/ask")
async def ask(q: AskRequest):
    results = await synapse_client.get("/graph/search")  # WRONG

# Required: 파이프라인에 위임
@router.post("/ask")
async def ask(q: AskRequest):
    result = await nl2sql_pipeline.execute(q.question, q.datasource_id)
    return AskResponse(**result)
```

### 2.2 파이프라인 계층 <- -> 코어 계층

**경계 규칙**: 파이프라인은 코어 모듈을 조합하는 오케스트레이터이며, 각 코어 모듈은 독립적으로 테스트 가능해야 한다.

**근거**: NL2SQL 파이프라인의 각 단계(임베딩, 검색, 생성, 검증, 실행)는 독립적 관심사이다. 한 단계의 변경이 다른 단계에 영향을 주지 않아야 한다.

### 2.3 코어 계층 <- -> 데이터 계층

**경계 규칙**: 코어 모듈은 데이터 계층에 직접 접근하지 않고, 추상화된 인터페이스(Repository 패턴)를 통해 접근한다.

**근거**: Target DB(비즈니스 데이터)와 Synapse Graph API(메타데이터)의 접근 패턴이 다르며, 이력 저장소를 PostgreSQL 표준으로 유지하면서도 레거시(K-AIR SQLite) 호환 경로에 유연하게 대응해야 한다.

---

## 3. 데이터 흐름

### 3.1 NL2SQL 요청 흐름

```
Client                    Oracle                    Synapse         Target DB       OpenAI
  │                         │                          │                │              │
  │ POST /text2sql/ask      │                          │                │              │
  │────────────────────────>│                          │                │              │
  │                         │                          │                │              │
  │                         │ 1. embed(question)       │                │              │
  │                         │─────────────────────────────────────────────────────────>│
  │                         │<─────────────────────────────────────────────────────────│
  │                         │    vector                │                │              │
  │                         │                          │                │              │
  │                         │ 2. graph_search(vector)  │                │              │
  │                         │─────────────────────────>│                │              │
  │                         │<─────────────────────────│                │              │
  │                         │    tables, columns, fks  │                │              │
  │                         │                          │                │              │
  │                         │ 3. generate_sql(schema,  │                │              │
  │                         │    question, mappings)   │                │              │
  │                         │─────────────────────────────────────────────────────────>│
  │                         │<─────────────────────────────────────────────────────────│
  │                         │    sql_query             │                │              │
  │                         │                          │                │              │
  │                         │ 4. guard(sql_query)      │                │              │
  │                         │───┐                      │                │              │
  │                         │<──┘ pass/reject          │                │              │
  │                         │                          │                │              │
  │                         │ 5. execute(sql_query)    │                │              │
  │                         │─────────────────────────────────────────>│              │
  │                         │<─────────────────────────────────────────│              │
  │                         │    rows                  │                │              │
  │                         │                          │                │              │
  │                         │ 6. visualize(rows)       │                │              │
  │                         │───┐                      │                │              │
  │                         │<──┘ chart_type           │                │              │
  │                         │                          │                │              │
  │  Response               │                          │                │              │
  │<────────────────────────│                          │                │              │
  │  {sql, data, viz, ...}  │                          │                │              │
  │                         │                          │                │              │
  │                         │ 7. cache_postprocess     │                │              │
  │                         │    (background)          │                │              │
  │                         │─────────────────────────>│                │              │
  │                         │    save Query node       │                │              │
```

### 3.2 ReAct 스트리밍 흐름

```
Client                     Oracle                     OpenAI
  │                          │                           │
  │ POST /text2sql/react     │                           │
  │─────────────────────────>│                           │
  │                          │                           │
  │  NDJSON Stream           │ 1. Select tables          │
  │<─ {"step":"select",...}──│──────────────────────────>│
  │                          │<──────────────────────────│
  │                          │                           │
  │<─ {"step":"generate",...}│ 2. Generate SQL           │
  │                          │──────────────────────────>│
  │                          │<──────────────────────────│
  │                          │                           │
  │<─ {"step":"validate",...}│ 3. Validate               │
  │                          │───┐                       │
  │                          │<──┘                       │
  │                          │                           │
  │<─ {"step":"fix",...}     │ 4. Fix (if needed)        │
  │                          │──────────────────────────>│
  │                          │<──────────────────────────│
  │                          │                           │
  │<─ {"step":"quality",...} │ 5. Quality check          │
  │                          │──────────────────────────>│
  │                          │<──────────────────────────│
  │                          │                           │
  │<─ {"step":"triage",...}  │ 6. Triage (routing)       │
  │                          │───┐                       │
  │                          │<──┘                       │
  │                          │                           │
  │<─ {"step":"result",...}  │                           │
  │  Connection close        │                           │
```

---

## 4. 외부 시스템 통합

### 4.1 통합 지점 맵

| 외부 시스템 | 통합 방식 | 프로토콜 | 데이터 방향 |
|------------|----------|---------|------------|
| **Synapse** | Graph/Meta API | HTTP REST | Oracle -> Synapse (조회) |
| **Target DB** | asyncpg/aiomysql | TCP | 읽기 전용 (SELECT) |
| **OpenAI** | HTTP REST | HTTPS | Oracle -> OpenAI (프롬프트/응답) |
| **Core 인증** | JWT 검증 | HTTP Header | Core -> Oracle (토큰 전달) |
| **Core Watch** | 이벤트 버스 | HTTP REST | Oracle <-> Core (이벤트 룰/알림) |
| **Redis** | Redis 프로토콜 | TCP :6379 | 양방향 (캐시) |

### 4.2 장애 격리

| 장애 지점 | 영향 범위 | 격리 전략 |
|----------|----------|----------|
| OpenAI API 불가 | SQL 생성 불가 | 캐시된 쿼리로 폴백, 에러 메시지 반환 |
| Synapse API 불가 | 메타/그래프 검색 불가 | SQL 실행 경로는 유지, 메타 검색만 degraded |
| Target DB 불가 | SQL 실행 불가 | SQL 생성까지는 정상, 실행만 에러 반환 |
| Redis 불가 | 캐시 미작동 | 서비스 정상, 성능 저하만 발생 |

### 장애 격리 참조

> **전체 복원력 설계**: Circuit Breaker 설정 (Core→Oracle: 5회/60s, 30s Open), Fallback 전략, K8s Probe (Readiness: Synapse+TargetDB 검사), DLQ 설계는 Core의 [resilience-patterns.md](../../../core/docs/01_architecture/resilience-patterns.md)를 참조한다.

---

## 5. 동기/비동기 경계

| 작업 | 동기/비동기 | 근거 |
|------|-----------|------|
| API 요청 처리 | 비동기 (async/await) | FastAPI 기반, 높은 동시성 요구 |
| Synapse API 호출 | 비동기 | httpx async client 사용 |
| Target DB 쿼리 | 비동기 | asyncpg/aiomysql 사용 |
| LLM 호출 | 비동기 | OpenAI async client 사용 |
| 캐시 후처리 | 비동기 백그라운드 | BackgroundTasks / asyncio.create_task |
| Enum 캐싱 | 비동기 백그라운드 | 서버 시작 시 bootstrap |
| 이벤트 스케줄러 | 비동기 백그라운드 | 주기적 SQL 실행 |

---

## 결정 사항

| 결정 | 근거 | 관련 ADR |
|------|------|---------|
| FastAPI 선택 | 비동기 I/O, 자동 OpenAPI 문서, Python 생태계 | - |
| 그래프 조회는 Synapse API 경유 | Neo4j 스키마 변경 영향 차단, 서비스 경계 명확화 | Synapse ADR/아키텍처 문서 |
| 파이프라인-코어 분리 | K-AIR 원본의 혼재 문제 해결 | - |
| 이벤트 엔진 Core 이관 | 여러 서비스가 공유해야 할 관심사 | - |

## 금지 사항

- Router에서 외부 API/DB에 직접 접근 금지
- 코어 모듈 간 순환 의존 금지
- 동기 I/O (requests, psycopg2 등) 사용 금지
- LLM 호출 결과를 검증 없이 SQL 실행에 전달 금지

## 관련 문서

- [00_overview/system-overview.md](../00_overview/system-overview.md): 시스템 개요
- [01_architecture/nl2sql-pipeline.md](./nl2sql-pipeline.md): NL2SQL 파이프라인 상세
- [01_architecture/sql-guard.md](./sql-guard.md): SQL Guard 검증 체계
- [03_backend/service-structure.md](../03_backend/service-structure.md): 서비스 내부 구조
