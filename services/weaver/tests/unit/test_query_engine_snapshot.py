"""QueryPolicyEngine + SchemaSnapshotService 단위 테스트 — Sprint 8.

SQL 안전성 검증, 서킷 브레이커, 감사 로그, 스냅샷 변경 감지 등 검증.
"""

import pytest
from app.services.query_engine import (
    QueryCaller,
    QueryPolicyEngine,
    _validate_sql,
)
from app.services.snapshot_baseline import (
    ChangeType,
    SchemaSnapshotService,
)
from app.services.adapters.normalization import (
    StandardColumnMetadata,
    StandardMetadata,
    StandardSchemaMetadata,
    StandardTableMetadata,
)


# ── SQL 검증 ── #

class TestSQLValidation:
    def test_select_allowed(self):
        assert _validate_sql("SELECT * FROM users", QueryCaller.DIRECT_SQL) is None

    def test_with_cte_allowed(self):
        assert _validate_sql("WITH cte AS (SELECT 1) SELECT * FROM cte", QueryCaller.DIRECT_SQL) is None

    def test_insert_blocked(self):
        result = _validate_sql("INSERT INTO users VALUES (1)", QueryCaller.DIRECT_SQL)
        assert result is not None  # INSERT는 SELECT/WITH 아니므로 차단됨

    def test_delete_blocked(self):
        result = _validate_sql("DELETE FROM users WHERE id = 1", QueryCaller.DIRECT_SQL)
        assert result is not None

    def test_drop_blocked(self):
        result = _validate_sql("DROP TABLE users", QueryCaller.DIRECT_SQL)
        assert result is not None

    def test_multi_statement_blocked(self):
        result = _validate_sql("SELECT 1; DROP TABLE users", QueryCaller.DIRECT_SQL)
        assert result is not None
        assert "멀티" in result

    def test_writable_cte_blocked(self):
        """WITH ... AS (DELETE ...) SELECT — writable CTE 차단"""
        sql = "WITH deleted AS (DELETE FROM users RETURNING *) SELECT * FROM deleted"
        result = _validate_sql(sql, QueryCaller.DIRECT_SQL)
        assert result is not None

    def test_empty_sql_blocked(self):
        result = _validate_sql("", QueryCaller.DIRECT_SQL)
        assert result is not None

    def test_update_in_subquery_blocked(self):
        sql = "SELECT * FROM (UPDATE users SET name='x' RETURNING *) AS t"
        result = _validate_sql(sql, QueryCaller.DIRECT_SQL)
        assert result is not None

    def test_case_insensitive(self):
        assert _validate_sql("select 1", QueryCaller.DIRECT_SQL) is None
        result = _validate_sql("Insert Into t values(1)", QueryCaller.DIRECT_SQL)
        assert result is not None


# ── 서킷 브레이커 ── #

class TestCircuitBreaker:
    def test_block_and_check(self):
        engine = QueryPolicyEngine()
        engine.block_table("public.users")
        result = engine._check_circuit_breaker("SELECT * FROM public.users WHERE id = 1")
        assert result == "public.users"

    def test_unblock(self):
        engine = QueryPolicyEngine()
        engine.block_table("public.users")
        engine.unblock_table("public.users")
        assert engine._check_circuit_breaker("SELECT * FROM public.users") is None

    def test_no_block(self):
        engine = QueryPolicyEngine()
        assert engine._check_circuit_breaker("SELECT 1") is None


# ── 감사 로그 ── #

class TestAuditLog:
    @pytest.mark.asyncio
    async def test_audit_recorded(self):
        engine = QueryPolicyEngine()
        await engine._record_audit_safe(
            "test_ds", QueryCaller.DIRECT_SQL, "user1", "tenant1",
            "abc123", success=True, row_count=10,
        )
        logs = engine.get_audit_logs("tenant1")
        assert len(logs) == 1
        assert logs[0].datasource_name == "test_ds"

    @pytest.mark.asyncio
    async def test_audit_tenant_isolation(self):
        engine = QueryPolicyEngine()
        await engine._record_audit_safe("ds", QueryCaller.DIRECT_SQL, "u1", "t1", "h1")
        await engine._record_audit_safe("ds", QueryCaller.DIRECT_SQL, "u2", "t2", "h2")
        assert len(engine.get_audit_logs("t1")) == 1
        assert len(engine.get_audit_logs("t2")) == 1


# ── 스키마 스냅샷 ── #

def _make_metadata(tables: list[tuple[str, list[tuple[str, str]]]]) -> StandardMetadata:
    """테스트용 StandardMetadata 생성"""
    std_tables = []
    for tname, cols in tables:
        std_cols = [StandardColumnMetadata(name=c[0], data_type=c[1]) for c in cols]
        std_tables.append(StandardTableMetadata(name=tname, columns=std_cols))
    return StandardMetadata(
        source_engine="test",
        schemas=[StandardSchemaMetadata(schema_name="public", tables=std_tables)],
    )


class TestSchemaSnapshot:
    @pytest.mark.asyncio
    async def test_save_and_retrieve(self):
        svc = SchemaSnapshotService()
        meta = _make_metadata([("users", [("id", "INTEGER"), ("name", "TEXT")])])
        sid = await svc.save_snapshot("ds1", meta, tenant_id="t1")
        assert sid

        snap = await svc.get_last_snapshot("ds1", tenant_id="t1")
        assert snap is not None
        assert snap.total_tables == 1
        assert snap.total_columns == 2

    @pytest.mark.asyncio
    async def test_detect_table_added(self):
        svc = SchemaSnapshotService()
        meta1 = _make_metadata([("users", [("id", "INTEGER")])])
        await svc.save_snapshot("ds2", meta1, tenant_id="t1")

        meta2 = _make_metadata([
            ("users", [("id", "INTEGER")]),
            ("orders", [("id", "INTEGER"), ("total", "DECIMAL")]),
        ])
        report = await svc.detect_changes("ds2", meta2, tenant_id="t1")
        assert report.has_changes
        added = [c for c in report.changes if c.change_type == ChangeType.TABLE_ADDED]
        assert any(c.table_name == "orders" for c in added)

    @pytest.mark.asyncio
    async def test_detect_table_removed(self):
        svc = SchemaSnapshotService()
        meta1 = _make_metadata([("users", [("id", "INTEGER")]), ("old", [("x", "TEXT")])])
        await svc.save_snapshot("ds3", meta1, tenant_id="t1")

        meta2 = _make_metadata([("users", [("id", "INTEGER")])])
        report = await svc.detect_changes("ds3", meta2, tenant_id="t1")
        removed = [c for c in report.changes if c.change_type == ChangeType.TABLE_REMOVED]
        assert any(c.table_name == "old" for c in removed)

    @pytest.mark.asyncio
    async def test_detect_column_type_changed(self):
        svc = SchemaSnapshotService()
        meta1 = _make_metadata([("t", [("col", "INTEGER")])])
        await svc.save_snapshot("ds4", meta1, tenant_id="t1")

        meta2 = _make_metadata([("t", [("col", "TEXT")])])
        report = await svc.detect_changes("ds4", meta2, tenant_id="t1")
        type_changes = [c for c in report.changes if c.change_type == ChangeType.COLUMN_TYPE_CHANGED]
        assert len(type_changes) >= 1

    @pytest.mark.asyncio
    async def test_tenant_isolation(self):
        svc = SchemaSnapshotService()
        meta = _make_metadata([("t", [("id", "INTEGER")])])
        await svc.save_snapshot("ds5", meta, tenant_id="t1")
        await svc.save_snapshot("ds5", meta, tenant_id="t2")

        assert await svc.get_last_snapshot("ds5", tenant_id="t1") is not None
        assert await svc.get_last_snapshot("ds5", tenant_id="t2") is not None
        assert await svc.get_last_snapshot("ds5", tenant_id="t3") is None

    @pytest.mark.asyncio
    async def test_first_snapshot_all_added(self):
        """첫 스냅샷 없으면 모든 테이블이 TABLE_ADDED"""
        svc = SchemaSnapshotService()
        meta = _make_metadata([("a", [("id", "INTEGER")]), ("b", [("id", "INTEGER")])])
        report = await svc.detect_changes("ds_new", meta, tenant_id="t1")
        added = [c for c in report.changes if c.change_type == ChangeType.TABLE_ADDED]
        assert len(added) == 2
