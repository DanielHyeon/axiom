"""Code Analyzer 단위 테스트 — Sprint 8.

JPA 어노테이션, SQLAlchemy, Django ORM 패턴 매칭 + DDL 파서 통합 검증.
"""

import pytest
from pathlib import Path
from app.services.code_analyzer import CodeAnalyzer


@pytest.fixture
def analyzer():
    return CodeAnalyzer()


@pytest.fixture
def sandbox_dir(tmp_path):
    return tmp_path / "sandbox"


def _write_file(sandbox_dir: Path, rel_path: str, content: str) -> None:
    """테스트용 파일 생성"""
    file_path = sandbox_dir / rel_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content)


# ── JPA 분석 ── #

class TestJavaJPAAnalysis:
    @pytest.mark.asyncio
    async def test_jpa_entity_detection(self, analyzer, sandbox_dir):
        _write_file(sandbox_dir, "Order.java", """
package com.example;

import javax.persistence.*;

@Entity
@Table(name = "orders")
public class Order {
    @Id
    private Long id;

    @Column(name = "customer_name")
    private String customerName;

    @Column(name = "total_amount")
    private Double totalAmount;
}
""")
        events = []
        async for event in analyzer.analyze("test1", str(sandbox_dir)):
            events.append(event)

        table_events = [e for e in events if e.event_type == "table_found"]
        assert len(table_events) == 1
        assert table_events[0].data["table_name"] == "orders"
        assert table_events[0].evidence is not None
        assert table_events[0].evidence.confidence >= 0.8

    @pytest.mark.asyncio
    async def test_jpa_fk_detection(self, analyzer, sandbox_dir):
        _write_file(sandbox_dir, "OrderItem.java", """
@Entity
@Table(name = "order_items")
public class OrderItem {
    @Id
    private Long id;

    @ManyToOne
    @JoinColumn(name = "order_id")
    private Order order;
}
""")
        events = []
        async for event in analyzer.analyze("test2", str(sandbox_dir)):
            events.append(event)

        fk_events = [e for e in events if e.event_type == "fk_inferred"]
        assert len(fk_events) >= 1
        # G01b: 블록 파서는 fk_column, 정규식 폴백은 source_columns
        fk_data = fk_events[0].data
        assert fk_data.get("fk_column") == "order_id" or fk_data.get("source_columns") == ["order_id"]

    @pytest.mark.asyncio
    async def test_non_entity_java_skipped(self, analyzer, sandbox_dir):
        """@Entity 없는 Java 파일은 스킵"""
        _write_file(sandbox_dir, "Utils.java", """
public class Utils {
    public static String format(String s) { return s.trim(); }
}
""")
        events = []
        async for event in analyzer.analyze("test3", str(sandbox_dir)):
            events.append(event)
        table_events = [e for e in events if e.event_type == "table_found"]
        assert len(table_events) == 0


# ── SQLAlchemy 분석 ── #

class TestPythonSQLAlchemyAnalysis:
    @pytest.mark.asyncio
    async def test_sqlalchemy_model(self, analyzer, sandbox_dir):
        _write_file(sandbox_dir, "models.py", """
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    dept_id = Column(Integer, ForeignKey('departments.id'))
""")
        events = []
        async for event in analyzer.analyze("test4", str(sandbox_dir)):
            events.append(event)

        table_events = [e for e in events if e.event_type == "table_found"]
        assert len(table_events) == 1
        assert table_events[0].data["table_name"] == "users"

        fk_events = [e for e in events if e.event_type == "fk_inferred"]
        assert len(fk_events) == 1
        assert fk_events[0].data["target_table"] == "departments"


# ── DDL 파서 통합 ── #

class TestDDLIntegration:
    @pytest.mark.asyncio
    async def test_ddl_file_parsed(self, analyzer, sandbox_dir):
        _write_file(sandbox_dir, "schema.sql", """
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(200)
        );
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        );
        """)
        events = []
        async for event in analyzer.analyze("test5", str(sandbox_dir)):
            events.append(event)

        table_events = [e for e in events if e.event_type == "table_found"]
        assert len(table_events) == 2

        fk_events = [e for e in events if e.event_type == "fk_inferred"]
        assert len(fk_events) == 1
        assert fk_events[0].data["target_table"] == "customers"
        assert fk_events[0].evidence.confidence >= 0.9


# ── 엣지 케이스 ── #

class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_empty_sandbox(self, analyzer, sandbox_dir):
        sandbox_dir.mkdir(parents=True, exist_ok=True)
        events = []
        async for event in analyzer.analyze("test6", str(sandbox_dir)):
            events.append(event)
        complete = [e for e in events if e.event_type == "complete"]
        assert len(complete) == 1

    @pytest.mark.asyncio
    async def test_nonexistent_sandbox(self, analyzer):
        events = []
        async for event in analyzer.analyze("test7", "/nonexistent/path"):
            events.append(event)
        errors = [e for e in events if e.event_type == "error"]
        assert len(errors) >= 1

    @pytest.mark.asyncio
    async def test_evidence_always_attached(self, analyzer, sandbox_dir):
        """모든 table_found/fk_inferred 이벤트에 evidence 첨부"""
        _write_file(sandbox_dir, "test.sql", "CREATE TABLE t (id INT);")
        async for event in analyzer.analyze("test8", str(sandbox_dir)):
            if event.event_type in ("table_found", "fk_inferred"):
                assert event.evidence is not None
                assert event.evidence.source_file
