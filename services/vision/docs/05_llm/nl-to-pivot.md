# 자연어 → 피벗 쿼리 LangGraph 워크플로우

> **최종 수정일**: 2026-02-19
> **상태**: Draft
> **Phase**: 3.6
> **이식 원본**: K-AIR data-platform-olap-main LangGraph 5노드 워크플로우

---

## 이 문서가 답하는 질문

- 자연어를 피벗 쿼리로 변환하는 LangGraph 워크플로우의 구조는?
- 각 노드의 역할과 입출력은 무엇인가?
- 프롬프트 정책은 어떻게 되는가?
- 실패 시 재시도 로직은?
- Axiom Oracle의 NL→SQL과 어떻게 다른가?

---

## 1. 워크플로우 개요

### 1.1 Vision NL→피벗 vs Oracle NL→SQL

| 항목 | Vision NL→피벗 | Oracle NL→SQL |
|------|---------------|--------------|
| **입력** | 자연어 질의 | 자연어 질의 |
| **출력** | 피벗 파라미터 → 피벗 SQL | 범용 SQL |
| **대상 테이블** | Materialized View (OLAP) | 모든 테이블 (OLTP) |
| **LLM 역할** | 차원/측도/필터 추출 | SQL 직접 생성 |
| **검증** | 큐브 메타데이터 기반 | SQLGlot + 스키마 매칭 |
| **소속** | Vision 모듈 | Oracle 모듈 |

### 1.2 5노드 LangGraph 워크플로우

```
┌─ NL→Pivot LangGraph Workflow ──────────────────────────────────┐
│                                                                 │
│  START                                                          │
│    │                                                            │
│    ▼                                                            │
│  ┌──────────────────────────────────┐                          │
│  │ Node 1: metadata_load            │                          │
│  │ - 사용 가능한 큐브 목록 로드     │                          │
│  │ - 차원/레벨/측도 컨텍스트 구성   │                          │
│  │ - 입력: {}                       │                          │
│  │ - 출력: cube_context (str)       │                          │
│  └──────────┬───────────────────────┘                          │
│             │                                                   │
│             ▼                                                   │
│  ┌──────────────────────────────────┐                          │
│  │ Node 2: nl_to_pivot_params       │                          │
│  │ - LLM: GPT-4o Structured Output │                          │
│  │ - 자연어 → PivotRequest 변환    │                          │
│  │ - 입력: user_query + cube_context│                          │
│  │ - 출력: PivotRequest JSON        │                          │
│  └──────────┬───────────────────────┘                          │
│             │                                                   │
│             ▼                                                   │
│  ┌──────────────────────────────────┐                          │
│  │ Node 3: sql_generation           │                          │
│  │ - PivotRequest → SQL 변환        │                          │
│  │ - pivot_engine.generate_pivot_sql│                          │
│  │ - 입력: PivotRequest             │                          │
│  │ - 출력: sql_string               │                          │
│  └──────────┬───────────────────────┘                          │
│             │                                                   │
│             ▼                                                   │
│  ┌──────────────────────────────────┐                          │
│  │ Node 4: sql_validation           │  ← 실패 시 Node 2로     │
│  │ - SQLGlot 구조 검증              │     재시도 (최대 2회)    │
│  │ - 테이블 화이트리스트 검증       │                          │
│  │ - 위험 키워드 차단               │                          │
│  │ - 입력: sql_string               │                          │
│  │ - 출력: validated_sql | error     │                          │
│  └──────────┬───────────────────────┘                          │
│             │                                                   │
│             ▼                                                   │
│  ┌──────────────────────────────────┐                          │
│  │ Node 5: execution_and_response   │                          │
│  │ - SQL 실행 (타임아웃 30초)       │                          │
│  │ - 결과 → PivotResponse 변환      │                          │
│  │ - 입력: validated_sql             │                          │
│  │ - 출력: PivotResponse             │                          │
│  └──────────┬───────────────────────┘                          │
│             │                                                   │
│             ▼                                                   │
│           END                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. LangGraph 상태 정의

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated

class NLPivotState(TypedDict):
    # Input
    user_query: str
    cube_name: str | None        # Optional cube specification

    # Internal state
    cube_context: str            # Formatted cube metadata for LLM
    pivot_request: dict | None   # Parsed PivotRequest
    generated_sql: str | None    # Generated SQL
    validation_error: str | None # Validation error message
    retry_count: int             # Number of retries

    # Output
    result: dict | None          # Query result
    confidence: float            # LLM confidence
    error: str | None            # Final error if any
```

---

## 3. 각 노드 상세

### 3.1 Node 1: metadata_load

```python
async def metadata_load(state: NLPivotState) -> NLPivotState:
    """
    Load available cube metadata and format as LLM context.
    """
    store = CubeMetadataStore()

    if state.get("cube_name"):
        cubes = [await store.load_cube(state["cube_name"])]
    else:
        cubes = await store.load_all_cubes()

    context_parts = []
    for cube in cubes:
        context_parts.append(f"## Cube: {cube.name}")
        context_parts.append(f"Fact Table: {cube.fact_table}")
        context_parts.append("\n### Dimensions:")
        for dim in cube.dimensions:
            levels = ", ".join(f"{l.name}({l.column})" for l in dim.levels)
            context_parts.append(f"- {dim.name}: [{levels}]")
        context_parts.append("\n### Measures:")
        for m in cube.measures:
            context_parts.append(f"- {m.name}: {m.aggregator}({m.column})")

    return {
        **state,
        "cube_context": "\n".join(context_parts),
        "retry_count": 0,
    }
```

### 3.2 Node 2: nl_to_pivot_params

```python
from langchain_openai import ChatOpenAI

NL_TO_PIVOT_SYSTEM_PROMPT = """
당신은 비즈니스 프로세스 인텔리전스 도메인의 OLAP 분석 전문가입니다.
사용자의 자연어 질의를 피벗 테이블 파라미터로 변환합니다.

## 사용 가능한 큐브 메타데이터
{cube_context}

## 출력 형식 (JSON)
{{
  "cube_name": "큐브 이름",
  "rows": ["Dimension.Level", ...],
  "columns": ["Dimension.Level", ...],
  "measures": ["MeasureName", ...],
  "filters": [
    {{"dimension_level": "Dimension.Level", "operator": "=", "values": [...]}}
  ]
}}

## 규칙
1. rows, columns, measures는 반드시 큐브 메타데이터에 존재하는 이름만 사용
2. "~별"은 rows로, "추이"는 columns의 Time 차원으로 해석
3. "성과율"은 AvgPerformanceRate, "건수"는 CaseCount 측도로 매핑
4. 연도, 유형 등 명시적 필터가 있으면 filters에 추가
5. 명확하지 않은 부분은 가장 합리적인 해석을 선택

## 비즈니스 도메인 용어 매핑
- 구조조정 = CaseType.CaseCategory = "구조조정"
- 성장전략 = CaseType.CaseCategory = "성장전략"
- 제조업 = Organization.Industry = "제조업"
- 핵심 이해관계자 = Stakeholder.StakeholderType = "핵심 이해관계자"
- 금융기관 = Stakeholder.StakeholderType = "금융기관"
"""

async def nl_to_pivot_params(state: NLPivotState) -> NLPivotState:
    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL,
        temperature=0,
        response_format={"type": "json_object"}
    )

    messages = [
        {"role": "system", "content": NL_TO_PIVOT_SYSTEM_PROMPT.format(
            cube_context=state["cube_context"]
        )},
        {"role": "user", "content": state["user_query"]}
    ]

    # If retrying, include the error context
    if state.get("validation_error"):
        messages.append({
            "role": "user",
            "content": f"이전 시도에서 오류 발생: {state['validation_error']}. 수정해서 다시 생성해 주세요."
        })

    response = await llm.ainvoke(messages)
    pivot_params = json.loads(response.content)

    return {
        **state,
        "pivot_request": pivot_params,
        "confidence": estimate_confidence(pivot_params, state["user_query"]),
    }
```

### 3.3 Node 3: sql_generation

```python
async def sql_generation(state: NLPivotState) -> NLPivotState:
    store = CubeMetadataStore()
    cube = await store.load_cube(state["pivot_request"]["cube_name"])

    request = PivotRequest(**state["pivot_request"])
    sql = generate_pivot_sql(request, cube)

    return {**state, "generated_sql": sql}
```

### 3.4 Node 4: sql_validation

```python
async def sql_validation(state: NLPivotState) -> NLPivotState:
    try:
        validate_pivot_sql(state["generated_sql"], ALLOWED_TABLES)
        return {**state, "validation_error": None}
    except SQLValidationError as e:
        return {
            **state,
            "validation_error": str(e),
            "retry_count": state["retry_count"] + 1,
        }
```

### 3.5 Node 5: execution_and_response

```python
async def execution_and_response(state: NLPivotState) -> NLPivotState:
    async with get_session() as db:
        result = await asyncio.wait_for(
            db.execute(text(state["generated_sql"])),
            timeout=settings.QUERY_TIMEOUT
        )
        rows = result.fetchall()
        columns = list(result.keys())

    return {
        **state,
        "result": {
            "columns": columns,
            "rows": [dict(zip(columns, row)) for row in rows],
            "total_rows": len(rows),
        },
        "error": None,
    }
```

---

## 4. 조건부 라우팅

```python
def should_retry(state: NLPivotState) -> str:
    """
    After validation, decide whether to retry or proceed.
    """
    if state.get("validation_error") and state["retry_count"] < 2:
        return "retry"  # Back to Node 2
    elif state.get("validation_error"):
        return "fail"   # Max retries exceeded
    else:
        return "execute" # Proceed to Node 5

# Build graph
graph = StateGraph(NLPivotState)
graph.add_node("metadata_load", metadata_load)
graph.add_node("nl_to_pivot_params", nl_to_pivot_params)
graph.add_node("sql_generation", sql_generation)
graph.add_node("sql_validation", sql_validation)
graph.add_node("execution_and_response", execution_and_response)

graph.add_edge("metadata_load", "nl_to_pivot_params")
graph.add_edge("nl_to_pivot_params", "sql_generation")
graph.add_edge("sql_generation", "sql_validation")

graph.add_conditional_edges(
    "sql_validation",
    should_retry,
    {
        "retry": "nl_to_pivot_params",
        "fail": END,
        "execute": "execution_and_response",
    }
)

graph.add_edge("execution_and_response", END)
graph.set_entry_point("metadata_load")

nl_pivot_workflow = graph.compile()
```

---

## 5. 프롬프트 정책

### 5.1 LLM은 비결정적이다

- 동일한 질의에 다른 피벗 파라미터가 생성될 수 있다
- **검증 노드**가 이를 보완한다 (잘못된 차원/측도 참조 차단)
- 신뢰도(confidence) 점수를 반환하여 UI에서 사용자 확인 유도

### 5.2 금지 사항

- LLM이 SQL을 직접 생성하지 않는다 (피벗 파라미터만 생성)
- LLM 프롬프트에 실제 데이터 포함 금지 (메타데이터만 제공)
- LLM 응답을 검증 없이 실행 금지

### 5.3 LLM 장애 시 Fallback

- LLM API 장애 시 수동 피벗 쿼리 빌더로 안내
- Circuit breaker: 5회 연속 실패 시 30초 차단

---

## 6. 평가 기준

| 지표 | 목표 | 측정 방법 |
|------|------|----------|
| 정확도 | 사용자 의도 반영 90%+ | 수동 평가 (테스트 셋 50개) |
| 응답 시간 | < 5초 (LLM 호출 포함) | 엔드투엔드 latency |
| 재시도율 | < 10% | validation_error 발생률 |
| 안전성 | SQL injection 0건 | SQLGlot 검증 통과율 |

<!-- affects: 02_api/olap-api.md, 01_architecture/olap-engine.md -->
<!-- requires-update: 없음 -->
