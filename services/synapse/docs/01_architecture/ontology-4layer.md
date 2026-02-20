# 4계층 온톨로지 아키텍처 상세

## 이 문서가 답하는 질문

- 4계층 온톨로지의 각 계층은 무엇을 표현하는가?
- 비즈니스 프로세스 인텔리전스에서 각 계층의 노드는 구체적으로 어떤 것들인가?
- 계층 간 관계는 어떻게 정의되는가?
- 온톨로지 모델을 Neo4j에서 어떻게 구현하는가?

<!-- affects: backend, data, llm, api -->
<!-- requires-update: 06_data/neo4j-schema.md, 06_data/ontology-model.md, 01_architecture/process-mining-engine.md -->

---

## 1. 설계 배경

### 1.1 왜 4계층인가?

비즈니스 프로세스 데이터는 본질적으로 계층적 구조를 가진다:

1. **물리적 자원**이 존재하고 (기업, 자산, 인력, 계약)
2. 이 자원들이 **비즈니스 프로세스**에 참여하며 (데이터 수집, 프로세스 분석, 최적화, 실행)
3. 프로세스 실행 과정에서 **정량적 지표**가 산출되고 (매출, 비용, 처리량)
4. 이 지표들이 **전략적 성과**를 결정한다 (프로세스 효율성, ROI)

이 4단계를 명시적으로 분리함으로써:
- **역방향 추적**: "효율성이 낮은 이유"를 KPI → Measure → Process → Resource 순으로 역추적
- **영향도 분석**: "리소스를 변경하면 어떤 KPI가 변하는가"를 순방향으로 예측
- **데이터 완전성 검증**: 각 계층의 노드가 상위/하위 관계를 갖는지 검증

### 1.2 K-AIR 온톨로지와의 차이

| 항목 | K-AIR (범용 설계) | Axiom (비즈니스 프로세스 인텔리전스) |
|------|---------------|------------------|
| Resource | 설비, 센서, 인력 | Company, Asset, Contract, Employee |
| Process | 설비 점검, 운영 | DataCollection, ProcessAnalysis, Optimization |
| Measure | 수율, 처리량 | Revenue, Cost, OperatingProfit, Throughput |
| KPI | 설비효율, 가동률 | ProcessEfficiency, CostReduction, ROI |

구조는 동일하되, 도메인 개체가 완전히 다르다. K-AIR에서는 설계만 존재하고 구현되지 않았으므로 (0%), Axiom에서 처음 구현한다.

### 1.3 EventStorming 개념과 온톨로지 매핑

EventStorming은 도메인 이벤트를 중심으로 비즈니스 프로세스를 모델링하는 기법이다. EventStorming의 각 구성요소는 4계층 온톨로지에 자연스럽게 매핑된다.

| EventStorming 개념 | 색상 | 온톨로지 계층 | 매핑 노드 | 매핑 근거 |
|-------------------|------|------------|----------|----------|
| **Actor** | 작은 노란색 | Resource | `:Employee:Resource`, `:Company:Resource` | 프로세스를 트리거하는 행위자 = 자원 |
| **Aggregate** | 노란색 | Resource | `:Asset:Resource`, `:Inventory:Resource` | 비즈니스 상태를 보유하는 엔티티 = 자원 |
| **Command** | 파란색 | Process | `:BusinessAction:Process` | 의도적인 행위 = 프로세스 활동 |
| **Domain Event** | 주황색 | Process | `:BusinessEvent:Process` | 발생한 사실 = 프로세스 단계의 결과 |
| **Policy** | 보라색 | Process | `:BusinessRule:Process` | 자동화된 반응 = 비즈니스 규칙 |
| **Read Model** | 초록색 | Measure | `:Measure` (하위 유형) | 현재 상태의 조회 뷰 = 측정값 |
| **External System** | 분홍색 | Resource | `:Resource` (외부 시스템) | 외부 시스템 = 외부 자원 |
| **ContextBox** | - | Business Domain | 비즈니스 도메인 경계 (조직, 부서, 시스템 등) | 도메인 범위 구분 = 그래프 내 라벨/그룹 태그 |

#### EventStorming → 온톨로지 변환 흐름

```
EventStorming Canvas                    4계층 온톨로지

[Actor: 물류팀장]                  ──▶  (:Employee:Resource {name: "물류팀장"})
    │ triggers                              │ PARTICIPATES_IN
    ▼                                       ▼
[Command: 출하 지시]               ──▶  (:BusinessAction:Process {name: "출하 지시"})
    │ produces                              │ TRIGGERS
    ▼                                       ▼
[Event: 출하됨]                    ──▶  (:BusinessEvent:Process {name: "출하됨"})
    │ policy                                │ PRODUCES
    ▼                                       ▼
[Policy: 배송 추적 시작]           ──▶  (:BusinessRule:Process {name: "배송 추적 시작"})
                                            │ PRODUCES
                                            ▼
                                        (:Measure {name: "배송완료율", value: 95.2})
                                            │ CONTRIBUTES_TO
                                            ▼
                                        (:KPI {name: "물류 효율성"})
```

#### 시간축 속성 (Temporal Properties)

EventStorming의 Event 노드에 시간축 속성을 부여하여 Process Mining과 연결한다.

| 속성 | 타입 | 설명 |
|------|------|------|
| `timestamp` | DATETIME | 이벤트 발생 시각 |
| `duration` | FLOAT | 이벤트 소요시간 (초) |
| `sla_threshold` | FLOAT | SLA 기준 시간 (초) |
| `expected_duration` | FLOAT | 설계 시 예상 소요시간 (초) |
| `actual_avg_duration` | FLOAT | 실제 평균 소요시간 (초) - 이벤트 로그에서 계산 |
| `violation_rate` | FLOAT | SLA 위반율 (0.0-1.0) - 이벤트 로그에서 계산 |

---

## 2. 계층 상세

### 2.1 Resource 계층 (자원)

> "프로젝트에 존재하는 물리적/논리적 구성요소"

#### 노드 유형

| 노드 유형 | Neo4j 레이블 | 주요 속성 | 설명 |
|----------|------------|----------|------|
| **Company** | `:Company:Resource` | name, registration_no, representative, industry | 대상 조직/관련 기업 |
| **Asset** | `:Asset:Resource` | name, type, market_value, disposal_value, appraised_date | 자산 (부동산, 설비, 지적재산) |
| **Employee** | `:Employee:Resource` | name, position, department, salary | 종업원 |
| **CashReserve** | `:CashReserve:Resource` | account_type, balance, bank, as_of_date | 예금/현금성 자산 |
| **Inventory** | `:Inventory:Resource` | item_type, quantity, unit_cost, total_value | 재고 자산 |
| **Financial** | `:Financial:Resource` | fiscal_year, revenue, ebitda, net_income, total_debt | 재무 정보 |
| **Contract** | `:Contract:Resource` | counterparty, principal, terms, contract_type, priority | 계약 정보 |

#### 공통 속성

모든 Resource 노드는 다음 공통 속성을 갖는다:

```json
{
  "id": "uuid",
  "case_id": "uuid",
  "org_id": "uuid",
  "type": "Company | Asset | Employee | ...",
  "name": "string",
  "created_at": "datetime",
  "updated_at": "datetime",
  "source": "manual | extracted | ingested",
  "confidence": 0.0-1.0,
  "verified": true/false
}
```

#### EventStorming 매핑: Resource 계층

| EventStorming 개념 | 매핑 노드 유형 | 매핑 규칙 |
|-------------------|-------------|----------|
| **Actor** (행위자) | Employee, Company | 프로세스를 트리거하는 사람/조직 |
| **Aggregate** (집합) | Asset, Inventory, CashReserve | 비즈니스 상태를 가진 엔티티 |
| **External System** | Resource (외부 시스템) | 외부 데이터 소스 |

#### Cypher 예시: Resource 노드 생성

```cypher
CREATE (c:Company:Resource {
  id: randomUUID(),
  case_id: $case_id,
  org_id: $org_id,
  type: 'Company',
  name: 'XYZ 주식회사',
  registration_no: '123-45-67890',
  representative: '홍길동',
  industry: '제조업',
  source: 'ingested',
  confidence: 1.0,
  verified: true,
  created_at: datetime(),
  updated_at: datetime()
})
RETURN c
```

---

### 2.2 Process 계층 (프로세스)

> "자원이 참여하는 비즈니스 프로세스 단계"

#### 노드 유형

| 노드 유형 | Neo4j 레이블 | 주요 속성 | 설명 |
|----------|------------|----------|------|
| **DataCollection** | `:DataCollection:Process` | source_system, collection_date, data_volume | 데이터 수집 |
| **ProcessAnalysis** | `:ProcessAnalysis:Process` | analysis_type, start_date, findings_count | 프로세스 분석 |
| **Optimization** | `:Optimization:Process` | target_metric, improvement_rate, approval_status | 최적화 |
| **Execution** | `:Execution:Process` | start_date, end_date, execution_count | 실행 |
| **Review** | `:Review:Process` | review_date, reviewer, approval_rate | 검토/평가 |
| **Investigation** | `:Investigation:Process` | investigator, report_date, findings | 조사 절차 |

#### EventStorming 확장 노드

| 노드 유형 | Neo4j 레이블 | 주요 속성 | 설명 |
|----------|------------|----------|------|
| **BusinessEvent** | `:BusinessEvent:Process` | name, timestamp, duration, sla_threshold, expected_duration, actual_avg_duration, violation_rate | EventStorming의 Domain Event. 시간축 속성 포함 |
| **BusinessAction** | `:BusinessAction:Process` | name, actor_id, trigger_type | EventStorming의 Command. 프로세스를 트리거하는 행위 |
| **BusinessRule** | `:BusinessRule:Process` | name, condition, action, is_automated | EventStorming의 Policy. 이벤트에 반응하는 자동화 규칙 |

#### 보조 노드

| 노드 유형 | Neo4j 레이블 | 설명 |
|----------|------------|------|
| **Activity** | `:Activity` | 프로세스 내 개별 활동 (name, stage, responsible_party, deadline) |
| **Decision** | `:Decision` | 의사결정 (type, date, decision_maker, ruling) |

#### EventStorming 매핑: Process 계층

| EventStorming 개념 | 매핑 노드 유형 | 매핑 규칙 |
|-------------------|-------------|----------|
| **Command** (명령) | BusinessAction | Actor가 트리거하는 의도적 행위 → Command→Event 체인의 시작점 |
| **Domain Event** (도메인 이벤트) | BusinessEvent | "~됨"으로 표현되는 발생한 사실 → 시간축 속성과 이벤트 로그 바인딩 |
| **Policy** (정책/규칙) | BusinessRule | Event에 자동 반응하는 비즈니스 규칙 → 다음 Command를 트리거 |

#### Cypher 예시: Process 노드 및 관계 생성

```cypher
// Process 노드 생성
CREATE (p:DataCollection:Process {
  id: randomUUID(),
  case_id: $case_id,
  org_id: $org_id,
  type: 'DataCollection',
  name: '데이터 수집',
  source_system: 'ERP',
  collection_date: date('2024-01-15'),
  stage: 'completed',
  source: 'ingested',
  created_at: datetime()
})

// Resource → Process 관계 생성
MATCH (r:Company:Resource {case_id: $case_id, name: 'XYZ 주식회사'})
MATCH (p:DataCollection:Process {case_id: $case_id})
CREATE (r)-[:PARTICIPATES_IN {role: 'target_organization', since: date('2024-01-15')}]->(p)
```

---

### 2.3 Measure 계층 (지표)

> "프로세스 실행에서 파생되는 정량적 측정값"

#### 노드 유형

| 노드 유형 | Neo4j 레이블 | 주요 속성 | 설명 |
|----------|------------|----------|------|
| **Revenue** | `:Revenue:Measure` | amount, currency, as_of_date | 매출 |
| **Cost** | `:Cost:Measure` | amount, cost_type, period | 비용 |
| **OperatingProfit** | `:OperatingProfit:Measure` | amount, margin_rate, as_of_date | 영업이익 |
| **Throughput** | `:Throughput:Measure` | volume, unit, period | 처리량 |
| **CycleTime** | `:CycleTime:Measure` | duration, unit, process_id | 사이클 타임 |
| **ResourceUtilization** | `:ResourceUtilization:Measure` | rate, resource_id, period | 리소스 활용률 |

#### 보조 노드

| 노드 유형 | Neo4j 레이블 | 설명 |
|----------|------------|------|
| **MeasureSnapshot** | `:MeasureSnapshot` | 시점별 측정값 스냅샷 (measure_id, period, value) |

#### EventStorming 매핑: Measure 계층

| EventStorming 개념 | 매핑 규칙 |
|-------------------|----------|
| **Read Model** (조회 뷰) | 이벤트 체인의 결과로 산출되는 정량적 지표 → Measure 노드로 자동 생성 |
| **Event 체인 결과** | Command→Event 체인이 완료되면 해당 체인에서 Measure가 산출됨 |

Event → Measure 바인딩 예시:
```
{출하됨} ──produces──▶ [배송완료율: 95.2%] ──contributes_to──▶ (물류 효율성 KPI)
{결제됨} ──produces──▶ [일매출: 1.2억]     ──contributes_to──▶ (수익성 KPI)
```

#### Cypher 예시: Measure 노드 및 관계 생성

```cypher
// Measure 노드 생성
CREATE (m:Revenue:Measure {
  id: randomUUID(),
  case_id: $case_id,
  org_id: $org_id,
  type: 'Revenue',
  name: '매출',
  amount: 50000000000,
  currency: 'KRW',
  as_of_date: date('2024-06-01'),
  formula: 'SUM(all revenue streams)',
  data_type: 'currency',
  source: 'ingested',
  created_at: datetime()
})

// Process → Measure 관계 생성
MATCH (p:ProcessAnalysis:Process {case_id: $case_id})
MATCH (m:Revenue:Measure {case_id: $case_id})
CREATE (p)-[:PRODUCES {calculation: 'revenue_analysis'}]->(m)
```

---

### 2.4 KPI 계층 (성과)

> "Measure에서 산출되는 전략적 성과 지표"

#### 노드 유형

| 노드 유형 | Neo4j 레이블 | 주요 속성 | 설명 |
|----------|------------|----------|------|
| **ProcessEfficiency** | `:ProcessEfficiency:KPI` | target, actual, formula | 프로세스 효율성 |
| **CostReduction** | `:CostReduction:KPI` | target, actual, formula | 비용 절감률 |
| **ROI** | `:ROI:KPI` | target, actual, formula | 투자 수익률 |
| **CustomerSatisfaction** | `:CustomerSatisfaction:KPI` | score, max_score, criteria | 고객 만족도 |
| **ProjectCompletion** | `:ProjectCompletion:KPI` | target_months, actual_months | 프로젝트 완료 기간 |

#### 보조 노드

| 노드 유형 | Neo4j 레이블 | 설명 |
|----------|------------|------|
| **KPITarget** | `:KPITarget` | 목표 기준 (kpi_id, green_threshold, yellow, red) |
| **KPIHistory** | `:KPIHistory` | 기간별 KPI 이력 (kpi_id, period, value, status) |

#### EventStorming 매핑: KPI 계층

| 매핑 규칙 | 설명 |
|----------|------|
| Measure 집계 → KPI | 여러 Measure 노드가 하나의 KPI에 CONTRIBUTES_TO 관계로 집계됨 |
| 시간축 집계 → KPI | 시간축 속성(violation_rate, actual_avg_duration)이 KPI 산출에 활용 |

EventStorming에서 KPI는 직접 모델링되지 않으나, Event 체인에서 산출된 Measure들의 집계로 자동 연결된다.

#### Cypher 예시: KPI 노드 및 관계 생성

```cypher
// KPI 노드 생성
CREATE (k:ProcessEfficiency:KPI {
  id: randomUUID(),
  case_id: $case_id,
  org_id: $org_id,
  type: 'ProcessEfficiency',
  name: '프로세스 효율성',
  target: 0.90,
  actual: 0.85,
  formula: 'Throughput / ResourceUtilization',
  reporting_period: '2024-Q2',
  source: 'calculated',
  created_at: datetime()
})

// Measure → KPI 관계 생성
MATCH (m:Throughput:Measure {case_id: $case_id})
MATCH (k:ProcessEfficiency:KPI {case_id: $case_id})
CREATE (m)-[:CONTRIBUTES_TO {weight: 1.0, formula: 'numerator'}]->(k)

// KPI → Measure 역방향 의존
MATCH (k:ProcessEfficiency:KPI {case_id: $case_id})
MATCH (m:ResourceUtilization:Measure {case_id: $case_id})
CREATE (k)-[:DEPENDS_ON {formula: 'denominator'}]->(m)
```

---

## 3. 관계 타입 상세

### 3.1 핵심 관계

```
(Resource)-[:PARTICIPATES_IN {role, since}]->(Process)
(Resource)-[:CONTRIBUTES_TO {contribution_type}]->(Measure)
(Process)-[:PRODUCES {calculation}]->(Measure)
(Measure)-[:CONTRIBUTES_TO {weight, formula}]->(KPI)
(KPI)-[:DEPENDS_ON {formula}]->(Measure)
(Process)-[:INFLUENCES {impact_type, strength}]->(KPI)
```

### 3.2 EventStorming 관계

```
(Resource)-[:TRIGGERS {role}]->(BusinessAction)
(BusinessAction)-[:PRODUCES]->(BusinessEvent)
(BusinessEvent)-[:ACTIVATES]->(BusinessRule)
(BusinessRule)-[:TRIGGERS]->(BusinessAction)
(BusinessEvent)-[:PRODUCES]->(Measure)
(BusinessEvent)-[:FOLLOWED_BY {avg_duration, case_count}]->(BusinessEvent)
(BusinessEvent)-[:BINDS_TO {source_table, source_event, timestamp_column, case_id_column, filter_condition}]->(EventLog)
```

### 3.3 보조 관계

```
(Process)-[:HAS_ACTIVITY]->(Activity)
(Process)-[:RESULTED_IN]->(Decision)
(Measure)-[:HAS_SNAPSHOT]->(MeasureSnapshot)
(KPI)-[:HAS_TARGET]->(KPITarget)
(KPI)-[:HAS_HISTORY]->(KPIHistory)
(Resource)-[:BOUND_BY]->(Inventory)
(Inventory)-[:ALLOCATED_TO]->(Contract)
(Resource)-[:OWNS]->(Asset)
```

### 3.3 관계 그래프 시각화

```
Company ──PARTICIPATES_IN──▶ DataCollection ──PRODUCES──▶ Revenue ──CONTRIBUTES_TO──▶ ProcessEfficiency
   │                              │                             │                                    │
   ├─OWNS──▶ Asset               ├─HAS_ACTIVITY──▶ Activity    ├─HAS_SNAPSHOT──▶ MeasureSnapshot     ├─HAS_TARGET──▶ KPITarget
   │                              │                                                                  │
   ├─HAS──▶ Financial            └─RESULTED_IN──▶ Decision                                          └─HAS_HISTORY──▶ KPIHistory
   │
   └─HAS──▶ Contract ──BOUND_BY──▶ Inventory
```

---

## 4. 전체 Cypher 경로 탐색 예시

### 4.1 KPI에서 근본 자원까지 역추적

```cypher
// "프로세스 효율성이 85%인 이유를 역추적"
MATCH path = (k:KPI {type: 'ProcessEfficiency', case_id: $case_id})
  -[:DEPENDS_ON|CONTRIBUTES_TO*..3]-(m:Measure)
  <-[:PRODUCES]-(p:Process)
  <-[:PARTICIPATES_IN]-(r:Resource)
RETURN path
ORDER BY length(path)
```

### 4.2 자원 변경의 KPI 영향도 분석

```cypher
// "자산 A를 변경하면 어떤 KPI가 영향받는가?"
MATCH (a:Asset:Resource {id: $asset_id, case_id: $case_id})
MATCH path = (a)-[:PARTICIPATES_IN|CONTRIBUTES_TO|PRODUCES|CONTRIBUTES_TO*..4]->(k:KPI)
RETURN DISTINCT k.type AS affected_kpi, k.name AS kpi_name, length(path) AS distance
ORDER BY distance
```

### 4.3 특정 케이스의 전체 온톨로지 조회

```cypher
// 케이스 전체 온톨로지 서브그래프
MATCH (n {case_id: $case_id})
WHERE n:Resource OR n:Process OR n:Measure OR n:KPI
OPTIONAL MATCH (n)-[r]->(m {case_id: $case_id})
WHERE m:Resource OR m:Process OR m:Measure OR m:KPI
RETURN n, r, m
```

---

## 5. 비즈니스 프로세스 온톨로지 매핑 예시

### 5.1 완전한 프로젝트 예시

```
[Resource 계층]
  ├─ (:Company:Resource {name: "ABC 제조", industry: "제조업"})
  ├─ (:Asset:Resource {name: "스마트 공장", type: "Facility", market_value: 200억})
  ├─ (:Asset:Resource {name: "생산 설비", type: "Equipment", market_value: 50억})
  ├─ (:Contract:Resource {counterparty: "원자재 공급사", principal: 100억, contract_type: "공급계약"})
  ├─ (:Contract:Resource {counterparty: "유통사", principal: 80억, contract_type: "판매계약"})
  ├─ (:Financial:Resource {fiscal_year: 2023, revenue: 500억, ebitda: 50억})
  └─ (:Employee:Resource {count: 1000, department: "생산부"})

[Process 계층]
  ├─ (:DataCollection:Process {source_system: "ERP", collection_date: "2024-01-15"})
  ├─ (:ProcessAnalysis:Process {analysis_type: "bottleneck", findings_count: 12})
  ├─ (:Optimization:Process {target_metric: "throughput", improvement_rate: 0.15})
  └─ (:Execution:Process {execution_count: 3, start: "2024-09-01"})

[Measure 계층]
  ├─ (:Revenue:Measure {amount: 500억})
  ├─ (:Cost:Measure {amount: 400억})
  ├─ (:OperatingProfit:Measure {amount: 50억})
  ├─ (:Throughput:Measure {volume: 10000, unit: "units/month"})
  ├─ (:CycleTime:Measure {duration: 48, unit: "hours"})
  └─ (:ResourceUtilization:Measure {rate: 0.78})

[KPI 계층]
  ├─ (:ProcessEfficiency:KPI {target: 0.90, actual: 0.85})
  ├─ (:CostReduction:KPI {target: 0.20, actual: 0.15})
  └─ (:ROI:KPI {target: 0.25, actual: 0.20})
```

---

## 6. pm4py Process Mining과 온톨로지 연동

pm4py로 발견된 프로세스 모델은 4계층 온톨로지에 자동으로 반영된다. 이 연동을 통해 설계(EventStorming)와 실행(이벤트 로그)의 차이를 온톨로지 그래프 위에서 직접 분석할 수 있다.

### 6.1 발견된 모델 → 온톨로지 매핑

| pm4py 산출물 | 온톨로지 노드/관계 | 설명 |
|-------------|-----------------|------|
| Transition (활동) | `:BusinessEvent:Process` | 발견된 각 활동이 Process 계층 노드로 생성 |
| Arc (전이) | `(:BusinessEvent)-[:FOLLOWED_BY]->(:BusinessEvent)` | 활동 간 순서 관계 |
| Activity duration 통계 | `:CycleTime:Measure` | 활동별 평균 소요시간이 Measure 노드로 생성 |
| SLA violation rate | `:Measure` (type="SLACompliance") | SLA 위반율이 Measure 노드로 생성 |
| Bottleneck score | `:Measure` (type="BottleneckScore") | 병목 점수가 Measure 노드로 생성 |
| Conformance fitness | `:KPI` (type="ProcessEfficiency") | 적합성 점수가 KPI 노드에 반영 |

### 6.2 연동 흐름

```
이벤트 로그 인제스트
    │
    ▼ pm4py Process Discovery
    │
    ├─ Petri Net / BPMN 생성
    │      │
    │      ▼ 활동/전이 → Process 계층 노드 + FOLLOWED_BY 관계
    │
    ├─ Temporal Analysis
    │      │
    │      ▼ duration_stats → Measure 계층 (CycleTime, SLACompliance, BottleneckScore)
    │
    └─ Conformance Checking
           │
           ▼ fitness/precision → KPI 계층 (ProcessEfficiency)에 CONTRIBUTES_TO 관계
```

EventStorming 모델이 이미 존재하는 경우, pm4py가 발견한 활동은 기존 `:BusinessEvent` 노드에 `actual_avg_duration`, `violation_rate` 등의 시간축 속성으로 바인딩된다. 신규 활동(설계에 없는 활동)이 발견되면 `source="discovered"` 속성과 함께 새 노드가 생성된다.

---

## 결정 사항

| 결정 | 근거 |
|------|------|
| 4계층 구조 채택 | K-AIR 온톨로지 설계를 비즈니스 프로세스 인텔리전스에 적용 (ADR-002) |
| 다중 레이블 사용 | Neo4j 5의 다중 레이블 인덱싱으로 계층 + 유형 동시 검색 가능 |
| case_id 필수 | 멀티테넌트 + 케이스별 격리 필수 (07_security/data-access.md) |
| MERGE 패턴 사용 | 인제스트 시 중복 생성 방지 (upsert 패턴) |

## 재검토 조건

- 신규 도메인의 Process 유형이 현재 유형으로 표현 불가할 경우
- 5번째 계층 (예: Strategy) 필요성이 대두될 경우
- Neo4j가 아닌 다른 그래프 DB로 전환 검토 시
- EventStorming 개념 중 현재 매핑으로 표현 불가한 패턴이 발견될 경우
- 시간축 속성의 정밀도가 비즈니스 요구를 충족하지 못할 경우

---

## 근거 문서

- ADR-002: 4계층 온톨로지 설계 결정 (`99_decisions/ADR-002-4layer-ontology.md`)
- K-AIR 역설계 분석 보고서 섹션 2.3, 4.7.2
- `06_data/neo4j-schema.md` (Neo4j 전체 스키마)
- `06_data/ontology-model.md` (온톨로지 데이터 모델)
