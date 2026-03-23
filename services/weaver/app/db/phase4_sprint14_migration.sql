-- Phase 4 Sprint 14: Schema-Semantic Drift Detector (SSDD)
-- G33b: 드리프트 이력 + 해결 추적

CREATE TABLE IF NOT EXISTS weaver.schema_drifts (
    drift_id        TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    tenant_id       TEXT NOT NULL DEFAULT '',
    datasource_name TEXT NOT NULL,
    schema_name     TEXT NOT NULL DEFAULT '',
    table_name      TEXT NOT NULL DEFAULT '',
    column_name     TEXT,
    drift_type      TEXT NOT NULL,        -- DriftType enum
    severity        TEXT NOT NULL,        -- critical, warning, info
    diff_json       JSONB NOT NULL DEFAULT '{}',
    impact_score    INTEGER NOT NULL DEFAULT 0,
    affected_contracts JSONB DEFAULT '[]',
    affected_ontology_nodes JSONB DEFAULT '[]',
    resolution_status TEXT NOT NULL DEFAULT 'detected',
    resolution_comment TEXT,
    resolved_by     TEXT,
    resolved_at     TIMESTAMPTZ,
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 테넌트 + 데이터소스별 조회
CREATE INDEX IF NOT EXISTS idx_drifts_tenant_ds
    ON weaver.schema_drifts (tenant_id, datasource_name, detected_at DESC);

-- 심각도 + 해결 상태별 조회
CREATE INDEX IF NOT EXISTS idx_drifts_severity_status
    ON weaver.schema_drifts (severity, resolution_status);

-- 미해결 CRITICAL 드리프트 빠른 조회
CREATE INDEX IF NOT EXISTS idx_drifts_unresolved_critical
    ON weaver.schema_drifts (tenant_id, severity)
    WHERE resolution_status = 'detected' AND severity = 'critical';
