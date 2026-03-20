# SQL Guard 검증 체계

## 이 문서가 답하는 질문

- SQL Guard는 어떤 단계로 SQL을 검증하는가?
- SQLGlot은 어떤 역할을 하고, 왜 선택했는가?
- AST 노드 타입 기반 검증은 어떻게 동작하는가?
- 검증 실패 시 어떻게 처리되는가?

<!-- affects: 02_api, 03_backend, 07_security -->
<!-- requires-update: 07_security/sql-safety.md -->

---

## 1. SQL Guard 개요

SQL Guard는 LLM이 생성한 SQL이 **안전하고 성능 기준을 충족하는지** 검증하는 다층 방어 시스템이다.

LLM은 비결정적 시스템이므로 악의적이지 않더라도 위험한 SQL(DELETE, DROP)을 생성하거나, 과도하게 복잡한 쿼리를 만들 수 있다. SQL Guard는 이러한 위험을 실행 전에 차단한다.

> **현재 구현**: `app/core/sql_guard.py` -- SQLGlot AST 기반 6단계 검증. 키워드 블랙리스트 대신 AST 노드 타입으로 정밀 검출한다.

```text
LLM 생성 SQL
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                 SQL Guard (6단계, AST 기반)                   │
│                                                              │
│  Phase 1: sqlglot.parse() → 멀티스테이트먼트 감지            │
│  Phase 2: SELECT 문 타입 확인 (DML 이면 거부)               │
│  Phase 3: AST 노드 순회 — 금지 노드 타입 검출               │
│           (Insert/Update/Delete/Drop/Create/Alter/           │
│            Grant/Command/Merge)                              │
│  Phase 4: 구조적 제한 (JOIN 개수, 서브쿼리 깊이)            │
│  Phase 5: 화이트리스트 테이블 검증 (allowed_tables)          │
│  Phase 6: LIMIT 자동 삽입 (없으면 추가)                      │
│                                                              │
│  결과: PASS | REJECT | FIX                                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 검증 Phase 상세

`SQLGuard.guard_sql()` 메서드는 6개의 Phase를 순서대로 실행한다. 각 Phase가 실패하면 즉시 `REJECT`를 반환하고 후속 Phase는 실행하지 않는다.

### 2.1 Phase 1: AST 파싱 + 멀티스테이트먼트 감지

**목적**: SQL 구문을 AST로 파싱하고, 세미콜론 주입을 통한 다중 문장 공격을 차단한다.

> **핵심 설계**: `sqlglot.parse_one()`이 아닌 `sqlglot.parse()`를 사용한다. `parse()`는 세미콜론으로 분리된 여러 문장을 리스트로 반환하므로, 멀티스테이트먼트를 정확히 감지할 수 있다.

```python
# sqlglot.parse()는 리스트를 반환 — 단일 문장만 허용
parsed_list = sqlglot.parse(sql_query, dialect=config.dialect)
parsed_list = [p for p in parsed_list if p is not None]

# 파싱 실패 → REJECT
# 빈 SQL → REJECT
# len(parsed_list) > 1 → REJECT ("다중 SQL 문 감지 — 단일 SELECT만 허용")
```

**거부 조건**:

| 조건 | 위반 메시지 |
| ---- | ---------- |
| `ParseError` / `TokenError` 발생 | `"SQL 파싱 실패: {에러 상세}"` |
| 파싱 결과 빈 리스트 | `"빈 SQL 문"` |
| 2개 이상의 문장 감지 | `"다중 SQL 문 감지 — 단일 SELECT만 허용"` |

### 2.2 Phase 2: SELECT 문 타입 확인

**목적**: 파싱된 AST의 루트 노드가 `exp.Select`인지 확인한다. SELECT가 아닌 DML/DDL 문은 즉시 거부된다.

```python
parsed = parsed_list[0]

if not isinstance(parsed, exp.Select):
    # REJECT — "SELECT 문만 허용됩니다. 감지된 유형: {타입명}"
```

이 Phase에서 `INSERT INTO ... SELECT`, `CREATE TABLE AS SELECT` 같은 패턴도 루트 노드 타입이 `Insert`, `Create`이므로 정확히 거부된다.

### 2.3 Phase 3: AST 노드 순회 -- 금지 노드 타입 검출

**목적**: AST 트리 전체를 순회하며 금지된 노드 타입이 포함되어 있는지 검사한다. 문자열 패턴 매칭이 아닌 AST 노드 타입을 검사하므로, 컬럼명에 `insert`나 `delete` 같은 단어가 포함되어도 오탐이 발생하지 않는다.

```python
# 금지 AST 노드 타입 정의
_FORBIDDEN_TYPES = (
    exp.Insert,     # INSERT 문
    exp.Update,     # UPDATE 문
    exp.Delete,     # DELETE 문
    exp.Drop,       # DROP TABLE / INDEX 등
    exp.Create,     # CREATE TABLE / INDEX 등
    exp.Alter,      # ALTER TABLE 등
    exp.Grant,      # GRANT / REVOKE 권한
    exp.Command,    # EXEC, EXECUTE, TRUNCATE 등 시스템 명령
    exp.Merge,      # MERGE / UPSERT
)

# AST 전체 순회
for node in parsed.walk():
    if isinstance(node, tuple):
        node = node[0]
    if isinstance(node, _FORBIDDEN_TYPES):
        violations.append(f"금지된 SQL 연산: {type(node).__name__}")
```

**키워드 블랙리스트 대비 장점**:

| 기존 키워드 방식 문제 | AST 노드 방식 해결 |
| --------------------- | ------------------- |
| `SELECT insert_date FROM ...` 오탐 | 컬럼명은 `Column` 노드이므로 무시됨 |
| `SELECT "DELETE" AS label` 오탐 | 문자열 리터럴은 `Literal` 노드이므로 무시됨 |
| 주석 안 키워드 오탐 (`-- DROP TABLE`) | 주석은 파싱 단계에서 제거됨 |
| 대소문자 변형 우회 | AST 노드 타입은 대소문자 무관 |

### 2.4 Phase 4: 구조적 제한 검사

**목적**: 쿼리 복잡도를 제한하여 성능 사고를 방지한다. JOIN 개수와 서브쿼리 중첩 깊이를 검사한다.

```python
# JOIN 개수 검사 — exp.Join 노드를 find_all()로 카운트
join_count = self._measure_join_count(parsed)  # len(list(ast.find_all(exp.Join)))
if join_count > config.max_join_depth:
    violations.append(f"JOIN 깊이 초과: {join_count} > {config.max_join_depth}")

# 서브쿼리 중첩 깊이 검사 — 재귀 depth 계산 (단순 카운트가 아님)
sq_depth = self._measure_subquery_depth(parsed)
if sq_depth > config.max_subquery_depth:
    violations.append(f"서브쿼리 깊이 초과: {sq_depth} > {config.max_subquery_depth}")
```

**서브쿼리 깊이 계산 방식**: AST 트리를 재귀 순회하며 `exp.Subquery` 노드를 만날 때마다 깊이를 1 증가시킨다. 단순 노드 카운트가 아닌 실제 중첩 depth를 계산한다.

```text
SELECT * FROM (SELECT * FROM (SELECT 1))
                ↑ depth=1      ↑ depth=2    → 최종 depth = 2
```

**제약 기본값** (`GuardConfig`):

| 제약 | 기본값 | 근거 |
| ---- | ------ | ---- |
| `max_join_depth` | 5 | 5개 이상 JOIN은 대부분 비효율적 쿼리 |
| `max_subquery_depth` | 3 | 3단계 이상 중첩은 성능 저하 유발 |

### 2.5 Phase 5: 화이트리스트 테이블 검증

**목적**: SQL에서 참조하는 테이블이 허용 목록에 포함되는지 확인한다. 허용되지 않은 테이블 접근을 차단하여 데이터 격리를 보장한다.

```python
# config.allowed_tables가 None이면 이 Phase를 건너뜀 (검사 안 함)
if config.allowed_tables is not None:
    # AST에서 모든 exp.Table 노드를 추출 → 테이블 이름 소문자 집합
    referenced = self._extract_referenced_tables(parsed)
    allowed_set = {t.lower() for t in config.allowed_tables}
    unauthorized = referenced - allowed_set

    if unauthorized:
        # REJECT — "허용되지 않은 테이블: {테이블명, ...}"
```

**동작 방식**:

- `_extract_referenced_tables()`가 AST에서 `exp.Table` 노드를 모두 찾아 이름을 소문자로 추출한다.
- `allowed_tables`도 소문자로 변환하여 대소문자 무관 비교를 수행한다.
- NL2SQL 파이프라인에서 스키마 카탈로그에 있는 테이블만 `GuardConfig.allowed_tables`로 전달한다.
- `allowed_tables`가 `None`이면 테이블 검증을 건너뛴다 (개발/테스트 환경 대응).

### 2.6 Phase 6: LIMIT 자동 삽입

**목적**: LIMIT 절이 없는 쿼리에 자동으로 LIMIT을 추가하여 대량 데이터 반환을 방지한다. 이 Phase는 거부가 아닌 자동 수정이므로, 결과 상태가 `FIX`가 된다.

```python
fixed_ast = parsed.copy()

if not fixed_ast.args.get("limit"):
    # sqlglot의 .limit() 메서드로 AST 수준에서 LIMIT 추가
    fixed_ast = fixed_ast.limit(config.row_limit)
    fixes.append(f"LIMIT {config.row_limit} 자동 추가")

# AST → SQL 문자열 변환 (방언 유지)
fixed_sql = fixed_ast.sql(dialect=config.dialect)

# LIMIT 추가됨 → FIX / 변경 없음 → PASS
```

**기본 LIMIT**: `row_limit = 1000` (GuardConfig 기본값)

> **참고**: 기존 문자열 연결 방식(`sql + " LIMIT 1000"`)이 아닌 AST의 `.limit()` 메서드를 사용한다. 이 방식은 이미 LIMIT이 있는 쿼리에서 중복 추가를 방지하고, 최종 SQL을 `fixed_ast.sql(dialect=...)` 로 생성하여 방언 호환성을 보장한다.

---

## 3. 검증 흐름 전체

`SQLGuard` 클래스의 `guard_sql()` 메서드가 6개 Phase를 순서대로 실행한다. 동기 메서드이며, 싱글톤 인스턴스(`sql_guard`)를 통해 호출된다.

```python
class SQLGuard:
    def guard_sql(self, sql_query: str, config: GuardConfig | None = None) -> GuardResult:
        if config is None:
            config = GuardConfig()

        violations: list[str] = []

        # Phase 1: AST 파싱 + 멀티스테이트먼트 감지
        parsed_list = sqlglot.parse(sql_query, dialect=config.dialect)
        parsed_list = [p for p in parsed_list if p is not None]
        if not parsed_list:
            return GuardResult(status="REJECT", sql=sql_query, violations=["빈 SQL 문"])
        if len(parsed_list) > 1:
            return GuardResult(status="REJECT", sql=sql_query,
                               violations=["다중 SQL 문 감지 — 단일 SELECT만 허용"])

        parsed = parsed_list[0]

        # Phase 2: SELECT 문 타입 확인
        if not isinstance(parsed, exp.Select):
            return GuardResult(status="REJECT", sql=sql_query,
                               violations=[f"SELECT 문만 허용됩니다. 감지된 유형: {type(parsed).__name__}"])

        # Phase 3: AST 노드 순회 — 금지 노드 타입 검출
        for node in parsed.walk():
            if isinstance(node, tuple):
                node = node[0]
            if isinstance(node, _FORBIDDEN_TYPES):
                violations.append(f"금지된 SQL 연산: {type(node).__name__}")
        if violations:
            return GuardResult(status="REJECT", sql=sql_query, violations=violations)

        # Phase 4: 구조적 제한 (JOIN 개수, 서브쿼리 깊이)
        join_count = self._measure_join_count(parsed)
        if join_count > config.max_join_depth:
            violations.append(f"JOIN 깊이 초과: {join_count} > {config.max_join_depth}")
        sq_depth = self._measure_subquery_depth(parsed)
        if sq_depth > config.max_subquery_depth:
            violations.append(f"서브쿼리 깊이 초과: {sq_depth} > {config.max_subquery_depth}")
        if violations:
            return GuardResult(status="REJECT", sql=sql_query, violations=violations)

        # Phase 5: 화이트리스트 테이블 검증
        if config.allowed_tables is not None:
            referenced = self._extract_referenced_tables(parsed)
            allowed_set = {t.lower() for t in config.allowed_tables}
            unauthorized = referenced - allowed_set
            if unauthorized:
                return GuardResult(status="REJECT", sql=sql_query,
                                   violations=[f"허용되지 않은 테이블: {', '.join(sorted(unauthorized))}"])

        # Phase 6: LIMIT 자동 삽입
        fixes: list[str] = []
        fixed_ast = parsed.copy()
        if not fixed_ast.args.get("limit"):
            fixed_ast = fixed_ast.limit(config.row_limit)
            fixes.append(f"LIMIT {config.row_limit} 자동 추가")
        fixed_sql = fixed_ast.sql(dialect=config.dialect)

        if fixes:
            return GuardResult(status="FIX", sql=fixed_sql, fixes=fixes)
        return GuardResult(status="PASS", sql=fixed_sql)

# 싱글톤 인스턴스
sql_guard = SQLGuard()
```

---

## 4. 설정 모델

`GuardConfig`는 Pydantic `BaseModel`로 정의되며, 호출 시 커스터마이즈할 수 있다. `None`을 전달하면 기본값이 사용된다.

```python
class GuardConfig(BaseModel):
    dialect: str = "postgres"                    # SQL 방언
    max_join_depth: int = 5                      # JOIN 개수 상한
    max_subquery_depth: int = 3                  # 서브쿼리 중첩 깊이 상한
    row_limit: int = 1000                        # LIMIT 자동 추가 기준
    allowed_tables: list[str] | None = None      # 허용 테이블 (None이면 검사 안 함)
```

---

## 5. 결과 모델

`GuardResult`는 SQL Guard 검증의 반환 타입이다. `guard_sql()` 메서드가 항상 이 모델을 반환하며, 호출자는 `status` 필드로 분기 처리한다.

```python
class GuardResult(BaseModel):
    """SQL 검증 결과. 기존 API 계약 유지."""
    status: str          # "PASS" | "FIX" | "REJECT"
    sql: str             # 원본 또는 수정된 SQL
    violations: list[str] = []   # REJECT 시 위반 사유 목록
    fixes: list[str] = []       # FIX 시 자동 수정 내역 목록
```

**필드 설명**:

| 필드 | 타입 | 설명 |
| ---- | ---- | ---- |
| `status` | `str` | 검증 결과 상태. `"PASS"` (안전, 변경 없음), `"FIX"` (자동 수정 적용됨), `"REJECT"` (위험, 실행 불가) |
| `sql` | `str` | 최종 SQL 문자열. `PASS`/`FIX`이면 실행 가능한 SQL, `REJECT`이면 원본 SQL |
| `violations` | `list[str]` | `REJECT` 시 위반 사유 목록. `PASS`/`FIX`이면 빈 리스트 |
| `fixes` | `list[str]` | `FIX` 시 자동 수정 내역. 예: `["LIMIT 1000 자동 추가"]` |

**사용 예시**:

```python
result = sql_guard.guard_sql("SELECT * FROM orders", config)

if result.status == "PASS":
    execute(result.sql)
elif result.status == "FIX":
    log_fixes(result.fixes)
    execute(result.sql)
elif result.status == "REJECT":
    notify_user(result.violations)
```

---

## 6. 에러 처리

> **참고: 코드 독스트링과 문서 Phase 수 차이** -- 소스 코드(`sql_guard.py`)의 모듈 독스트링은 검증 단계를 간략하게 기술하며, Phase 2(SELECT 타입 확인)와 Phase 3(금지 노드 검출)을 하나의 "AST 검증" 단계로 묶어 5단계로 설명할 수 있다. 본 문서에서는 각 Phase의 목적과 거부 조건을 명확히 분리하기 위해 6단계로 나누어 기술한다. 코드의 실제 실행 흐름은 본 문서의 6단계와 동일하다.

### 6.1 검증 실패 시 사용자 응답

| 실패 유형 | 사용자 메시지 | 내부 처리 |
| --------- | ------------- | --------- |
| 비-SELECT 문 감지 | "데이터 조회(SELECT)만 가능합니다" | 로깅 + 차단 |
| 파싱 실패 | "SQL 생성에 문제가 발생했습니다. 다시 질문해주세요" | 재생성 시도 (ReAct) |
| 금지 노드 타입 | "데이터 변경 작업은 허용되지 않습니다" | 로깅 + 차단 |
| JOIN/서브쿼리 초과 | "너무 복잡한 쿼리입니다. 질문을 나눠주세요" | 로깅 + 차단 |
| 화이트리스트 위반 | "해당 데이터에 접근 권한이 없습니다" | 보안 로깅 + 차단 |

### 6.2 ReAct에서의 검증 실패 처리

ReAct 파이프라인에서는 검증 실패 시 **Fix 단계**로 분기하여 LLM에게 수정을 요청한다:

```text
Generate → Validate → [REJECT] → Fix → Validate → [PASS] → Execute
                                    ↑              │
                                    └──[REJECT]────┘ (최대 3회)
```

---

## 결정 사항

| 결정 | 근거 |
| ---- | ---- |
| 6단계 AST 기반 방어 채택 | 단일 계층은 우회 가능, 다층 방어로 안전성 확보 |
| AST 노드 타입 검사 | 키워드 블랙리스트는 오탐/미탐 문제 있음, AST 노드 타입은 정밀하고 우회 불가 |
| SQLGlot 사용 | AST 기반 정밀 분석 가능 ([ADR-003](../99_decisions/ADR-003-sqlglot-validation.md)) |
| 자동 보정 포함 (Phase 6) | 사소한 문제(LIMIT 누락)로 전체 요청 실패는 비효율적 |
| ReAct Fix 루프 | 검증 실패를 LLM 자체 수정 기회로 활용 |

## 금지 사항

- SQL Guard를 우회하는 직접 SQL 실행 경로 금지
- 검증 없이 LLM 생성 SQL을 Target DB에 전달 금지
- `_FORBIDDEN_TYPES` 목록을 런타임에 동적으로 축소하는 것 금지

## 관련 문서

- [07_security/sql-safety.md](../07_security/sql-safety.md): SQL 안전성 정책
- [99_decisions/ADR-003-sqlglot-validation.md](../99_decisions/ADR-003-sqlglot-validation.md): SQLGlot 선택 결정
- [03_backend/sql-execution.md](../03_backend/sql-execution.md): SQL 실행 엔진
