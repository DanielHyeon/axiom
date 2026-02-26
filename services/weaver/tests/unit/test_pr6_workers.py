"""PR6 tests: Parse task + Impact task."""
from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.worker.parse_task import parse_sql_regex, run_parse_task, ParseResult


# ── FakeRedis (reused from PR5 tests) ────────────────────────

class FakeRedis:
    def __init__(self):
        self._strings: dict[str, str] = {}
        self._hashes: dict[str, dict[str, str]] = {}

    async def get(self, key):
        return self._strings.get(key)

    async def set(self, key, value, *, ex=None):
        self._strings[key] = value

    async def hset(self, key, *, mapping):
        if key not in self._hashes:
            self._hashes[key] = {}
        self._hashes[key].update(mapping)

    async def hgetall(self, key):
        return self._hashes.get(key, {})

    async def expire(self, key, ttl):
        pass


# ── parse_sql_regex tests ────────────────────────────────────

class TestParseSqlRegex:

    def test_simple_select(self):
        r = parse_sql_regex("SELECT id, name FROM users WHERE id = 1")
        assert r.mode == "primary"
        assert "users" in r.tables
        assert "id" in r.select_columns or "name" in r.select_columns
        assert r.confidence > 0.5

    def test_join_query(self):
        sql = (
            "SELECT o.id, u.name FROM orders o "
            "INNER JOIN users u ON o.user_id = u.id "
            "WHERE o.status = 'active'"
        )
        r = parse_sql_regex(sql)
        assert r.mode == "primary"
        assert len(r.tables) >= 2
        assert len(r.joins) >= 1

    def test_group_by(self):
        sql = "SELECT dept, COUNT(*) FROM employees GROUP BY dept"
        r = parse_sql_regex(sql)
        assert "dept" in r.group_by

    def test_schema_qualified_table(self):
        sql = "SELECT 1 FROM sales.orders WHERE id = 1"
        r = parse_sql_regex(sql)
        assert any("sales.orders" in t for t in r.tables)

    def test_empty_sql_fails(self):
        r = parse_sql_regex("")
        assert r.mode == "failed"
        assert r.errors

    def test_garbage_sql_fails(self):
        r = parse_sql_regex("XYZZY BLARG FLURB")
        assert r.mode == "failed"

    def test_no_select_is_fallback(self):
        # UPDATE without clear SELECT columns pattern
        r = parse_sql_regex("UPDATE users SET name = 'x' WHERE id = 1")
        assert r.tables  # should still extract 'users'
        # mode depends on whether select columns found
        assert r.mode in ("primary", "fallback")

    def test_predicates_extracted(self):
        sql = "SELECT 1 FROM t WHERE a = 1 AND b = 2"
        r = parse_sql_regex(sql)
        assert len(r.predicates) >= 2

    def test_multiple_tables(self):
        sql = "SELECT a.x, b.y FROM alpha a JOIN beta b ON a.id = b.id"
        r = parse_sql_regex(sql)
        assert len(r.tables) >= 2


# ── run_parse_task tests (mocked conn) ───────────────────────

class TestRunParseTask:

    @pytest.mark.asyncio
    async def test_parsed_status_on_valid_sql(self):
        conn = AsyncMock()
        conn.fetchrow.return_value = {
            "normalized_sql": "select id, name from users where id = ?"
        }

        status = await run_parse_task(conn, "t1", 1)
        assert status == "parsed"
        # Verify UPDATE was called
        conn.execute.assert_called_once()
        args = conn.execute.call_args[0]
        assert args[1] == "parsed"  # parse_status

    @pytest.mark.asyncio
    async def test_failed_status_on_garbage(self):
        conn = AsyncMock()
        conn.fetchrow.return_value = {"normalized_sql": "XYZZY BLARG"}

        status = await run_parse_task(conn, "t1", 2)
        assert status == "failed"

    @pytest.mark.asyncio
    async def test_skipped_when_row_not_found(self):
        conn = AsyncMock()
        conn.fetchrow.return_value = None

        status = await run_parse_task(conn, "t1", 999)
        assert status == "skipped"
        conn.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_fallback_on_no_select_columns(self):
        conn = AsyncMock()
        # INSERT without select
        conn.fetchrow.return_value = {
            "normalized_sql": "INSERT INTO users (name) VALUES (?)"
        }
        status = await run_parse_task(conn, "t1", 3)
        # Should be fallback (has table but no select columns)
        assert status in ("fallback", "parsed")

    @pytest.mark.asyncio
    async def test_updates_parsed_fields(self):
        conn = AsyncMock()
        conn.fetchrow.return_value = {
            "normalized_sql": "select id from orders where status = ?"
        }

        await run_parse_task(conn, "t1", 10)
        args = conn.execute.call_args[0]
        # args[4] = parsed_tables JSON
        tables = json.loads(args[4])
        assert "orders" in tables


# ── Impact task tests ────────────────────────────────────────

class TestRunImpactTask:

    @pytest.mark.asyncio
    async def test_queued_to_done(self):
        """Impact task runs the full pipeline and stores result."""
        from app.worker.impact_task import run_impact_task
        from app.services.query_log_analyzer import AnalysisResult

        rd = FakeRedis()
        conn = AsyncMock()

        # Mock analyze_query_logs to return a minimal AnalysisResult
        mock_analysis = AnalysisResult(
            time_from="2026-01-27T00:00:00+00:00",
            time_to="2026-02-26T00:00:00+00:00",
            total_queries=42,
            used_queries=42,
            column_stats={},
            table_counts={},
            join_edges={},
            evidence_samples={},
            cooccur=None,
        )

        job_id = "test-job-1"
        await rd.hset(f"insight:job:{job_id}", mapping={
            "job_id": job_id,
            "tenant_id": "t1",
            "status": "queued",
            "progress": "0",
            "error": "",
            "result": "",
            "updated_at": "0",
        })

        with patch(
            "app.worker.impact_task.analyze_query_logs",
            return_value=mock_analysis,
        ):
            await run_impact_task(
                rd, conn,
                job_id=job_id,
                tenant_id="t1",
                datasource_id="ds1",
                kpi_fingerprint="kpi1",
                time_range="30d",
                top=50,
            )

        job = await rd.hgetall(f"insight:job:{job_id}")
        assert job["status"] == "done"
        assert job["progress"] == "100"
        result = json.loads(job["result"])
        graph = result["graph"]
        assert graph["meta"]["explain"]["total_queries_analyzed"] == 42

    @pytest.mark.asyncio
    async def test_queued_to_failed_on_error(self):
        from app.worker.impact_task import run_impact_task

        rd = FakeRedis()
        conn = AsyncMock()

        job_id = "test-job-2"
        await rd.hset(f"insight:job:{job_id}", mapping={
            "job_id": job_id,
            "tenant_id": "t1",
            "status": "queued",
            "progress": "0",
            "error": "",
            "result": "",
            "updated_at": "0",
        })

        with patch(
            "app.worker.impact_task.analyze_query_logs",
            side_effect=Exception("DB connection lost"),
        ):
            await run_impact_task(
                rd, conn,
                job_id=job_id,
                tenant_id="t1",
                datasource_id="ds1",
                kpi_fingerprint="kpi1",
            )

        job = await rd.hgetall(f"insight:job:{job_id}")
        assert job["status"] == "failed"
        assert "DB connection lost" in job["error"]

    @pytest.mark.asyncio
    async def test_progress_updates_during_execution(self):
        """Verify progress increments during task execution."""
        from app.worker.impact_task import run_impact_task
        from app.services.query_log_analyzer import AnalysisResult

        rd = FakeRedis()
        conn = AsyncMock()

        mock_analysis = AnalysisResult(
            time_from="2026-01-27T00:00:00+00:00",
            time_to="2026-02-26T00:00:00+00:00",
            total_queries=10,
            used_queries=10,
            column_stats={},
            table_counts={},
            join_edges={},
            evidence_samples={},
            cooccur=None,
        )

        job_id = "test-job-3"
        await rd.hset(f"insight:job:{job_id}", mapping={
            "job_id": job_id,
            "status": "queued",
            "progress": "0",
            "error": "",
            "result": "",
            "updated_at": "0",
            "tenant_id": "t1",
        })

        with patch(
            "app.worker.impact_task.analyze_query_logs",
            return_value=mock_analysis,
        ):
            await run_impact_task(
                rd, conn,
                job_id=job_id,
                tenant_id="t1",
                datasource_id="ds1",
                kpi_fingerprint="kpi1",
            )

        # After completion, progress should be 100
        job = await rd.hgetall(f"insight:job:{job_id}")
        assert job["progress"] == "100"
