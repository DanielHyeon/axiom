-- Phase 1 Sprint 3: Schema Snapshots + Query Audit Log
-- G33a: Physical Snapshot Baseline
-- G40: Unified Query Execution Plane audit

-- ── 스키마 스냅샷 ── --
CREATE TABLE IF NOT EXISTS weaver.schema_snapshots (
    snapshot_id     TEXT PRIMARY KEY,
    datasource_name TEXT NOT NULL,
    tenant_id       TEXT NOT NULL DEFAULT '',
    table_hashes    JSONB NOT NULL DEFAULT '[]',
    total_tables    INTEGER NOT NULL DEFAULT 0,
    total_columns   INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 데이터소스별 최신 스냅샷 빠른 조회
CREATE INDEX IF NOT EXISTS idx_snapshots_ds_created
    ON weaver.schema_snapshots (datasource_name, created_at DESC);

-- 테넌트 격리
CREATE INDEX IF NOT EXISTS idx_snapshots_tenant
    ON weaver.schema_snapshots (tenant_id, datasource_name);

-- ── 변경 감지 이력 ── --
CREATE TABLE IF NOT EXISTS weaver.schema_changes (
    change_id       TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    datasource_name TEXT NOT NULL,
    tenant_id       TEXT NOT NULL DEFAULT '',
    prev_snapshot_id TEXT,
    curr_snapshot_id TEXT NOT NULL,
    change_type     TEXT NOT NULL,  -- table_added, table_removed, column_type_changed 등
    schema_name     TEXT NOT NULL DEFAULT '',
    table_name      TEXT NOT NULL DEFAULT '',
    column_name     TEXT,
    old_value       TEXT,
    new_value       TEXT,
    description     TEXT NOT NULL DEFAULT '',
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_changes_ds_detected
    ON weaver.schema_changes (datasource_name, detected_at DESC);

CREATE INDEX IF NOT EXISTS idx_changes_tenant
    ON weaver.schema_changes (tenant_id, datasource_name);

-- ── 쿼리 감사 로그 ── --
CREATE TABLE IF NOT EXISTS weaver.query_audit_logs (
    audit_id        TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    datasource_name TEXT NOT NULL,
    caller          TEXT NOT NULL,  -- direct_sql, nl2sql, profiling, drift_detect
    user_id         TEXT NOT NULL,
    tenant_id       TEXT NOT NULL,
    sql_hash        TEXT NOT NULL,  -- SQL 전문 대신 해시 (보안)
    row_count       INTEGER NOT NULL DEFAULT 0,
    execution_time_ms REAL NOT NULL DEFAULT 0.0,
    success         BOOLEAN NOT NULL DEFAULT true,
    error           TEXT,
    blocked_reason  TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 테넌트별 감사 로그 조회
CREATE INDEX IF NOT EXISTS idx_audit_tenant_created
    ON weaver.query_audit_logs (tenant_id, created_at DESC);

-- 데이터소스별 감사 로그
CREATE INDEX IF NOT EXISTS idx_audit_ds_created
    ON weaver.query_audit_logs (datasource_name, created_at DESC);

-- 차단된 쿼리 모니터링
CREATE INDEX IF NOT EXISTS idx_audit_blocked
    ON weaver.query_audit_logs (blocked_reason)
    WHERE blocked_reason IS NOT NULL;
