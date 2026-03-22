"""Sprint 1: 시멘틱 계약 사후 검증 테스트.

SQLGuard.validate_semantic_contract() 메서드가
LLM 생성 SQL의 시멘틱 계약 준수 여부를 올바르게 검증하는지 테스트한다.

검증 항목:
- 승인된 테이블만 사용하는지 (UNAPPROVED_TABLE)
- 금지된 조인 경로를 사용하지 않는지 (BANNED_JOIN_PATH)
- 팬아웃 위험 조인에 경고를 내는지 (FANOUT_RISK)
- N:N 조인에 GROUP BY가 있는지 (NN_JOIN_NO_GROUP_BY)
- 모드별 동작 (log_only, warn, enforce)
- CTE 별칭 / 서브쿼리 / 대소문자 등 엣지 케이스
"""

import pytest

from app.core.sql_guard import SQLGuard, SemanticValidationResult, SemanticViolation
from app.infrastructure.acl.synapse_acl import (
    SemanticContractContext,
    SemanticJoinRule,
)


# ---------------------------------------------------------------------------
# 공통 픽스처: 테스트용 시멘틱 계약 컨텍스트
# ---------------------------------------------------------------------------


@pytest.fixture
def basic_ctx() -> SemanticContractContext:
    """기본 시멘틱 컨텍스트: orders, customers 테이블 승인, 1:N 조인 허용."""
    return SemanticContractContext(
        measures=[],
        dimensions=[],
        allowed_joins=[
            SemanticJoinRule(
                join_id="j1",
                left_entity_id="orders",
                right_entity_id="customers",
                join_type="LEFT",
                join_condition="orders.customer_id = customers.id",
                relationship_type="1:N",
                fanout_risk_score=0.2,
            ),
        ],
        banned_entity_pairs=[],
        synonym_map={},
        entity_sources={
            "orders": "public.orders",
            "customers": "public.customers",
        },
        quality_warnings=[],
    )


@pytest.fixture
def banned_ctx() -> SemanticContractContext:
    """금지 조인이 있는 컨텍스트: orders ↔ secret_logs 금지."""
    return SemanticContractContext(
        measures=[],
        dimensions=[],
        allowed_joins=[
            SemanticJoinRule(
                join_id="j1",
                left_entity_id="orders",
                right_entity_id="customers",
                join_type="LEFT",
                join_condition="orders.customer_id = customers.id",
                relationship_type="1:N",
                fanout_risk_score=0.1,
            ),
        ],
        banned_entity_pairs=[("orders", "secret_logs")],
        synonym_map={},
        entity_sources={
            "orders": "public.orders",
            "customers": "public.customers",
            "secret_logs": "audit.secret_logs",
        },
        quality_warnings=[],
    )


@pytest.fixture
def fanout_ctx() -> SemanticContractContext:
    """팬아웃 위험이 높은 조인 컨텍스트."""
    return SemanticContractContext(
        measures=[],
        dimensions=[],
        allowed_joins=[
            SemanticJoinRule(
                join_id="j1",
                left_entity_id="orders",
                right_entity_id="line_items",
                join_type="LEFT",
                join_condition="orders.id = line_items.order_id",
                relationship_type="1:N",
                fanout_risk_score=0.85,
            ),
        ],
        banned_entity_pairs=[],
        synonym_map={},
        entity_sources={
            "orders": "orders",
            "line_items": "line_items",
        },
        quality_warnings=[],
    )


@pytest.fixture
def nn_ctx() -> SemanticContractContext:
    """N:N(다대다) 조인 컨텍스트."""
    return SemanticContractContext(
        measures=[],
        dimensions=[],
        allowed_joins=[
            SemanticJoinRule(
                join_id="j1",
                left_entity_id="students",
                right_entity_id="courses",
                join_type="INNER",
                join_condition="enrollment.student_id = students.id AND enrollment.course_id = courses.id",
                relationship_type="N:N",
                fanout_risk_score=0.3,
            ),
        ],
        banned_entity_pairs=[],
        synonym_map={},
        entity_sources={
            "students": "students",
            "courses": "courses",
        },
        quality_warnings=[],
    )


@pytest.fixture
def guard() -> SQLGuard:
    """SQLGuard 인스턴스."""
    return SQLGuard()


# ---------------------------------------------------------------------------
# 1. 정상 통과 테스트
# ---------------------------------------------------------------------------


def test_pass_valid_query(guard: SQLGuard, basic_ctx: SemanticContractContext):
    """승인된 테이블 + 승인된 조인 → 통과해야 한다."""
    sql = "SELECT o.id, c.name FROM orders o LEFT JOIN customers c ON o.customer_id = c.id LIMIT 10"
    result = guard.validate_semantic_contract(sql, basic_ctx, mode="enforce")
    assert result.passed is True
    assert len(result.violations) == 0


# ---------------------------------------------------------------------------
# 2. 금지 조인 감지
# ---------------------------------------------------------------------------


def test_block_banned_join(guard: SQLGuard, banned_ctx: SemanticContractContext):
    """금지된 조인 경로(orders ↔ secret_logs) 사용 시 BLOCK."""
    sql = "SELECT * FROM orders o JOIN secret_logs s ON o.id = s.order_id LIMIT 10"
    result = guard.validate_semantic_contract(sql, banned_ctx, mode="enforce")
    assert result.passed is False
    codes = [v.code for v in result.violations]
    assert "BANNED_JOIN_PATH" in codes


# ---------------------------------------------------------------------------
# 3. 미승인 테이블 감지
# ---------------------------------------------------------------------------


def test_block_unapproved_table(guard: SQLGuard, basic_ctx: SemanticContractContext):
    """entity_sources에 없는 raw 테이블 사용 시 BLOCK."""
    sql = "SELECT * FROM orders o JOIN raw_payments p ON o.id = p.order_id LIMIT 10"
    result = guard.validate_semantic_contract(sql, basic_ctx, mode="enforce")
    assert result.passed is False
    codes = [v.code for v in result.violations]
    assert "UNAPPROVED_TABLE" in codes
    # raw_payments가 위반 증거에 있어야 한다
    evidence_tables = [v.evidence.get("table") for v in result.violations if v.code == "UNAPPROVED_TABLE"]
    assert "raw_payments" in evidence_tables


# ---------------------------------------------------------------------------
# 4. 팬아웃 위험 경고
# ---------------------------------------------------------------------------


def test_warn_fanout_risk(guard: SQLGuard, fanout_ctx: SemanticContractContext):
    """fanout_risk_score >= 0.7인 조인 → WARN."""
    sql = "SELECT * FROM orders o LEFT JOIN line_items li ON o.id = li.order_id LIMIT 10"
    result = guard.validate_semantic_contract(sql, fanout_ctx, mode="enforce")
    # 팬아웃은 WARN이므로 passed=True (BLOCK 위반 없음)
    assert result.passed is True
    warn_codes = [w.code for w in result.warnings]
    assert "FANOUT_RISK" in warn_codes


# ---------------------------------------------------------------------------
# 5. N:N 조인 GROUP BY 검사
# ---------------------------------------------------------------------------


def test_nn_join_without_group_by(guard: SQLGuard, nn_ctx: SemanticContractContext):
    """N:N 조인에 GROUP BY가 없으면 WARN."""
    sql = "SELECT s.name, c.title FROM students s INNER JOIN courses c ON s.id = c.id LIMIT 10"
    result = guard.validate_semantic_contract(sql, nn_ctx, mode="enforce")
    assert result.passed is True  # WARN이므로 통과
    warn_codes = [w.code for w in result.warnings]
    assert "NN_JOIN_NO_GROUP_BY" in warn_codes


def test_nn_join_with_group_by(guard: SQLGuard, nn_ctx: SemanticContractContext):
    """N:N 조인에 GROUP BY가 있으면 경고 없음."""
    sql = "SELECT s.name, COUNT(*) FROM students s INNER JOIN courses c ON s.id = c.id GROUP BY s.name LIMIT 10"
    result = guard.validate_semantic_contract(sql, nn_ctx, mode="enforce")
    assert result.passed is True
    nn_warns = [w for w in result.warnings if w.code == "NN_JOIN_NO_GROUP_BY"]
    assert len(nn_warns) == 0


# ---------------------------------------------------------------------------
# 6. 다중 위반 동시 감지
# ---------------------------------------------------------------------------


def test_multiple_violations(guard: SQLGuard, banned_ctx: SemanticContractContext):
    """미승인 테이블 + 금지 조인이 동시에 발생하는 경우."""
    sql = "SELECT * FROM orders o JOIN secret_logs s ON o.id = s.order_id JOIN unknown_table u ON o.id = u.id LIMIT 10"
    result = guard.validate_semantic_contract(sql, banned_ctx, mode="enforce")
    assert result.passed is False
    codes = [v.code for v in result.violations]
    assert "BANNED_JOIN_PATH" in codes
    assert "UNAPPROVED_TABLE" in codes


# ---------------------------------------------------------------------------
# 7. 모드별 동작 테스트
# ---------------------------------------------------------------------------


def test_log_only_mode(guard: SQLGuard, banned_ctx: SemanticContractContext):
    """log_only 모드: 금지 조인이 있어도 항상 passed=True."""
    sql = "SELECT * FROM orders o JOIN secret_logs s ON o.id = s.order_id LIMIT 10"
    result = guard.validate_semantic_contract(sql, banned_ctx, mode="log_only")
    assert result.passed is True
    # 위반은 기록되어야 한다
    assert len(result.violations) > 0


def test_warn_mode(guard: SQLGuard, banned_ctx: SemanticContractContext):
    """warn 모드: BLOCK 위반이 있어도 passed=True, 위반 내용은 기록."""
    sql = "SELECT * FROM orders o JOIN secret_logs s ON o.id = s.order_id LIMIT 10"
    result = guard.validate_semantic_contract(sql, banned_ctx, mode="warn")
    assert result.passed is True
    assert len(result.violations) > 0


def test_enforce_mode(guard: SQLGuard, banned_ctx: SemanticContractContext):
    """enforce 모드: BLOCK 위반 시 passed=False."""
    sql = "SELECT * FROM orders o JOIN secret_logs s ON o.id = s.order_id LIMIT 10"
    result = guard.validate_semantic_contract(sql, banned_ctx, mode="enforce")
    assert result.passed is False
    assert len(result.violations) > 0


# ---------------------------------------------------------------------------
# 8. 파싱 실패 시 fail-closed
# ---------------------------------------------------------------------------


def test_parse_failure_fail_closed(guard: SQLGuard, basic_ctx: SemanticContractContext):
    """유효하지 않은 SQL → enforce 모드에서 passed=False (fail-closed)."""
    sql = "SELECTTTT *** FROMM nowhere!!!"
    result = guard.validate_semantic_contract(sql, basic_ctx, mode="enforce")
    assert result.passed is False
    codes = [v.code for v in result.violations]
    assert "PARSE_FAILURE" in codes


def test_parse_failure_log_only_passes(guard: SQLGuard, basic_ctx: SemanticContractContext):
    """유효하지 않은 SQL → log_only 모드에서 passed=True."""
    sql = "SELECTTTT *** FROMM nowhere!!!"
    result = guard.validate_semantic_contract(sql, basic_ctx, mode="log_only")
    assert result.passed is True


# ---------------------------------------------------------------------------
# 9. 빈 컨텍스트: 검사할 게 없으면 통과
# ---------------------------------------------------------------------------


def test_no_semantic_context(guard: SQLGuard):
    """entity_sources도 allowed_joins도 없는 빈 컨텍스트 → 통과."""
    empty_ctx = SemanticContractContext()
    sql = "SELECT * FROM anything LIMIT 10"
    result = guard.validate_semantic_contract(sql, empty_ctx, mode="enforce")
    assert result.passed is True
    assert len(result.violations) == 0
    assert len(result.warnings) == 0


# ---------------------------------------------------------------------------
# 10. CTE 별칭이 오탐되지 않는지
# ---------------------------------------------------------------------------


def test_cte_table_resolution(guard: SQLGuard, basic_ctx: SemanticContractContext):
    """CTE 별칭(monthly)은 물리 테이블이 아니므로 UNAPPROVED_TABLE 오탐이 없어야 한다."""
    sql = """
    WITH monthly AS (
        SELECT customer_id, SUM(amount) as total
        FROM orders
        GROUP BY customer_id
    )
    SELECT c.name, m.total
    FROM monthly m
    JOIN customers c ON m.customer_id = c.id
    LIMIT 10
    """
    result = guard.validate_semantic_contract(sql, basic_ctx, mode="enforce")
    assert result.passed is True
    # CTE 'monthly'가 미승인 테이블로 잡히면 안 된다
    unapproved = [v for v in result.violations if v.code == "UNAPPROVED_TABLE"]
    assert len(unapproved) == 0


# ---------------------------------------------------------------------------
# 11. 서브쿼리 안의 테이블도 감지
# ---------------------------------------------------------------------------


def test_subquery_table_detection(guard: SQLGuard, basic_ctx: SemanticContractContext):
    """서브쿼리 안에 있는 미승인 테이블도 잡아야 한다."""
    sql = "SELECT * FROM orders WHERE id IN (SELECT order_id FROM hidden_table) LIMIT 10"
    result = guard.validate_semantic_contract(sql, basic_ctx, mode="enforce")
    assert result.passed is False
    codes = [v.code for v in result.violations]
    assert "UNAPPROVED_TABLE" in codes
    evidence_tables = [v.evidence.get("table") for v in result.violations if v.code == "UNAPPROVED_TABLE"]
    assert "hidden_table" in evidence_tables


# ---------------------------------------------------------------------------
# 12. 테이블 별칭이 오탐되지 않는지
# ---------------------------------------------------------------------------


def test_alias_not_false_positive(guard: SQLGuard, basic_ctx: SemanticContractContext):
    """테이블 별칭(o, c)이 미승인 테이블로 잡히면 안 된다."""
    sql = "SELECT o.id, c.name FROM orders o JOIN customers c ON o.customer_id = c.id LIMIT 10"
    result = guard.validate_semantic_contract(sql, basic_ctx, mode="enforce")
    assert result.passed is True


# ---------------------------------------------------------------------------
# 13. 셀프 조인 (같은 테이블 두 번 조인)
# ---------------------------------------------------------------------------


def test_self_join_allowed(guard: SQLGuard, basic_ctx: SemanticContractContext):
    """승인된 테이블의 셀프 조인은 허용되어야 한다."""
    sql = "SELECT a.id, b.id FROM orders a JOIN orders b ON a.parent_id = b.id LIMIT 10"
    result = guard.validate_semantic_contract(sql, basic_ctx, mode="enforce")
    # 셀프 조인은 같은 테이블이므로 BANNED 체크에 걸리지 않아야 한다
    banned = [v for v in result.violations if v.code == "BANNED_JOIN_PATH"]
    assert len(banned) == 0


# ---------------------------------------------------------------------------
# 14. 대소문자 혼합 테이블명
# ---------------------------------------------------------------------------


def test_mixed_case_table_names(guard: SQLGuard, basic_ctx: SemanticContractContext):
    """대소문자가 섞인 테이블명도 올바르게 매칭되어야 한다."""
    sql = "SELECT * FROM Orders O JOIN Customers C ON O.customer_id = C.id LIMIT 10"
    result = guard.validate_semantic_contract(sql, basic_ctx, mode="enforce")
    assert result.passed is True


# ---------------------------------------------------------------------------
# 15. 스키마 한정 테이블명 (schema.table)
# ---------------------------------------------------------------------------


def test_schema_qualified_table(guard: SQLGuard):
    """schema.table 형식도 올바르게 처리되어야 한다."""
    ctx = SemanticContractContext(
        measures=[],
        dimensions=[],
        allowed_joins=[
            SemanticJoinRule(
                join_id="j1",
                left_entity_id="sales",
                right_entity_id="products",
                join_type="LEFT",
                join_condition="sales.product_id = products.id",
                relationship_type="1:N",
                fanout_risk_score=0.1,
            ),
        ],
        banned_entity_pairs=[],
        synonym_map={},
        entity_sources={
            "sales": "dw.sales",
            "products": "dw.products",
        },
        quality_warnings=[],
    )
    # 스키마 한정 쿼리도 테이블명으로 매칭
    sql = "SELECT s.id FROM dw.sales s LEFT JOIN dw.products p ON s.product_id = p.id LIMIT 10"
    result = guard.validate_semantic_contract(sql, ctx, mode="enforce")
    # sales, products 모두 승인된 테이블
    assert result.passed is True


# ---------------------------------------------------------------------------
# 16. entity_sources가 비어있으면 테이블 검사 건너뛰기
# ---------------------------------------------------------------------------


def test_empty_entity_sources_skips_table_check(guard: SQLGuard):
    """entity_sources가 비어있으면 UNAPPROVED_TABLE 검사를 하지 않는다."""
    ctx = SemanticContractContext(
        allowed_joins=[
            SemanticJoinRule(
                join_id="j1",
                left_entity_id="a",
                right_entity_id="b",
                join_type="INNER",
                join_condition="a.id = b.a_id",
                relationship_type="1:N",
                fanout_risk_score=0.1,
            ),
        ],
        entity_sources={},
    )
    sql = "SELECT * FROM anything JOIN whatever ON anything.id = whatever.id LIMIT 10"
    result = guard.validate_semantic_contract(sql, ctx, mode="enforce")
    unapproved = [v for v in result.violations if v.code == "UNAPPROVED_TABLE"]
    assert len(unapproved) == 0


# ---------------------------------------------------------------------------
# 17. SemanticViolation 데이터 클래스 필드 검증
# ---------------------------------------------------------------------------


def test_violation_has_all_fields(guard: SQLGuard, banned_ctx: SemanticContractContext):
    """위반 객체에 필수 필드(code, severity, message, user_message, evidence)가 있어야 한다."""
    sql = "SELECT * FROM orders o JOIN secret_logs s ON o.id = s.order_id LIMIT 10"
    result = guard.validate_semantic_contract(sql, banned_ctx, mode="enforce")
    assert len(result.violations) > 0
    v = result.violations[0]
    assert v.code
    assert v.severity in ("BLOCK", "WARN")
    assert v.message
    assert v.user_message
    assert isinstance(v.evidence, dict)


# ---------------------------------------------------------------------------
# 18. 금지 조인의 양방향 감지 (순서 무관)
# ---------------------------------------------------------------------------


def test_banned_join_bidirectional(guard: SQLGuard):
    """banned_entity_pairs가 (A, B)이면 B→A 순서 조인도 잡아야 한다."""
    ctx = SemanticContractContext(
        allowed_joins=[],
        banned_entity_pairs=[("alpha", "beta")],
        entity_sources={
            "alpha": "alpha",
            "beta": "beta",
        },
    )
    # beta가 FROM, alpha가 JOIN에 오는 역순
    sql = "SELECT * FROM beta b JOIN alpha a ON b.id = a.beta_id LIMIT 10"
    result = guard.validate_semantic_contract(sql, ctx, mode="enforce")
    assert result.passed is False
    codes = [v.code for v in result.violations]
    assert "BANNED_JOIN_PATH" in codes
