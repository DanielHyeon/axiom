# Vision 데이터베이스 스키마

> **최종 수정일**: 2026-02-20
> **상태**: Draft
> **근거**: 01_architecture/architecture-overview.md, K-AIR 역설계 분석
> **변경 이력**: 2026-02-20 `org_id` → `tenant_id` 통일 (Core SSOT 기준, `app.current_tenant_id` GUC 사용)

---

## 이 문서가 답하는 질문

- Vision 모듈이 소유하는 테이블은 무엇인가?
- 각 테이블의 DDL과 필드별 의미는?
- Materialized View는 어떻게 정의되는가?
- 인덱스 전략은?
- 데이터 생명주기(생성 → 사용 → 폐기)는?

---

## 1. Vision 소유 테이블 (신규)

### 1.1 what_if_scenarios

시나리오 정의 및 상태를 관리한다.

```sql
CREATE TABLE what_if_scenarios (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id         UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    tenant_id       UUID NOT NULL,        -- Core tenants.id (JWT tenant_id)

    scenario_name   VARCHAR(200) NOT NULL,
    scenario_type   VARCHAR(20) NOT NULL DEFAULT 'CUSTOM',
        -- BASELINE, OPTIMISTIC, PESSIMISTIC, STRESS, CUSTOM
    status          VARCHAR(20) NOT NULL DEFAULT 'DRAFT',
        -- DRAFT, READY, COMPUTING, COMPLETED, FAILED, ARCHIVED
    description     TEXT,
    base_scenario_id UUID REFERENCES what_if_scenarios(id),

    -- Parameters (structured JSON)
    parameters      JSONB NOT NULL DEFAULT '{}',
    constraints     JSONB NOT NULL DEFAULT '[]',

    -- Computation metadata
    solver_method   VARCHAR(20),          -- 'SLSQP', 'linprog'
    solver_iterations INTEGER,
    computation_time_ms INTEGER,
    error_message   TEXT,

    -- Result summary (denormalized for quick access)
    is_feasible     BOOLEAN,
    feasibility_score DECIMAL(5,4),       -- 0.0000 ~ 1.0000
    total_allocation BIGINT,              -- KRW
    overall_allocation_rate DECIMAL(5,4),

    created_by      UUID NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    computed_at     TIMESTAMPTZ,

    CONSTRAINT chk_scenario_type CHECK (
        scenario_type IN ('BASELINE', 'OPTIMISTIC', 'PESSIMISTIC', 'STRESS', 'CUSTOM')
    ),
    CONSTRAINT chk_status CHECK (
        status IN ('DRAFT', 'READY', 'COMPUTING', 'COMPLETED', 'FAILED', 'ARCHIVED')
    )
);

-- Indexes
CREATE INDEX idx_scenarios_case_id ON what_if_scenarios(case_id);
CREATE INDEX idx_scenarios_tenant_id ON what_if_scenarios(tenant_id);
CREATE INDEX idx_scenarios_status ON what_if_scenarios(status);
CREATE INDEX idx_scenarios_case_status ON what_if_scenarios(case_id, status);

-- RLS Policy (Core와 동일한 GUC 변수 사용)
ALTER TABLE what_if_scenarios ENABLE ROW LEVEL SECURITY;
CREATE POLICY scenarios_tenant_isolation ON what_if_scenarios
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);
```

### 1.2 scenario_parameter_overrides

시나리오별 개별 파라미터 오버라이드를 관리한다.

```sql
CREATE TABLE scenario_parameter_overrides (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scenario_id     UUID NOT NULL REFERENCES what_if_scenarios(id) ON DELETE CASCADE,

    parameter_path  VARCHAR(100) NOT NULL,  -- 'interest_rate', 'ebitda_growth_rate'
    original_value  DECIMAL(20,6),
    override_value  DECIMAL(20,6) NOT NULL,
    description     TEXT,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_scenario_param UNIQUE (scenario_id, parameter_path)
);

CREATE INDEX idx_overrides_scenario_id ON scenario_parameter_overrides(scenario_id);
```

### 1.3 scenario_results

시나리오 계산 결과를 연도/이해관계자 클래스별로 저장한다.

```sql
CREATE TABLE scenario_results (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scenario_id     UUID NOT NULL REFERENCES what_if_scenarios(id) ON DELETE CASCADE,

    result_type     VARCHAR(20) NOT NULL,   -- 'yearly', 'stakeholder_class', 'summary'
    period          INTEGER,                 -- year number (for 'yearly')
    stakeholder_class  VARCHAR(20),            -- 'priority', 'secured', 'unsecured'

    -- Financial metrics
    revenue         BIGINT,
    ebitda          BIGINT,
    interest_expense BIGINT,
    operating_cost  BIGINT,
    disposal_proceeds BIGINT,
    net_cashflow    BIGINT,
    allocation_amount BIGINT,
    cumulative_allocation BIGINT,
    cash_balance    BIGINT,
    dscr            DECIMAL(5,2),

    -- Stakeholder class metrics
    total_obligation BIGINT,
    allocation_rate  DECIMAL(5,4),

    -- Extra data
    metadata        JSONB DEFAULT '{}',

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_result_type CHECK (
        result_type IN ('yearly', 'stakeholder_class', 'summary')
    )
);

CREATE INDEX idx_results_scenario_id ON scenario_results(scenario_id);
CREATE INDEX idx_results_type ON scenario_results(scenario_id, result_type);
```

### 1.4 cube_definitions

큐브 정의 XML을 저장한다.

```sql
CREATE TABLE cube_definitions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL,        -- Core tenants.id
    name            VARCHAR(100) NOT NULL,
    xml_content     TEXT NOT NULL,
    fact_table      VARCHAR(100) NOT NULL,
    dimension_count INTEGER NOT NULL,
    measure_count   INTEGER NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,

    uploaded_by     UUID,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_cube_tenant_name UNIQUE (tenant_id, name)
);

CREATE INDEX idx_cube_tenant ON cube_definitions(tenant_id);

ALTER TABLE cube_definitions ENABLE ROW LEVEL SECURITY;
CREATE POLICY cubes_tenant_isolation ON cube_definitions
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);
```

### 1.5 etl_sync_history

ETL 동기화 이력을 기록한다.

```sql
CREATE TABLE etl_sync_history (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL,        -- Core tenants.id
    sync_type       VARCHAR(20) NOT NULL,   -- 'full', 'incremental', 'event'
    target_view     VARCHAR(100) NOT NULL,
    status          VARCHAR(20) NOT NULL,   -- 'running', 'completed', 'failed'

    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    duration_ms     INTEGER,
    rows_affected   INTEGER,
    error_message   TEXT,
    triggered_by    VARCHAR(50)             -- 'airflow', 'api', 'event:data_registered'
);

CREATE INDEX idx_sync_history_tenant ON etl_sync_history(tenant_id);
CREATE INDEX idx_sync_history_view ON etl_sync_history(tenant_id, target_view, started_at DESC);
```

---

## 2. Phase 4 테이블 (See-Why)

### 2.1 causal_graphs

인과 그래프 모델을 저장한다.

```sql
CREATE TABLE causal_graphs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL,        -- Core tenants.id
    case_type       VARCHAR(20) NOT NULL,   -- 'RESTRUCTURING', 'GROWTH'
    version         VARCHAR(20) NOT NULL,   -- 'v1.0', 'v2.1'

    nodes_json      JSONB NOT NULL,         -- Variable definitions
    edges_json      JSONB NOT NULL,         -- Causal edges with coefficients
    edge_count      INTEGER NOT NULL,
    training_samples INTEGER NOT NULL,
    training_data_range JSONB,              -- {"from": "2020-01", "to": "2025-12"}

    algorithm       VARCHAR(50),            -- 'PC+LiNGAM', 'PC', 'LiNGAM'
    overall_confidence DECIMAL(5,4),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_by     UUID,                   -- HITL reviewer
    reviewed_at     TIMESTAMPTZ,

    CONSTRAINT uq_causal_graph_version UNIQUE (tenant_id, case_type, version)
);

CREATE INDEX idx_causal_graphs_tenant ON causal_graphs(tenant_id);

ALTER TABLE causal_graphs ENABLE ROW LEVEL SECURITY;
CREATE POLICY causal_graphs_tenant_isolation ON causal_graphs
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);
```

### 2.2 case_causal_analysis

사건별 인과 분석 결과를 저장한다.

```sql
CREATE TABLE case_causal_analysis (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id         UUID NOT NULL REFERENCES cases(id),
    tenant_id       UUID NOT NULL,        -- Core tenants.id
    graph_id        UUID NOT NULL REFERENCES causal_graphs(id),

    status          VARCHAR(20) NOT NULL DEFAULT 'PENDING',
        -- PENDING, ANALYZING, COMPLETED, FAILED
    root_causes_json JSONB,                 -- Ranked root causes with SHAP
    timeline_json   JSONB,                  -- Causal timeline events
    shap_values_json JSONB,                 -- Full SHAP breakdown
    overall_confidence DECIMAL(5,4),

    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    computation_time_ms INTEGER,
    error_message   TEXT,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_causal_analysis_case ON case_causal_analysis(case_id);
CREATE INDEX idx_causal_analysis_tenant ON case_causal_analysis(tenant_id);

ALTER TABLE case_causal_analysis ENABLE ROW LEVEL SECURITY;
CREATE POLICY causal_analysis_tenant_isolation ON case_causal_analysis
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);
```

### 2.3 causal_explanations

LLM 생성 설명문과 반사실 분석 결과를 저장한다.

```sql
CREATE TABLE causal_explanations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id     UUID NOT NULL REFERENCES case_causal_analysis(id) ON DELETE CASCADE,
    case_id         UUID NOT NULL REFERENCES cases(id),
    tenant_id       UUID NOT NULL,        -- Core tenants.id (JWT tenant_id)

    explanation_type VARCHAR(30) NOT NULL,
        -- 'summary', 'detailed', 'counterfactual'
    causal_chain    JSONB,                  -- Ordered causal events
    shap_values     JSONB,                  -- Related SHAP values
    counterfactual_json JSONB,              -- Counterfactual scenarios
    explanation_text TEXT,                   -- LLM-generated Korean text
    language        VARCHAR(5) DEFAULT 'ko',

    confidence      DECIMAL(5,4),
    llm_model       VARCHAR(50),            -- 'gpt-4o'
    prompt_version  VARCHAR(20),            -- 'v1.0'

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_explanations_analysis ON causal_explanations(analysis_id);
CREATE INDEX idx_explanations_case ON causal_explanations(case_id);
CREATE INDEX idx_explanations_tenant ON causal_explanations(tenant_id);

ALTER TABLE causal_explanations ENABLE ROW LEVEL SECURITY;
CREATE POLICY explanations_tenant_isolation ON causal_explanations
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);
```

---

## 2.4 자식 테이블 격리 전략

| 테이블 | tenant_id | RLS | 격리 방식 | 비고 |
|--------|-----------|-----|----------|------|
| `what_if_scenarios` | O | O | 직접 격리 | 루트 엔티티 |
| `scenario_parameter_overrides` | - | - | FK CASCADE (`scenario_id`) | 항상 scenario_id 경유 접근 |
| `scenario_results` | - | - | FK CASCADE (`scenario_id`) | 항상 scenario_id 경유 접근 |
| `cube_definitions` | O | O | 직접 격리 | 독립 엔티티 |
| `etl_sync_history` | O | - | WHERE 조건 | 이력 테이블 |
| `causal_graphs` | O | O | 직접 격리 | 독립 엔티티 |
| `case_causal_analysis` | O | O | 직접 격리 | case_id + tenant_id |
| `causal_explanations` | O | O | 직접 격리 | case_id로 독립 조회 가능 |

> **설계 원칙**: `case_id`로 독립 조회하는 테이블은 반드시 `tenant_id` + RLS를 갖는다. FK CASCADE로만 접근하는 순수 자식 테이블(`scenario_parameter_overrides`, `scenario_results`)은 부모 RLS에 위임한다.

---

## 3. 데이터 생명주기

| 데이터 | 생성 | 사용 | 보관 | 폐기 |
|--------|------|------|------|------|
| 시나리오 | 사용자 생성 | 비교/분석 | ARCHIVED 상태 | 케이스 삭제 시 CASCADE |
| 시나리오 결과 | 솔버 계산 | 비교표/차트 | 시나리오와 동일 | 시나리오 삭제 시 CASCADE |
| 큐브 정의 | 관리자 업로드 | 피벗 쿼리 시 참조 | 무기한 | 수동 삭제 |
| MV 데이터 | ETL REFRESH | 피벗 쿼리 | 다음 REFRESH까지 | REFRESH로 대체 |
| 인과 그래프 | ML 학습 | 분석 요청 시 | 버전 관리 | 비활성화 (is_active=false) |
| 분석 결과 | 분석 실행 | 조회/보고서 | 무기한 | 수동 삭제 |
| LLM 설명문 | LLM 생성 | 보고서 삽입 | 분석 결과와 동일 | 분석 삭제 시 CASCADE |

---

## 4. 금액 표현 규칙

| 규칙 | 설명 |
|------|------|
| 단위 | KRW (원) |
| 타입 | `BIGINT` (정수) |
| 이유 | 소수점 없음 (원화), DECIMAL보다 연산 빠름 |
| 표시 형식 | 프론트엔드에서 "5,200,000,000" 또는 "52억" 변환 |

---

## 관련 문서

- Core DB 운영 (`services/core/docs/06_data/database-operations.md`): 백업/복구, MV 갱신 pg_cron, 슬로우 쿼리 관리, 관리자 대시보드

<!-- affects: 03_backend/service-structure.md, 01_architecture/architecture-overview.md -->
<!-- requires-update: 없음 (이 문서가 스키마 원본) -->
