# Synapse 아키텍처 개요

## 이 문서가 답하는 질문

- Synapse의 전체 아키텍처는 어떻게 구성되어 있는가?
- Neo4j 그래프 설계의 핵심 원칙은 무엇인가?
- 각 내부 모듈의 경계와 책임은 어떻게 나뉘는가?
- K-AIR에서 이식한 부분과 신규 개발 부분의 경계는 어디인가?
- Process Mining Engine은 기존 아키텍처에 어떻게 통합되는가?
- EventStorming 모델에서 온톨로지까지의 데이터 파이프라인은?

<!-- affects: api, backend, frontend, llm -->
<!-- requires-update: 02_api/ontology-api.md, 03_backend/service-structure.md, 01_architecture/process-mining-engine.md -->

---

## 1. 아키텍처 다이어그램

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Axiom Core (Gateway)                            │
│                   REST 요청 라우팅 + 인증                             │
└──────────┬──────────────────────────────────────┬────────────────────┘
           │ REST API                              │ Redis Streams
           ▼                                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Synapse FastAPI Server                            │
│                                                                       │
│  ┌─────────────┐  ┌────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │  API Layer   │  │  API Layer  │  │  API Layer    │  │  API Layer  │ │
│  │  ontology.py │  │ schema_edit│  │ extraction.py │  │ process_   │ │
│  │  CRUD + 탐색 │  │ 메타 편집  │  │ 비정형→추출  │  │ mining.py  │ │
│  └──────┬──────┘  └──────┬─────┘  └──────┬───────┘  └──────┬─────┘ │
│         │                │               │                  │        │
│  ┌──────▼────────────────▼───────────────▼──────────────────▼──────┐ │
│  │                        Graph Layer                               │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │ │
│  │  │neo4j_bootstrap│  │ graph_search │  │ ontology_schema/     │  │ │
│  │  │스키마 초기화  │  │ 벡터+경로검색│  │ ingest + process_    │  │ │
│  │  │(← K-AIR)     │  │ (← K-AIR)    │  │ graph (신규 개발)    │  │ │
│  │  └──────────────┘  └──────────────┘  └──────────────────────┘  │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │                    Extraction Layer                                │ │
│  │  ┌──────────────┐  ┌────────────────┐  ┌──────────────────────┐ │ │
│  │  │ner_extractor │  │ relation_      │  │ ontology_mapper      │ │ │
│  │  │GPT-4o NER    │  │ extractor      │  │ 매핑 (비정형/음성)   │ │ │
│  │  └──────────────┘  └────────────────┘  └──────────────────────┘ │ │
│  │  ┌──────────────┐  ┌────────────────┐                             │ │
│  │  │audio_ingestio│  │ code_archaeolog│                             │ │
│  │  │n_worker (음성)│  │ y_worker (코드 │                             │ │
│  │  └──────────────┘  └────────────────┘                             │ │
└──────────────────────────────────────────────────────────────────┘ │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │                  Process Mining Layer (신규)                       │ │
│  │  ┌────────────────┐  ┌────────────────┐  ┌──────────────────┐  │ │
│  │  │process_        │  │ conformance_   │  │ temporal_        │  │ │
│  │  │discovery.py    │  │ checker.py     │  │ analysis.py      │  │ │
│  │  │pm4py 알고리즘  │  │ 적합성 검사    │  │ 시간축 분석      │  │ │
│  │  │Alpha/Heuristic │  │ Token replay   │  │ 병목/SLA/추세    │  │ │
│  │  │/Inductive Miner│  │ fitness/precis.│  │                  │  │ │
│  │  └────────────────┘  └────────────────┘  └──────────────────┘  │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │                        Core Layer                                 │ │
│  │  neo4j_client.py │ embedding_client.py │ llm_client.py │ redis  │ │
│  └──────────────────────────────────────────────────────────────────┘ │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │  Neo4j 5  │ │ Postgres │ │  Redis   │
        │ Graph +   │ │ pgvector │ │ Streams  │
        │ Vector +  │ │+이벤트로그│ │ + Cache  │
        │ Process   │ │          │ │          │
        └──────────┘ └──────────┘ └──────────┘
```

---

## 2. 레이어 아키텍처

### 2.1 API Layer (표면)

| 파일 | 책임 | 출처 |
|------|------|------|
| `api/ontology.py` | 온톨로지 CRUD, 계층 탐색, 관계 관리 | 신규 개발 |
| `api/schema_edit.py` | 테이블/컬럼 설명 편집, FK 관계 관리 | K-AIR text2sql 이식 |
| `api/extraction.py` | 비정형 문서 → 온톨로지 추출 (비동기) | 신규 개발 |

**원칙**:
- API Layer는 HTTP 요청/응답 변환만 담당한다
- 비즈니스 로직을 API Layer에 두지 않는다
- 모든 API는 Core를 경유하여 호출된다 (직접 외부 노출 금지)

### 2.2 Graph Layer (핵심)

| 파일 | 책임 | 출처 |
|------|------|------|
| `graph/neo4j_bootstrap.py` | Neo4j 스키마 초기화, 노드/관계 생성, 인덱스/제약조건 | K-AIR text2sql 이식 |
| `graph/graph_search.py` | 벡터 유사도 검색 + FK 그래프 경로 탐색 | K-AIR text2sql 이식 |
| `graph/ontology_schema.py` | 4계층 온톨로지 스키마 정의/마이그레이션 | 신규 개발 |
| `graph/ontology_ingest.py` | 케이스 데이터 → 온톨로지 노드 자동 생성 | 신규 개발 |

**원칙**:
- 모든 Neo4j Cypher 쿼리는 Graph Layer에만 존재한다
- 다른 레이어는 Graph Layer의 함수를 호출한다 (Cypher 직접 작성 금지)
- 트랜잭션 경계는 Graph Layer 함수 단위이다

### 2.3 Extraction Layer (추출 엔진)

| 파일 | 책임 | 출처 |
|------|------|------|
| `extraction/ner_extractor.py` | GPT-4o 기반 개체명 인식 (NER) | 신규 개발 |
| `extraction/relation_extractor.py` | 개체 간 관계 추출 | 신규 개발 |
| `extraction/ontology_mapper.py` | 추출된 개체/관계 → 4계층 온톨로지 매핑 | 신규 개발 |

**원칙**:
- LLM 호출은 Extraction Layer에서만 발생한다
- 모든 LLM 응답에는 신뢰도 점수가 포함된다
- 0.75 미만 신뢰도 필드는 반드시 HITL 검토를 거친다

### 2.4 Process Mining Layer (프로세스 마이닝 엔진) -- 신규

| 파일 | 책임 | 출처 |
|------|------|------|
| `mining/process_discovery.py` | pm4py 기반 프로세스 모델 발견 (Alpha/Heuristic/Inductive Miner) | 신규 개발 |
| `mining/conformance_checker.py` | 설계 모델 vs 실행 로그 적합성 검사 (Token-based replay) | 신규 개발 |
| `mining/temporal_analysis.py` | 시간축 분석, 병목 탐지, SLA 위반 검출 | 신규 개발 |
| `mining/variant_analyzer.py` | 프로세스 변종 통계, 편차 분석 | 신규 개발 |
| `mining/event_log_manager.py` | 이벤트 로그 인제스트/변환 (XES, CSV, DB) | 신규 개발 |

**원칙**:
- pm4py 호출은 Process Mining Layer에서만 발생한다
- EventStorming 모델(설계)과 이벤트 로그(실행)는 명시적으로 분리된 입력이다
- 모든 마이닝 결과는 Graph Layer를 통해 Neo4j에 저장한다
- 대용량 이벤트 로그 처리는 비동기 작업으로 수행한다

### 2.5 Core Layer (인프라)

| 파일 | 책임 |
|------|------|
| `core/neo4j_client.py` | Neo4j 드라이버 연결 관리 (싱글톤) |

---

## 3. 데이터 흐름

### 3.1 온톨로지 조회 흐름

```
Canvas → Core → Synapse API → Graph Layer → Neo4j
                                    │
                                    └→ 결과 JSON 반환
```

### 3.2 비정형 및 특수 소스(음성, Legacy Code) 추출 흐름

```
Canvas → Core → Synapse API (POST /extract-ontology 또는 /ingest/audio)
                     │
                     ▼ 비동기 작업 생성 (task_id 즉시 반환)
                     │
                     ▼ Extraction Layer
                     ├─ 1a. [문서] 텍스트 청킹 (800토큰)
                     ├─ 1b. [오디오] Whisper STT 전사 및 PII 마스킹 처리
                     ├─ 1c. [레거시 코드] AST 기반 제어/데이터 흐름(DFG) 파싱
                     ├─ 2. NER 및 규칙 추론 (GPT-4o Structured Output / Rules Engine)
                     ├─ 3. 관계(Relation) 및 정책(Policy) 추출
                     ├─ 4. 4계층 온톨로지 매핑
                     └─ 5. 신뢰도 < 0.80 → HITL 대기열
                              │
                              ▼ Graph Layer
                              └─ 신뢰도 >= 0.80 → Neo4j 자동 반영
                                 신뢰도 < 0.80 → 인간 확인 후 반영
```

### 3.3 자동 인제스트 흐름 (이벤트 기반)

```
Core ──(Redis Streams)──▶ Synapse Event Consumer
                              │
                              ▼ ontology_ingest.py
                              ├─ 케이스 데이터 변경 감지
                              ├─ 변경된 데이터 → 온톨로지 노드 매핑
                              └─ Neo4j MERGE (upsert)
```

### 3.4 EventStorming → 온톨로지 매핑 흐름

```
Canvas (EventStorming Designer)
  │
  │ POST /api/v3/synapse/ontology/eventstorming
  ▼
Synapse API → Service Layer
  │
  ├─ 1. EventStorming 모델 파싱
  │     Actor → Resource 계층 (Employee/Company)
  │     Aggregate → Resource 계층 (Asset/Inventory)
  │     Command → Process 계층 (활동)
  │     Event → Process 계층 (BusinessEvent) + 시간축 속성
  │     Policy → Process 계층 (BusinessRule)
  │
  ├─ 2. Measure 바인딩
  │     Event 체인에서 Measure 노드 자동 생성
  │     Measure → KPI 관계 설정
  │
  ├─ 3. 시간축 속성 부여
  │     각 Event에 duration, sla_threshold, expected_duration 설정
  │
  └─ 4. Graph Layer → Neo4j MERGE
        온톨로지 노드/관계 생성
```

### 3.5 Process Mining 흐름

```
Canvas → Core → Synapse API (POST /process-mining/discover)
                     │
                     ▼ 비동기 작업 생성 (task_id 즉시 반환)
                     │
                     ▼ Process Mining Layer
                     ├─ 1. Event Log 조회 (PostgreSQL)
                     ├─ 2. pm4py DataFrame 변환
                     ├─ 3. Algorithm 실행 (Alpha/Heuristic/Inductive)
                     ├─ 4. Conformance Checking (설계 vs 실행)
                     ├─ 5. Variant Analysis (변종 통계)
                     └─ 6. 결과 저장 (PostgreSQL + Neo4j)
                              │
                              ▼ Graph Layer
                              └─ 프로세스 모델 노드/관계 Neo4j 반영
                                 시간축 속성 업데이트
```

### 3.6 이벤트 로그 인제스트 흐름

```
Canvas → Core → Synapse API (POST /event-logs/ingest)
                     │
                     ▼ event_log_manager.py
                     ├─ 1. 소스 연결 (CSV 업로드 / DB 테이블 / XES 파일)
                     ├─ 2. 컬럼 매핑 (case_id, activity, timestamp)
                     ├─ 3. pm4py.format_dataframe() 변환
                     ├─ 4. PostgreSQL event_log_entries 저장
                     └─ 5. 프로세스 인스턴스 추출 → process_instances 저장
```

### 3.7 그래프 검색 흐름 (Oracle 연동)

```
Oracle → Synapse API (POST /graph/search)
              │
              ▼ graph_search.py
              ├─ 1. 벡터 유사도 검색 (cosine similarity)
              ├─ 2. 결과 노드에서 FK 그래프 경로 탐색 (최대 3홉)
              └─ 3. 관련 테이블/컬럼 메타데이터 반환
```

---

## 4. Neo4j 그래프 설계 원칙

### 4.1 노드 레이블링 전략

```
기존 K-AIR 이식 노드:     4계층 온톨로지 확장 노드:     Process Mining 확장 노드:
  (:Table)                   (:Resource)                    (:BusinessEvent)
  (:Column)                  (:Process)                     (:BusinessAction)
  (:Query)                   (:Measure)                     (:BusinessRule)
  (:ValueMapping)            (:KPI)                         (:EventLog)
                             (:Activity)                    (:ProcessInstance)
                             (:Decision)                    (:ProcessVariant)
                             (:MeasureSnapshot)
                             (:KPITarget)
                             (:KPIHistory)
```

### 4.2 다중 레이블 사용

하나의 노드가 여러 레이블을 가질 수 있다. 예를 들어 자산 노드는:

```cypher
(:Asset:Resource {name: "본사 건물", type: "RealEstate", market_value: 5000000000})
```

### 4.3 케이스 격리

모든 온톨로지 노드에 `case_id`와 `org_id` 속성을 포함하여 데이터 격리를 보장한다.

```cypher
// 항상 case_id로 필터링
MATCH (r:Resource {case_id: $case_id})
RETURN r
```

### 4.4 인덱스 전략

| 인덱스 유형 | 대상 | 목적 |
|------------|------|------|
| 유니크 제약조건 | `(Table.name)`, `(Column.table_name, Column.name)` | 중복 방지 |
| 벡터 인덱스 | `table_vector`, `column_vector`, `query_vector` | 유사도 검색 |
| 복합 인덱스 | `(Resource.case_id, Resource.type)` | 케이스별 조회 |
| 풀텍스트 인덱스 | `description`, `name` 필드 | 텍스트 검색 |

---

## 5. 경계 결정 근거

### 5.1 왜 Synapse는 독립 서비스인가?

| 근거 | 설명 |
|------|------|
| **장애 격리** | Neo4j 장애가 Core/Oracle에 전파되지 않음 |
| **독립 스케일링** | 대량 문서 추출 시 Synapse만 스케일 아웃 |
| **기술 특수성** | Neo4j 전문 지식이 필요한 팀이 독립 운영 |
| **K-AIR 이식 용이** | text2sql의 Neo4j 코드를 깔끔하게 분리 가능 |

### 5.2 왜 Synapse와 Oracle은 Neo4j를 공유하는가?

| 근거 | 설명 |
|------|------|
| **네트워크 비용** | 그래프 복제 대비 공유가 비용 효율적 |
| **일관성** | 단일 소스로 데이터 불일치 방지 |
| **읽기/쓰기 분리** | Synapse가 쓰기, Oracle이 읽기 (Synapse API 경유) |

> **결정**: Oracle은 Neo4j에 직접 쿼리하지 않고, Synapse REST API를 통해 간접 접근한다. 이는 스키마 변경 시 Oracle 코드를 수정하지 않아도 되게 하기 위함이다.

### 장애 격리 참조

> **전체 복원력 설계**: Circuit Breaker 설정 (Core→Synapse: 5회/60s, 30s Open), Fallback 전략, K8s Probe (Startup: Neo4j bootstrap 90s 허용, Readiness: Neo4j+Redis 검사), DLQ 설계는 Core의 [resilience-patterns.md](../../../core/docs/01_architecture/resilience-patterns.md)를 참조한다.

---

## 6. 동기/비동기 경계

| 작업 | 방식 | 근거 |
|------|------|------|
| 온톨로지 노드 CRUD | 동기 (REST) | 즉시 응답 필요 |
| 그래프 검색 | 동기 (REST) | Oracle Text2SQL 파이프라인 내 실시간 요청 |
| 스키마 편집 | 동기 (REST) | 즉시 반영 확인 필요 |
| 비정형 문서 추출 | **비동기** (작업 큐) | LLM 호출 포함, 수 분 소요 가능 |
| 자동 인제스트 | **비동기** (Redis Streams) | 이벤트 기반, 최종 일관성 |
| HITL 검토 완료 | 동기 (REST) | 인간 확인 후 즉시 반영 |
| 이벤트 로그 인제스트 | **비동기** (작업 큐) | 대용량 CSV/DB 데이터 수집, 수 분 소요 가능 |
| Process Discovery | **비동기** (작업 큐) | pm4py 알고리즘 실행, 대용량 로그 시 수 분 소요 |
| Conformance Checking | **비동기** (작업 큐) | Token replay 연산량 비례 |
| 병목 분석 / Variant 조회 | 동기 (REST) | 사전 계산된 결과 조회 |

---

## 금지 규칙

- Graph Layer 외부에서 Cypher 쿼리를 직접 작성하지 않는다
- API Layer에 비즈니스 로직을 두지 않는다
- Extraction Layer 외부에서 LLM을 호출하지 않는다
- Process Mining Layer 외부에서 pm4py를 직접 호출하지 않는다
- case_id 없이 온톨로지 노드를 생성하지 않는다
- 신뢰도 0.75 미만 추출 결과를 자동 반영하지 않는다
- Process Mining Layer에서 Neo4j를 직접 조작하지 않는다 (Graph Layer 경유)

## 필수 규칙

- 모든 Neo4j 쿼리에 case_id 필터를 포함한다
- 비동기 작업은 task_id를 즉시 반환한다
- LLM 응답에는 항상 신뢰도 점수를 포함한다
- 외부 모듈은 Synapse REST API만 사용한다
- 이벤트 로그에는 case_id_column, activity_column, timestamp_column 매핑이 필수이다
- Process Mining 결과에는 항상 사용된 알고리즘과 파라미터를 기록한다

---

## 근거 문서

- ADR-001: Neo4j 5 선택 근거 (`99_decisions/ADR-001-neo4j-graph.md`)
- ADR-005: pm4py Process Mining 선택 (`99_decisions/ADR-005-pm4py-process-mining.md`)
- K-AIR 역설계 분석 보고서 섹션 2.1, 4.11.5
- `01_architecture/ontology-4layer.md` (4계층 온톨로지 상세)
- `01_architecture/extraction-pipeline.md` (추출 파이프라인 상세)
- `01_architecture/process-mining-engine.md` (Process Mining Engine 상세)
- `01_architecture/audio-ingestion-pipeline.md` (음성 ASR -> 온톨로지 Ingestion)
- `01_architecture/code-archaeology-pipeline.md` (레거시 코드 -> DDD Aggregate 추출)
