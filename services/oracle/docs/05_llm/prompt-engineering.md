# SQL 생성 프롬프트 설계

## 이 문서가 답하는 질문

- SQL 생성 프롬프트는 어떤 구조로 구성되는가?
- 프롬프트에 포함되는 정보는 무엇인가?
- 프롬프트 인젝션은 어떻게 방어하는가?
- 비즈니스 프로세스 인텔리전스 도메인 특화 프롬프트 규칙은?

<!-- affects: 01_architecture, 07_security -->
<!-- requires-update: 03_backend/graph-search.md -->

---

## 1. 프롬프트 구조 개요

K-AIR `prompt.py`(112줄) 기반. SQL 생성 프롬프트는 **5개 섹션**으로 구성된다.

```
┌─────────────────────────────────────────────────────┐
│  System Prompt                                       │
│  ┌─────────────────────────────────────────────────┐│
│  │ Section 1: 역할 정의                             ││
│  │ "당신은 {dialect} SQL 전문가입니다"               ││
│  ├─────────────────────────────────────────────────┤│
│  │ Section 2: 규칙                                  ││
│  │ SELECT만, LIMIT 필수, 별칭 AS 필수 등            ││
│  ├─────────────────────────────────────────────────┤│
│  │ Section 3: 스키마 (DDL)                          ││
│  │ CREATE TABLE ... (graph_search 결과)             ││
│  ├─────────────────────────────────────────────────┤│
│  │ Section 4: 값 매핑                               ││
│  │ "본사" → "본사영업부"                             ││
│  ├─────────────────────────────────────────────────┤│
│  │ Section 5: 참고 쿼리 (캐시)                      ││
│  │ 유사 질문의 기존 검증 SQL                         ││
│  └─────────────────────────────────────────────────┘│
│                                                      │
│  User Prompt                                         │
│  ┌─────────────────────────────────────────────────┐│
│  │ "다음 질문에 대한 SQL을 작성하세요: {question}"   ││
│  └─────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────┘
```

---

## 2. 각 섹션 상세

### 2.1 Section 1: 역할 정의

```python
ROLE_PROMPT = """
당신은 {dialect} SQL 전문가입니다.
주어진 데이터베이스 스키마와 사용자 질문을 기반으로
정확하고 효율적인 SQL 쿼리를 작성합니다.

도메인: 비즈니스 프로세스 인텔리전스 데이터
"""
```

**역할 정의 설계 원칙**:
- 구체적인 전문 분야 명시 (비즈니스 프로세스 인텔리전스)
- SQL 방언 명시 (PostgreSQL/MySQL)
- 기대 출력 형태 명시 (SQL 쿼리)

### 2.2 Section 2: 규칙

```python
RULES_PROMPT = """
## 필수 규칙

1. SELECT 문만 작성합니다. INSERT, UPDATE, DELETE는 절대 사용하지 마세요.
2. 결과는 반드시 LIMIT {row_limit}로 제한합니다.
3. 테이블과 컬럼 이름은 스키마에 있는 것만 정확히 사용합니다.
4. 별칭(alias)은 반드시 AS 키워드를 사용합니다.
5. 날짜 필터는 명시적 형변환을 사용합니다:
   - PostgreSQL: EXTRACT(YEAR FROM date_column) = 2024
   - MySQL: YEAR(date_column) = 2024
6. 집계 쿼리(COUNT, SUM, AVG)는 반드시 GROUP BY를 포함합니다.
7. NULL 비교는 IS NULL / IS NOT NULL을 사용합니다 (= NULL 금지).
8. 문자열 비교는 대소문자를 고려합니다.
9. JOIN은 EXPLICIT JOIN 구문을 사용합니다 (WHERE 절 JOIN 금지).
10. 서브쿼리보다 JOIN을 우선 사용합니다.

## 금지 사항

- 시스템 테이블 접근 금지 (information_schema, pg_catalog 등)
- 위험 함수 사용 금지 (SLEEP, BENCHMARK, LOAD_FILE 등)
- 주석(-- 또는 /* */) 포함 금지
- 여러 개의 SQL 문 작성 금지 (세미콜론으로 분리된 다중 문)

## 출력 형식

SQL 쿼리만 출력합니다. 설명이나 마크다운 코드 블록은 포함하지 마세요.
"""
```

### 2.3 Section 3: 스키마 (DDL)

```python
def format_schema_as_ddl(
    tables: list[TableInfo],
    columns: list[ColumnInfo],
    fk_paths: list[FKPath]
) -> str:
    """
    그래프 검색 결과를 CREATE TABLE DDL 형태로 포맷팅.

    예시 출력:
    ```
    CREATE TABLE process_metrics (
        metric_id BIGINT PRIMARY KEY,           -- 지표 고유 ID
        org_id INTEGER NOT NULL,                -- 조직 ID (FK: organizations.org_id)
        process_name VARCHAR(100),              -- 프로세스 이름
        measured_date DATE,                     -- 측정일
        status VARCHAR(20),                     -- 상태 (SUCCESS/FAILED/...)
        target_org VARCHAR(100),                -- 대상 조직명
        total_value DECIMAL(15,2)               -- 총 금액 (원)
    );

    CREATE TABLE organizations (
        org_id INTEGER PRIMARY KEY,             -- 조직 ID
        org_name VARCHAR(100),                  -- 조직명
        region VARCHAR(50)                      -- 지역
    );

    -- FK 관계: process_metrics.org_id -> organizations.org_id
    ```
    """
    ddl_parts = []
    for table in tables:
        cols = [c for c in columns if c.table_name == table.name]
        col_lines = []
        for col in cols:
            nullable = "" if col.nullable else " NOT NULL"
            pk = " PRIMARY KEY" if col.is_primary_key else ""
            comment = f"  -- {col.description}" if col.description else ""
            col_lines.append(
                f"    {col.name} {col.data_type}{nullable}{pk},{comment}"
            )

        ddl = f"CREATE TABLE {table.name} (\n"
        ddl += "\n".join(col_lines)
        ddl += "\n);"
        ddl_parts.append(ddl)

    # FK 관계 주석 추가
    for fk in fk_paths:
        ddl_parts.append(
            f"-- FK: {fk.from_table}.{fk.from_column} -> "
            f"{fk.to_table}.{fk.to_column}"
        )

    return "\n\n".join(ddl_parts)
```

### 2.4 Section 4: 값 매핑

```python
def format_value_mappings(mappings: list[ValueMapping]) -> str:
    """
    자연어 → DB 값 매핑 정보를 프롬프트에 포함.

    예시 출력:
    ## 값 매핑 (자연어 표현 → 데이터베이스 실제 값)
    - "본사" → organizations.org_name = '본사영업부'
    - "성공" → process_metrics.status = 'SUCCESS'
    - "실패" → process_metrics.status = 'FAILED'
    """
    if not mappings:
        return ""

    lines = ["## 값 매핑 (자연어 표현 -> 데이터베이스 실제 값)"]
    for m in mappings:
        lines.append(
            f'- "{m.natural_value}" -> {m.column_fqn} = \'{m.db_value}\''
        )
    return "\n".join(lines)
```

### 2.5 Section 5: 참고 쿼리

```python
def format_cached_queries(queries: list[CachedQuery]) -> str:
    """
    유사 질문의 기존 검증 SQL을 참고 정보로 제공.

    예시 출력:
    ## 참고: 유사 질문의 검증된 SQL
    질문: "2023년 총 프로젝트 수익은?"
    SQL: SELECT SUM(revenue) FROM project_financials
         WHERE EXTRACT(YEAR FROM fiscal_date) = 2023
    (유사도: 0.92)
    """
    if not queries:
        return ""

    lines = ["## 참고: 유사 질문의 검증된 SQL"]
    for q in queries:
        lines.append(f"질문: \"{q.question}\"")
        lines.append(f"SQL: {q.sql}")
        lines.append(f"(유사도: {q.similarity_score:.2f})")
        lines.append("")
    return "\n".join(lines)
```

---

## 3. 프롬프트 조립

```python
# prompt.py 기반
def build_sql_prompt(
    question: str,
    schema_result: SchemaSearchResult,
    dialect: str = "postgresql",
    row_limit: int = 1000
) -> tuple[str, str]:
    """
    시스템 프롬프트와 사용자 프롬프트를 조립.

    반환: (system_prompt, user_prompt)
    """
    system_prompt = "\n\n".join([
        ROLE_PROMPT.format(dialect=dialect),
        RULES_PROMPT.format(row_limit=row_limit),
        "## 데이터베이스 스키마",
        format_schema_as_ddl(
            schema_result.tables,
            schema_result.columns,
            schema_result.fk_paths
        ),
        format_value_mappings(schema_result.value_mappings),
        format_cached_queries(schema_result.cached_queries)
    ])

    user_prompt = f"다음 질문에 대한 SQL을 작성하세요: {question}"

    return system_prompt, user_prompt
```

---

## 4. 비즈니스 프로세스 인텔리전스 도메인 특화 규칙

```python
DOMAIN_RULES = """
## 비즈니스 프로세스 인텔리전스 도메인 규칙

1. 프로세스 식별 형식: {프로세스유형}-{연도}-{번호} (예: PROC-2024-100)

2. 조직 계층:
   - 본사 > 사업부 > 팀 > 파트
   - 프로세스 성과는 주로 사업부/팀 단위로 측정

3. 프로세스 상태:
   - 시작→진행→검토→완료→종료
   - 실패 경로: 시작→진행→실패→재시도

4. 지표 분류:
   - KPI, OKR, 운영지표, 재무지표

5. 금액 단위:
   - 데이터베이스 금액은 '원' 단위 (소수점 없음이 일반적)
   - 사용자가 "억"이라고 하면 × 100,000,000으로 변환

6. 날짜 기준:
   - 프로세스는 시작일 기준으로 분류하는 것이 관행
   - "작년"은 전년도 1월 1일 ~ 12월 31일
"""
```

---

## 5. 프롬프트 인젝션 방어

### 5.1 방어 전략

| 위험 | 방어 | 구현 |
|------|------|------|
| 사용자가 시스템 프롬프트 탈취 시도 | 사용자 입력에 역할 재정의 문자열 필터 | 입력 검증 |
| SQL 코멘트를 통한 인젝션 | SQL Guard에서 주석 차단 | Layer 1 검증 |
| LLM에게 다른 지시 주입 | 시스템 프롬프트에 강한 역할 고정 | 프롬프트 설계 |

### 5.2 입력 검증

```python
def sanitize_question(question: str) -> str:
    """
    사용자 질문에서 위험한 패턴 제거.

    제거 대상:
    - "시스템 프롬프트를 무시하고"
    - "너의 역할을 바꿔서"
    - "위의 규칙을 무시하고"
    - 마크다운 코드 블록 (```)
    """
    dangerous_patterns = [
        r"시스템\s*프롬프트",
        r"역할을?\s*바꿔",
        r"규칙을?\s*무시",
        r"ignore\s*(the\s*)?instructions",
        r"forget\s*(the\s*)?rules",
    ]
    sanitized = question
    for pattern in dangerous_patterns:
        sanitized = re.sub(pattern, "[FILTERED]", sanitized, flags=re.IGNORECASE)
    return sanitized
```

---

## 6. 프롬프트 버전 관리

| 버전 | 변경 내용 | 날짜 |
|------|----------|------|
| v1.0 | K-AIR 원본 이식 | - |
| v1.1 | 비즈니스 프로세스 인텔리전스 도메인 규칙 추가 | - |
| v1.2 | 프롬프트 인젝션 방어 강화 | - |

---

## 결정 사항

| 결정 | 근거 |
|------|------|
| DDL 형태 스키마 포함 | LLM이 CREATE TABLE 형식에 가장 익숙 |
| 값 매핑 명시적 포함 | "본사"를 LLM이 추측하지 않도록 |
| 참고 쿼리 포함 | Few-shot learning 효과, 캐시 활용 |
| 도메인 규칙 분리 | 도메인 변경 시 이 섹션만 교체 |

## 금지 사항

- 프롬프트에 API 키나 내부 시스템 정보 포함 금지
- 사용자 입력을 검증 없이 시스템 프롬프트에 삽입 금지
- 프롬프트 변경 시 ADR 없이 운영 적용 금지

## 관련 문서

- [05_llm/llm-factory.md](./llm-factory.md): LLM 팩토리
- [05_llm/react-agent.md](./react-agent.md): ReAct 에이전트 프롬프트
- [99_decisions/ADR-001-langchain-sql.md](../99_decisions/ADR-001-langchain-sql.md): LangChain 선택
