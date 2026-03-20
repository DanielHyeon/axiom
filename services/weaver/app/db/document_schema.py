"""문서→온톨로지 추출 파이프라인용 PostgreSQL DDL (Phase 2-D).

테이블:
  - weaver.documents      : 업로드된 문서 메타데이터
  - weaver.doc_fragments  : 텍스트 청킹 결과 (페이지·위치 기반)
  - weaver.extraction_jobs: DDD 추출 잡 상태 + 결과 저장

DB 접속은 기존 Weaver 패턴(asyncpg pool + POSTGRES_DSN)을 따른다.
"""
from __future__ import annotations

import logging

from app.core.config import settings

logger = logging.getLogger("axiom.weaver.document_schema")

# ── DDL ───────────────────────────────────────────────────────── #

_DDL = """\
CREATE SCHEMA IF NOT EXISTS weaver;

-- 문서 메타데이터
CREATE TABLE IF NOT EXISTS weaver.documents (
    id            VARCHAR PRIMARY KEY,
    case_id       VARCHAR NOT NULL DEFAULT '',
    tenant_id     VARCHAR NOT NULL DEFAULT '',
    filename      VARCHAR NOT NULL,
    file_type     VARCHAR NOT NULL,
    file_size     BIGINT  NOT NULL DEFAULT 0,
    page_count    INTEGER NOT NULL DEFAULT 0,
    status        VARCHAR NOT NULL DEFAULT 'uploaded',
    storage_path  VARCHAR NOT NULL DEFAULT '',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_documents_case
    ON weaver.documents (case_id);
CREATE INDEX IF NOT EXISTS idx_documents_tenant
    ON weaver.documents (tenant_id);

-- 문서 조각 (텍스트 청킹 결과)
CREATE TABLE IF NOT EXISTS weaver.doc_fragments (
    id          VARCHAR PRIMARY KEY,
    doc_id      VARCHAR NOT NULL REFERENCES weaver.documents(id) ON DELETE CASCADE,
    page        INTEGER NOT NULL DEFAULT 0,
    span_start  INTEGER NOT NULL DEFAULT 0,
    span_end    INTEGER NOT NULL DEFAULT 0,
    text        TEXT    NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_doc_fragments_doc
    ON weaver.doc_fragments (doc_id);

-- DDD 추출 잡 상태 + 결과
CREATE TABLE IF NOT EXISTS weaver.extraction_jobs (
    id            VARCHAR PRIMARY KEY,
    doc_id        VARCHAR NOT NULL REFERENCES weaver.documents(id) ON DELETE CASCADE,
    case_id       VARCHAR NOT NULL DEFAULT '',
    tenant_id     VARCHAR NOT NULL DEFAULT '',
    status        VARCHAR NOT NULL DEFAULT 'queued',
    progress      INTEGER NOT NULL DEFAULT 0,
    result        JSONB,
    error         TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at  TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_extraction_jobs_doc
    ON weaver.extraction_jobs (doc_id);
CREATE INDEX IF NOT EXISTS idx_extraction_jobs_status
    ON weaver.extraction_jobs (status);
"""

# ── asyncpg 풀 (outbox.py 패턴 재사용) ───────────────────────── #

_pool = None


async def _get_pool():
    """asyncpg 커넥션 풀 싱글톤 반환."""
    global _pool
    if _pool is not None:
        return _pool
    dsn = settings.postgres_dsn
    if not dsn:
        raise RuntimeError("POSTGRES_DSN 설정이 필요합니다 (document_schema)")
    import asyncpg
    _pool = await asyncpg.create_pool(
        dsn=dsn, min_size=1, max_size=3,
        server_settings={"search_path": "weaver,public"},
    )
    return _pool


async def get_document_pool():
    """외부 모듈에서 문서 관련 DB 풀을 가져올 때 사용."""
    return await _get_pool()


async def ensure_document_tables() -> None:
    """서비스 시작 시 문서 관련 테이블 생성을 보장한다."""
    try:
        pool = await _get_pool()
        async with pool.acquire() as conn:
            await conn.execute(_DDL)
        logger.info("weaver.documents / doc_fragments / extraction_jobs 테이블 보장 완료")
    except Exception:
        logger.warning(
            "문서 테이블 DDL 실행 실패 (PostgreSQL 미연결 가능성)",
            exc_info=True,
        )
