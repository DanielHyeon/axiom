# ReAct 에이전트

## 이 문서가 답하는 질문

- ReAct 에이전트의 6단계는 각각 무엇을 하는가?
- 각 단계에서 LLM에게 어떤 프롬프트를 전달하는가?
- 루프 제어(반복/종료/실패)는 어떻게 동작하는가?
- 단일 Ask와 ReAct의 차이점과 사용 기준은?

<!-- affects: 02_api, 01_architecture -->
<!-- requires-update: 02_api/text2sql-api.md -->

---

## 1. ReAct란

**ReAct**(Reasoning + Acting)는 LLM이 **사고(Think)와 행동(Act)을 교대로 반복**하며 복합 문제를 해결하는 패턴이다.

단순 질문("총 프로젝트 수익은?")은 단일 Ask로 충분하지만, 복합 질문("작년 대비 성공률 변동 TOP 5")은 여러 단계의 SQL 실행과 추론이 필요하다. ReAct는 이런 복합 질문을 처리한다.

### 1.1 Ask vs ReAct 선택 기준

| 기준 | Ask (단일) | ReAct (다단계) |
|------|-----------|-------------|
| 질문 복잡도 | 단순 조회, 집계 | 비교, 추세, 다단계 계산 |
| SQL 수 | 1개 | 1~N개 |
| 응답 형태 | JSON | NDJSON 스트림 |
| 지연 시간 | 1~3초 | 5~30초 |
| 예시 | "2024년 총 프로젝트 수익" | "전년 대비 변동률 TOP 5" |

---

## 2. 6단계 상세

```
┌──────────────────────────────────────────────────────────┐
│  ReAct Pipeline (최대 max_iterations 반복)                │
│                                                           │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐             │
│  │ 1.Select │──>│2.Generate│──>│3.Validate│             │
│  │ 테이블   │   │ SQL 생성 │   │ SQL 검증 │             │
│  │ 선택     │   │          │   │          │             │
│  └──────────┘   └──────────┘   └─────┬────┘             │
│                                       │                   │
│                                  PASS │ REJECT            │
│                                       │    │              │
│                                       ▼    ▼              │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐             │
│  │ 6.Triage │<──│5.Quality │<──│  4.Fix   │             │
│  │ 결과분류 │   │ 품질점검 │   │ SQL 수정 │             │
│  └────┬─────┘   └──────────┘   └──────────┘             │
│       │                                                   │
│  ┌────┼───────────────────────────────────┐              │
│  │    ▼                                    │              │
│  │ ┌──────────┐  ┌──────────┐  ┌────────┐ │              │
│  │ │ COMPLETE │  │ CONTINUE │  │  FAIL  │ │              │
│  │ │ 최종응답 │  │ 1로 복귀 │  │ 에러   │ │              │
│  │ └──────────┘  └──────────┘  └────────┘ │              │
│  └─────────────────────────────────────────┘              │
└──────────────────────────────────────────────────────────┘
```

### 2.1 단계 1: Select (테이블 선택)

```python
SELECT_PROMPT = """
## 역할
당신은 데이터베이스 스키마 선택 전문가입니다.

## 맥락
{context}

## 이전 단계 결과
{previous_results}

## 작업
다음 질문에 답하기 위해 필요한 테이블을 선택하세요.

질문: {question}

## 출력 형식 (JSON)
{{
    "reasoning": "이 테이블들이 필요한 이유...",
    "tables": ["table1", "table2"],
    "strategy": "단일 SQL로 가능 | 다단계 SQL 필요"
}}
"""
```

**동작**:
1. 그래프 검색으로 후보 테이블 탐색
2. LLM에게 필요한 테이블 선택 요청
3. FK 경로 자동 포함
4. 이전 반복의 결과를 맥락으로 제공

### 2.2 단계 2: Generate (SQL 생성)

```python
GENERATE_PROMPT = """
## 역할
당신은 {dialect} SQL 전문가입니다.

## 스키마
{schema_ddl}

## 값 매핑
{value_mappings}

## 이전 결과
{previous_sql_results}

## 작업
다음 질문(또는 하위 질문)에 대한 SQL을 작성하세요.

질문: {current_question}

## 규칙
{rules}

## 출력
SQL 쿼리만 출력하세요.
"""
```

**동작**:
1. Select 단계에서 선택된 테이블의 스키마를 DDL로 포맷
2. 이전 반복의 SQL 실행 결과를 맥락으로 제공
3. LLM이 현재 단계에 필요한 SQL 생성

### 2.3 단계 3: Validate (SQL 검증)

SQL Guard의 4계층 검증 실행 (상세: [01_architecture/sql-guard.md](../01_architecture/sql-guard.md))

```python
async def validate_step(sql: str, config: GuardConfig) -> ValidateResult:
    result = await guard_sql(sql, config)

    if result.status == "REJECT":
        return ValidateResult(
            passed=False,
            next_step="fix",
            violations=result.violations
        )
    elif result.status == "FIX":
        return ValidateResult(
            passed=True,
            sql=result.sql,  # 자동 수정된 SQL
            fixes=result.fixes
        )
    else:
        return ValidateResult(passed=True, sql=sql)
```

### 2.4 단계 4: Fix (SQL 수정)

검증 실패 시 LLM에게 수정을 요청한다.

```python
FIX_PROMPT = """
## 상황
생성된 SQL이 검증에 실패했습니다.

## 원본 SQL
{original_sql}

## 위반 사항
{violations}

## 작업
위반 사항을 수정한 SQL을 작성하세요.
원래 질문의 의도는 유지하면서 안전성 규칙을 준수해야 합니다.

## 출력
수정된 SQL만 출력하세요.
"""
```

**Fix 루프 제한**: 최대 3회. 3회 수정 실패 시 해당 반복은 실패로 처리.

### 2.5 단계 5: Quality (품질 점검)

SQL 실행 결과의 품질을 점검한다.

```python
QUALITY_PROMPT = """
## 역할
당신은 SQL 결과 품질 심사관입니다.

## 질문
{question}

## SQL
{sql}

## 실행 결과 (상위 10행)
{result_preview}

## 평가 항목
1. 결과가 질문에 대한 답인가?
2. 결과가 합리적인가? (이상치, NULL 과다 등)
3. 추가 데이터가 필요한가?

## 출력 형식 (JSON)
{{
    "score": 0.85,
    "is_complete": false,
    "feedback": "2023년 데이터도 필요합니다",
    "next_question": "2023년 조직별 프로세스 성공률은?"
}}
"""
```

### 2.6 단계 6: Triage (결과 분류/라우팅)

품질 점검 결과에 따라 다음 행동을 결정한다.

```python
async def triage_step(
    quality_result: QualityResult,
    iteration: int,
    max_iterations: int
) -> TriageDecision:
    """
    결정 로직:

    1. is_complete = true AND score >= 0.8
       → COMPLETE: 최종 결과 반환

    2. is_complete = false AND iteration < max_iterations
       → CONTINUE: 다음 반복 (next_question 활용)

    3. is_complete = false AND iteration >= max_iterations
       → FAIL: 최대 반복 도달, 현재까지 결과 반환

    4. score < 0.5
       → FAIL: 품질 미달, 에러 메시지 반환
    """
    if quality_result.is_complete and quality_result.score >= 0.8:
        return TriageDecision(action="COMPLETE")

    if iteration >= max_iterations:
        return TriageDecision(
            action="FAIL",
            reason=f"최대 반복 횟수({max_iterations})에 도달했습니다"
        )

    if quality_result.score < 0.5:
        return TriageDecision(
            action="FAIL",
            reason="결과 품질이 기준에 미달합니다"
        )

    return TriageDecision(
        action="CONTINUE",
        next_question=quality_result.next_question
    )
```

---

## 3. 상태 관리

### 3.1 ReAct 세션 상태

```python
@dataclass
class ReactSession:
    """ReAct 세션 상태."""

    question: str                          # 원본 질문
    datasource_id: str                     # 데이터소스 ID
    iterations: list[ReactIteration] = []  # 반복 이력
    current_iteration: int = 0             # 현재 반복 번호
    max_iterations: int = 5               # 최대 반복 횟수
    status: str = "running"                # running / completed / failed

@dataclass
class ReactIteration:
    """단일 반복의 결과."""

    iteration: int
    question: str                   # 현재 반복의 질문
    selected_tables: list[str]
    generated_sql: str
    validation_result: ValidateResult
    execution_result: ExecutionResult | None
    quality_result: QualityResult | None
    triage_decision: TriageDecision
```

### 3.2 이전 결과의 맥락 전달

각 반복에서 이전 반복의 결과를 맥락으로 제공한다:

```python
def build_previous_context(iterations: list[ReactIteration]) -> str:
    """
    이전 반복의 결과를 맥락 문자열로 변환.

    예시:
    ## 이전 단계 결과

    ### 반복 1
    질문: "2024년 조직별 프로세스 성공률"
    SQL: SELECT org_name, COUNT(CASE WHEN ...) ...
    결과: 15개 행 (디지털사업부: 72%, 영업본부: 68%, ...)
    품질 피드백: "2023년 데이터도 필요합니다"

    ### 반복 2
    질문: "2023년 조직별 프로세스 성공률"
    SQL: SELECT org_name, COUNT(CASE WHEN ...) ...
    결과: 15개 행 (디지털사업부: 65%, 영업본부: 71%, ...)
    """
```

---

## 4. NDJSON 스트리밍

### 4.1 스트림 형식

```python
async def stream_react(session: ReactSession) -> AsyncGenerator[str, None]:
    """
    각 단계의 결과를 NDJSON으로 스트리밍.
    각 줄은 독립적인 JSON 객체.
    """
    for iteration in run_react_loop(session):
        yield json.dumps({
            "step": "select",
            "iteration": iteration.iteration,
            "data": {
                "tables": iteration.selected_tables,
                "reasoning": iteration.select_reasoning
            }
        }) + "\n"

        yield json.dumps({
            "step": "generate",
            "iteration": iteration.iteration,
            "data": {
                "sql": iteration.generated_sql,
                "reasoning": iteration.generate_reasoning
            }
        }) + "\n"

        # ... 나머지 단계도 동일
```

---

## 5. 설정

| 설정 | 기본값 | 설명 |
|------|--------|------|
| `max_iterations` | 5 | ReAct 최대 반복 횟수 |
| `fix_max_retries` | 3 | Fix 단계 최대 재시도 |
| `quality_min_score` | 0.5 | 최소 품질 점수 (미달 시 FAIL) |
| `complete_min_score` | 0.8 | 완료 최소 점수 |
| `select_temperature` | 0.3 | Select 단계 LLM temperature |
| `generate_temperature` | 0.1 | Generate 단계 LLM temperature |
| `quality_temperature` | 0.5 | Quality 단계 LLM temperature |

---

## 결정 사항

| 결정 | 근거 |
|------|------|
| 6단계 분리 | 각 단계의 관심사 분리, 중간 결과 스트리밍 가능 |
| NDJSON 스트리밍 | SSE보다 단순, 각 줄이 독립 JSON이라 파싱 용이 |
| 최대 5회 반복 | 비용 제어, 무한 루프 방지 |
| Quality + Triage 분리 | 평가와 결정을 분리하여 로직 명확화 |

## 관련 문서

- [02_api/text2sql-api.md](../02_api/text2sql-api.md): ReAct API 스펙
- [05_llm/prompt-engineering.md](./prompt-engineering.md): SQL 생성 프롬프트
- [01_architecture/nl2sql-pipeline.md](../01_architecture/nl2sql-pipeline.md): 파이프라인 전체 구조
