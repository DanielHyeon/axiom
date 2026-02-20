# Neo4j 전체 스키마

> **최종 수정일**: 2026-02-20
> **상태**: Active
> **변경 이력**: 2026-02-20 `org_id` → `tenant_id` 통일, `embedding` → `vector` 속성명 통일, K-AIR 관계명 Oracle/Weaver v2 정합

## 이 문서가 답하는 질문

- Neo4j에 저장되는 전체 노드/관계 스키마는?
- K-AIR 이식 스키마와 4계층 온톨로지 확장 스키마의 구분은?
- 각 노드의 속성과 타입은?
- 인덱스/제약조건 전체 목록은?

<!-- affects: backend, api, frontend -->
<!-- requires-update: 03_backend/neo4j-bootstrap.md, 01_architecture/process-mining-engine.md -->

---

## 1. 스키마 개요

Synapse의 Neo4j 스키마는 두 영역으로 구성된다:

```
┌────────────────────────────────────────────────────┐
│  K-AIR 이식 스키마 (Schema Metadata)                 │
│  Table, Column, Query, ValueMapping                 │
│  → Oracle Text2SQL 지원용                           │
├────────────────────────────────────────────────────┤
│  4계층 온톨로지 스키마 (Ontology)                    │
│  Resource, Process, Measure, KPI                    │
│  + 보조: Activity, Decision, Snapshot, Target, etc  │
│  → 비즈니스 프로세스 도메인 지식그래프               │
├────────────────────────────────────────────────────┤
│  Process Mining 확장 스키마 (EventStorming + Mining) │
│  BusinessEvent, BusinessAction, BusinessRule        │
│  EventLog, ProcessInstance                          │
│  + 시간축 속성, 이벤트 로그 바인딩                   │
│  → Process Mining Engine 지원                       │
├────────────────────────────────────────────────────┤
│  시스템 노드                                         │
│  SchemaVersion                                      │
│  → 스키마 버전 추적                                  │
└────────────────────────────────────────────────────┘
```

---

## 2. 노드 스키마 상세

### 2.1 K-AIR 이식 노드

#### :Table

```
(:Table {
  name: STRING,              // UNIQUE, NOT NULL - 테이블명
  description: STRING,       // 자연어 설명
  vector: LIST<FLOAT>,       // 1536차원 임베딩 벡터 (Oracle 소유)
  row_count: INTEGER,        // 행 수 (참고용)
  sample_data: STRING,       // 샘플 데이터 JSON
  created_at: DATETIME,
  updated_at: DATETIME
})
```

#### :Column

```
(:Column {
  name: STRING,              // NOT NULL - 컬럼명
  table_name: STRING,        // NOT NULL - 소속 테이블명
  // UNIQUE 제약: (table_name, name)
  data_type: STRING,         // 데이터 타입 (varchar, integer, numeric 등)
  description: STRING,       // 자연어 설명
  vector: LIST<FLOAT>,       // 1536차원 임베딩 벡터 (Oracle 소유)
  nullable: BOOLEAN,         // NULL 허용 여부
  is_pk: BOOLEAN,            // Primary Key 여부
  is_fk: BOOLEAN,            // Foreign Key 여부
  created_at: DATETIME,
  updated_at: DATETIME
})
```

#### :Query

```
(:Query {
  question: STRING,          // UNIQUE - 자연어 질문
  sql: STRING,               // 대응 SQL
  description: STRING,       // 쿼리 설명
  vector: LIST<FLOAT>,       // 1536차원 임베딩 벡터 (Oracle 소유)
  verified: BOOLEAN,         // 검증 여부
  created_at: DATETIME,
  updated_at: DATETIME
})
```

#### :ValueMapping

```
(:ValueMapping {
  column_name: STRING,       // 대상 컬럼명
  table_name: STRING,        // 대상 테이블명
  original_value: STRING,    // 원본 값 (예: "active")
  mapped_value: STRING,      // 매핑 값 (예: "활성")
  created_at: DATETIME
})
```

---

### 2.2 4계층 온톨로지 노드

#### :Resource (공통 속성)

모든 Resource 하위 유형은 다음 공통 속성을 갖는다:

```
(:Resource {
  id: STRING,                // UNIQUE - UUID
  case_id: STRING,           // NOT NULL - 프로젝트 ID
  tenant_id: STRING,          // NOT NULL - 테넌트 ID (Core SSOT)
  type: STRING,              // 하위 유형 (Company, Asset, Employee 등)
  name: STRING,              // 이름
  description: STRING,       // 설명
  source: STRING,            // manual | extracted | ingested
  confidence: FLOAT,         // 0.0-1.0
  verified: BOOLEAN,         // HITL 확인 여부
  created_at: DATETIME,
  updated_at: DATETIME
})
```

#### :Company:Resource

```
(:Company:Resource {
  ...공통 속성,
  registration_no: STRING,   // 사업자등록번호
  representative: STRING,    // 대표자명
  industry: STRING,          // 업종
  address: STRING,           // 주소
  employee_count: INTEGER    // 종업원 수
})
```

#### :Asset:Resource

```
(:Asset:Resource {
  ...공통 속성,
  asset_type: STRING,        // RealEstate, Equipment, IP, Inventory
  market_value: FLOAT,       // 시가
  book_value: FLOAT,         // 장부 가액
  appraised_date: DATE,      // 감정 일자
  appraiser: STRING,         // 감정인
  location: STRING           // 소재지
})
```

#### :Contract:Resource

```
(:Contract:Resource {
  ...공통 속성,
  counterparty: STRING,      // 거래 상대방
  contract_value: FLOAT,     // 계약 금액
  contract_type: STRING,     // supply, service, partnership
  start_date: DATE,          // 계약 시작일
  end_date: DATE             // 계약 종료일
})
```

#### :Employee:Resource

```
(:Employee:Resource {
  ...공통 속성,
  position: STRING,          // 직위
  department: STRING,        // 부서
  annual_salary: FLOAT,      // 연봉
  employment_start: DATE     // 입사일
})
```

#### :Financial:Resource

```
(:Financial:Resource {
  ...공통 속성,
  fiscal_year: INTEGER,      // 회계연도
  revenue: FLOAT,            // 매출액
  ebitda: FLOAT,             // EBITDA
  net_income: FLOAT,         // 순이익
  total_debt: FLOAT,         // 총 부채
  total_assets: FLOAT,       // 총 자산
  cash: FLOAT                // 현금성 자산
})
```

#### :CashReserve:Resource

```
(:CashReserve:Resource {
  ...공통 속성,
  account_type: STRING,      // 계좌 유형
  balance: FLOAT,            // 잔액
  bank: STRING,              // 은행명
  as_of_date: DATE           // 기준일
})
```

#### :Inventory:Resource

```
(:Inventory:Resource {
  ...공통 속성,
  inventory_type: STRING,    // raw_material, finished_goods, wip
  quantity: FLOAT,           // 수량
  unit_cost: FLOAT,          // 단가
  total_value: FLOAT,        // 총 가치
  warehouse: STRING          // 보관 위치
})
```

---

#### :Process (공통 속성)

```
(:Process {
  id: STRING,                // UNIQUE
  case_id: STRING,           // NOT NULL
  tenant_id: STRING,         // NOT NULL - 테넌트 ID (Core SSOT)
  type: STRING,              // DataCollection, ProcessAnalysis 등
  name: STRING,
  stage: STRING,             // started, in_progress, completed, cancelled
  start_date: DATE,
  end_date: DATE,
  source: STRING,
  confidence: FLOAT,
  verified: BOOLEAN,
  created_at: DATETIME,
  updated_at: DATETIME
})
```

Process 하위 유형별 추가 속성은 `01_architecture/ontology-4layer.md`를 참조한다.

#### :Activity

```
(:Activity {
  id: STRING,
  process_id: STRING,        // 소속 Process 노드 ID
  name: STRING,
  stage: STRING,
  responsible_party: STRING,
  deadline: DATE,
  completed: BOOLEAN
})
```

#### :Decision

```
(:Decision {
  id: STRING,
  process_id: STRING,
  type: STRING,              // approval, review, escalation
  date: DATE,
  department: STRING,
  decision_maker: STRING,
  summary: STRING            // 결정 내용 요약
})
```

---

#### :Measure (공통 속성)

```
(:Measure {
  id: STRING,                // UNIQUE
  case_id: STRING,           // NOT NULL
  tenant_id: STRING,         // NOT NULL - 테넌트 ID (Core SSOT)
  type: STRING,              // Revenue, Cost, OperatingProfit 등
  name: STRING,
  amount: FLOAT,             // 금액
  currency: STRING,          // KRW, USD
  formula: STRING,           // 산출 공식
  data_type: STRING,         // currency, count, percentage, duration
  as_of_date: DATE,
  source: STRING,
  confidence: FLOAT,
  created_at: DATETIME,
  updated_at: DATETIME
})
```

#### :MeasureSnapshot

```
(:MeasureSnapshot {
  id: STRING,
  measure_id: STRING,
  period: STRING,            // "2024-Q1", "2024-06"
  value: FLOAT,
  recorded_at: DATETIME
})
```

---

#### :KPI (공통 속성)

```
(:KPI {
  id: STRING,                // UNIQUE
  case_id: STRING,           // NOT NULL
  tenant_id: STRING,         // NOT NULL - 테넌트 ID (Core SSOT)
  type: STRING,              // ProcessEfficiency, CostReduction, ROI 등
  name: STRING,
  target: FLOAT,             // 목표값
  actual: FLOAT,             // 실적값
  formula: STRING,           // 산출 공식
  reporting_period: STRING,  // "2024-Q2"
  source: STRING,
  created_at: DATETIME,
  updated_at: DATETIME
})
```

#### :KPITarget

```
(:KPITarget {
  id: STRING,
  kpi_id: STRING,
  green_threshold: FLOAT,    // 양호 기준
  yellow_threshold: FLOAT,   // 주의 기준
  red_threshold: FLOAT       // 위험 기준
})
```

#### :KPIHistory

```
(:KPIHistory {
  id: STRING,
  kpi_id: STRING,
  period: STRING,
  value: FLOAT,
  status: STRING,            // green, yellow, red
  recorded_at: DATETIME
})
```

---

### 2.3 Process Mining 확장 노드

#### :BusinessEvent:Process

EventStorming의 Domain Event를 표현하며, 시간축 속성과 이벤트 로그 바인딩 속성을 포함한다.

```
(:BusinessEvent:Process {
  id: STRING,                // UNIQUE - UUID
  case_id: STRING,           // NOT NULL
  tenant_id: STRING,         // NOT NULL - 테넌트 ID (Core SSOT)
  type: STRING,              // "BusinessEvent"
  name: STRING,              // 이벤트 이름 (예: "출하됨", "결제 완료됨")
  stage: STRING,             // pending, active, completed
  source: STRING,            // manual | extracted | ingested

  // ---- 시간축 속성 (Temporal Properties) ----
  timestamp: DATETIME,       // 이벤트 발생 시각 (설계 시 예시값, 실행 시 실제값)
  duration: FLOAT,           // 이벤트 소요시간 (초)
  sla_threshold: FLOAT,      // SLA 기준 시간 (초)
  expected_duration: FLOAT,  // 설계 시 예상 소요시간 (초)
  actual_avg_duration: FLOAT,// 실제 평균 소요시간 (이벤트 로그에서 계산)
  violation_rate: FLOAT,     // SLA 위반율 (0.0-1.0, 이벤트 로그에서 계산)

  // ---- 이벤트 로그 바인딩 속성 ----
  source_table: STRING,      // 바인딩된 DB 테이블 (예: "order_events")
  source_event: STRING,      // 테이블 내 이벤트 값 (예: "SHIPPED")
  timestamp_column: STRING,  // 타임스탬프 컬럼 (예: "event_time")
  case_id_column: STRING,    // 프로세스 인스턴스 식별 컬럼 (예: "order_id")
  filter_condition: STRING,  // 추가 필터 조건 (예: "status = 'ACTIVE'")

  confidence: FLOAT,
  verified: BOOLEAN,
  created_at: DATETIME,
  updated_at: DATETIME
})
```

#### :BusinessAction:Process

EventStorming의 Command를 표현한다. Actor가 트리거하는 의도적 행위이다.

```
(:BusinessAction:Process {
  id: STRING,                // UNIQUE
  case_id: STRING,           // NOT NULL
  tenant_id: STRING,         // NOT NULL - 테넌트 ID (Core SSOT)
  type: STRING,              // "BusinessAction"
  name: STRING,              // 액션 이름 (예: "출하 지시", "결제 요청")
  actor_id: STRING,          // 트리거하는 Actor(Resource) 노드 ID
  trigger_type: STRING,      // user_initiated, system_triggered, time_triggered
  stage: STRING,

  // ---- 시간축 속성 ----
  expected_duration: FLOAT,  // 예상 처리 시간 (초)
  actual_avg_duration: FLOAT,// 실제 평균 처리 시간

  source: STRING,
  confidence: FLOAT,
  verified: BOOLEAN,
  created_at: DATETIME,
  updated_at: DATETIME
})
```

#### :BusinessRule:Process

EventStorming의 Policy를 표현한다. Event에 반응하여 다음 Command를 트리거하는 자동화 규칙이다.

```
(:BusinessRule:Process {
  id: STRING,                // UNIQUE
  case_id: STRING,           // NOT NULL
  tenant_id: STRING,         // NOT NULL - 테넌트 ID (Core SSOT)
  type: STRING,              // "BusinessRule"
  name: STRING,              // 규칙 이름 (예: "배송 추적 시작", "재고 부족 알림")
  condition: STRING,         // 트리거 조건 (예: "event.type == 'SHIPPED'")
  action: STRING,            // 실행 액션 설명
  is_automated: BOOLEAN,     // 자동 실행 여부

  source: STRING,
  confidence: FLOAT,
  verified: BOOLEAN,
  created_at: DATETIME,
  updated_at: DATETIME
})
```

#### :EventLog

이벤트 로그 소스를 표현하는 노드이다. BusinessEvent가 BINDS_TO 관계로 연결된다.

```
(:EventLog {
  id: STRING,                // UNIQUE
  case_id: STRING,           // NOT NULL
  tenant_id: STRING,         // NOT NULL - 테넌트 ID (Core SSOT)
  name: STRING,              // 이벤트 로그 이름 (예: "주문 프로세스 2024년 로그")
  source_type: STRING,       // csv, xes, database, streaming
  source_config: STRING,     // JSON: 소스 연결 정보
  total_events: INTEGER,     // 전체 이벤트 수
  total_cases: INTEGER,      // 전체 케이스(프로세스 인스턴스) 수
  total_activities: INTEGER, // 고유 활동 수
  date_range_start: DATETIME,// 이벤트 시작 일시
  date_range_end: DATETIME,  // 이벤트 종료 일시
  created_at: DATETIME,
  updated_at: DATETIME
})
```

#### :ProcessInstance

개별 프로세스 실행 인스턴스를 표현한다. 이벤트 로그에서 case_id 기준으로 추출된다.

```
(:ProcessInstance {
  id: STRING,                // UNIQUE
  case_id: STRING,           // NOT NULL (Axiom case_id)
  tenant_id: STRING,         // NOT NULL - 테넌트 ID (Core SSOT)
  log_id: STRING,            // 소속 EventLog 노드 ID
  instance_case_id: STRING,  // 이벤트 로그 내 프로세스 인스턴스 식별자 (order_id 등)
  variant_id: STRING,        // 프로세스 변종 ID
  start_time: DATETIME,      // 인스턴스 시작 시각
  end_time: DATETIME,        // 인스턴스 종료 시각
  duration: FLOAT,           // 전체 소요시간 (초)
  activity_count: INTEGER,   // 활동 수
  is_conformant: BOOLEAN,    // 설계 모델 적합 여부
  created_at: DATETIME
})
```

---

### 2.4 시스템 노드

#### :SchemaVersion

```
(:SchemaVersion {
  service: STRING,           // "synapse"
  version: STRING,           // "2.0.0"
  updated_at: DATETIME
})
```

---

## 3. 관계 스키마 상세

### 3.1 K-AIR 이식 관계

| 관계 | 시작 노드 | 끝 노드 | 속성 |
|------|----------|---------|------|
| `FK_TO` | Column | Column | description |
| `HAS_COLUMN` | Table | Column | - |
| `USES_TABLE` | Query | Table | - |
| `MAPPED_VALUE` | ValueMapping | Column | - |

### 3.2 4계층 온톨로지 관계

| 관계 | 시작 노드 | 끝 노드 | 속성 |
|------|----------|---------|------|
| `PARTICIPATES_IN` | Resource | Process | role, since |
| `PRODUCES` | Process | Measure | calculation |
| `CONTRIBUTES_TO` | Resource/Measure | Measure/KPI | weight, formula, contribution_type |
| `DEPENDS_ON` | KPI | Measure | formula |
| `INFLUENCES` | Process | KPI | impact_type, strength |
| `HAS_ACTIVITY` | Process | Activity | - |
| `RESULTED_IN` | Process | Decision | - |
| `HAS_SNAPSHOT` | Measure | MeasureSnapshot | - |
| `HAS_TARGET` | KPI | KPITarget | - |
| `HAS_HISTORY` | KPI | KPIHistory | - |
| `OWNS` | Company | Asset | - |
| `HAS_CONTRACT_WITH` | Company | Contract | - |
| `SUPPLIES_TO` | Company | Company | - |

### 3.3 Process Mining 관계

| 관계 | 시작 노드 | 끝 노드 | 속성 |
|------|----------|---------|------|
| `TRIGGERS` | Resource/BusinessRule | BusinessAction | role |
| `PRODUCES` | BusinessAction | BusinessEvent | - |
| `ACTIVATES` | BusinessEvent | BusinessRule | - |
| `FOLLOWED_BY` | BusinessEvent | BusinessEvent | avg_duration, case_count, probability |
| `BINDS_TO` | BusinessEvent | EventLog | source_table, source_event, timestamp_column, case_id_column, filter_condition |
| `HAS_INSTANCE` | EventLog | ProcessInstance | - |
| `BELONGS_TO_VARIANT` | ProcessInstance | ProcessVariant | - |

---

## 4. 제약조건 전체 목록

| 이름 | 대상 | 유형 | 속성 |
|------|------|------|------|
| `table_name_unique` | Table | UNIQUE | name |
| `column_composite_unique` | Column | UNIQUE | (table_name, name) |
| `query_question_unique` | Query | UNIQUE | question |
| `resource_id_unique` | Resource | UNIQUE | id |
| `process_id_unique` | Process | UNIQUE | id |
| `measure_id_unique` | Measure | UNIQUE | id |
| `kpi_id_unique` | KPI | UNIQUE | id |
| `resource_case_id` | Resource | NOT NULL | case_id |
| `process_case_id` | Process | NOT NULL | case_id |
| `measure_case_id` | Measure | NOT NULL | case_id |
| `kpi_case_id` | KPI | NOT NULL | case_id |
| `event_log_id_unique` | EventLog | UNIQUE | id |
| `process_instance_id_unique` | ProcessInstance | UNIQUE | id |
| `event_log_case_id` | EventLog | NOT NULL | case_id |
| `process_instance_case_id` | ProcessInstance | NOT NULL | case_id |

---

## 5. 인덱스 전체 목록

| 이름 | 대상 | 유형 | 속성 |
|------|------|------|------|
| `table_vector` | Table | VECTOR (1536, cosine) | vector |
| `column_vector` | Column | VECTOR (1536, cosine) | vector |
| `query_vector` | Query | VECTOR (1536, cosine) | vector |
| `resource_case_type` | Resource | COMPOSITE | (case_id, type) |
| `process_case_type` | Process | COMPOSITE | (case_id, type) |
| `measure_case_type` | Measure | COMPOSITE | (case_id, type) |
| `kpi_case_type` | KPI | COMPOSITE | (case_id, type) |
| `resource_source` | Resource | SINGLE | source |
| `resource_verified` | Resource | COMPOSITE | (case_id, verified) |
| `ontology_fulltext` | Resource/Process/Measure/KPI | FULLTEXT | (name, description) |
| `schema_fulltext` | Table/Column | FULLTEXT | (name, description) |
| `event_log_case` | EventLog | COMPOSITE | (case_id, source_type) |
| `process_instance_log` | ProcessInstance | COMPOSITE | (log_id, instance_case_id) |
| `business_event_temporal` | BusinessEvent | COMPOSITE | (case_id, timestamp) |
| `business_event_source` | BusinessEvent | COMPOSITE | (source_table, source_event) |

---

## 근거 문서

- `01_architecture/ontology-4layer.md` (4계층 온톨로지 설계)
- `01_architecture/process-mining-engine.md` (Process Mining Engine 아키텍처)
- `03_backend/neo4j-bootstrap.md` (초기화 구현)
- `06_data/vector-indexes.md` (벡터 인덱스 상세)
- `06_data/event-log-schema.md` (이벤트 로그 PostgreSQL 스키마)
- ADR-005: pm4py Process Mining 선택 (`99_decisions/ADR-005-pm4py-process-mining.md`)
- K-AIR `app/core/neo4j_bootstrap.py` 원본
- `(Core) 06_data/database-operations.md` (Neo4j 백업/복구, 유지보수, DR 전략)
