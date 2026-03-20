"""Vision 서비스 공용 PostgreSQL 유틸리티 모듈.

psycopg2 지연 임포트, DB URL 변환, ThreadedConnectionPool 싱글톤을 제공한다.
각 모듈(simulation_schema, event_fork_engine, whatif_fork)에서 중복되던
_import_psycopg2(), _db_url() 코드를 이 모듈로 통합한다.
"""
from __future__ import annotations

import logging
import os
import sys
import threading
from contextlib import contextmanager
from typing import Any

logger = logging.getLogger("axiom.vision.pg_utils")

# 커넥션 풀 싱글톤 (스레드 안전)
_pool_lock = threading.Lock()
_pool: Any = None  # psycopg2.pool.ThreadedConnectionPool | None


def _import_psycopg2():
    """psycopg2를 지연 임포트한다. 시스템 경로 폴백 포함.

    Returns:
        psycopg2 모듈 (RealDictCursor 접근은 psycopg2.extras.RealDictCursor 로 가능)
    """
    try:
        import psycopg2
        return psycopg2
    except Exception:
        for path in (
            "/usr/lib/python3/dist-packages",
            os.path.expanduser("~/.local/lib/python3.12/site-packages"),
        ):
            if path not in sys.path:
                sys.path.insert(0, path)
        import psycopg2
        return psycopg2


def _db_url() -> str:
    """PostgreSQL 접속 URL을 반환한다. asyncpg 프리픽스를 psycopg2용으로 변환."""
    url = os.getenv(
        "VISION_STATE_DATABASE_URL",
        "postgresql://arkos:arkos@localhost:5432/insolvency_os",
    ).strip()
    if url.startswith("postgresql+asyncpg://"):
        return "postgresql://" + url[len("postgresql+asyncpg://"):]
    return url


def get_connection_pool(minconn: int = 2, maxconn: int = 10):
    """psycopg2.pool.ThreadedConnectionPool 싱글톤을 반환한다.

    스레드 안전: threading.Lock으로 초기화를 보호한다.
    이미 생성된 풀이 있으면 재사용한다.

    Args:
        minconn: 최소 커넥션 수 (기본 2)
        maxconn: 최대 커넥션 수 (기본 10)

    Returns:
        ThreadedConnectionPool 인스턴스
    """
    global _pool
    if _pool is not None:
        return _pool

    with _pool_lock:
        # 더블 체크 패턴 — Lock 획득 사이에 다른 스레드가 이미 생성했을 수 있음
        if _pool is not None:
            return _pool

        psycopg2 = _import_psycopg2()
        from psycopg2 import pool as psycopg2_pool

        db_url = _db_url()
        _pool = psycopg2_pool.ThreadedConnectionPool(
            minconn=minconn,
            maxconn=maxconn,
            dsn=db_url,
        )
        logger.info(
            "ThreadedConnectionPool 생성 완료 (min=%d, max=%d)",
            minconn, maxconn,
        )
        return _pool


@contextmanager
def get_conn_from_pool():
    """커넥션 풀에서 커넥션을 가져오고, 사용 후 자동 반납하는 컨텍스트 매니저.

    사용 예:
        with get_conn_from_pool() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            conn.commit()

    예외 발생 시에도 커넥션이 안전하게 풀에 반환된다.
    """
    pool = get_connection_pool()
    conn = pool.getconn()
    try:
        yield conn
    finally:
        pool.putconn(conn)
