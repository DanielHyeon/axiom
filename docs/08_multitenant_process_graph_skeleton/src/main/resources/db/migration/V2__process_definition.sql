CREATE TABLE IF NOT EXISTS axiom.process_definitions (
    id                  UUID PRIMARY KEY,
    tenant_id           UUID NOT NULL REFERENCES axiom.tenants(id),
    org_unit_id         UUID REFERENCES axiom.org_units(id),
    workspace_id        UUID REFERENCES axiom.workspaces(id),
    process_key         VARCHAR(200) NOT NULL,
    name                VARCHAR(300) NOT NULL,
    description         TEXT,
    domain_code         VARCHAR(100) NOT NULL,
    owner_role_code     VARCHAR(100),
    status              VARCHAR(30) NOT NULL,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_process_key UNIQUE (tenant_id, workspace_id, process_key)
);

CREATE TABLE IF NOT EXISTS axiom.process_versions (
    id                  UUID PRIMARY KEY,
    tenant_id           UUID NOT NULL REFERENCES axiom.tenants(id),
    process_definition_id UUID NOT NULL REFERENCES axiom.process_definitions(id),
    version_no          INTEGER NOT NULL,
    is_current          BOOLEAN NOT NULL DEFAULT FALSE,
    published_at        TIMESTAMP,
    effective_from      TIMESTAMP,
    effective_to        TIMESTAMP,
    status              VARCHAR(30) NOT NULL,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_process_version UNIQUE (process_definition_id, version_no)
);

CREATE TABLE IF NOT EXISTS axiom.step_definitions (
    id                  UUID PRIMARY KEY,
    tenant_id           UUID NOT NULL REFERENCES axiom.tenants(id),
    process_version_id  UUID NOT NULL REFERENCES axiom.process_versions(id),
    step_key            VARCHAR(200) NOT NULL,
    name                VARCHAR(300) NOT NULL,
    step_type           VARCHAR(50) NOT NULL,
    sequence_no         INTEGER NOT NULL,
    owner_role_code     VARCHAR(100),
    input_contract_code VARCHAR(100),
    output_contract_code VARCHAR(100),
    sla_minutes         INTEGER,
    is_automated        BOOLEAN NOT NULL DEFAULT FALSE,
    status              VARCHAR(30) NOT NULL,
    CONSTRAINT uq_step_key UNIQUE (process_version_id, step_key)
);

CREATE TABLE IF NOT EXISTS axiom.process_interfaces (
    id                  UUID PRIMARY KEY,
    tenant_id           UUID NOT NULL REFERENCES axiom.tenants(id),
    process_version_id  UUID NOT NULL REFERENCES axiom.process_versions(id),
    interface_code      VARCHAR(200) NOT NULL,
    direction           VARCHAR(20) NOT NULL,
    payload_type        VARCHAR(100) NOT NULL,
    schema_ref          VARCHAR(500),
    required_flag       BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_process_interface UNIQUE (process_version_id, interface_code, direction)
);

CREATE INDEX IF NOT EXISTS idx_process_definitions_scope
    ON axiom.process_definitions (tenant_id, org_unit_id, workspace_id);

CREATE INDEX IF NOT EXISTS idx_process_versions_process_definition_id
    ON axiom.process_versions (process_definition_id);

CREATE INDEX IF NOT EXISTS idx_step_definitions_process_version_id
    ON axiom.step_definitions (process_version_id);
