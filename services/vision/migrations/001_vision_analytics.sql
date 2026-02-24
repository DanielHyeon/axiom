-- Vision Analytics 스키마 (Phase V1 Full-spec)
-- Vision BC 전용 스키마에 테이블 생성. core_case는 Core 소유.
-- 실행: psql $DATABASE_URL -f migrations/001_vision_analytics.sql

CREATE SCHEMA IF NOT EXISTS vision;
SET search_path TO vision, public;

-- KPI 요약 (period/case_type별 1행)
CREATE TABLE IF NOT EXISTS vision_analytics_kpi (
    tenant_id TEXT NOT NULL,
    period TEXT NOT NULL,
    case_type TEXT NOT NULL DEFAULT 'ALL',
    total_cases INTEGER NOT NULL DEFAULT 0,
    active_cases INTEGER NOT NULL DEFAULT 0,
    total_obligations_amount BIGINT NOT NULL DEFAULT 0,
    avg_performance_rate DECIMAL(5,4) NOT NULL DEFAULT 0,
    avg_case_duration_days INTEGER NOT NULL DEFAULT 0,
    stakeholder_satisfaction_rate DECIMAL(5,4) NOT NULL DEFAULT 0,
    prev_total_cases INTEGER,
    prev_active_cases INTEGER,
    prev_total_obligations_amount BIGINT,
    prev_avg_performance_rate DECIMAL(5,4),
    prev_avg_case_duration_days INTEGER,
    prev_stakeholder_satisfaction_rate DECIMAL(5,4),
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tenant_id, period, case_type)
);

-- 사건 추이 (기간별 시계열)
CREATE TABLE IF NOT EXISTS vision_analytics_trend (
    id SERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    period TEXT NOT NULL,
    granularity TEXT NOT NULL DEFAULT 'monthly',
    case_type TEXT,
    new_cases INTEGER NOT NULL DEFAULT 0,
    completed_cases INTEGER NOT NULL DEFAULT 0,
    active_cases INTEGER NOT NULL DEFAULT 0,
    total_obligations_registered BIGINT NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_vision_analytics_trend_tenant_period
    ON vision_analytics_trend(tenant_id, period, granularity);

-- 이해관계자 분포 (distribution_by별 세그먼트)
CREATE TABLE IF NOT EXISTS vision_analytics_stakeholder_dist (
    id SERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    distribution_by TEXT NOT NULL,
    segment_label TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    count_pct DECIMAL(5,4) NOT NULL DEFAULT 0,
    amount BIGINT NOT NULL DEFAULT 0,
    amount_pct DECIMAL(5,4) NOT NULL DEFAULT 0,
    avg_satisfaction_rate DECIMAL(5,4) NOT NULL DEFAULT 0,
    case_type TEXT,
    year INTEGER
);
CREATE INDEX IF NOT EXISTS idx_vision_analytics_stakeholder_tenant
    ON vision_analytics_stakeholder_dist(tenant_id, distribution_by);

-- 성과율 추이
CREATE TABLE IF NOT EXISTS vision_analytics_performance_trend (
    id SERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    period TEXT NOT NULL,
    granularity TEXT NOT NULL DEFAULT 'quarterly',
    case_type TEXT,
    stakeholder_type TEXT,
    avg_performance_rate DECIMAL(5,4) NOT NULL DEFAULT 0,
    secured_rate DECIMAL(5,4) NOT NULL DEFAULT 0,
    general_rate DECIMAL(5,4) NOT NULL DEFAULT 0,
    priority_rate DECIMAL(5,4) NOT NULL DEFAULT 0,
    case_count INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_vision_analytics_perf_tenant
    ON vision_analytics_performance_trend(tenant_id, period);

-- 케이스별 재무 요약 (core_case와 1:1, 확장 데이터)
CREATE TABLE IF NOT EXISTS vision_analytics_case_financial (
    case_id TEXT NOT NULL PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    case_number TEXT NOT NULL DEFAULT '',
    company_name TEXT NOT NULL DEFAULT '',
    financials JSONB NOT NULL DEFAULT '{}',
    execution_progress JSONB NOT NULL DEFAULT '{}',
    stakeholder_breakdown JSONB NOT NULL DEFAULT '[]',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_vision_analytics_case_financial_tenant
    ON vision_analytics_case_financial(tenant_id);

-- 대시보드 위젯 구성 (메타데이터, 선택)
CREATE TABLE IF NOT EXISTS vision_analytics_dashboards (
    id TEXT NOT NULL PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    title TEXT NOT NULL,
    widgets_json JSONB NOT NULL DEFAULT '[]',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
