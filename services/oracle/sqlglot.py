"""로컬 sqlglot 모의 모듈.

실제 sqlglot 패키지가 설치되지 않은 환경에서
SQLGuard AST 기반 검증을 지원하기 위한 최소 구현.

지원 기능:
- parse(): 세미콜론으로 분리된 다중 SQL 문 파싱
- parse_one(): 단일 SQL 문 파싱
- AST 노드 타입: Select, Insert, Update, Delete, Drop, Create, Alter, Grant, Command, Merge
- walk(): AST 트리 순회 (노드 직접 반환)
- iter_expressions(): 자식 노드 순회
- Table: SQL에서 참조된 테이블 추출
- Subquery: 서브쿼리 깊이 계산 (재귀 AST 구성)
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import Iterable, List, Generator


class errors:
    class ParseError(Exception):
        pass

    class TokenError(Exception):
        pass


class exp:
    @dataclass
    class Expression:
        """AST 노드 기본 클래스."""
        args: dict = field(default_factory=dict)

        @property
        def name(self) -> str:
            return self.args.get("name", "")

        def find_all(self, kind) -> Generator:
            """해당 타입의 모든 자손 노드를 찾는다."""
            for child in self._all_descendants():
                if isinstance(child, kind):
                    yield child

        def _all_descendants(self) -> Generator:
            """모든 자손 노드를 재귀적으로 순회한다."""
            for child in self.iter_expressions():
                yield child
                yield from child._all_descendants()

        def iter_expressions(self) -> Generator:
            """직접 자식 노드만 반환한다."""
            children = self.args.get("_children", [])
            for child in children:
                if isinstance(child, exp.Expression):
                    yield child

        def walk(self) -> Generator:
            """자신을 포함한 모든 노드를 순회한다."""
            yield self
            for child in self.iter_expressions():
                yield from child.walk()

        def copy(self):
            return copy.deepcopy(self)

        def sql(self, dialect: str = "postgres") -> str:
            _ = dialect
            return self.args.get("_raw_sql", "")

    @dataclass
    class Join(Expression):
        pass

    @dataclass
    class Subquery(Expression):
        """서브쿼리 노드. 자식으로 Select를 포함할 수 있다."""
        pass

    @dataclass
    class Table(Expression):
        """테이블 참조 노드."""

        @property
        def name(self) -> str:
            return self.args.get("name", "")

    # ── DML/DDL 타입 (금지 노드 검출용) ──
    @dataclass
    class Insert(Expression):
        pass

    @dataclass
    class Update(Expression):
        pass

    @dataclass
    class Delete(Expression):
        pass

    @dataclass
    class Drop(Expression):
        pass

    @dataclass
    class Create(Expression):
        pass

    @dataclass
    class Alter(Expression):
        pass

    @dataclass
    class Grant(Expression):
        pass

    @dataclass
    class Command(Expression):
        """EXEC, EXECUTE, TRUNCATE 등 명령문."""
        pass

    @dataclass
    class Merge(Expression):
        pass

    @dataclass
    class Select(Expression):
        """SELECT 문 AST 노드."""

        def find_all(self, kind) -> Generator:
            """해당 타입의 모든 자손 노드를 찾는다."""
            for child in self._all_descendants():
                if isinstance(child, kind):
                    yield child

        def limit(self, n: int):
            self.args["limit"] = n
            return self

        def sql(self, dialect: str = "postgres") -> str:
            _ = dialect
            text = self.args.get("_raw_sql", "").strip().rstrip(";")
            if "limit" in self.args and self.args["limit"] is not True:
                # LIMIT 자동 추가: 기존 LIMIT이 없으면 추가
                if not re.search(r"\blimit\s+\d+\b", text, flags=re.IGNORECASE):
                    text = f"{text} LIMIT {int(self.args['limit'])}"
            return text


# ──────────────────────────────────────────────────────────────
# 파서 헬퍼
# ──────────────────────────────────────────────────────────────

def _extract_table_names(sql: str) -> list[str]:
    """SQL에서 테이블 이름 추출 (FROM, JOIN 뒤)."""
    tables: list[str] = []
    # FROM 절 테이블
    for m in re.finditer(r'\bFROM\s+([a-zA-Z_][\w.]*)', sql, re.IGNORECASE):
        name = m.group(1)
        # 서브쿼리 "(SELECT ..." 제외
        if name.upper() != "SELECT":
            tables.append(name.split(".")[-1])
    # JOIN 절 테이블
    for m in re.finditer(r'\bJOIN\s+([a-zA-Z_][\w.]*)', sql, re.IGNORECASE):
        name = m.group(1)
        tables.append(name.split(".")[-1])
    return tables


def _build_subquery_tree(sql: str) -> list[exp.Expression]:
    """서브쿼리를 재귀적으로 AST 노드 트리로 구성한다.

    서브쿼리 깊이를 정확히 계산하기 위해 재귀 구조를 만든다.
    """
    children: list[exp.Expression] = []

    # JOIN 노드 추출
    join_count = len(re.findall(r'\bJOIN\b', sql, flags=re.IGNORECASE))
    for _ in range(join_count):
        children.append(exp.Join())

    # 테이블 노드 추출
    for table_name in _extract_table_names(sql):
        children.append(exp.Table(args={"name": table_name}))

    # 서브쿼리 추출 (괄호 매칭)
    # 간단한 구현: "( SELECT ..." 패턴 찾아서 괄호 매칭
    pos = 0
    while pos < len(sql):
        # "(" 다음에 SELECT가 오는 패턴 찾기
        match = re.search(r'\(\s*SELECT\b', sql[pos:], re.IGNORECASE)
        if not match:
            break

        start = pos + match.start()
        # 괄호 매칭으로 서브쿼리 범위 찾기
        depth = 0
        end = start
        for i in range(start, len(sql)):
            if sql[i] == '(':
                depth += 1
            elif sql[i] == ')':
                depth -= 1
                if depth == 0:
                    end = i
                    break

        if end > start:
            inner_sql = sql[start + 1:end].strip()
            # 서브쿼리 내부를 재귀적으로 파싱
            inner_children = _build_subquery_tree(inner_sql)
            sub_node = exp.Subquery(args={"_children": inner_children, "_raw_sql": inner_sql})
            children.append(sub_node)
            pos = end + 1
        else:
            pos = start + 1

    return children


def _detect_statement_type(sql: str) -> type:
    """SQL 문의 첫 키워드로 statement 타입을 판별한다."""
    text = sql.strip()
    # 첫 키워드 추출 (괄호, 공백 전까지)
    first_word = re.match(r'(\w+)', text, re.IGNORECASE)
    if not first_word:
        return exp.Expression
    keyword = first_word.group(1).upper()

    type_map = {
        "SELECT": exp.Select,
        "INSERT": exp.Insert,
        "UPDATE": exp.Update,
        "DELETE": exp.Delete,
        "DROP": exp.Drop,
        "CREATE": exp.Create,
        "ALTER": exp.Alter,
        "GRANT": exp.Grant,
        "REVOKE": exp.Grant,
        "EXEC": exp.Command,
        "EXECUTE": exp.Command,
        "TRUNCATE": exp.Command,
        "MERGE": exp.Merge,
        "WITH": None,  # CTE — 특별 처리 필요
    }

    if keyword == "WITH":
        # CTE: WITH ... AS (...) SELECT ... → Select로 처리
        if re.search(r'\bSELECT\b', text, re.IGNORECASE):
            return exp.Select
        return exp.Expression

    return type_map.get(keyword, exp.Expression)


def parse(sql_query: str, dialect: str = "postgres") -> list:
    """세미콜론으로 분리된 다중 SQL 문을 파싱한다.

    Args:
        sql_query: SQL 문자열 (세미콜론으로 분리 가능)
        dialect: SQL 방언

    Returns:
        파싱된 AST 노드 리스트 (각 문장별)
    """
    _ = dialect
    text = (sql_query or "").strip()
    if not text:
        return [None]

    # 문자열 리터럴 안의 세미콜론을 보호하면서 분리
    statements = _split_statements(text)

    results: list = []
    for stmt in statements:
        stmt = stmt.strip().rstrip(";").strip()
        if not stmt:
            continue
        results.append(_parse_single(stmt))

    return results if results else [None]


def _split_statements(sql: str) -> list[str]:
    """문자열 리터럴을 보호하면서 세미콜론으로 SQL 분리."""
    statements: list[str] = []
    current = []
    in_single_quote = False
    in_double_quote = False
    i = 0

    while i < len(sql):
        c = sql[i]

        if c == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
            current.append(c)
        elif c == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
            current.append(c)
        elif c == ';' and not in_single_quote and not in_double_quote:
            statements.append(''.join(current))
            current = []
        else:
            current.append(c)
        i += 1

    if current:
        statements.append(''.join(current))

    return statements


def _parse_single(text: str) -> exp.Expression:
    """단일 SQL 문을 AST 노드로 파싱한다."""
    if not text.strip():
        return None

    stmt_type = _detect_statement_type(text)

    if stmt_type == exp.Select:
        children = _build_subquery_tree(text)
        has_limit = bool(re.search(r'\bLIMIT\s+\d+\b', text, flags=re.IGNORECASE))
        node = stmt_type(args={"_raw_sql": text, "_children": children})
        if has_limit:
            node.args["limit"] = True
        return node
    else:
        return stmt_type(args={"_raw_sql": text})


def parse_one(sql_query: str, dialect: str = "postgres") -> exp.Expression:
    """단일 SQL 문을 파싱한다. 멀티스테이트먼트는 첫 번째만 반환.

    빈 SQL이면 ParseError를 발생시킨다.
    """
    _ = dialect
    text = (sql_query or "").strip()
    if not text:
        raise errors.ParseError("empty sql")

    return _parse_single(text)
