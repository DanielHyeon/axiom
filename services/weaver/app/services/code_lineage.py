"""G13: 코드 리니지 추출기 — SQL/ETL 코드에서 데이터 흐름 DAG 생성.

SQL 파일에서 테이블 참조를 추출하고 source → transform → sink 리니지를 구성한다.
정규식 기반 MVP — Phase 3에서 SQLGlot AST 또는 ANTLR 정밀 파싱으로 교체 가능.

지원 구문:
- SELECT ... FROM ... JOIN ... (소스 테이블 추출)
- INSERT INTO ... SELECT ... (싱크 + 소스 추출)
- CREATE TABLE ... AS SELECT ... (CTAS)
- WITH cte AS (...) SELECT ... (CTE 추출)
- 서브쿼리의 FROM 절 테이블
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from app.services.parsers.sqlglot_lineage import sqlglot_extractor
from app.services.parsers.lineage_models import (
    ColumnLineage,
    ColumnLineageConfidence,
    LineageEdge,
    LineageEdgeType,
    LineageGraph,
    LineageNode,
    LineageNodeType,
)

logger = logging.getLogger("axiom.weaver.code_lineage")

# 파일 읽기 최대 크기
_MAX_FILE_READ = 1024 * 1024

# ── SQL 패턴 ── #

# FROM/JOIN 절 테이블 추출 (schema.table 또는 table AS alias)
_FROM_TABLE = re.compile(
    r'\b(?:FROM|JOIN)\s+(?:LATERAL\s+)?'
    r'("?[A-Za-z_]\w*"?(?:\."?[A-Za-z_]\w*"?)?)'
    r'(?:\s+(?:AS\s+)?([A-Za-z_]\w*))?',
    re.IGNORECASE,
)

# INSERT INTO table
_INSERT_INTO = re.compile(
    r'\bINSERT\s+INTO\s+("?[A-Za-z_]\w*"?(?:\."?[A-Za-z_]\w*"?)?)',
    re.IGNORECASE,
)

# CREATE TABLE ... AS SELECT
_CTAS = re.compile(
    r'\bCREATE\s+(?:OR\s+REPLACE\s+)?(?:TEMP(?:ORARY)?\s+)?TABLE\s+'
    r'("?[A-Za-z_]\w*"?(?:\."?[A-Za-z_]\w*"?)?)\s+AS\b',
    re.IGNORECASE,
)

# WITH cte_name AS (...)
_CTE = re.compile(
    r'\bWITH\s+(?:RECURSIVE\s+)?'
    r'([A-Za-z_]\w*)\s+AS\s*\(',
    re.IGNORECASE,
)

# 추가 CTE (,cte2 AS (...))
_CTE_ADDITIONAL = re.compile(
    r',\s*([A-Za-z_]\w*)\s+AS\s*\(',
    re.IGNORECASE,
)

# G13: INSERT INTO t(col1, col2) 컬럼 리스트 추출
_INSERT_COLS = re.compile(
    r'\bINSERT\s+INTO\s+\S+\s*\(([^)]+)\)',
    re.IGNORECASE,
)

# G13: SELECT 절 컬럼 추출 (FROM 앞까지)
_SELECT_COLS = re.compile(
    r'\bSELECT\s+(.*?)\bFROM\b',
    re.IGNORECASE | re.DOTALL,
)

# 집계/변환 함수 감지
_AGGREGATE_FUNCS = re.compile(
    r'\b(COUNT|SUM|AVG|MIN|MAX|GROUP_CONCAT|STRING_AGG|ARRAY_AGG|'
    r'ROW_NUMBER|RANK|DENSE_RANK|LAG|LEAD|NTILE|'
    r'CASE\s+WHEN|COALESCE|NULLIF|CAST)\b',
    re.IGNORECASE,
)

# 시스템/내장 테이블 제외
_SYSTEM_TABLES = {
    "dual", "information_schema", "pg_catalog", "sys", "system",
    "generate_series", "unnest", "lateral",
}


def _unquote(name: str) -> str:
    """Quoted identifier 제거"""
    return name.strip().strip('"')


def _split_qualified(name: str) -> tuple[str, str]:
    """schema.table → (schema, table)"""
    parts = name.split(".")
    if len(parts) >= 2:
        return _unquote(parts[0]), _unquote(parts[1])
    return "", _unquote(parts[0])


def _is_system_table(name: str) -> bool:
    """시스템 테이블 여부"""
    return _unquote(name).lower() in _SYSTEM_TABLES


class CodeLineageExtractor:
    """SQL/ETL 코드에서 데이터 리니지 자동 추출.

    사용법:
        extractor = CodeLineageExtractor()
        graph = await extractor.extract_lineage(upload_id, sandbox_dir)
    """

    async def extract_lineage(
        self,
        upload_id: str,
        sandbox_dir: str,
    ) -> LineageGraph:
        """샌드박스 내 SQL 파일에서 리니지 DAG 생성"""
        base = Path(sandbox_dir)
        graph = LineageGraph(upload_id=upload_id)

        if not base.exists():
            graph.errors.append("샌드박스 미존재")
            return graph

        # SQL 파일 수집
        sql_files = [
            f for f in base.rglob("*")
            if f.is_file() and f.suffix.lower() in {".sql", ".ddl"}
        ]

        if not sql_files:
            graph.errors.append("SQL 파일을 찾을 수 없습니다")
            return graph

        for sql_file in sql_files[:500]:  # 최대 500 파일
            rel_path = str(sql_file.relative_to(base))
            graph.source_files.append(rel_path)

            try:
                content = sql_file.read_text(encoding="utf-8", errors="ignore")[:_MAX_FILE_READ]
                self._extract_from_sql(content, rel_path, upload_id, graph)
            except Exception as e:
                graph.errors.append(f"{rel_path}: {str(e)[:100]}")

        # 중복 노드 병합 (같은 테이블명)
        self._merge_duplicate_nodes(graph)

        logger.info(
            "리니지 추출 완료: upload_id=%s, nodes=%d, edges=%d, files=%d",
            upload_id, graph.node_count, graph.edge_count, len(graph.source_files),
        )
        return graph

    def _extract_from_sql(
        self,
        sql: str,
        rel_path: str,
        upload_id: str,
        graph: LineageGraph,
    ) -> None:
        """단일 SQL 텍스트에서 리니지 추출 — G13: SQLGlot 우선, 정규식 폴백"""
        # G13 고도화: SQLGlot AST 시도
        if sqlglot_extractor.is_available():
            try:
                ast_graph = sqlglot_extractor.extract_from_sql(sql, source_file=rel_path)
                if ast_graph.node_count > 0:
                    graph.nodes.extend(ast_graph.nodes)
                    graph.edges.extend(ast_graph.edges)
                    graph.column_lineages.extend(ast_graph.column_lineages)  # G13: 컬럼 리니지 전파
                    graph.errors.extend(ast_graph.errors)
                    return  # SQLGlot 성공 → 정규식 스킵
            except Exception as e:
                logger.debug("SQLGlot 폴백: %s — %s", rel_path, e)

        # 정규식 폴백 (기존 MVP)
        # 주석 제거
        cleaned = self._strip_comments(sql)

        # 구문 단위로 분리 (세미콜론)
        statements = [s.strip() for s in cleaned.split(";") if s.strip()]

        _MAX_STMT_SIZE = 100_000  # M1: 구문당 100KB 제한

        for stmt in statements[:5000]:  # M3: 파일당 최대 5000 구문
            if len(stmt) > _MAX_STMT_SIZE:
                graph.errors.append(f"{rel_path}: 구문 크기 초과 ({len(stmt)} bytes), 스킵")
                continue

            stmt_upper = stmt.upper().lstrip()

            if "INSERT INTO" in stmt_upper:
                self._extract_insert_lineage(stmt, rel_path, upload_id, graph)
            elif stmt_upper.startswith("CREATE") and re.search(r'\bAS\b', stmt_upper):
                # M1: re.DOTALL + .* ReDoS 방지 → 단순 문자열 체크 + \bAS\b 워드 경계
                self._extract_ctas_lineage(stmt, rel_path, upload_id, graph)
            elif stmt_upper.startswith("SELECT") or stmt_upper.startswith("WITH"):
                self._extract_select_sources(stmt, rel_path, graph)

    def _extract_insert_lineage(
        self,
        stmt: str,
        rel_path: str,
        upload_id: str,
        graph: LineageGraph,
    ) -> None:
        """INSERT INTO ... SELECT ... → 싱크 + 소스 + 엣지"""
        # 싱크 테이블
        sink_match = _INSERT_INTO.search(stmt)
        if not sink_match:
            return
        sink_schema, sink_table = _split_qualified(sink_match.group(1))
        if _is_system_table(sink_table):
            return

        sink_node = LineageNode(
            node_type=LineageNodeType.SINK,
            name=sink_table,
            schema_name=sink_schema,
            source_file=rel_path,
        )
        graph.nodes.append(sink_node)

        # G13: 정규식 기반 컬럼 리니지 (INSERT INTO t(c1,c2) SELECT a.c1, b.c2)
        self._extract_insert_column_lineage(stmt, sink_table, rel_path, graph)

        # CTE 추출
        cte_nodes = self._extract_ctes(stmt, rel_path, graph)

        # 소스 테이블
        # INSERT INTO 부분 이후의 SELECT에서 FROM 추출
        select_part = stmt[sink_match.end():]
        sources = self._extract_table_refs(select_part)

        has_transform = bool(_AGGREGATE_FUNCS.search(select_part))

        for src_name, src_alias in sources:
            src_schema, src_table = _split_qualified(src_name)
            if _is_system_table(src_table):
                continue

            # CTE 이름이면 CTE 노드 참조
            cte_node = cte_nodes.get(src_table.lower())
            if cte_node:
                graph.edges.append(LineageEdge(
                    edge_type=LineageEdgeType.FLOWS_TO,
                    source_node_id=cte_node.node_id,
                    target_node_id=sink_node.node_id,
                    description="CTE→sink",
                ))
                continue

            src_node = LineageNode(
                node_type=LineageNodeType.SOURCE,
                name=src_table,
                schema_name=src_schema,
                alias=src_alias,
                source_file=rel_path,
            )
            graph.nodes.append(src_node)

            if has_transform:
                # 변환 노드 삽입
                transform_node = LineageNode(
                    node_type=LineageNodeType.TRANSFORM,
                    name=f"transform_{sink_table}",
                    transform_logic="aggregate/function",
                    source_file=rel_path,
                )
                graph.nodes.append(transform_node)
                graph.edges.append(LineageEdge(
                    source_node_id=src_node.node_id,
                    target_node_id=transform_node.node_id,
                    description=f"{src_table}→transform",
                ))
                graph.edges.append(LineageEdge(
                    source_node_id=transform_node.node_id,
                    target_node_id=sink_node.node_id,
                    description=f"transform→{sink_table}",
                ))
            else:
                graph.edges.append(LineageEdge(
                    source_node_id=src_node.node_id,
                    target_node_id=sink_node.node_id,
                    description=f"{src_table}→{sink_table}",
                ))

    def _extract_ctas_lineage(
        self,
        stmt: str,
        rel_path: str,
        upload_id: str,
        graph: LineageGraph,
    ) -> None:
        """CREATE TABLE ... AS SELECT → CTAS 리니지"""
        ctas_match = _CTAS.search(stmt)
        if not ctas_match:
            return
        sink_schema, sink_table = _split_qualified(ctas_match.group(1))

        sink_node = LineageNode(
            node_type=LineageNodeType.SINK,
            name=sink_table,
            schema_name=sink_schema,
            source_file=rel_path,
        )
        graph.nodes.append(sink_node)

        # AS 이후 SELECT에서 소스 추출
        select_part = stmt[ctas_match.end():]
        sources = self._extract_table_refs(select_part)

        for src_name, src_alias in sources:
            src_schema, src_table = _split_qualified(src_name)
            if _is_system_table(src_table):
                continue

            src_node = LineageNode(
                node_type=LineageNodeType.SOURCE,
                name=src_table,
                schema_name=src_schema,
                alias=src_alias,
                source_file=rel_path,
            )
            graph.nodes.append(src_node)
            graph.edges.append(LineageEdge(
                source_node_id=src_node.node_id,
                target_node_id=sink_node.node_id,
                description=f"CTAS: {src_table}→{sink_table}",
            ))

    def _extract_select_sources(
        self,
        stmt: str,
        rel_path: str,
        graph: LineageGraph,
    ) -> None:
        """독립 SELECT — 소스 테이블만 추출"""
        sources = self._extract_table_refs(stmt)
        for src_name, src_alias in sources:
            src_schema, src_table = _split_qualified(src_name)
            if _is_system_table(src_table):
                continue
            src_node = LineageNode(
                node_type=LineageNodeType.SOURCE,
                name=src_table,
                schema_name=src_schema,
                alias=src_alias,
                source_file=rel_path,
            )
            graph.nodes.append(src_node)

    def _extract_ctes(
        self,
        stmt: str,
        rel_path: str,
        graph: LineageGraph,
    ) -> dict[str, LineageNode]:
        """WITH 절에서 CTE 이름 추출"""
        cte_nodes: dict[str, LineageNode] = {}

        for pattern in [_CTE, _CTE_ADDITIONAL]:
            for m in pattern.finditer(stmt):
                cte_name = m.group(1)
                node = LineageNode(
                    node_type=LineageNodeType.CTE,
                    name=cte_name,
                    source_file=rel_path,
                )
                graph.nodes.append(node)
                cte_nodes[cte_name.lower()] = node

        return cte_nodes

    def _extract_table_refs(self, sql: str) -> list[tuple[str, str]]:
        """FROM/JOIN 절에서 테이블 참조 추출 → [(table_name, alias)]"""
        refs = []
        seen = set()
        for m in _FROM_TABLE.finditer(sql):
            table_name = m.group(1)
            alias = m.group(2) or ""
            key = _unquote(table_name).lower()
            if key not in seen and not _is_system_table(key):
                refs.append((table_name, alias))
                seen.add(key)
        return refs

    def _merge_duplicate_nodes(self, graph: LineageGraph) -> None:
        """같은 테이블명의 중복 노드 병합 — 엣지 대상 ID 업데이트"""
        # 이름 → 첫 번째 노드 ID
        canonical: dict[str, str] = {}
        removed_ids: set[str] = set()

        for node in graph.nodes:
            key = f"{node.node_type.value}:{node.schema_name}.{node.name}".lower()
            if key in canonical:
                removed_ids.add(node.node_id)
                # 엣지의 참조 ID를 canonical로 교체
                old_id = node.node_id
                new_id = canonical[key]
                for edge in graph.edges:
                    if edge.source_node_id == old_id:
                        edge.source_node_id = new_id
                    if edge.target_node_id == old_id:
                        edge.target_node_id = new_id
            else:
                canonical[key] = node.node_id

        # 중복 노드 제거
        graph.nodes = [n for n in graph.nodes if n.node_id not in removed_ids]

        # M2: 엣지 중복 제거 (노드 병합 후 동일 source→target 엣지 발생)
        seen_edges: set[tuple[str, str, str]] = set()
        deduped: list[LineageEdge] = []
        for edge in graph.edges:
            edge_key = (edge.source_node_id, edge.target_node_id, edge.edge_type.value)
            if edge_key not in seen_edges:
                seen_edges.add(edge_key)
                deduped.append(edge)
        graph.edges = deduped

    def _extract_insert_column_lineage(
        self,
        stmt: str,
        sink_table: str,
        rel_path: str,
        graph: LineageGraph,
    ) -> None:
        """G13: INSERT INTO t(c1,c2) SELECT x.c1, y.c2 → 컬럼 매핑 추출 (정규식 폴백)"""
        # INSERT 컬럼 리스트 추출
        ins_match = _INSERT_COLS.search(stmt)
        if not ins_match:
            return
        target_cols = [c.strip() for c in ins_match.group(1).split(",") if c.strip()]

        # SELECT 컬럼 추출
        sel_match = _SELECT_COLS.search(stmt[ins_match.end():])
        if not sel_match:
            return
        select_raw = sel_match.group(1)
        # 간단한 쉼표 분리 (중첩 괄호 무시 — 정규식 MVP)
        select_exprs = [e.strip() for e in select_raw.split(",") if e.strip()]

        # 컬럼 1:1 매핑
        for i, (tgt_col, src_expr) in enumerate(zip(target_cols, select_exprs)):
            # 소스 표현식에서 테이블.컬럼 추출
            parts = src_expr.split(".")
            if len(parts) == 2:
                src_table = _unquote(parts[0].split()[-1])  # alias 또는 테이블명
                src_col = _unquote(parts[1].split()[0])      # AS 제거
            else:
                src_table = "unknown"
                src_col = _unquote(parts[-1].split()[0])

            # 함수 포함 여부로 신뢰도 결정
            has_func = bool(_AGGREGATE_FUNCS.search(src_expr))
            confidence = ColumnLineageConfidence.MEDIUM if has_func else ColumnLineageConfidence.HIGH

            graph.column_lineages.append(ColumnLineage(
                source_table=src_table,
                source_column=src_col,
                target_table=sink_table,
                target_column=_unquote(tgt_col),
                transform_expression=src_expr[:200] if has_func else "",
                confidence=confidence,
                source_file=rel_path,
            ))

    def _strip_comments(self, sql: str) -> str:
        """SQL 주석 제거"""
        sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
        sql = re.sub(r'--[^\n]*', '', sql)
        return sql
