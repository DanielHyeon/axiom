"""PR1 tests: InsightStore DDL migration and pool management."""
from __future__ import annotations

import pytest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.insight_store import InsightStore, InsightStoreUnavailableError


def _make_mock_pool():
    """Create a mock asyncpg pool where acquire() returns an async context manager."""
    conn = AsyncMock()
    pool = MagicMock()

    @asynccontextmanager
    async def _acquire():
        yield conn

    pool.acquire = _acquire
    return pool, conn


class TestInsightStoreMigration:
    """Verify DDL migration creates correct tables and indexes."""

    @pytest.mark.asyncio
    async def test_migrate_creates_three_tables(self):
        store = InsightStore()
        pool, conn = _make_mock_pool()
        store._pool = pool

        await store._migrate()

        executed_sqls = [call.args[0] for call in conn.execute.call_args_list]
        combined = "\n".join(executed_sqls)

        assert "insight_ingest_batches" in combined
        assert "insight_query_logs" in combined
        assert "insight_driver_scores" in combined

    @pytest.mark.asyncio
    async def test_migrate_creates_unique_index_on_query_logs(self):
        store = InsightStore()
        pool, conn = _make_mock_pool()
        store._pool = pool

        await store._migrate()

        executed_sqls = [call.args[0] for call in conn.execute.call_args_list]
        combined = "\n".join(executed_sqls)

        assert "uq_iql_tenant_query" in combined
        assert "tenant_id, query_id" in combined

    @pytest.mark.asyncio
    async def test_migrate_enables_rls_on_all_tables(self):
        store = InsightStore()
        pool, conn = _make_mock_pool()
        store._pool = pool

        await store._migrate()

        executed_sqls = [call.args[0] for call in conn.execute.call_args_list]
        combined = "\n".join(executed_sqls)

        assert "ENABLE ROW LEVEL SECURITY" in combined
        for tbl in ("insight_ingest_batches", "insight_query_logs", "insight_driver_scores"):
            assert f"{tbl}_tenant_isolation" in combined

    @pytest.mark.asyncio
    async def test_migrate_creates_parse_status_partial_index(self):
        store = InsightStore()
        pool, conn = _make_mock_pool()
        store._pool = pool

        await store._migrate()

        executed_sqls = [call.args[0] for call in conn.execute.call_args_list]
        combined = "\n".join(executed_sqls)

        assert "idx_iql_parse_status" in combined
        assert "WHERE parse_status = 'pending'" in combined

    @pytest.mark.asyncio
    async def test_query_logs_table_has_required_columns(self):
        store = InsightStore()
        pool, conn = _make_mock_pool()
        store._pool = pool

        await store._migrate()

        executed_sqls = [call.args[0] for call in conn.execute.call_args_list]
        combined = "\n".join(executed_sqls)

        required_cols = [
            "tenant_id", "datasource_id", "query_id", "raw_sql",
            "normalized_sql", "sql_hash", "executed_at", "received_at",
            "parse_status", "parsed_tables", "parsed_joins",
            "parsed_predicates", "parsed_select", "parsed_group_by",
        ]
        for col in required_cols:
            assert col in combined, f"Missing column: {col}"


class TestInsightStorePool:
    """Verify pool lifecycle and error handling."""

    @pytest.mark.asyncio
    async def test_missing_dsn_raises_unavailable(self):
        store = InsightStore()
        with patch("app.services.insight_store.settings") as mock_settings:
            mock_settings.postgres_dsn = ""
            with pytest.raises(InsightStoreUnavailableError, match="POSTGRES_DSN"):
                await store._get_pool()

    @pytest.mark.asyncio
    async def test_pool_reused_after_first_init(self):
        store = InsightStore()
        fake_pool = MagicMock()
        store._pool = fake_pool
        result = await store._get_pool()
        assert result is fake_pool

    @pytest.mark.asyncio
    async def test_health_check_executes_select(self):
        store = InsightStore()
        pool, conn = _make_mock_pool()
        store._pool = pool

        await store.health_check()

        conn.execute.assert_called_once_with("SELECT 1")

    @pytest.mark.asyncio
    async def test_get_pool_public_accessor(self):
        store = InsightStore()
        fake_pool = MagicMock()
        store._pool = fake_pool
        result = await store.get_pool()
        assert result is fake_pool
