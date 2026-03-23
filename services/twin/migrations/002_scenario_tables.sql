-- ============================================================
-- Phase 5: Scenario / What-if — DB 마이그레이션
-- 구현 계획서 §5.2 기준 — twin 스키마 확장
-- ============================================================

-- 1. scenario_definitions
CREATE TABLE IF NOT EXISTS twin.scenario_definitions (
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
CREATE UNIQUE INDEX IF NOT EXISTS uq_scenario_definitions_active
    ON twin.scenario_definitions(tenant_id, workspace_id, code) WHERE is_deleted = false;

-- 2. scenario_change_sets
CREATE TABLE IF NOT EXISTS twin.scenario_change_sets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL,
    scenario_definition_id UUID NOT NULL REFERENCES twin.scenario_definitions(id),
    change_type VARCHAR(50) NOT NULL,
    target_entity_type VARCHAR(50) NOT NULL,
    target_entity_id UUID NOT NULL,
    patch_json JSONB NOT NULL,
    display_order INTEGER NOT NULL DEFAULT 0,
    version BIGINT NOT NULL DEFAULT 0,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_scenario_change_sets_scenario
    ON twin.scenario_change_sets(tenant_id, scenario_definition_id);

-- 3. scenario_runs
CREATE TABLE IF NOT EXISTS twin.scenario_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL,
    workspace_id UUID NOT NULL,
    scenario_definition_id UUID NOT NULL REFERENCES twin.scenario_definitions(id),
    base_snapshot_id UUID NOT NULL REFERENCES twin.twin_snapshots(id),
    run_number INTEGER NOT NULL DEFAULT 1,
    status VARCHAR(30) NOT NULL DEFAULT 'PENDING',
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    result_summary_json JSONB,
    comparison_json JSONB,
    error_message TEXT,
    engine_version VARCHAR(50),
    input_manifest_json JSONB,
    baseline_snapshot_hash VARCHAR(128),
    assumption_set_version INTEGER,
    started_by VARCHAR,
    random_seed BIGINT,
    engine_artifact_hash VARCHAR(128),
    version BIGINT NOT NULL DEFAULT 0,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_by VARCHAR,
    updated_by VARCHAR,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_scenario_runs_scenario
    ON twin.scenario_runs(tenant_id, scenario_definition_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_scenario_runs_run_no
    ON twin.scenario_runs(tenant_id, scenario_definition_id, run_number)
    WHERE is_deleted = false;

-- 4. simulation_coefficients (보정계수 테이블)
CREATE TABLE IF NOT EXISTS twin.simulation_coefficients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL,
    workspace_id UUID NOT NULL,
    target_entity_type VARCHAR(50) NOT NULL,
    target_entity_id UUID,
    change_type VARCHAR(50) NOT NULL,
    effect_metric VARCHAR(50) NOT NULL,
    coefficient NUMERIC(8,4) NOT NULL,
    confidence NUMERIC(5,2),
    source VARCHAR(30) NOT NULL DEFAULT 'DEFAULT',
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_sim_coefficients_active
    ON twin.simulation_coefficients(
        tenant_id, workspace_id,
        COALESCE(target_entity_id, '00000000-0000-0000-0000-000000000000'::uuid),
        change_type, effect_metric
    ) WHERE is_deleted = false;
