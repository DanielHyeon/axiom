"""G13 고도화: SQLGlot AST 기반 정밀 리니지 추출.

정규식 MVP(code_lineage.py)를 SQLGlot AST 파싱으로 고도화하여
서브쿼리, CTE, UNION, 윈도우 함수 등 복잡한 SQL의 리니지를 정확하게 추출한다.

SQLGlot이 설치되지 않으면 기존 정규식 폴백을 사용한다.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.parsers.lineage_models import (
    ColumnLineage,
    ColumnLineageConfidence,
    LineageEdge,
    LineageEdgeType,
    LineageGraph,
    LineageNode,
    LineageNodeType,
)

logger = logging.getLogger("axiom.weaver.parsers.sqlglot_lineage")

try:
    import sqlglot  # type: ignore
    from sqlglot import exp as sqlglot_exp  # type: ignore
    HAS_SQLGLOT = True
except ImportError:
    HAS_SQLGLOT = False


# 시스템 테이블 제외
_SYSTEM_TABLES = {
    "dual", "information_schema", "pg_catalog", "sys", "system",
    "generate_series", "unnest",
}


class SQLGlotLineageExtractor:
    """SQLGlot AST 기반 정밀 리니지 추출.

    정규식 MVP 대비 장점:
    - 서브쿼리 내 FROM 정확 추출
    - CTE 체인 (WITH a AS (...), b AS (SELECT FROM a)) 올바른 의존성
    - UNION/INTERSECT/EXCEPT 양쪽 소스 추출
    - 컬럼 수준 리니지 (SELECT a.col1, b.col2 → 출처 테이블 매핑)
    - INSERT ... SELECT ... ON CONFLICT 등 복잡 구문
    """

    def __init__(self, dialect: str = "postgres") -> None:
        self.dialect = dialect

    def is_available(self) -> bool:
        return HAS_SQLGLOT

    def extract_from_sql(
        self,
        sql: str,
        source_file: str = "",
    ) -> LineageGraph:
        """단일 SQL 텍스트에서 정밀 리니지 추출"""
        if not HAS_SQLGLOT:
            logger.warning("sqlglot 미설치 — 정규식 폴백 필요")
            return LineageGraph()

        graph = LineageGraph(source_files=[source_file] if source_file else [])

        try:
            statements = sqlglot.parse(sql, dialect=self.dialect, error_level=sqlglot.ErrorLevel.WARN)
        except Exception as e:
            graph.errors.append(f"SQLGlot 파싱 실패: {str(e)[:200]}")
            return graph

        for stmt in statements:
            if stmt is None:
                continue
            try:
                self._process_statement(stmt, source_file, graph)
            except Exception as e:
                graph.errors.append(f"구문 처리 오류: {str(e)[:200]}")

        # 중복 노드 병합
        self._merge_nodes(graph)
        return graph

    def _process_statement(
        self,
        stmt: Any,
        source_file: str,
        graph: LineageGraph,
    ) -> None:
        """AST 노드 타입별 리니지 추출"""
        # INSERT INTO ... SELECT
        if isinstance(stmt, sqlglot_exp.Insert):
            self._process_insert(stmt, source_file, graph)

        # CREATE TABLE ... AS SELECT
        elif isinstance(stmt, sqlglot_exp.Create):
            self._process_create_as(stmt, source_file, graph)

        # 독립 SELECT (CTE 포함)
        elif isinstance(stmt, sqlglot_exp.Select):
            self._process_select(stmt, source_file, graph, sink_node=None)

    def _process_insert(
        self,
        stmt: Any,
        source_file: str,
        graph: LineageGraph,
    ) -> None:
        """INSERT INTO target SELECT ... FROM sources"""
        # 싱크 테이블
        table_expr = stmt.find(sqlglot_exp.Table)
        if not table_expr:
            return
        sink_name = self._table_name(table_expr)
        if not sink_name or sink_name.lower() in _SYSTEM_TABLES:
            return

        sink_node = LineageNode(
            node_type=LineageNodeType.SINK,
            name=sink_name,
            schema_name=self._schema_name(table_expr),
            source_file=source_file,
        )
        graph.nodes.append(sink_node)

        # SELECT 부분에서 소스 추출
        select = stmt.find(sqlglot_exp.Select)
        if select:
            self._process_select(select, source_file, graph, sink_node=sink_node)

    def _process_create_as(
        self,
        stmt: Any,
        source_file: str,
        graph: LineageGraph,
    ) -> None:
        """CREATE TABLE ... AS SELECT"""
        # CTAS인지 확인
        select = stmt.find(sqlglot_exp.Select)
        if not select:
            return

        # 대상 테이블
        table_expr = stmt.find(sqlglot_exp.Table)
        if not table_expr:
            return
        sink_name = self._table_name(table_expr)
        if not sink_name:
            return

        sink_node = LineageNode(
            node_type=LineageNodeType.SINK,
            name=sink_name,
            schema_name=self._schema_name(table_expr),
            source_file=source_file,
        )
        graph.nodes.append(sink_node)
        self._process_select(select, source_file, graph, sink_node=sink_node)

    def _process_select(
        self,
        select: Any,
        source_file: str,
        graph: LineageGraph,
        sink_node: LineageNode | None = None,
    ) -> None:
        """SELECT 문에서 소스 테이블 추출 + 엣지 생성"""
        # CTE 추출
        cte_names: set[str] = set()
        for cte in select.find_all(sqlglot_exp.CTE):
            cte_alias = cte.alias
            if cte_alias:
                cte_names.add(cte_alias)
                cte_node = LineageNode(
                    node_type=LineageNodeType.CTE,
                    name=cte_alias,
                    source_file=source_file,
                )
                graph.nodes.append(cte_node)

                # CTE 내부 SELECT에서 소스 추출 → CTE 노드로 연결
                inner_select = cte.find(sqlglot_exp.Select)
                if inner_select:
                    inner_sources = self._extract_table_refs(inner_select)
                    for src_name, src_schema in inner_sources:
                        if src_name.lower() not in _SYSTEM_TABLES and src_name not in cte_names:
                            src_node = LineageNode(
                                node_type=LineageNodeType.SOURCE,
                                name=src_name,
                                schema_name=src_schema,
                                source_file=source_file,
                            )
                            graph.nodes.append(src_node)
                            graph.edges.append(LineageEdge(
                                source_node_id=src_node.node_id,
                                target_node_id=cte_node.node_id,
                                description=f"{src_name}→CTE:{cte_alias}",
                            ))

        # 메인 SELECT에서 소스 테이블 추출
        sources = self._extract_table_refs(select)
        for src_name, src_schema in sources:
            if src_name.lower() in _SYSTEM_TABLES:
                continue

            # CTE 참조면 CTE 노드 연결
            if src_name in cte_names:
                if sink_node:
                    # CTE → sink 엣지
                    cte_match = next(
                        (n for n in graph.nodes if n.node_type == LineageNodeType.CTE and n.name == src_name),
                        None,
                    )
                    if cte_match:
                        graph.edges.append(LineageEdge(
                            source_node_id=cte_match.node_id,
                            target_node_id=sink_node.node_id,
                            description=f"CTE:{src_name}→{sink_node.name}",
                        ))
                continue

            src_node = LineageNode(
                node_type=LineageNodeType.SOURCE,
                name=src_name,
                schema_name=src_schema,
                source_file=source_file,
            )
            graph.nodes.append(src_node)

            if sink_node:
                graph.edges.append(LineageEdge(
                    source_node_id=src_node.node_id,
                    target_node_id=sink_node.node_id,
                    description=f"{src_name}→{sink_node.name}",
                ))

        # G13: 컬럼 수준 리니지 추출
        self._extract_column_lineage(
            select, source_file, graph,
            sink_name=sink_node.name if sink_node else "",
        )

    def _extract_column_lineage(
        self,
        select: Any,
        source_file: str,
        graph: LineageGraph,
        sink_name: str = "",
    ) -> None:
        """G13: SELECT 표현식에서 컬럼 수준 리니지 추출.

        각 SELECT 항목을 AST 순회하여 소스 테이블.컬럼 → 타겟 컬럼 매핑을 생성한다.
        """
        if not HAS_SQLGLOT:
            return

        # 테이블 별칭 → 실제 이름 매핑
        alias_map = self._build_alias_map(select)

        # SELECT 표현식 순회
        expressions = select.args.get("expressions") or []
        for i, expr in enumerate(expressions):
            try:
                self._trace_column_expr(
                    expr, alias_map, sink_name, source_file, graph, i,
                )
            except Exception as e:
                logger.debug("컬럼 리니지 추적 실패 (expr %d): %s", i, e)

    def _build_alias_map(self, select: Any) -> dict[str, str]:
        """FROM/JOIN 절의 테이블 별칭 → 실제 이름 매핑"""
        alias_map: dict[str, str] = {}
        if not HAS_SQLGLOT:
            return alias_map
        for table in select.find_all(sqlglot_exp.Table):
            name = self._table_name(table)
            alias = table.alias
            if alias and name:
                alias_map[alias] = name
            elif name:
                alias_map[name] = name
        return alias_map

    def _trace_column_expr(
        self,
        expr: Any,
        alias_map: dict[str, str],
        sink_name: str,
        source_file: str,
        graph: LineageGraph,
        position: int,
    ) -> None:
        """개별 SELECT 표현식에서 소스 컬럼 추적"""
        # 타겟 컬럼명 (alias 또는 원본)
        target_col = ""
        if hasattr(expr, "alias") and expr.alias:
            target_col = expr.alias
        elif isinstance(expr, sqlglot_exp.Column):
            target_col = expr.name
        else:
            target_col = f"col_{position}"

        # SELECT * 처리
        if isinstance(expr, sqlglot_exp.Star):
            # 모든 테이블의 모든 컬럼 (스키마 모름 → LOW 신뢰도)
            for alias, real_name in alias_map.items():
                if real_name.lower() not in _SYSTEM_TABLES:
                    graph.column_lineages.append(ColumnLineage(
                        source_table=real_name,
                        source_column="*",
                        target_table=sink_name,
                        target_column="*",
                        confidence=ColumnLineageConfidence.LOW,
                        source_file=source_file,
                    ))
            return

        # AST에서 모든 Column 참조 추출
        col_refs = list(expr.find_all(sqlglot_exp.Column)) if hasattr(expr, "find_all") else []

        if not col_refs:
            return

        # 표현식 타입에 따라 신뢰도 결정
        is_simple = isinstance(expr, sqlglot_exp.Column)  # 단순 참조
        is_aliased = hasattr(expr, "alias") and expr.alias
        has_func = bool(list(expr.find_all(sqlglot_exp.Func))) if hasattr(expr, "find_all") else False
        transform_expr = ""

        if has_func:
            # 함수 포함 → 변환식 기록
            confidence = ColumnLineageConfidence.MEDIUM
            try:
                transform_expr = expr.sql(dialect=self.dialect)[:200]
            except Exception:
                transform_expr = "expression"
        elif is_simple:
            confidence = ColumnLineageConfidence.HIGH
        else:
            confidence = ColumnLineageConfidence.MEDIUM

        for col_ref in col_refs:
            source_col = col_ref.name
            # 테이블 참조 해석
            table_ref = col_ref.args.get("table")
            if table_ref and hasattr(table_ref, "name"):
                source_table = alias_map.get(table_ref.name, table_ref.name)
            elif len(alias_map) == 1:
                # 테이블이 하나뿐이면 자동 매핑
                source_table = next(iter(alias_map.values()))
            else:
                source_table = "unknown"

            if source_table.lower() in _SYSTEM_TABLES:
                continue

            graph.column_lineages.append(ColumnLineage(
                source_table=source_table,
                source_column=source_col,
                target_table=sink_name,
                target_column=target_col,
                transform_expression=transform_expr,
                confidence=confidence,
                source_file=source_file,
            ))

    def _extract_table_refs(self, node: Any) -> list[tuple[str, str]]:
        """AST 노드에서 모든 테이블 참조 추출 → [(table_name, schema)]"""
        refs: list[tuple[str, str]] = []
        seen: set[str] = set()

        for table in node.find_all(sqlglot_exp.Table):
            name = self._table_name(table)
            schema = self._schema_name(table)
            if name and name.lower() not in seen:
                seen.add(name.lower())
                refs.append((name, schema))

        return refs

    def _table_name(self, table_expr: Any) -> str:
        """테이블 AST 노드에서 이름 추출"""
        return table_expr.name if hasattr(table_expr, 'name') else ""

    def _schema_name(self, table_expr: Any) -> str:
        """테이블 AST 노드에서 스키마명 추출"""
        db = table_expr.args.get("db")
        if db and hasattr(db, 'name'):
            return db.name
        return ""

    def _merge_nodes(self, graph: LineageGraph) -> None:
        """중복 노드 병합 + 엣지 dedup"""
        canonical: dict[str, str] = {}
        removed: set[str] = set()

        for node in graph.nodes:
            key = f"{node.node_type.value}:{node.schema_name}.{node.name}".lower()
            if key in canonical:
                old_id = node.node_id
                new_id = canonical[key]
                removed.add(old_id)
                for edge in graph.edges:
                    if edge.source_node_id == old_id:
                        edge.source_node_id = new_id
                    if edge.target_node_id == old_id:
                        edge.target_node_id = new_id
            else:
                canonical[key] = node.node_id

        graph.nodes = [n for n in graph.nodes if n.node_id not in removed]

        # 엣지 dedup
        seen: set[tuple[str, str]] = set()
        deduped = []
        for edge in graph.edges:
            key = (edge.source_node_id, edge.target_node_id)
            if key not in seen:
                seen.add(key)
                deduped.append(edge)
        graph.edges = deduped


# 모듈 수준 인스턴스
sqlglot_extractor = SQLGlotLineageExtractor()
