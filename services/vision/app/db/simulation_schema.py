"""시뮬레이션 브랜치 및 이벤트 테이블 DDL (Event Fork Engine용).

vision.simulation_branches — 시뮬레이션 브랜치 (포크 시점에서 생성된 가상 이벤트 스트림)
vision.simulation_events  — 브랜치 내 개별 시뮬레이션 이벤트 로그

DB 접속은 Vision이 이미 사용하는 psycopg2 + VISION_STATE_DATABASE_URL을 재활용한다.
outbox.py의 ensure_outbox_table() 패턴을 동일하게 따른다.
"""
from __future__ import annotations

import logging

from app.db.pg_utils import get_conn_from_pool

logger = logging.getLogger("axiom.vision.simulation_schema")


# ── DDL: vision.simulation_branches + vision.simulation_events ── #

_DDL = """\
-- 스키마 보장
CREATE SCHEMA IF NOT EXISTS vision;

-- ────────────────────────────────────────────────────────────────
-- 시뮬레이션 브랜치: 특정 시점에서 포크된 가상 이벤트 스트림
-- ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS vision.simulation_branches (
    id              TEXT PRIMARY KEY,                    -- sim_branch_{uuid}
    case_id         TEXT NOT NULL,
    tenant_id       TEXT NOT NULL,
    name            TEXT NOT NULL,                       -- "2026 원가 20% 절감 시나리오"
    description     TEXT,
    base_timestamp  TIMESTAMPTZ NOT NULL,                -- 포크 기준 시점
    status          TEXT NOT NULL DEFAULT 'created',     -- created | running | completed | failed

    -- 시뮬레이션 설정
    interventions   JSONB NOT NULL DEFAULT '[]'::jsonb,  -- InterventionSpec 배열
    gwt_overrides   JSONB DEFAULT '{}'::jsonb,           -- 오버라이드할 GWT 룰 설정

    -- 결과
    result_summary  JSONB,                               -- KPI 델타, 영향도 요약
    event_count     INTEGER DEFAULT 0,                   -- 시뮬레이션 이벤트 수

    -- 감사
    created_by      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ
);

-- 동일 case 내 브랜치 이름 중복 방지
CREATE UNIQUE INDEX IF NOT EXISTS uq_sim_branch_case_name
    ON vision.simulation_branches (case_id, name);

-- 테넌트별 최신순 조회 인덱스
CREATE INDEX IF NOT EXISTS idx_sim_branch_tenant
    ON vision.simulation_branches (tenant_id, created_at DESC);

-- 활성 상태 브랜치 빠른 조회
CREATE INDEX IF NOT EXISTS idx_sim_branch_status
    ON vision.simulation_branches (status) WHERE status != 'completed';


-- ────────────────────────────────────────────────────────────────
-- 시뮬레이션 이벤트 로그: 브랜치 내 가상 이벤트
-- ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS vision.simulation_events (
    id              TEXT PRIMARY KEY,                     -- sim_evt_{uuid}
    branch_id       TEXT NOT NULL
                    REFERENCES vision.simulation_branches(id)
                    ON DELETE CASCADE,
    sequence_number INTEGER NOT NULL,                    -- 브랜치 내 이벤트 순서

    -- 이벤트 데이터 (EventOutbox와 동일 구조)
    event_type      TEXT NOT NULL,
    aggregate_type  TEXT,
    aggregate_id    TEXT,
    payload         JSONB NOT NULL,

    -- 메타데이터
    source          TEXT NOT NULL DEFAULT 'intervention', -- intervention | gwt_rule | cascade
    source_rule_id  TEXT,                                -- GWT 룰에 의해 생성된 경우 룰 ID

    -- 이 이벤트 적용 후 상태 스냅샷
    state_snapshot  JSONB,                               -- {node_id: {field: value, ...}, ...}

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- 브랜치 내 시퀀스 유일 보장
    CONSTRAINT uq_sim_event_seq UNIQUE (branch_id, sequence_number)
);

-- 브랜치별 이벤트 순서 조회 인덱스
CREATE INDEX IF NOT EXISTS idx_sim_event_branch_seq
    ON vision.simulation_events (branch_id, sequence_number);
"""


def ensure_simulation_tables() -> None:
    """서비스 시작 시 simulation_branches / simulation_events 테이블을 멱등적으로 생성한다.

    outbox.py의 ensure_outbox_table()과 동일 패턴:
    - psycopg2 동기 커넥션 사용
    - DDL 실패 시 경고만 남기고 서비스 시작은 계속 진행
    """
    try:
        with get_conn_from_pool() as conn:
            cur = conn.cursor()
            cur.execute(_DDL)
            cur.close()
            conn.commit()
        logger.info("vision.simulation_branches / simulation_events 테이블 보장 완료")
    except Exception:
        logger.warning(
            "simulation tables DDL 실패 (PG가 비가용 상태일 수 있음)",
            exc_info=True,
        )
