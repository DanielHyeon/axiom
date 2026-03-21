-- OLAP Studio 초기 스키마 마이그레이션
-- 버전: 001
-- 설명: 19개 테이블 생성 (데이터소스, 모델, 큐브, ETL, 피벗, 리니지, AI, Outbox)

-- 스키마 생성
CREATE SCHEMA IF NOT EXISTS olap;

-- ─── 3.1 데이터 소스 ────────────────────────────────────────

CREATE TABLE olap.data_sources (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id               UUID NOT NULL,
    project_id              UUID NOT NULL,
    name                    VARCHAR(200) NOT NULL,
    source_type             VARCHAR(50) NOT NULL DEFAULT 'POSTGRES',
    connection_config       JSONB NOT NULL DEFAULT '{}',
    credential_ref          VARCHAR(200) DEFAULT '',
    is_active               BOOLEAN NOT NULL DEFAULT true,
    last_health_status      VARCHAR(20),
    last_health_checked_at  TIMESTAMP,
    created_at              TIMESTAMP NOT NULL DEFAULT now(),
    created_by              VARCHAR(100) NOT NULL,
    updated_at              TIMESTAMP NOT NULL DEFAULT now(),
    updated_by              VARCHAR(100) NOT NULL,
    deleted_at              TIMESTAMP,
    UNIQUE(tenant_id, project_id, name)
);

-- ─── 3.2 스타 스키마 모델 ───────────────────────────────────

CREATE TABLE olap.models (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL,
    project_id          UUID NOT NULL,
    name                VARCHAR(200) NOT NULL,
    description         TEXT DEFAULT '',
    source_id           UUID REFERENCES olap.data_sources(id),
    model_status        VARCHAR(20) NOT NULL DEFAULT 'DRAFT',
    semantic_version    VARCHAR(20) NOT NULL DEFAULT '0.1.0',
    published_at        TIMESTAMP,
    created_at          TIMESTAMP NOT NULL DEFAULT now(),
    created_by          VARCHAR(100) NOT NULL,
    updated_at          TIMESTAMP NOT NULL DEFAULT now(),
    updated_by          VARCHAR(100) NOT NULL,
    deleted_at          TIMESTAMP,
    version_no          INT NOT NULL DEFAULT 1,
    UNIQUE(tenant_id, project_id, name)
);

CREATE TABLE olap.dimensions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id            UUID NOT NULL REFERENCES olap.models(id) ON DELETE CASCADE,
    name                VARCHAR(200) NOT NULL,
    physical_table_name VARCHAR(200) NOT NULL,
    grain_description   TEXT DEFAULT '',
    column_map          JSONB NOT NULL DEFAULT '{}',
    hierarchies         JSONB NOT NULL DEFAULT '[]',
    attributes          JSONB NOT NULL DEFAULT '[]',
    created_at          TIMESTAMP NOT NULL DEFAULT now(),
    updated_at          TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE(model_id, name)
);

CREATE TABLE olap.facts (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id                UUID NOT NULL REFERENCES olap.models(id) ON DELETE CASCADE,
    name                    VARCHAR(200) NOT NULL,
    physical_table_name     VARCHAR(200) NOT NULL,
    grain_description       TEXT DEFAULT '',
    measures                JSONB NOT NULL DEFAULT '[]',
    degenerate_dimensions   JSONB NOT NULL DEFAULT '[]',
    created_at              TIMESTAMP NOT NULL DEFAULT now(),
    updated_at              TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE(model_id, name)
);

CREATE TABLE olap.joins (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id            UUID NOT NULL REFERENCES olap.models(id) ON DELETE CASCADE,
    left_entity_type    VARCHAR(20) NOT NULL,
    left_entity_id      UUID NOT NULL,
    right_entity_type   VARCHAR(20) NOT NULL,
    right_entity_id     UUID NOT NULL,
    join_type           VARCHAR(20) NOT NULL DEFAULT 'INNER',
    join_expression     TEXT NOT NULL DEFAULT '',
    cardinality         VARCHAR(10) NOT NULL DEFAULT '1:N',
    is_active           BOOLEAN NOT NULL DEFAULT true,
    created_at          TIMESTAMP NOT NULL DEFAULT now(),
    updated_at          TIMESTAMP NOT NULL DEFAULT now()
);

-- ─── 3.3 큐브 / Mondrian ───────────────────────────────────

CREATE TABLE olap.cubes (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL,
    project_id          UUID NOT NULL,
    model_id            UUID REFERENCES olap.models(id),
    name                VARCHAR(200) NOT NULL,
    description         TEXT DEFAULT '',
    cube_status         VARCHAR(20) NOT NULL DEFAULT 'DRAFT',
    ai_generated        BOOLEAN NOT NULL DEFAULT false,
    default_currency    VARCHAR(10),
    default_locale      VARCHAR(10),
    metadata            JSONB NOT NULL DEFAULT '{}',
    created_at          TIMESTAMP NOT NULL DEFAULT now(),
    created_by          VARCHAR(100) NOT NULL,
    updated_at          TIMESTAMP NOT NULL DEFAULT now(),
    updated_by          VARCHAR(100) NOT NULL,
    deleted_at          TIMESTAMP,
    version_no          INT NOT NULL DEFAULT 1,
    UNIQUE(tenant_id, project_id, name)
);

CREATE TABLE olap.cube_dimensions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cube_id             UUID NOT NULL REFERENCES olap.cubes(id) ON DELETE CASCADE,
    dimension_name      VARCHAR(200) NOT NULL,
    source_dimension_id UUID REFERENCES olap.dimensions(id),
    display_order       INT NOT NULL DEFAULT 0,
    visibility_rule     JSONB NOT NULL DEFAULT '{}',
    UNIQUE(cube_id, dimension_name)
);

CREATE TABLE olap.cube_measures (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cube_id             UUID NOT NULL REFERENCES olap.cubes(id) ON DELETE CASCADE,
    measure_name        VARCHAR(200) NOT NULL,
    aggregation_type    VARCHAR(30) NOT NULL DEFAULT 'SUM',
    expression          TEXT,
    format_string       VARCHAR(50),
    display_order       INT NOT NULL DEFAULT 0,
    UNIQUE(cube_id, measure_name)
);

CREATE TABLE olap.mondrian_documents (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cube_id             UUID NOT NULL REFERENCES olap.cubes(id) ON DELETE CASCADE,
    xml_content         TEXT NOT NULL,
    xml_hash            VARCHAR(64) NOT NULL,
    document_status     VARCHAR(20) NOT NULL DEFAULT 'GENERATED',
    validation_result   JSONB,
    deployed_at         TIMESTAMP,
    created_at          TIMESTAMP NOT NULL DEFAULT now(),
    updated_at          TIMESTAMP NOT NULL DEFAULT now()
);

-- ─── 3.4 ETL ────────────────────────────────────────────────

CREATE TABLE olap.etl_pipelines (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL,
    project_id          UUID NOT NULL,
    name                VARCHAR(200) NOT NULL,
    description         TEXT DEFAULT '',
    pipeline_type       VARCHAR(20) NOT NULL DEFAULT 'BATCH',
    source_config       JSONB NOT NULL DEFAULT '{}',
    target_config       JSONB NOT NULL DEFAULT '{}',
    transform_spec      JSONB NOT NULL DEFAULT '{}',
    schedule_cron       VARCHAR(100),
    airflow_dag_id      VARCHAR(200),
    status              VARCHAR(20) NOT NULL DEFAULT 'DRAFT',
    created_at          TIMESTAMP NOT NULL DEFAULT now(),
    created_by          VARCHAR(100) NOT NULL,
    updated_at          TIMESTAMP NOT NULL DEFAULT now(),
    updated_by          VARCHAR(100) NOT NULL,
    deleted_at          TIMESTAMP,
    version_no          INT NOT NULL DEFAULT 1,
    UNIQUE(tenant_id, project_id, name)
);

CREATE TABLE olap.etl_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pipeline_id     UUID NOT NULL REFERENCES olap.etl_pipelines(id),
    run_status      VARCHAR(20) NOT NULL DEFAULT 'QUEUED',
    trigger_type    VARCHAR(20) NOT NULL DEFAULT 'MANUAL',
    started_at      TIMESTAMP,
    ended_at        TIMESTAMP,
    rows_read       BIGINT DEFAULT 0,
    rows_written    BIGINT DEFAULT 0,
    error_message   TEXT,
    metrics         JSONB NOT NULL DEFAULT '{}',
    triggered_by    VARCHAR(100) NOT NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE olap.etl_run_steps (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id          UUID NOT NULL REFERENCES olap.etl_runs(id) ON DELETE CASCADE,
    step_name       VARCHAR(200) NOT NULL,
    step_order      INT NOT NULL,
    step_status     VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    started_at      TIMESTAMP,
    ended_at        TIMESTAMP,
    metrics         JSONB NOT NULL DEFAULT '{}',
    error_message   TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT now()
);

-- ─── 3.5 피벗 / 질의 이력 ──────────────────────────────────

CREATE TABLE olap.pivot_views (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL,
    project_id      UUID NOT NULL,
    cube_id         UUID REFERENCES olap.cubes(id),
    name            VARCHAR(200) NOT NULL,
    layout          JSONB NOT NULL DEFAULT '{}',
    filter_config   JSONB NOT NULL DEFAULT '{}',
    sort_config     JSONB NOT NULL DEFAULT '{}',
    owner_user_id   VARCHAR(100) NOT NULL,
    is_shared       BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMP NOT NULL DEFAULT now(),
    updated_at      TIMESTAMP NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMP
);

CREATE TABLE olap.query_history (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL,
    project_id          UUID NOT NULL,
    query_type          VARCHAR(20) NOT NULL,
    cube_id             UUID,
    input_text          TEXT,
    generated_sql       TEXT,
    execution_ms        INT,
    result_row_count    INT,
    status              VARCHAR(20) NOT NULL DEFAULT 'SUCCESS',
    error_message       TEXT,
    executed_by         VARCHAR(100) NOT NULL,
    created_at          TIMESTAMP NOT NULL DEFAULT now()
);

-- ─── 3.6 리니지 ─────────────────────────────────────────────

CREATE TABLE olap.lineage_entities (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL,
    project_id      UUID NOT NULL,
    entity_type     VARCHAR(30) NOT NULL,
    entity_key      VARCHAR(500) NOT NULL,
    display_name    VARCHAR(200) NOT NULL,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMP NOT NULL DEFAULT now(),
    updated_at      TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE(tenant_id, project_id, entity_type, entity_key)
);

CREATE TABLE olap.lineage_edges (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_entity_id  UUID NOT NULL REFERENCES olap.lineage_entities(id) ON DELETE CASCADE,
    to_entity_id    UUID NOT NULL REFERENCES olap.lineage_entities(id) ON DELETE CASCADE,
    edge_type       VARCHAR(30) NOT NULL,
    relation        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE(from_entity_id, to_entity_id, edge_type)
);

-- ─── 3.7 AI 생성 결과 ──────────────────────────────────────

CREATE TABLE olap.ai_generations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL,
    project_id      UUID NOT NULL,
    generation_type VARCHAR(30) NOT NULL,
    input_context   JSONB NOT NULL DEFAULT '{}',
    result          JSONB NOT NULL DEFAULT '{}',
    status          VARCHAR(20) NOT NULL DEFAULT 'COMPLETED',
    approved_by     VARCHAR(100),
    approved_at     TIMESTAMP,
    created_at      TIMESTAMP NOT NULL DEFAULT now(),
    created_by      VARCHAR(100) NOT NULL
);

-- ─── 3.8 Outbox 이벤트 ─────────────────────────────────────

CREATE TABLE olap.outbox_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL,
    project_id      UUID NOT NULL,
    aggregate_type  VARCHAR(50) NOT NULL,
    aggregate_id    UUID NOT NULL,
    event_type      VARCHAR(100) NOT NULL,
    event_version   VARCHAR(10) NOT NULL DEFAULT '1.0',
    payload         JSONB NOT NULL,
    occurred_at     TIMESTAMP NOT NULL DEFAULT now(),
    published_at    TIMESTAMP,
    publish_status  VARCHAR(20) NOT NULL DEFAULT 'PENDING'
);

-- ─── 인덱스 ─────────────────────────────────────────────────

CREATE INDEX idx_data_sources_tenant ON olap.data_sources(tenant_id, project_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_models_tenant ON olap.models(tenant_id, project_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_cubes_tenant ON olap.cubes(tenant_id, project_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_etl_pipelines_tenant ON olap.etl_pipelines(tenant_id, project_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_etl_runs_pipeline ON olap.etl_runs(pipeline_id, started_at DESC);
CREATE INDEX idx_etl_run_steps_run ON olap.etl_run_steps(run_id, step_order);
CREATE INDEX idx_pivot_views_tenant ON olap.pivot_views(tenant_id, project_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_query_history_tenant ON olap.query_history(tenant_id, project_id, created_at DESC);
CREATE INDEX idx_lineage_entities_tenant ON olap.lineage_entities(tenant_id, project_id);
CREATE INDEX idx_lineage_edges_from ON olap.lineage_edges(from_entity_id);
CREATE INDEX idx_lineage_edges_to ON olap.lineage_edges(to_entity_id);
CREATE INDEX idx_ai_generations_tenant ON olap.ai_generations(tenant_id, project_id, created_at DESC);
CREATE INDEX idx_outbox_pending ON olap.outbox_events(publish_status, occurred_at) WHERE publish_status = 'PENDING';

-- ─── DW 스키마 (OLAP 데이터 웨어하우스용) ──────────────────
CREATE SCHEMA IF NOT EXISTS dw;
