"""G13: 코드 리니지 모델 — source → transform → sink 그래프.

SQL/ETL 코드에서 추출한 데이터 흐름을 DAG로 표현한다.
Neo4j에 :LineageNode / :FLOWS_TO 관계로 저장하거나 Mermaid 다이어그램으로 시각화한다.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class LineageNodeType(str, Enum):
    """리니지 노드 유형"""
    SOURCE = "source"           # 데이터 읽기 원천 (FROM 절)
    SINK = "sink"               # 데이터 쓰기 대상 (INSERT INTO, CREATE TABLE AS)
    TRANSFORM = "transform"     # 변환 로직 (함수, 집계, 조인, 서브쿼리)
    CTE = "cte"                 # Common Table Expression
    TEMP_TABLE = "temp_table"   # 임시 테이블


class LineageEdgeType(str, Enum):
    """리니지 엣지 유형"""
    FLOWS_TO = "flows_to"       # 데이터 흐름 (source→transform, transform→sink)
    DERIVED_FROM = "derived_from"  # 역방향 (sink가 source에서 파생)
    JOINED_WITH = "joined_with"    # 조인 관계


class ColumnLineageConfidence(str, Enum):
    """G13: 컬럼 리니지 신뢰도"""
    HIGH = "high"       # 직접 참조 (a.col1)
    MEDIUM = "medium"   # 표현식 내 참조 (SUM(a.col1))
    LOW = "low"         # SELECT * 또는 추론
    UNKNOWN = "unknown"


class ColumnLineage(BaseModel):
    """G13: 컬럼 수준 리니지 — 소스 컬럼 → 타겟 컬럼 매핑"""
    source_table: str
    source_column: str
    target_table: str = ""           # INSERT INTO 대상 (독립 SELECT면 빈 문자열)
    target_column: str = ""          # 타겟 컬럼 (alias 또는 원본 이름)
    transform_expression: str = ""   # 변환식 (SUM(...), CASE WHEN 등)
    confidence: ColumnLineageConfidence = ColumnLineageConfidence.HIGH
    source_file: str = ""


class LineageNode(BaseModel):
    """리니지 DAG 노드"""
    node_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    node_type: LineageNodeType
    name: str                           # 테이블명, CTE명, 함수명
    schema_name: str = ""
    alias: str = ""                     # SQL 별칭
    source_file: str = ""               # 출처 파일
    line_number: int = 0
    columns_referenced: list[str] = Field(default_factory=list)  # SELECT에서 참조한 컬럼
    transform_logic: str = ""           # 변환 SQL 조각 (집계, 함수 등)


class LineageEdge(BaseModel):
    """리니지 DAG 엣지"""
    edge_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    edge_type: LineageEdgeType = LineageEdgeType.FLOWS_TO
    source_node_id: str
    target_node_id: str
    columns_mapped: list[dict] = Field(default_factory=list)  # [{source_col, target_col}]
    description: str = ""


def _sanitize_mermaid_label(text: str) -> str:
    """Mermaid 라벨 XSS 방지 — 특수 문자 제거 + 길이 제한 (C1/C2 수정)"""
    sanitized = re.sub(r'[\n\r"\'|{}\[\]()]+', ' ', text)
    return sanitized[:120].strip() or "unnamed"


class LineageGraph(BaseModel):
    """리니지 DAG — 전체 그래프"""
    upload_id: str = ""
    nodes: list[LineageNode] = Field(default_factory=list)
    edges: list[LineageEdge] = Field(default_factory=list)
    column_lineages: list[ColumnLineage] = Field(default_factory=list)  # G13: 컬럼 수준 리니지
    source_files: list[str] = Field(default_factory=list)
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    errors: list[str] = Field(default_factory=list)

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    def to_mermaid(self) -> str:
        """Mermaid flowchart 문법으로 변환 — 프론트엔드 시각화용.

        C1/C2 수정: 모든 라벨을 _sanitize_mermaid_label()로 XSS 방지.
        """
        lines = ["graph LR"]
        id_map = {n.node_id: f"N{i}" for i, n in enumerate(self.nodes)}

        for node in self.nodes:
            mid = id_map[node.node_id]
            label = _sanitize_mermaid_label(node.name)
            if node.alias and node.alias != node.name:
                label = _sanitize_mermaid_label(f"{node.name} {node.alias}")

            if node.node_type == LineageNodeType.SOURCE:
                lines.append(f"    {mid}[({label})]")
            elif node.node_type == LineageNodeType.SINK:
                lines.append(f"    {mid}[/{label}/]")
            elif node.node_type == LineageNodeType.CTE:
                lines.append(f"    {mid}>{label}]")
            else:
                lines.append(f"    {mid}[{label}]")

        for edge in self.edges:
            src = id_map.get(edge.source_node_id, "?")
            tgt = id_map.get(edge.target_node_id, "?")
            label = _sanitize_mermaid_label(edge.description or edge.edge_type.value)
            lines.append(f"    {src} -->|{label}| {tgt}")

        return "\n".join(lines)

    def to_column_mermaid(self) -> str:
        """G13: 컬럼 수준 리니지를 Mermaid 다이어그램으로 변환.

        테이블 → 컬럼 → 타겟 컬럼 흐름을 표현한다.
        """
        if not self.column_lineages:
            return "graph LR\n    NO_COLUMN_LINEAGE[컬럼 리니지 없음]"

        lines = ["graph LR"]
        # 테이블별 컬럼 그룹화
        tables: dict[str, set[str]] = {}
        for cl in self.column_lineages:
            tables.setdefault(cl.source_table, set()).add(cl.source_column)
            if cl.target_table:
                tables.setdefault(cl.target_table, set()).add(cl.target_column)

        # 서브그래프 (테이블별)
        for i, (tbl, cols) in enumerate(tables.items()):
            safe_tbl = _sanitize_mermaid_label(tbl)
            lines.append(f"    subgraph T{i}[{safe_tbl}]")
            for col in sorted(cols):
                safe_col = _sanitize_mermaid_label(col)
                node_id = f"T{i}_{re.sub(r'[^a-zA-Z0-9]', '_', col)}"
                lines.append(f"        {node_id}[{safe_col}]")
            lines.append("    end")

        # 컬럼 간 엣지
        tbl_idx = {tbl: i for i, tbl in enumerate(tables)}
        for cl in self.column_lineages:
            if not cl.target_table:
                continue
            src_id = f"T{tbl_idx[cl.source_table]}_{re.sub(r'[^a-zA-Z0-9]', '_', cl.source_column)}"
            tgt_id = f"T{tbl_idx[cl.target_table]}_{re.sub(r'[^a-zA-Z0-9]', '_', cl.target_column)}"
            label = _sanitize_mermaid_label(cl.transform_expression or "direct")
            lines.append(f"    {src_id} -->|{label}| {tgt_id}")

        return "\n".join(lines)
