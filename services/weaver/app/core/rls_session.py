from __future__ import annotations

from contextlib import asynccontextmanager


@asynccontextmanager
async def rls_session(pool, tenant_id: str):
    """Acquire a connection with RLS ``SET LOCAL`` scoped to a transaction.

    Usage::

        async with rls_session(pool, tenant_id) as conn:
            rows = await conn.fetch("SELECT * FROM weaver.insight_query_logs")

    The ``SET LOCAL`` ensures ``app.current_tenant_id`` is visible only within
    this transaction and automatically reverts when the connection returns to the
    pool — preventing cross-tenant data leaks in pgbouncer / connection-pool
    scenarios.
    """
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "SELECT set_config('app.current_tenant_id', $1, true)",
                tenant_id,
            )
            yield conn
