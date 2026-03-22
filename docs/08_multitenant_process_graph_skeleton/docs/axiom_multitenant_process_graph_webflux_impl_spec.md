# Axiom 멀티테넌트 프로세스 그래프 + 디지털 트윈 구현 명세서

- 작성일: 2026-03-23
- 기준 문서: `axiom_multitenant_process_graph_digital_twin_detailed_design.md`
- 대상 스택: Spring Boot 3.x, WebFlux, R2DBC PostgreSQL, Neo4j, Redis, Kafka(또는 Redis Streams), React/TypeScript
- 상태: Implementation-ready / 백엔드 우선
- 목적: Axiom에 **멀티테넌트 거버넌스 + 프로세스 정의/관계 그래프 + 디지털 트윈 상태/시나리오**를 실제 구현 가능한 수준으로 구체화

---

# 0. 문서 목적과 적용 범위

이 문서는 이전 상세 설계서를 실제 구현 단위까지 내린 문서다. 단순 개념 설명이 아니라 아래 항목을 바로 개발에 옮길 수 있도록 정의한다.

- 서비스 모듈 경계
- Spring Boot/WebFlux 패키지 구조
- PostgreSQL 엔티티 / 테이블 / 인덱스
- Neo4j 노드 / 관계 / 동기화 방식
- REST API / DTO / 요청-응답 규격
- Reactor 기반 서비스 흐름
- 인증/권한/스코프 전파 구조
- Outbox / 이벤트 계약 / 프로젝션 처리
- Twin 상태 집계 규칙
- What-if 시나리오 실행 구조
- React 화면과 API 매핑
- 단계별 구현 순서와 마이그레이션 규칙

본 문서는 다음 팀이 그대로 사용할 수 있게 설계되었다.

- 백엔드 아키텍트
- Spring Boot/WebFlux 개발자
- 프론트엔드 React 개발자
- 데이터/그래프 모델러
- 플랫폼 운영자

---

# 1. 구현 전략 요약

## 1.1 한 줄 요약

Axiom은 아래 4개 레이어를 분리 구현한다.

1. **Governance Layer**: 테넌트, 조직, 워크스페이스, 역할, 정책
2. **Process Definition Layer**: 프로세스 정의, 단계, 인터페이스, 규칙, KPI
3. **Graph & Impact Layer**: 프로세스 간 관계, 데이터 흐름, KPI 영향, Neo4j 탐색
4. **Twin Runtime Layer**: 인스턴스, 상태, 이벤트, 스냅샷, 시나리오

## 1.2 반드시 지켜야 할 구현 원칙

### 원칙 A. 모든 주요 API는 TenantContext 없이는 동작하지 않는다
`tenant_id`를 요청 본문에 직접 받지 말고, 인증 토큰 + 헤더 + 권한 정책을 통해 서버가 최종 결정한다.

### 원칙 B. Postgres가 Source of Truth, Neo4j는 Projection이다
정의/버전/권한/실행 데이터는 PostgreSQL에 저장하고, Neo4j는 관계 탐색용으로 동기화한다.

### 원칙 C. 그래프 갱신은 동기 쓰기보다 Outbox 기반 비동기 Projection이 기본이다
사용자 저장 트랜잭션과 Neo4j 갱신을 강결합하면 장애 전파가 커진다.

### 원칙 D. Twin은 이벤트 우선, 집계는 파생 상태다
현재 상태를 직접 수정하는 API를 최소화하고, 가급적 TwinEvent를 발행하여 상태를 만든다.

### 원칙 E. 정의 모델과 운영 모델을 섞지 않는다
ProcessDefinition/ProcessVersion과 ProcessInstance/TwinState는 분리 저장한다.

---

# 2. 서비스/모듈 구조

Axiom이 이미 모놀리식/모듈러 구조를 일부 갖고 있다면, 1차 구현은 모듈러 모놀리스로 시작하고 이후 서비스 분리를 가능하게 설계하는 것이 현실적이다.

## 2.1 추천 모듈 분리

```text
axiom-backend/
├── axiom-gateway
├── axiom-governance
├── axiom-process-model
├── axiom-digital-twin
├── axiom-simulation
├── axiom-graph-projection
├── axiom-common-security
├── axiom-common-events
├── axiom-common-web
└── axiom-common-test
```

초기에는 하나의 Spring Boot 앱 내부에 multi-module Maven/Gradle 구조로 시작해도 된다.

## 2.2 모듈 책임

### axiom-governance
- Tenant, OrgUnit, Workspace, Membership, RoleBinding
- Scope 정책 계산
- 사용자에게 허용된 tenant/workspace 목록 제공

### axiom-process-model
- ProcessDomain, ProcessGroup, ProcessDefinition, ProcessVersion
- StepDefinition, InterfaceContract, RuleDefinition, KPIBinding
- ProcessRelation 생성/수정

### axiom-digital-twin
- ProcessInstance, StepInstance, WorkItem, TwinEvent, TwinState, TwinSnapshot
- 운영 현황 집계 API

### axiom-simulation
- ScenarioDefinition, ScenarioRun, ScenarioChangeSet, ScenarioResult
- 현재 Snapshot 복제 후 가정 적용

### axiom-graph-projection
- Outbox 소비
- Neo4j 노드/엣지 upsert
- 영향도 탐색 쿼리

### axiom-common-security
- JWT 파싱
- TenantContext, WorkspaceScopeContext
- Reactive authorization manager

### axiom-common-events
- Event envelope
- Outbox relay 공통
- idempotency / version helpers

---

# 3. 패키지 구조

## 3.1 Governance 패키지

```text
aio/axiom/governance/
├── controller
├── service
├── domain
│   ├── entity
│   ├── enumtype
│   └── policy
├── repository
├── dto
│   ├── request
│   ├── response
│   └── projection
├── mapper
├── security
└── event
```

## 3.2 Process Model 패키지

```text
aio/axiom/processmodel/
├── controller
├── service
├── domain
│   ├── entity
│   ├── aggregate
│   └── enumtype
├── repository
├── dto
├── mapper
├── validation
└── event
```

## 3.3 Digital Twin 패키지

```text
aio/axiom/digitaltwin/
├── controller
├── service
├── domain
│   ├── entity
│   ├── calculator
│   └── enumtype
├── repository
├── dto
├── mapper
├── projection
└── event
```

## 3.4 Simulation 패키지

```text
aio/axiom/simulation/
├── controller
├── service
├── domain
├── repository
├── dto
├── mapper
└── engine
```

---

# 4. 멀티테넌시 및 권한 모델

## 4.1 TenantContext 규칙

모든 요청은 아래 컨텍스트를 가진다.

```java
public record TenantContext(
    UUID actorUserId,
    UUID tenantId,
    UUID orgUnitId,
    UUID workspaceId,
    Set<String> roleCodes,
    Set<String> permissionCodes,
    String timezone,
    Locale locale
) {}
```

## 4.2 컨텍스트 해석 우선순위

1. JWT에 포함된 기본 tenant_id
2. `X-Axiom-Tenant-Id` 헤더가 있을 경우, 사용자가 접근 가능한 tenant인지 검증
3. `X-Axiom-Workspace-Id`가 있으면 tenant와 일치 여부 검증
4. GovernanceService에서 최종 Scope 계산

## 4.3 권한 모델

권한은 단순 RBAC가 아니라 `Role + Scope + Policy Rule` 조합으로 간다.

### 권장 Permission 예시
- `tenant.read`
- `tenant.manage`
- `workspace.read`
- `workspace.manage`
- `process.read`
- `process.write`
- `process.publish`
- `process.relate`
- `twin.read`
- `twin.write`
- `scenario.run`
- `scenario.manage`
- `graph.read`
- `graph.admin`

### 권장 Role 예시
- PLATFORM_ADMIN
- TENANT_ADMIN
- DOMAIN_OWNER
- PROCESS_ARCHITECT
- PROCESS_ANALYST
- TWIN_OPERATOR
- PM
- PMO
- AUDITOR
- VIEWER

## 4.4 WebFlux 보안 구현 포인트

- `ReactiveAuthenticationManager`로 JWT 검증
- `ServerSecurityContextRepository` 또는 JWT stateless
- `ReactiveAuthorizationManager<AuthorizationContext>`에서 route별 permission 검사
- Controller 내에서 직접 tenant_id를 파라미터로 받더라도 무조건 `TenantContext`와 교차 검증

### 예시

```java
public Mono<TenantContext> currentTenantContext() {
    return ReactiveSecurityContextHolder.getContext()
        .map(SecurityContext::getAuthentication)
        .cast(AxiomAuthenticationToken.class)
        .map(AxiomAuthenticationToken::tenantContext);
}
```

---

# 5. PostgreSQL 스키마 명세

아래 스키마는 R2DBC/PostgreSQL 기준이다.

## 5.1 공통 컬럼 규칙

모든 주요 테이블은 아래 공통 컬럼을 가진다.

- `id uuid primary key`
- `tenant_id uuid not null`
- `created_at timestamptz not null`
- `updated_at timestamptz not null`
- `created_by uuid null`
- `updated_by uuid null`
- `version bigint not null default 0`  ← optimistic lock 용
- `is_deleted boolean not null default false`

## 5.2 Governance 테이블

### tenants

```sql
create table tenants (
  id uuid primary key,
  code varchar(100) not null unique,
  name varchar(255) not null,
  industry_type varchar(100),
  status varchar(30) not null,
  default_timezone varchar(64) not null,
  data_residency varchar(64),
  created_at timestamptz not null,
  updated_at timestamptz not null,
  version bigint not null default 0,
  is_deleted boolean not null default false
);
```

### org_units

```sql
create table org_units (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  parent_org_unit_id uuid null references org_units(id),
  code varchar(100) not null,
  name varchar(255) not null,
  org_type varchar(50) not null,
  owner_user_id uuid null,
  path varchar(1000) not null,
  created_at timestamptz not null,
  updated_at timestamptz not null,
  version bigint not null default 0,
  is_deleted boolean not null default false,
  unique (tenant_id, code)
);
create index idx_org_units_tenant_parent on org_units(tenant_id, parent_org_unit_id);
create index idx_org_units_tenant_path on org_units(tenant_id, path);
```

### workspaces

```sql
create table workspaces (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  org_unit_id uuid not null references org_units(id),
  code varchar(100) not null,
  name varchar(255) not null,
  workspace_type varchar(50) not null,
  visibility_policy varchar(50) not null,
  created_at timestamptz not null,
  updated_at timestamptz not null,
  version bigint not null default 0,
  is_deleted boolean not null default false,
  unique (tenant_id, code)
);
create index idx_workspaces_tenant_org on workspaces(tenant_id, org_unit_id);
```

### memberships

```sql
create table memberships (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  user_id uuid not null,
  org_unit_id uuid null references org_units(id),
  workspace_id uuid null references workspaces(id),
  role_code varchar(100) not null,
  status varchar(30) not null,
  effective_from timestamptz,
  effective_to timestamptz,
  created_at timestamptz not null,
  updated_at timestamptz not null,
  version bigint not null default 0,
  is_deleted boolean not null default false
);
create index idx_memberships_tenant_user on memberships(tenant_id, user_id);
create index idx_memberships_tenant_workspace on memberships(tenant_id, workspace_id);
```

## 5.3 Process Model 테이블

### process_domains

```sql
create table process_domains (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  workspace_id uuid not null references workspaces(id),
  code varchar(100) not null,
  name varchar(255) not null,
  description text,
  created_at timestamptz not null,
  updated_at timestamptz not null,
  version bigint not null default 0,
  is_deleted boolean not null default false,
  unique (tenant_id, workspace_id, code)
);
```

### process_groups

```sql
create table process_groups (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  domain_id uuid not null references process_domains(id),
  parent_group_id uuid null references process_groups(id),
  code varchar(100) not null,
  name varchar(255) not null,
  path varchar(1000) not null,
  display_order integer not null default 0,
  created_at timestamptz not null,
  updated_at timestamptz not null,
  version bigint not null default 0,
  is_deleted boolean not null default false,
  unique (tenant_id, domain_id, code)
);
create index idx_process_groups_tenant_domain on process_groups(tenant_id, domain_id);
```

### process_definitions

```sql
create table process_definitions (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  domain_id uuid not null references process_domains(id),
  group_id uuid null references process_groups(id),
  namespace varchar(300) not null,
  code varchar(100) not null,
  name varchar(255) not null,
  description text,
  process_type varchar(50) not null,
  lifecycle_status varchar(30) not null,
  owner_org_unit_id uuid null references org_units(id),
  primary_role_code varchar(100),
  current_version_no integer not null default 1,
  is_template boolean not null default false,
  template_source_id uuid null,
  created_at timestamptz not null,
  updated_at timestamptz not null,
  created_by uuid,
  updated_by uuid,
  version bigint not null default 0,
  is_deleted boolean not null default false,
  unique (tenant_id, namespace),
  unique (tenant_id, domain_id, code)
);
create index idx_process_definitions_tenant_domain on process_definitions(tenant_id, domain_id);
create index idx_process_definitions_tenant_group on process_definitions(tenant_id, group_id);
```

### process_versions

```sql
create table process_versions (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  process_definition_id uuid not null references process_definitions(id),
  version_no integer not null,
  status varchar(30) not null,
  source_type varchar(30) not null,
  parent_version_id uuid null references process_versions(id),
  change_summary text,
  published_at timestamptz,
  published_by uuid,
  valid_from timestamptz,
  valid_to timestamptz,
  created_at timestamptz not null,
  updated_at timestamptz not null,
  created_by uuid,
  updated_by uuid,
  version bigint not null default 0,
  is_deleted boolean not null default false,
  unique (tenant_id, process_definition_id, version_no)
);
create index idx_process_versions_tenant_definition on process_versions(tenant_id, process_definition_id);
create index idx_process_versions_tenant_status on process_versions(tenant_id, status);
```

### step_definitions

```sql
create table step_definitions (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  process_version_id uuid not null references process_versions(id),
  parent_step_id uuid null references step_definitions(id),
  code varchar(100) not null,
  name varchar(255) not null,
  step_type varchar(50) not null,
  actor_type varchar(50) not null,
  actor_ref varchar(200),
  input_contract_id uuid null,
  output_contract_id uuid null,
  sla_minutes integer,
  auto_executable boolean not null default false,
  display_order integer not null default 0,
  path varchar(1000) not null,
  created_at timestamptz not null,
  updated_at timestamptz not null,
  created_by uuid,
  updated_by uuid,
  version bigint not null default 0,
  is_deleted boolean not null default false,
  unique (tenant_id, process_version_id, code)
);
create index idx_step_definitions_version on step_definitions(tenant_id, process_version_id);
create index idx_step_definitions_parent on step_definitions(tenant_id, parent_step_id);
```

### interface_contracts

```sql
create table interface_contracts (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  workspace_id uuid not null references workspaces(id),
  code varchar(100) not null,
  name varchar(255) not null,
  contract_type varchar(50) not null,
  schema_json jsonb not null,
  semantic_type varchar(100),
  version_label varchar(50),
  created_at timestamptz not null,
  updated_at timestamptz not null,
  created_by uuid,
  updated_by uuid,
  version bigint not null default 0,
  is_deleted boolean not null default false,
  unique (tenant_id, workspace_id, code, version_label)
);
create index idx_interface_contracts_schema_gin on interface_contracts using gin(schema_json);
```

### rule_definitions

```sql
create table rule_definitions (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  workspace_id uuid not null references workspaces(id),
  code varchar(100) not null,
  name varchar(255) not null,
  rule_type varchar(50) not null,
  expression_language varchar(50) not null,
  expression_text text not null,
  severity varchar(30),
  description text,
  created_at timestamptz not null,
  updated_at timestamptz not null,
  created_by uuid,
  updated_by uuid,
  version bigint not null default 0,
  is_deleted boolean not null default false,
  unique (tenant_id, workspace_id, code)
);
```

### kpi_definitions

```sql
create table kpi_definitions (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  workspace_id uuid not null references workspaces(id),
  code varchar(100) not null,
  name varchar(255) not null,
  unit varchar(50),
  target_direction varchar(20) not null,
  aggregation_type varchar(30) not null,
  formula_text text,
  created_at timestamptz not null,
  updated_at timestamptz not null,
  created_by uuid,
  updated_by uuid,
  version bigint not null default 0,
  is_deleted boolean not null default false,
  unique (tenant_id, workspace_id, code)
);
```

### process_relation_edges

이 테이블은 그래프 Projection의 원천이다.

```sql
create table process_relation_edges (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  workspace_id uuid not null references workspaces(id),
  source_entity_type varchar(50) not null,
  source_entity_id uuid not null,
  target_entity_type varchar(50) not null,
  target_entity_id uuid not null,
  relation_type varchar(50) not null,
  weight numeric(10,4),
  condition_expression text,
  metadata_json jsonb,
  valid_from timestamptz,
  valid_to timestamptz,
  created_at timestamptz not null,
  updated_at timestamptz not null,
  created_by uuid,
  updated_by uuid,
  version bigint not null default 0,
  is_deleted boolean not null default false
);
create index idx_relation_edges_tenant_source on process_relation_edges(tenant_id, source_entity_type, source_entity_id);
create index idx_relation_edges_tenant_target on process_relation_edges(tenant_id, target_entity_type, target_entity_id);
create index idx_relation_edges_tenant_relation on process_relation_edges(tenant_id, relation_type);
create index idx_relation_edges_metadata_gin on process_relation_edges using gin(metadata_json);
```

## 5.4 Digital Twin 테이블

### process_instances

```sql
create table process_instances (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  workspace_id uuid not null references workspaces(id),
  process_definition_id uuid not null references process_definitions(id),
  process_version_id uuid not null references process_versions(id),
  business_key varchar(200),
  source_system varchar(100),
  status varchar(30) not null,
  priority varchar(30),
  started_at timestamptz,
  completed_at timestamptz,
  due_at timestamptz,
  current_step_id uuid null,
  root_instance_id uuid null,
  parent_instance_id uuid null,
  payload_json jsonb,
  created_at timestamptz not null,
  updated_at timestamptz not null,
  created_by uuid,
  updated_by uuid,
  version bigint not null default 0,
  is_deleted boolean not null default false,
  unique (tenant_id, workspace_id, business_key)
);
create index idx_process_instances_tenant_status on process_instances(tenant_id, workspace_id, status);
create index idx_process_instances_tenant_definition on process_instances(tenant_id, process_definition_id);
create index idx_process_instances_payload_gin on process_instances using gin(payload_json);
```

### step_instances

```sql
create table step_instances (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  process_instance_id uuid not null references process_instances(id),
  step_definition_id uuid not null references step_definitions(id),
  status varchar(30) not null,
  assigned_actor_type varchar(50),
  assigned_actor_ref varchar(200),
  entered_at timestamptz,
  started_at timestamptz,
  completed_at timestamptz,
  due_at timestamptz,
  wait_reason varchar(200),
  result_code varchar(100),
  payload_json jsonb,
  created_at timestamptz not null,
  updated_at timestamptz not null,
  created_by uuid,
  updated_by uuid,
  version bigint not null default 0,
  is_deleted boolean not null default false
);
create index idx_step_instances_process on step_instances(tenant_id, process_instance_id);
create index idx_step_instances_status on step_instances(tenant_id, status);
```

### twin_events

```sql
create table twin_events (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  workspace_id uuid not null references workspaces(id),
  event_type varchar(100) not null,
  aggregate_type varchar(50) not null,
  aggregate_id uuid not null,
  causation_id uuid,
  correlation_id uuid,
  idempotency_key varchar(200) not null,
  occurred_at timestamptz not null,
  payload_json jsonb not null,
  source_channel varchar(50) not null,
  processing_status varchar(30) not null,
  created_at timestamptz not null,
  updated_at timestamptz not null,
  version bigint not null default 0,
  is_deleted boolean not null default false,
  unique (tenant_id, idempotency_key)
);
create index idx_twin_events_aggregate on twin_events(tenant_id, aggregate_type, aggregate_id);
create index idx_twin_events_type_occurred on twin_events(tenant_id, event_type, occurred_at desc);
create index idx_twin_events_payload_gin on twin_events using gin(payload_json);
```

### twin_states

```sql
create table twin_states (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  workspace_id uuid not null references workspaces(id),
  entity_type varchar(50) not null,
  entity_id uuid not null,
  state_code varchar(50) not null,
  health_score numeric(5,2),
  sla_status varchar(30),
  queue_size integer,
  avg_cycle_time_minutes numeric(12,2),
  avg_wait_time_minutes numeric(12,2),
  exception_rate numeric(8,4),
  last_event_at timestamptz,
  snapshot_ref_id uuid,
  metrics_json jsonb,
  created_at timestamptz not null,
  updated_at timestamptz not null,
  version bigint not null default 0,
  is_deleted boolean not null default false,
  unique (tenant_id, workspace_id, entity_type, entity_id)
);
create index idx_twin_states_tenant_entity on twin_states(tenant_id, workspace_id, entity_type, entity_id);
create index idx_twin_states_metrics_gin on twin_states using gin(metrics_json);
```

### twin_snapshots

```sql
create table twin_snapshots (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  workspace_id uuid not null references workspaces(id),
  snapshot_type varchar(30) not null,
  entity_scope_type varchar(50) not null,
  entity_scope_id uuid,
  captured_at timestamptz not null,
  summary_json jsonb not null,
  created_at timestamptz not null,
  updated_at timestamptz not null,
  version bigint not null default 0,
  is_deleted boolean not null default false
);
create index idx_twin_snapshots_scope on twin_snapshots(tenant_id, workspace_id, entity_scope_type, entity_scope_id, captured_at desc);
create index idx_twin_snapshots_summary_gin on twin_snapshots using gin(summary_json);
```

## 5.5 Simulation 테이블

### scenario_definitions

```sql
create table scenario_definitions (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  workspace_id uuid not null references workspaces(id),
  code varchar(100) not null,
  name varchar(255) not null,
  base_snapshot_id uuid not null references twin_snapshots(id),
  scenario_type varchar(50) not null,
  description text,
  status varchar(30) not null,
  created_at timestamptz not null,
  updated_at timestamptz not null,
  created_by uuid,
  updated_by uuid,
  version bigint not null default 0,
  is_deleted boolean not null default false,
  unique (tenant_id, workspace_id, code)
);
```

### scenario_change_sets

```sql
create table scenario_change_sets (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  scenario_definition_id uuid not null references scenario_definitions(id),
  change_type varchar(50) not null,
  target_entity_type varchar(50) not null,
  target_entity_id uuid not null,
  patch_json jsonb not null,
  display_order integer not null default 0,
  created_at timestamptz not null,
  updated_at timestamptz not null,
  version bigint not null default 0,
  is_deleted boolean not null default false
);
create index idx_scenario_change_sets_scenario on scenario_change_sets(tenant_id, scenario_definition_id);
```

### scenario_runs

```sql
create table scenario_runs (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  workspace_id uuid not null references workspaces(id),
  scenario_definition_id uuid not null references scenario_definitions(id),
  base_snapshot_id uuid not null references twin_snapshots(id),
  status varchar(30) not null,
  started_at timestamptz,
  completed_at timestamptz,
  result_summary_json jsonb,
  error_message text,
  created_at timestamptz not null,
  updated_at timestamptz not null,
  created_by uuid,
  updated_by uuid,
  version bigint not null default 0,
  is_deleted boolean not null default false
);
```

## 5.6 Outbox 테이블

```sql
create table event_outbox (
  id uuid primary key,
  tenant_id uuid not null,
  aggregate_type varchar(100) not null,
  aggregate_id uuid not null,
  event_type varchar(100) not null,
  event_version integer not null,
  idempotency_key varchar(200) not null,
  payload_json jsonb not null,
  headers_json jsonb,
  published boolean not null default false,
  published_at timestamptz,
  retry_count integer not null default 0,
  created_at timestamptz not null,
  unique (tenant_id, idempotency_key)
);
create index idx_outbox_published_created on event_outbox(published, created_at);
```

---

# 6. Neo4j 모델 명세

Neo4j는 프로세스 관계와 영향도 탐색, 경로 분석, 시맨틱 보강에 사용한다.

## 6.1 노드 타입

- `Tenant`
- `OrgUnit`
- `Workspace`
- `ProcessDomain`
- `ProcessGroup`
- `ProcessDefinition`
- `ProcessVersion`
- `StepDefinition`
- `InterfaceContract`
- `RuleDefinition`
- `KpiDefinition`
- `TwinEntity`
- `TwinSnapshot`

## 6.2 공통 노드 속성

```cypher
{
  id: "uuid",
  tenantId: "uuid",
  workspaceId: "uuid",
  code: "...",
  name: "...",
  status: "...",
  version: 3,
  updatedAt: datetime(...)
}
```

## 6.3 관계 타입

- `CONTAINS`
- `BELONGS_TO`
- `HAS_VERSION`
- `HAS_STEP`
- `TRIGGERS`
- `CONSUMES`
- `PRODUCES`
- `BLOCKS`
- `DEPENDS_ON`
- `HANDOFF_TO`
- `GOVERNED_BY`
- `MEASURED_BY`
- `INFLUENCES_KPI`
- `CURRENT_STATE`
- `SNAPSHOTTED_AS`

## 6.4 제약/인덱스 예시

```cypher
CREATE CONSTRAINT tenant_id IF NOT EXISTS FOR (n:Tenant) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT process_definition_id IF NOT EXISTS FOR (n:ProcessDefinition) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT process_version_id IF NOT EXISTS FOR (n:ProcessVersion) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT step_definition_id IF NOT EXISTS FOR (n:StepDefinition) REQUIRE n.id IS UNIQUE;
CREATE INDEX process_definition_tenant IF NOT EXISTS FOR (n:ProcessDefinition) ON (n.tenantId);
CREATE INDEX step_definition_tenant IF NOT EXISTS FOR (n:StepDefinition) ON (n.tenantId);
```

## 6.5 Projection 원칙

- Postgres 저장 성공 후 Outbox 생성
- GraphProjectionConsumer가 이벤트 수신
- Neo4j `MERGE`로 idempotent upsert
- 삭제는 hard delete보다 `active=false` soft projection 권장

---

# 7. 자바 엔티티/애그리게이트 설계

## 7.1 공통 Base Entity

```java
@Getter
@Setter
public abstract class BaseTenantEntity {
    @Id
    private UUID id;
    private UUID tenantId;
    private Instant createdAt;
    private Instant updatedAt;
    private UUID createdBy;
    private UUID updatedBy;
    private Long version;
    private Boolean isDeleted;
}
```

## 7.2 Governance 엔티티 예시

```java
@Table("tenants")
public class TenantEntity extends BaseTenantEntity {
    private String code;
    private String name;
    private String industryType;
    private TenantStatus status;
    private String defaultTimezone;
    private String dataResidency;
}
```

```java
@Table("workspaces")
public class WorkspaceEntity extends BaseTenantEntity {
    private UUID orgUnitId;
    private String code;
    private String name;
    private WorkspaceType workspaceType;
    private VisibilityPolicy visibilityPolicy;
}
```

## 7.3 Process Model 엔티티 예시

```java
@Table("process_definitions")
public class ProcessDefinitionEntity extends BaseTenantEntity {
    private UUID domainId;
    private UUID groupId;
    private String namespace;
    private String code;
    private String name;
    private String description;
    private ProcessType processType;
    private LifecycleStatus lifecycleStatus;
    private UUID ownerOrgUnitId;
    private String primaryRoleCode;
    private Integer currentVersionNo;
    private Boolean isTemplate;
    private UUID templateSourceId;
}
```

```java
@Table("process_relation_edges")
public class ProcessRelationEdgeEntity extends BaseTenantEntity {
    private UUID workspaceId;
    private String sourceEntityType;
    private UUID sourceEntityId;
    private String targetEntityType;
    private UUID targetEntityId;
    private RelationType relationType;
    private BigDecimal weight;
    private String conditionExpression;
    private Json metadataJson;
    private Instant validFrom;
    private Instant validTo;
}
```

## 7.4 Digital Twin 엔티티 예시

```java
@Table("process_instances")
public class ProcessInstanceEntity extends BaseTenantEntity {
    private UUID workspaceId;
    private UUID processDefinitionId;
    private UUID processVersionId;
    private String businessKey;
    private String sourceSystem;
    private InstanceStatus status;
    private PriorityCode priority;
    private Instant startedAt;
    private Instant completedAt;
    private Instant dueAt;
    private UUID currentStepId;
    private UUID rootInstanceId;
    private UUID parentInstanceId;
    private Json payloadJson;
}
```

```java
@Table("twin_states")
public class TwinStateEntity extends BaseTenantEntity {
    private UUID workspaceId;
    private String entityType;
    private UUID entityId;
    private String stateCode;
    private BigDecimal healthScore;
    private String slaStatus;
    private Integer queueSize;
    private BigDecimal avgCycleTimeMinutes;
    private BigDecimal avgWaitTimeMinutes;
    private BigDecimal exceptionRate;
    private Instant lastEventAt;
    private UUID snapshotRefId;
    private Json metricsJson;
}
```

## 7.5 애그리게이트 규칙

R2DBC는 JPA Aggregate처럼 자동 연관 저장이 약하므로, Aggregate는 서비스 계층에서 명시적으로 다룬다.

### Aggregate 추천
- `ProcessDefinitionAggregate`
  - ProcessDefinitionEntity
  - current draft/published version
  - step definitions
  - interface bindings
  - rule bindings
  - kpi bindings

- `ProcessRuntimeAggregate`
  - ProcessInstanceEntity
  - current step instance
  - recent twin events
  - current twin state

---

# 8. Enum 설계

## 8.1 공통 Enum

```java
public enum TenantStatus { ACTIVE, SUSPENDED, ARCHIVED }
public enum WorkspaceType { PROCESS, ANALYTICS, TWIN, SANDBOX }
public enum VisibilityPolicy { PRIVATE, ORG_SHARED, TENANT_SHARED }
```

## 8.2 Process Enum

```java
public enum ProcessType { HUMAN, SYSTEM, HYBRID, AI_AGENT, PIPELINE }
public enum LifecycleStatus { DRAFT, REVIEW, PUBLISHED, DEPRECATED, ARCHIVED }
public enum StepType { START, TASK, DECISION, WAIT, END, SUBPROCESS, CHECKPOINT }
public enum ActorType { USER, ROLE, SYSTEM, AGENT, EXTERNAL }
public enum RelationType {
    TRIGGERS, CONSUMES, PRODUCES, BLOCKS, DEPENDS_ON,
    HANDOFF_TO, GOVERNED_BY, MEASURED_BY, INFLUENCES_KPI
}
```

## 8.3 Twin Enum

```java
public enum InstanceStatus { CREATED, QUEUED, RUNNING, WAITING, COMPLETED, FAILED, CANCELLED }
public enum TwinEventStatus { RECEIVED, PROJECTED, FAILED, IGNORED }
public enum SnapshotType { SCHEDULED, MANUAL, EVENT_DRIVEN, SCENARIO_BASE }
public enum ScenarioRunStatus { PENDING, RUNNING, COMPLETED, FAILED }
```

---

# 9. Repository 명세

## 9.1 R2DBC Repository 예시

```java
public interface ProcessDefinitionRepository extends ReactiveCrudRepository<ProcessDefinitionEntity, UUID> {
    Flux<ProcessDefinitionEntity> findByTenantIdAndDomainIdAndIsDeletedFalse(UUID tenantId, UUID domainId);
    Mono<ProcessDefinitionEntity> findByTenantIdAndIdAndIsDeletedFalse(UUID tenantId, UUID id);
    Mono<Boolean> existsByTenantIdAndNamespaceAndIsDeletedFalse(UUID tenantId, String namespace);
}
```

```java
public interface ProcessRelationEdgeRepository extends ReactiveCrudRepository<ProcessRelationEdgeEntity, UUID> {
    Flux<ProcessRelationEdgeEntity> findByTenantIdAndWorkspaceIdAndSourceEntityTypeAndSourceEntityIdAndIsDeletedFalse(
        UUID tenantId, UUID workspaceId, String sourceEntityType, UUID sourceEntityId);
}
```

## 9.2 Custom Query Repository 필요한 곳

- 계층 탐색(OrgUnit path, ProcessGroup path)
- Twin 집계 조회
- KPI summary
- Snapshot 생성용 통계 조회

### 예시

```java
public interface TwinDashboardQueryRepository {
    Mono<TwinWorkspaceSummaryProjection> fetchWorkspaceSummary(UUID tenantId, UUID workspaceId);
    Flux<TwinProcessHealthProjection> fetchProcessHealthList(UUID tenantId, UUID workspaceId, String status);
}
```

---

# 10. DTO 설계

## 10.1 공통 응답 규격

```java
public record ApiResponse<T>(
    boolean success,
    T data,
    ErrorResponse error,
    String traceId,
    Instant timestamp
) {}
```

## 10.2 Governance DTO

```java
public record CreateTenantRequest(
    @NotBlank String code,
    @NotBlank String name,
    String industryType,
    @NotBlank String defaultTimezone,
    String dataResidency
) {}
```

```java
public record WorkspaceResponse(
    UUID id,
    UUID tenantId,
    UUID orgUnitId,
    String code,
    String name,
    String workspaceType,
    String visibilityPolicy,
    Instant createdAt,
    Instant updatedAt
) {}
```

## 10.3 Process DTO

```java
public record CreateProcessDefinitionRequest(
    UUID domainId,
    UUID groupId,
    @NotBlank String namespace,
    @NotBlank String code,
    @NotBlank String name,
    String description,
    String processType,
    UUID ownerOrgUnitId,
    String primaryRoleCode,
    boolean template
) {}
```

```java
public record UpsertStepDefinitionRequest(
    UUID id,
    UUID parentStepId,
    @NotBlank String code,
    @NotBlank String name,
    @NotBlank String stepType,
    @NotBlank String actorType,
    String actorRef,
    UUID inputContractId,
    UUID outputContractId,
    Integer slaMinutes,
    boolean autoExecutable,
    Integer displayOrder
) {}
```

```java
public record CreateProcessRelationRequest(
    UUID workspaceId,
    @NotBlank String sourceEntityType,
    @NotNull UUID sourceEntityId,
    @NotBlank String targetEntityType,
    @NotNull UUID targetEntityId,
    @NotBlank String relationType,
    BigDecimal weight,
    String conditionExpression,
    Map<String, Object> metadata
) {}
```

## 10.4 Twin DTO

```java
public record StartProcessInstanceRequest(
    UUID workspaceId,
    UUID processDefinitionId,
    UUID processVersionId,
    String businessKey,
    String sourceSystem,
    String priority,
    Instant dueAt,
    Map<String, Object> payload
) {}
```

```java
public record PublishTwinEventRequest(
    UUID workspaceId,
    @NotBlank String eventType,
    @NotBlank String aggregateType,
    @NotNull UUID aggregateId,
    UUID causationId,
    UUID correlationId,
    @NotBlank String idempotencyKey,
    Instant occurredAt,
    Map<String, Object> payload,
    @NotBlank String sourceChannel
) {}
```

```java
public record TwinStateResponse(
    UUID entityId,
    String entityType,
    String stateCode,
    BigDecimal healthScore,
    String slaStatus,
    Integer queueSize,
    BigDecimal avgCycleTimeMinutes,
    BigDecimal avgWaitTimeMinutes,
    BigDecimal exceptionRate,
    Instant lastEventAt,
    Map<String, Object> metrics
) {}
```

## 10.5 Scenario DTO

```java
public record CreateScenarioRequest(
    UUID workspaceId,
    String code,
    String name,
    UUID baseSnapshotId,
    String scenarioType,
    String description,
    List<ScenarioChangeSetItem> changes
) {}
```

```java
public record ScenarioChangeSetItem(
    String changeType,
    String targetEntityType,
    UUID targetEntityId,
    Map<String, Object> patch,
    Integer displayOrder
) {}
```

---

# 11. REST API 명세

아래 경로는 `/api/v1` 기준이다.

## 11.1 Governance API

### Tenant
- `GET /governance/tenants/me`
- `POST /governance/tenants`
- `GET /governance/tenants/{tenantId}`
- `PATCH /governance/tenants/{tenantId}`

### OrgUnit
- `POST /governance/org-units`
- `GET /governance/org-units/tree?workspaceId=...`
- `PATCH /governance/org-units/{orgUnitId}`

### Workspace
- `POST /governance/workspaces`
- `GET /governance/workspaces`
- `GET /governance/workspaces/{workspaceId}`
- `PATCH /governance/workspaces/{workspaceId}`
- `GET /governance/workspaces/{workspaceId}/members`

## 11.2 Process Model API

### Domain/Group
- `POST /process/domains`
- `GET /process/domains?workspaceId=...`
- `POST /process/groups`
- `GET /process/groups/tree?domainId=...`

### ProcessDefinition
- `POST /process/definitions`
- `GET /process/definitions?domainId=...&groupId=...&status=...`
- `GET /process/definitions/{id}`
- `PATCH /process/definitions/{id}`
- `POST /process/definitions/{id}/publish`
- `POST /process/definitions/{id}/clone`

### Version/Step
- `GET /process/definitions/{id}/versions`
- `POST /process/definitions/{id}/versions/{versionNo}/steps:bulk-upsert`
- `GET /process/versions/{versionId}/steps`

### Relation / Impact
- `POST /process/relations`
- `DELETE /process/relations/{relationId}`
- `GET /process/definitions/{id}/relations`
- `GET /process/definitions/{id}/impact?direction=UPSTREAM&depth=3`
- `GET /process/definitions/{id}/graph`

## 11.3 Digital Twin API

### Runtime
- `POST /twin/instances`
- `GET /twin/instances/{id}`
- `GET /twin/instances?workspaceId=...&status=RUNNING`
- `POST /twin/events`
- `GET /twin/states/{entityType}/{entityId}`
- `GET /twin/dashboard/workspaces/{workspaceId}`
- `GET /twin/dashboard/workspaces/{workspaceId}/processes`
- `POST /twin/snapshots`
- `GET /twin/snapshots?workspaceId=...`

## 11.4 Scenario API

- `POST /simulation/scenarios`
- `GET /simulation/scenarios?workspaceId=...`
- `GET /simulation/scenarios/{scenarioId}`
- `POST /simulation/scenarios/{scenarioId}/runs`
- `GET /simulation/runs/{runId}`
- `GET /simulation/runs/{runId}/diff`

---

# 12. 요청/응답 예시

## 12.1 프로세스 생성

### Request

```json
{
  "domainId": "0b7f5d78-8c7a-48d6-918b-6f4a0bdbbd62",
  "groupId": "fc50d0ef-a4b6-4ed0-93ea-5d145b378741",
  "namespace": "insurance.claim.review",
  "code": "CLAIM_REVIEW",
  "name": "보험금 청구 심사",
  "description": "접수된 보험금 청구건에 대한 심사 프로세스",
  "processType": "HYBRID",
  "ownerOrgUnitId": "70561c1b-15cc-4301-a4f3-6ac5d37b7baf",
  "primaryRoleCode": "PROCESS_ANALYST",
  "template": false
}
```

### Response

```json
{
  "success": true,
  "data": {
    "id": "6c0b31be-3c77-42a1-8d5c-bb1e56f2fc23",
    "namespace": "insurance.claim.review",
    "code": "CLAIM_REVIEW",
    "name": "보험금 청구 심사",
    "lifecycleStatus": "DRAFT",
    "currentVersionNo": 1,
    "createdAt": "2026-03-23T12:10:00Z"
  },
  "error": null,
  "traceId": "8cfcbbe7de2046be",
  "timestamp": "2026-03-23T12:10:00Z"
}
```

## 12.2 Twin 이벤트 발행

```json
{
  "workspaceId": "e5fcb001-c804-41f5-8e42-bd0f0f4aa012",
  "eventType": "process.step.entered",
  "aggregateType": "PROCESS_INSTANCE",
  "aggregateId": "7c99939d-b0b2-4f8c-a286-65d4d6acbe28",
  "idempotencyKey": "claim-20260323-0001-step-entered-02",
  "occurredAt": "2026-03-23T12:20:00Z",
  "payload": {
    "stepDefinitionId": "28c7d0fd-3bcf-4a3b-a4c5-873db4f4c8aa",
    "stepCode": "MEDICAL_REVIEW",
    "queueSize": 43,
    "assigneePool": "medical-review-team"
  },
  "sourceChannel": "manual-ui"
}
```

---

# 13. 서비스 계층 설계

## 13.1 GovernanceService

주요 책임:
- 현재 사용자의 tenant/workspace scope 계산
- membership 기반 접근 가능 범위 조회
- workspace 전환 시 scope 재계산

```java
public interface GovernanceService {
    Mono<TenantContext> resolveTenantContext(Authentication authentication, UUID requestedTenantId, UUID requestedWorkspaceId);
    Flux<WorkspaceResponse> listAccessibleWorkspaces(UUID userId, UUID tenantId);
    Mono<Boolean> hasPermission(UUID userId, UUID tenantId, UUID workspaceId, String permissionCode);
}
```

## 13.2 ProcessDefinitionService

주요 책임:
- 프로세스 정의 생성/수정
- 버전 발행
- 단계 bulk upsert
- relation edge 생성
- outbox 이벤트 기록

```java
public interface ProcessDefinitionService {
    Mono<ProcessDefinitionResponse> create(TenantContext ctx, CreateProcessDefinitionRequest request);
    Mono<ProcessDefinitionResponse> update(TenantContext ctx, UUID id, UpdateProcessDefinitionRequest request);
    Mono<ProcessVersionResponse> publish(TenantContext ctx, UUID definitionId);
    Flux<StepDefinitionResponse> bulkUpsertSteps(TenantContext ctx, UUID definitionId, Integer versionNo, List<UpsertStepDefinitionRequest> requests);
}
```

## 13.3 ImpactAnalysisService

주요 책임:
- Neo4j 영향도 탐색
- Upstream/Downstream path 반환
- relation type 필터링

```java
public interface ImpactAnalysisService {
    Mono<ImpactGraphResponse> findImpactGraph(TenantContext ctx, UUID processDefinitionId, Direction direction, int depth);
}
```

## 13.4 TwinRuntimeService

주요 책임:
- 인스턴스 생성
- TwinEvent 적재
- 상태 계산 트리거
- 작업 현황 집계

```java
public interface TwinRuntimeService {
    Mono<ProcessInstanceResponse> startInstance(TenantContext ctx, StartProcessInstanceRequest request);
    Mono<TwinEventResponse> publishEvent(TenantContext ctx, PublishTwinEventRequest request);
    Mono<TwinStateResponse> getCurrentState(TenantContext ctx, String entityType, UUID entityId);
    Mono<TwinWorkspaceDashboardResponse> getWorkspaceDashboard(TenantContext ctx, UUID workspaceId);
}
```

## 13.5 ScenarioService

주요 책임:
- 시나리오 정의 저장
- Snapshot clone
- ChangeSet 적용
- 결과 계산

```java
public interface ScenarioService {
    Mono<ScenarioResponse> createScenario(TenantContext ctx, CreateScenarioRequest request);
    Mono<ScenarioRunResponse> runScenario(TenantContext ctx, UUID scenarioId);
    Mono<ScenarioDiffResponse> getDiff(TenantContext ctx, UUID runId);
}
```

---

# 14. Reactor/WebFlux 흐름 설계

## 14.1 프로세스 저장 흐름

```text
Controller
  → Security/Scope Check
  → Validation
  → ProcessDefinitionService
      → save process_definitions
      → save process_versions (draft if new)
      → insert outbox event
  → return response
```

### 구현 포인트
- `TransactionalOperator`로 R2DBC 트랜잭션 묶기
- Outbox insert를 동일 트랜잭션에 포함
- Neo4j 저장은 하지 않음

## 14.2 Twin 이벤트 처리 흐름

```text
POST /twin/events
  → TwinRuntimeService.publishEvent
      → dedupe by idempotency_key
      → insert twin_events
      → insert outbox event (twin.event.received)
  → TwinProjectorConsumer
      → load event
      → calculate state delta
      → upsert twin_states
      → optionally create snapshot
```

## 14.3 Scenario 실행 흐름

```text
POST /simulation/scenarios/{id}/runs
  → create scenario_run(status=PENDING)
  → publish scenario.run.requested event
  → async engine consumes
      → load base snapshot
      → apply change sets
      → compute derived metrics
      → write result summary
      → update run status COMPLETED
```

---

# 15. 트랜잭션 경계와 일관성 규칙

## 15.1 강일관성 필요한 것

- Tenant / Workspace 생성
- ProcessDefinition + ProcessVersion 동시 생성
- Step bulk upsert
- TwinEvent 적재와 idempotency 보장
- ScenarioDefinition + ChangeSet 저장

## 15.2 결과적 일관성 허용 가능한 것

- Neo4j projection
- Twin dashboard summary
- Snapshot background generation
- 시뮬레이션 결과 캐시

## 15.3 멱등성 규칙

### Twin 이벤트
`tenant_id + idempotency_key` unique

### Outbox relay
`event_outbox.id` 기준 at-least-once 전송 + 소비자 측 dedupe

### Neo4j projection
`MERGE (n {id: $id})` + relationship unique key metadata 활용

---

# 16. Outbox / 이벤트 계약 명세

## 16.1 이벤트 Envelope

```json
{
  "eventId": "uuid",
  "tenantId": "uuid",
  "workspaceId": "uuid",
  "aggregateType": "PROCESS_DEFINITION",
  "aggregateId": "uuid",
  "eventType": "process.definition.created",
  "eventVersion": 1,
  "occurredAt": "2026-03-23T12:00:00Z",
  "actorUserId": "uuid",
  "idempotencyKey": "...",
  "payload": {},
  "headers": {
    "traceId": "...",
    "correlationId": "..."
  }
}
```

## 16.2 핵심 이벤트 목록

### Governance
- `tenant.created`
- `workspace.created`
- `membership.assigned`

### Process Model
- `process.definition.created`
- `process.definition.updated`
- `process.version.published`
- `process.steps.bulk_upserted`
- `process.relation.created`
- `process.relation.deleted`

### Digital Twin
- `process.instance.started`
- `process.instance.completed`
- `process.step.entered`
- `process.step.completed`
- `process.instance.failed`
- `twin.state.updated`
- `twin.snapshot.created`

### Simulation
- `scenario.created`
- `scenario.run.requested`
- `scenario.run.completed`
- `scenario.run.failed`

## 16.3 Graph Projection가 구독해야 할 이벤트

- `process.definition.created`
- `process.definition.updated`
- `process.version.published`
- `process.steps.bulk_upserted`
- `process.relation.created`
- `process.relation.deleted`
- `twin.state.updated` (선택)

---

# 17. Neo4j Projection 구현 명세

## 17.1 Projection Consumer 구조

```text
GraphProjectionConsumer
├── ProcessDefinitionProjector
├── ProcessRelationProjector
├── TwinStateProjector
└── GraphProjectionErrorHandler
```

## 17.2 예시 Cypher

### ProcessDefinition upsert

```cypher
MERGE (p:ProcessDefinition {id: $id})
SET p.tenantId = $tenantId,
    p.workspaceId = $workspaceId,
    p.code = $code,
    p.name = $name,
    p.namespace = $namespace,
    p.status = $status,
    p.updatedAt = datetime($updatedAt)
```

### Relation upsert

```cypher
MATCH (s {id: $sourceId}), (t {id: $targetId})
MERGE (s)-[r:TRIGGERS {edgeId: $edgeId}]->(t)
SET r.tenantId = $tenantId,
    r.workspaceId = $workspaceId,
    r.weight = $weight,
    r.updatedAt = datetime($updatedAt)
```

## 17.3 영향도 탐색 쿼리 예시

```cypher
MATCH p=(root:ProcessDefinition {id: $rootId, tenantId: $tenantId})-[:TRIGGERS|BLOCKS|DEPENDS_ON*1..3]->(n)
RETURN p
```

업무상 필요하면 relation type 필터, workspace 제한, active flag를 추가한다.

---

# 18. Twin 상태 계산 규칙

TwinState는 원장 데이터가 아니라 파생 상태다. 아래 계산 규칙을 명확히 두어야 한다.

## 18.1 계산 입력

- 최근 TwinEvent
- ProcessInstance 상태
- StepInstance 진행 상태
- KPI 측정값
- 선택적으로 외부 시스템 metric

## 18.2 핵심 파생 필드 계산

### state_code
- RUNNING / WAITING / BLOCKED / DEGRADED / HEALTHY / FAILED

### health_score
예시 계산식:

```text
health_score =
  100
  - overdue_ratio * 25
  - exception_rate * 30
  - queue_pressure_score * 20
  - cycle_time_breach_score * 25
```

### sla_status
- ON_TRACK
- AT_RISK
- BREACHED

### queue_size
현재 WAITING / QUEUED step instance count

### avg_cycle_time_minutes
최근 N건 completed instance 평균

### exception_rate
최근 N건 중 failed / exception count 비율

## 18.3 Snapshot 생성 정책

### 자동 생성 조건
- 주기 스케줄(예: 15분)
- 주요 상태 급변(health_score 15점 이상 하락)
- 시나리오 실행 전 baseline capture
- 수동 버튼 요청

---

# 19. What-if / 시나리오 엔진 명세

초기 버전은 정교한 이산사건시뮬레이션보다, **규칙 기반 비교 시뮬레이션**으로 시작하는 것이 합리적이다.

## 19.1 지원할 변경 유형

- `RESOURCE_CAPACITY_CHANGE`
- `STEP_SLA_CHANGE`
- `ROUTING_RULE_CHANGE`
- `AUTOMATION_RATE_CHANGE`
- `PRIORITY_POLICY_CHANGE`
- `THRESHOLD_RULE_CHANGE`

## 19.2 시나리오 실행 순서

1. base snapshot 로드
2. 관련 process/twin state 로드
3. change set 순서대로 patch 적용
4. 영향 그래프를 따라 downstream recalculation
5. KPI diff 계산
6. 결과 요약 저장

## 19.3 결과 예시

- 평균 처리시간 -12%
- 대기열 43 → 27
- SLA breach risk 18% → 9%
- 심사 인력 2명 증원 시 지급 승인 단계 지연은 8%만 개선
- 실제 병목은 문서 보완 단계에 존재

즉, 단순 수치 변환이 아니라 **그래프 영향 전파를 반영한 설명형 결과**가 핵심이다.

---

# 20. Controller 설계 샘플

## 20.1 ProcessDefinitionController

```java
@RestController
@RequestMapping("/api/v1/process/definitions")
@RequiredArgsConstructor
public class ProcessDefinitionController {

    private final ProcessDefinitionService processDefinitionService;
    private final TenantContextFacade tenantContextFacade;

    @PostMapping
    public Mono<ApiResponse<ProcessDefinitionResponse>> create(@Valid @RequestBody CreateProcessDefinitionRequest request) {
        return tenantContextFacade.current()
            .flatMap(ctx -> processDefinitionService.create(ctx, request))
            .map(ApiResponses::success);
    }

    @PostMapping("/{id}/publish")
    public Mono<ApiResponse<ProcessVersionResponse>> publish(@PathVariable UUID id) {
        return tenantContextFacade.current()
            .flatMap(ctx -> processDefinitionService.publish(ctx, id))
            .map(ApiResponses::success);
    }
}
```

## 20.2 TwinRuntimeController

```java
@RestController
@RequestMapping("/api/v1/twin")
@RequiredArgsConstructor
public class TwinRuntimeController {

    private final TwinRuntimeService twinRuntimeService;
    private final TenantContextFacade tenantContextFacade;

    @PostMapping("/events")
    public Mono<ApiResponse<TwinEventResponse>> publishEvent(@Valid @RequestBody PublishTwinEventRequest request) {
        return tenantContextFacade.current()
            .flatMap(ctx -> twinRuntimeService.publishEvent(ctx, request))
            .map(ApiResponses::success);
    }
}
```

---

# 21. Validation 규칙

## 21.1 프로세스 정의 저장 시

- namespace는 tenant 내 unique
- 같은 process version 내 step code unique
- input/output contract는 같은 tenant/workspace 소속이어야 함
- PUBLISHED 버전은 직접 수정 불가, clone 후 새 버전 생성

## 21.2 relation edge 저장 시

- source/target는 같은 tenant여야 함
- workspace 간 관계를 허용할지 정책으로 결정
- 자기 자신으로의 동일 relation은 일부 타입만 허용
- relation_type 조합 검증 필요
  - 예: `KPI -> PRODUCES -> Process`는 금지

## 21.3 twin event 저장 시

- idempotency_key 필수
- occurred_at 미래 시간 허용 범위 제한
- aggregate_type + aggregate_id 실제 존재 여부 검증
- payload schema 검증 선택 적용

---

# 22. 에러 처리 규격

## 22.1 에러 코드 예시

- `TENANT_SCOPE_INVALID`
- `WORKSPACE_ACCESS_DENIED`
- `PROCESS_NAMESPACE_DUPLICATED`
- `PROCESS_VERSION_NOT_EDITABLE`
- `STEP_CODE_DUPLICATED`
- `RELATION_TARGET_NOT_FOUND`
- `TWIN_EVENT_DUPLICATED`
- `SCENARIO_BASE_SNAPSHOT_NOT_FOUND`
- `GRAPH_PROJECTION_FAILED`

## 22.2 ErrorResponse

```java
public record ErrorResponse(
    String code,
    String message,
    Map<String, Object> details
) {}
```

---

# 23. 캐시와 성능 전략

## 23.1 Redis 캐시 대상

- 사용자별 accessible workspace 목록
- ProcessDefinition summary
- Graph exploration short-lived result
- Twin dashboard summary (30~60초)

## 23.2 캐시 금지 대상

- 권한 판정 최종 결과를 장시간 캐시
- Twin event 원장
- Scenario run 상태

## 23.3 페이지네이션 기준

- ProcessDefinition list: cursor 또는 offset 50~100
- ProcessInstance list: cursor 기반 권장
- TwinEvent list: occurred_at desc + cursor

---

# 24. 관측성/운영 설계

## 24.1 필수 로그 필드

- traceId
- tenantId
- workspaceId
- actorUserId
- aggregateType
- aggregateId
- eventType
- scenarioRunId

## 24.2 메트릭

- API latency by module
- outbox lag
- graph projection retry count
- twin event processing latency
- scenario run duration
- snapshot generation duration

## 24.3 알림 포인트

- outbox relay 5분 이상 적체
- graph projection failure rate > 3%
- twin state stale > 15분
- scenario failure count 급증

---

# 25. 테스트 전략

## 25.1 단위 테스트

- Tenant scope resolver
- permission policy
- namespace uniqueness validator
- relation type validator
- twin state calculator
- scenario patch applier

## 25.2 통합 테스트

- WebFlux controller + R2DBC + Testcontainers(Postgres)
- Neo4j projection consumer + Testcontainers(Neo4j)
- outbox relay idempotency
- process publish workflow
- twin event ingestion → state update end-to-end

## 25.3 계약 테스트

- REST DTO schema
- event envelope schema
- Neo4j projection event contract

---

# 26. React 화면 구조와 API 매핑

## 26.1 화면 트리

```text
/tenant-admin
  /tenants
  /org-units
  /workspaces

/process-studio
  /domains
  /groups
  /definitions
  /definitions/:id
  /definitions/:id/graph
  /definitions/:id/impact

/digital-twin
  /cockpit
  /instances
  /states
  /snapshots

/simulation
  /scenarios
  /scenarios/:id
  /runs/:id
```

## 26.2 주요 React 컴포넌트

### Tenant Admin
- `TenantListPage.tsx`
- `OrgUnitTreePage.tsx`
- `WorkspaceListPage.tsx`
- `MembershipMatrixPage.tsx`

### Process Studio
- `ProcessDomainPage.tsx`
- `ProcessGroupTree.tsx`
- `ProcessDefinitionListPage.tsx`
- `ProcessDefinitionEditorPage.tsx`
- `StepCanvas.tsx`
- `ProcessRelationPanel.tsx`
- `ImpactExplorerPage.tsx`

### Digital Twin
- `TwinCockpitPage.tsx`
- `TwinProcessHealthTable.tsx`
- `TwinStateDrawer.tsx`
- `TwinSnapshotTimeline.tsx`
- `ProcessInstanceListPage.tsx`

### Simulation
- `ScenarioListPage.tsx`
- `ScenarioEditorPage.tsx`
- `ScenarioDiffPage.tsx`
- `ScenarioRunStatusCard.tsx`

## 26.3 화면별 핵심 API 매핑

### ProcessDefinitionEditorPage
- `GET /process/definitions/{id}`
- `GET /process/versions/{versionId}/steps`
- `POST /process/definitions/{id}/versions/{versionNo}/steps:bulk-upsert`
- `POST /process/definitions/{id}/publish`

### ImpactExplorerPage
- `GET /process/definitions/{id}/impact?direction=DOWNSTREAM&depth=3`

### TwinCockpitPage
- `GET /twin/dashboard/workspaces/{workspaceId}`
- `GET /twin/dashboard/workspaces/{workspaceId}/processes`

### ScenarioEditorPage
- `GET /twin/snapshots?workspaceId=...`
- `POST /simulation/scenarios`
- `POST /simulation/scenarios/{scenarioId}/runs`

---

# 27. 단계별 구현 계획

## Phase 1. Governance 기반 도입

목표:
- tenant/workspace scope 정착
- 인증과 API scope 보호
- 기본 관리 화면 제공

산출물:
- tenants, org_units, workspaces, memberships 테이블
- TenantContext resolver
- governance REST API
- workspace selector UI

## Phase 2. Process Model MVP

목표:
- 프로세스 정의/버전/단계 저장
- publish workflow
- relation edge 저장

산출물:
- process_definitions, process_versions, step_definitions
- interface_contracts, rule_definitions, kpi_definitions
- process_relation_edges
- process studio 기본 화면

## Phase 3. Graph Projection / Impact Analysis

목표:
- Neo4j projection 가동
- 영향도 탐색 API 구현

산출물:
- outbox relay
- graph projection consumer
- impact explorer 화면

## Phase 4. Digital Twin MVP

목표:
- process instance / twin event / twin state / snapshot
- 운영 현황 대시보드

산출물:
- twin runtime API
- twin dashboard
- state calculator

## Phase 5. Simulation MVP

목표:
- baseline snapshot 기반 what-if
- 변화 적용 및 결과 diff 제공

산출물:
- scenario CRUD
- scenario run engine
- diff UI

---

# 28. 현재 Axiom에 붙일 때의 주의점

## 28.1 기존 도메인과 충돌 가능성

Axiom에 이미 아래가 있으면 중복 모델이 생길 수 있다.

- ontology concept hierarchy
- workflow/what-if domain entity
- project/workspace/organization 개념
- AI agent execution history

따라서 신규 모델은 기존 개념을 덮어쓰기보다 **명시적 매핑 테이블/브리지**로 연결하는 것이 안전하다.

### 추천 브리지 테이블
- `process_definition_ontology_mappings`
- `workspace_project_mappings`
- `rule_definition_policy_mappings`
- `kpi_definition_metric_mappings`

## 28.2 기존 인증 구조와의 결합

현재 Axiom이 gateway 기반 auth를 이미 갖고 있다면 아래만 보강하면 된다.

- JWT에 기본 tenant claims 추가
- gateway에서 workspace switch header 허용
- downstream service가 tenant context 재검증

## 28.3 멀티테넌트 마이그레이션 방식

기존 데이터에 tenant 개념이 없다면 1차로 `DEFAULT_TENANT`를 만든 뒤 점진적으로 분리한다.

1. 모든 기존 row에 default tenant 부여
2. workspace/domain별 소속 tenant 명시
3. 이후 고객사/조직 분리 시 row migration 수행

---

# 29. 권장 초기 범위와 후순위 범위

## 29.1 초기 범위에 꼭 넣을 것

- Tenant/Workspace scope
- ProcessDefinition / Version / Step
- Relation Edge
- Outbox
- Neo4j projection
- TwinEvent / TwinState / Snapshot
- ScenarioDefinition / Run

## 29.2 후순위로 미뤄도 되는 것

- BPMN import/export
- 복잡한 resource calendar simulation
- 외부 시스템 실시간 양방향 sync
- Graph ML 추천
- 규칙 DSL 편집기 고도화

---

# 30. 최종 구현 권고안

실행 우선순위를 한 줄로 정리하면 다음과 같다.

**멀티테넌트 스코프와 프로세스 정의 모델을 먼저 고정하고, 관계 그래프를 Neo4j Projection으로 붙인 뒤, Twin 이벤트 기반 운영 상태와 What-if 시나리오를 순차적으로 올리는 방식이 가장 안정적이다.**

이 순서를 어기면 다음 문제가 생긴다.

- tenant 경계 없는 그래프 → 데이터 혼선
- 정의 모델 없는 twin → 상태 의미 불명확
- outbox 없는 graph sync → 장애 전파
- snapshot 없는 simulation → 재현 불가

따라서 구현 순서는 반드시 아래를 따른다.

1. Governance / Scope
2. Process Definition / Version / Step
3. Relation Edge / Outbox
4. Graph Projection / Impact Analysis
5. Twin Runtime / Snapshot
6. Scenario Engine / Diff UI

---

# 31. 바로 다음 단계 제안

이 문서 다음 단계로 가장 효율적인 산출물은 아래 둘 중 하나다.

1. **DB 마이그레이션 SQL + Spring Entity/Repository 코드 골격 파일 세트**
2. **React 화면별 상세 컴포넌트 명세 + API hook/usecase 문서**

실제 착수 관점에서는 1번이 먼저이고, 팀 동시 진행 관점에서는 1번과 2번을 병렬로 가져가는 것이 좋다.
