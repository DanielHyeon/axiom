-- ============================================================
-- Phase 4: Digital Twin Runtime — DB 마이그레이션
-- 구현 계획서 §4.3 기준 — twin 스키마
-- ============================================================

CREATE SCHEMA IF NOT EXISTS twin;

-- 1. aggregate_sequences: aggregate_seq 원자적 발급
CREATE TABLE IF NOT EXISTS twin.aggregate_sequences (
    tenant_id VARCHAR NOT NULL,
    aggregate_type VARCHAR(50) NOT NULL,
    aggregate_id UUID NOT NULL,
    last_seq BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (tenant_id, aggregate_type, aggregate_id)
);

-- 2. twin_entities: 트윈 엔티티 레지스트리
CREATE TABLE IF NOT EXISTS twin.twin_entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    ref_table VARCHAR(64) NOT NULL,
    ref_id UUID NOT NULL,
    twin_key VARCHAR(255) NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_twin_entities_key_active
    ON twin.twin_entities(tenant_id, twin_key) WHERE is_deleted = false;

-- 3. process_instances: 실행 중인 업무
CREATE TABLE IF NOT EXISTS twin.process_instances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL,
    workspace_id UUID NOT NULL,
    process_definition_id UUID NOT NULL,
    process_version_id UUID NOT NULL,
    business_key VARCHAR(200),
    source_system VARCHAR(100),
    status VARCHAR(30) NOT NULL,
    priority VARCHAR(30),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    due_at TIMESTAMPTZ,
    current_step_instance_id UUID,
    root_instance_id UUID,
    parent_instance_id UUID,
    payload_json JSONB,
    version BIGINT NOT NULL DEFAULT 0,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_by VARCHAR,
    updated_by VARCHAR,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_instances_status ON twin.process_instances(tenant_id, workspace_id, status);
CREATE INDEX IF NOT EXISTS idx_instances_definition ON twin.process_instances(tenant_id, process_definition_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_instances_business_key ON twin.process_instances(tenant_id, workspace_id, business_key)
    WHERE business_key IS NOT NULL AND is_deleted = false;
ALTER TABLE twin.process_instances
    ADD CONSTRAINT fk_instances_root FOREIGN KEY (root_instance_id) REFERENCES twin.process_instances(id),
    ADD CONSTRAINT fk_instances_parent FOREIGN KEY (parent_instance_id) REFERENCES twin.process_instances(id);

-- workspace 복합 FK용 UNIQUE
ALTER TABLE twin.process_instances
    ADD CONSTRAINT uq_instances_tenant_ws_id UNIQUE (tenant_id, workspace_id, id);

-- 4. step_instances
CREATE TABLE IF NOT EXISTS twin.step_instances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL,
    workspace_id UUID NOT NULL,
    process_instance_id UUID NOT NULL,
    step_definition_id UUID NOT NULL,
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
CREATE INDEX IF NOT EXISTS idx_step_instances_process ON twin.step_instances(tenant_id, process_instance_id);
CREATE INDEX IF NOT EXISTS idx_step_instances_workspace_status ON twin.step_instances(tenant_id, workspace_id, status);

-- step_instances → process_instances 복합 FK
ALTER TABLE twin.step_instances
    ADD CONSTRAINT fk_step_instances_process
    FOREIGN KEY (tenant_id, workspace_id, process_instance_id)
    REFERENCES twin.process_instances(tenant_id, workspace_id, id);

-- current_step_instance_id FK
ALTER TABLE twin.process_instances
    ADD CONSTRAINT fk_instances_current_step
    FOREIGN KEY (current_step_instance_id) REFERENCES twin.step_instances(id);

-- 5. twin_events (Day-1 partitioned)
CREATE TABLE IF NOT EXISTS twin.twin_events (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL,
    workspace_id UUID NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    event_version INTEGER NOT NULL DEFAULT 1,
    schema_version VARCHAR(10) NOT NULL DEFAULT '1.0',
    aggregate_type VARCHAR(50) NOT NULL,
    aggregate_id UUID NOT NULL,
    ordering_key VARCHAR(200) NOT NULL,
    aggregate_seq BIGINT NOT NULL,
    idempotency_key VARCHAR(200) NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    producer_service VARCHAR(50) NOT NULL DEFAULT 'twin',
    actor_user_id VARCHAR,
    trace_id VARCHAR(64),
    causation_id UUID,
    correlation_id UUID,
    payload_json JSONB NOT NULL,
    source_channel VARCHAR(50) NOT NULL,
    processing_status VARCHAR(30) NOT NULL DEFAULT 'RECEIVED',
    version BIGINT NOT NULL DEFAULT 0,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id, occurred_at)
) PARTITION BY RANGE (occurred_at);

CREATE TABLE IF NOT EXISTS twin.twin_events_2026_03 PARTITION OF twin.twin_events
    FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');
CREATE TABLE IF NOT EXISTS twin.twin_events_2026_04 PARTITION OF twin.twin_events
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
CREATE TABLE IF NOT EXISTS twin.twin_events_2026_05 PARTITION OF twin.twin_events
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');

CREATE UNIQUE INDEX IF NOT EXISTS uq_twin_events_idempotency
    ON twin.twin_events(tenant_id, aggregate_type, aggregate_id, idempotency_key, occurred_at)
    WHERE is_deleted = false;
CREATE INDEX IF NOT EXISTS idx_twin_events_aggregate ON twin.twin_events(tenant_id, aggregate_type, aggregate_id);
CREATE INDEX IF NOT EXISTS idx_twin_events_occurred ON twin.twin_events(tenant_id, event_type, occurred_at DESC);

-- 6. twin_states
CREATE TABLE IF NOT EXISTS twin.twin_states (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL,
    workspace_id UUID NOT NULL,
    twin_entity_id UUID NOT NULL REFERENCES twin.twin_entities(id),
    entity_type VARCHAR(50) NOT NULL,
    entity_id UUID NOT NULL,
    state_code VARCHAR(50) NOT NULL,
    health_score NUMERIC(5,2),
    sla_status VARCHAR(30),
    queue_size INTEGER,
    avg_cycle_time_minutes NUMERIC(12,2),
    avg_wait_time_minutes NUMERIC(12,2),
    exception_rate NUMERIC(8,4),
    last_event_at TIMESTAMPTZ,
    last_event_seq BIGINT,
    snapshot_ref_id UUID,
    metrics_json JSONB,
    version BIGINT NOT NULL DEFAULT 0,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_twin_states_entity_active
    ON twin.twin_states(tenant_id, workspace_id, entity_type, entity_id) WHERE is_deleted = false;

-- 7. twin_snapshots
CREATE TABLE IF NOT EXISTS twin.twin_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL,
    workspace_id UUID NOT NULL,
    snapshot_type VARCHAR(30) NOT NULL,
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

-- twin_states.snapshot_ref_id FK
ALTER TABLE twin.twin_states
    ADD CONSTRAINT fk_twin_states_snapshot_ref
    FOREIGN KEY (snapshot_ref_id) REFERENCES twin.twin_snapshots(id);

-- 8. event_outbox
CREATE TABLE IF NOT EXISTS twin.event_outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL,
    workspace_id UUID,
    aggregate_type VARCHAR(100) NOT NULL,
    aggregate_id UUID NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    event_version INTEGER NOT NULL DEFAULT 1,
    schema_version VARCHAR(10) NOT NULL DEFAULT '1.0',
    ordering_key VARCHAR(200) NOT NULL,
    aggregate_seq BIGINT NOT NULL,
    idempotency_key VARCHAR(200) NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    producer_service VARCHAR(50) NOT NULL DEFAULT 'twin',
    actor_user_id VARCHAR,
    trace_id VARCHAR(64),
    correlation_id UUID,
    causation_id UUID,
    payload_json JSONB NOT NULL,
    headers_json JSONB,
    published BOOLEAN NOT NULL DEFAULT false,
    published_at TIMESTAMPTZ,
    retry_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_twin_outbox_idempotency
    ON twin.event_outbox(tenant_id, aggregate_type, aggregate_id, idempotency_key);
CREATE INDEX IF NOT EXISTS idx_outbox_unpublished ON twin.event_outbox(published, created_at);
