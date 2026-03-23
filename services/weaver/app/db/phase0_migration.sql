-- Phase 0: 운영 공통 기반 DB 마이그레이션
-- G35 Execution Control Plane + G36 Secret Governance + G41 Publish Workflow

-- ── G35: 작업 실행 레코드 ── --
CREATE TABLE IF NOT EXISTS weaver.job_runs (
    run_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_type        VARCHAR(50) NOT NULL,
    tenant_id       VARCHAR(100) NOT NULL,
    triggered_by    VARCHAR(200) NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
    progress        NUMERIC(5,4) NOT NULL DEFAULT 0.0 CHECK (progress >= 0 AND progress <= 1),
    steps_json      JSONB DEFAULT '[]',
    artifacts_json  JSONB DEFAULT '[]',
    retry_policy    JSONB NOT NULL DEFAULT '{"max_retries":3,"backoff_seconds":5.0,"retry_on":["timeout","connection_error"]}',
    cancel_token    VARCHAR(200),
    idempotency_key VARCHAR(200),
    parent_run_id   UUID REFERENCES weaver.job_runs(run_id),
    worker_id       VARCHAR(200),
    lease_until      TIMESTAMPTZ,
    last_heartbeat_at TIMESTAMPTZ,
    resume_token    TEXT,
    result_checksum VARCHAR(128),
    error_message   TEXT,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_jobs_tenant_type ON weaver.job_runs(tenant_id, job_type, status);
CREATE INDEX IF NOT EXISTS idx_jobs_idempotency ON weaver.job_runs(idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_jobs_stale ON weaver.job_runs(status, lease_until) WHERE status = 'running';

-- ── G36: 비밀정보 참조 ── --
CREATE TABLE IF NOT EXISTS weaver.secrets (
    secret_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       VARCHAR(100) NOT NULL,
    key_path        VARCHAR(500) NOT NULL UNIQUE,
    vault_type      VARCHAR(30) NOT NULL DEFAULT 'internal',
    encrypted_value TEXT,           -- vault_type=internal일 때 Fernet 암호문
    expires_at      TIMESTAMPTZ,
    last_rotated_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_secrets_tenant ON weaver.secrets(tenant_id);
CREATE INDEX IF NOT EXISTS idx_secrets_expiry ON weaver.secrets(expires_at) WHERE expires_at IS NOT NULL;

-- ── G41: 산출물 승격/롤백 이력 ── --
CREATE TABLE IF NOT EXISTS weaver.publish_records (
    record_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       VARCHAR(100) NOT NULL,
    target_type     VARCHAR(50) NOT NULL,    -- table, semantic_entity, ontology_node, drift_fix
    target_id       VARCHAR(200) NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'draft',
    diff_preview    JSONB,
    publish_note    TEXT,
    rollback_reason TEXT,
    promoted_by     VARCHAR(200),
    promoted_at     TIMESTAMPTZ,
    rolled_back_by  VARCHAR(200),
    rolled_back_at  TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_publish_target ON weaver.publish_records(tenant_id, target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_publish_status ON weaver.publish_records(tenant_id, status);
