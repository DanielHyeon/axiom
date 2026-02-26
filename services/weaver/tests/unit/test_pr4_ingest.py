"""PR4 tests: Ingest API, SQL normalize, idempotency, query store."""
from __future__ import annotations

import hashlib
import pytest
from datetime import datetime, timezone

from app.services.sql_normalize import normalize_sql, mask_pii
from app.services.idempotency import realtime_query_id, batch_query_id


# ── SQL Normalize tests ──────────────────────────────────────

class TestNormalizeSql:

    def test_lowercases(self):
        assert normalize_sql("SELECT * FROM Users") == "select * from users"

    def test_strips_line_comments(self):
        sql = "SELECT 1 -- this is a comment\nFROM t"
        assert "comment" not in normalize_sql(sql)

    def test_strips_block_comments(self):
        sql = "SELECT /* block */ 1 FROM t"
        assert "block" not in normalize_sql(sql)

    def test_collapses_whitespace(self):
        sql = "SELECT   1   FROM   t"
        assert normalize_sql(sql) == "select 1 from t"

    def test_strips_leading_trailing(self):
        assert normalize_sql("  SELECT 1  ") == "select 1"


class TestMaskPii:

    def test_masks_string_literals(self):
        assert mask_pii("WHERE name = 'John Doe'") == "WHERE name = '?'"

    def test_masks_numeric_literals(self):
        result = mask_pii("WHERE id = 12345")
        assert "12345" not in result
        assert "?" in result

    def test_preserves_keywords(self):
        result = mask_pii("SELECT col FROM t WHERE id = 42")
        assert "select" in result.lower()
        assert "from" in result.lower()


# ── Idempotency tests ────────────────────────────────────────

class TestRealtimeQueryId:

    def test_deterministic(self):
        a = realtime_query_id("select 1", "t1", "ds1", "req1")
        b = realtime_query_id("select 1", "t1", "ds1", "req1")
        assert a == b

    def test_different_request_id_produces_different_hash(self):
        a = realtime_query_id("select 1", "t1", "ds1", "req1")
        b = realtime_query_id("select 1", "t1", "ds1", "req2")
        assert a != b

    def test_is_sha256_hex_truncated(self):
        qid = realtime_query_id("sql", "t", "d", "r")
        assert len(qid) == 32
        int(qid, 16)  # raises if not hex


class TestBatchQueryId:

    def test_deterministic(self):
        dt = datetime(2026, 2, 26, 12, 3, 45, tzinfo=timezone.utc)
        a = batch_query_id("select 1", "t1", "ds1", dt)
        b = batch_query_id("select 1", "t1", "ds1", dt)
        assert a == b

    def test_5min_bucket_same_bucket(self):
        dt1 = datetime(2026, 2, 26, 12, 1, 0, tzinfo=timezone.utc)
        dt2 = datetime(2026, 2, 26, 12, 4, 59, tzinfo=timezone.utc)
        a = batch_query_id("select 1", "t1", "ds1", dt1)
        b = batch_query_id("select 1", "t1", "ds1", dt2)
        assert a == b

    def test_5min_bucket_different_bucket(self):
        dt1 = datetime(2026, 2, 26, 12, 4, 0, tzinfo=timezone.utc)
        dt2 = datetime(2026, 2, 26, 12, 5, 0, tzinfo=timezone.utc)
        a = batch_query_id("select 1", "t1", "ds1", dt1)
        b = batch_query_id("select 1", "t1", "ds1", dt2)
        assert a != b


# ── Query Store tests (unit, mocked conn) ────────────────────

class TestInsertLogs:

    @pytest.mark.asyncio
    async def test_insert_returns_counts(self):
        from unittest.mock import AsyncMock
        from app.services.insight_query_store import insert_logs

        conn = AsyncMock()
        # First call returns a row (inserted), second returns None (deduped)
        conn.fetchrow.side_effect = [{"id": 1}, None]

        logs = [
            {
                "query_id": "q1", "raw_sql": "SELECT 1",
                "normalized_sql": "select 1", "sql_hash": "abc",
                "datasource_id": "ds1", "executed_at": datetime.now(timezone.utc),
                "duration_ms": 100, "user_id": "u1", "source": "oracle",
            },
            {
                "query_id": "q2", "raw_sql": "SELECT 2",
                "normalized_sql": "select 2", "sql_hash": "def",
                "datasource_id": "ds1", "executed_at": datetime.now(timezone.utc),
                "duration_ms": None, "user_id": None, "source": "oracle",
            },
        ]

        result = await insert_logs(conn, "t1", logs)
        assert result == {"inserted": 1, "deduped": 1}
        assert conn.fetchrow.call_count == 2

    @pytest.mark.asyncio
    async def test_insert_batch_record(self):
        from unittest.mock import AsyncMock
        from app.services.insight_query_store import insert_batch_record

        conn = AsyncMock()
        conn.fetchrow.return_value = {"id": 42}

        batch_id = await insert_batch_record(conn, "t1", "oracle", 10)
        assert batch_id == 42
        conn.fetchrow.assert_called_once()
