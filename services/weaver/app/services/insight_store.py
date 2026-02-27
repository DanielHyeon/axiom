from __future__ import annotations

import logging

from app.core.config import settings
from app.services.resilience import CircuitBreakerOpenError, SimpleCircuitBreaker, with_retry

logger = logging.getLogger("weaver.insight_store")


class InsightStoreUnavailableError(RuntimeError):
    pass


class InsightStore:
    """Manages the Insight View tables (asyncpg pool, idempotent DDL migration).

    Pattern follows PostgresMetadataStore: lazy pool init, circuit breaker,
    ``CREATE TABLE IF NOT EXISTS`` for zero-downtime schema creation.
    """

    _DB_SCHEMA = "weaver"

    def __init__(self) -> None:
        self._pool = None
        self._breaker = SimpleCircuitBreaker(failure_threshold=3, reset_timeout_seconds=20.0)

    # ── pool management ──────────────────────────────────────

    async def _get_pool(self):
        try:
            self._breaker.preflight()
        except CircuitBreakerOpenError as exc:
            raise InsightStoreUnavailableError(str(exc)) from exc
        if self._pool is not None:
            return self._pool
        dsn = settings.postgres_dsn
        if not dsn:
            raise InsightStoreUnavailableError("POSTGRES_DSN is required for insight store")
        try:
            import asyncpg
        except Exception as exc:
            raise InsightStoreUnavailableError("asyncpg is not installed") from exc

        async def _create():
            return await asyncpg.create_pool(
                dsn=dsn, min_size=1, max_size=5,
                server_settings={"search_path": f"{self._DB_SCHEMA},public"},
            )

        try:
            self._pool = await with_retry(_create, retries=2, base_delay_seconds=0.05)
            self._breaker.on_success()
        except CircuitBreakerOpenError as exc:
            raise InsightStoreUnavailableError(str(exc)) from exc
        except Exception as exc:
            self._breaker.on_failure()
            raise InsightStoreUnavailableError(str(exc)) from exc
        await self._migrate()
        return self._pool

    async def get_pool(self):
        """Public accessor for the asyncpg pool."""
        return await self._get_pool()

    async def health_check(self) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute("SELECT 1")

    # ── DDL migration (idempotent) ───────────────────────────

    async def _migrate(self) -> None:
        pool = self._pool
        async with pool.acquire() as conn:
            await conn.execute(f"CREATE SCHEMA IF NOT EXISTS {self._DB_SCHEMA}")

            # 1. insight_ingest_batches
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS weaver.insight_ingest_batches (
                    id BIGSERIAL PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'oracle',
                    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    row_count INT NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'accepted',
                    error_message TEXT
                )
            """)
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_iib_tenant "
                "ON weaver.insight_ingest_batches(tenant_id, received_at DESC)"
            )

            # 2. insight_query_logs
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS weaver.insight_query_logs (
                    id BIGSERIAL PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    datasource_id TEXT NOT NULL,
                    query_id TEXT NOT NULL,
                    raw_sql TEXT NOT NULL,
                    normalized_sql TEXT NOT NULL DEFAULT '',
                    sql_hash TEXT NOT NULL DEFAULT '',
                    executed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    duration_ms INT,
                    user_id TEXT,
                    source TEXT NOT NULL DEFAULT 'oracle',
                    batch_id BIGINT,
                    parse_status TEXT NOT NULL DEFAULT 'pending',
                    parse_warnings JSONB DEFAULT '[]'::jsonb,
                    parse_errors JSONB DEFAULT '[]'::jsonb,
                    parsed_tables JSONB DEFAULT '[]'::jsonb,
                    parsed_joins JSONB DEFAULT '[]'::jsonb,
                    parsed_predicates JSONB DEFAULT '[]'::jsonb,
                    parsed_select JSONB DEFAULT '[]'::jsonb,
                    parsed_group_by JSONB DEFAULT '[]'::jsonb,
                    parse_mode TEXT,
                    parse_confidence DOUBLE PRECISION
                )
            """)
            await conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_iql_tenant_query "
                "ON weaver.insight_query_logs(tenant_id, query_id)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_iql_tenant_ds_time "
                "ON weaver.insight_query_logs(tenant_id, datasource_id, executed_at DESC)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_iql_parse_status "
                "ON weaver.insight_query_logs(parse_status) WHERE parse_status = 'pending'"
            )

            # 3. insight_driver_scores
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS weaver.insight_driver_scores (
                    id BIGSERIAL PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    datasource_id TEXT NOT NULL,
                    kpi_fingerprint TEXT NOT NULL,
                    column_key TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'DRIVER',
                    score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                    breakdown JSONB NOT NULL DEFAULT '{}'::jsonb,
                    scoring_config JSONB NOT NULL DEFAULT '{"decay":"step","weights":{"usage":0.45}}'::jsonb,
                    formula_version TEXT NOT NULL DEFAULT 'v1',
                    graph_json JSONB,
                    time_range TEXT NOT NULL DEFAULT '30d',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    expires_at TIMESTAMPTZ
                )
            """)
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ids_tenant_kpi "
                "ON weaver.insight_driver_scores(tenant_id, kpi_fingerprint, created_at DESC)"
            )

            # RLS policies
            for tbl in ("insight_ingest_batches", "insight_query_logs", "insight_driver_scores"):
                await conn.execute(f"ALTER TABLE weaver.{tbl} ENABLE ROW LEVEL SECURITY")
                await conn.execute(f"""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_policies
                            WHERE tablename = '{tbl}'
                              AND policyname = '{tbl}_tenant_isolation'
                        ) THEN
                            EXECUTE format(
                                'CREATE POLICY {tbl}_tenant_isolation ON weaver.{tbl} '
                                'USING (tenant_id = current_setting(''app.current_tenant_id'', true))'
                            );
                        END IF;
                    END
                    $$
                """)

            # Idempotent column additions for existing deployments
            for col, col_type in [
                ("parse_mode", "TEXT"),
                ("parse_confidence", "DOUBLE PRECISION"),
                ("kpi_fingerprint", "TEXT"),   # P0-A Option A: KPI fingerprint tag
                ("kpi_name", "TEXT"),           # P0-A Option A: KPI display name
            ]:
                await conn.execute(f"""
                    DO $$
                    BEGIN
                        ALTER TABLE weaver.insight_query_logs ADD COLUMN {col} {col_type};
                    EXCEPTION WHEN duplicate_column THEN
                        NULL;
                    END
                    $$
                """)

            logger.info("InsightStore migration complete (3 tables + RLS)")


insight_store = InsightStore()
