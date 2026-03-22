CREATE TABLE IF NOT EXISTS axiom.kpi_definitions (
    id                  UUID PRIMARY KEY,
    tenant_id           UUID NOT NULL REFERENCES axiom.tenants(id),
    kpi_code            VARCHAR(100) NOT NULL,
    name                VARCHAR(200) NOT NULL,
    description         TEXT,
    scope_type          VARCHAR(50) NOT NULL,
    calculation_type    VARCHAR(50) NOT NULL,
    unit                VARCHAR(50),
    threshold_config_json JSONB,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_kpi_code UNIQUE (tenant_id, kpi_code)
);

CREATE TABLE IF NOT EXISTS axiom.process_kpi_bindings (
    id                  UUID PRIMARY KEY,
    tenant_id           UUID NOT NULL REFERENCES axiom.tenants(id),
    process_definition_id UUID NOT NULL REFERENCES axiom.process_definitions(id),
    kpi_definition_id   UUID NOT NULL REFERENCES axiom.kpi_definitions(id),
    binding_type        VARCHAR(50) NOT NULL,
    weight_value        NUMERIC(10,4),
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_process_kpi_binding UNIQUE (process_definition_id, kpi_definition_id, binding_type)
);

CREATE TABLE IF NOT EXISTS axiom.twin_scenarios (
    id                  UUID PRIMARY KEY,
    tenant_id           UUID NOT NULL REFERENCES axiom.tenants(id),
    scenario_key        VARCHAR(100) NOT NULL,
    name                VARCHAR(200) NOT NULL,
    base_snapshot_id    UUID REFERENCES axiom.twin_snapshots(id),
    status              VARCHAR(30) NOT NULL,
    assumption_json     JSONB NOT NULL,
    created_by          VARCHAR(200),
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_scenario_key UNIQUE (tenant_id, scenario_key)
);

CREATE TABLE IF NOT EXISTS axiom.scenario_runs (
    id                  UUID PRIMARY KEY,
    tenant_id           UUID NOT NULL REFERENCES axiom.tenants(id),
    scenario_id         UUID NOT NULL REFERENCES axiom.twin_scenarios(id),
    run_status          VARCHAR(30) NOT NULL,
    started_at          TIMESTAMP NOT NULL,
    completed_at        TIMESTAMP,
    result_json         JSONB,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_twin_scenarios_tenant_id
    ON axiom.twin_scenarios (tenant_id, status);
