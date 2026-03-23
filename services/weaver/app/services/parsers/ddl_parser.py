"""G04: DDL 정적 파서 — CREATE TABLE / ALTER TABLE / COMMENT ON 구문 파싱.

KAIR ddl_static_parser.py 기반 포팅. 정규식 기반 파서로
PostgreSQL + Oracle + MySQL 구문을 지원한다.

지원 구문:
- CREATE TABLE [IF NOT EXISTS] [schema.]table (col_defs, constraints)
- COMMENT ON TABLE/COLUMN
- ALTER TABLE ADD PRIMARY KEY / FOREIGN KEY
- 인라인 FK/PK 제약조건
- Quoted identifiers ("SCHEMA"."TABLE")
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.services.parsers.ddl_models import (
    DDLParseResult,
    ParsedColumn,
    ParsedForeignKey,
    ParsedIndex,
    ParsedPrimaryKey,
    ParsedTable,
    ParsedView,
)

logger = logging.getLogger("axiom.weaver.parsers.ddl")


# ── 정규식 패턴 ── #

# 식별자: 일반 또는 quoted ("schema"."table")
_IDENT = r'(?:"[^"]+"|[A-Za-z_]\w*)'
_QUALIFIED_IDENT = rf'(?:{_IDENT}\.)?{_IDENT}'

# CREATE TABLE 매칭
_CREATE_TABLE = re.compile(
    rf'CREATE\s+TABLE\s+(IF\s+NOT\s+EXISTS\s+)?({_QUALIFIED_IDENT})\s*\('
    , re.IGNORECASE | re.DOTALL,
)

# COMMENT ON TABLE
_COMMENT_TABLE = re.compile(
    rf"COMMENT\s+ON\s+TABLE\s+({_QUALIFIED_IDENT})\s+IS\s+'([^']*)'",
    re.IGNORECASE,
)

# COMMENT ON COLUMN
_COMMENT_COLUMN = re.compile(
    rf"COMMENT\s+ON\s+COLUMN\s+({_QUALIFIED_IDENT})\.({_IDENT})\s+IS\s+'([^']*)'",
    re.IGNORECASE,
)

# ALTER TABLE ADD PRIMARY KEY
_ALTER_PK = re.compile(
    rf"ALTER\s+TABLE\s+({_QUALIFIED_IDENT})\s+ADD\s+(?:CONSTRAINT\s+{_IDENT}\s+)?PRIMARY\s+KEY\s*\(([^)]+)\)",
    re.IGNORECASE,
)

# ALTER TABLE ADD FOREIGN KEY
_ALTER_FK = re.compile(
    rf"ALTER\s+TABLE\s+({_QUALIFIED_IDENT})\s+ADD\s+(?:CONSTRAINT\s+({_IDENT})\s+)?"
    rf"FOREIGN\s+KEY\s*\(([^)]+)\)\s*REFERENCES\s+({_QUALIFIED_IDENT})\s*\(([^)]+)\)"
    rf"(?:\s+ON\s+DELETE\s+(\w+(?:\s+\w+)?))?(?:\s+ON\s+UPDATE\s+(\w+(?:\s+\w+)?))?",
    re.IGNORECASE,
)

# 인라인 컬럼 정의 (CREATE TABLE 내부)
_COLUMN_DEF = re.compile(
    rf'^\s*({_IDENT})\s+(\w[\w\s(),.]*?)(?:\s+(NOT\s+NULL|NULL))?'
    rf'(?:\s+DEFAULT\s+(.+?))?'
    rf'(?:\s+PRIMARY\s+KEY)?'
    rf'(?:\s+REFERENCES\s+({_QUALIFIED_IDENT})\s*\(({_IDENT})\))?'
    r'\s*$',
    re.IGNORECASE,
)

# 인라인 PK 제약조건
_INLINE_PK = re.compile(
    rf'^\s*(?:CONSTRAINT\s+{_IDENT}\s+)?PRIMARY\s+KEY\s*\(([^)]+)\)\s*$',
    re.IGNORECASE,
)

# 인라인 FK 제약조건
_INLINE_FK = re.compile(
    rf'^\s*(?:CONSTRAINT\s+({_IDENT})\s+)?FOREIGN\s+KEY\s*\(([^)]+)\)\s*'
    rf'REFERENCES\s+({_QUALIFIED_IDENT})\s*\(([^)]+)\)'
    rf'(?:\s+ON\s+DELETE\s+(\w+(?:\s+\w+)?))?'
    rf'(?:\s+ON\s+UPDATE\s+(\w+(?:\s+\w+)?))?',
    re.IGNORECASE,
)

# ── G01b: 방언 확장 정규식 ── #

# 대괄호 식별자 (T-SQL): [schema].[table]
_BRACKET_IDENT = r'(?:\[[^\]]+\]|"[^"]+"|[A-Za-z_]\w*)'
_BRACKET_QUALIFIED = rf'(?:{_BRACKET_IDENT}\.)?{_BRACKET_IDENT}'

# 백틱 식별자 (MySQL): `schema`.`table`
_BACKTICK_IDENT = r'(?:`[^`]+`|"[^"]+"|[A-Za-z_]\w*)'

# CREATE [MATERIALIZED] VIEW
_CREATE_VIEW = re.compile(
    rf'CREATE\s+(?:OR\s+REPLACE\s+)?(MATERIALIZED\s+)?VIEW\s+({_QUALIFIED_IDENT})\s+AS\s+',
    re.IGNORECASE | re.DOTALL,
)

# FROM/JOIN 절 테이블 참조 (뷰 소스 추출용)
_FROM_TABLE_SIMPLE = re.compile(
    r'\b(?:FROM|JOIN)\s+(?:LATERAL\s+)?("?[A-Za-z_]\w*"?(?:\."?[A-Za-z_]\w*"?)?)',
    re.IGNORECASE,
)

# CREATE [UNIQUE] INDEX ... ON table (cols) [INCLUDE (cols)]
_CREATE_INDEX = re.compile(
    rf'CREATE\s+(UNIQUE\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?({_QUALIFIED_IDENT})\s+'
    rf'ON\s+({_QUALIFIED_IDENT})\s*\(([^)]+)\)',
    re.IGNORECASE,
)

# INCLUDE (col1, col2) — 커버링 인덱스
_INDEX_INCLUDE = re.compile(
    r'\bINCLUDE\s*\(([^)]+)\)', re.IGNORECASE,
)


def _unquote(ident: str) -> str:
    """Quoted identifier에서 따옴표 제거"""
    s = ident.strip()
    if s.startswith('"') and s.endswith('"'):
        return s[1:-1]
    return s


def _split_qualified(name: str) -> tuple[str, str]:
    """'schema.table' 또는 '"SCHEMA"."TABLE"' → (schema, table)"""
    name = name.strip()
    # quoted 식별자 분리
    parts = re.findall(r'"[^"]+"|[A-Za-z_]\w*', name)
    if len(parts) >= 2:
        return _unquote(parts[0]), _unquote(parts[1])
    return "", _unquote(parts[0]) if parts else ""


def _split_column_list(cols_str: str) -> list[str]:
    """'col1, col2, col3' → ['col1', 'col2', 'col3']"""
    return [_unquote(c.strip()) for c in cols_str.split(",") if c.strip()]


def _extract_body(ddl: str, start_pos: int) -> str:
    """CREATE TABLE (...) 에서 괄호 내부 본문 추출 (중첩 괄호 처리)"""
    depth = 0
    body_start = None
    for i in range(start_pos, len(ddl)):
        if ddl[i] == '(':
            if depth == 0:
                body_start = i + 1
            depth += 1
        elif ddl[i] == ')':
            depth -= 1
            if depth == 0 and body_start is not None:
                return ddl[body_start:i]
    return ""


def _parse_column_defs(body: str) -> tuple[list[ParsedColumn], ParsedPrimaryKey | None, list[ParsedForeignKey]]:
    """CREATE TABLE 본문에서 컬럼 정의 + 인라인 제약조건 파싱"""
    columns: list[ParsedColumn] = []
    pk: ParsedPrimaryKey | None = None
    fks: list[ParsedForeignKey] = []

    # 줄 단위로 분리 (쉼표 기준, 괄호 내부 쉼표는 무시)
    lines = _smart_split(body)

    for line in lines:
        line = line.strip().rstrip(",")
        if not line:
            continue

        # 인라인 PK
        m = _INLINE_PK.match(line)
        if m:
            pk = ParsedPrimaryKey(columns=_split_column_list(m.group(1)))
            continue

        # 인라인 FK
        m = _INLINE_FK.match(line)
        if m:
            target_schema, target_table = _split_qualified(m.group(3))
            fks.append(ParsedForeignKey(
                constraint_name=_unquote(m.group(1)) if m.group(1) else "",
                source_columns=_split_column_list(m.group(2)),
                target_schema=target_schema,
                target_table=target_table,
                target_columns=_split_column_list(m.group(4)),
                on_delete=(m.group(5) or "").strip(),
                on_update=(m.group(6) or "").strip(),
            ))
            continue

        # 일반 컬럼 정의
        m = _COLUMN_DEF.match(line)
        if m:
            col_name = _unquote(m.group(1))
            data_type = m.group(2).strip()
            nullable_str = (m.group(3) or "").strip().upper()
            default_val = (m.group(4) or "").strip() or None
            is_pk = bool(re.search(r'\bPRIMARY\s+KEY\b', line, re.IGNORECASE))

            nullable = nullable_str != "NOT NULL"
            if is_pk:
                nullable = False

            col = ParsedColumn(
                name=col_name,
                data_type=data_type,
                nullable=nullable,
                is_primary_key=is_pk,
                default_value=default_val,
            )
            columns.append(col)

            # 인라인 FK 참조 (REFERENCES table(col))
            if m.group(5):
                ref_schema, ref_table = _split_qualified(m.group(5))
                ref_col = _unquote(m.group(6)) if m.group(6) else ""
                fks.append(ParsedForeignKey(
                    source_columns=[col_name],
                    target_schema=ref_schema,
                    target_table=ref_table,
                    target_columns=[ref_col] if ref_col else [],
                ))

            if is_pk and pk is None:
                pk = ParsedPrimaryKey(columns=[col_name])
            elif is_pk and pk is not None:
                pk.columns.append(col_name)

    # PK에 해당하는 컬럼 is_primary_key 업데이트
    if pk:
        pk_cols = set(pk.columns)
        for col in columns:
            if col.name in pk_cols:
                col.is_primary_key = True
                col.nullable = False

    return columns, pk, fks


def _smart_split(body: str) -> list[str]:
    """괄호 내부 쉼표를 무시하고 최상위 쉼표로 분리"""
    lines = []
    depth = 0
    current = []
    for ch in body:
        if ch == '(':
            depth += 1
            current.append(ch)
        elif ch == ')':
            depth -= 1
            current.append(ch)
        elif ch == ',' and depth == 0:
            lines.append(''.join(current))
            current = []
        else:
            current.append(ch)
    if current:
        lines.append(''.join(current))
    return lines


# ── 메인 파서 ── #

class DDLParser:
    """DDL 정적 파서 — CREATE TABLE / ALTER TABLE / COMMENT ON.

    사용법:
        parser = DDLParser(dialect="postgresql")
        result = parser.parse(ddl_text, source_file="schema.sql")
    """

    def __init__(self, dialect: str = "postgresql") -> None:
        self.dialect = dialect

    def parse(self, ddl_text: str, source_file: str = "") -> DDLParseResult:
        """전체 DDL 텍스트 파싱 → DDLParseResult"""
        result = DDLParseResult(source_file=source_file, dialect=self.dialect)

        # 주석 제거
        cleaned = self._strip_comments(ddl_text)

        # 1. CREATE TABLE 파싱
        self._parse_create_tables(cleaned, result)

        # 2. ALTER TABLE ADD PK/FK 파싱
        self._parse_alter_tables(cleaned, result)

        # 3. COMMENT ON TABLE/COLUMN 파싱
        self._parse_comments(cleaned, result)

        # G01b: 뷰 + 독립 인덱스 + 방언별 후처리
        self._parse_views(cleaned, result)
        self._parse_indexes(cleaned, result)
        self._parse_dialect_specific(cleaned, result)

        logger.info(
            "DDL 파싱 완료: %s (tables=%d, views=%d, errors=%d)",
            source_file, result.table_count, result.view_count, result.error_count,
        )
        return result

    def parse_file(self, file_path: str, max_size: int = 10 * 1024 * 1024) -> DDLParseResult:
        """파일에서 DDL 파싱 (M5: 최대 10MB 제한)"""
        from pathlib import Path
        p = Path(file_path)
        if not p.exists() or not p.is_file():
            return DDLParseResult(errors=[f"파일 미존재: {file_path}"], source_file=file_path)
        if p.stat().st_size > max_size:
            return DDLParseResult(errors=[f"파일 크기 초과: {p.stat().st_size} bytes"], source_file=file_path)
        content = p.read_text(encoding="utf-8", errors="ignore")
        return self.parse(content, source_file=file_path)

    # ── 내부 메서드 ── #

    def _strip_comments(self, sql: str) -> str:
        """SQL 주석 제거 (-- 한 줄, /* */ 블록)"""
        # 블록 주석 제거
        sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
        # 한 줄 주석 제거
        sql = re.sub(r'--[^\n]*', '', sql)
        return sql

    def _parse_create_tables(self, ddl: str, result: DDLParseResult) -> None:
        """CREATE TABLE 구문 파싱"""
        for match in _CREATE_TABLE.finditer(ddl):
            try:
                if_not_exists = bool(match.group(1))
                schema_name, table_name = _split_qualified(match.group(2))

                # 괄호 내부 본문 추출
                body = _extract_body(ddl, match.start())
                if not body:
                    result.errors.append(f"CREATE TABLE 본문 추출 실패: {match.group(2)}")
                    continue

                columns, pk, fks = _parse_column_defs(body)

                table = ParsedTable(
                    schema_name=schema_name,
                    table_name=table_name,
                    columns=columns,
                    primary_key=pk,
                    foreign_keys=fks,
                    if_not_exists=if_not_exists,
                )
                result.tables.append(table)

            except Exception as e:
                result.errors.append(f"CREATE TABLE 파싱 오류 ({match.group(2)}): {e}")

    def _parse_alter_tables(self, ddl: str, result: DDLParseResult) -> None:
        """ALTER TABLE ADD PK/FK 파싱 → 기존 테이블에 병합"""
        table_map = {
            (t.schema_name, t.table_name): t for t in result.tables
        }

        # ALTER TABLE ADD PRIMARY KEY
        for match in _ALTER_PK.finditer(ddl):
            schema, table_name = _split_qualified(match.group(1))
            pk_cols = _split_column_list(match.group(2))
            table = table_map.get((schema, table_name))
            if table:
                table.primary_key = ParsedPrimaryKey(columns=pk_cols)
                for col in table.columns:
                    if col.name in pk_cols:
                        col.is_primary_key = True
                        col.nullable = False

        # ALTER TABLE ADD FOREIGN KEY
        for match in _ALTER_FK.finditer(ddl):
            schema, table_name = _split_qualified(match.group(1))
            constraint_name = _unquote(match.group(2)) if match.group(2) else ""
            source_cols = _split_column_list(match.group(3))
            target_schema, target_table = _split_qualified(match.group(4))
            target_cols = _split_column_list(match.group(5))

            table = table_map.get((schema, table_name))
            if table:
                table.foreign_keys.append(ParsedForeignKey(
                    constraint_name=constraint_name,
                    source_columns=source_cols,
                    target_schema=target_schema,
                    target_table=target_table,
                    target_columns=target_cols,
                    on_delete=(match.group(6) or "").strip(),
                    on_update=(match.group(7) or "").strip(),
                ))

    def _parse_comments(self, ddl: str, result: DDLParseResult) -> None:
        """COMMENT ON TABLE/COLUMN 파싱"""
        table_map = {
            (t.schema_name, t.table_name): t for t in result.tables
        }

        # COMMENT ON TABLE
        for match in _COMMENT_TABLE.finditer(ddl):
            schema, table_name = _split_qualified(match.group(1))
            comment_text = match.group(2)
            table = table_map.get((schema, table_name))
            if table:
                table.comment = comment_text

        # COMMENT ON COLUMN
        for match in _COMMENT_COLUMN.finditer(ddl):
            schema, table_name = _split_qualified(match.group(1))
            col_name = _unquote(match.group(2))
            comment_text = match.group(3)
            table = table_map.get((schema, table_name))
            if table:
                for col in table.columns:
                    if col.name == col_name:
                        col.comment = comment_text
                        break

    # ── G01b: 방언 확장 메서드 ── #

    def _parse_views(self, ddl: str, result: DDLParseResult) -> None:
        """G01b: CREATE [MATERIALIZED] VIEW 파싱 — 뷰 소스 테이블 추출"""
        for match in _CREATE_VIEW.finditer(ddl):
            is_materialized = bool(match.group(1))
            schema, view_name = _split_qualified(match.group(2))
            # AS 이후 SELECT SQL (다음 세미콜론까지)
            after_as = ddl[match.end():]
            semi_pos = after_as.find(";")
            select_sql = (after_as[:semi_pos] if semi_pos >= 0 else after_as).strip()

            # 뷰가 참조하는 테이블 추출
            source_tables: list[str] = []
            for tbl_match in _FROM_TABLE_SIMPLE.finditer(select_sql):
                tbl = _unquote(tbl_match.group(1))
                if tbl.lower() not in {"dual", "generate_series", "unnest"}:
                    source_tables.append(tbl)

            view = ParsedView(
                schema_name=schema,
                view_name=view_name,
                is_materialized=is_materialized,
                select_sql=select_sql[:5000],
                source_tables=list(dict.fromkeys(source_tables)),
            )
            result.views.append(view)

    def _parse_indexes(self, ddl: str, result: DDLParseResult) -> None:
        """G01b: CREATE INDEX 파싱 — INCLUDE 컬럼 포함"""
        for match in _CREATE_INDEX.finditer(ddl):
            is_unique = bool(match.group(1))
            index_name = _unquote(match.group(2))
            columns = _split_column_list(match.group(4))
            # INCLUDE 절 추출
            include_cols: list[str] = []
            remaining = ddl[match.end():match.end() + 200]
            inc_match = _INDEX_INCLUDE.search(remaining)
            if inc_match:
                include_cols = _split_column_list(inc_match.group(1))

            idx = ParsedIndex(
                index_name=index_name,
                columns=columns,
                is_unique=is_unique,
                include_columns=include_cols,
            )
            result.indexes.append(idx)

            # 해당 테이블에 인덱스 연결
            _, table_name = _split_qualified(match.group(3))
            for table in result.tables:
                if table.table_name == _unquote(table_name):
                    table.indexes.append(idx)
                    break

    def _parse_dialect_specific(self, ddl: str, result: DDLParseResult) -> None:
        """G01b: 방언별 특수 구문 후처리"""
        if self.dialect == "tsql":
            self._post_process_tsql(result)
        elif self.dialect == "mysql":
            self._post_process_mysql(ddl, result)
        elif self.dialect == "snowflake":
            self._post_process_snowflake(ddl, result)

    def _post_process_tsql(self, result: DDLParseResult) -> None:
        """T-SQL: IDENTITY 컬럼 + 계산 컬럼 표시"""
        for table in result.tables:
            for col in table.columns:
                if re.search(r'\bIDENTITY\b', col.data_type, re.IGNORECASE):
                    col.is_identity = True
                    col.data_type = re.sub(
                        r'\s*IDENTITY\s*(?:\(\d+\s*,\s*\d+\))?', '',
                        col.data_type, flags=re.IGNORECASE,
                    ).strip()

    def _post_process_mysql(self, ddl: str, result: DDLParseResult) -> None:
        """MySQL: ENGINE + AUTO_INCREMENT 추출"""
        for table in result.tables:
            for col in table.columns:
                if re.search(r'\bAUTO_INCREMENT\b', col.data_type, re.IGNORECASE):
                    col.is_auto_increment = True
                    col.data_type = re.sub(
                        r'\s*AUTO_INCREMENT', '', col.data_type, flags=re.IGNORECASE,
                    ).strip()

    def _post_process_snowflake(self, ddl: str, result: DDLParseResult) -> None:
        """Snowflake: CLUSTER BY 추출"""
        for table in result.tables:
            pattern = re.compile(
                rf'CREATE\s+.*?TABLE\s+.*?{re.escape(table.table_name)}.*?\)\s*'
                rf'CLUSTER\s+BY\s*\(([^)]+)\)',
                re.IGNORECASE | re.DOTALL,
            )
            m = pattern.search(ddl)
            if m:
                table.dialect_info["cluster_by"] = _split_column_list(m.group(1))
