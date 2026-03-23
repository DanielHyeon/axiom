"""Code Lineage 단위 테스트 — Sprint 8.

INSERT INTO, CTAS, CTE, FROM/JOIN 리니지 추출 + Mermaid 생성 검증.
"""

import pytest
from pathlib import Path
from app.services.code_lineage import CodeLineageExtractor
from app.services.parsers.lineage_models import LineageNodeType, _sanitize_mermaid_label


@pytest.fixture
def extractor():
    return CodeLineageExtractor()


@pytest.fixture
def sandbox_dir(tmp_path):
    return tmp_path / "sandbox"


def _write_sql(sandbox_dir: Path, filename: str, content: str) -> None:
    sandbox_dir.mkdir(parents=True, exist_ok=True)
    (sandbox_dir / filename).write_text(content)


# ── INSERT INTO ── #

class TestInsertLineage:
    @pytest.mark.asyncio
    async def test_simple_insert(self, extractor, sandbox_dir):
        _write_sql(sandbox_dir, "etl.sql", """
        INSERT INTO target_table
        SELECT a.id, b.name
        FROM source_a a
        JOIN source_b b ON a.id = b.a_id;
        """)
        graph = await extractor.extract_lineage("t1", str(sandbox_dir))
        assert graph.node_count >= 3  # source_a, source_b, target_table

        sinks = [n for n in graph.nodes if n.node_type == LineageNodeType.SINK]
        assert len(sinks) == 1
        assert sinks[0].name == "target_table"

        sources = [n for n in graph.nodes if n.node_type == LineageNodeType.SOURCE]
        source_names = {s.name for s in sources}
        assert "source_a" in source_names
        assert "source_b" in source_names

        assert graph.edge_count >= 2

    @pytest.mark.asyncio
    async def test_insert_with_aggregate(self, extractor, sandbox_dir):
        """집계 함수 있으면 transform 노드 삽입"""
        _write_sql(sandbox_dir, "agg.sql", """
        INSERT INTO summary
        SELECT category, COUNT(*), SUM(amount)
        FROM transactions
        GROUP BY category;
        """)
        graph = await extractor.extract_lineage("t2", str(sandbox_dir))
        transforms = [n for n in graph.nodes if n.node_type == LineageNodeType.TRANSFORM]
        assert len(transforms) >= 1


# ── CTAS ── #

class TestCTASLineage:
    @pytest.mark.asyncio
    async def test_create_table_as(self, extractor, sandbox_dir):
        _write_sql(sandbox_dir, "ctas.sql", """
        CREATE TABLE daily_summary AS
        SELECT date, SUM(amount)
        FROM sales
        GROUP BY date;
        """)
        graph = await extractor.extract_lineage("t3", str(sandbox_dir))
        sinks = [n for n in graph.nodes if n.node_type == LineageNodeType.SINK]
        assert any(s.name == "daily_summary" for s in sinks)

        sources = [n for n in graph.nodes if n.node_type == LineageNodeType.SOURCE]
        assert any(s.name == "sales" for s in sources)


# ── CTE ── #

class TestCTELineage:
    @pytest.mark.asyncio
    async def test_with_cte(self, extractor, sandbox_dir):
        _write_sql(sandbox_dir, "cte.sql", """
        WITH active_users AS (
            SELECT id, name FROM users WHERE active = true
        )
        INSERT INTO report
        SELECT * FROM active_users;
        """)
        graph = await extractor.extract_lineage("t4", str(sandbox_dir))
        ctes = [n for n in graph.nodes if n.node_type == LineageNodeType.CTE]
        assert any(c.name == "active_users" for c in ctes)


# ── 중복 병합 ── #

class TestDuplicateMerge:
    @pytest.mark.asyncio
    async def test_same_table_merged(self, extractor, sandbox_dir):
        """같은 소스 테이블이 여러 파일에서 참조되면 하나로 병합"""
        _write_sql(sandbox_dir, "a.sql", "INSERT INTO sink1 SELECT * FROM shared_source;")
        _write_sql(sandbox_dir, "b.sql", "INSERT INTO sink2 SELECT * FROM shared_source;")
        graph = await extractor.extract_lineage("t5", str(sandbox_dir))

        source_nodes = [n for n in graph.nodes
                        if n.node_type == LineageNodeType.SOURCE and n.name == "shared_source"]
        assert len(source_nodes) == 1  # 병합됨

    @pytest.mark.asyncio
    async def test_edges_deduped_after_merge(self, extractor, sandbox_dir):
        """노드 병합 후 중복 엣지 제거"""
        _write_sql(sandbox_dir, "dup.sql", """
        INSERT INTO target SELECT * FROM src;
        INSERT INTO target SELECT * FROM src;
        """)
        graph = await extractor.extract_lineage("t6", str(sandbox_dir))
        # 동일 source→target 엣지는 1개만
        edge_keys = [(e.source_node_id, e.target_node_id) for e in graph.edges]
        assert len(edge_keys) == len(set(edge_keys))


# ── Mermaid 생성 ── #

class TestMermaidGeneration:
    @pytest.mark.asyncio
    async def test_mermaid_output(self, extractor, sandbox_dir):
        _write_sql(sandbox_dir, "simple.sql", """
        INSERT INTO report SELECT * FROM sales JOIN products ON sales.pid = products.id;
        """)
        graph = await extractor.extract_lineage("t7", str(sandbox_dir))
        mermaid = graph.to_mermaid()
        assert mermaid.startswith("graph LR")
        assert "N0" in mermaid
        assert "-->" in mermaid

    def test_mermaid_label_sanitization(self):
        """특수문자가 제거되는지 확인"""
        assert '"' not in _sanitize_mermaid_label('table"name')
        assert '|' not in _sanitize_mermaid_label('label|pipe')
        assert '\n' not in _sanitize_mermaid_label('multi\nline')
        assert len(_sanitize_mermaid_label("x" * 200)) <= 120


# ── 시스템 테이블 제외 ── #

class TestSystemTableExclusion:
    @pytest.mark.asyncio
    async def test_system_tables_excluded(self, extractor, sandbox_dir):
        _write_sql(sandbox_dir, "sys.sql", """
        SELECT * FROM information_schema.tables;
        SELECT * FROM pg_catalog.pg_class;
        SELECT * FROM dual;
        """)
        graph = await extractor.extract_lineage("t8", str(sandbox_dir))
        source_names = {n.name for n in graph.nodes if n.node_type == LineageNodeType.SOURCE}
        assert "information_schema" not in source_names
        assert "pg_catalog" not in source_names
        assert "dual" not in source_names


# ── 에러 처리 ── #

class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_nonexistent_dir(self, extractor):
        graph = await extractor.extract_lineage("t9", "/nonexistent")
        assert len(graph.errors) >= 1

    @pytest.mark.asyncio
    async def test_no_sql_files(self, extractor, sandbox_dir):
        sandbox_dir.mkdir(parents=True, exist_ok=True)
        (sandbox_dir / "readme.md").write_text("# Not SQL")
        graph = await extractor.extract_lineage("t10", str(sandbox_dir))
        assert len(graph.errors) >= 1

    @pytest.mark.asyncio
    async def test_empty_sql_file(self, extractor, sandbox_dir):
        _write_sql(sandbox_dir, "empty.sql", "")
        graph = await extractor.extract_lineage("t11", str(sandbox_dir))
        assert graph.node_count == 0
