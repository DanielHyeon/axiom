# SQL Guard 검증 체계

## 이 문서가 답하는 질문

- SQL Guard는 어떤 계층으로 SQL을 검증하는가?
- SQLGlot은 어떤 역할을 하고, 왜 선택했는가?
- 화이트리스트/블랙리스트 기반 검증은 어떻게 동작하는가?
- 검증 실패 시 어떻게 처리되는가?

<!-- affects: 02_api, 03_backend, 07_security -->
<!-- requires-update: 07_security/sql-safety.md -->

---

## 1. SQL Guard 개요

SQL Guard는 LLM이 생성한 SQL이 **안전하고 성능 기준을 충족하는지** 검증하는 다층 방어 시스템이다.

LLM은 비결정적 시스템이므로 악의적이지 않더라도 위험한 SQL(DELETE, DROP)을 생성하거나, 과도하게 복잡한 쿼리를 만들 수 있다. SQL Guard는 이러한 위험을 실행 전에 차단한다.

```
LLM 생성 SQL
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                     SQL Guard (4단계)                        │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Layer 1      │  │ Layer 2      │  │ Layer 3          │  │
│  │ 키워드       │→│ SQLGlot      │→│ 구조적 제약      │  │
│  │ 블랙리스트   │  │ 구문 파싱    │  │ (깊이/복잡도)    │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Layer 4: 자동 보정 (LIMIT 추가 등)                    │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  결과: PASS (실행 가능) | REJECT (실행 차단) | FIX (수정 후 │
│        PASS)                                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 검증 계층 상세

### 2.1 Layer 1: 키워드 블랙리스트

**목적**: 명백히 위험한 SQL 문을 빠르게 차단

```python
# sql_guard.py 기반
FORBIDDEN_KEYWORDS = [
    # DML (Data Manipulation)
    "INSERT", "UPDATE", "DELETE", "MERGE", "UPSERT",

    # DDL (Data Definition)
    "CREATE", "ALTER", "DROP", "TRUNCATE", "RENAME",

    # DCL (Data Control)
    "GRANT", "REVOKE",

    # 위험 함수
    "SLEEP", "BENCHMARK", "LOAD_FILE", "INTO OUTFILE",
    "INTO DUMPFILE", "INFORMATION_SCHEMA",

    # 시스템 명령
    "EXEC", "EXECUTE", "xp_cmdshell", "sp_",

    # 주석 기반 공격
    "--", "/*", "*/",
]

def check_forbidden_keywords(sql: str) -> list[str]:
    """
    대소문자 무시하고 금지 키워드 존재 여부 확인.
    SELECT 문 내 서브쿼리 안의 키워드도 탐지.

    반환: 발견된 금지 키워드 목록 (빈 목록이면 통과)
    """
    sql_upper = sql.upper()
    found = []
    for keyword in FORBIDDEN_KEYWORDS:
        if keyword in sql_upper:
            # SELECT 문의 컬럼 이름과 구별 필요
            # 예: "SELECT insert_date FROM ..." 은 허용
            if not _is_column_name_context(sql, keyword):
                found.append(keyword)
    return found
```

**주의사항**: 컬럼명에 금지 키워드가 포함된 경우(예: `insert_date`, `update_time`)는 허용해야 한다. 이를 위해 컨텍스트 분석이 필요하다.

### 2.2 Layer 2: SQLGlot 구문 파싱

**목적**: SQL 구문이 문법적으로 올바른지 검증하고, AST(추상 구문 트리)를 통해 정밀 분석

```python
import sqlglot

def parse_and_validate(sql: str, dialect: str = "postgres") -> ParseResult:
    """
    SQLGlot으로 SQL 파싱.

    검증 항목:
    1. 구문 파싱 성공 여부
    2. SELECT 문 타입 확인 (DML 이면 거부)
    3. 테이블 이름 추출 (화이트리스트 검증용)
    4. 함수 호출 추출 (위험 함수 검사)
    """
    try:
        parsed = sqlglot.parse_one(sql, dialect=dialect)

        # SELECT 문인지 확인
        if not isinstance(parsed, sqlglot.exp.Select):
            return ParseResult(
                success=False,
                error=f"SELECT 문만 허용됩니다. 감지된 유형: {type(parsed).__name__}"
            )

        # 테이블 이름 추출
        tables = [t.name for t in parsed.find_all(sqlglot.exp.Table)]

        # 함수 호출 추출
        functions = [f.name for f in parsed.find_all(sqlglot.exp.Anonymous)]

        return ParseResult(
            success=True,
            tables=tables,
            functions=functions,
            ast=parsed
        )
    except sqlglot.errors.ParseError as e:
        return ParseResult(success=False, error=str(e))
```

**SQLGlot 선택 근거**: [ADR-003](../99_decisions/ADR-003-sqlglot-validation.md) 참조

### 2.3 Layer 3: 구조적 제약 검사

**목적**: 쿼리 복잡도를 제한하여 성능 사고 방지

```python
def check_structural_constraints(
    ast: sqlglot.Expression,
    max_join_depth: int = 5,
    max_subquery_depth: int = 3
) -> ConstraintResult:
    """
    AST 기반 구조적 제약 검사.

    검증 항목:
    1. JOIN 깊이: 테이블 JOIN 수 <= max_join_depth
    2. 서브쿼리 깊이: 중첩 서브쿼리 <= max_subquery_depth
    3. UNION 수: UNION/UNION ALL 수 <= 5
    4. 와일드카드: SELECT * 사용 경고 (차단은 아님)
    """

    # JOIN 깊이 측정
    joins = list(ast.find_all(sqlglot.exp.Join))
    if len(joins) > max_join_depth:
        return ConstraintResult(
            passed=False,
            violation=f"JOIN 깊이 초과: {len(joins)} > {max_join_depth}"
        )

    # 서브쿼리 깊이 측정
    subquery_depth = _measure_subquery_depth(ast)
    if subquery_depth > max_subquery_depth:
        return ConstraintResult(
            passed=False,
            violation=f"서브쿼리 깊이 초과: {subquery_depth} > {max_subquery_depth}"
        )

    return ConstraintResult(passed=True)
```

**제약 기본값**:

| 제약 | 기본값 | 근거 |
|------|--------|------|
| `max_join_depth` | 5 | 5개 이상 JOIN은 대부분 비효율적 쿼리 |
| `max_subquery_depth` | 3 | 3단계 이상 중첩은 성능 저하 유발 |
| UNION 최대 수 | 5 | 과도한 UNION은 메모리 문제 유발 |

### 2.4 Layer 4: 자동 보정

**목적**: 사소한 문제는 자동 수정하여 사용자 경험 향상

```python
def auto_fix(sql: str, ast: sqlglot.Expression) -> FixResult:
    """
    자동 보정 항목:
    1. LIMIT 없으면 LIMIT {row_limit} 추가
    2. ORDER BY 없는 LIMIT에 경고 추가
    3. 세미콜론 제거
    4. 불필요한 공백/개행 정리
    """
    fixed_sql = sql
    fixes_applied = []

    # LIMIT 자동 추가
    if not _has_limit(ast):
        fixed_sql = f"{fixed_sql.rstrip(';')} LIMIT {ROW_LIMIT}"
        fixes_applied.append(f"LIMIT {ROW_LIMIT} 자동 추가")

    # 세미콜론 제거
    if fixed_sql.rstrip().endswith(';'):
        fixed_sql = fixed_sql.rstrip(';').rstrip()
        fixes_applied.append("세미콜론 제거")

    return FixResult(sql=fixed_sql, fixes=fixes_applied)
```

---

## 3. 검증 흐름 전체

```python
async def guard_sql(sql: str, config: GuardConfig) -> GuardResult:
    """
    SQL Guard 전체 흐름.

    반환:
    - status: PASS | REJECT | FIX
    - sql: 원본 또는 수정된 SQL
    - violations: 위반 목록
    - fixes: 적용된 자동 수정 목록
    """

    # Layer 1: 키워드 블랙리스트
    forbidden = check_forbidden_keywords(sql)
    if forbidden:
        return GuardResult(
            status="REJECT",
            violations=[f"금지 키워드 발견: {', '.join(forbidden)}"]
        )

    # Layer 2: SQLGlot 파싱
    parse = parse_and_validate(sql, dialect=config.dialect)
    if not parse.success:
        return GuardResult(
            status="REJECT",
            violations=[f"SQL 파싱 실패: {parse.error}"]
        )

    # Layer 3: 구조적 제약
    constraint = check_structural_constraints(
        parse.ast,
        max_join_depth=config.max_join_depth,
        max_subquery_depth=config.max_subquery_depth
    )
    if not constraint.passed:
        return GuardResult(
            status="REJECT",
            violations=[constraint.violation]
        )

    # Layer 4: 자동 보정
    fix = auto_fix(sql, parse.ast)
    if fix.fixes:
        return GuardResult(
            status="FIX",
            sql=fix.sql,
            fixes=fix.fixes
        )

    return GuardResult(status="PASS", sql=sql)
```

---

## 4. 화이트리스트 기반 테이블 검증

**K-AIR에는 없지만 Axiom에서 추가 예정인 기능**:

비즈니스 프로세스 인텔리전스 도메인에서는 접근 가능한 테이블을 명시적으로 제한해야 한다.

```python
# Axiom 추가 기능
class TableWhitelist:
    """
    데이터소스별 접근 가능 테이블 화이트리스트.
    Neo4j의 Table 노드 중 text_to_sql_is_valid=True 인 것만 허용.
    """

    async def check(self, tables: list[str], datasource_id: str) -> WhitelistResult:
        """
        SQL에서 사용된 테이블이 모두 화이트리스트에 포함되는지 확인.

        미포함 테이블이 있으면 REJECT.
        """
        allowed = await self._get_allowed_tables(datasource_id)
        unauthorized = [t for t in tables if t not in allowed]

        if unauthorized:
            return WhitelistResult(
                passed=False,
                unauthorized_tables=unauthorized
            )
        return WhitelistResult(passed=True)
```

---

## 5. 에러 처리

### 5.1 검증 실패 시 사용자 응답

| 실패 유형 | 사용자 메시지 | 내부 처리 |
|----------|-------------|----------|
| DML 키워드 | "데이터 조회(SELECT)만 가능합니다" | 로깅 + 차단 |
| 파싱 실패 | "SQL 생성에 문제가 발생했습니다. 다시 질문해주세요" | 재생성 시도 (ReAct) |
| JOIN 초과 | "너무 복잡한 쿼리입니다. 질문을 나눠주세요" | 로깅 + 차단 |
| 화이트리스트 위반 | "해당 데이터에 접근 권한이 없습니다" | 보안 로깅 + 차단 |

### 5.2 ReAct에서의 검증 실패 처리

ReAct 파이프라인에서는 검증 실패 시 **Fix 단계**로 분기하여 LLM에게 수정을 요청한다:

```
Generate → Validate → [REJECT] → Fix → Validate → [PASS] → Execute
                                    ↑              │
                                    └──[REJECT]────┘ (최대 3회)
```

---

## 결정 사항

| 결정 | 근거 |
|------|------|
| 4계층 방어 채택 | 단일 계층은 우회 가능, 다층 방어로 안전성 확보 |
| SQLGlot 사용 | AST 기반 정밀 분석 가능 ([ADR-003](../99_decisions/ADR-003-sqlglot-validation.md)) |
| 자동 보정 포함 | 사소한 문제(LIMIT 누락)로 전체 요청 실패는 비효율적 |
| ReAct Fix 루프 | 검증 실패를 LLM 자체 수정 기회로 활용 |

## 금지 사항

- SQL Guard를 우회하는 직접 SQL 실행 경로 금지
- 검증 없이 LLM 생성 SQL을 Target DB에 전달 금지
- 블랙리스트를 런타임에 동적으로 축소하는 것 금지

## 관련 문서

- [07_security/sql-safety.md](../07_security/sql-safety.md): SQL 안전성 정책
- [99_decisions/ADR-003-sqlglot-validation.md](../99_decisions/ADR-003-sqlglot-validation.md): SQLGlot 선택 결정
- [03_backend/sql-execution.md](../03_backend/sql-execution.md): SQL 실행 엔진
