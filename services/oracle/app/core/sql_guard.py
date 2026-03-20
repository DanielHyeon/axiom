"""SQLGlot AST 기반 SQL 안전성 검증 모듈.

LLM이 생성한 SQL을 실행 전에 검증한다.
문자열 패턴 매칭 대신 sqlglot AST 노드 타입을 검사하여
INSERT, UPDATE, DELETE 등 위험한 SQL 연산을 정확하게 탐지한다.

#6 SQLGlot AST 검증 (P1-1)
- Critical C5: Command + Merge 추가 (SetItem 아님)
- Critical C6: parse() 먼저 → 멀티스테이트먼트 검사 → AST 노드 검사
"""

from __future__ import annotations

import sqlglot
from sqlglot import exp
from pydantic import BaseModel


class GuardResult(BaseModel):
    """SQL 검증 결과. 기존 API 계약 유지."""
    status: str          # "PASS" | "FIX" | "REJECT"
    sql: str             # 원본 또는 수정된 SQL
    violations: list[str] = []
    fixes: list[str] = []


class GuardConfig(BaseModel):
    """SQL 검증 설정."""
    dialect: str = "postgres"
    max_join_depth: int = 5        # JOIN 개수 상한
    max_subquery_depth: int = 3    # 서브쿼리 중첩 깊이 상한
    row_limit: int = 1000          # LIMIT 자동 추가 기준
    allowed_tables: list[str] | None = None  # 허용 테이블 화이트리스트 (None이면 검사 안 함)


# ──────────────────────────────────────────────────────────────
# 금지 AST 노드 타입 (C5: Command + Merge 포함, SetItem 아님)
# ──────────────────────────────────────────────────────────────
_FORBIDDEN_TYPES = (
    exp.Insert,     # INSERT 문
    exp.Update,     # UPDATE 문
    exp.Delete,     # DELETE 문
    exp.Drop,       # DROP TABLE / INDEX 등
    exp.Create,     # CREATE TABLE / INDEX 등
    exp.Alter,      # ALTER TABLE 등
    exp.Grant,      # GRANT / REVOKE 권한
    exp.Command,    # EXEC, EXECUTE 등 (C5: SetItem → Command)
    exp.Merge,      # MERGE / UPSERT (C5: 추가)
)


class SQLGuard:
    """AST 기반 SQL 안전성 검증기.

    실행 순서 (C6 준수):
    1. sqlglot.parse() → 멀티스테이트먼트 감지
    2. parsed_list[0] → AST 노드 검사
    3. 구조적 제한 (JOIN 깊이, 서브쿼리 깊이)
    4. 화이트리스트 테이블 검증
    5. LIMIT 자동 삽입
    """

    def _measure_subquery_depth(self, ast: exp.Expression) -> int:
        """AST 트리를 재귀 순회하여 최대 서브쿼리 중첩 깊이를 계산한다.

        기존 버그 수정: 단순 노드 카운트가 아닌 실제 depth 계산.
        예: SELECT * FROM (SELECT * FROM (SELECT 1)) → depth = 2
        """
        def _walk(node: exp.Expression, depth: int) -> int:
            # 현재 노드가 Subquery이면 깊이 1 증가
            max_d = depth
            if isinstance(node, exp.Subquery):
                depth += 1
                max_d = depth
            # 자식 노드 재귀 순회
            for child in node.iter_expressions():
                max_d = max(max_d, _walk(child, depth))
            return max_d

        return _walk(ast, 0)

    def _measure_join_count(self, ast: exp.Expression) -> int:
        """AST에서 JOIN 노드 개수를 센다."""
        return len(list(ast.find_all(exp.Join)))

    def _extract_referenced_tables(self, ast: exp.Expression) -> set[str]:
        """AST에서 참조된 모든 테이블 이름을 추출한다 (소문자)."""
        tables: set[str] = set()
        for table_node in ast.find_all(exp.Table):
            name = table_node.name
            if name:
                tables.add(name.lower())
        return tables

    def guard_sql(self, sql_query: str, config: GuardConfig | None = None) -> GuardResult:
        """SQL 문을 검증하고, 필요하면 LIMIT을 자동 추가한다.

        Returns:
            GuardResult:
            - status="PASS": 안전한 SQL (변경 없음)
            - status="FIX": LIMIT 등 자동 수정 적용됨
            - status="REJECT": 위험한 SQL (실행 불가)
        """
        if config is None:
            config = GuardConfig()

        violations: list[str] = []

        # ── Phase 1: AST 파싱 + 멀티스테이트먼트 검사 (C6: parse 먼저) ──
        try:
            # sqlglot.parse()는 세미콜론으로 분리된 여러 문장을 리스트로 반환
            parsed_list = sqlglot.parse(sql_query, dialect=config.dialect)
        except (sqlglot.errors.ParseError, sqlglot.errors.TokenError) as e:
            return GuardResult(
                status="REJECT",
                sql=sql_query,
                violations=[f"SQL 파싱 실패: {e}"],
            )

        # None 항목 제거 (빈 문자열 파싱 시 발생 가능)
        parsed_list = [p for p in parsed_list if p is not None]

        if not parsed_list:
            return GuardResult(
                status="REJECT",
                sql=sql_query,
                violations=["빈 SQL 문"],
            )

        # 멀티스테이트먼트 거부 (세미콜론 주입 방어)
        if len(parsed_list) > 1:
            return GuardResult(
                status="REJECT",
                sql=sql_query,
                violations=["다중 SQL 문 감지 — 단일 SELECT만 허용"],
            )

        parsed = parsed_list[0]

        # ── Phase 2: Statement 타입 검증 (SELECT만 허용) ──
        if not isinstance(parsed, exp.Select):
            return GuardResult(
                status="REJECT",
                sql=sql_query,
                violations=[f"SELECT 문만 허용됩니다. 감지된 유형: {type(parsed).__name__}"],
            )

        # ── Phase 3: AST 노드 순회 — 금지 노드 타입 검출 ──
        for node in parsed.walk():
            # walk()는 (node, parent, key) 튜플을 반환
            if isinstance(node, tuple):
                node = node[0]
            if isinstance(node, _FORBIDDEN_TYPES):
                violations.append(f"금지된 SQL 연산: {type(node).__name__}")

        if violations:
            return GuardResult(
                status="REJECT",
                sql=sql_query,
                violations=violations,
            )

        # ── Phase 4: 구조적 제한 검사 ──
        # JOIN 깊이 (개수) 검사
        join_count = self._measure_join_count(parsed)
        if join_count > config.max_join_depth:
            violations.append(
                f"JOIN 깊이 초과: {join_count} > {config.max_join_depth}"
            )

        # 서브쿼리 중첩 깊이 검사 (버그 수정된 재귀 depth 계산)
        sq_depth = self._measure_subquery_depth(parsed)
        if sq_depth > config.max_subquery_depth:
            violations.append(
                f"서브쿼리 깊이 초과: {sq_depth} > {config.max_subquery_depth}"
            )

        if violations:
            return GuardResult(
                status="REJECT",
                sql=sql_query,
                violations=violations,
            )

        # ── Phase 5: 화이트리스트 테이블 검증 ──
        if config.allowed_tables is not None:
            referenced = self._extract_referenced_tables(parsed)
            allowed_set = {t.lower() for t in config.allowed_tables}
            unauthorized = referenced - allowed_set
            if unauthorized:
                return GuardResult(
                    status="REJECT",
                    sql=sql_query,
                    violations=[f"허용되지 않은 테이블: {', '.join(sorted(unauthorized))}"],
                )

        # ── Phase 6: LIMIT 자동 삽입 ──
        fixes: list[str] = []
        fixed_ast = parsed.copy()
        if not fixed_ast.args.get("limit"):
            fixed_ast = fixed_ast.limit(config.row_limit)
            fixes.append(f"LIMIT {config.row_limit} 자동 추가")

        fixed_sql = fixed_ast.sql(dialect=config.dialect)

        if fixes:
            return GuardResult(status="FIX", sql=fixed_sql, fixes=fixes)

        return GuardResult(status="PASS", sql=fixed_sql)


# 싱글톤 인스턴스 (기존 import 호환성 유지)
sql_guard = SQLGuard()
