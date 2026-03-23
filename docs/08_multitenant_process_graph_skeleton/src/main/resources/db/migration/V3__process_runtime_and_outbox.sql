CREATE TABLE IF NOT EXISTS axiom.process_instances (
    id                  UUID PRIMARY KEY,
    tenant_id           UUID NOT NULL REFERENCES axiom.tenants(id),
    process_definition_id UUID NOT NULL REFERENCES axiom.process_definitions(id),
    process_version_id  UUID NOT NULL REFERENCES axiom.process_versions(id),
    business_case_id    VARCHAR(200),
    status              VARCHAR(30) NOT NULL,
    started_at          TIMESTAMP NOT NULL,
    completed_at        TIMESTAMP,
    current_step_key    VARCHAR(200),
    current_assignee_id VARCHAR(200),
    priority            VARCHAR(30) NOT NULL DEFAULT 'NORMAL',
    correlation_id      VARCHAR(200),
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS axiom.step_instances (
    id                  UUID PRIMARY KEY,
    tenant_id           UUID NOT NULL REFERENCES axiom.tenants(id),
    process_instance_id UUID NOT NULL REFERENCES axiom.process_instances(id),
    step_definition_id  UUID NOT NULL REFERENCES axiom.step_definitions(id),
    step_key            VARCHAR(200) NOT NULL,
    status              VARCHAR(30) NOT NULL,
    entered_at          TIMESTAMP NOT NULL,
    completed_at        TIMESTAMP,
    assignee_id         VARCHAR(200),
    duration_millis     BIGINT,
    error_code          VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS axiom.twin_events (
    id                  UUID PRIMARY KEY,
    tenant_id           UUID NOT NULL REFERENCES axiom.tenants(id),
    aggregate_type      VARCHAR(100) NOT NULL,
    aggregate_id        UUID NOT NULL,
    event_type          VARCHAR(200) NOT NULL,
    event_time          TIMESTAMP NOT NULL,
    correlation_id      VARCHAR(200),
    payload_json        JSONB NOT NULL,
    source_system       VARCHAR(100),
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS axiom.twin_snapshots (
    id                  UUID PRIMARY KEY,
    tenant_id           UUID NOT NULL REFERENCES axiom.tenants(id),
    snapshot_key        VARCHAR(200) NOT NULL,
    scope_type          VARCHAR(50) NOT NULL,
    scope_id            UUID,
    snapshot_time       TIMESTAMP NOT NULL,
    metrics_json        JSONB NOT NULL,
    state_json          JSONB NOT NULL,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS axiom.outbox_events (
    id                  UUID PRIMARY KEY,
    tenant_id           UUID NOT NULL REFERENCES axiom.tenants(id),
    aggregate_type      VARCHAR(100) NOT NULL,
    aggregate_id        UUID NOT NULL,
    event_type          VARCHAR(200) NOT NULL,
    payload_json        JSONB NOT NULL,
    headers_json        JSONB,
    status              VARCHAR(30) NOT NULL DEFAULT 'PENDING',
    occurred_at         TIMESTAMP NOT NULL,
    published_at        TIMESTAMP,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_process_instances_scope
    ON axiom.process_instances (tenant_id, process_definition_id, status);

CREATE INDEX IF NOT EXISTS idx_twin_events_aggregate
    ON axiom.twin_events (tenant_id, aggregate_type, aggregate_id, event_time DESC);

CREATE INDEX IF NOT EXISTS idx_outbox_events_status
    ON axiom.outbox_events (status, occurred_at);
