CREATE SCHEMA IF NOT EXISTS axiom;

CREATE TABLE IF NOT EXISTS axiom.tenants (
    id                  UUID PRIMARY KEY,
    code                VARCHAR(100) NOT NULL UNIQUE,
    name                VARCHAR(200) NOT NULL,
    status              VARCHAR(30) NOT NULL,
    industry_code       VARCHAR(50),
    default_timezone    VARCHAR(100) NOT NULL DEFAULT 'Asia/Seoul',
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS axiom.org_units (
    id                  UUID PRIMARY KEY,
    tenant_id           UUID NOT NULL REFERENCES axiom.tenants(id),
    parent_org_unit_id  UUID REFERENCES axiom.org_units(id),
    code                VARCHAR(100) NOT NULL,
    name                VARCHAR(200) NOT NULL,
    org_type            VARCHAR(50) NOT NULL,
    status              VARCHAR(30) NOT NULL,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_org_unit_code UNIQUE (tenant_id, code)
);

CREATE TABLE IF NOT EXISTS axiom.workspaces (
    id                  UUID PRIMARY KEY,
    tenant_id           UUID NOT NULL REFERENCES axiom.tenants(id),
    org_unit_id         UUID REFERENCES axiom.org_units(id),
    code                VARCHAR(100) NOT NULL,
    name                VARCHAR(200) NOT NULL,
    domain_type         VARCHAR(50) NOT NULL,
    status              VARCHAR(30) NOT NULL,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_workspace_code UNIQUE (tenant_id, code)
);

CREATE INDEX IF NOT EXISTS idx_org_units_tenant_id
    ON axiom.org_units (tenant_id);

CREATE INDEX IF NOT EXISTS idx_workspaces_tenant_id
    ON axiom.workspaces (tenant_id);
