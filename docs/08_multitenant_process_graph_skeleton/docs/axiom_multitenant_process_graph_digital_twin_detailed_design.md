# Axiom 멀티테넌트 프로세스 그래프 + 디지털 트윈 상세 설계서

- 작성일: 2026-03-23
- 대상: Axiom Core / Oracle / Vision / What-if / Ontology / Digital Twin 확장
- 목적: Axiom에 부재한 **회사별(테넌트), 업무별(도메인), 프로세스 간 관계 분석, 시간 기반 디지털 트윈** 구조를 통합적으로 도입하기 위한 상세 설계
- 상태: 설계안 (Implementation-ready)

---

## 0. 문서가 답하는 핵심 질문

이 문서는 다음 질문에 대한 구현 가능한 답을 제시한다.

1. Axiom에 회사별/조직별/업무별 테넌트 구조를 어떻게 넣을 것인가?
2. 하나의 업무 프로세스가 다른 업무 프로세스에 미치는 영향과 연결을 어떤 모델로 저장하고 분석할 것인가?
3. 디지털 트윈을 단순 시각화가 아니라 시간축을 가진 운영 모델로 어떻게 구현할 것인가?
4. PostgreSQL, Neo4j, Event Bus를 어떻게 역할 분리할 것인가?
5. 백엔드/프론트엔드/API/이벤트/권한/마이그레이션을 어떤 순서로 도입할 것인가?

---

# 1. 설계 목표

## 1.1 목표

Axiom을 다음 구조로 확장한다.

- **멀티테넌트 운영 구조**: 회사/계열사/부서/업무영역 단위 격리
- **프로세스 정의 구조**: 업무 흐름, 단계, 역할, 입력/출력 계약, KPI 정의
- **프로세스 관계 그래프**: 업무 간 의존성, 핸드오프, 데이터 흐름, KPI 영향 관계 표현
- **디지털 트윈 구조**: 현재 상태, 과거 스냅샷, 이벤트 흐름, 미래 시나리오 시뮬레이션
- **What-if 분석 구조**: 규칙 변경, 인력 배치, 자동화율, 우선순위 정책 변경 효과 분석

## 1.2 비목표

이번 설계는 아래를 직접 구현 범위로 보지 않는다.

- 범용 BPMN 엔진 자체 구현
- 모든 외부 시스템과의 실시간 양방향 연동
- 완전 자동 프로세스 마이닝 플랫폼 구현
- 고정밀 DES(Discrete Event Simulation) 엔진의 풀스펙 개발

즉, 본 설계는 **운영 모델과 분석 모델을 정립**하고, 이후 실행 엔진과 시뮬레이터를 점진적으로 고도화할 수 있는 토대를 만드는 것이 핵심이다.

---

# 2. 핵심 설계 원칙

## 2.1 트리와 그래프를 분리한다

Axiom은 아래 두 구조를 동시에 가져야 한다.

1. **Containment Tree**
   - Tenant → OrgUnit → Workspace/Domain → ProcessGroup → ProcessDefinition
   - 소유권, 권한, 메뉴, 관리 범위 표현에 사용

2. **Dependency Graph**
   - Process A → Process B
   - Step → KPI
   - Rule → Process
   - DataObject → Process
   - 상호 영향과 연쇄 분석에 사용

트리만 있으면 폴더 구조가 되고, 그래프만 있으면 관리 경계가 무너진다. 둘을 분리하고 연결해야 한다.

## 2.2 정의와 실행을 분리한다

프로세스는 반드시 아래 4층으로 분리한다.

- **Definition**: 설계도, 버전, 단계, 규칙, 인터페이스
- **Instance**: 실제 실행 중인 업무 케이스
- **Observation**: 상태, 큐 길이, 처리시간, SLA, 예외율
- **Scenario**: 바꿨을 때 예상되는 미래 상태

## 2.3 디지털 트윈은 이벤트 + 스냅샷 구조로 만든다

디지털 트윈은 단순 대시보드가 아니다. 아래가 모두 필요하다.

- Twin Entity
- Twin State
- Twin Event
- Twin Snapshot
- Twin Scenario

## 2.4 모든 핵심 엔티티는 스코프를 가진다

모든 저장 엔티티에 최소 아래 스코프를 둔다.

- tenant_id
- org_unit_id (nullable)
- workspace_id / domain_id
- namespace
- visibility_scope

## 2.5 템플릿과 오버라이드를 분리한다

업종 표준 프로세스 템플릿을 제공하더라도 실제 운영은 고객사마다 다르므로 아래 구조를 사용한다.

- global template
- tenant clone
- tenant override patch

---

# 3. 전체 아키텍처

## 3.1 논리 아키텍처

```text
┌───────────────────────────────────────────────────────────────┐
│                        Axiom Frontend                         │
│  Tenant Admin / Process Studio / Graph Explorer / Twin Cockpit│
└───────────────────────────────────────────────────────────────┘
                 │
                 ▼
┌───────────────────────────────────────────────────────────────┐
│                       API Gateway / BFF                       │
│        Auth / Tenant Context / Routing / Aggregation          │
└───────────────────────────────────────────────────────────────┘
        │                  │                    │
        ▼                  ▼                    ▼
┌────────────────┐ ┌──────────────────┐ ┌──────────────────────┐
│ Governance Svc │ │ Process Model Svc│ │ Digital Twin Svc     │
│ Tenant/RBAC    │ │ Definition/Graph │ │ Instance/State/Event │
└────────────────┘ └──────────────────┘ └──────────────────────┘
        │                  │                    │
        ▼                  ▼                    ▼
┌────────────────┐ ┌──────────────────┐ ┌──────────────────────┐
│ PostgreSQL     │ │ Neo4j            │ │ Event Bus / Outbox   │
│ metadata/txn   │ │ dependency graph │ │ state propagation    │
└────────────────┘ └──────────────────┘ └──────────────────────┘
                              │
                              ▼
                     ┌──────────────────┐
                     │ What-if / Sim Svc│
                     │ scenario engine  │
                     └──────────────────┘
```

## 3.2 서비스 경계

### A. Governance Service
역할:
- Tenant/OrgUnit/Workspace 관리
- 사용자-역할-정책 매핑
- scope resolution
- 템플릿 배포 권한 검증

### B. Process Model Service
역할:
- ProcessDefinition / StepDefinition / Interface / Rule / KPI 모델 관리
- 버전 관리
- 프로세스 간 관계 생성/수정
- Neo4j 그래프 동기화
- 영향도 분석 API 제공

### C. Digital Twin Service
역할:
- ProcessInstance / StepInstance 관리
- TwinEvent 수집
- TwinState 계산
- Snapshot 생성
- 운영 대시보드 집계

### D. What-if / Simulation Service
역할:
- 현재 snapshot 복제
- scenario branch 생성
- 정책/규칙/자원 변경 가정 적용
- 결과 비교 및 영향도 계산

### E. Ontology / Semantic Layer Integration
역할:
- 프로세스/데이터 계약/문서/지표를 온톨로지 개념과 매핑
- 시멘틱 검색 및 자동 연결 보강
- 동일 프로세스 후보 추천, 상위 개념 매핑

---

# 4. 핵심 도메인 모델

## 4.1 멀티테넌시 / 거버넌스

### Tenant
- id (uuid)
- code (varchar, unique)
- name
- industry_type
- status (ACTIVE, SUSPENDED, ARCHIVED)
- default_timezone
- data_residency
- created_at, updated_at

### OrgUnit
- id
- tenant_id
- parent_org_unit_id (nullable)
- code
- name
- org_type (HQ, DIVISION, DEPARTMENT, SUBSIDIARY, CENTER)
- owner_user_id (nullable)
- path
- created_at, updated_at

### Workspace
- id
- tenant_id
- org_unit_id
- code
- name
- workspace_type (PROCESS, ANALYTICS, TWIN, SANDBOX)
- visibility_policy
- created_at, updated_at

### ProcessDomain
- id
- tenant_id
- workspace_id
- code
- name
- domain_type (CLAIM, PAYMENT, RISK, SALES, SUPPORT, COMPLIANCE, GENERIC)
- description
- created_at, updated_at

## 4.2 프로세스 정의

### ProcessDefinition
- id
- tenant_id
- workspace_id
- domain_id
- namespace (`tenant.claim.review`)
- code
- name
- description
- process_type (HUMAN, SYSTEM, AI, HYBRID)
- lifecycle_state (DRAFT, ACTIVE, DEPRECATED, ARCHIVED)
- owner_org_unit_id
- primary_kpi_set_id (nullable)
- ontology_concept_id (nullable)
- current_version_id (nullable)
- created_by, created_at, updated_at

### ProcessVersion
- id
- process_definition_id
- version_no (e.g. 1.0.0)
- base_template_id (nullable)
- version_status (DRAFT, PUBLISHED, DEPRECATED)
- change_summary
- effective_from
- effective_to (nullable)
- is_current
- hash
- created_by, created_at

### StepDefinition
- id
- process_version_id
- step_key
- name
- step_type (START, TASK, DECISION, WAIT, HANDOFF, END, SUBPROCESS)
- sequence_order
- lane_role_id (nullable)
- sla_minutes (nullable)
- automation_level (MANUAL, ASSISTED, AUTOMATED, AI_AUTONOMOUS)
- input_contract_id (nullable)
- output_contract_id (nullable)
- rule_set_id (nullable)
- ui_metadata_json
- created_at, updated_at

### ProcessInterface
- id
- tenant_id
- workspace_id
- code
- name
- interface_type (EVENT, DOCUMENT, API, DATASET, MESSAGE)
- schema_ref
- version
- contract_json
- created_at, updated_at

### RuleDefinition
- id
- tenant_id
- workspace_id
- code
- name
- rule_type (BUSINESS_RULE, POLICY, THRESHOLD, ROUTING, VALIDATION, AI_GUARDRAIL)
- expression_language (SQL, JSONLOGIC, PY_EXPR, DSL)
- expression_body
- severity
- owner_org_unit_id
- created_at, updated_at

### KPIDefinition
- id
- tenant_id
- workspace_id
- code
- name
- unit
- target_formula
- actual_formula
- threshold_json
- aggregation_window
- created_at, updated_at

## 4.3 프로세스 실행 / 디지털 트윈

### ProcessInstance
- id
- tenant_id
- process_definition_id
- process_version_id
- business_key
- source_system
- source_ref_id
- status (CREATED, RUNNING, WAITING, BLOCKED, COMPLETED, FAILED, CANCELLED)
- started_at
- ended_at (nullable)
- current_step_id (nullable)
- current_assignee_id (nullable)
- priority
- attributes_json
- created_at, updated_at

### StepInstance
- id
- tenant_id
- process_instance_id
- step_definition_id
- status (PENDING, ACTIVE, WAITING, DONE, FAILED, SKIPPED)
- entered_at
- exited_at
- assignee_id (nullable)
- duration_ms (nullable)
- input_payload_json
- output_payload_json
- exception_code (nullable)
- created_at, updated_at

### TwinEntity
- id
- tenant_id
- entity_type (PROCESS, STEP, SYSTEM, ORG_UNIT, DATA_OBJECT, KPI)
- ref_table
- ref_id
- twin_key
- display_name
- created_at

### TwinState
- id
- tenant_id
- twin_entity_id
- snapshot_time
- state_type (CURRENT, DERIVED, PREDICTED)
- state_json
- health_score
- risk_score
- bottleneck_score
- updated_at

### TwinEvent
- id
- tenant_id
- entity_type
- entity_ref_id
- event_type
- event_time
- correlation_id
- causation_id
- payload_json
- processed_status
- created_at

### TwinSnapshot
- id
- tenant_id
- workspace_id
- snapshot_type (SCHEDULED, MANUAL, SCENARIO_BASELINE, SCENARIO_RESULT)
- captured_at
- source_event_cursor
- summary_json
- storage_ref
- created_by

### TwinScenario
- id
- tenant_id
- workspace_id
- name
- baseline_snapshot_id
- scenario_status (DRAFT, RUNNING, COMPLETED, FAILED)
- assumption_json
- change_set_json
- created_by
- created_at, updated_at

### SimulationResult
- id
- tenant_id
- scenario_id
- result_version
- summary_json
- comparison_json
- output_artifact_ref
- created_at

---

# 5. 프로세스 간 분석을 위한 그래프 모델

## 5.1 노드 타입

Neo4j 노드 라벨 권장안:

- `Tenant`
- `OrgUnit`
- `Workspace`
- `Process`
- `ProcessVersion`
- `Step`
- `Interface`
- `DataObject`
- `Rule`
- `KPI`
- `TwinEntity`
- `System`
- `Role`

## 5.2 엣지 타입

### 구조/소속
- `(Tenant)-[:OWNS]->(Workspace)`
- `(Workspace)-[:CONTAINS]->(Process)`
- `(Process)-[:HAS_VERSION]->(ProcessVersion)`
- `(ProcessVersion)-[:HAS_STEP]->(Step)`

### 프로세스 간 관계
- `(Process)-[:TRIGGERS]->(Process)`
- `(Process)-[:HANDOFF_TO]->(Process)`
- `(Process)-[:BLOCKS]->(Process)`
- `(Process)-[:DEPENDS_ON]->(Process)`
- `(Process)-[:INFLUENCES_KPI]->(KPI)`
- `(Process)-[:CONSUMES]->(Interface)`
- `(Process)-[:PRODUCES]->(Interface)`
- `(Process)-[:GOVERNED_BY]->(Rule)`
- `(Process)-[:OWNED_BY]->(OrgUnit)`

### 단계 수준 관계
- `(Step)-[:NEXT]->(Step)`
- `(Step)-[:EMITS]->(Interface)`
- `(Step)-[:REQUIRES]->(Rule)`
- `(Step)-[:MEASURED_BY]->(KPI)`

### 디지털 트윈 관계
- `(TwinEntity)-[:MIRRORS]->(Process)`
- `(TwinEntity)-[:OBSERVES]->(KPI)`
- `(TwinEntity)-[:STATE_OF]->(Step)`

## 5.3 관계 메타데이터

각 관계에는 아래 속성을 둘 수 있다.

- relation_type
- criticality (LOW, MEDIUM, HIGH, CRITICAL)
- latency_sensitivity
- data_contract_ref
- propagation_mode (SYNC, ASYNC, BATCH)
- confidence_score (자동 추론 관계인 경우)
- valid_from, valid_to
- created_by, created_at

## 5.4 대표 분석 질의

### A. 영향도 확산 분석
특정 프로세스 변경이 어떤 프로세스/KPI/부서에 영향을 미치는지 탐색.

### B. 병목 상류 추적
SLA 위반 Step에서 상류 BLOCKS / DEPENDS_ON 경로를 추적.

### C. 데이터 계약 변경 영향 분석
특정 Interface 스키마 변경 시 영향을 받는 Process/Step 탐색.

### D. 규칙 변경 파급 분석
RuleDefinition 수정이 어떤 업무와 KPI에 전파되는지 계산.

---

# 6. PostgreSQL 스키마 초안

## 6.1 거버넌스

```sql
create table tenants (
  id uuid primary key,
  code varchar(64) not null unique,
  name varchar(255) not null,
  industry_type varchar(64),
  status varchar(32) not null,
  default_timezone varchar(64) not null default 'Asia/Seoul',
  data_residency varchar(64),
  created_at timestamptz not null,
  updated_at timestamptz not null
);

create table org_units (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  parent_org_unit_id uuid references org_units(id),
  code varchar(64) not null,
  name varchar(255) not null,
  org_type varchar(32) not null,
  owner_user_id uuid,
  path text,
  created_at timestamptz not null,
  updated_at timestamptz not null,
  unique (tenant_id, code)
);

create table workspaces (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  org_unit_id uuid references org_units(id),
  code varchar(64) not null,
  name varchar(255) not null,
  workspace_type varchar(32) not null,
  visibility_policy jsonb,
  created_at timestamptz not null,
  updated_at timestamptz not null,
  unique (tenant_id, code)
);
```

## 6.2 프로세스 정의

```sql
create table process_domains (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  workspace_id uuid not null references workspaces(id),
  code varchar(64) not null,
  name varchar(255) not null,
  domain_type varchar(64) not null,
  description text,
  created_at timestamptz not null,
  updated_at timestamptz not null,
  unique (tenant_id, workspace_id, code)
);

create table process_definitions (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  workspace_id uuid not null references workspaces(id),
  domain_id uuid references process_domains(id),
  namespace varchar(255) not null,
  code varchar(64) not null,
  name varchar(255) not null,
  description text,
  process_type varchar(32) not null,
  lifecycle_state varchar(32) not null,
  owner_org_unit_id uuid references org_units(id),
  primary_kpi_set_id uuid,
  ontology_concept_id varchar(128),
  current_version_id uuid,
  created_by uuid,
  created_at timestamptz not null,
  updated_at timestamptz not null,
  unique (tenant_id, namespace),
  unique (tenant_id, workspace_id, code)
);

create table process_versions (
  id uuid primary key,
  process_definition_id uuid not null references process_definitions(id),
  version_no varchar(32) not null,
  base_template_id uuid,
  version_status varchar(32) not null,
  change_summary text,
  effective_from timestamptz,
  effective_to timestamptz,
  is_current boolean not null default false,
  hash varchar(128),
  created_by uuid,
  created_at timestamptz not null,
  unique (process_definition_id, version_no)
);

create table process_interfaces (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  workspace_id uuid not null references workspaces(id),
  code varchar(64) not null,
  name varchar(255) not null,
  interface_type varchar(32) not null,
  schema_ref varchar(255),
  version varchar(32),
  contract_json jsonb not null,
  created_at timestamptz not null,
  updated_at timestamptz not null,
  unique (tenant_id, workspace_id, code, version)
);

create table step_definitions (
  id uuid primary key,
  process_version_id uuid not null references process_versions(id),
  step_key varchar(64) not null,
  name varchar(255) not null,
  step_type varchar(32) not null,
  sequence_order integer not null,
  lane_role_id uuid,
  sla_minutes integer,
  automation_level varchar(32) not null,
  input_contract_id uuid references process_interfaces(id),
  output_contract_id uuid references process_interfaces(id),
  rule_set_id uuid,
  ui_metadata_json jsonb,
  created_at timestamptz not null,
  updated_at timestamptz not null,
  unique (process_version_id, step_key)
);
```

## 6.3 관계 메타데이터

```sql
create table process_relations (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  workspace_id uuid not null references workspaces(id),
  from_process_id uuid not null references process_definitions(id),
  to_process_id uuid not null references process_definitions(id),
  relation_type varchar(32) not null,
  criticality varchar(16) not null,
  propagation_mode varchar(16),
  interface_id uuid references process_interfaces(id),
  relation_metadata jsonb,
  valid_from timestamptz,
  valid_to timestamptz,
  created_by uuid,
  created_at timestamptz not null
);

create table rule_definitions (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  workspace_id uuid not null references workspaces(id),
  code varchar(64) not null,
  name varchar(255) not null,
  rule_type varchar(32) not null,
  expression_language varchar(32) not null,
  expression_body text not null,
  severity varchar(16),
  owner_org_unit_id uuid references org_units(id),
  created_at timestamptz not null,
  updated_at timestamptz not null,
  unique (tenant_id, workspace_id, code)
);

create table kpi_definitions (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  workspace_id uuid not null references workspaces(id),
  code varchar(64) not null,
  name varchar(255) not null,
  unit varchar(32),
  target_formula text,
  actual_formula text,
  threshold_json jsonb,
  aggregation_window varchar(32),
  created_at timestamptz not null,
  updated_at timestamptz not null,
  unique (tenant_id, workspace_id, code)
);
```

## 6.4 실행/트윈

```sql
create table process_instances (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  process_definition_id uuid not null references process_definitions(id),
  process_version_id uuid not null references process_versions(id),
  business_key varchar(128),
  source_system varchar(64),
  source_ref_id varchar(128),
  status varchar(32) not null,
  started_at timestamptz,
  ended_at timestamptz,
  current_step_id uuid,
  current_assignee_id uuid,
  priority varchar(16),
  attributes_json jsonb,
  created_at timestamptz not null,
  updated_at timestamptz not null,
  unique (tenant_id, process_definition_id, business_key)
);

create table step_instances (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  process_instance_id uuid not null references process_instances(id),
  step_definition_id uuid not null references step_definitions(id),
  status varchar(32) not null,
  entered_at timestamptz,
  exited_at timestamptz,
  assignee_id uuid,
  duration_ms bigint,
  input_payload_json jsonb,
  output_payload_json jsonb,
  exception_code varchar(64),
  created_at timestamptz not null,
  updated_at timestamptz not null
);

create table twin_entities (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  entity_type varchar(32) not null,
  ref_table varchar(64) not null,
  ref_id uuid not null,
  twin_key varchar(255) not null,
  display_name varchar(255) not null,
  created_at timestamptz not null,
  unique (tenant_id, twin_key)
);

create table twin_states (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  twin_entity_id uuid not null references twin_entities(id),
  snapshot_time timestamptz not null,
  state_type varchar(16) not null,
  state_json jsonb not null,
  health_score numeric(5,2),
  risk_score numeric(5,2),
  bottleneck_score numeric(5,2),
  updated_at timestamptz not null
);

create table twin_events (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  entity_type varchar(32) not null,
  entity_ref_id uuid,
  event_type varchar(64) not null,
  event_time timestamptz not null,
  correlation_id varchar(128),
  causation_id varchar(128),
  payload_json jsonb not null,
  processed_status varchar(16) not null default 'PENDING',
  created_at timestamptz not null
);

create table twin_snapshots (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  workspace_id uuid not null references workspaces(id),
  snapshot_type varchar(32) not null,
  captured_at timestamptz not null,
  source_event_cursor varchar(128),
  summary_json jsonb,
  storage_ref varchar(255),
  created_by uuid
);

create table twin_scenarios (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  workspace_id uuid not null references workspaces(id),
  name varchar(255) not null,
  baseline_snapshot_id uuid not null references twin_snapshots(id),
  scenario_status varchar(32) not null,
  assumption_json jsonb,
  change_set_json jsonb,
  created_by uuid,
  created_at timestamptz not null,
  updated_at timestamptz not null
);

create table simulation_results (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  scenario_id uuid not null references twin_scenarios(id),
  result_version integer not null,
  summary_json jsonb not null,
  comparison_json jsonb,
  output_artifact_ref varchar(255),
  created_at timestamptz not null
);
```

---

# 7. Neo4j 동기화 설계

## 7.1 동기화 원칙

- PostgreSQL이 **source of truth**
- Neo4j는 **query-optimized graph projection**
- 모든 그래프 갱신은 Outbox/Event 기반 비동기 동기화

## 7.2 Outbox 이벤트 예시

- `governance.tenant.created`
- `process.definition.created`
- `process.version.published`
- `process.step.updated`
- `process.relation.created`
- `rule.definition.updated`
- `kpi.definition.updated`
- `twin.entity.registered`

## 7.3 Graph Projection Worker

역할:
- outbox polling 또는 Redis Streams/Kafka consumer
- PostgreSQL row fetch
- Neo4j MERGE upsert
- relation tombstone 처리
- sync lag metric 측정

## 7.4 Neo4j 예시 Cypher

```cypher
MERGE (p:Process {id: $process_id})
SET p.name = $name,
    p.tenant_id = $tenant_id,
    p.workspace_id = $workspace_id,
    p.namespace = $namespace,
    p.lifecycle_state = $lifecycle_state,
    p.updated_at = datetime($updated_at)
```

```cypher
MATCH (a:Process {id: $from_id}), (b:Process {id: $to_id})
MERGE (a)-[r:DEPENDS_ON {relation_id: $relation_id}]->(b)
SET r.criticality = $criticality,
    r.propagation_mode = $propagation_mode,
    r.valid_from = datetime($valid_from)
```

---

# 8. 이벤트 계약 설계

## 8.1 이벤트 공통 Envelope

```json
{
  "event_id": "uuid",
  "event_type": "process.instance.step_entered",
  "event_version": "1.0",
  "tenant_id": "uuid",
  "workspace_id": "uuid",
  "entity_type": "STEP_INSTANCE",
  "entity_id": "uuid",
  "occurred_at": "2026-03-23T10:00:00Z",
  "correlation_id": "case-123",
  "causation_id": "evt-previous",
  "producer": "digital-twin-service",
  "payload": {}
}
```

## 8.2 핵심 도메인 이벤트

### Governance
- `tenant.created`
- `org_unit.created`
- `workspace.created`
- `membership.assigned`
- `policy.updated`

### Process Definition
- `process.definition.created`
- `process.version.published`
- `step.definition.updated`
- `interface.contract.changed`
- `process.relation.created`
- `process.relation.removed`

### Runtime / Twin
- `process.instance.created`
- `process.instance.started`
- `process.instance.blocked`
- `process.instance.completed`
- `step.instance.entered`
- `step.instance.completed`
- `step.instance.failed`
- `twin.snapshot.captured`
- `kpi.threshold.breached`

### Scenario
- `scenario.created`
- `scenario.run.started`
- `scenario.run.completed`
- `scenario.delta.detected`

## 8.3 멱등성 키 전략

- governance 이벤트: `tenant_id + entity_id + event_type + version`
- runtime 이벤트: `tenant_id + process_instance_id + step_instance_id + event_type + timestamp bucket`
- scenario 이벤트: `scenario_id + result_version`

---

# 9. 인증/권한/스코프 설계

## 9.1 JWT Claims 권장안

```json
{
  "sub": "user-id",
  "tenant_id": "tenant-id",
  "active_workspace_id": "workspace-id",
  "roles": ["TENANT_ADMIN", "PROCESS_ARCHITECT"],
  "org_unit_ids": ["ou-1", "ou-2"],
  "permissions": ["process:read", "process:write", "twin:read"]
}
```

## 9.2 권한 모델

### 시스템 역할
- SUPER_ADMIN
- PLATFORM_OPERATOR

### 테넌트 역할
- TENANT_ADMIN
- TENANT_AUDITOR
- DOMAIN_MANAGER
- PROCESS_ARCHITECT
- OPERATION_ANALYST
- TWIN_OPERATOR
- SCENARIO_ANALYST

## 9.3 ABAC 조건

추가 속성:
- tenant match
- workspace membership
- org ownership
- domain ownership
- classification scope
- process lifecycle state

예시:
- `PROCESS_ARCHITECT`는 자신이 소속된 workspace의 DRAFT/PUBLISHED 프로세스 수정 가능
- `TWIN_OPERATOR`는 runtime/twin 데이터 수정 가능하나 definition은 불가
- `AUDITOR`는 모든 스냅샷/이벤트 조회 가능하나 시나리오 실행은 불가

## 9.4 데이터 접근 강제

모든 Repository / Query / Neo4j traversal에서 tenant_id를 강제한다.

권장 방식:
- PostgreSQL: RLS(Row Level Security) 또는 application-level tenant predicate 강제
- Neo4j: 모든 MATCH에 `tenant_id` 조건 포함
- 캐시 키: `tenant_id`를 prefix에 포함

---

# 10. API 설계 초안

## 10.1 Governance API

### Tenant / Workspace
- `POST /api/governance/tenants`
- `GET /api/governance/tenants/{tenantId}`
- `POST /api/governance/tenants/{tenantId}/org-units`
- `POST /api/governance/tenants/{tenantId}/workspaces`
- `GET /api/governance/workspaces/{workspaceId}`
- `POST /api/governance/workspaces/{workspaceId}/members`

### 예시 DTO

```json
{
  "code": "insure-a",
  "name": "Insure A",
  "industryType": "INSURANCE",
  "defaultTimezone": "Asia/Seoul"
}
```

## 10.2 Process Model API

### Process Definition
- `POST /api/process-model/processes`
- `GET /api/process-model/processes/{processId}`
- `GET /api/process-model/processes?workspaceId=&domainId=&q=`
- `POST /api/process-model/processes/{processId}/versions`
- `POST /api/process-model/process-versions/{versionId}/publish`
- `POST /api/process-model/process-versions/{versionId}/steps`
- `PATCH /api/process-model/steps/{stepId}`

### Relations
- `POST /api/process-model/relations`
- `DELETE /api/process-model/relations/{relationId}`
- `GET /api/process-model/processes/{processId}/upstream`
- `GET /api/process-model/processes/{processId}/downstream`
- `GET /api/process-model/processes/{processId}/impact-map`

### Contracts / Rules / KPI
- `POST /api/process-model/interfaces`
- `POST /api/process-model/rules`
- `POST /api/process-model/kpis`
- `POST /api/process-model/processes/{processId}/bindings/kpis`

## 10.3 Digital Twin API

### Runtime
- `POST /api/twin/process-instances`
- `GET /api/twin/process-instances/{instanceId}`
- `POST /api/twin/step-instances/{stepInstanceId}/enter`
- `POST /api/twin/step-instances/{stepInstanceId}/complete`
- `POST /api/twin/step-instances/{stepInstanceId}/fail`

### State / Snapshot
- `GET /api/twin/entities/{entityId}/state`
- `GET /api/twin/entities/{entityId}/timeline`
- `POST /api/twin/snapshots`
- `GET /api/twin/snapshots/{snapshotId}`
- `GET /api/twin/workspaces/{workspaceId}/cockpit`

## 10.4 Scenario / What-if API

- `POST /api/scenario`
- `POST /api/scenario/{scenarioId}/run`
- `GET /api/scenario/{scenarioId}`
- `GET /api/scenario/{scenarioId}/result`
- `GET /api/scenario/{scenarioId}/compare/{baselineSnapshotId}`

### 시나리오 생성 예시

```json
{
  "workspaceId": "uuid",
  "name": "심사 자동화율 20% 증가",
  "baselineSnapshotId": "uuid",
  "assumption": {
    "arrivalRate": "+5%",
    "fraudScreeningSensitivity": "same"
  },
  "changeSet": [
    {
      "type": "STEP_AUTOMATION_LEVEL",
      "targetRefId": "step-uuid",
      "before": "ASSISTED",
      "after": "AUTOMATED"
    }
  ]
}
```

---

# 11. 프론트엔드 화면 구조

## 11.1 메뉴 구조 권장안

```text
운영 거버넌스
 ├─ 테넌트 관리
 ├─ 조직/워크스페이스 관리
 └─ 권한/정책 관리

프로세스 스튜디오
 ├─ 도메인 관리
 ├─ 프로세스 정의
 ├─ 인터페이스/계약
 ├─ 규칙/정책
 └─ KPI 바인딩

프로세스 그래프
 ├─ 영향도 분석
 ├─ 상류/하류 탐색
 ├─ 병목 경로 분석
 └─ 데이터 계약 영향 분석

디지털 트윈
 ├─ 운영 코크핏
 ├─ 프로세스 상태 타임라인
 ├─ 이벤트 스트림
 └─ 스냅샷 뷰어

시나리오 분석
 ├─ What-if 생성
 ├─ 결과 비교
 └─ 시나리오 히스토리
```

## 11.2 주요 화면 컴포넌트 명세

### A. TenantAdminPage
- TenantListPanel
- OrgTreePanel
- WorkspaceTable
- MembershipDialog
- PolicyMatrixPanel

### B. ProcessStudioPage
- DomainSidebar
- ProcessListPane
- ProcessVersionTabs
- ProcessCanvas
- StepPropertyPanel
- InterfaceBindingPanel
- RuleBindingPanel
- KpiBindingPanel

### C. ProcessGraphExplorerPage
- GraphFilterBar
- DependencyGraphCanvas
- ImpactSummaryStrip
- UpstreamListCard
- DownstreamListCard
- CriticalPathPanel

### D. TwinCockpitPage
- TwinHealthStrip
- BottleneckHeatmap
- QueueLengthPanel
- SLAAlertPanel
- EventTimelinePanel
- SnapshotCompareCard

### E. ScenarioWorkbenchPage
- BaselineSnapshotSelector
- AssumptionEditor
- ChangeSetBuilder
- ScenarioRunPanel
- DeltaComparisonTable
- KPIImpactChart

## 11.3 화면 UX 원칙

- 좌측은 범위 선택(tenant/workspace/domain/process)
- 중앙은 그래프/캔버스/주요 분석 뷰
- 우측은 선택 엔티티 속성, KPI, 상태, 이벤트, 영향도 요약
- 모든 화면에서 현재 active scope를 상단 breadcrumb로 표시
- 그래프는 tenant/workspace/domain 필터 없이 절대 열리지 않도록 제한

---

# 12. 디지털 트윈 상태 계산 로직

## 12.1 상태 계산 레이어

### Raw Event Layer
원본 이벤트 수집.

### Derived State Layer
이벤트를 기반으로 현재 상태 계산.
예:
- current_step
- wait_time
- overdue_flag
- queue_size
- failure_rate

### Health/Risk Layer
규칙과 KPI를 적용하여 health/risk 점수 계산.

### Predictive Layer
간단한 추정 모델로 near-future 상태 예측.
예:
- 2시간 내 backlog 증가 예상
- 현재 정책 유지 시 SLA breach 확률 38%

## 12.2 점수 예시

```text
health_score = 100
  - overdue_ratio * 30
  - failure_rate * 20
  - avg_wait_vs_sla_ratio * 25
  - bottleneck_centrality * 25
```

```text
risk_score =
  weighted_sum(
    backlog_growth_rate,
    blocked_instances,
    exception_rate,
    critical_dependency_failure,
    kpi_breach_count
  )
```

## 12.3 병목 계산 예시

입력:
- step별 평균 체류시간
- step별 대기 건수
- downstream blocking weight
- criticality

출력:
- bottleneck_score
- critical path candidate
- upstream root cause candidate

---

# 13. 시나리오/What-if 엔진 설계

## 13.1 목표

아래 질문에 답하는 엔진을 제공한다.

- 심사 자동화율을 20% 높이면 처리시간은 얼마나 줄어드는가?
- 특정 승인 규칙을 완화하면 민원율과 리스크는 어떻게 바뀌는가?
- 인력을 한 단계에서 다른 단계로 재배치하면 병목이 해소되는가?
- 사기 탐지 민감도를 높이면 오탐/미탐/처리지연 균형이 어떻게 바뀌는가?

## 13.2 시나리오 변경 타입

- STEP_AUTOMATION_LEVEL
- STEP_CAPACITY
- ARRIVAL_RATE
- ROUTING_RULE
- KPI_THRESHOLD
- PRIORITY_POLICY
- ORG_ASSIGNMENT
- INTERFACE_LATENCY

## 13.3 실행 방식

초기 단계:
- 규칙 기반 근사 시뮬레이션
- 큐 길이/처리시간/KPI 변화 추정

중기 단계:
- discrete event simulation engine 연결
- historical calibration

## 13.4 결과 출력

- baseline vs scenario KPI 비교표
- critical path 변화
- blocked instance 추정치
- SLA breach probability
- impact graph overlay

---

# 14. 온톨로지/시멘틱 레이어와의 연결 포인트

## 14.1 연결 이유

프로세스 이름과 실제 의미는 테넌트마다 다르다. 시멘틱 레이어를 통해 아래를 보강한다.

- 유사 프로세스 추천
- 표준 업무군 매핑
- 데이터 객체/문서/규칙의 개념 정렬
- 영향 관계 자동 후보 탐지

## 14.2 매핑 엔티티

### SemanticBinding
- id
- tenant_id
- entity_type (PROCESS, STEP, INTERFACE, RULE, KPI)
- entity_id
- ontology_concept_id
- mapping_confidence
- mapping_source (MANUAL, RULE, LLM, IMPORT)
- approved_by
- approved_at

## 14.3 사용 예

- “보험금 접수”와 “청구 등록”을 상위 개념 `Claim Intake`로 묶음
- “심사 승인율”, “자동 승인률”을 KPI ontology에서 정렬
- Interface schema 필드와 semantic term를 연결하여 계약 영향도 보강

---

# 15. 백엔드 구현 구조 권장안

## 15.1 패키지 구조 예시

```text
axiom-backend/
  governance-service/
    domain/
    application/
    adapters/in/web/
    adapters/out/persistence/postgres/
    security/

  process-model-service/
    domain/
      process/
      step/
      relation/
      interface/
      rule/
      kpi/
    application/
      commands/
      queries/
      graph_sync/
    adapters/out/postgres/
    adapters/out/neo4j/
    adapters/out/outbox/

  digital-twin-service/
    domain/
      instance/
      state/
      event/
      snapshot/
      scenario/
    application/
      event_handlers/
      state_calculators/
      projections/
    adapters/out/postgres/
    adapters/out/eventbus/

  scenario-service/
    domain/
    application/
    adapters/out/postgres/
```

## 15.2 주요 애그리게이트

### Governance
- TenantAggregate
- WorkspaceAggregate
- MembershipAggregate

### Process Model
- ProcessDefinitionAggregate
- ProcessVersionAggregate
- RelationAggregate

### Digital Twin
- ProcessInstanceAggregate
- TwinSnapshotAggregate
- ScenarioAggregate

---

# 16. 운영 및 관측성

## 16.1 필수 운영 지표

- tenant별 API latency
- graph sync lag
- outbox backlog
- twin event processing delay
- snapshot generation duration
- scenario runtime
- tenant별 active process count
- tenant별 graph traversal cost

## 16.2 감사 로그

모든 민감 변경에 대해 감사 로그를 남긴다.

- 프로세스 정의 변경
- 관계 생성/삭제
- 규칙 수정
- 시나리오 실행
- 권한 변경
- 스냅샷 수동 생성

## 16.3 재처리 전략

- twin event handler는 idempotent 하게 구현
- failed event는 dead-letter로 이동
- snapshot은 재생성 가능
- graph projection은 full rebuild 지원

---

# 17. 마이그레이션 계획

## Phase 1. Tenant/Workspace 도입

### 목표
Axiom 기존 전역 구조에 tenant/workspace scope 추가.

### 작업
- 공통 인증 토큰에 tenant context 추가
- PostgreSQL 핵심 테이블에 tenant_id 추가
- 기존 도메인 엔티티에 workspace_id nullable 컬럼 추가
- API Gateway에서 tenant scope inject
- 화면 상단 scope selector 추가

### 산출물
- tenants/org_units/workspaces 기본 CRUD
- tenant-aware repository foundation
- scope middleware

## Phase 2. Process Definition 모델 도입

### 목표
업무를 정식 엔티티로 등록 가능한 구조 마련.

### 작업
- process_definitions / versions / steps / interfaces / rules / kpis 생성
- 프로세스 스튜디오 기본 화면 구현
- 버전 publish workflow 구현
- semantic binding optional 연계

### 산출물
- ProcessStudio MVP
- versioning + validation rules

## Phase 3. Process Relation Graph 도입

### 목표
업무 간 연결 분석 가능 구조 완성.

### 작업
- process_relations 테이블 생성
- graph projection worker 구현
- Neo4j schema/index 구성
- impact/upstream/downstream API 구현
- 그래프 탐색 UI 구현

### 산출물
- Graph Explorer MVP
- 영향도 분석 API

## Phase 4. Digital Twin Runtime 도입

### 목표
정의 모델 위에 실제 상태 모델 연결.

### 작업
- process_instances / step_instances / twin_events / twin_states / snapshots 생성
- 이벤트 ingest API 구현
- 상태 계산기 및 코크핏 집계 구현
- Snapshot scheduler 구현

### 산출물
- Twin Cockpit MVP
- 이벤트 기반 상태 갱신

## Phase 5. Scenario / What-if 도입

### 목표
현재 상태 기반 가상 실험 가능화.

### 작업
- twin_scenarios / simulation_results 구현
- baseline snapshot clone
- 규칙 기반 근사 시뮬레이터 구현
- 결과 비교 UI 구현

### 산출물
- What-if Workbench MVP
- KPI delta / bottleneck delta 분석

## Phase 6. 외부 연동 및 자동화 고도화

### 목표
수동 입력 중심 구조에서 반자동/자동 수집으로 확장.

### 작업
- 외부 BPM/ERP/CRM/문서 시스템 adapter 추가
- CDC 또는 webhook 기반 이벤트 수집
- process mining 보강
- predictive model calibration

---

# 18. 우선순위 및 현실적 권장안

## 18.1 반드시 먼저 해야 하는 것

1. tenant/workspace scope
2. process definition/version 구조
3. process relations + Neo4j projection

이 세 가지가 없으면 디지털 트윈은 화면만 생기고 실제 분석 기반이 없다.

## 18.2 초기에는 단순화해도 되는 것

- org_unit hierarchy depth는 2~3레벨부터 시작
- scenario engine은 규칙 기반 근사 계산부터 시작
- semantic binding은 manual-first, assist-later
- event bus는 Redis Streams부터 시작 가능

## 18.3 나중에 고도화할 것

- 풀 discrete event simulation
- process mining 자동 관계 추론
- AI 기반 병목 원인 추천
- auto-generated process contracts
- cross-tenant benchmark analytics

---

# 19. 주요 리스크와 대응

## 리스크 1. 모든 것을 BPM처럼 만들려다 범위가 폭증함
대응:
- 정의/그래프/트윈/시나리오를 단계적으로 분리 도입

## 리스크 2. 테넌트만 넣고 프로세스 관계가 부실해짐
대응:
- 반드시 process_relations와 interface contracts를 같이 설계

## 리스크 3. 디지털 트윈이 단순 모니터링 대시보드가 됨
대응:
- 이벤트, 스냅샷, 시나리오를 반드시 별도 엔티티로 둠

## 리스크 4. Neo4j를 source of truth처럼 사용하게 됨
대응:
- PostgreSQL source of truth 원칙 고수, Neo4j는 projection 전용

## 리스크 5. 권한 체계가 역할 기반만으로 끝남
대응:
- tenant + workspace + org + domain 기반 ABAC 추가

---

# 20. 최종 권고안

Axiom의 현재 공백은 “회사별 구분이 없다”보다 더 크다. 본질적으로는 아래 세 가지가 빠져 있다.

1. **운영 경계**: 누구의 조직, 누구의 업무, 누구의 권한인가
2. **관계 구조**: 이 업무가 다른 업무에 어떤 방식으로 연결되는가
3. **시간 구조**: 지금 어떤 상태이며, 바꾸면 어떻게 달라지는가

따라서 최종 구현 방향은 다음과 같아야 한다.

- PostgreSQL에 **멀티테넌트 거버넌스 + 프로세스 정의 + 런타임/트윈 메타데이터** 저장
- Neo4j에 **프로세스/단계/규칙/KPI/인터페이스 간 관계 그래프** 투영
- Event Bus/Outbox로 **정의 변경과 런타임 상태 변화**를 비동기 전파
- 프론트엔드는 **프로세스 스튜디오 / 그래프 탐색기 / 디지털 트윈 코크핏 / 시나리오 워크벤치**로 분리
- 도입 순서는 **Tenant → Process Definition → Graph → Twin → Scenario**로 진행

이 구조가 되면 Axiom은 단순 문서/지식/분석 플랫폼을 넘어서, **기업별 업무구조와 운영상태를 반영하고 프로세스 간 영향도와 미래 시나리오까지 분석하는 멀티테넌트 운영 디지털 트윈 플랫폼**으로 확장될 수 있다.

---

# 21. 바로 다음 단계에서 작성할 수 있는 후속 문서

이 상세 설계서를 기준으로 바로 이어서 아래 문서를 작성할 수 있다.

1. Spring Boot/WebFlux 기준 서비스별 엔티티/DTO/Repository/Controller 명세서
2. Neo4j 노드/엣지 인덱스 및 Cypher 쿼리 설계서
3. React 화면별 컴포넌트 트리 + 상태관리 설계서
4. Event Contract Registry 초안
5. 단계별 DB migration SQL 스크립트 초안
6. Phase 1~5 구현 백로그 (Epic/Feature/Story 수준)

