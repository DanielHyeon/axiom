"""서브스키마 컨텍스트 모듈 (#7 P1-1).

LLM에 전체 DDL 대신 관련 테이블/컬럼만 축소하여 전달한다.
토큰 효율을 높이고 SQL 생성 정확도를 개선한다.

사용 흐름:
1. 검색 결과에서 SubSchemaContext 구성
2. build_sub_schema_ddl()로 DDL 문자열 생성
3. LLM 프롬프트에 주입
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RelevantColumn:
    """검색으로 선별된 관련 컬럼."""
    name: str                    # 컬럼 이름
    data_type: str = "VARCHAR"   # 데이터 타입
    description: str = ""        # 컬럼 설명 (있으면 주석으로 표시)
    score: float = 0.0           # 검색 관련도 점수
    is_key: bool = False         # PK 여부


@dataclass
class RelevantTable:
    """검색으로 선별된 관련 테이블 (서브스키마 단위)."""
    name: str                    # 테이블 이름
    schema: str = ""             # 스키마 이름 (예: public)
    description: str = ""        # 테이블 설명
    columns: list[RelevantColumn] = field(default_factory=list)
    score: float = 0.0           # 검색 관련도 점수


@dataclass
class SubSchemaContext:
    """LLM에 전달할 축소된 스키마 컨텍스트.

    전체 스키마가 아닌, 질문과 관련된 테이블/컬럼만 포함한다.
    """
    tables: list[RelevantTable] = field(default_factory=list)
    fk_relationships: list[dict] = field(default_factory=list)
    value_mappings: list[dict] = field(default_factory=list)
    similar_queries: list[dict] = field(default_factory=list)
    enum_hints: list[dict] = field(default_factory=list)  # #8 enum cache와 연동


def build_sub_schema_ddl(ctx: SubSchemaContext) -> str:
    """서브스키마 컨텍스트를 DDL 형식 문자열로 변환한다.

    LLM 프롬프트에 들어갈 CREATE TABLE + FK + Enum 힌트 + 값 매핑 + 유사 쿼리를
    하나의 텍스트 블록으로 조립한다.

    Args:
        ctx: 축소된 스키마 컨텍스트

    Returns:
        DDL 형식의 문자열 (예: CREATE TABLE sales (...); ...)
    """
    lines: list[str] = []

    # ── 테이블 DDL 생성 ──
    for t in ctx.tables:
        col_defs: list[str] = []
        for c in t.columns:
            # 타입 문자열 조립
            type_str = c.data_type or "VARCHAR"
            pk = " PRIMARY KEY" if c.is_key else ""
            desc = f"  -- {c.description}" if c.description else ""
            col_defs.append(f"  {c.name} {type_str}{pk}{desc}")

        # 테이블 이름에 스키마 접두사 붙이기 (있으면)
        table_name = f"{t.schema}.{t.name}" if t.schema else t.name
        table_desc = f"  -- {t.description}" if t.description else ""

        if col_defs:
            cols = ",\n".join(col_defs)
            lines.append(f"CREATE TABLE {table_name} ({table_desc}\n{cols}\n);")
        else:
            # 컬럼 정보가 없는 경우 (드물지만 방어)
            lines.append(f"CREATE TABLE {table_name} ();{table_desc}")

    ddl = "\n\n".join(lines)

    # ── FK 관계 (선택된 테이블 간) ──
    if ctx.fk_relationships:
        fk_lines: list[str] = []
        for fk in ctx.fk_relationships[:20]:
            fk_lines.append(
                f"  {fk.get('from_table', '')}.{fk.get('from_column', '')} "
                f"-> {fk.get('to_table', '')}.{fk.get('to_column', '')}"
            )
        ddl += "\n\n-- Foreign Key Relationships:\n" + "\n".join(fk_lines)

    # ── Enum 힌트 (#8과 연동) ──
    if ctx.enum_hints:
        hint_lines: list[str] = []
        for h in ctx.enum_hints[:30]:
            # 최대 10개 값만 표시
            values_str = ", ".join(
                [f"'{v}'" for v in h.get("values", [])[:10]]
            )
            hint_lines.append(
                f"  {h.get('table', '')}.{h.get('column', '')}: [{values_str}]"
            )
        ddl += "\n\n-- Known Column Values (enum hints):\n" + "\n".join(hint_lines)

    # ── 값 매핑 (자연어 → DB 값) ──
    if ctx.value_mappings:
        vm_lines: list[str] = []
        for vm in ctx.value_mappings[:10]:
            vm_lines.append(
                f"  '{vm.get('natural_language', '')}' -> "
                f"'{vm.get('db_value', '')}' "
                f"({vm.get('table', '')}.{vm.get('column', '')})"
            )
        ddl += "\n\n-- Value Mappings (natural language -> DB value):\n" + "\n".join(vm_lines)

    # ── 유사 캐시 쿼리 (참고용) ──
    if ctx.similar_queries:
        sq_lines: list[str] = []
        for sq in ctx.similar_queries[:3]:
            q_text = sq.get("question", "")[:100]
            s_text = sq.get("sql", "")[:200]
            sq_lines.append(f"  Q: {q_text}\n  SQL: {s_text}")
        ddl += "\n\n-- Similar Cached Queries:\n" + "\n\n".join(sq_lines)

    return ddl
