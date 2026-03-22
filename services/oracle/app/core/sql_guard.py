"""SQLGlot AST 기반 SQL 안전성 검증 모듈.

LLM이 생성한 SQL을 실행 전에 검증한다.
문자열 패턴 매칭 대신 sqlglot AST 노드 타입을 검사하여
INSERT, UPDATE, DELETE 등 위험한 SQL 연산을 정확하게 탐지한다.

#6 SQLGlot AST 검증 (P1-1)
- Critical C5: Command + Merge 추가 (SetItem 아님)
- Critical C6: parse() 먼저 → 멀티스테이트먼트 검사 → AST 노드 검사

Sprint 1: 시멘틱 계약 사후 검증 (validate_semantic_contract)
- 금지 조인 감지 (BANNED_JOIN_PATH)
- 미승인 테이블 감지 (UNAPPROVED_TABLE)
- 팬아웃 위험 경고 (FANOUT_RISK)
- N:N 조인 GROUP BY 검사 (NN_JOIN_NO_GROUP_BY)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp
from pydantic import BaseModel

logger = logging.getLogger("oracle.sql_guard")


class GuardResult(BaseModel):
    """SQL 검증 결과. 기존 API 계약 유지."""
    status: str          # "PASS" | "FIX" | "REJECT"
    sql: str             # 원본 또는 수정된 SQL
    violations: list[str] = []
    fixes: list[str] = []


# ---------------------------------------------------------------------------
# Sprint 1: 시멘틱 계약 검증 결과 모델
# ---------------------------------------------------------------------------


@dataclass
class SemanticViolation:
    """시멘틱 계약 위반 항목.

    code: 위반 종류 (BANNED_JOIN_PATH, UNAPPROVED_TABLE, FANOUT_RISK, NN_JOIN_NO_GROUP_BY)
    severity: 차단 여부 ("BLOCK" = 실행 불가, "WARN" = 경고만)
    message: 개발자용 메시지 (영어)
    user_message: 사용자용 메시지 (한국어)
    evidence: 위반 근거 데이터 (테이블명, 점수 등)
    """
    code: str
    severity: str
    message: str
    user_message: str
    evidence: dict = field(default_factory=dict)


@dataclass
class SemanticValidationResult:
    """시멘틱 계약 검증 전체 결과.

    passed: True면 SQL 실행 가능, False면 차단
    violations: BLOCK 수준 위반 목록
    warnings: WARN 수준 경고 목록
    """
    passed: bool
    violations: list[SemanticViolation] = field(default_factory=list)
    warnings: list[SemanticViolation] = field(default_factory=list)


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

    # ──────────────────────────────────────────────────────────────
    # Sprint 1: 시멘틱 계약 사후 검증
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_cte_aliases(ast: exp.Expression) -> set[str]:
        """AST의 _raw_sql에서 CTE(WITH 절) 별칭을 추출한다 (소문자).

        이 프로젝트의 sqlglot은 커스텀 빌드로 args에 _raw_sql과 _children만 제공한다.
        exp.CTE 타입이 없으므로 원문 SQL에서 'WITH alias AS (' 패턴을 찾는다.
        CTE 별칭은 실제 테이블이 아니므로 오탐 방지를 위해 제외해야 한다.
        """
        import re

        aliases: set[str] = set()
        raw_sql = ast.args.get("_raw_sql", "")
        if not raw_sql:
            return aliases

        cte_block_match = re.search(
            r"\bWITH\b\s+(.*?)\bSELECT\b",
            raw_sql, re.IGNORECASE | re.DOTALL,
        )
        if cte_block_match:
            cte_defs = cte_block_match.group(1)
            alias_pattern = re.compile(r"(\w+)\s+AS\s*\(", re.IGNORECASE)
            for alias in alias_pattern.findall(cte_defs):
                aliases.add(alias.lower())
        return aliases

    def _extract_real_tables(self, ast: exp.Expression) -> set[str]:
        """AST에서 실제 물리 테이블 이름만 추출한다 (소문자).

        CTE 별칭은 제외한다 — CTE는 가상 테이블이므로 오탐 방지.
        이 프로젝트의 sqlglot은 _raw_sql과 _children만 제공하는 커스텀 빌드이다.
        """
        cte_aliases = self._extract_cte_aliases(ast)
        tables: set[str] = set()
        for table_node in ast.find_all(exp.Table):
            if not (name := table_node.name):
                continue
            lower_name = name.lower()
            # CTE 별칭이면 건너뛴다 (물리 테이블이 아님)
            if lower_name in cte_aliases:
                continue
            tables.add(lower_name)
        return tables

    def _extract_join_table_pairs(self, ast: exp.Expression) -> list[tuple[str, str]]:
        """AST의 _children에서 Table 노드 순서를 이용해 JOIN 쌍을 추출한다.

        이 프로젝트의 sqlglot은 커스텀 빌드로 _children에 Table 노드가
        FROM, JOIN 순서대로 들어온다.
        첫 번째 Table = FROM 테이블, 이후 Table = JOIN 테이블.
        반환: [(from_table, join1_table), (join1_table, join2_table), ...] (모두 소문자)
        """
        cte_aliases = self._extract_cte_aliases(ast)
        children = ast.args.get("_children", [])

        # _children에서 Table 노드를 순서대로 추출
        tables_in_order: list[str] = []
        for child in children:
            if isinstance(child, exp.Table) and child.name:
                lower_name = child.name.lower()
                if lower_name not in cte_aliases:
                    tables_in_order.append(lower_name)

        # 인접 테이블 쌍 생성: (A, B), (B, C), ...
        pairs: list[tuple[str, str]] = []
        for i in range(len(tables_in_order) - 1):
            left = tables_in_order[i]
            right = tables_in_order[i + 1]
            if left != right:  # 셀프 조인이 아닌 경우만
                pairs.append((left, right))
        return pairs

    @staticmethod
    def _has_group_by(ast: exp.Expression) -> bool:
        """SQL에 GROUP BY 절이 있는지 확인한다.

        이 프로젝트의 sqlglot은 커스텀 빌드로 exp.Group 타입이 없고
        AST args에도 "group" 키가 없다. _raw_sql에서 키워드를 찾는다.
        """
        raw_sql = ast.args.get("_raw_sql", "")
        return "GROUP BY" in raw_sql.upper()

    def validate_semantic_contract(
        self,
        sql: str,
        semantic_ctx: "SemanticContractContext",
        mode: str = "enforce",
    ) -> SemanticValidationResult:
        """LLM이 생성한 SQL이 시멘틱 계약을 위반하는지 검증한다.

        검증 항목:
        1. 금지된 조인 경로 사용 (BANNED_JOIN_PATH) → BLOCK
        2. 미승인 테이블 사용 (UNAPPROVED_TABLE) → BLOCK
        3. 팬아웃 위험 조인 (FANOUT_RISK) → WARN
        4. N:N 조인에 GROUP BY 없음 (NN_JOIN_NO_GROUP_BY) → WARN

        mode 동작:
        - "log_only": 항상 passed=True (위반을 기록만 함)
        - "warn": 항상 passed=True (위반을 warnings에 담음)
        - "enforce": BLOCK 위반이 있으면 passed=False
        """
        from app.infrastructure.acl.synapse_acl import SemanticContractContext

        all_issues: list[SemanticViolation] = []

        # ── 0단계: SQL 파싱 (실패하면 fail-closed) ──
        try:
            ast = sqlglot.parse_one(sql, dialect="postgres")
            # 이 프로젝트의 sqlglot은 파싱 실패해도 예외를 던지지 않고
            # 일반 Expression을 반환한다. Select가 아니면 유효하지 않은 SQL이다.
            if not isinstance(ast, exp.Select):
                raise ValueError(f"Not a SELECT statement: {type(ast).__name__}")
        except Exception as exc:
            logger.warning("semantic_validate_parse_failed: %s", exc)
            violation = SemanticViolation(
                code="PARSE_FAILURE",
                severity="BLOCK",
                message=f"SQL parse failed: {exc}",
                user_message="SQL을 분석할 수 없습니다. 올바른 SQL인지 확인해 주세요.",
                evidence={"raw_sql": sql[:200]},
            )
            return SemanticValidationResult(
                passed=(mode != "enforce"),
                violations=[violation],
                warnings=[],
            )

        # ── 1단계: 실제 테이블 추출 ──
        real_tables = self._extract_real_tables(ast)
        join_pairs = self._extract_join_table_pairs(ast)

        # ── 2단계: 승인된 물리 테이블 집합 구축 ──
        # entity_sources 값(물리 소스 참조)에서 테이블 이름 추출
        approved_tables: set[str] = set()
        for entity_id, source_ref in semantic_ctx.entity_sources.items():
            if source_ref:
                # "schema.table" 형식이면 테이블 이름만 추출
                table_part = source_ref.rsplit(".", 1)[-1] if "." in source_ref else source_ref
                approved_tables.add(table_part.lower())
                # 전체 schema.table도 추가 (schema-qualified 쿼리 대응)
                approved_tables.add(source_ref.lower())

        # entity_id 자체도 테이블 이름일 수 있으므로 추가
        for entity_id in semantic_ctx.entity_sources:
            if entity_id:
                approved_tables.add(entity_id.lower())

        # ── 3단계: 미승인 테이블 검사 (entity_sources가 있을 때만) ──
        if approved_tables:
            for tbl in real_tables:
                if tbl not in approved_tables:
                    all_issues.append(SemanticViolation(
                        code="UNAPPROVED_TABLE",
                        severity="BLOCK",
                        message=f"Table '{tbl}' is not in approved entity sources",
                        user_message=f"테이블 '{tbl}'은(는) 승인된 시멘틱 계약에 포함되지 않습니다.",
                        evidence={"table": tbl, "approved": sorted(approved_tables)},
                    ))

        # ── 4단계: 금지 조인 경로 검사 ──
        # banned_entity_pairs를 소문자 쌍 집합으로 변환
        banned_set: set[frozenset[str]] = set()
        for left, right in semantic_ctx.banned_entity_pairs:
            banned_set.add(frozenset([left.lower(), right.lower()]))

        # entity_sources에서 물리 테이블 → entity_id 역매핑 구축
        table_to_entity: dict[str, str] = {}
        for entity_id, source_ref in semantic_ctx.entity_sources.items():
            if source_ref:
                table_part = source_ref.rsplit(".", 1)[-1] if "." in source_ref else source_ref
                table_to_entity[table_part.lower()] = entity_id.lower()
                table_to_entity[source_ref.lower()] = entity_id.lower()
            # entity_id 자체가 테이블 이름일 수도 있다
            table_to_entity[entity_id.lower()] = entity_id.lower()

        if banned_set:
            for left_tbl, right_tbl in join_pairs:
                left_entity = table_to_entity.get(left_tbl, left_tbl)
                right_entity = table_to_entity.get(right_tbl, right_tbl)
                pair_key = frozenset([left_entity, right_entity])
                if pair_key in banned_set:
                    all_issues.append(SemanticViolation(
                        code="BANNED_JOIN_PATH",
                        severity="BLOCK",
                        message=f"Join between '{left_tbl}' and '{right_tbl}' is forbidden by semantic contract",
                        user_message=f"테이블 '{left_tbl}'과(와) '{right_tbl}'의 조인은 금지되어 있습니다.",
                        evidence={"left": left_tbl, "right": right_tbl,
                                  "left_entity": left_entity, "right_entity": right_entity},
                    ))

        # ── 5단계: 팬아웃 위험 + N:N GROUP BY 검사 ──
        # allowed_joins를 entity 쌍으로 조회할 수 있는 맵 생성
        join_rule_map: dict[frozenset[str], "SemanticJoinRule"] = {}
        for rule in semantic_ctx.allowed_joins:
            key = frozenset([rule.left_entity_id.lower(), rule.right_entity_id.lower()])
            join_rule_map[key] = rule

        has_group_by = self._has_group_by(ast)

        for left_tbl, right_tbl in join_pairs:
            left_entity = table_to_entity.get(left_tbl, left_tbl)
            right_entity = table_to_entity.get(right_tbl, right_tbl)
            pair_key = frozenset([left_entity, right_entity])
            rule = join_rule_map.get(pair_key)
            if not rule:
                continue

            # 팬아웃 위험 경고: fanout_risk_score >= 0.7
            if rule.fanout_risk_score >= 0.7:
                all_issues.append(SemanticViolation(
                    code="FANOUT_RISK",
                    severity="WARN",
                    message=f"Join '{left_tbl}' ↔ '{right_tbl}' has high fanout risk ({rule.fanout_risk_score})",
                    user_message=f"'{left_tbl}'과(와) '{right_tbl}' 조인은 데이터 팽창 위험이 높습니다 (위험도: {rule.fanout_risk_score}).",
                    evidence={"left": left_tbl, "right": right_tbl,
                              "fanout_risk_score": rule.fanout_risk_score},
                ))

            # N:N 조인에서 GROUP BY가 없으면 경고
            if rule.relationship_type.lower() in ("n:n", "many_to_many", "m:n"):
                if not has_group_by:
                    all_issues.append(SemanticViolation(
                        code="NN_JOIN_NO_GROUP_BY",
                        severity="WARN",
                        message=f"N:N join '{left_tbl}' ↔ '{right_tbl}' without GROUP BY may produce duplicates",
                        user_message=f"'{left_tbl}'과(와) '{right_tbl}'은(는) 다대다 관계입니다. GROUP BY 없이 사용하면 중복이 발생할 수 있습니다.",
                        evidence={"left": left_tbl, "right": right_tbl,
                                  "relationship_type": rule.relationship_type},
                    ))

        # ── 결과 분류: BLOCK vs WARN ──
        block_violations = [v for v in all_issues if v.severity == "BLOCK"]
        warn_violations = [v for v in all_issues if v.severity == "WARN"]

        # mode에 따라 passed 결정
        if mode == "log_only":
            # 로그만 남기고 항상 통과
            if all_issues:
                logger.info("semantic_contract_log_only: violations=%d, warnings=%d",
                            len(block_violations), len(warn_violations))
            return SemanticValidationResult(
                passed=True,
                violations=block_violations,
                warnings=warn_violations,
            )
        elif mode == "warn":
            # 경고만 하고 통과
            if all_issues:
                logger.warning("semantic_contract_warnings: violations=%d, warnings=%d",
                               len(block_violations), len(warn_violations))
            return SemanticValidationResult(
                passed=True,
                violations=block_violations,
                warnings=warn_violations,
            )
        else:
            # enforce: BLOCK 위반이 있으면 차단
            passed = len(block_violations) == 0
            if not passed:
                logger.warning("semantic_contract_enforce_blocked: violations=%d",
                               len(block_violations))
            return SemanticValidationResult(
                passed=passed,
                violations=block_violations,
                warnings=warn_violations,
            )


# 싱글톤 인스턴스 (기존 import 호환성 유지)
sql_guard = SQLGuard()
