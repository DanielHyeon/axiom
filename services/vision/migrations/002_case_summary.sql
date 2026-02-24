-- Vision CQRS 읽기 모델 (DDD-P2-03)
-- Core BC의 케이스/프로세스 이벤트를 소비하여 독립적으로 유지하는 비정규화 요약 테이블.
-- 실행: psql $DATABASE_URL -f migrations/002_case_summary.sql

SET search_path TO vision, public;

CREATE TABLE IF NOT EXISTS case_summary (
    tenant_id VARCHAR NOT NULL,
    total_cases INTEGER NOT NULL DEFAULT 0,
    active_cases INTEGER NOT NULL DEFAULT 0,
    completed_cases INTEGER NOT NULL DEFAULT 0,
    cancelled_cases INTEGER NOT NULL DEFAULT 0,
    avg_completion_days FLOAT,
    last_updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id)
);
