-- ============================================================
-- Phase 2: Process Definition 모델 — DB 마이그레이션
-- 구현 계획서 §2.2 기준 — 12개 테이블
-- 모든 UNIQUE는 partial unique index (soft delete 정책)
-- ============================================================

-- 1. process_domains: 업무 영역 분류
CREATE TABLE IF NOT EXISTS process_domains (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL REFERENCES tenants(id),
    workspace_id UUID NOT NULL REFERENCES workspaces(id),
    code VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    domain_type VARCHAR(64),
    description TEXT,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_process_domains_active
    ON process_domains(tenant_id, workspace_id, code) WHERE is_deleted = false;

-- 2. process_groups: 폴더 구조
CREATE TABLE IF NOT EXISTS process_groups (
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
CREATE UNIQUE INDEX IF NOT EXISTS uq_process_groups_active
    ON process_groups(tenant_id, domain_id, code) WHERE is_deleted = false;
CREATE INDEX IF NOT EXISTS idx_process_groups_tenant_domain ON process_groups(tenant_id, domain_id);

-- 3. process_definitions: 프로세스 정의
CREATE TABLE IF NOT EXISTS process_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL REFERENCES tenants(id),
    workspace_id UUID NOT NULL REFERENCES workspaces(id),
    domain_id UUID NOT NULL REFERENCES process_domains(id),
    group_id UUID REFERENCES process_groups(id),
    namespace VARCHAR(300) NOT NULL,
    code VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    process_type VARCHAR(50) NOT NULL,
    lifecycle_status VARCHAR(30) NOT NULL DEFAULT 'DRAFT',
    owner_org_unit_id UUID REFERENCES org_units(id),
    primary_role_code VARCHAR(100),
    current_version_id UUID,
    is_template BOOLEAN NOT NULL DEFAULT false,
    template_source_id UUID,
    ontology_concept_id VARCHAR(128),
    version BIGINT NOT NULL DEFAULT 0,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_by VARCHAR,
    updated_by VARCHAR,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_process_definitions_namespace_active
    ON process_definitions(tenant_id, namespace) WHERE is_deleted = false;
CREATE UNIQUE INDEX IF NOT EXISTS uq_process_definitions_domain_code_active
    ON process_definitions(tenant_id, domain_id, code) WHERE is_deleted = false;
CREATE INDEX IF NOT EXISTS idx_process_definitions_tenant_domain ON process_definitions(tenant_id, domain_id);
CREATE INDEX IF NOT EXISTS idx_process_definitions_tenant_status ON process_definitions(tenant_id, lifecycle_status)
    WHERE is_deleted = false;

-- 4. process_versions: 버전 관리
CREATE TABLE IF NOT EXISTS process_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL REFERENCES tenants(id),
    process_definition_id UUID NOT NULL REFERENCES process_definitions(id),
    version_no INTEGER NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'DRAFT',
    source_type VARCHAR(30) NOT NULL DEFAULT 'MANUAL',
    parent_version_id UUID REFERENCES process_versions(id),
    change_summary TEXT,
    hash VARCHAR(128),
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
CREATE UNIQUE INDEX IF NOT EXISTS uq_process_versions_active
    ON process_versions(tenant_id, process_definition_id, version_no) WHERE is_deleted = false;
CREATE INDEX IF NOT EXISTS idx_process_versions_tenant_def ON process_versions(tenant_id, process_definition_id);

-- current_version_id FK (순환 참조 → DEFERRABLE)
ALTER TABLE process_definitions
    ADD CONSTRAINT fk_process_definitions_current_version
    FOREIGN KEY (current_version_id) REFERENCES process_versions(id)
    DEFERRABLE INITIALLY DEFERRED;

-- 5. interface_contracts: 입출력 스키마
CREATE TABLE IF NOT EXISTS interface_contracts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL REFERENCES tenants(id),
    workspace_id UUID NOT NULL REFERENCES workspaces(id),
    code VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    contract_type VARCHAR(50) NOT NULL,
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
CREATE UNIQUE INDEX IF NOT EXISTS uq_interface_contracts_active
    ON interface_contracts(tenant_id, workspace_id, code, COALESCE(version_label, ''))
    WHERE is_deleted = false;

-- 6. rule_definitions: 규칙 정의
CREATE TABLE IF NOT EXISTS rule_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL REFERENCES tenants(id),
    workspace_id UUID NOT NULL REFERENCES workspaces(id),
    code VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    rule_type VARCHAR(50) NOT NULL,
    expression_language VARCHAR(50) NOT NULL,
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
CREATE UNIQUE INDEX IF NOT EXISTS uq_rule_definitions_active
    ON rule_definitions(tenant_id, workspace_id, code) WHERE is_deleted = false;

-- 7. kpi_definitions: KPI 정의
CREATE TABLE IF NOT EXISTS kpi_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL REFERENCES tenants(id),
    workspace_id UUID NOT NULL REFERENCES workspaces(id),
    code VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    unit VARCHAR(50),
    target_direction VARCHAR(20) NOT NULL,
    aggregation_type VARCHAR(30) NOT NULL,
    formula_text TEXT,
    version BIGINT NOT NULL DEFAULT 0,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_by VARCHAR,
    updated_by VARCHAR,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_kpi_definitions_active
    ON kpi_definitions(tenant_id, workspace_id, code) WHERE is_deleted = false;

-- 8. step_definitions: 프로세스 내 단계
CREATE TABLE IF NOT EXISTS step_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL REFERENCES tenants(id),
    process_version_id UUID NOT NULL REFERENCES process_versions(id),
    parent_step_id UUID REFERENCES step_definitions(id),
    code VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    step_type VARCHAR(50) NOT NULL,
    actor_type VARCHAR(50) NOT NULL,
    actor_ref VARCHAR(200),
    automation_level VARCHAR(32) NOT NULL DEFAULT 'MANUAL',
    input_contract_id UUID REFERENCES interface_contracts(id),
    output_contract_id UUID REFERENCES interface_contracts(id),
    rule_set_id UUID REFERENCES rule_definitions(id),
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
CREATE UNIQUE INDEX IF NOT EXISTS uq_step_definitions_active
    ON step_definitions(tenant_id, process_version_id, code) WHERE is_deleted = false;
CREATE INDEX IF NOT EXISTS idx_step_definitions_version ON step_definitions(tenant_id, process_version_id);

-- 9. step_transition_edges: 단계 간 전이
CREATE TABLE IF NOT EXISTS step_transition_edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL REFERENCES tenants(id),
    process_version_id UUID NOT NULL REFERENCES process_versions(id),
    from_step_id UUID NOT NULL REFERENCES step_definitions(id),
    to_step_id UUID NOT NULL REFERENCES step_definitions(id),
    transition_type VARCHAR(50) NOT NULL,
    condition_expression TEXT,
    is_default BOOLEAN NOT NULL DEFAULT false,
    display_order INTEGER NOT NULL DEFAULT 0,
    metadata_json JSONB,
    version BIGINT NOT NULL DEFAULT 0,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_step_transition_active
    ON step_transition_edges(tenant_id, process_version_id, from_step_id, to_step_id, transition_type)
    WHERE is_deleted = false;

-- 10. step_kpi_bindings: Step ↔ KPI N:M
CREATE TABLE IF NOT EXISTS step_kpi_bindings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL REFERENCES tenants(id),
    step_definition_id UUID NOT NULL REFERENCES step_definitions(id),
    kpi_definition_id UUID NOT NULL REFERENCES kpi_definitions(id),
    binding_type VARCHAR(30) NOT NULL DEFAULT 'MEASURED_BY',
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_step_kpi_binding_active
    ON step_kpi_bindings(step_definition_id, kpi_definition_id, binding_type)
    WHERE is_deleted = false;

-- 11. process_relation_edges: 프로세스 간 관계
CREATE TABLE IF NOT EXISTS process_relation_edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL REFERENCES tenants(id),
    workspace_id UUID NOT NULL REFERENCES workspaces(id),
    source_entity_type VARCHAR(50) NOT NULL,
    source_entity_id UUID NOT NULL,
    target_entity_type VARCHAR(50) NOT NULL,
    target_entity_id UUID NOT NULL,
    relation_type VARCHAR(50) NOT NULL,
    criticality VARCHAR(16) NOT NULL DEFAULT 'MEDIUM',
    propagation_mode VARCHAR(16),
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
CREATE INDEX IF NOT EXISTS idx_relation_edges_source
    ON process_relation_edges(tenant_id, source_entity_type, source_entity_id);
CREATE INDEX IF NOT EXISTS idx_relation_edges_target
    ON process_relation_edges(tenant_id, target_entity_type, target_entity_id);

-- 12. bpm_process_definition_bridge: 기존 BPM ↔ 신규 매핑
CREATE TABLE IF NOT EXISTS bpm_process_definition_bridge (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL REFERENCES tenants(id),
    legacy_bpm_definition_id VARCHAR NOT NULL,
    new_process_definition_id UUID NOT NULL REFERENCES process_definitions(id),
    migration_status VARCHAR(30) NOT NULL DEFAULT 'MAPPED',
    migrated_at TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (legacy_bpm_definition_id)
);
