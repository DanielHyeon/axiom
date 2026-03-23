"""DDL 파서 단위 테스트 — Sprint 8 E2E 테스트.

CREATE TABLE, ALTER TABLE, COMMENT ON, 인라인 FK/PK,
Quoted identifiers, IF NOT EXISTS 등 핵심 구문 파싱 검증.
"""

import pytest
from app.services.parsers.ddl_parser import DDLParser
from app.services.parsers.ddl_models import DDLParseResult


@pytest.fixture
def parser():
    return DDLParser(dialect="postgresql")


# ── CREATE TABLE 기본 ── #

class TestCreateTable:
    def test_simple_table(self, parser):
        ddl = """
        CREATE TABLE orders (
            id INTEGER NOT NULL PRIMARY KEY,
            customer_id INTEGER,
            total NUMERIC(10,2),
            created_at TIMESTAMP DEFAULT now()
        );
        """
        result = parser.parse(ddl)
        assert result.table_count == 1
        assert result.error_count == 0

        t = result.tables[0]
        assert t.table_name == "orders"
        assert len(t.columns) == 4
        assert t.columns[0].name == "id"
        assert t.columns[0].is_primary_key is True
        assert t.columns[0].nullable is False

    def test_if_not_exists(self, parser):
        ddl = "CREATE TABLE IF NOT EXISTS users (id INT PRIMARY KEY, name VARCHAR(100));"
        result = parser.parse(ddl)
        assert result.table_count == 1
        assert result.tables[0].if_not_exists is True

    def test_schema_qualified(self, parser):
        ddl = 'CREATE TABLE myschema.products (id INT, name TEXT);'
        result = parser.parse(ddl)
        assert result.tables[0].schema_name == "myschema"
        assert result.tables[0].table_name == "products"

    def test_quoted_identifiers(self, parser):
        ddl = 'CREATE TABLE "MySchema"."Order_Items" ("ItemId" INT, "Price" DECIMAL(8,2));'
        result = parser.parse(ddl)
        assert result.tables[0].schema_name == "MySchema"
        assert result.tables[0].table_name == "Order_Items"

    def test_multiple_tables(self, parser):
        ddl = """
        CREATE TABLE a (id INT);
        CREATE TABLE b (id INT, a_id INT);
        CREATE TABLE c (id INT);
        """
        result = parser.parse(ddl)
        assert result.table_count == 3

    def test_nullable_detection(self, parser):
        ddl = """
        CREATE TABLE t (
            col_nn INT NOT NULL,
            col_null INT NULL,
            col_default INT
        );
        """
        result = parser.parse(ddl)
        cols = {c.name: c for c in result.tables[0].columns}
        assert cols["col_nn"].nullable is False
        assert cols["col_null"].nullable is True
        assert cols["col_default"].nullable is True


# ── 인라인 제약조건 ── #

class TestInlineConstraints:
    def test_inline_pk(self, parser):
        ddl = """
        CREATE TABLE t (
            id INT,
            name TEXT,
            PRIMARY KEY (id)
        );
        """
        result = parser.parse(ddl)
        t = result.tables[0]
        assert t.primary_key is not None
        assert t.primary_key.columns == ["id"]
        pk_col = [c for c in t.columns if c.name == "id"][0]
        assert pk_col.is_primary_key is True
        assert pk_col.nullable is False

    def test_inline_fk(self, parser):
        ddl = """
        CREATE TABLE order_items (
            id INT PRIMARY KEY,
            order_id INT,
            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
        );
        """
        result = parser.parse(ddl)
        t = result.tables[0]
        assert len(t.foreign_keys) == 1
        fk = t.foreign_keys[0]
        assert fk.source_columns == ["order_id"]
        assert fk.target_table == "orders"
        assert fk.target_columns == ["id"]
        assert fk.on_delete.upper() == "CASCADE"

    def test_inline_references(self, parser):
        """컬럼 정의에 REFERENCES 포함"""
        ddl = """
        CREATE TABLE payments (
            id INT PRIMARY KEY,
            order_id INT REFERENCES orders(id)
        );
        """
        result = parser.parse(ddl)
        t = result.tables[0]
        assert len(t.foreign_keys) >= 1
        fk = t.foreign_keys[0]
        assert fk.target_table == "orders"


# ── ALTER TABLE ── #

class TestAlterTable:
    def test_alter_add_pk(self, parser):
        ddl = """
        CREATE TABLE t (id INT, name TEXT);
        ALTER TABLE t ADD PRIMARY KEY (id);
        """
        result = parser.parse(ddl)
        t = result.tables[0]
        assert t.primary_key is not None
        assert t.primary_key.columns == ["id"]

    def test_alter_add_fk(self, parser):
        ddl = """
        CREATE TABLE orders (id INT);
        CREATE TABLE items (id INT, order_id INT);
        ALTER TABLE items ADD CONSTRAINT fk_order
            FOREIGN KEY (order_id) REFERENCES orders(id);
        """
        result = parser.parse(ddl)
        items = [t for t in result.tables if t.table_name == "items"][0]
        assert len(items.foreign_keys) == 1
        assert items.foreign_keys[0].constraint_name == "fk_order"


# ── COMMENT ON ── #

class TestComments:
    def test_comment_on_table(self, parser):
        ddl = """
        CREATE TABLE products (id INT, name TEXT);
        COMMENT ON TABLE products IS '상품 마스터 테이블';
        """
        result = parser.parse(ddl)
        assert result.tables[0].comment == "상품 마스터 테이블"

    def test_comment_on_column(self, parser):
        ddl = """
        CREATE TABLE products (id INT, name TEXT);
        COMMENT ON COLUMN products.name IS '상품명';
        """
        result = parser.parse(ddl)
        name_col = [c for c in result.tables[0].columns if c.name == "name"][0]
        assert name_col.comment == "상품명"

    def test_sql_comments_stripped(self, parser):
        ddl = """
        -- 이것은 주석
        CREATE TABLE t (
            id INT, /* 블록 주석 */
            name TEXT
        );
        """
        result = parser.parse(ddl)
        assert result.table_count == 1


# ── 에러 처리 ── #

class TestErrorHandling:
    def test_empty_input(self, parser):
        result = parser.parse("")
        assert result.table_count == 0
        assert result.error_count == 0

    def test_invalid_sql(self, parser):
        result = parser.parse("THIS IS NOT SQL AT ALL;")
        assert result.table_count == 0

    def test_partial_parse(self, parser):
        """유효한 DDL + 깨진 DDL → 유효한 것만 파싱"""
        ddl = """
        CREATE TABLE good_table (id INT, name TEXT);
        CREATE TABLE bad_table (;
        """
        result = parser.parse(ddl)
        assert result.table_count >= 1

    def test_source_file_recorded(self, parser):
        result = parser.parse("SELECT 1;", source_file="test.sql")
        assert result.source_file == "test.sql"
