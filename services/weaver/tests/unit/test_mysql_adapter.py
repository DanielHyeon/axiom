"""MySQL 어댑터 단위 테스트.

MySQLSchemaIntrospector의 SQL 생성 및 타입 변환 로직을 테스트한다.
실제 MySQL 연결 없이 순수 로직만 검증.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.mysql_adapter import MySQLSchemaIntrospector


# ── 타입 변환 테스트 ───────────────────────────────────────────────


class TestFormatColumnType:
    """MySQL 컬럼 타입 포맷터 테스트"""

    def test_varchar_with_length(self):
        """varchar(255) 형식"""
        result = MySQLSchemaIntrospector._format_column_type(
            data_type="varchar", char_max_length=255, num_precision=None, num_scale=None
        )
        assert result == "varchar(255)"

    def test_char_with_length(self):
        """char(10) 형식"""
        result = MySQLSchemaIntrospector._format_column_type(
            data_type="char", char_max_length=10, num_precision=None, num_scale=None
        )
        assert result == "char(10)"

    def test_decimal_with_precision(self):
        """decimal(10,2) 형식"""
        result = MySQLSchemaIntrospector._format_column_type(
            data_type="decimal", char_max_length=None, num_precision=10, num_scale=2
        )
        assert result == "decimal(10,2)"

    def test_int_simple(self):
        """int (길이 없음)"""
        result = MySQLSchemaIntrospector._format_column_type(
            data_type="int", char_max_length=None, num_precision=None, num_scale=None
        )
        assert result == "int"

    def test_text_simple(self):
        """text 타입"""
        result = MySQLSchemaIntrospector._format_column_type(
            data_type="text", char_max_length=None, num_precision=None, num_scale=None
        )
        assert result == "text"

    def test_none_data_type(self):
        """None 타입은 unknown"""
        result = MySQLSchemaIntrospector._format_column_type(
            data_type=None, char_max_length=None, num_precision=None, num_scale=None
        )
        assert result == "unknown"

    def test_decimal_zero_scale(self):
        """decimal(10,0) — scale이 0인 경우"""
        result = MySQLSchemaIntrospector._format_column_type(
            data_type="numeric", char_max_length=None, num_precision=10, num_scale=0
        )
        assert result == "numeric(10,0)"

    def test_binary_with_length(self):
        """binary(16) 형식"""
        result = MySQLSchemaIntrospector._format_column_type(
            data_type="binary", char_max_length=16, num_precision=None, num_scale=None
        )
        assert result == "binary(16)"


# ── 인스턴스 생성 테스트 ───────────────────────────────────────────


class TestMySQLSchemaIntrospector:
    """MySQLSchemaIntrospector 클래스 테스트"""

    def test_instantiation(self):
        """인스턴스 생성 확인"""
        introspector = MySQLSchemaIntrospector()
        assert introspector is not None

    def test_validate_dependency_without_aiomysql(self):
        """aiomysql 미설치 시 ImportError 발생"""
        introspector = MySQLSchemaIntrospector()
        with patch("app.core.mysql_adapter.HAS_AIOMYSQL", False):
            with pytest.raises(ImportError, match="aiomysql"):
                introspector._validate_dependency()


# ── 스키마 조회 테스트 (모킹) ──────────────────────────────────────


class TestGetSchemas:
    """스키마 목록 조회 테스트"""

    @pytest.mark.asyncio
    async def test_get_schemas(self):
        """시스템 스키마를 제외한 사용자 스키마 반환"""
        introspector = MySQLSchemaIntrospector()

        mock_conn = MagicMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[
            ("mydb",),
            ("sales",),
            ("inventory",),
        ])
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=False)
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.close = MagicMock()

        async def fake_get_conn(params):
            return mock_conn

        with patch.object(introspector, "_get_connection", side_effect=fake_get_conn):
            result = await introspector.get_schemas({"host": "localhost"})

        assert result == ["mydb", "sales", "inventory"]
        mock_conn.close.assert_called_once()


class TestGetTables:
    """테이블 목록 조회 테스트"""

    @pytest.mark.asyncio
    async def test_get_tables(self):
        """테이블 정보를 올바르게 반환"""
        introspector = MySQLSchemaIntrospector()

        mock_conn = MagicMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[
            ("orders", "BASE TABLE", "InnoDB", 1500, "주문 테이블"),
            ("products", "BASE TABLE", "InnoDB", 200, ""),
            ("sales_view", "VIEW", None, None, "매출 뷰"),
        ])
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=False)
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.close = MagicMock()

        async def fake_get_conn(params):
            return mock_conn

        with patch.object(introspector, "_get_connection", side_effect=fake_get_conn):
            result = await introspector.get_tables({"host": "localhost"}, schema="mydb")

        assert len(result) == 3
        assert result[0]["name"] == "orders"
        assert result[0]["type"] == "BASE TABLE"
        assert result[0]["engine"] == "InnoDB"
        assert result[0]["row_count"] == 1500
        assert result[2]["type"] == "VIEW"

    @pytest.mark.asyncio
    async def test_get_tables_empty_schema_raises(self):
        """빈 스키마명은 ValueError 발생"""
        introspector = MySQLSchemaIntrospector()
        with pytest.raises(ValueError, match="스키마"):
            await introspector.get_tables({}, schema="")


class TestGetColumns:
    """컬럼 목록 조회 테스트"""

    @pytest.mark.asyncio
    async def test_get_columns(self):
        """컬럼 정보를 올바르게 반환"""
        introspector = MySQLSchemaIntrospector()

        mock_conn = MagicMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[
            ("id", "int", "NO", None, "PRI", "기본키", 1, None, 10, 0),
            ("name", "varchar", "YES", None, "", "이름", 2, 255, None, None),
            ("price", "decimal", "NO", "0.00", "", "가격", 3, None, 10, 2),
        ])
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=False)
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.close = MagicMock()

        async def fake_get_conn(params):
            return mock_conn

        with patch.object(introspector, "_get_connection", side_effect=fake_get_conn):
            result = await introspector.get_columns(
                {"host": "localhost"}, schema="mydb", table="products"
            )

        assert len(result) == 3
        # PK 확인
        assert result[0]["name"] == "id"
        assert result[0]["is_primary"] is True
        assert result[0]["nullable"] is False
        assert result[0]["type"] == "int"
        # varchar(255)
        assert result[1]["type"] == "varchar(255)"
        assert result[1]["nullable"] is True
        # decimal(10,2)
        assert result[2]["type"] == "decimal(10,2)"
        assert result[2]["default"] == "0.00"

    @pytest.mark.asyncio
    async def test_get_columns_empty_params_raises(self):
        """필수 파라미터 누락 시 ValueError"""
        introspector = MySQLSchemaIntrospector()
        with pytest.raises(ValueError):
            await introspector.get_columns({}, schema="", table="t")


class TestGetForeignKeys:
    """FK 조회 테스트"""

    @pytest.mark.asyncio
    async def test_get_foreign_keys(self):
        """FK 정보를 올바르게 반환"""
        introspector = MySQLSchemaIntrospector()

        mock_conn = MagicMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[
            ("fk_order_user", "orders", "user_id", "users", "id"),
            ("fk_order_product", "order_items", "product_id", "products", "id"),
        ])
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=False)
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.close = MagicMock()

        async def fake_get_conn(params):
            return mock_conn

        with patch.object(introspector, "_get_connection", side_effect=fake_get_conn):
            result = await introspector.get_foreign_keys({"host": "localhost"}, schema="mydb")

        assert len(result) == 2
        assert result[0]["constraint_name"] == "fk_order_user"
        assert result[0]["table"] == "orders"
        assert result[0]["column"] == "user_id"
        assert result[0]["referenced_table"] == "users"
        assert result[0]["referenced_column"] == "id"

    @pytest.mark.asyncio
    async def test_get_foreign_keys_empty_schema_raises(self):
        """빈 스키마명은 ValueError"""
        introspector = MySQLSchemaIntrospector()
        with pytest.raises(ValueError, match="스키마"):
            await introspector.get_foreign_keys({}, schema="")


# ── 싱글턴 인스턴스 테스트 ─────────────────────────────────────────


class TestSingleton:
    """모듈 레벨 싱글턴 인스턴스 테스트"""

    def test_module_instance(self):
        """mysql_introspector 싱글턴이 존재한다"""
        from app.core.mysql_adapter import mysql_introspector
        assert isinstance(mysql_introspector, MySQLSchemaIntrospector)
