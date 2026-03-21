"""PostgreSQL 비동기 연결 풀 — asyncpg 기반."""
from __future__ import annotations

import asyncio

import asyncpg
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

_pool: asyncpg.Pool | None = None
_pool_lock = asyncio.Lock()


async def get_pool() -> asyncpg.Pool:
    """연결 풀을 가져온다. 없으면 생성한다.

    asyncio.Lock으로 동시 생성 경합(race condition)을 방지한다.
    """
    global _pool
    if _pool is not None:
        return _pool
    async with _pool_lock:
        # 락 획득 후 재확인 — 다른 코루틴이 이미 생성했을 수 있음
        if _pool is not None:
            return _pool
        dsn = settings.DATABASE_URL
        if dsn.startswith("postgresql+asyncpg://"):
            dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
        _pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10)
        logger.info("asyncpg_pool_created", min_size=2, max_size=10)
        return _pool


async def close_pool() -> None:
    """연결 풀을 닫는다."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("asyncpg_pool_closed")


async def execute_query(
    sql: str,
    params: list | None = None,
    timeout: float | None = None,
) -> list[dict]:
    """SQL을 실행하고 결과를 dict 리스트로 반환한다."""
    pool = await get_pool()
    _timeout = timeout or settings.QUERY_TIMEOUT_SEC
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *(params or []), timeout=_timeout)
        return [dict(row) for row in rows]


async def execute_command(sql: str, params: list | None = None) -> str:
    """DDL/DML을 실행하고 상태 문자열을 반환한다."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.execute(sql, *(params or []))
