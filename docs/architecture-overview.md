# Axiom 아키텍처 개요 (v5.0)

> 6개 마이크로서비스 + 1 React SPA의 전체 시스템 구성도

<!-- affects: all services, all frontend features -->
<!-- requires-update: docs/01_architecture/, docs/02_api/ -->

## 이 문서가 답하는 질문

- Axiom 시스템은 어떤 서비스로 구성되어 있는가?
- 각 서비스는 어떤 역할을 담당하는가?
- 서비스 간 데이터는 어떻게 흐르는가?
- 보안과 인증은 어떻게 설계되었는가?
- 데이터베이스 스키마는 어떻게 분리되어 있는가?

---

## 1. 시스템 아키텍처

### 전체 구성도

```
┌─────────────────────────────────────────────────────────────────┐
│                        Canvas (React SPA)                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐│
│  │  NL2SQL  │ │  OLAP    │ │ OLAP     │ │  온톨로지│ │  케이스││
│  │  Schema  │ │ Pivot    │ │ Studio   │ │  그래프  │ │  관리  ││
│  │  Canvas  │ │ (Vision) │ │ (Pivot)  │ │ (Cytosc.)│ │        ││
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └───┬────┘│
│       │            │            │            │           │      │
└───────┼────────────┼────────────┼────────────┼───────────┼──────┘
        │            │            │            │           │
  ┌─────▼─────┐┌─────▼─────┐┌────▼──────┐┌───▼─────┐┌───▼─────┐
  │  Oracle   ││  Vision   ││OLAP Studio││ Synapse ││  Core   │
  │  :9004    ││  :9100    ││  :9005    ││  :9003  ││  :9002  │
  │           ││           ││           ││         ││         │
  │ NL2SQL    ││ OLAP피벗  ││ 스타스키마 ││ 온톨로지││ BPM     │
  │ ReAct+HIL ││ What-if   ││ 큐브관리  ││ 그래프  ││ 인증    │
  │ 피드백    ││ 인과분석  ││ ETL/리니지││ DMN엔진 ││ 이벤트  │
  │ LLM캐시  ││ RCA       ││ Airflow   ││ 관계추론││ 케이스  │
  │           ││ 캘린더    ││ AI큐브    ││ 마이닝  ││ 감시    │
  │           ││ 시나리오  ││ NL2SQL    ││ 스키마  ││         │
  └─────┬─────┘└─────┬─────┘└────┬──────┘└───┬─────┘└───┬─────┘
        │            │           │            │           │
  ┌─────▼─────┐      │     ┌────▼──────┐┌───▼──────────▼─────┐
  │  Weaver   │      │     │           ││                     │
  │  :9001    │      │     │ PostgreSQL││      Neo4j          │
  │           │      │     │  :15432   ││      :17687         │
  │ 데이터    │      │     │           ││                     │
  │ 패브릭    │      │     │ core      ││ 온톨로지 5계층      │
  │ 메타      │      │     │ synapse   ││ 리니지 그래프       │
  │ 카탈로그  │      │     │ vision    ││ BehaviorModel       │
  │ 인트로    │      │     │ weaver    ││ 메타데이터 그래프   │
  │ 스펙션    │      │     │ oracle    ││                     │
  │ 자동      │      │     │ olap      ││                     │
  │ 바인딩    │      │     │           ││                     │
  └─────┬─────┘      │     └────┬──────┘└─────────────────────┘
        │            │          │
        └────────────┼──────────┘
                     │
               ┌─────▼──────────┐
               │     Redis      │
               │     :16379     │
               │                │
               │ Streams        │
               │ (이벤트 버스)  │
               │ 캐싱           │
               │ (Insight/LLM)  │
               │ 시나리오       │
               │ 저장소         │
               └────────────────┘
```

### 포트 매핑 (컨테이너 → 호스트)

| 서비스 | 내부 포트 | 외부 포트 | 비고 |
|--------|-----------|-----------|------|
| Canvas | 5173 | 5174 | React SPA (Vite dev server) |
| Core | 8002 | 9002 | BPM + 인증 |
| Weaver | 8001 | 9001 | 데이터 패브릭 |
| Synapse | 8003 | 9003 | 온톨로지 |
| Oracle | 8004 | 9004 | NL2SQL |
| Vision | 8000 | 9100 | OLAP + What-if |
| OLAP Studio | 8000 | 9005 | 스타 스키마 + 큐브 (신규) |
| PostgreSQL | 5432 | 15432 | 관계형 DB |
| Neo4j | 7687 | 17687 | 그래프 DB |
| Redis | 6379 | 16379 | 캐시 + 이벤트 버스 |

---

## 2. 서비스별 역할

### 2.1 Core (port 9002)

**담당 질문**: "사용자는 누구이고, 어떤 권한이 있으며, 비즈니스 프로세스는 어떻게 흘러가는가?"

- **BPM 오케스트레이션**: ProcessDefinition -> ProcessInstance -> WorkItem 3계층 구조
- **JWT 인증/인가**: Access 토큰 15분 + Refresh 토큰 7일 (HS256)
- **멀티테넌트 관리**: Tenant -> User -> Role 계층, X-Tenant-Id 헤더 기반 격리
- **케이스 라이프사이클**: Case -> CaseActivity 추적, 상태 전이 관리
- **이벤트 소싱**: EventOutbox 테이블 + Relay Worker를 통한 Redis Streams 발행
- **실시간 감시**: WatchRule -> WatchAlert, 조건 기반 알림 트리거

### 결정 사항

- 이벤트 소싱에 Transactional Outbox 패턴을 채택한 이유: DB 트랜잭션과 이벤트 발행의 원자성 보장
- JWT HS256을 선택한 이유: 마이크로서비스 간 공유 시크릿 기반으로 단순성 확보 (RS256은 키 관리 복잡도 대비 이점 부족)

---

### 2.2 Synapse (port 9003)

**담당 질문**: "비즈니스 개념은 어떻게 연결되어 있고, 데이터의 의미는 무엇인가?"

- **5계층 온톨로지**: KPI / Driver / Measure / Process / Resource 계층 구조
- **Neo4j 그래프 검색**: 키워드 + 벡터 유사도 하이브리드 검색
- **프로세스 마이닝**: 이벤트 로그에서 프로세스 발견 및 적합도 분석
- **스키마 편집**: 테이블/컬럼 설명 관리 + 임베딩 생성
- **스키마 네비게이션**: FK 기반 관련 테이블 탐색, 휴리스틱 스코어링
- **DMN 규칙 엔진**: 결정 테이블 기반 비즈니스 규칙 평가 (FIRST/COLLECT/PRIORITY 정책)
- **관계 추론 엔진**: LLM 기반 시맨틱 추론 + 레이어 규칙 폴백
- **BehaviorModel 관리**: OntologyBehavior:Model 멀티레이블 + READS_FIELD/PREDICTS_FIELD 링크
- **메타데이터 그래프**: DataSource -> Schema -> Table -> Column 계층 (Neo4j)

### 온톨로지 5계층 관계 구조

```
KPI Layer:      OEE, Throughput Rate, Defect Rate, Downtime
  ^ DERIVED_FROM
Driver Layer:   환율변동, 수요변동, 유가변동 (인과 분석 자동 생성)
  ^ CAUSES / INFLUENCES
Measure Layer:  Availability, Performance, Quality, Cycle Time
  ^ OBSERVED_IN
Process Layer:  Assembly, Inspection, Packaging, Maintenance
  ^ USES / SUPPORTS
Resource Layer: Machines, Robots, Operators, Materials, Sensors
```

### 관계 속성

| 속성 | 타입 | 설명 |
|------|------|------|
| weight | float (0.0~1.0) | 관계 강도 |
| lag | int (일) | 시간 지연 |
| confidence | float (0.0~1.0) | 신뢰도 |
| method | string | 도출 방법 (granger, pearson, llm 등) |
| direction | string | 방향 (positive, negative, unknown) |

---

### 2.3 Weaver (port 9001)

**담당 질문**: "실제 데이터는 어디에 있고, 어떤 구조를 갖고 있는가?"

- **데이터 패브릭**: 이기종 데이터소스 통합 레이어
- **메타데이터 카탈로그**: 테이블/컬럼 메타데이터 + 비즈니스 용어 글로서리
- **스키마 인트로스펙션**: 데이터소스 연결 후 자동 스키마 탐지
- **Insight 잡 스토어**: Redis 캐시 기반 비동기 분석 잡 관리
- **자동 데이터소스 바인딩**: 2단계 매칭 (이름 정확/부분 -> LLM 시맨틱)
- **한국어-영어 도메인 용어 매핑**: 탁도->turbidity, 잔류염소->chlorine 등

### 결정 사항

- Insight 잡에 Redis를 사용한 이유: 별도 잡 큐(Celery 등) 도입 없이 경량 비동기 처리
- 자동 바인딩을 2단계로 분리한 이유: LLM 호출 비용 최소화 (Phase 1 이름 매칭으로 대부분 해결)

---

### 2.4 Oracle (port 9004)

**담당 질문**: "자연어 질문을 어떻게 정확한 SQL로 변환하는가?"

- **NL2SQL 엔진**: ReAct 패턴 + Human-in-the-Loop (HIL) 워크플로
- **SQLGlot AST 검증**: 생성된 SQL의 구문/의미 검증
- **품질 게이트**: SQL 실행 전 다단계 검증 파이프라인
- **Value Mapping + Enum Cache**: DB 실제 값과 자연어 표현 매핑
- **피드백 분석**: 사용자 피드백 기반 프롬프트 개선
- **LLM 시맨틱 캐시**: SHA-256 해시 정확 매칭 + 코사인 유사도 시맨틱 매칭 (2단계)

### NL2SQL 파이프라인

```
사용자 질문
    |
    v
[Sub-schema Context 선택] -- Weaver 메타데이터 참조
    |
    v
[LLM 시맨틱 캐시 조회] -- 히트 시 즉시 반환
    |
    v
[ReAct Loop]
    |-- Thought: 질문 분석
    |-- Action: SQL 생성
    |-- Observation: SQLGlot AST 검증
    |-- (반복)
    v
[품질 게이트] -- Value Mapping, Enum 검증
    |
    v
[HIL 확인] -- 사용자 수정 가능
    |
    v
[SQL 실행 + 결과 반환]
```

---

### 2.5 Vision (port 9100)

**담당 질문**: "데이터에서 어떤 인과관계가 있고, 변수를 바꾸면 무슨 일이 일어나는가?"

- **OLAP 피벗 분석**: 온톨로지 기반 다차원 분석
- **What-if DAG 시뮬레이션**: 변수 개입(intervention) 시 전파 효과 계산
- **인과 분석**: Granger 인과성 + VAR 모델 (statsmodels)
- **근본 원인 분석 (RCA)**: KPI 이상 시 역방향 추적
- **What-if 시뮬레이션 위자드**: 9단계 파이프라인 (탐색 -> 학습 -> 시뮬레이션 -> 비교)
- **비즈니스 캘린더**: 공휴일 DB + 영업일 필터링
- **시나리오 저장/비교/재실행**: Redis 기반 30일 TTL

---

### 2.6 OLAP Studio (port 9005) -- 신규

**담당 질문**: "데이터 웨어하우스를 어떻게 모델링하고, ETL은 어떻게 관리하는가?"

- **스타 스키마 모델 관리**: Dimension / Fact / Join 정의
- **큐브 관리**: OLAP 큐브 CRUD + Mondrian XML import/export
- **드래그앤드롭 피벗 분석**: 큐브 기반 대화형 피벗
- **ETL 파이프라인**: CRUD + 실행 + 이력 관리
- **Airflow 연동**: DAG 생성/트리거/상태 조회
- **데이터 리니지**: PostgreSQL + Neo4j 동기화, 소스->타겟 추적
- **AI 큐브/DDL 생성**: OpenAI 기반 자동 모델링
- **탐색형 NL2SQL**: 4단계 파이프라인 (큐브 컨텍스트 기반)
- **Outbox 이벤트 발행**: Redis Relay Worker를 통한 비동기 이벤트

---

## 3. 데이터 흐름

### 3.1 이벤트 버스 (Redis Streams)

```
[Core EventOutbox] ──publish──> Redis Stream: axiom:core:events
                                    |
                                    +──> Synapse (온톨로지 인제스트)
                                    +──> Vision (감시 알림)

[Synapse Outbox]   ──publish──> Redis Stream: axiom:synapse:events
                                    |
                                    +──> Weaver (메타데이터 동기화)

[OLAP Studio Outbox] ──publish──> Redis Stream: axiom:olap-studio:events
                                    |
                                    +──> Synapse (리니지 그래프 반영)
                                    +──> Vision (큐브 참조 메타데이터)
                                    +──> Weaver (카탈로그 동기화)
```

### Transactional Outbox 패턴

```
[서비스 로직]
    |
    v
[DB 트랜잭션] ── INSERT 비즈니스 데이터
    |               + INSERT event_outbox 레코드
    v               (단일 트랜잭션)
[COMMIT]
    |
    v
[Relay Worker] ── outbox 테이블 폴링
    |               published=false 레코드 조회
    v
[Redis Stream 발행] ── 성공 시 published=true 업데이트
```

### 3.2 인증 흐름

```
Client --> [JWT 토큰] --> Gateway / TenantMiddleware
    |
    +-- scope.state.tenant_id    (테넌트 식별)
    +-- scope.state.user_id      (사용자 식별)
    +-- scope.state.project_id   (OLAP Studio 프로젝트 스코프)
    +-- scope.state.roles        (역할 목록)
```

### 3.3 NL2SQL 실행 흐름

```
Canvas 채팅 UI
    | POST /api/oracle/ask
    v
Oracle API (레이트 리밋 -> 인증 -> 검증)
    | Sub-schema 선택 (Weaver 메타데이터)
    v
LLM 시맨틱 캐시 조회
    | 미스 시 ReAct Loop 진입
    v
SQLGlot AST 검증 + 품질 게이트
    | Value Mapping 적용
    v
HIL 확인 (사용자 수정 가능)
    |
    v
SQL 실행 -> 결과 반환 (Canvas)
```

### 3.4 OLAP Studio 피벗 실행 흐름

```
Canvas PivotBuilder
    | POST /api/gateway/olap/pivot/execute
    v
OLAP Studio API (rate limit -> auth -> capability check)
    | generate_pivot_sql(query) -> (sql, params)
    v
asyncpg execute_query(sql, params)
    |
    v
PostgreSQL DW 스키마 (olap.* tables)
    |
    v
QueryResult -> PivotResultGrid (Canvas)
```

---

## 4. 보안 아키텍처

### 인증

| 항목 | 설명 |
|------|------|
| 알고리즘 | HS256 (대칭키) |
| Access 토큰 | 15분 TTL |
| Refresh 토큰 | 7일 TTL |
| Gateway 모드 | X-Tenant-Id 헤더 기반 |
| 직접 접근 | JWT 토큰 검증 |

### 권한 (RBAC)

| 역할 | 권한 범위 |
|------|-----------|
| admin | 모든 기능 (시스템 설정 포함) |
| manager | 편집 + 실행 + 팀 관리 |
| engineer | 편집 + 실행 (데이터 모델링) |
| analyst | 조회 + 피벗 + NL2SQL |
| attorney | 케이스 관리 + 문서 접근 |
| staff | 기본 업무 기능 |
| viewer | 읽기 전용 |

### 데이터 격리

- **PostgreSQL**: 모든 쿼리에 `tenant_id` + `project_id` WHERE 조건 강제
- **Neo4j**: Cypher 쿼리에 `$tid` 파라미터 바인딩
- **Redis**: 키에 테넌트 네임스페이스 접두사 (예: `axiom:{tenant_id}:...`)

### 입력 검증

| 영역 | 방어 기법 |
|------|-----------|
| SQL | `$N` 파라미터 바인딩 (asyncpg), 연산자/집계 화이트리스트 |
| Cypher | 파라미터 바인딩, depth 범위 강제 (1~10) |
| XML | XXE 방지 (`resolve_entities=False`) |
| DMN | `ast.literal_eval` 사용 (`eval` 금지) |
| LLM | 프롬프트 입력 길이 제한 + 출력 구조 검증 |

### 레이트 리밋

| 서비스 | 엔드포인트 | 제한 |
|--------|-----------|------|
| Oracle | /ask | 30/min |
| Oracle | /react | 10/min |
| OLAP Studio | AI 생성 | 10/min |
| OLAP Studio | NL2SQL | 20/min |
| OLAP Studio | 피벗 실행 | 60/min |
| OLAP Studio | Airflow | 5/min |
| Synapse | 관계 추론 | 15/min |

---

## 5. PostgreSQL 스키마 구조

| 스키마 | 서비스 | 주요 테이블 |
|--------|--------|------------|
| core | Core | tenants, users, cases, process_definitions, process_instances, work_items, watch_rules, watch_alerts, event_outbox |
| synapse | Synapse | event_logs, schema_edit_history, schema_descriptions |
| vision | Vision | holidays |
| weaver | Weaver | datasources, insight_jobs, insight_results, metadata_catalog |
| oracle | Oracle | feedback, query_logs, semantic_cache |
| olap | OLAP Studio | data_sources, models, dimensions, facts, joins, cubes, cube_dimensions, cube_measures, mondrian_documents, etl_pipelines, etl_runs, etl_run_steps, pivot_views, query_history, lineage_entities, lineage_edges, ai_generations, outbox_events |
| dw | OLAP Studio | (데이터 웨어하우스 -- ETL에 의해 동적 생성) |

### Neo4j 노드 레이블

| 레이블 | 용도 |
|--------|------|
| :KPI | KPI 계층 엔티티 |
| :Driver | 드라이버 계층 엔티티 |
| :Measure | 측정 계층 엔티티 |
| :Process | 프로세스 계층 엔티티 |
| :Resource | 자원 계층 엔티티 |
| :OntologyBehavior:Model | 행동 모델 (멀티레이블) |
| :DataSource | 데이터소스 메타데이터 |
| :Schema | 스키마 메타데이터 |
| :Table | 테이블 메타데이터 |
| :Column | 컬럼 메타데이터 |
| :LineageEntity | 리니지 엔티티 |

### Neo4j 관계 타입

| 관계 | 방향 | 설명 |
|------|------|------|
| DERIVED_FROM | KPI -> Measure | KPI가 측정값에서 도출됨 |
| OBSERVED_IN | Measure -> Process | 측정값이 프로세스에서 관찰됨 |
| USES | Process -> Resource | 프로세스가 자원을 사용함 |
| SUPPORTS | Resource -> Process | 자원이 프로세스를 지원함 |
| CAUSES | Driver -> KPI | 드라이버가 KPI에 영향 (강한 인과) |
| INFLUENCES | Driver -> KPI | 드라이버가 KPI에 영향 (약한 상관) |
| PRECEDES | Process -> Process | 프로세스 순서 관계 |
| RELATED_TO | any -> any | 일반 연관 관계 |
| READS_FIELD | Model -> Column | 모델이 필드를 읽음 |
| PREDICTS_FIELD | Model -> Column | 모델이 필드를 예측함 |
| HAS_SCHEMA | DataSource -> Schema | 데이터소스의 스키마 |
| HAS_TABLE | Schema -> Table | 스키마의 테이블 |
| HAS_COLUMN | Table -> Column | 테이블의 컬럼 |

---

## 6. 기술 스택 요약

### 프론트엔드

| 기술 | 버전 | 용도 |
|------|------|------|
| React | 19.2 | UI 프레임워크 |
| TypeScript | 5.9 | 타입 안전성 |
| Vite | 7.3 | 빌드 도구 |
| Tailwind CSS | 4.2 | 유틸리티 CSS |
| shadcn/ui (Radix) | - | UI 컴포넌트 |
| Zustand | 5.0 | 상태 관리 |
| TanStack Query | 5.90 | 서버 상태 동기화 |
| TanStack Table | 8.21 | 테이블 렌더링 |
| Cytoscape | - | 그래프 시각화 (온톨로지) |
| Konva | - | 캔버스 렌더링 (프로세스 디자이너) |
| Recharts | - | 차트 시각화 |
| Monaco Editor | - | 코드/SQL 에디터 |
| Mermaid.js | - | ERD 다이어그램 |
| Yjs + y-websocket | - | CRDT 실시간 협업 |
| i18next | - | 국제화 (ko/en) |

### 백엔드

| 기술 | 버전 | 용도 |
|------|------|------|
| Python | 3.12 | 런타임 |
| FastAPI | - | REST API 프레임워크 |
| SQLAlchemy | - | ORM (PostgreSQL) |
| asyncpg | - | 비동기 PostgreSQL 드라이버 |
| neo4j-driver | - | Neo4j 드라이버 |
| LangChain | - | LLM 오케스트레이션 |
| OpenAI GPT-4o | - | 프로덕션 LLM |
| SQLGlot | - | SQL AST 파싱/검증 |
| statsmodels | - | 인과 분석 (Granger/VAR) |
| scikit-learn | - | 회귀 모델 (What-if) |
| pandas | - | 데이터 처리 |

---

## 7. 관련 문서

| 문서 | 경로 | 내용 |
|------|------|------|
| ADR-033 통합 스키마 네비게이션 | `docs/text2sql-unified-spec.md` | G1-G8 구현 포함 |
| G1-G8 갭 구현 계획서 | `docs/schema-canvas-gap-implementation-plan.md` | 4 Phase 상세 계획 |
| OLAP Studio 통합 설계서 | `docs/olap-studio-integration-plan.md` | 8 Phase 마이그레이션 |
| KAIR 이식 기능 가이드 | `docs/kair-features-guide.md` | 7개 이식 기능 사용 안내 |
| 시맨틱 레이어 아키텍처 | `docs/architecture-semantic-layer.md` | 시맨틱 레이어 설계 철학 |
| 서비스 엔드포인트 SSOT | `docs/service-endpoints-ssot.md` | 전체 API 엔드포인트 목록 |

---

## 8. 재평가 조건

이 문서는 다음 상황에서 업데이트가 필요하다:

- 새 마이크로서비스가 추가되거나 기존 서비스가 분할/병합될 때
- 데이터베이스 스키마에 새 테이블이 추가될 때
- 인증/인가 모델이 변경될 때
- 서비스 간 통신 패턴이 변경될 때 (예: gRPC 도입)
- Neo4j 노드 레이블 또는 관계 타입이 추가될 때

<!-- 마지막 업데이트: 2026-03-22 -->
<!-- 근거: CLAUDE.md v4.0, 코드베이스 검증 기반 -->
