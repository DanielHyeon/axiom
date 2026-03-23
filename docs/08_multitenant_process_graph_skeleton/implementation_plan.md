# Axiom 멀티테넌트 프로세스 그래프 + 디지털 트윈 — 구현 계획서

- 작성일: 2026-03-23
- 기준 문서: `docs/axiom_multitenant_process_graph_digital_twin_detailed_design.md`, `docs/axiom_multitenant_process_graph_webflux_impl_spec.md`
- 대상 스택: **Python 3.12 + FastAPI + SQLAlchemy (asyncpg) + Neo4j + Redis Streams** (기존 Axiom 스택 준수)
- 상태: **구현 착수 가능** (v4.3 — DDL/Envelope/FK 완전 동기화 마감)

---

## 0. 핵심 결정 사항

> **변경 이력**
>
> **v4.3 (DDL/주석/운영 규칙 1:1 최종 마감)**
>
> - Section 0.7 오래된 NOTE 삭제 — workspace 강제 정책으로 통일
> - membership WORKSPACE CHECK에 org_unit_id IS NULL 추가 (scope 완전 잠금)
> - aggregate_seq 발급: MAX+1 → 전용 aggregate_sequences 테이블 원자적 counter
> - twin.event_outbox에 aggregate_seq 컬럼 추가 (envelope 완전 일치)
> - Phase 4 twin_events DDL을 Day-1 partitioned table로 통일 (일반 테이블 표현 제거)
> - step_instances 단일 FK 제거 → 복합 FK (tenant_id, workspace_id, process_instance_id) 최종 형태만
>
> **v4.2 (운영 계약 + 정합성 최종 마감)**
>
> - 듀얼 라이트 금지: 신규 스키마 = write source of truth, 기존 라우트는 read-only adapter
> - membership scope_type (TENANT/ORG_UNIT/WORKSPACE) + CHECK 제약 추가
> - aggregate_seq 도입: 이벤트 순서 확정 기준 (occurred_at 보조, clock skew 대비)
> - workspace denorm FK 강화: step_instances→process_instances (tenant_id, workspace_id, id)
> - process_definitions→process_domains workspace 일치 복합 FK
> - 파티셔닝 Day-1 적용 대상 명확화 (twin_events만 Day-1, audit_logs는 later)
> - API 운영 계약: pagination/sort/filter 규약, 에러 코드 14종, Idempotency-Key 6개 엔드포인트
> - DB CAS 패턴: UPDATE ... WHERE version = :expected로 race window 제거
> - process_relation_edges 참조 무결성 검증 잡 추가
> - audit_logs.actor_roles TEXT → TEXT[] 배열, detail_json 마스킹 원칙
> - scenario_runs에 random_seed + engine_artifact_hash 추가
> - cutover 체크리스트 5개 항목 + rollback 절차 명문화
>
> **v4.1 (DDL 정합성 최종 보정)**
>
> - process_definitions→process_domains 복합 FK SQL 오류 수정 (컬럼 수 불일치)
> - twin_events/event_outbox에 EventEnvelope 표준 컬럼 실제 반영 (ordering_key, schema_version, producer_service, trace_id, actor_user_id)
> - 멱등성 unique에 is_deleted=false 조건 추가 (twin_events)
> - business_key unique에 is_deleted=false 조건 추가 (process_instances)
> - self-hierarchy 복합 FK 강화 (org_units, process_groups, step_definitions, process_versions)
> - step_transition_edges from/to를 (tenant_id, process_version_id, step_id) 복합 FK로 강화
> - Redis Streams ordering_key 구현 방식 정밀화 (네이티브 파티셔닝 아님 명시)
>
> **v4 (운영 투입 전 최종 하드닝)**
>
> - 0.7 복합 FK 기반 tenant/workspace 정합성 DB 레벨 강제
> - 0.8 membership 기간 겹침 방지 — tstzrange exclusion constraint
> - 0.9 이벤트 envelope 표준 (13필드) + ordering_key 기반 순서 보장 정책
> - 0.10 publish validator 강화 (12규칙 모듈화)
> - 0.11 audit_logs 테이블 + permission catalog (19개 permission)
> - 0.12 scenario 재현성 필드 (engine_version, input_manifest 등) + simulation_coefficients 테이블
> - 0.13 운영 데이터 수명주기 (retention 정책 + twin_events partition + 복합 인덱스 6개)
> - 0.14 동시 편집 충돌 정책 (optimistic version check + draft lock)
> - Phase 0 확장 (1주→1~2주): 이벤트 envelope, audit log, 복합 FK 인프라 추가
>
> **v3 (착수 기준 보강)**
>
> - 0.1 식별자 타입 정합성: TenantContext의 tenant_id/user_id를 str로 통일
> - 0.2 soft delete + UNIQUE 충돌 수정: 전체 테이블 partial unique index 전환
> - 0.3 workspace scope 보안 규칙 명문화: 헤더 신뢰 금지, membership 검증 필수
> - 0.4 membership 중복/기간 겹침 방지 인덱스 추가
> - 0.5 step_transition_edges 테이블 신규 추가 (단계 간 흐름 모델)
> - 0.6 current_version_id FK 순환 참조 → DEFERRABLE로 해결, current_version_no 제거
> - 0.7 step_definitions FK 보강 (input/output_contract_id, rule_set_id)
> - 0.8 Twin 런타임 보강: current_step_instance_id, self FK, workspace denorm
> - 0.9 멱등성 키 스코프 재정의: (tenant, aggregate_type, aggregate_id, key)
> - 0.10 Scenario 의존성 수정: 초기 버전은 PostgreSQL 기반 전파 (Neo4j 불필요)
> - 0.11 Neo4j 관계 타입 화이트리스트 강제
> - 0.12 운영 복구 경로 추가: replay/rebuild/reconciliation job
> - Phase 0 (플랫폼 하드닝) 신설, Phase 2.5 (프로세스 흐름 모델) 신설
>
> **v2 (1차 리뷰 반영)**
>
> - CRITICAL-1: tenants/users PK VARCHAR 통일
> - CRITICAL-2: Core는 public 스키마, Twin만 twin 스키마
> - CRITICAL-3: 누락 인덱스 추가
> - MAJOR-1~5: JWT 마이그레이션, Vision 경계, BPM 브리지, TwinEntity, Cross-schema FK

### 0.1 스택 변환: Java/Spring → Python/FastAPI

설계 문서는 Java/Spring WebFlux + R2DBC 기준이나, Axiom의 기존 6개 서비스가 모두 **Python FastAPI + SQLAlchemy asyncpg** 기반이므로 동일 스택으로 구현한다.

| 설계 문서 (Java)              | Axiom 구현 (Python)                        |
|-------------------------------|---------------------------------------------|
| Spring WebFlux + R2DBC        | FastAPI + SQLAlchemy async + asyncpg        |
| `@Table` Entity               | SQLAlchemy `mapped_column` ORM Model        |
| `ReactiveCrudRepository`      | SQLAlchemy async `AsyncSession` Repository  |
| `Mono<T>` / `Flux<T>`        | `async def` / `AsyncGenerator`              |
| `TransactionalOperator`       | `async with session.begin()`                |
| Spring Data Neo4j             | `neo4j` Python async driver                 |
| `@RestController`             | FastAPI `APIRouter`                         |
| Bean Validation               | Pydantic `BaseModel` validation             |
| JWT `ReactiveAuthManager`     | 기존 `core.security` JWT + `Depends()`      |
| Flyway migration              | Alembic 또는 raw SQL migration              |

### 0.2 서비스 경계 결정

**기존 서비스 확장 + 신규 서비스 1개 추가** 방식 채택:

| 모듈                     | 배치 결정                  | 근거                                         |
|--------------------------|---------------------------|----------------------------------------------|
| **Governance**           | `services/core/` 확장      | 기존 Tenant/User/Auth 모델이 Core에 이미 존재  |
| **Process Model**        | `services/core/` 확장      | 기존 BPM ProcessDefinition/WorkItem이 Core에 존재 |
| **Graph Projection**     | `services/synapse/` 확장   | Neo4j 클라이언트와 온톨로지 그래프가 Synapse에 존재 |
| **Digital Twin Runtime** | **신규 `services/twin/`**  | 이벤트/상태/스냅샷은 독립 도메인, 기존 서비스와 혼합 방지 |
| **Simulation/What-if**   | **신규 `services/twin/`**  | Twin Runtime과 동일 서비스 내 별도 모듈       |

### 0.3 PostgreSQL 스키마 배치

> **CRITICAL 결정**: 기존 Core 서비스는 `public` 스키마를 사용한다 (schema prefix 없음).
> 기존 `tenants.id`와 `users.id`는 `VARCHAR(String)` 타입이므로, 신규 테이블의 FK도 `VARCHAR`로 통일한다.
> Twin 서비스만 `twin` 스키마를 사용한다 (greenfield).

```
public 스키마 (Core 서비스 — 기존 + 확장)
├── tenants (기존 — industry_type/timezone 등 컬럼 보강)
├── users (기존)
├── org_units (신규)
├── workspaces (신규)
├── memberships (신규)
├── process_domains (신규)
├── process_groups (신규)
├── process_definitions (기존 bpm_process_definition과 브리지)
├── process_versions (신규)
├── step_definitions (신규)
├── interface_contracts (신규)
├── rule_definitions (신규)
├── kpi_definitions (신규)
├── process_relation_edges (신규)
├── bpm_process_definition_bridge (신규 — 기존 BPM ↔ 신규 매핑)
└── event_outbox (기존)

twin 스키마 (Twin 서비스 — 신규, 별도 스키마)
├── twin_entities (신규 — 트윈 엔티티 레지스트리)
├── process_instances (기존 bpm_process_instance 마이그레이션)
├── step_instances (신규)
├── twin_events (신규)
├── twin_states (신규)
├── twin_snapshots (신규)
├── scenario_definitions (신규)
├── scenario_change_sets (신규)
├── scenario_runs (신규)
└── event_outbox (신규)
```

> **Cross-schema FK 전략**: Twin 서비스의 `process_instances.process_definition_id`는
> `public.process_definitions(id)`를 참조하지만, 현재는 동일 DB(`insolvency_os`)에 있으므로
> cross-schema FK가 동작한다. 향후 서비스별 DB 분리 시에는 FK를 제거하고
> 이벤트 기반 결과적 일관성으로 전환한다. (ADR로 문서화 필요)

### 0.4 Neo4j 확장 전략

기존 Synapse의 5계층 온톨로지 그래프에 **프로세스 그래프 노드/엣지를 추가 투영**:

- 신규 노드 라벨: `:ProcessDefinition`, `:ProcessVersion`, `:StepDefinition`, `:InterfaceContract`, `:RuleDefinition`, `:KpiDefinition`, `:TwinEntity`
- 신규 관계 타입: `:TRIGGERS`, `:BLOCKS`, `:DEPENDS_ON`, `:HANDOFF_TO`, `:CONSUMES`, `:PRODUCES`, `:GOVERNED_BY`, `:MEASURED_BY`, `:INFLUENCES_KPI`
- 기존 온톨로지 연결: `(:ProcessDefinition)-[:MAPPED_TO]->(:OntologyConcept)`

### 0.5 Vision What-if vs Twin Simulation 경계

> **MAJOR 결정**: 기존 Vision 서비스의 WhatIfWizard(9단계)와 신규 Twin Simulation의 역할을 분리한다.

| 구분 | Vision What-if (기존) | Twin Simulation (신규) |
| ------- | ----------------------- | ----------------------- |
| **대상** | KPI 인과 관계 (통계 기반) | 프로세스 운영 상태 (정의 기반) |
| **분석 방식** | Granger/VAR 통계 모델 + DAG | 규칙 기반 근사 → DES 고도화 |
| **변경 대상** | KPI 변수값 (수요, 환율 등) | 프로세스 자원/정책/자동화율 |
| **출력** | KPI 예측값 + 인과 경로 | 처리시간/대기열/SLA 변화 |
| **데이터 원천** | 온톨로지 Driver Layer | ProcessDefinition + TwinState |
| **UI** | `/analysis/insight` What-if 탭 | `/simulation/scenarios` |

**통합 포인트** (Phase 6):

- Twin Simulation 결과를 Vision의 DAG에 KPI 변화 입력으로 전달
- Vision의 인과 분석 결과를 Twin의 영향도 전파에 활용

### 0.6 구현 원칙

1. **PostgreSQL = Source of Truth**, Neo4j = Projection (쿼리 최적화 전용)
2. **Outbox 기반 비동기 Projection** — 도메인 저장 트랜잭션과 Neo4j 갱신 분리
3. **TenantContext 필수** — 모든 API는 tenant_id 없이 동작 불가
4. **이벤트 우선 상태** — TwinState는 TwinEvent로부터 파생
5. **정의 ↔ 실행 분리** — ProcessDefinition과 ProcessInstance 별도 스키마
6. **복합 FK로 tenant/workspace 정합성 DB 강제** — 애플리케이션 검증만으로는 크로스 테넌트 참조 방지 불가 (v4)
7. **이벤트 envelope 표준화** — 모든 도메인 이벤트는 표준 필드 세트를 반드시 포함 (v4)
8. **동시 편집은 optimistic version check** — bulk-upsert API는 클라이언트 version 필수 전송 (v4)

### 0.7 복합 FK 기반 Tenant/Workspace 정합성 강제 (v4)

자식 테이블이 부모 테이블과 **같은 tenant/workspace에 속함**을 DB 레벨에서 완전히 보장한다.
애플리케이션 레이어 검증만으로는 버그, 마이그레이션 스크립트, 직접 SQL 실행 시 교차 오염을 막을 수 없다.

**원칙**: 부모 테이블에 `(tenant_id, id)` 또는 `(tenant_id, workspace_id, id)` UNIQUE 제약을 두고,
자식 테이블이 이 복합 키를 FK로 참조한다.

**적용 대상 (핵심 참조 체인)**:

```
tenants(id)
  └─ org_units(tenant_id, id)
       └─ workspaces(tenant_id, org_unit_id)  ← org_unit 소속 tenant 일치 보장
  └─ workspaces(tenant_id, id)
       └─ process_domains(tenant_id, workspace_id)
            └─ process_definitions(tenant_id, domain_id)
                 └─ process_versions(tenant_id, process_definition_id)
                      └─ step_definitions(tenant_id, process_version_id)
                      └─ step_transition_edges(tenant_id, process_version_id)
  └─ memberships(tenant_id, user_id)  ← user 소속 tenant 일치 보장

twin 스키마:
  twin.process_instances(tenant_id, workspace_id)
       └─ twin.step_instances(tenant_id, process_instance_id)
```

**필요한 복합 UNIQUE 제약 (부모 테이블)**:

```sql
-- 부모 테이블에 복합 유니크 추가 (PK 외에 tenant_id를 포함한 키)
ALTER TABLE org_units      ADD CONSTRAINT uq_org_units_tenant_id      UNIQUE (tenant_id, id);
ALTER TABLE workspaces     ADD CONSTRAINT uq_workspaces_tenant_id     UNIQUE (tenant_id, id);
ALTER TABLE workspaces     ADD CONSTRAINT uq_workspaces_tenant_org    UNIQUE (tenant_id, org_unit_id, id);
-- process_domains: (tenant_id, id) UNIQUE는 복합 FK 섹션에서 ALTER로 추가
ALTER TABLE process_definitions ADD CONSTRAINT uq_procdefs_tenant_id  UNIQUE (tenant_id, id);
ALTER TABLE process_versions ADD CONSTRAINT uq_procvers_tenant_id     UNIQUE (tenant_id, id);
```

**자식 테이블 FK 변경 (단일 FK → 복합 FK)**:

```sql
-- workspaces: org_unit이 같은 tenant에 속하는지 보장
ALTER TABLE workspaces
    DROP CONSTRAINT IF EXISTS workspaces_org_unit_id_fkey,
    ADD CONSTRAINT fk_workspaces_org_unit
    FOREIGN KEY (tenant_id, org_unit_id) REFERENCES org_units(tenant_id, id);

-- process_domains: workspace가 같은 tenant에 속하는지 보장
ALTER TABLE process_domains
    DROP CONSTRAINT IF EXISTS process_domains_workspace_id_fkey,
    ADD CONSTRAINT fk_domains_workspace
    FOREIGN KEY (tenant_id, workspace_id) REFERENCES workspaces(tenant_id, id);

-- process_definitions → process_domains: workspace 일치까지 DB 강제 (v4.2 최종 정책)
-- 아래 v4.2 블록의 fk_procdefs_domain_ws가 최종 FK이므로 여기서는 생략
-- (v4.2 블록에서 workspace 포함 복합 FK로 강화됨)

-- process_versions: definition이 같은 tenant에 속하는지 보장
ALTER TABLE process_versions
    DROP CONSTRAINT IF EXISTS process_versions_process_definition_id_fkey,
    ADD CONSTRAINT fk_procvers_definition
    FOREIGN KEY (tenant_id, process_definition_id) REFERENCES process_definitions(tenant_id, id);

-- step_definitions: version이 같은 tenant에 속하는지 보장
ALTER TABLE step_definitions
    DROP CONSTRAINT IF EXISTS step_definitions_process_version_id_fkey,
    ADD CONSTRAINT fk_stepdefs_version
    FOREIGN KEY (tenant_id, process_version_id) REFERENCES process_versions(tenant_id, id);

-- step_transition_edges: version이 같은 tenant에 속하는지 보장
ALTER TABLE step_transition_edges
    DROP CONSTRAINT IF EXISTS step_transition_edges_process_version_id_fkey,
    ADD CONSTRAINT fk_transitions_version
    FOREIGN KEY (tenant_id, process_version_id) REFERENCES process_versions(tenant_id, id);

-- twin.step_instances: process_instance가 같은 tenant + workspace에 속하는지 보장 (v4.2)
ALTER TABLE twin.process_instances
    ADD CONSTRAINT uq_instances_tenant_ws_id UNIQUE (tenant_id, workspace_id, id);

ALTER TABLE twin.step_instances
    DROP CONSTRAINT IF EXISTS step_instances_process_instance_id_fkey,
    ADD CONSTRAINT fk_step_instances_process
    FOREIGN KEY (tenant_id, workspace_id, process_instance_id)
    REFERENCES twin.process_instances(tenant_id, workspace_id, id);
-- v4.2: workspace denorm 정합성을 DB가 보장 — 부모와 다른 workspace_id 불가

-- process_definitions: workspace_id와 domain의 workspace가 일치하는지 보장 (v4.2)
-- domain은 이미 (tenant_id, workspace_id)로 scoped되어 있으므로,
-- definitions → domains FK를 workspace 포함 복합키로 강화
ALTER TABLE process_domains ADD CONSTRAINT uq_domains_tenant_ws_id UNIQUE (tenant_id, workspace_id, id);
ALTER TABLE process_definitions
    DROP CONSTRAINT IF EXISTS fk_procdefs_domain,
    ADD CONSTRAINT fk_procdefs_domain_ws
    FOREIGN KEY (tenant_id, workspace_id, domain_id)
    REFERENCES process_domains(tenant_id, workspace_id, id);
```

**Self-hierarchy 및 version-scope 제약 강화 (v4.1)**:

계층형 self-reference와 step transition이 같은 tenant/version 내에서만 연결되도록 복합 FK를 추가한다.

```sql
-- org_units: 부모가 같은 tenant에 속하는지 보장
ALTER TABLE org_units ADD CONSTRAINT uq_org_units_tenant_id UNIQUE (tenant_id, id);
ALTER TABLE org_units
    DROP CONSTRAINT IF EXISTS org_units_parent_org_unit_id_fkey,
    ADD CONSTRAINT fk_org_units_parent
    FOREIGN KEY (tenant_id, parent_org_unit_id) REFERENCES org_units(tenant_id, id);

-- process_groups: 부모가 같은 tenant에 속하는지 보장
ALTER TABLE process_groups ADD CONSTRAINT uq_process_groups_tenant_id UNIQUE (tenant_id, id);
ALTER TABLE process_groups
    DROP CONSTRAINT IF EXISTS process_groups_parent_group_id_fkey,
    ADD CONSTRAINT fk_process_groups_parent
    FOREIGN KEY (tenant_id, parent_group_id) REFERENCES process_groups(tenant_id, id);

-- step_definitions: 부모 step이 같은 tenant + 같은 version에 속하는지 보장
ALTER TABLE step_definitions ADD CONSTRAINT uq_step_defs_tenant_version_id UNIQUE (tenant_id, process_version_id, id);
ALTER TABLE step_definitions
    DROP CONSTRAINT IF EXISTS step_definitions_parent_step_id_fkey,
    ADD CONSTRAINT fk_step_defs_parent
    FOREIGN KEY (tenant_id, process_version_id, parent_step_id)
    REFERENCES step_definitions(tenant_id, process_version_id, id);

-- step_transition_edges: from/to step이 같은 tenant + 같은 version에 속하는지 보장
ALTER TABLE step_transition_edges
    DROP CONSTRAINT IF EXISTS step_transition_edges_from_step_id_fkey,
    DROP CONSTRAINT IF EXISTS step_transition_edges_to_step_id_fkey,
    ADD CONSTRAINT fk_transitions_from_step
    FOREIGN KEY (tenant_id, process_version_id, from_step_id)
    REFERENCES step_definitions(tenant_id, process_version_id, id),
    ADD CONSTRAINT fk_transitions_to_step
    FOREIGN KEY (tenant_id, process_version_id, to_step_id)
    REFERENCES step_definitions(tenant_id, process_version_id, id);

-- process_versions: 부모 버전이 같은 tenant에 속하는지 보장
ALTER TABLE process_versions
    DROP CONSTRAINT IF EXISTS process_versions_parent_version_id_fkey,
    ADD CONSTRAINT fk_process_versions_parent
    FOREIGN KEY (tenant_id, parent_version_id) REFERENCES process_versions(tenant_id, id);
```

> **주의**: 복합 FK는 부모 테이블에 반드시 해당 복합 UNIQUE가 있어야 한다.
> self-hierarchy FK는 `(tenant_id, id)` 또는 `(tenant_id, version_id, id)` UNIQUE를 부모에 추가한 후 적용한다.
> step transition의 `(tenant_id, process_version_id, step_id)` 복합 FK는 **같은 version 소속 step끼리만 연결됨**을 DB가 보장한다.

### 0.8 Membership 기간 겹침 방지 — Exclusion Constraint (v4)

동일 scope/role에서 기간이 겹치는 멤버십을 DB 레벨에서 완전히 차단한다.

```sql
-- btree_gist 확장 필요 (tstzrange 기반 exclusion constraint에 필수)
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- 기존 활성 중복 방지 인덱스는 유지 (즉시 중복 체크용)
-- 추가로 기간 겹침 방지 exclusion constraint
ALTER TABLE memberships ADD COLUMN effective_range tstzrange
    GENERATED ALWAYS AS (
        tstzrange(
            COALESCE(effective_from, '-infinity'::timestamptz),
            COALESCE(effective_to, 'infinity'::timestamptz),
            '[)'
        )
    ) STORED;

ALTER TABLE memberships ADD CONSTRAINT excl_membership_no_overlap
    EXCLUDE USING gist (
        tenant_id WITH =,
        user_id WITH =,
        COALESCE(workspace_id, '00000000-0000-0000-0000-000000000000'::uuid) WITH =,
        COALESCE(org_unit_id, '00000000-0000-0000-0000-000000000000'::uuid) WITH =,
        role_code WITH =,
        effective_range WITH &&
    ) WHERE (is_deleted = false);
```

> **동작**: 같은 (tenant, user, workspace, org_unit, role) 조합에서 기간이 겹치면
> INSERT/UPDATE 자체가 실패한다. 애플리케이션에서 추가 검증 불필요.

### 0.9 이벤트 Envelope 표준 및 순서 보장 정책 (v4)

#### 이벤트 Envelope 표준 필드

모든 도메인 이벤트는 아래 필드를 반드시 포함한다:

```python
@dataclass
class EventEnvelope:
    # 필수 필드
    event_id: UUID                  # 이벤트 고유 ID
    event_type: str                 # 예: process.definition.created
    event_version: int              # 스키마 버전 (호환성 관리)
    schema_version: str             # envelope 구조 버전 (예: "1.0")
    tenant_id: str                  # 테넌트 ID
    workspace_id: UUID | None       # 워크스페이스 ID
    aggregate_type: str             # 예: PROCESS_DEFINITION
    aggregate_id: UUID              # 대상 엔티티 ID
    ordering_key: str               # 순서 보장 키 (아래 정책 참조)
    aggregate_seq: int              # v4.2: aggregate 내 단조 증가 시퀀스 (순서 확정 기준)
    idempotency_key: str            # 멱등성 키
    occurred_at: datetime           # 이벤트 발생 시각
    producer_service: str           # 발행 서비스명 (core, synapse, twin 등)
    actor_user_id: str | None       # 행위자 ID

    # 추적 필드
    trace_id: str                   # OpenTelemetry trace ID
    correlation_id: UUID | None     # 비즈니스 상관 ID (케이스 ID 등)
    causation_id: UUID | None       # 원인 이벤트 ID (이벤트 체이닝)

    # 페이로드
    payload: dict                   # 이벤트별 데이터
```

#### 순서 보장 정책

| 소비 패턴 | ordering_key 규칙 | 보장 수준 |
| --------- | ----------------- | --------- |
| Graph Projection | `{aggregate_type}:{aggregate_id}` | aggregate 단위 순서 보장 |
| Twin State Projector | `{aggregate_type}:{aggregate_id}` | aggregate 단위 순서 보장 |
| 대시보드 집계 | 순서 불필요 | at-least-once |
| Scenario 실행 | `scenario:{scenario_id}` | scenario 단위 순서 보장 |

**Redis Streams 구현**:

> **주의**: Redis Streams는 Kafka처럼 키 기반 파티셔닝을 네이티브로 제공하지 않는다.
> `ordering_key` 기반 순서 보장은 **애플리케이션 레벨에서 구현**해야 한다.

구현 방식 (택 1):

1. **Dispatcher 패턴 (권장)**: 단일 consumer가 Redis Stream에서 읽고, `ordering_key` hash 기반으로 내부 워커 큐에 재분배. 같은 `ordering_key`는 항상 같은 워커에 배정 → aggregate 단위 순서 보장.
2. **Stream 샤딩**: `ordering_key` hash로 여러 Redis Stream에 분산 (`twin-events:{hash % N}`). 각 Stream은 단일 consumer group이 순서대로 소비.
3. **Single-flight**: aggregate별 처리 중 lock을 잡아 동시 처리 방지 (처리량 낮음, 초기에만 권장).

선택 기준: 초기에는 이벤트 처리량이 낮으므로 방식 1(Dispatcher)로 시작하고, 처리량 증가 시 방식 2로 전환한다.

**순서 역전 방지 (소비자 측, v4.2 보강)**:

- **`aggregate_seq`가 순서 판단의 1차 기준** — 같은 aggregate에서 `last_applied_seq`보다 작은 seq는 skip
- `occurred_at`은 2차 참고용 (clock skew 대비, seq가 없는 외부 이벤트용)
- twin_states에 `last_event_seq` 저장 → `aggregate_seq <= last_event_seq`이면 무시
- graph projection은 `aggregate_seq` 비교 → 이전 seq로 덮어쓰지 않음
- `aggregate_seq` 발급: **전용 카운터 테이블** `twin.aggregate_sequences`에서 원자적으로 발급

```sql
-- aggregate_seq 발급 전용 테이블
CREATE TABLE twin.aggregate_sequences (
    tenant_id VARCHAR NOT NULL,
    aggregate_type VARCHAR(50) NOT NULL,
    aggregate_id UUID NOT NULL,
    last_seq BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (tenant_id, aggregate_type, aggregate_id)
);

-- 이벤트 발행 트랜잭션 안에서 원자적 발급 (첫 이벤트도 안전)
INSERT INTO twin.aggregate_sequences (tenant_id, aggregate_type, aggregate_id, last_seq)
VALUES (:tenant_id, :aggregate_type, :aggregate_id, 1)
ON CONFLICT (tenant_id, aggregate_type, aggregate_id)
DO UPDATE SET last_seq = twin.aggregate_sequences.last_seq + 1
RETURNING last_seq;
```

> MAX+1 방식은 첫 이벤트(행 없음)에서 race condition이 발생할 수 있으므로 사용하지 않는다.

### 0.10 프로세스 Publish Validator 명세 (v4)

DRAFT → PUBLISHED 발행 시 아래 규칙을 **모두 통과해야** 상태 전이가 허용된다.
`ProcessPublishValidator` 모듈로 분리하여 서비스 계층에서 호출한다.

```python
# services/core/app/modules/process_model/validation/publish_validator.py

class PublishValidationRule:
    """발행 검증 규칙 — 하나라도 실패하면 PUBLISH 거부"""

PUBLISH_RULES = [
    # 구조 규칙
    "EXACTLY_ONE_START: START 타입 step이 정확히 1개 존재",
    "AT_LEAST_ONE_END: END 타입 step이 최소 1개 존재",
    "NO_ORPHAN_STEPS: 모든 step은 최소 1개의 incoming 또는 outgoing transition 보유",
    "NON_END_HAS_OUTGOING: END가 아닌 모든 step은 최소 1개의 outgoing transition 보유",
    "DECISION_HAS_DEFAULT: DECISION step은 is_default=true인 outgoing transition 정확히 1개",
    "ALL_TRANSITIONS_SAME_VERSION: 모든 transition이 같은 process_version 소속",
    "NO_UNREACHABLE_STEPS: START에서 모든 step에 도달 가능 (BFS/DFS 검증)",

    # 참조 무결성 규칙
    "CONTRACTS_SAME_TENANT: input/output_contract_id가 같은 tenant/workspace 소속",
    "RULES_SAME_TENANT: rule_set_id가 같은 tenant/workspace 소속",
    "KPI_BINDINGS_VALID: step_kpi_bindings의 kpi_definition_id가 존재하고 같은 tenant 소속",

    # 원자적 발행 규칙
    "ATOMIC_VERSION_SWITCH: current_version_id 교체 + 이전 버전 valid_to 설정이 한 트랜잭션",
    "HASH_UNIQUE: 같은 hash를 가진 PUBLISHED 버전이 이미 존재하면 경고 (중복 발행 방지)",
]
```

**검증 실패 시 응답**:

```json
{
  "success": false,
  "error": {
    "code": "PROCESS_PUBLISH_VALIDATION_FAILED",
    "message": "3 validation rules failed",
    "details": {
      "failures": [
        {"rule": "EXACTLY_ONE_START", "message": "Found 0 START steps, expected 1"},
        {"rule": "NO_UNREACHABLE_STEPS", "message": "Steps [STEP_X, STEP_Y] unreachable from START"},
        {"rule": "DECISION_HAS_DEFAULT", "message": "DECISION step 'risk_check' has no default transition"}
      ]
    }
  }
}
```

### 0.11 감사 로그 및 Permission Catalog (v4)

#### Audit Log 테이블

민감 변경 액션은 별도 감사 로그에 기록한다 (created_by/updated_by 컬럼과는 별개).

```sql
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL,
    actor_user_id VARCHAR NOT NULL,
    actor_roles TEXT[] NOT NULL,                -- v4.2: 배열 타입 (질의/분석 용이, 쉼표 구분 문자열 대신)
    action VARCHAR(100) NOT NULL,              -- permission code (아래 catalog 참조)
    target_type VARCHAR(50) NOT NULL,          -- PROCESS_DEFINITION, MEMBERSHIP, SCENARIO 등
    target_id UUID NOT NULL,
    workspace_id UUID,
    detail_json JSONB,                         -- before/after diff (변경 필드만 저장, payload 전체 금지, 민감정보 마스킹)
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_logs_tenant_target ON audit_logs(tenant_id, target_type, target_id, occurred_at DESC);
CREATE INDEX idx_audit_logs_tenant_actor ON audit_logs(tenant_id, actor_user_id, occurred_at DESC);
CREATE INDEX idx_audit_logs_tenant_action ON audit_logs(tenant_id, action, occurred_at DESC);
```

**감사 대상 액션**:

- `governance:workspace:create/update/delete`
- `governance:membership:grant/revoke`
- `governance:workspace-switch`
- `process:definition:create/update/delete`
- `process:version:publish/deprecate`
- `process:relation:create/delete`
- `twin:event:write`
- `twin:snapshot:capture`
- `scenario:run:start`
- `graph:projection:rebuild`

#### Permission Catalog

엔드포인트별 필요 권한을 미리 정의한다. 구현 시 이 catalog에서 lookup한다.

| Permission Code | 설명 | 허용 역할 |
| --------------- | ---- | --------- |
| `governance:tenant:read` | 테넌트 정보 조회 | 모든 인증 사용자 |
| `governance:tenant:manage` | 테넌트 설정 변경 | PLATFORM_ADMIN, TENANT_ADMIN |
| `governance:workspace:create` | 워크스페이스 생성 | TENANT_ADMIN |
| `governance:workspace:read` | 워크스페이스 조회 | 해당 workspace 멤버 |
| `governance:membership:grant` | 멤버십 할당 | TENANT_ADMIN, DOMAIN_OWNER |
| `governance:membership:revoke` | 멤버십 해제 | TENANT_ADMIN |
| `process:definition:read` | 프로세스 정의 조회 | PROCESS_ARCHITECT, PROCESS_ANALYST, VIEWER |
| `process:definition:write` | 프로세스 정의 생성/수정 | PROCESS_ARCHITECT |
| `process:version:publish` | 버전 발행 | PROCESS_ARCHITECT, DOMAIN_OWNER |
| `process:relation:create` | 관계 엣지 생성 | PROCESS_ARCHITECT |
| `process:clone` | 프로세스 복제 | PROCESS_ARCHITECT |
| `graph:read` | 그래프 탐색/영향도 조회 | PROCESS_ANALYST, PROCESS_ARCHITECT |
| `graph:admin` | 그래프 재구축 | PLATFORM_ADMIN |
| `twin:read` | 트윈 상태/대시보드 조회 | TWIN_OPERATOR, PROCESS_ANALYST |
| `twin:event:write` | 트윈 이벤트 발행 | TWIN_OPERATOR, SYSTEM |
| `twin:snapshot:capture` | 수동 스냅샷 캡처 | TWIN_OPERATOR |
| `scenario:read` | 시나리오 조회 | PROCESS_ANALYST, SCENARIO_ANALYST |
| `scenario:run` | 시나리오 실행 | SCENARIO_ANALYST |
| `scenario:manage` | 시나리오 생성/삭제 | SCENARIO_ANALYST, PROCESS_ARCHITECT |

### 0.12 Scenario 재현성 보장 필드 (v4)

시나리오 실행 결과의 **완전한 재현**을 위해 `scenario_runs` 테이블에 아래 필드를 추가한다.

```sql
ALTER TABLE twin.scenario_runs ADD COLUMN engine_version VARCHAR(50);
ALTER TABLE twin.scenario_runs ADD COLUMN input_manifest_json JSONB;
ALTER TABLE twin.scenario_runs ADD COLUMN baseline_snapshot_hash VARCHAR(128);
ALTER TABLE twin.scenario_runs ADD COLUMN assumption_set_version INTEGER;
ALTER TABLE twin.scenario_runs ADD COLUMN started_by VARCHAR;
ALTER TABLE twin.scenario_runs ADD COLUMN random_seed BIGINT;
ALTER TABLE twin.scenario_runs ADD COLUMN engine_artifact_hash VARCHAR(128);
```

| 필드 | 용도 |
| ---- | ---- |
| `engine_version` | 시뮬레이션 엔진 버전 (코드 변경 추적) |
| `input_manifest_json` | 실행 시점에 사용된 모든 입력 파라미터/계수 스냅샷 |
| `baseline_snapshot_hash` | baseline snapshot의 content hash (변경 감지) |
| `assumption_set_version` | 가정 셋 버전 (동일 시나리오의 가정 변경 추적) |
| `started_by` | 실행 요청자 (audit 연계) |

**시뮬레이션 보정계수 테이블 분리**:

하드코딩된 변화율 람다를 DB 테이블로 분리하여 프로세스/단계별 맞춤 가능하게 한다.

```sql
CREATE TABLE twin.simulation_coefficients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL,
    workspace_id UUID NOT NULL,
    target_entity_type VARCHAR(50) NOT NULL,    -- PROCESS, STEP
    target_entity_id UUID,                      -- NULL이면 전역 기본값
    change_type VARCHAR(50) NOT NULL,           -- AUTOMATION_RATE_CHANGE, RESOURCE_CAPACITY_CHANGE 등
    effect_metric VARCHAR(50) NOT NULL,         -- avg_cycle_time, exception_rate, queue_size 등
    coefficient NUMERIC(8,4) NOT NULL,          -- 변화율 계수
    confidence NUMERIC(5,2),                    -- 계수 신뢰도 (실측 기반이면 높음)
    source VARCHAR(30) NOT NULL DEFAULT 'DEFAULT',  -- DEFAULT, CALIBRATED, MANUAL
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_sim_coefficients_active
    ON twin.simulation_coefficients(
        tenant_id, workspace_id,
        COALESCE(target_entity_id, '00000000-0000-0000-0000-000000000000'::uuid),
        change_type, effect_metric
    ) WHERE is_deleted = false;
```

> 이렇게 하면 "보험금 지급심사 프로세스"와 "일반 민원 프로세스"에
> 서로 다른 자동화 효과 계수(0.6 vs 0.3)를 적용할 수 있다.

### 0.13 운영 데이터 수명주기 및 성능 계획 (v4)

#### Retention 정책

| 테이블 | 보관 정책 | 구현 방식 |
| ------ | --------- | --------- |
| `twin.twin_events` | 6개월 hot / 2년 archive | 월 단위 range partition (`occurred_at`) |
| `twin.event_outbox` | published 후 7일 보관 | 주기적 DELETE (cron) |
| `twin.twin_snapshots` | 최근 100개 hot / 나머지 cold | `summary_json`만 장기 보관 |
| `twin.scenario_runs` | 완료 후 `result_summary_json`만 장기 | `input_manifest_json` 90일 보관 |
| `audit_logs` | 3년 보관 (규정 준수) | 년 단위 partition |
| `twin.step_instances` | 완료 후 90일 hot | process_instances와 동일 lifecycle |

#### 파티셔닝 Day-1 적용 대상 (v4.2 명확화)

| 테이블 | Day-1 partition | 근거 |
| ------ | --------------- | ---- |
| `twin.twin_events` | **Yes** | 이벤트 폭증 예상, 나중에 repartition은 downtime 필요 |
| `audit_logs` | No (초기 일반 테이블) | 초기 볼륨 낮음, 10만건 이상 시 연 단위 partition migration |
| 기타 twin 테이블 | No | 볼륨 예측 불확실, 필요 시 online repartition |

#### twin_events 파티셔닝 DDL (Day-1 적용)

```sql
-- Phase 4 DDL에서 twin_events를 처음부터 partitioned table로 생성
CREATE TABLE twin.twin_events (
    -- (기존 컬럼 동일 — Phase 4.3 DDL 참조)
) PARTITION BY RANGE (occurred_at);

-- 월별 파티션 생성 (자동화 스크립트로 관리)
CREATE TABLE twin.twin_events_2026_03
    PARTITION OF twin.twin_events
    FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');

CREATE TABLE twin.twin_events_2026_04
    PARTITION OF twin.twin_events
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
-- ... 자동 생성 cron job
```

#### 추가 복합 인덱스 (대시보드 쿼리 최적화)

```sql
-- process_instances: 워크스페이스별 기한 임박 조회
CREATE INDEX idx_instances_ws_due
    ON twin.process_instances(tenant_id, workspace_id, status, due_at)
    WHERE is_deleted = false AND status IN ('RUNNING', 'WAITING', 'QUEUED');

-- step_instances: 단계별 상태 집계
CREATE INDEX idx_step_instances_def_status
    ON twin.step_instances(tenant_id, workspace_id, step_definition_id, status)
    WHERE is_deleted = false;

-- twin_states: 대시보드 건강도 필터
CREATE INDEX idx_twin_states_health
    ON twin.twin_states(tenant_id, workspace_id, state_code, sla_status)
    WHERE is_deleted = false;
```

### 0.14 동시 편집 충돌 정책 (v4)

#### Optimistic Version Check

Process Studio에서 여러 사용자가 같은 DRAFT 버전을 동시 편집할 때의 충돌 방지:

1. **모든 bulk-upsert API는 `version` 파라미터 필수**:

```python
class BulkUpsertStepsRequest(BaseModel):
    expected_version: int           # 클라이언트가 마지막으로 본 process_version.version
    steps: list[UpsertStepRequest]
```

2. **서버 검증**:

```python
async def bulk_upsert_steps(ctx, version_id, request):
    version = await repo.find_by_id(version_id)
    if version.version != request.expected_version:
        raise VersionConflictError(
            current_version=version.version,
            expected_version=request.expected_version
        )
    # ... 저장 로직
    version.version += 1  # optimistic lock increment
```

3. **충돌 시 응답 (409 Conflict)**:

```json
{
  "success": false,
  "error": {
    "code": "VERSION_CONFLICT",
    "message": "Process version was modified by another user",
    "details": {
      "current_version": 5,
      "expected_version": 4,
      "updated_by": "user-456",
      "updated_at": "2026-03-23T14:30:00Z"
    }
  }
}
```

4. **적용 대상 API**:
   - `POST /process/definitions/{id}/versions/{vno}/steps:bulk-upsert`
   - `POST /process/versions/{vid}/transitions:bulk-upsert`
   - `PATCH /process/definitions/{id}`
   - `POST /process/definitions/{id}/publish`

5. **Draft Lock (선택적 강화)**:

DRAFT 버전 편집 시작 시 Redis에 30분 TTL lock을 설정하여 다른 사용자에게 경고 표시:

```python
LOCK_KEY = f"process:draft-lock:{version_id}"
# 편집 시작: SET lock_key user_id EX 1800 NX
# 편집 중: EXPIRE lock_key 1800 (heartbeat로 갱신)
# 편집 종료: DEL lock_key
```

Lock이 있어도 저장은 허용하되, UI에서 "다른 사용자가 편집 중" 경고를 표시한다.

### 0.15 API 운영 계약 표준 (v4.2)

#### Pagination / Sort / Filter 규약

모든 목록 API는 아래 공통 쿼리 파라미터를 지원한다:

```
GET /api/v1/{resource}?page=1&page_size=50&sort_by=created_at&sort_dir=desc&q=keyword
```

| 파라미터 | 기본값 | 설명 |
| -------- | ------ | ---- |
| `page` | 1 | 1-based 페이지 번호 |
| `page_size` | 50 | 페이지 크기 (max: 200) |
| `sort_by` | `created_at` | 정렬 컬럼 (허용 컬럼 목록은 리소스별 정의) |
| `sort_dir` | `desc` | `asc` 또는 `desc` |
| `q` | - | 이름/코드 검색 (ILIKE) |

**응답 형식**:

```json
{
  "success": true,
  "data": { "items": [...], "total": 142, "page": 1, "page_size": 50 },
  "traceId": "..."
}
```

> twin_events, audit_logs 같은 대용량 테이블은 cursor-based pagination 권장:
> `?cursor=<last_id>&limit=100` 형태로 별도 정의.

#### 에러 코드 Catalog

| 코드 | HTTP | 설명 |
| ---- | ---- | ---- |
| `TENANT_SCOPE_REQUIRED` | 400 | tenant_id 미제공 |
| `WORKSPACE_SCOPE_REQUIRED` | 400 | workspace_id 미제공 (REQUIRE_WORKSPACE_SCOPE=true 시) |
| `WORKSPACE_ACCESS_DENIED` | 403 | 해당 workspace membership 없음 |
| `PERMISSION_DENIED` | 403 | 필요 permission 미보유 |
| `ENTITY_NOT_FOUND` | 404 | 대상 엔티티 미존재 |
| `NAMESPACE_DUPLICATED` | 409 | process namespace 중복 |
| `VERSION_CONFLICT` | 409 | optimistic lock 충돌 |
| `IDEMPOTENCY_CONFLICT` | 409 | 동일 멱등성 키로 다른 내용 요청 |
| `PROCESS_PUBLISH_VALIDATION_FAILED` | 422 | publish validator 규칙 위반 |
| `MEMBERSHIP_OVERLAP` | 422 | 기간 겹침 exclusion constraint 위반 |
| `RELATION_TYPE_INVALID` | 422 | 화이트리스트 외 관계 타입 |
| `LEGACY_BRIDGE_NOT_FOUND` | 404 | BPM 브리지 매핑 미존재 |
| `SCENARIO_BASE_SNAPSHOT_NOT_FOUND` | 404 | baseline snapshot 미존재 |
| `GRAPH_PROJECTION_FAILED` | 500 | Neo4j projection 오류 |

#### Idempotency-Key 적용 엔드포인트

아래 **상태 변경 API**는 요청 헤더 `Idempotency-Key`를 지원한다:

| 엔드포인트 | 저장 위치 | TTL |
| ---------- | --------- | --- |
| `POST /process/definitions` | Redis `idempotency:{key}` | 24h |
| `POST /process/definitions/{id}/publish` | Redis | 24h |
| `POST /twin/events` | twin.twin_events (DB unique) | 영구 |
| `POST /twin/snapshots` | Redis | 1h |
| `POST /simulation/scenarios/{id}/runs` | Redis | 1h |
| `POST /governance/memberships` | Redis | 24h |

**동작**: 동일 키로 재요청 시 기존 응답을 반환. 다른 body로 재요청 시 `409 IDEMPOTENCY_CONFLICT`.

### 0.16 Optimistic Locking DB CAS 패턴 (v4.2)

Section 0.14의 version check를 **DB 레벨 compare-and-swap**으로 강화한다.
애플리케이션에서 조회 → 비교 → 저장하면 race window가 남으므로, 단일 UPDATE 문으로 원자적 처리:

```python
# SQLAlchemy 기반 DB CAS 패턴
result = await session.execute(
    update(ProcessVersion)
    .where(
        ProcessVersion.id == version_id,
        ProcessVersion.version == expected_version,   # CAS 조건
        ProcessVersion.is_deleted == False,
    )
    .values(
        version=ProcessVersion.version + 1,
        # ... 기타 변경 필드
    )
)
if result.rowcount == 0:
    raise VersionConflictError(...)
```

**적용 대상**: `version BIGINT` 컬럼이 있는 모든 테이블의 UPDATE/bulk-upsert.

### 0.17 process_relation_edges 참조 무결성 검증 (v4.2)

polymorphic FK (`source_entity_type` + `source_entity_id`) 구조는 DB FK를 걸 수 없으므로,
dangling edge 방지를 위한 **정기 검증 잡**을 추가한다:

```python
# services/core/scripts/reconcile_relation_edges.py
# 1. entity_type별 실존 여부 체크
# 2. 미존재 edge → soft delete 또는 리포트
# 3. 주기: 일 1회 (cron)
# 4. 결과: Slack/email 알림 + metrics 기록
```

운영 도구 목록 (Section 10.1)에 추가:

| 도구 | 위치 | 용도 | Phase |
| ---- | ---- | ---- | ----- |
| **relation edge reconcile** | `services/core/scripts/reconcile_relation_edges.py` | polymorphic FK dangling edge 검증 | 2 |

---

## 1. Phase 0: 플랫폼 하드닝 (1~2주) — v3 신설, v4 확장

### 1.0 목표

Phase 1~5에서 반복적으로 부딪힐 기반 문제를 **선행 해결**한다. 이 단계를 건너뛰면 모든 Phase에서 동일한 타입 충돌, 보안 누수, 운영 복구 불능 문제가 반복 발생한다.

### 1.0.1 ID 타입 통일

- `TenantContext`, Pydantic DTO, ORM 모델에서 `tenant_id`/`user_id`를 `str`로 통일
- 기존 `core/security.py` JWT 파싱이 반환하는 타입 확인 및 정합성 보장
- 모든 신규 테이블 FK에서 `VARCHAR` 사용 확인 자동 검증 스크립트 작성

### 1.0.2 Soft Delete + Partial Unique 정책 수립

- 기존 테이블 중 `is_deleted` + `UNIQUE` 충돌이 있는 곳 점검
- 신규 테이블 DDL 생성 규칙: 일반 UNIQUE 금지, partial unique index만 사용
- 공통 SQLAlchemy Base 클래스에 `is_deleted` + `version` 컬럼 표준화

### 1.0.3 Workspace 보안 규칙 구현

- `TenantMiddleware` 확장: `X-Axiom-Workspace-Id` 헤더 수신 → membership 검증 → `TenantContext` 확정
- 검증 실패 시 `403 WORKSPACE_ACCESS_DENIED` 응답
- workspace-switch API stub 구현 (`POST /api/v1/governance/workspace-switch`)

### 1.0.4 운영 스크립트 뼈대

- outbox replay CLI (미발행 이벤트 재전송)
- projection rebuild job stub (Neo4j full rebuild 엔트리포인트)
- twin state recompute job stub (TwinEvent 재생 → TwinState 재계산)

### 1.0.5 Neo4j 관계 타입 화이트리스트

```python
# services/synapse/app/graph/relation_whitelist.py
ALLOWED_RELATION_TYPES = frozenset({
    'TRIGGERS', 'BLOCKS', 'DEPENDS_ON', 'HANDOFF_TO',
    'CONSUMES', 'PRODUCES', 'GOVERNED_BY', 'MEASURED_BY',
    'INFLUENCES_KPI', 'MAPPED_TO',
})

def validate_relation_type(rel_type: str) -> str:
    """Cypher 동적 관계 타입 주입 방지 — 화이트리스트 통과만 허용"""
    if rel_type not in ALLOWED_RELATION_TYPES:
        raise ValueError(f"Invalid relation type: {rel_type}")
    return rel_type
```

### 1.0.6 이벤트 Envelope 표준 구현 (v4)

- `EventEnvelope` dataclass 공통 모듈로 생성 (Section 0.9 명세 기준)
- 기존 Core/Synapse/Weaver/OLAP Studio outbox에 `ordering_key`, `schema_version`, `producer_service`, `trace_id` 컬럼 추가 (backward-compatible ALTER)
- Redis Streams consumer group 파티셔닝: `ordering_key` 기반 순서 보장 규칙 적용

### 1.0.7 Audit Log 테이블 + Permission Catalog 생성 (v4)

- `audit_logs` 테이블 생성 (Section 0.11 DDL 기준)
- Permission Catalog JSON/YAML 파일 작성 → 런타임 lookup 구조
- `@audit_logged` 데코레이터 공통 구현 (민감 액션 자동 기록)

### 1.0.8 복합 FK 기반 Tenant 정합성 인프라 (v4)

- 부모 테이블 복합 UNIQUE 제약 DDL 템플릿 작성 (Section 0.7 기준)
- Phase 1~2에서 테이블 생성 시 복합 FK를 즉시 적용할 수 있도록 순서 정의

### 1.0.9 산출물

- [x] TenantContext str 타입 통일 + 검증 테스트
- [x] Partial unique index 정책 문서 + DDL 템플릿
- [x] Workspace 보안 미들웨어
- [x] Outbox replay / projection rebuild / twin recompute CLI stub
- [x] Neo4j relation whitelist validator
- [x] EventEnvelope 표준 dataclass + ordering_key 정책 (v4)
- [x] audit_logs 테이블 + permission catalog (v4)
- [x] 복합 FK DDL 템플릿 + 적용 순서 정의 (v4)
- [x] `btree_gist` 확장 설치 확인 (v4 — membership exclusion constraint용)

### 1.0.10 구현 완료 파일 목록 (Phase 0 실제 구현)

| 파일 | 유형 | 구현 근거 |
| ---- | ---- | --------- |
| `services/core/app/core/tenant_context.py` | 신규 | §1.0.1 ID 타입 통일 + §1.0.3 Workspace 보안 |
| `services/core/app/core/permissions.py` | 신규 | §1.0.7 Permission Catalog (19종) |
| `services/core/app/core/base_entity.py` | 신규 | §1.0.2 Soft Delete + Partial Unique 정책 |
| `services/core/app/core/event_envelope.py` | 신규 | §1.0.6 EventEnvelope 표준 (18필드) |
| `services/core/app/core/audit.py` | 신규 | §1.0.7 AuditLog ORM + @audit_logged 데코레이터 |
| `services/core/scripts/outbox_replay.py` | 신규 | §1.0.4 운영 스크립트 (outbox replay CLI) |
| `services/synapse/app/graph/relation_whitelist.py` | 신규 | §1.0.5 Neo4j 관계 타입 화이트리스트 |
| `services/core/app/core/middleware.py` | 수정 | §1.0.3 X-Axiom-Workspace-Id 헤더 추출 |
| `services/core/app/core/security.py` | 수정 | §1.0.1 JWT v1/v2 호환 (role↔roles) |

**코드 리뷰 반영 사항**:

- outbox_replay.py: `publish_pending_once()` 반환 타입 dict → 올바른 unpacking 수정
- middleware.py: workspace 헤더 길이 64자 제한 (메모리 남용 방지)
- audit.py: 감사 로그 실패 시 WARNING → ERROR 레벨 상향
- security.py: `require_permission()` v2 미지원 주석 추가

---

## 2. Phase 1: Governance 기반 도입 (2주)

### 1.1 목표

기존 Core 서비스의 Tenant 모델을 확장하여 **OrgUnit/Workspace/Membership 계층 구조**를 도입하고, 모든 API에 **workspace scope**를 강제한다.

### 1.2 DB 마이그레이션

> **핵심**: 기존 `tenants.id`는 `VARCHAR` (String UUID), `users.id`도 `VARCHAR`.
> 신규 테이블의 `tenant_id`/`user_id` FK도 `VARCHAR`로 통일한다. 신규 테이블 자체 PK는 UUID 사용.
> 모든 테이블은 `public` 스키마 (schema prefix 없음).

#### 1.2.1 기존 tenants 테이블 보강

```sql
-- public 스키마 (기존 tenants 테이블 확장)
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS code VARCHAR(100);
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS industry_type VARCHAR(100);
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS default_timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Seoul';
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS data_residency VARCHAR(64);
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE';
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();

-- code에 unique 제약 (NULL 허용 상태에서 점진적 채우기 위해 별도)
-- UPDATE tenants SET code = id WHERE code IS NULL; -- 데이터 채운 후
-- ALTER TABLE tenants ALTER COLUMN code SET NOT NULL;
-- ALTER TABLE tenants ADD CONSTRAINT uq_tenants_code UNIQUE (code);
```

#### 1.2.2 신규 테이블

```sql
-- org_units: 조직 계층 (HQ → DIVISION → DEPARTMENT)
CREATE TABLE org_units (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL REFERENCES tenants(id),   -- VARCHAR: 기존 tenants.id 타입 호환
    parent_org_unit_id UUID REFERENCES org_units(id),
    code VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    org_type VARCHAR(50) NOT NULL,  -- HQ, DIVISION, DEPARTMENT, SUBSIDIARY, CENTER
    owner_user_id VARCHAR,           -- VARCHAR: 기존 users.id 타입 호환
    path VARCHAR(1000) NOT NULL,     -- 경로 문자열 (materialized path)
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    -- UNIQUE 제약은 partial index로 대체 (soft delete 후 재생성 허용)
);
CREATE UNIQUE INDEX uq_org_units_tenant_code_active
    ON org_units(tenant_id, code) WHERE is_deleted = false;
CREATE INDEX idx_org_units_tenant_parent ON org_units(tenant_id, parent_org_unit_id);
CREATE INDEX idx_org_units_tenant_path ON org_units(tenant_id, path);

-- workspaces: 작업 공간 (프로세스/분석/트윈/샌드박스)
CREATE TABLE workspaces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL REFERENCES tenants(id),
    org_unit_id UUID NOT NULL REFERENCES org_units(id),
    code VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    workspace_type VARCHAR(50) NOT NULL,  -- PROCESS, ANALYTICS, TWIN, SANDBOX
    visibility_policy VARCHAR(50) NOT NULL DEFAULT 'PRIVATE',
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_workspaces_tenant_code_active
    ON workspaces(tenant_id, code) WHERE is_deleted = false;
CREATE INDEX idx_workspaces_tenant_org ON workspaces(tenant_id, org_unit_id);

-- memberships: 사용자 역할 바인딩
CREATE TABLE memberships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL REFERENCES tenants(id),
    user_id VARCHAR NOT NULL REFERENCES users(id),  -- FK 연결 (v3)
    org_unit_id UUID REFERENCES org_units(id),
    workspace_id UUID REFERENCES workspaces(id),
    role_code VARCHAR(100) NOT NULL,  -- TENANT_ADMIN, PROCESS_ARCHITECT, TWIN_OPERATOR, etc.
    scope_type VARCHAR(20) NOT NULL,  -- v4.2: TENANT, ORG_UNIT, WORKSPACE
    status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',
    effective_from TIMESTAMPTZ,
    effective_to TIMESTAMPTZ,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- v4.2: scope_type에 따른 nullable 정합성 강제
    CONSTRAINT chk_membership_scope CHECK (
        (scope_type = 'TENANT'    AND org_unit_id IS NULL AND workspace_id IS NULL) OR
        (scope_type = 'ORG_UNIT'  AND org_unit_id IS NOT NULL AND workspace_id IS NULL) OR
        (scope_type = 'WORKSPACE' AND workspace_id IS NOT NULL AND org_unit_id IS NULL)
    )
);
CREATE INDEX idx_memberships_tenant_user ON memberships(tenant_id, user_id);
CREATE INDEX idx_memberships_tenant_workspace ON memberships(tenant_id, workspace_id);
-- 동일 scope+role 중복 활성 멤버십 방지 (v3)
CREATE UNIQUE INDEX uq_membership_active_scope_role
    ON memberships(
        tenant_id, user_id,
        COALESCE(workspace_id, '00000000-0000-0000-0000-000000000000'::uuid),
        COALESCE(org_unit_id, '00000000-0000-0000-0000-000000000000'::uuid),
        role_code
    ) WHERE is_deleted = false AND status = 'ACTIVE';
```

### 1.3 백엔드 구현 (Core 서비스 확장)

#### 1.3.1 모듈 구조

```
services/core/app/modules/governance/
├── api/
│   └── routes.py             # /api/v1/governance/* 라우터
├── application/
│   └── governance_service.py # OrgUnit/Workspace/Membership CRUD 서비스
├── domain/
│   ├── models.py             # SQLAlchemy ORM: OrgUnit, Workspace, Membership
│   ├── enums.py              # OrgType, WorkspaceType, VisibilityPolicy
│   └── errors.py             # GovernanceError
└── infrastructure/
    └── repositories.py       # 비동기 CRUD Repository
```

#### 1.3.2 API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| `POST` | `/api/v1/governance/org-units` | 조직 단위 생성 |
| `GET` | `/api/v1/governance/org-units/tree` | 조직 계층 트리 조회 |
| `PATCH` | `/api/v1/governance/org-units/{id}` | 조직 단위 수정 |
| `POST` | `/api/v1/governance/workspaces` | 워크스페이스 생성 |
| `GET` | `/api/v1/governance/workspaces` | 접근 가능 워크스페이스 목록 |
| `GET` | `/api/v1/governance/workspaces/{id}` | 워크스페이스 상세 |
| `PATCH` | `/api/v1/governance/workspaces/{id}` | 워크스페이스 수정 |
| `POST` | `/api/v1/governance/memberships` | 멤버십 할당 |
| `GET` | `/api/v1/governance/workspaces/{id}/members` | 워크스페이스 멤버 목록 |

#### 1.3.3 TenantContext 확장

기존 `X-Tenant-Id` 미들웨어에 workspace scope 추가:

```python
# 기존 TenantMiddleware 확장
@dataclass
class TenantContext:
    tenant_id: str          # VARCHAR — 기존 tenants.id 타입과 일치
    user_id: str            # VARCHAR — 기존 users.id 타입과 일치
    org_unit_id: UUID | None
    workspace_id: UUID | None
    role_codes: set[str]
    permission_codes: set[str]
    timezone: str
```

> **식별자 타입 원칙 (v3)**
>
> - 기존 식별자(`tenant_id`, `user_id`)는 `str`(VARCHAR)로 유지
> - 신규 내부 엔티티 PK만 `UUID` 사용
> - JWT claim, request header, DB column, ORM field, Pydantic DTO 타입을 모두 동일하게 맞춤
> - `TenantContext`를 `UUID`로 선언하면 인증 미들웨어, ORM, DTO, 헤더 파싱에서 타입 충돌 발생

**Workspace scope 보안 규칙 (v3)**:

1. `X-Axiom-Workspace-Id` 헤더가 있더라도 **JWT의 tenant_id와 membership 검증을 반드시 통과**해야 함
2. JWT의 `active_workspace_id`가 존재할 때 헤더가 다르면, **명시적 workspace-switch API**를 거친 뒤에만 허용
3. 서비스 레이어는 헤더에서 직접 workspace_id를 사용하지 않고, **검증 완료된 `TenantContext.workspace_id`만** 사용
4. 모든 list/read 쿼리는 `tenant_id`와 `workspace_id`를 함께 조건으로 넣음
5. GovernanceService에서 membership 기반 접근 검증
6. 모든 Repository 쿼리에 tenant_id 필수 WHERE 조건

#### 1.3.4 JWT 페이로드 마이그레이션 전략

기존 JWT 페이로드: `{sub, tenant_id, role(단수), permissions(리스트)}`

신규 JWT 페이로드:

```json
{
  "sub": "user-id",
  "tenant_id": "tenant-id",
  "active_workspace_id": "workspace-id",
  "roles": ["TENANT_ADMIN", "PROCESS_ARCHITECT"],
  "org_unit_ids": ["ou-1"],
  "permissions": ["process:read", "process:write", "twin:read"]
}
```

**호환성 전략**:

1. **Token v1 (기존)**: `role` 단수 → `roles` 리스트로 자동 변환, `workspace_id`=None 허용
2. **Token v2 (신규)**: `roles` 복수, `active_workspace_id` 포함
3. **전환 기간**: JWT 파싱 시 `role`/`roles` 둘 다 처리, workspace_id가 없으면 기존 API는 정상 동작
4. **Feature flag**: `REQUIRE_WORKSPACE_SCOPE=false` → Phase 2 완료 후 true로 전환
5. 기존 6개 서비스의 security.py에 영향 없음 (backward-compatible claim 구조)

### 1.4 프론트엔드

#### 1.4.1 신규 피처 슬라이스

```
canvas/src/features/governance/
├── api/
│   └── governanceApi.ts       # API 클라이언트
├── components/
│   ├── OrgUnitTreePanel.tsx   # 조직 계층 트리 (TreeView)
│   ├── WorkspaceListPanel.tsx # 워크스페이스 목록
│   ├── WorkspaceSelector.tsx  # 글로벌 워크스페이스 전환기 (AppLayout에 배치)
│   └── MembershipDialog.tsx   # 멤버십 할당 대화상자
├── hooks/
│   ├── useOrgUnits.ts
│   ├── useWorkspaces.ts
│   └── useMemberships.ts
├── store/
│   └── useGovernanceStore.ts  # 활성 workspace 상태
└── types/
    └── governance.ts
```

#### 1.4.2 라우트 추가

```typescript
// lib/routes/routes.ts 확장
GOVERNANCE: {
    ROOT: '/governance',
    ORG_UNITS: '/governance/org-units',
    WORKSPACES: '/governance/workspaces',
}
```

#### 1.4.3 AppLayout 변경

- 상단 breadcrumb에 `Tenant > OrgUnit > Workspace` scope 표시
- WorkspaceSelector 드롭다운 추가 (workspace 전환 시 X-Axiom-Workspace-Id 업데이트)

### 1.5 산출물

- [x] core.org_units / core.workspaces / core.memberships 테이블
- [x] TenantContext에 workspace scope 추가
- [x] Governance CRUD API 9개 엔드포인트
- [x] WorkspaceSelector UI + AppLayout 통합
- [x] 이벤트: `tenant.updated`, `org_unit.created`, `workspace.created`, `membership.assigned`

### 1.6 테스트

- 단위: TenantContext resolver, membership 접근 검증 로직
- 통합: API → DB CRUD → scope 강제 확인
- 프론트: WorkspaceSelector 전환 → API 호출 확인

### 1.7 구현 완료 파일 목록 (Phase 1 실제 구현)

| 파일 | 유형 | 구현 근거 |
| ---- | ---- | --------- |
| `services/core/migrations/002_governance_tables.sql` | 신규 | §1.2 tenants ALTER + org_units/workspaces/memberships/audit_logs |
| `services/core/app/modules/governance/domain/enums.py` | 신규 | OrgType, WorkspaceType, VisibilityPolicy, MembershipScopeType, MembershipStatus |
| `services/core/app/modules/governance/domain/errors.py` | 신규 | GovernanceError 계층 (NotFound, AccessDenied, DuplicateCode, MembershipOverlap) |
| `services/core/app/modules/governance/domain/models.py` | 신규 | OrgUnit, Workspace, Membership SQLAlchemy ORM (UUID PK, VARCHAR tenant_id FK) |
| `services/core/app/modules/governance/domain/schemas.py` | 신규 | Pydantic DTO: Create/Update/Response for OrgUnit, Workspace, Membership |
| `services/core/app/modules/governance/infrastructure/repositories.py` | 신규 | OrgUnitRepository, WorkspaceRepository, MembershipRepository (tenant_id 필수 WHERE) |
| `services/core/app/modules/governance/application/governance_service.py` | 신규 | GovernanceService: CRUD + 코드 중복 검사 + path 계산 + workspace 접근 검증 |
| `services/core/app/modules/governance/api/routes.py` | 신규 | 9개 API 엔드포인트 (§1.3.2) |
| `services/core/app/main.py` | 수정 | governance_router 등록 + CORS X-Axiom-Workspace-Id 헤더 허용 |

---

## 2. Phase 2: Process Definition 모델 도입 (3주)

### 2.1 목표

업무 프로세스를 **정식 엔티티**(정의/버전/단계/인터페이스/규칙/KPI)로 관리하고, 프로세스 간 **관계 엣지**를 PostgreSQL에 저장한다.

### 2.2 DB 마이그레이션

```sql
-- ============================================================
-- v3: 모든 UNIQUE 제약은 partial unique index로 대체
--     soft delete 후 동일 code 재생성 허용
-- ============================================================

-- 프로세스 도메인 (업무 영역 분류)
CREATE TABLE process_domains (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL REFERENCES tenants(id),
    workspace_id UUID NOT NULL REFERENCES workspaces(id),
    code VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    domain_type VARCHAR(64),                   -- CLAIM, PAYMENT, RISK, SALES, SUPPORT, COMPLIANCE, GENERIC
    description TEXT,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_process_domains_active
    ON process_domains(tenant_id, workspace_id, code) WHERE is_deleted = false;

-- 프로세스 그룹 (폴더 구조)
CREATE TABLE process_groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL REFERENCES tenants(id),
    domain_id UUID NOT NULL REFERENCES process_domains(id),
    parent_group_id UUID REFERENCES process_groups(id),
    code VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    path VARCHAR(1000) NOT NULL,
    display_order INTEGER NOT NULL DEFAULT 0,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_process_groups_active
    ON process_groups(tenant_id, domain_id, code) WHERE is_deleted = false;
CREATE INDEX idx_process_groups_tenant_domain ON process_groups(tenant_id, domain_id);

-- 프로세스 정의 (기존 bpm_process_definition 확장/마이그레이션)
CREATE TABLE process_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL REFERENCES tenants(id),
    workspace_id UUID NOT NULL REFERENCES workspaces(id),  -- 직접 참조 (쿼리 효율)
    domain_id UUID NOT NULL REFERENCES process_domains(id),
    group_id UUID REFERENCES process_groups(id),
    namespace VARCHAR(300) NOT NULL,           -- 예: insurance.claim.review
    code VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    process_type VARCHAR(50) NOT NULL,         -- HUMAN, SYSTEM, HYBRID, AI_AGENT, PIPELINE
    lifecycle_status VARCHAR(30) NOT NULL DEFAULT 'DRAFT',
    owner_org_unit_id UUID REFERENCES org_units(id),
    primary_role_code VARCHAR(100),
    current_version_id UUID,                   -- 활성 버전 (FK는 process_versions 생성 후 ALTER로 추가)
    is_template BOOLEAN NOT NULL DEFAULT false,
    template_source_id UUID,
    ontology_concept_id VARCHAR(128),          -- 온톨로지 연결 포인트
    version BIGINT NOT NULL DEFAULT 0,         -- optimistic lock
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_by VARCHAR,
    updated_by VARCHAR,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    -- v3: current_version_no 제거 — 조회 시 join 계산, drift 방지
);
CREATE UNIQUE INDEX uq_process_definitions_namespace_active
    ON process_definitions(tenant_id, namespace) WHERE is_deleted = false;
CREATE UNIQUE INDEX uq_process_definitions_domain_code_active
    ON process_definitions(tenant_id, domain_id, code) WHERE is_deleted = false;
CREATE INDEX idx_process_definitions_tenant_domain ON process_definitions(tenant_id, domain_id);
CREATE INDEX idx_process_definitions_tenant_status ON process_definitions(tenant_id, lifecycle_status)
    WHERE is_deleted = false;

-- 프로세스 버전 (버전별 스냅샷)
CREATE TABLE process_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL REFERENCES tenants(id),
    process_definition_id UUID NOT NULL REFERENCES process_definitions(id),
    version_no INTEGER NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'DRAFT',  -- DRAFT, REVIEW, PUBLISHED, DEPRECATED
    source_type VARCHAR(30) NOT NULL DEFAULT 'MANUAL',
    parent_version_id UUID REFERENCES process_versions(id),
    change_summary TEXT,
    hash VARCHAR(128),                            -- 버전 콘텐츠 해시 (중복 감지)
    published_at TIMESTAMPTZ,
    published_by VARCHAR,
    valid_from TIMESTAMPTZ,
    valid_to TIMESTAMPTZ,
    version BIGINT NOT NULL DEFAULT 0,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_by VARCHAR,
    updated_by VARCHAR,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_process_versions_active
    ON process_versions(tenant_id, process_definition_id, version_no) WHERE is_deleted = false;
CREATE INDEX idx_process_versions_tenant_def ON process_versions(tenant_id, process_definition_id);
CREATE INDEX idx_process_versions_tenant_status ON process_versions(tenant_id, status);

-- v3: current_version_id FK를 process_versions 생성 후 지연 추가 (순환 참조 방지)
ALTER TABLE process_definitions
    ADD CONSTRAINT fk_process_definitions_current_version
    FOREIGN KEY (current_version_id) REFERENCES process_versions(id)
    DEFERRABLE INITIALLY DEFERRED;

-- 인터페이스 계약 (입출력 스키마 정의) — step_definitions보다 먼저 생성 (FK 대상)
CREATE TABLE interface_contracts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL REFERENCES tenants(id),
    workspace_id UUID NOT NULL REFERENCES workspaces(id),
    code VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    contract_type VARCHAR(50) NOT NULL,        -- EVENT, DOCUMENT, API, DATASET, MESSAGE
    schema_json JSONB NOT NULL,
    semantic_type VARCHAR(100),
    version_label VARCHAR(50),
    version BIGINT NOT NULL DEFAULT 0,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_by VARCHAR,
    updated_by VARCHAR,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_interface_contracts_active
    ON interface_contracts(tenant_id, workspace_id, code, COALESCE(version_label, ''))
    WHERE is_deleted = false;

-- 규칙 정의
CREATE TABLE rule_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL REFERENCES tenants(id),
    workspace_id UUID NOT NULL REFERENCES workspaces(id),
    code VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    rule_type VARCHAR(50) NOT NULL,            -- BUSINESS_RULE, POLICY, THRESHOLD, ROUTING, VALIDATION, AI_GUARDRAIL
    expression_language VARCHAR(50) NOT NULL,   -- SQL, JSONLOGIC, PY_EXPR, DSL
    expression_text TEXT NOT NULL,
    severity VARCHAR(30),
    description TEXT,
    version BIGINT NOT NULL DEFAULT 0,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_by VARCHAR,
    updated_by VARCHAR,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_rule_definitions_active
    ON rule_definitions(tenant_id, workspace_id, code) WHERE is_deleted = false;

-- KPI 정의
CREATE TABLE kpi_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL REFERENCES tenants(id),
    workspace_id UUID NOT NULL REFERENCES workspaces(id),
    code VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    unit VARCHAR(50),
    target_direction VARCHAR(20) NOT NULL,     -- HIGHER_BETTER, LOWER_BETTER, TARGET_VALUE
    aggregation_type VARCHAR(30) NOT NULL,     -- SUM, AVG, COUNT, RATE, P95
    formula_text TEXT,
    version BIGINT NOT NULL DEFAULT 0,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_by VARCHAR,
    updated_by VARCHAR,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_kpi_definitions_active
    ON kpi_definitions(tenant_id, workspace_id, code) WHERE is_deleted = false;

-- 단계 정의 (프로세스 내 각 스텝) — interface_contracts, rule_definitions 생성 후
CREATE TABLE step_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL REFERENCES tenants(id),
    process_version_id UUID NOT NULL REFERENCES process_versions(id),
    parent_step_id UUID REFERENCES step_definitions(id),
    code VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    step_type VARCHAR(50) NOT NULL,            -- START, TASK, DECISION, WAIT, END, SUBPROCESS, CHECKPOINT
    actor_type VARCHAR(50) NOT NULL,           -- USER, ROLE, SYSTEM, AGENT, EXTERNAL
    actor_ref VARCHAR(200),
    automation_level VARCHAR(32) NOT NULL DEFAULT 'MANUAL',  -- MANUAL, ASSISTED, AUTOMATED, AI_AUTONOMOUS
    input_contract_id UUID REFERENCES interface_contracts(id),   -- v3: FK 추가
    output_contract_id UUID REFERENCES interface_contracts(id),  -- v3: FK 추가
    rule_set_id UUID REFERENCES rule_definitions(id),            -- v3: FK 추가
    sla_minutes INTEGER,
    auto_executable BOOLEAN NOT NULL DEFAULT false,
    display_order INTEGER NOT NULL DEFAULT 0,
    path VARCHAR(1000) NOT NULL,
    ui_metadata_json JSONB,
    version BIGINT NOT NULL DEFAULT 0,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_by VARCHAR,
    updated_by VARCHAR,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_step_definitions_active
    ON step_definitions(tenant_id, process_version_id, code) WHERE is_deleted = false;
CREATE INDEX idx_step_definitions_version ON step_definitions(tenant_id, process_version_id);
CREATE INDEX idx_step_definitions_parent ON step_definitions(tenant_id, parent_step_id);

-- v3: 단계 간 전이 엣지 (분기/병합/예외 경로 표현)
-- process designer, Neo4j projection, Twin 런타임, 시뮬레이션의 공통 원천
CREATE TABLE step_transition_edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL REFERENCES tenants(id),
    process_version_id UUID NOT NULL REFERENCES process_versions(id),
    from_step_id UUID NOT NULL REFERENCES step_definitions(id),
    to_step_id UUID NOT NULL REFERENCES step_definitions(id),
    transition_type VARCHAR(50) NOT NULL,      -- NEXT, YES, NO, ERROR, TIMEOUT, ESCALATE
    condition_expression TEXT,                  -- 조건식 (DECISION 노드 분기용)
    is_default BOOLEAN NOT NULL DEFAULT false,
    display_order INTEGER NOT NULL DEFAULT 0,
    metadata_json JSONB,
    version BIGINT NOT NULL DEFAULT 0,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_step_transition_from
    ON step_transition_edges(tenant_id, process_version_id, from_step_id);
CREATE INDEX idx_step_transition_to
    ON step_transition_edges(tenant_id, process_version_id, to_step_id);
CREATE UNIQUE INDEX uq_step_transition_active
    ON step_transition_edges(tenant_id, process_version_id, from_step_id, to_step_id, transition_type)
    WHERE is_deleted = false;

-- Step ↔ KPI 바인딩 (N:M 관계)
CREATE TABLE step_kpi_bindings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL REFERENCES tenants(id),
    step_definition_id UUID NOT NULL REFERENCES step_definitions(id),
    kpi_definition_id UUID NOT NULL REFERENCES kpi_definitions(id),
    binding_type VARCHAR(30) NOT NULL DEFAULT 'MEASURED_BY',  -- MEASURED_BY, CONTRIBUTES_TO
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_step_kpi_binding_active
    ON step_kpi_bindings(step_definition_id, kpi_definition_id, binding_type)
    WHERE is_deleted = false;

-- 프로세스 관계 엣지 (그래프 Projection의 원천)
CREATE TABLE process_relation_edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL REFERENCES tenants(id),
    workspace_id UUID NOT NULL REFERENCES workspaces(id),
    source_entity_type VARCHAR(50) NOT NULL,   -- PROCESS, STEP, KPI, RULE, INTERFACE
    source_entity_id UUID NOT NULL,
    target_entity_type VARCHAR(50) NOT NULL,
    target_entity_id UUID NOT NULL,
    relation_type VARCHAR(50) NOT NULL,        -- TRIGGERS, BLOCKS, DEPENDS_ON, HANDOFF_TO, etc.
    criticality VARCHAR(16) NOT NULL DEFAULT 'MEDIUM',  -- LOW, MEDIUM, HIGH, CRITICAL
    propagation_mode VARCHAR(16),              -- SYNC, ASYNC, BATCH
    weight NUMERIC(10,4),
    condition_expression TEXT,
    metadata_json JSONB,
    valid_from TIMESTAMPTZ,
    valid_to TIMESTAMPTZ,
    version BIGINT NOT NULL DEFAULT 0,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_by VARCHAR,
    updated_by VARCHAR,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_relation_edges_source ON process_relation_edges(tenant_id, source_entity_type, source_entity_id);
CREATE INDEX idx_relation_edges_target ON process_relation_edges(tenant_id, target_entity_type, target_entity_id);
CREATE INDEX idx_relation_edges_type ON process_relation_edges(tenant_id, relation_type);

-- BPM 브리지 테이블 (기존 bpm_process_definition ↔ 신규 process_definitions 매핑)
CREATE TABLE bpm_process_definition_bridge (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL REFERENCES tenants(id),
    legacy_bpm_definition_id VARCHAR NOT NULL,        -- 기존 bpm_process_definition.id
    new_process_definition_id UUID NOT NULL REFERENCES process_definitions(id),
    migration_status VARCHAR(30) NOT NULL DEFAULT 'MAPPED',  -- MAPPED, MIGRATED, DEPRECATED
    migrated_at TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (legacy_bpm_definition_id)
);
```

### 2.3 백엔드 구현 (Core 서비스 확장)

#### 2.3.1 모듈 구조

```
services/core/app/modules/process_model/
├── api/
│   ├── definition_routes.py      # /api/v1/process/definitions/* 라우터
│   ├── domain_routes.py          # /api/v1/process/domains/* 라우터
│   └── relation_routes.py        # /api/v1/process/relations/* 라우터
├── application/
│   ├── definition_service.py     # 프로세스 정의 생성/수정/발행
│   ├── version_service.py        # 버전 관리 + Step bulk upsert
│   └── relation_service.py       # 관계 엣지 CRUD + Outbox 기록
├── domain/
│   ├── models.py                 # ORM: ProcessDefinition, ProcessVersion, StepDefinition, etc.
│   ├── enums.py                  # ProcessType, LifecycleStatus, StepType, RelationType
│   ├── schemas.py                # Pydantic: 요청/응답 DTO
│   └── errors.py
├── infrastructure/
│   └── repositories.py
└── validation/
    ├── namespace_validator.py     # namespace 유일성 검증
    └── relation_validator.py      # 관계 타입 조합 검증
```

#### 2.3.2 핵심 API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| `POST` | `/api/v1/process/domains` | 프로세스 도메인 생성 |
| `GET` | `/api/v1/process/domains` | 도메인 목록 (workspaceId 필터) |
| `POST` | `/api/v1/process/groups` | 프로세스 그룹 생성 |
| `GET` | `/api/v1/process/groups/tree` | 그룹 계층 트리 |
| `POST` | `/api/v1/process/definitions` | 프로세스 정의 생성 |
| `GET` | `/api/v1/process/definitions` | 정의 목록 (domain/group/status 필터) |
| `GET` | `/api/v1/process/definitions/{id}` | 정의 상세 |
| `PATCH` | `/api/v1/process/definitions/{id}` | 정의 수정 |
| `POST` | `/api/v1/process/definitions/{id}/publish` | DRAFT → PUBLISHED 발행 |
| `POST` | `/api/v1/process/definitions/{id}/clone` | 템플릿 복제 |
| `GET` | `/api/v1/process/definitions/{id}/versions` | 버전 이력 |
| `POST` | `/api/v1/process/definitions/{id}/versions/{vno}/steps:bulk-upsert` | Step 일괄 저장 |
| `GET` | `/api/v1/process/versions/{vid}/steps` | Step 목록 |
| `POST` | `/api/v1/process/relations` | 관계 엣지 생성 |
| `DELETE` | `/api/v1/process/relations/{id}` | 관계 엣지 삭제 |
| `GET` | `/api/v1/process/definitions/{id}/relations` | 프로세스 관계 목록 |
| `POST` | `/api/v1/process/interfaces` | 인터페이스 계약 생성 |
| `POST` | `/api/v1/process/rules` | 규칙 정의 생성 |
| `POST` | `/api/v1/process/kpis` | KPI 정의 생성 |

#### 2.3.3 Outbox 이벤트

- `process.definition.created`
- `process.definition.updated`
- `process.version.published`
- `process.steps.bulk_upserted`
- `process.relation.created`
- `process.relation.deleted`

#### 2.3.4 Validation 규칙

- namespace는 tenant 내 unique
- 같은 process version 내 step code unique
- PUBLISHED 버전은 직접 수정 불가 → clone 후 새 버전
- relation의 source/target는 같은 tenant
- 자기 자신 관계는 일부 타입만 허용 (INFLUENCES_KPI 등)

### 2.4 프론트엔드

#### 2.4.1 신규 피처 슬라이스

```
canvas/src/features/process-studio/
├── api/
│   └── processModelApi.ts
├── components/
│   ├── DomainSidebar.tsx          # 도메인/그룹 트리 네비게이션
│   ├── ProcessListPane.tsx        # 프로세스 정의 목록 (필터/검색)
│   ├── ProcessVersionTabs.tsx     # 버전 탭 + publish 버튼
│   ├── StepCanvas.tsx             # 단계 편집 캔버스 (기존 process-designer 연계)
│   ├── StepPropertyPanel.tsx      # 단계 속성 편집 패널
│   ├── InterfaceBindingPanel.tsx   # 인터페이스 바인딩
│   ├── RuleBindingPanel.tsx        # 규칙 바인딩
│   ├── KpiBindingPanel.tsx         # KPI 바인딩
│   └── ProcessRelationPanel.tsx    # 프로세스 간 관계 편집
├── hooks/
│   ├── useProcessDefinitions.ts
│   ├── useProcessVersions.ts
│   ├── useStepDefinitions.ts
│   └── useProcessRelations.ts
├── store/
│   └── useProcessStudioStore.ts
└── types/
    └── processModel.ts
```

#### 2.4.2 라우트 추가

```typescript
PROCESS_STUDIO: {
    ROOT: '/process-studio',
    DOMAINS: '/process-studio/domains',
    DEFINITIONS: '/process-studio/definitions',
    DEFINITION_DETAIL: '/process-studio/definitions/:id',
    DEFINITION_GRAPH: '/process-studio/definitions/:id/graph',
}
```

### 2.5 기존 BPM 모듈과의 연계 (상세 마이그레이션 전략)

기존 `bpm_process_definition.definition` 컬럼은 JSON blob으로 전체 프로세스 구조를 저장한다.
신규 스키마는 이를 `process_versions`, `step_definitions`, `interface_contracts` 등으로 정규화한다.

**마이그레이션 4단계:**

> **v4.2 핵심 원칙: 듀얼 라이트 금지**
>
> 양쪽 API가 동시에 쓰기를 허용하면 source of truth가 분열된다.
> **신규 스키마가 write source of truth**, 기존 라우트는 adapter 위임만 허용한다.

1. **브리지 테이블 생성 + 데이터 추출** (Phase 2 시작 시)
   - `bpm_process_definition_bridge` 테이블로 old ID ↔ new ID 매핑
   - `bpm_process_definition.definition` JSON에서 step/interface/rule 추출 → 신규 테이블 INSERT
   - 실패 건은 로그로 남기고 수동 확인

2. **Shadow sync 검증 기간** (Phase 2 중간)
   - 기존 `/api/process/*` 라우트: **read-only 유지** (기존 UI 호환)
   - 신규 `/api/v1/process/definitions/*` 라우트: **유일한 쓰기 경로**
   - 기존 라우트의 GET 요청은 내부적으로 신규 서비스 → 기존 JSON 변환 adapter로 위임
   - `PROCESS_MODEL_V2=true` feature flag로 process-designer UI 전환

3. **Cutover 체크리스트** (Phase 3 시작 전 통과 필수)
   - [ ] bridge 매핑률 100% (모든 기존 정의가 신규 테이블에 존재)
   - [ ] row count 일치: definition/version/step 건수 비교
   - [ ] version hash 검증: 기존 JSON hash vs 신규 정규화 재계산 hash 일치
   - [ ] 샘플 10건 수동 대조: step 순서, transition, contract 매핑 확인
   - [ ] process-designer save/load round-trip 테스트 통과

4. **전환 완료 + Rollback 계획** (Phase 4 시작 전)
   - 기존 BPM 라우트 완전 제거 또는 404 반환
   - process-designer가 신규 API만 사용하도록 전환
   - bridge 테이블의 `migration_status`를 `MIGRATED`로 갱신
   - **Rollback**: cutover 실패 시 bridge 테이블 기준으로 신규 → 기존 JSON 역변환 스크립트 실행, feature flag off로 복구

기존 process-designer (Konva)는 **StepCanvas** 컴포넌트로 재사용한다.

### 2.6 산출물

- [x] 12개 신규 테이블 (process_domains, process_groups, process_definitions, process_versions, interface_contracts, rule_definitions, kpi_definitions, step_definitions, step_transition_edges, step_kpi_bindings, process_relation_edges, bpm_process_definition_bridge)
- [x] Process Model 모듈 (3 라우터, 3 서비스, 검증기)
- [x] 19개 API 엔드포인트
- [x] Process Studio UI (정의/버전/Step 편집 + 관계 패널)
- [x] Outbox 이벤트 6종

### 2.7 테스트

- 단위: namespace 유일성, relation 타입 조합, publish workflow FSM
- 통합: 프로세스 생성 → 버전 발행 → Step bulk upsert → relation 생성 end-to-end
- 프론트: Process Studio 편집 → API 호출 → 목록 갱신 확인

### 2.8 구현 완료 파일 목록 (Phase 2 실제 구현)

| 파일 | 유형 | 구현 근거 |
| ---- | ---- | --------- |
| `migrations/003_process_model_tables.sql` | 신규 | §2.2 DDL — 12개 테이블 |
| `process_model/domain/enums.py` | 신규 | ProcessType, LifecycleStatus, StepType 등 12개 enum |
| `process_model/domain/errors.py` | 신규 | ProcessModelError 계층 (7종) |
| `process_model/domain/models.py` | 신규 | 12개 ORM 모델 (ProcessDomain ~ BpmBridge) |
| `process_model/domain/schemas.py` | 신규 | Pydantic DTO — Create/Update/Response |
| `process_model/infrastructure/repositories.py` | 신규 | 6개 Repository (CAS 패턴 포함) |
| `process_model/validation/publish_validator.py` | 신규 | §0.10 Publish Validator 12규칙 (7규칙 구조 검증) |
| `process_model/application/definition_service.py` | 신규 | DefinitionService: CRUD + 발행 + Step bulk-upsert |
| `process_model/api/definition_routes.py` | 신규 | 16개 엔드포인트 (domains/definitions/versions/steps/interfaces/rules/kpis) |
| `process_model/api/relation_routes.py` | 신규 | 3개 엔드포인트 (relation CRUD) |
| `main.py` | 수정 | pm_definition_router + pm_relation_router 등록 |

---

## 2.5. Phase 2.5: 프로세스 흐름 모델 (1주) — v3 신설

### 2.5.1 목표

Phase 2에서 생성한 `step_definitions`에 **단계 간 전이(transition)** 정보를 추가하여, 프로세스 편집기/시뮬레이션/그래프 투영이 실제 동작할 수 있도록 한다.

> `step_transition_edges` 테이블은 Phase 2 DDL에 이미 포함되어 있으므로, 이 Phase에서는 **API/서비스/UI 구현**에 집중한다.

### 2.5.2 백엔드 구현

```
services/core/app/modules/process_model/
├── api/
│   └── transition_routes.py       # /api/v1/process/transitions/* 라우터
├── application/
│   └── transition_service.py      # 전이 CRUD + 유효성 검증
└── domain/
    └── transition_validator.py     # 순환 참조 방지, START/END 제약 등
```

| Method | Path | 설명 |
|--------|------|------|
| `POST` | `/api/v1/process/versions/{vid}/transitions:bulk-upsert` | 전이 일괄 저장 |
| `GET` | `/api/v1/process/versions/{vid}/transitions` | 전이 목록 |
| `DELETE` | `/api/v1/process/transitions/{id}` | 전이 삭제 |

**Validation 규칙**:

- `from_step_id`와 `to_step_id`는 같은 `process_version_id` 소속이어야 함
- START 타입 step은 `from_step_id`로만 사용 가능
- END 타입 step은 `to_step_id`로만 사용 가능
- DECISION step에서 나가는 전이는 `is_default=true`가 정확히 1개 존재해야 함
- 순환 경로는 허용하되 경고 로그 생성

### 2.5.3 프론트엔드

- 기존 `process-designer` Konva 캔버스의 연결선(connection) 저장 포맷을 `step_transition_edges` 구조에 맞춤
- StepCanvas에서 연결선 드로잉 시 `transition_type` 선택 UI 추가
- `useConnectionDraw.ts` 훅을 `step_transition_edges` API와 연동

### 2.5.4 Outbox 이벤트

- `process.transitions.bulk_upserted` — Graph Projection Consumer가 `:NEXT`, `:YES`, `:NO`, `:ERROR` 관계로 투영

### 2.5.5 산출물

- [x] Transition API 3개 엔드포인트
- [x] 전이 유효성 검증기 (순환/START/END/DECISION 규칙)
- [x] process-designer 연결선 ↔ transition API 연동
- [x] Outbox 이벤트 1종

---

## 3. Phase 3: Graph Projection + 영향도 분석 (2주)

### 3.1 목표

Core의 process_relation_edges를 **Neo4j에 비동기 투영**하고, **영향도 탐색 API**를 Synapse에 추가한다.

### 3.2 Neo4j 스키마

```cypher
-- 제약/인덱스
CREATE CONSTRAINT process_def_id IF NOT EXISTS FOR (n:ProcessDefinition) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT process_ver_id IF NOT EXISTS FOR (n:ProcessVersion) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT step_def_id IF NOT EXISTS FOR (n:StepDefinition) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT interface_id IF NOT EXISTS FOR (n:InterfaceContract) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT rule_def_id IF NOT EXISTS FOR (n:RuleDefinition) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT kpi_def_id IF NOT EXISTS FOR (n:KpiDefinition) REQUIRE n.id IS UNIQUE;

CREATE INDEX process_def_tenant IF NOT EXISTS FOR (n:ProcessDefinition) ON (n.tenantId);
CREATE INDEX step_def_tenant IF NOT EXISTS FOR (n:StepDefinition) ON (n.tenantId);
```

### 3.3 백엔드 구현 (Synapse 서비스 확장)

#### 3.3.1 Graph Projection Consumer

```
services/synapse/app/graph/
├── process_projection_consumer.py   # Redis Streams 소비자: process.* 이벤트 처리
├── process_definition_projector.py  # Neo4j MERGE: ProcessDefinition/Version/Step 노드
├── process_relation_projector.py    # Neo4j MERGE: 관계 엣지 투영
└── projection_error_handler.py      # dead-letter 처리 + 재시도
```

#### 3.3.2 이벤트 구독 대상

- `process.definition.created` → ProcessDefinition 노드 upsert
- `process.definition.updated` → ProcessDefinition 속성 갱신
- `process.version.published` → ProcessVersion 노드 + HAS_VERSION 관계
- `process.steps.bulk_upserted` → StepDefinition 노드 + HAS_STEP/NEXT 관계
- `process.relation.created` → 동적 관계 타입 upsert (TRIGGERS, BLOCKS 등)
- `process.relation.deleted` → 관계 soft-delete (active=false)
- `process.transitions.bulk_upserted` → StepDefinition 간 `:NEXT`/`:YES`/`:NO`/`:ERROR` 관계 upsert

#### 3.3.3 영향도 분석 API (Synapse에 추가)

| Method | Path | 설명 |
|--------|------|------|
| `GET` | `/api/v3/synapse/process-graph/definitions/{id}/impact` | 영향도 확산 분석 (direction, depth) |
| `GET` | `/api/v3/synapse/process-graph/definitions/{id}/upstream` | 상류 의존 프로세스 |
| `GET` | `/api/v3/synapse/process-graph/definitions/{id}/downstream` | 하류 영향 프로세스 |
| `GET` | `/api/v3/synapse/process-graph/definitions/{id}/graph` | 전체 관계 그래프 (Cytoscape 호환) |
| `GET` | `/api/v3/synapse/process-graph/definitions/{id}/critical-path` | 병목 경로 분석 |

#### 3.3.4 핵심 Cypher 쿼리

```cypher
-- 영향도 확산 (downstream, depth=3)
MATCH p=(root:ProcessDefinition {id: $rootId, tenantId: $tenantId})
      -[:TRIGGERS|BLOCKS|DEPENDS_ON|HANDOFF_TO*1..3]->(n)
WHERE n.tenantId = $tenantId
RETURN p

-- 병목 상류 추적
MATCH p=(target:ProcessDefinition {id: $targetId, tenantId: $tenantId})
      <-[:BLOCKS|DEPENDS_ON*1..5]-(upstream)
WHERE upstream.tenantId = $tenantId
RETURN upstream, relationships(p) AS rels
ORDER BY length(p)
```

### 3.4 프론트엔드

#### 3.4.1 신규 컴포넌트

```
canvas/src/features/process-graph/
├── components/
│   ├── ProcessGraphExplorer.tsx    # Cytoscape 그래프 뷰어 (기존 ontology 패턴 재사용)
│   ├── GraphFilterBar.tsx          # 관계 타입/workspace/domain 필터
│   ├── ImpactSummaryStrip.tsx      # 영향 범위 요약 스트립
│   ├── UpstreamListCard.tsx        # 상류 프로세스 카드
│   ├── DownstreamListCard.tsx      # 하류 프로세스 카드
│   └── CriticalPathPanel.tsx       # 병목 경로 패널
├── hooks/
│   ├── useImpactAnalysis.ts
│   └── useProcessGraph.ts
└── types/
    └── processGraph.ts
```

#### 3.4.2 라우트 추가

```typescript
PROCESS_STUDIO: {
    // ...기존
    IMPACT: '/process-studio/definitions/:id/impact',
    GRAPH_EXPLORER: '/process-studio/graph',
}
```

### 3.5 산출물

- [x] Neo4j 스키마/인덱스 설정
- [x] Graph Projection Consumer (7종 이벤트 처리 — transitions 포함)
- [x] 영향도 분석 API 5개 엔드포인트
- [x] Process Graph Explorer UI (Cytoscape)
- [x] Outbox → Redis Streams → Neo4j 비동기 파이프라인

### 3.6 테스트

- 단위: Projection Consumer 이벤트 처리 로직
- 통합: Core에서 relation 생성 → Outbox → Redis → Synapse Consumer → Neo4j 조회 end-to-end
- Cypher 쿼리 정확성: Testcontainers(Neo4j)

### 2.5+3 구현 완료 파일 목록

**Phase 2.5 (프로세스 흐름 모델)**:

| 파일 | 유형 | 구현 근거 |
| ---- | ---- | --------- |
| `process_model/validation/transition_validator.py` | 신규 | §2.5 전이 유효성 검증 (START/END/cycle) |
| `process_model/application/transition_service.py` | 신규 | 전이 CRUD + CAS + validation |
| `process_model/api/transition_routes.py` | 신규 | 3개 API 엔드포인트 |
| `main.py` | 수정 | pm_transition_router 등록 |

**Phase 3 (Graph Projection + 영향도 분석)**:

| 파일 | 유형 | 구현 근거 |
| ---- | ---- | --------- |
| `synapse/graph/process_graph_bootstrap.py` | 신규 | §3.2 Neo4j 스키마 (6 constraints + 3 indexes) |
| `synapse/graph/process_definition_projector.py` | 신규 | §3.3.1 Neo4j MERGE (definition/version/step/transition/relation) |
| `synapse/graph/process_projection_consumer.py` | 신규 | §3.3.2 Redis Streams 소비자 (7종 이벤트) |
| `synapse/api/process_graph.py` | 신규 | §3.3.3 영향도 분석 API (5개 엔드포인트) |
| `synapse/main.py` | 수정 | process_graph_router 등록 |

---

## 4. Phase 4: Digital Twin Runtime 도입 (3주)

### 4.1 목표

프로세스 정의 위에 **실시간 운영 상태 모델**을 올린다. TwinEvent → TwinState → Snapshot 파이프라인을 가동하고, **운영 코크핏 대시보드**를 제공한다.

### 4.2 신규 서비스: `services/twin/`

```
services/twin/
├── app/
│   ├── main.py                        # FastAPI 앱 (포트: 8006 → 9006)
│   ├── api/
│   │   ├── instance_routes.py         # /api/v1/twin/instances/*
│   │   ├── event_routes.py            # /api/v1/twin/events
│   │   ├── state_routes.py            # /api/v1/twin/states/*
│   │   ├── snapshot_routes.py         # /api/v1/twin/snapshots/*
│   │   └── dashboard_routes.py        # /api/v1/twin/dashboard/*
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── redis_client.py
│   │   └── middleware.py
│   ├── models/
│   │   ├── instance.py                # ProcessInstance, StepInstance ORM
│   │   ├── event.py                   # TwinEvent ORM
│   │   ├── state.py                   # TwinState ORM
│   │   ├── snapshot.py                # TwinSnapshot ORM
│   │   └── schemas.py                 # Pydantic DTO
│   ├── services/
│   │   ├── instance_service.py        # 인스턴스 생성/상태 전환
│   │   ├── event_service.py           # 이벤트 적재 + 멱등성 보장
│   │   ├── state_calculator.py        # 이벤트 → 상태 파생 계산
│   │   ├── snapshot_service.py        # 스냅샷 생성/조회
│   │   └── dashboard_service.py       # 집계 쿼리
│   ├── workers/
│   │   ├── state_projector.py         # TwinEvent 소비 → TwinState 갱신
│   │   ├── snapshot_scheduler.py      # 주기적 스냅샷 생성 (15분)
│   │   └── outbox_relay.py            # TwinRelayWorker
│   └── events/
│       └── consumer.py                # Redis Streams 이벤트 소비자
├── migrations/
│   └── 001_twin_schema.sql
├── requirements.txt
├── Dockerfile
└── pytest.ini
```

### 4.3 DB 마이그레이션 (twin 스키마)

```sql
CREATE SCHEMA IF NOT EXISTS twin;

-- 트윈 엔티티 레지스트리 (어떤 도메인 엔티티가 트윈을 갖는지 등록)
CREATE TABLE twin.twin_entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL,               -- VARCHAR: 기존 tenants.id 호환
    entity_type VARCHAR(50) NOT NULL,          -- PROCESS, STEP, SYSTEM, ORG_UNIT, DATA_OBJECT, KPI
    ref_table VARCHAR(64) NOT NULL,            -- 원본 테이블명
    ref_id UUID NOT NULL,                      -- 원본 엔티티 ID
    twin_key VARCHAR(255) NOT NULL,            -- 유일 식별 키
    display_name VARCHAR(255) NOT NULL,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_twin_entities_key_active
    ON twin.twin_entities(tenant_id, twin_key) WHERE is_deleted = false;
CREATE INDEX idx_twin_entities_ref ON twin.twin_entities(tenant_id, entity_type, ref_id);

-- 프로세스 인스턴스 (실행 중인 업무)
CREATE TABLE twin.process_instances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL,
    workspace_id UUID NOT NULL,
    process_definition_id UUID NOT NULL,        -- cross-schema FK to public.process_definitions
    process_version_id UUID NOT NULL,           -- cross-schema FK to public.process_versions
    business_key VARCHAR(200),                  -- nullable: business_key 없는 인스턴스 허용
    source_system VARCHAR(100),
    status VARCHAR(30) NOT NULL,               -- CREATED, QUEUED, RUNNING, WAITING, COMPLETED, FAILED, CANCELLED
    priority VARCHAR(30),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    due_at TIMESTAMPTZ,
    current_step_instance_id UUID,              -- v3: step_instance ID (step_instances 생성 후 FK 추가)
    root_instance_id UUID,                      -- v3: self FK (아래 ALTER로 추가)
    parent_instance_id UUID,                    -- v3: self FK (아래 ALTER로 추가)
    payload_json JSONB,
    version BIGINT NOT NULL DEFAULT 0,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_by VARCHAR,
    updated_by VARCHAR,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_instances_status ON twin.process_instances(tenant_id, workspace_id, status);
CREATE INDEX idx_instances_definition ON twin.process_instances(tenant_id, process_definition_id);
-- v4.1: soft delete + null 모두 고려
CREATE UNIQUE INDEX idx_instances_business_key ON twin.process_instances(tenant_id, workspace_id, business_key)
    WHERE business_key IS NOT NULL AND is_deleted = false;
-- v3: self-reference FK
ALTER TABLE twin.process_instances
    ADD CONSTRAINT fk_instances_root FOREIGN KEY (root_instance_id) REFERENCES twin.process_instances(id),
    ADD CONSTRAINT fk_instances_parent FOREIGN KEY (parent_instance_id) REFERENCES twin.process_instances(id);

-- 단계 인스턴스
-- v4.3: 최종 FK 형태 — 단일 FK 없음, 복합 FK만 사용 (Section 0.7 정책)
CREATE TABLE twin.step_instances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL,
    workspace_id UUID NOT NULL,                 -- v3: denormalize (대시보드 집계 최적화)
    process_instance_id UUID NOT NULL,          -- v4.3: 복합 FK로만 참조 (아래 ALTER)
    step_definition_id UUID NOT NULL,           -- cross-schema FK to public.step_definitions
    status VARCHAR(30) NOT NULL,
    assigned_actor_type VARCHAR(50),
    assigned_actor_ref VARCHAR(200),
    entered_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    due_at TIMESTAMPTZ,
    wait_reason VARCHAR(200),
    result_code VARCHAR(100),
    payload_json JSONB,
    version BIGINT NOT NULL DEFAULT 0,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_by VARCHAR,
    updated_by VARCHAR,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_step_instances_process ON twin.step_instances(tenant_id, process_instance_id);
CREATE INDEX idx_step_instances_status ON twin.step_instances(tenant_id, status);
CREATE INDEX idx_step_instances_workspace_status
    ON twin.step_instances(tenant_id, workspace_id, status);  -- v3: 대시보드 집계용

-- v4.3: step_instances → process_instances 복합 FK (workspace denorm 정합성 DB 보장)
-- 단일 FK 없음 — 이 복합 FK가 유일한 참조 경로
ALTER TABLE twin.step_instances
    ADD CONSTRAINT fk_step_instances_process
    FOREIGN KEY (tenant_id, workspace_id, process_instance_id)
    REFERENCES twin.process_instances(tenant_id, workspace_id, id);

-- v3: current_step_instance_id FK (step_instances 생성 후)
ALTER TABLE twin.process_instances
    ADD CONSTRAINT fk_instances_current_step
    FOREIGN KEY (current_step_instance_id) REFERENCES twin.step_instances(id);

-- 트윈 이벤트 (모든 상태 변경의 원천)
-- v4.1: EventEnvelope 표준 필드 완전 반영
-- v4.3: Day-1 partitioned table (Section 0.13 정책에 따라 처음부터 partition)
CREATE TABLE twin.twin_events (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL,
    workspace_id UUID NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    event_version INTEGER NOT NULL DEFAULT 1,          -- v4.1: 이벤트 스키마 버전
    schema_version VARCHAR(10) NOT NULL DEFAULT '1.0', -- v4.1: envelope 구조 버전
    aggregate_type VARCHAR(50) NOT NULL,
    aggregate_id UUID NOT NULL,
    ordering_key VARCHAR(200) NOT NULL,                -- v4.1: 순서 보장 키 (aggregate_type:aggregate_id)
    aggregate_seq BIGINT NOT NULL,                     -- v4.2: aggregate 내 단조 증가 시퀀스 (순서 확정 기준)
    idempotency_key VARCHAR(200) NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    producer_service VARCHAR(50) NOT NULL DEFAULT 'twin', -- v4.1: 발행 서비스
    actor_user_id VARCHAR,                             -- v4.1: 행위자
    trace_id VARCHAR(64),                              -- v4.1: OpenTelemetry trace
    causation_id UUID,
    correlation_id UUID,
    payload_json JSONB NOT NULL,
    source_channel VARCHAR(50) NOT NULL,       -- manual-ui, api, external-system, scheduler
    processing_status VARCHAR(30) NOT NULL DEFAULT 'RECEIVED',
    version BIGINT NOT NULL DEFAULT 0,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- partition table에서는 PK에 partition key 포함 필수
    PRIMARY KEY (id, occurred_at)
) PARTITION BY RANGE (occurred_at);
-- 초기 파티션 (자동 생성 cron으로 매월 사전 생성)
CREATE TABLE twin.twin_events_2026_03 PARTITION OF twin.twin_events
    FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');
CREATE TABLE twin.twin_events_2026_04 PARTITION OF twin.twin_events
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');

-- v4.1: 멱등성 — aggregate 스코프 + soft delete 고려
CREATE UNIQUE INDEX uq_twin_events_idempotency
    ON twin.twin_events(tenant_id, aggregate_type, aggregate_id, idempotency_key, occurred_at)
    WHERE is_deleted = false;
CREATE INDEX idx_twin_events_aggregate ON twin.twin_events(tenant_id, aggregate_type, aggregate_id);
CREATE INDEX idx_twin_events_occurred ON twin.twin_events(tenant_id, event_type, occurred_at DESC);
CREATE INDEX idx_twin_events_ordering ON twin.twin_events(tenant_id, ordering_key, occurred_at);

-- 트윈 상태 (이벤트로부터 파생된 현재 상태)
CREATE TABLE twin.twin_states (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL,
    workspace_id UUID NOT NULL,
    twin_entity_id UUID NOT NULL REFERENCES twin.twin_entities(id),
    entity_type VARCHAR(50) NOT NULL,
    entity_id UUID NOT NULL,
    state_code VARCHAR(50) NOT NULL,           -- HEALTHY, DEGRADED, WAITING, BLOCKED, FAILED
    health_score NUMERIC(5,2),                 -- 0~100
    sla_status VARCHAR(30),                    -- ON_TRACK, AT_RISK, BREACHED
    queue_size INTEGER,
    avg_cycle_time_minutes NUMERIC(12,2),
    avg_wait_time_minutes NUMERIC(12,2),
    exception_rate NUMERIC(8,4),
    last_event_at TIMESTAMPTZ,
    snapshot_ref_id UUID,                       -- v3: FK 아래에서 추가
    metrics_json JSONB,
    version BIGINT NOT NULL DEFAULT 0,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_twin_states_entity_active
    ON twin.twin_states(tenant_id, workspace_id, entity_type, entity_id) WHERE is_deleted = false;
CREATE INDEX idx_twin_states_entity ON twin.twin_states(tenant_id, workspace_id, entity_type, entity_id);

-- 트윈 스냅샷 (시점 캡처)
CREATE TABLE twin.twin_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL,
    workspace_id UUID NOT NULL,
    snapshot_type VARCHAR(30) NOT NULL,         -- SCHEDULED, MANUAL, EVENT_DRIVEN, SCENARIO_BASE
    entity_scope_type VARCHAR(50) NOT NULL,
    entity_scope_id UUID,
    captured_at TIMESTAMPTZ NOT NULL,
    summary_json JSONB NOT NULL,
    version BIGINT NOT NULL DEFAULT 0,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_by VARCHAR,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_twin_snapshots_scope ON twin.twin_snapshots(tenant_id, workspace_id, entity_scope_type, captured_at DESC);

-- v3: twin_states.snapshot_ref_id FK (twin_snapshots 생성 후)
ALTER TABLE twin.twin_states
    ADD CONSTRAINT fk_twin_states_snapshot_ref
    FOREIGN KEY (snapshot_ref_id) REFERENCES twin.twin_snapshots(id);

-- Outbox — v4.1+v4.3: EventEnvelope 표준 컬럼 완전 반영
-- twin_events와 동일한 envelope 필드셋을 유지하여 consumer가 outbox만으로도
-- 모든 표준 필드를 읽을 수 있도록 한다 (twin_events join 불필요)
CREATE TABLE twin.event_outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL,
    workspace_id UUID,                                 -- v4.1: workspace 컨텍스트
    aggregate_type VARCHAR(100) NOT NULL,
    aggregate_id UUID NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    event_version INTEGER NOT NULL DEFAULT 1,
    schema_version VARCHAR(10) NOT NULL DEFAULT '1.0', -- v4.1: envelope 구조 버전
    ordering_key VARCHAR(200) NOT NULL,                -- v4.1: 순서 보장 키
    aggregate_seq BIGINT NOT NULL,                     -- v4.3: 순서 확정 기준
    idempotency_key VARCHAR(200) NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,                  -- v4.3: 이벤트 발생 시각 (twin_events와 동일)
    producer_service VARCHAR(50) NOT NULL DEFAULT 'twin', -- v4.1: 발행 서비스
    actor_user_id VARCHAR,                             -- v4.1: 행위자
    trace_id VARCHAR(64),                              -- v4.1: OpenTelemetry trace
    correlation_id UUID,                               -- v4.3: 비즈니스 상관 ID
    causation_id UUID,                                 -- v4.3: 원인 이벤트 ID
    payload_json JSONB NOT NULL,
    headers_json JSONB,                                -- 보조 확장 필드 (표준 외 추가 메타데이터)
    published BOOLEAN NOT NULL DEFAULT false,
    published_at TIMESTAMPTZ,
    retry_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- v4.1: 멱등성 — aggregate 스코프
CREATE UNIQUE INDEX uq_twin_outbox_idempotency
    ON twin.event_outbox(tenant_id, aggregate_type, aggregate_id, idempotency_key);
CREATE INDEX idx_outbox_unpublished ON twin.event_outbox(published, created_at);
```

### 4.4 핵심 API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| `POST` | `/api/v1/twin/instances` | 프로세스 인스턴스 생성 |
| `GET` | `/api/v1/twin/instances/{id}` | 인스턴스 상세 |
| `GET` | `/api/v1/twin/instances` | 인스턴스 목록 (workspace/status 필터) |
| `POST` | `/api/v1/twin/events` | 트윈 이벤트 발행 (멱등성 보장) |
| `GET` | `/api/v1/twin/states/{entityType}/{entityId}` | 현재 상태 조회 |
| `GET` | `/api/v1/twin/dashboard/workspaces/{id}` | 워크스페이스 운영 요약 |
| `GET` | `/api/v1/twin/dashboard/workspaces/{id}/processes` | 프로세스별 건강도 목록 |
| `POST` | `/api/v1/twin/snapshots` | 수동 스냅샷 캡처 |
| `GET` | `/api/v1/twin/snapshots` | 스냅샷 목록 |

### 4.5 상태 계산 로직

```python
# 건강도 점수 계산
health_score = (
    100
    - overdue_ratio * 25        # SLA 초과 비율
    - exception_rate * 30       # 예외/실패 비율
    - queue_pressure_score * 20 # 대기열 압박
    - cycle_time_breach * 25    # 처리시간 SLA 초과
)

# SLA 상태 판정
sla_status = (
    "BREACHED" if overdue_ratio > 0.15
    else "AT_RISK" if overdue_ratio > 0.05
    else "ON_TRACK"
)
```

### 4.6 Docker Compose 추가

```yaml
twin-service:
    build: ./services/twin
    ports:
        - "9006:8006"
    environment:
        DATABASE_URL: postgresql+asyncpg://arkos:arkos@postgres-db:5432/insolvency_os
        DATABASE_SCHEMA: twin
        REDIS_URL: redis://redis-bus:6379
        JWT_SECRET_KEY: ${JWT_SECRET_KEY}
    depends_on:
        - postgres-db
        - redis-bus
```

### 4.7 프론트엔드

```
canvas/src/features/digital-twin/
├── components/
│   ├── TwinCockpitPage.tsx        # 운영 코크핏 (건강도 스트립 + 병목 히트맵)
│   ├── TwinHealthStrip.tsx        # 전체 건강도 스트립
│   ├── ProcessHealthTable.tsx     # 프로세스별 건강도 테이블
│   ├── QueueLengthPanel.tsx       # 대기열 현황
│   ├── SLAAlertPanel.tsx          # SLA 위반 알림
│   ├── EventTimelinePanel.tsx     # 이벤트 타임라인
│   ├── TwinStateDrawer.tsx        # 상태 상세 드로어
│   └── SnapshotTimeline.tsx       # 스냅샷 히스토리
├── hooks/
│   ├── useTwinDashboard.ts
│   ├── useTwinState.ts
│   └── useTwinSnapshots.ts
└── types/
    └── twin.ts
```

라우트:
```typescript
DIGITAL_TWIN: {
    COCKPIT: '/digital-twin/cockpit',
    INSTANCES: '/digital-twin/instances',
    SNAPSHOTS: '/digital-twin/snapshots',
}
```

### 4.8 산출물

- [x] `services/twin/` 신규 서비스 (Dockerfile + Docker Compose)
- [x] twin 스키마 6개 테이블
- [x] 9개 API 엔드포인트
- [x] State Calculator (이벤트 → 건강도/SLA/대기열 파생)
- [x] Snapshot Scheduler (15분 주기 자동 캡처)
- [x] TwinRelayWorker (Outbox → Redis)
- [x] Twin Cockpit UI

### 4.9 테스트

- 단위: state_calculator (건강도/SLA 계산), event idempotency
- 통합: 이벤트 발행 → 상태 갱신 → 대시보드 집계 end-to-end
- Worker: snapshot_scheduler 주기 실행 확인

### 4.10 구현 완료 파일 목록 (Phase 4 실제 구현)

| 파일 | 유형 | 구현 근거 |
| ---- | ---- | --------- |
| `services/twin/` 전체 디렉토리 | 신규 서비스 | §4.2 신규 서비스 구조 |
| `twin/app/core/config.py` | 신규 | DB/Redis/JWT 설정 |
| `twin/app/core/database.py` | 신규 | SQLAlchemy async + twin 스키마 |
| `twin/app/core/redis_client.py` | 신규 | Redis 연결 |
| `twin/migrations/001_twin_schema.sql` | 신규 | §4.3 DDL — 8 테이블 + aggregate_sequences (Day-1 partition) |
| `twin/app/models/twin_models.py` | 신규 | 8 ORM 모델 (TwinEntity~AggregateSequence) |
| `twin/app/models/schemas.py` | 신규 | Pydantic DTO (Request/Response 7종) |
| `twin/app/services/state_calculator.py` | 신규 | §4.5 건강도/SLA/상태코드 계산 |
| `twin/app/api/routes.py` | 신규 | 9개 API 엔드포인트 (aggregate_seq 원자적 발급 포함) |
| `twin/app/main.py` | 신규 | FastAPI 앱 (포트 8006) |
| `twin/Dockerfile` | 신규 | 컨테이너 이미지 |
| `twin/requirements.txt` | 신규 | Python 패키지 의존성 |

---

## 5. Phase 5: Scenario / What-if 엔진 (2주)

### 5.1 목표

현재 TwinSnapshot을 baseline으로, **가정(ChangeSet)**을 적용하여 **KPI 변화/병목 해소 효과**를 계산한다.

### 5.2 DB 마이그레이션 (twin 스키마 확장)

```sql
-- 시나리오 정의
CREATE TABLE twin.scenario_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL,
    workspace_id UUID NOT NULL,
    code VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    base_snapshot_id UUID NOT NULL REFERENCES twin.twin_snapshots(id),
    scenario_type VARCHAR(50) NOT NULL,
    description TEXT,
    status VARCHAR(30) NOT NULL DEFAULT 'DRAFT',
    version BIGINT NOT NULL DEFAULT 0,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_by VARCHAR,
    updated_by VARCHAR,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_scenario_definitions_active
    ON twin.scenario_definitions(tenant_id, workspace_id, code) WHERE is_deleted = false;

-- 시나리오 변경 셋 (가정 패치)
CREATE TABLE twin.scenario_change_sets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL,
    scenario_definition_id UUID NOT NULL REFERENCES twin.scenario_definitions(id),
    change_type VARCHAR(50) NOT NULL,          -- RESOURCE_CAPACITY_CHANGE, AUTOMATION_RATE_CHANGE, etc.
    target_entity_type VARCHAR(50) NOT NULL,
    target_entity_id UUID NOT NULL,
    patch_json JSONB NOT NULL,
    display_order INTEGER NOT NULL DEFAULT 0,
    version BIGINT NOT NULL DEFAULT 0,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_scenario_change_sets_scenario ON twin.scenario_change_sets(tenant_id, scenario_definition_id);

-- 시나리오 실행
CREATE TABLE twin.scenario_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL,
    workspace_id UUID NOT NULL,
    scenario_definition_id UUID NOT NULL REFERENCES twin.scenario_definitions(id),
    base_snapshot_id UUID NOT NULL REFERENCES twin.twin_snapshots(id),
    run_number INTEGER NOT NULL DEFAULT 1,      -- 동일 시나리오의 여러 실행 구분
    status VARCHAR(30) NOT NULL DEFAULT 'PENDING',  -- PENDING, RUNNING, COMPLETED, FAILED
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    result_summary_json JSONB,
    comparison_json JSONB,                      -- baseline vs scenario diff 결과
    error_message TEXT,
    -- v4: 재현성 보장 필드
    engine_version VARCHAR(50),                 -- 시뮬레이션 엔진 버전
    input_manifest_json JSONB,                  -- 실행 시점 모든 입력 파라미터/계수 스냅샷
    baseline_snapshot_hash VARCHAR(128),         -- baseline snapshot content hash
    assumption_set_version INTEGER,             -- 가정 셋 버전
    started_by VARCHAR,                         -- 실행 요청자
    random_seed BIGINT,                         -- v4.2: 확률 요소 재현용 (DES 고도화 대비)
    engine_artifact_hash VARCHAR(128),          -- v4.2: 엔진 코드/컨테이너 해시
    version BIGINT NOT NULL DEFAULT 0,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_by VARCHAR,
    updated_by VARCHAR,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_scenario_runs_scenario ON twin.scenario_runs(tenant_id, scenario_definition_id);
CREATE UNIQUE INDEX uq_scenario_runs_run_no
    ON twin.scenario_runs(tenant_id, scenario_definition_id, run_number)
    WHERE is_deleted = false;
```

### 5.3 백엔드 구현 (Twin 서비스 내 simulation 모듈)

```
services/twin/app/
├── simulation/
│   ├── api/
│   │   └── scenario_routes.py     # /api/v1/simulation/scenarios/*
│   ├── services/
│   │   ├── scenario_service.py    # 시나리오 CRUD + 실행 트리거
│   │   └── simulation_engine.py   # 규칙 기반 근사 시뮬레이션 엔진
│   ├── models/
│   │   ├── scenario.py            # ORM
│   │   └── schemas.py             # Pydantic DTO
│   └── engine/
│       ├── change_applier.py      # ChangeSet → 상태 패치 적용
│       ├── impact_propagator.py   # PostgreSQL relation/transition 엣지 따라 downstream 재계산
│       ├── diff_calculator.py     # baseline vs scenario diff 계산
│       └── coefficient_loader.py  # v4: simulation_coefficients 테이블에서 보정계수 로드
```

### 5.4 핵심 API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| `POST` | `/api/v1/simulation/scenarios` | 시나리오 생성 |
| `GET` | `/api/v1/simulation/scenarios` | 시나리오 목록 |
| `GET` | `/api/v1/simulation/scenarios/{id}` | 시나리오 상세 |
| `POST` | `/api/v1/simulation/scenarios/{id}/runs` | 시나리오 실행 |
| `GET` | `/api/v1/simulation/runs/{id}` | 실행 결과 조회 |
| `GET` | `/api/v1/simulation/runs/{id}/diff` | baseline vs scenario diff |
| `GET` | `/api/v1/simulation/coefficients` | 보정계수 목록 (v4) |
| `PUT` | `/api/v1/simulation/coefficients` | 보정계수 수정 (v4) |

### 5.5 시뮬레이션 엔진 (초기 버전: 규칙 기반 근사)

```python
# 지원하는 변경 유형과 영향 계산
CHANGE_EFFECTS = {
    "AUTOMATION_RATE_CHANGE": lambda delta: {
        "avg_cycle_time": -delta * 0.6,     # 자동화율 1% 증가 → 처리시간 0.6% 감소
        "exception_rate": -delta * 0.3,     # 예외율 0.3% 감소
    },
    "RESOURCE_CAPACITY_CHANGE": lambda delta: {
        "queue_size": -delta * 0.4,         # 인력 1명 추가 → 대기열 0.4 감소
        "avg_wait_time": -delta * 0.5,
    },
    "THRESHOLD_RULE_CHANGE": lambda delta: {
        "exception_rate": delta * 0.2,       # 기준 강화 → 예외율 증가
        "avg_cycle_time": delta * 0.1,
    },
}
```

### 5.6 프론트엔드

```
canvas/src/features/scenario/
├── components/
│   ├── ScenarioListPage.tsx
│   ├── ScenarioEditorPage.tsx      # BaselineSelector + ChangeSetBuilder
│   ├── BaselineSnapshotSelector.tsx
│   ├── ChangeSetBuilder.tsx        # 변경 타입 선택 + 슬라이더 조정
│   ├── ScenarioRunPanel.tsx        # 실행 상태 + 진행률
│   ├── DeltaComparisonTable.tsx    # before/after KPI 비교표
│   └── KPIImpactChart.tsx          # Recharts 막대/비교 차트
├── hooks/
│   ├── useScenarios.ts
│   └── useScenarioRun.ts
└── types/
    └── scenario.ts
```

라우트:
```typescript
SIMULATION: {
    SCENARIOS: '/simulation/scenarios',
    SCENARIO_DETAIL: '/simulation/scenarios/:id',
    RUN_DETAIL: '/simulation/runs/:id',
}
```

### 5.7 산출물

- [x] 3개 시나리오 테이블 + simulation_coefficients
- [x] 규칙 기반 근사 시뮬레이션 엔진
- [x] 8개 API 엔드포인트
- [x] Scenario Workbench UI (편집기 + diff 비교)

### 5.8 구현 완료 파일 목록 (Phase 5 실제 구현)

| 파일 | 유형 | 구현 근거 |
| ---- | ---- | --------- |
| `twin/migrations/002_scenario_tables.sql` | 신규 | §5.2 DDL — 4 테이블 (scenario_definitions/change_sets/runs + simulation_coefficients) |
| `twin/simulation/models/scenario.py` | 신규 | 4 ORM 모델 (ScenarioDefinition, ScenarioChangeSet, ScenarioRun, SimulationCoefficient) |
| `twin/simulation/models/schemas.py` | 신규 | Pydantic DTO — Create/Run/Response + CoefficientUpdate |
| `twin/simulation/engine/coefficient_loader.py` | 신규 | §0.12 보정계수 DB 로드 + 전역 기본값 폴백 |
| `twin/simulation/engine/change_applier.py` | 신규 | §5.5 ChangeSet → baseline 메트릭 적용 |
| `twin/simulation/engine/diff_calculator.py` | 신규 | baseline vs scenario diff (delta + delta_pct) |
| `twin/simulation/engine/impact_propagator.py` | 신규 | PostgreSQL relation 엣지 기반 downstream 전파 |
| `twin/simulation/services/scenario_service.py` | 신규 | ScenarioService: CRUD + 실행 + 재현성 필드 기록 |
| `twin/simulation/api/scenario_routes.py` | 신규 | 8개 API 엔드포인트 (scenarios/runs/diff/coefficients) |
| `twin/app/main.py` | 수정 | simulation_router 등록 |

---

## 6. 전체 일정 요약 (v4 수정)

```
Phase 0:   플랫폼 하드닝          ─── 2주  ──→ ID 타입/보안/복구/이벤트 표준/감사/복합FK
Phase 1:   Governance 기반        ─── 2주  ──→ Tenant/Workspace scope + 관리 UI
Phase 2:   Process Definition     ─── 3주  ──→ 프로세스 스튜디오 MVP + publish validator
Phase 2.5: 프로세스 흐름 모델     ─── 1주  ──→ step_transition_edges + 편집기 연동
Phase 3:   Graph Projection       ─── 2주  ──→ 영향도 분석 + 그래프 탐색    ┐
Phase 4:   Digital Twin Runtime   ─── 3주  ──→ 운영 코크핏 + 이벤트 상태     ├ 병렬 가능
Phase 5:   Scenario / What-if     ─── 2주  ──→ PostgreSQL 기반 시뮬레이션   ┘
                                  ─── 총 12~15주 (병렬 시 12주) ──
```

### Phase 간 의존성 (v3 수정)

```
Phase 0 (하드닝)
    └──→ Phase 1 (Governance) ← 보안/타입 기반 필수
            └──→ Phase 2 (Process Model) ← tenant/workspace scope 필수
                    └──→ Phase 2.5 (흐름 모델) ← step_definitions 필수
                            ├──→ Phase 3 (Graph)  ← relation_edges + transitions + outbox
                            └──→ Phase 4 (Twin)   ← process_definitions 참조 (Phase 3 독립)
                                    └──→ Phase 5 (Scenario) ← snapshot 필수
```

> **Phase 3과 Phase 4는 병렬 진행 가능** — Phase 4(Twin)는 process_definitions(Phase 2 산출물)만
> 필요하며, Neo4j graph projection(Phase 3)과는 독립적이다. Twin Cockpit 대시보드는
> PostgreSQL 집계 쿼리를 사용하므로 Neo4j 없이 동작한다.

> **Phase 5 의존성 수정 (v3)** — Scenario의 `impact_propagator`가 "그래프 경로 따라 downstream
> 재계산"을 하므로 Neo4j 의존 가능성이 있었으나, 초기 버전은 **PostgreSQL의
> `process_relation_edges` + `step_transition_edges`만으로 영향 전파를 계산**한다.
> Neo4j 기반 고도화는 Phase 6에서 수행. 따라서 Phase 5는 Phase 3 완료를 기다리지 않아도 된다.

**절대 순서를 어겨선 안 되는 이유:**

- Phase 0 없이 착수 → 매 Phase마다 타입 충돌/보안 허점 반복
- tenant 경계 없는 그래프 → 데이터 혼선
- 흐름 모델 없는 process → Twin/Simulation/Graph 모두 불완전
- outbox 없는 graph sync → 장애 전파
- snapshot 없는 simulation → 재현 불가

---

## 7. 리스크와 대응 (v3 보강)

| # | 리스크 | 영향 | 대응 |
|---|--------|------|------|
| 1 | 기존 BPM 모델과 신규 ProcessDefinition 중복 | 데이터 이중관리 | Phase 2에서 브리지 테이블 + 4단계 마이그레이션 |
| 2 | Neo4j Projection lag 증가 | 영향도 분석 데이터 지연 | dead-letter + retry + lag metric 알림 (5분 적체) |
| 3 | Twin 서비스 장애 시 이벤트 유실 | 상태 불일치 | 멱등성 키(aggregate 스코프) + Outbox + replay CLI |
| 4 | 시뮬레이션 결과 정확도 부족 | 사용자 신뢰 하락 | 초기 "규칙 기반 근사" 명시, 실측 축적 후 고도화 |
| 5 | 스키마 마이그레이션 충돌 | 기존 서비스 장애 | ALTER는 backward-compatible, twin은 별도 스키마 |
| 6 | soft delete 후 재생성 불가 | 운영 불편 | v3: partial unique index 전면 적용 |
| 7 | workspace 헤더 조작으로 권한 상승 | 보안 취약점 | v3: membership 검증 필수, 헤더 직접 신뢰 금지 |
| 8 | Projection/State 정합성 틀어짐 | 대시보드 데이터 불일치 | v3: rebuild/recompute/reconciliation job 운영 |
| 9 | Neo4j 관계 타입 난립/주입 | 그래프 오염 | v3: 화이트리스트 enum 강제 |

---

## 8. 후순위 고도화 항목

Phase 6 이후 점진적으로 추가:

1. **BPMN import/export** — 기존 process-designer Konva 캔버스와 연동
2. **외부 시스템 실시간 연동** — CDC/webhook 기반 이벤트 자동 수집
3. **Discrete Event Simulation** — 고정밀 시뮬레이션 엔진 교체
4. **Process Mining 자동 관계 추론** — LLM 기반 프로세스 관계 후보 탐지
5. **Cross-tenant 벤치마크** — 업종별 프로세스 성과 비교
6. **AI 기반 병목 원인 추천** — LangChain Agent 연계
7. **온톨로지-프로세스 자동 매핑** — SemanticBinding 테이블 + LLM confidence scoring

---

## 9. 기존 Axiom과의 연결 포인트 정리

| Axiom 기존 자산 | 연결 방식 | Phase |
|----------------|-----------|-------|
| Core: `tenants` 테이블 | ALTER TABLE 확장 (industry_type, timezone 추가) | 1 |
| Core: `bpm_process_definition` | 브리지 테이블 → 점진적 마이그레이션 | 2 |
| Core: `event_outbox` + SyncWorker | 동일 패턴으로 process.* 이벤트 발행 | 2 |
| Synapse: Neo4j 온톨로지 그래프 | `:ProcessDefinition`-[:MAPPED_TO]->`:OntologyConcept` | 3 |
| Synapse: Graph Projection 패턴 | ProcessProjectionConsumer 추가 | 3 |
| Vision: What-if 시뮬레이션 | 기존 WhatIfWizard와 병행, 향후 통합 | 5 |
| Canvas: process-designer (Konva) | StepCanvas 컴포넌트로 재사용 | 2 |
| Canvas: ontology (Cytoscape) | ProcessGraphExplorer에서 동일 패턴 재사용 | 3 |
| Canvas: createApiClient | twin 서비스용 API 클라이언트 추가 | 4 |
| Canvas: ROUTES SSOT | GOVERNANCE, PROCESS_STUDIO, DIGITAL_TWIN, SIMULATION 추가 | 1~5 |

---

## 10. 운영 복구 경로 (v3 신설)

Outbox, Redis Streams, Neo4j projection, Twin state projector가 모두 참여하는 구조에서는 **장애 복구용 도구**가 반드시 필요하다.

### 10.1 필수 운영 도구 목록

| 도구                         | 위치                                               | 용도                                                     | Phase |
| ---------------------------- | -------------------------------------------------- | -------------------------------------------------------- | ----- |
| **outbox replay CLI**        | `services/core/scripts/outbox_replay.py`            | 미발행 이벤트 재전송 (날짜 범위/이벤트 타입 필터)        | 0     |
| **projection rebuild job**   | `services/synapse/scripts/rebuild_projection.py`    | Neo4j 전체 재구축 (PostgreSQL → Neo4j full sync)         | 3     |
| **twin state recompute**     | `services/twin/scripts/recompute_states.py`         | TwinEvent 재생 → TwinState 재계산 (workspace 단위)       | 4     |
| **PG↔Neo4j reconciliation** | `services/synapse/scripts/reconcile_graph.py`       | PostgreSQL과 Neo4j 노드/엣지 수 비교 + 불일치 리포트     | 3     |
| **DLQ monitor**              | `services/twin/workers/dlq_monitor.py`              | dead-letter 큐 적체 감시 + 알림 발송                     | 4     |

### 10.2 운영 알림 기준치

| 지표                       | 임계값             | 알림 수준  |
| -------------------------- | ------------------ | ---------- |
| outbox relay 적체          | 5분 이상 미발행    | WARNING    |
| graph projection 실패율    | 3% 초과            | CRITICAL   |
| twin state stale           | 15분 이상 미갱신   | WARNING    |
| scenario 실패 건수 급증    | 1시간 내 3건 이상  | WARNING    |
| DLQ 적체                   | 10건 이상          | CRITICAL   |

### 10.3 복구 시나리오별 대응

| 시나리오               | 복구 절차                                                                    |
| ---------------------- | ---------------------------------------------------------------------------- |
| Neo4j 데이터 유실      | `rebuild_projection.py --full` 실행 (PostgreSQL 기준 전체 재구축)            |
| TwinState 정합성 깨짐  | `recompute_states.py --workspace-id=X` 실행                                  |
| Outbox 이벤트 누락     | `outbox_replay.py --from-date=YYYY-MM-DD --event-type=process.*`             |
| 멱등성 키 충돌         | DLQ에서 원인 이벤트 확인 → 수동 승인 또는 키 재생성                          |

---

## 11. 즉시 실행 가능한 다음 단계 (v3 수정)

이 계획서 승인 후 바로 착수할 작업 — **Phase 0부터 시작**:

1. **Phase 0: TenantContext str 타입 통일** → `services/core/app/core/middleware.py` 수정
2. **Phase 0: Workspace 보안 미들웨어** → `services/core/app/core/middleware.py` 확장
3. **Phase 0: Partial unique index 정책 문서** → DDL 템플릿 작성
4. **Phase 0: outbox replay CLI** → `services/core/scripts/outbox_replay.py`
5. **Phase 0: Neo4j relation whitelist** → `services/synapse/app/graph/relation_whitelist.py`

Phase 0 완료 후:

1. **Phase 1 DB 마이그레이션 SQL 작성** → `services/core/migrations/`
2. **Phase 1 ORM 모델 구현** → `services/core/app/modules/governance/domain/models.py`
3. **Phase 1 API 라우터 구현** → `services/core/app/modules/governance/api/routes.py`
4. **Phase 1 프론트엔드 WorkspaceSelector** → `canvas/src/features/governance/`

병렬 진행 가능:

- 백엔드 팀: Phase 0 → Phase 1 API + DB
- 프론트엔드 팀: Phase 1 UI 설계 → Phase 2 화면 설계 (Phase 0 동안 선행)

---

## 12. 전체 체크리스트 (v3 + v4)

### v3 체크리스트

- [x] TenantContext 타입 보정 (`tenant_id: str`, `user_id: str`)
- [x] soft delete + partial unique 정책 전체 테이블 반영
- [x] workspace scope 검증 규칙 명문화 (4개 규칙)
- [x] membership 중복/기간 겹침 방지 인덱스
- [x] `step_transition_edges` 테이블 + Phase 2.5 신설
- [x] `current_version_id` FK DEFERRABLE, `current_version_no` 제거
- [x] step binding FK 추가 (`input_contract_id`, `output_contract_id`, `rule_set_id`)
- [x] `step_kpi_bindings` N:M 조인 테이블 추가
- [x] Twin `current_step_instance_id` + self FK + workspace denorm
- [x] 멱등성 키 스코프: `(tenant, aggregate_type, aggregate_id, key)`
- [x] Scenario 초기 버전은 PostgreSQL 기반 전파 (Neo4j 불필요)
- [x] Neo4j 관계 타입 화이트리스트 강제
- [x] 운영 복구 경로 추가 (replay/rebuild/recompute/reconcile/DLQ)
- [x] Phase 0 (플랫폼 하드닝) 신설
- [x] Phase 2.5 (프로세스 흐름 모델) 신설
- [x] Phase 간 의존성 다이어그램 업데이트
- [x] 리스크 테이블 9건으로 확장
- [x] `twin_states.snapshot_ref_id` FK 추가
- [x] `scenario_runs.run_number` + `comparison_json` 추가

### v4 체크리스트

- [x] 복합 FK 기반 tenant/workspace 정합성 DB 레벨 강제 (Section 0.7)
- [x] membership 기간 겹침 방지 — `tstzrange` exclusion constraint (Section 0.8)
- [x] 이벤트 envelope 표준 13필드 + `ordering_key` 순서 보장 정책 (Section 0.9)
- [x] publish validator 12규칙 모듈화 (Section 0.10)
- [x] `audit_logs` 테이블 + permission catalog 19개 (Section 0.11)
- [x] scenario 재현성 필드 5개 추가 (`engine_version` 등) (Section 0.12)
- [x] `simulation_coefficients` 보정계수 테이블 (Section 0.12)
- [x] retention 정책 6개 테이블 정의 (Section 0.13)
- [x] `twin_events` 월별 range partition DDL (Section 0.13)
- [x] 대시보드 복합 인덱스 3개 추가 (Section 0.13)
- [x] 동시 편집 optimistic version check + 409 VERSION_CONFLICT (Section 0.14)
- [x] draft lock Redis TTL 구조 (Section 0.14)
- [x] Phase 0 확장 (1주→2주): envelope/audit/복합FK 인프라 추가
- [x] Phase 5 `scenario_runs` DDL에 재현성 필드 반영
- [x] Phase 5 `coefficient_loader.py` + 보정계수 API 2개 추가
- [x] 전체 일정 12~15주 (병렬 시 12주)로 업데이트

### v4.1 체크리스트 (DDL 정합성 최종 보정)

- [x] `process_definitions→process_domains` 복합 FK 컬럼 수 불일치 수정 — `(tenant_id, domain_id) → (tenant_id, id)`
- [x] `twin.twin_events`에 EventEnvelope 표준 컬럼 6개 추가 (`ordering_key`, `schema_version`, `event_version`, `producer_service`, `trace_id`, `actor_user_id`)
- [x] `twin.event_outbox`에 EventEnvelope 표준 컬럼 5개 추가 (`workspace_id`, `ordering_key`, `schema_version`, `producer_service`, `trace_id`)
- [x] `twin_events` 멱등성 unique에 `WHERE is_deleted = false` 추가
- [x] `process_instances.business_key` unique에 `AND is_deleted = false` 추가
- [x] self-hierarchy 복합 FK: `org_units.parent` → `(tenant_id, id)` 참조
- [x] self-hierarchy 복합 FK: `process_groups.parent` → `(tenant_id, id)` 참조
- [x] self-hierarchy 복합 FK: `step_definitions.parent` → `(tenant_id, process_version_id, id)` 참조
- [x] self-hierarchy 복합 FK: `process_versions.parent` → `(tenant_id, id)` 참조
- [x] `step_transition_edges.from/to_step_id` → `(tenant_id, process_version_id, id)` 복합 FK 강화
- [x] Redis Streams `ordering_key` 구현 방식 정밀화 — Dispatcher 패턴 권장, 네이티브 파티셔닝 아님 명시

### v4.2 체크리스트 (운영 계약 + 정합성 최종 마감)

- [x] 듀얼 라이트 금지 — 신규 스키마 write source of truth, cutover 체크리스트 5항목 + rollback 절차
- [x] membership `scope_type` (TENANT/ORG_UNIT/WORKSPACE) + CHECK 제약 추가
- [x] `aggregate_seq BIGINT` 이벤트 순서 확정 기준 — EventEnvelope + twin_events DDL 반영
- [x] workspace denorm FK: `step_instances→process_instances` `(tenant_id, workspace_id, id)` 복합 FK
- [x] `process_definitions→process_domains` workspace 일치 `(tenant_id, workspace_id, id)` 복합 FK
- [x] 파티셔닝 Day-1 적용 대상 명확화 (`twin_events`만 Day-1, `audit_logs`는 later)
- [x] API pagination/sort/filter 규약 표준화
- [x] 에러 코드 catalog 14종 정의
- [x] Idempotency-Key 적용 엔드포인트 6개 + 저장 위치/TTL 명시
- [x] DB CAS 패턴: `UPDATE ... WHERE version = :expected` 단일 문으로 race window 제거
- [x] `process_relation_edges` polymorphic FK 참조 무결성 검증 잡 추가
- [x] `audit_logs.actor_roles` TEXT → TEXT[] 배열 + `detail_json` 마스킹 원칙
- [x] `scenario_runs`에 `random_seed` + `engine_artifact_hash` 추가

### v4.3 체크리스트 (DDL/주석/운영 규칙 1:1 최종 마감)

- [x] Section 0.7 오래된 NOTE 삭제 — "tenant만으로 충분" → "workspace 강제가 최종 정책" 통일
- [x] membership WORKSPACE CHECK: `org_unit_id IS NULL` 추가 (scope 3종 완전 잠금)
- [x] `aggregate_seq` 발급: `MAX+1` → `twin.aggregate_sequences` 전용 카운터 테이블 (`INSERT ON CONFLICT RETURNING`)
- [x] `twin.event_outbox`에 `aggregate_seq BIGINT NOT NULL` 컬럼 추가 (envelope DDL 완전 일치)
- [x] Phase 4 `twin_events` DDL: 일반 테이블 → Day-1 `PARTITION BY RANGE (occurred_at)` 통일, "NOTE: partition 고려" 제거
- [x] `step_instances`: 인라인 단일 FK `REFERENCES twin.process_instances(id)` 제거 → 복합 FK `(tenant_id, workspace_id, process_instance_id)` 최종 형태만
- [x] `twin.event_outbox`에 `occurred_at`, `correlation_id`, `causation_id` 추가 — EventEnvelope 18필드 완전 일치 확인

> **v4.3 최종 검증**: EventEnvelope dataclass 18필드 ↔ twin_events DDL ↔ event_outbox DDL 3자 대조 완료.
> 차이는 저장 레이어 전용 컬럼(`source_channel`, `processing_status`, `published`, `retry_count`)뿐이며,
> envelope 계약 필드는 100% 일치.
