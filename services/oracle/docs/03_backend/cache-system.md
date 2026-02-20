# 캐시 후처리 시스템

## 이 문서가 답하는 질문

- 품질 게이트는 어떤 기준으로 캐시를 승인/거부하는가?
- 백그라운드 워커는 어떤 작업을 수행하는가?
- 값 매핑 캐시는 어떻게 생성되고 유지되는가?
- Enum 캐시 부트스트랩은 무엇인가?

<!-- affects: 05_llm, 06_data -->
<!-- requires-update: 06_data/neo4j-schema.md, 06_data/value-mapping.md -->

---

## 1. 모듈 개요

K-AIR의 `cache_postprocess.py`(1,977줄)과 `enum_cache_bootstrap.py`(513줄)는 NL2SQL의 학습 루프를 구현하는 핵심 모듈이다.

**목적**: SQL 생성 결과를 평가하고, 품질 기준을 충족하는 것만 Synapse 백엔드 그래프 저장소에 영속화하여 향후 유사 질문의 정확도를 높인다.

```
NL2SQL 실행 완료
    │
    ▼ (백그라운드)
┌─────────────────────────────────────────────────────────┐
│ Cache Postprocess Pipeline                               │
│                                                          │
│  ┌───────────┐   ┌───────────┐   ┌──────────────────┐  │
│  │ 1. 품질   │──>│ 2. 쿼리   │──>│ 3. 값 매핑      │  │
│  │    게이트  │   │    영속화  │   │    추출/영속화   │  │
│  │ (LLM심사) │   │ (Synapse) │   │ (Synapse)       │  │
│  └───────────┘   └───────────┘   └──────────────────┘  │
│                                                          │
│  결과: Query 노드, ValueMapping 노드 생성                │
└─────────────────────────────────────────────────────────┘
```

---

## 2. 품질 게이트 상세

### 2.1 심사 프로세스

```python
async def quality_gate(
    question: str,
    sql: str,
    result_preview: list[list],
    column_info: list[ColumnMeta],
    judge_rounds: int = 2,
    conf_threshold: float = 0.90
) -> QualityGateResult:
    """
    LLM 심사관이 SQL 품질을 독립적으로 N회 평가.

    평가 기준:
    1. 질문-SQL 정합성: SQL이 질문의 의도를 정확히 반영하는가?
    2. 결과 합리성: 반환된 데이터가 상식적으로 합리적인가?
    3. SQL 품질: SQL 작성이 효율적이고 정확한가?
    """
```

### 2.2 심사 프롬프트

```python
JUDGE_PROMPT = """
당신은 SQL 품질 심사관입니다.

다음 질문, SQL, 실행 결과를 보고 품질을 평가하세요.

## 질문
{question}

## 생성된 SQL
{sql}

## 실행 결과 (상위 5행)
{result_preview}

## 평가 기준
1. 정합성 (0.0~1.0): SQL이 질문의 의도를 정확히 반영하는가?
2. 합리성 (0.0~1.0): 결과가 상식적으로 합리적인가?
3. 품질 (0.0~1.0): SQL이 효율적이고 올바르게 작성되었는가?

## 응답 형식 (JSON)
{{
    "accuracy": 0.95,
    "reasonableness": 0.90,
    "quality": 0.88,
    "overall": 0.91,
    "reasoning": "설명..."
}}
"""
```

### 2.3 N회 독립 심사

```python
async def _run_judge_rounds(
    question: str,
    sql: str,
    result_preview: list,
    rounds: int = 2
) -> list[JudgeScore]:
    """
    rounds회 독립적으로 LLM 심사 실행.
    - 각 라운드는 서로 다른 temperature로 실행 (다양성 확보)
    - 결과의 평균을 최종 점수로 사용
    """
    scores = []
    for i in range(rounds):
        temperature = 0.3 + (i * 0.2)  # 0.3, 0.5, 0.7...
        score = await _judge_single_round(
            question, sql, result_preview,
            temperature=temperature
        )
        scores.append(score)

    return scores
```

### 2.4 게이트 결정 로직

```python
def _gate_decision(
    scores: list[JudgeScore],
    conf_threshold: float = 0.90
) -> GateDecision:
    """
    N회 심사 결과의 평균 overall 점수로 결정.

    - 평균 >= conf_threshold → APPROVE (캐시 영속화)
    - 평균 >= conf_threshold - 0.1 → PENDING (추가 심사 필요)
    - 평균 < conf_threshold - 0.1 → REJECT (캐시하지 않음)
    """
    avg_overall = sum(s.overall for s in scores) / len(scores)

    if avg_overall >= conf_threshold:
        return GateDecision(status="APPROVE", confidence=avg_overall)
    elif avg_overall >= conf_threshold - 0.1:
        return GateDecision(status="PENDING", confidence=avg_overall)
    else:
        return GateDecision(status="REJECT", confidence=avg_overall)
```

---

## 3. 쿼리 영속화

### 3.1 Neo4j Query 노드 생성

```cypher
// 품질 게이트 APPROVE 시 Neo4j에 영속화
CREATE (q:Query {
    id: $query_id,
    question: $question,
    sql: $sql,
    summary: $summary,
    vector: $question_vector,
    datasource_id: $datasource_id,
    verified: false,
    confidence: $confidence,
    created_at: datetime(),
    judge_scores: $judge_scores
})

// 사용된 테이블과 관계 생성
WITH q
UNWIND $tables_used AS table_name
MATCH (t:Table {name: table_name, datasource_id: $datasource_id})
CREATE (q)-[:USES_TABLE]->(t)
```

### 3.2 유사 쿼리 연결

```cypher
// 기존 유사 쿼리와 SIMILAR_TO 관계 생성
CALL db.index.vector.queryNodes(
    'query_vector',
    5,
    $question_vector
)
YIELD node AS similar, score
WHERE similar.id <> $query_id
  AND score >= 0.85
WITH similar, score
MATCH (q:Query {id: $query_id})
CREATE (q)-[:SIMILAR_TO {score: score}]->(similar)
```

---

## 4. 값 매핑 추출

### 4.1 값 매핑이란

자연어 질문에 포함된 고유명사("본사")를 DB 실제 값("본사영업부" 또는 코드값 "ORG_001")으로 매핑하는 것.

### 4.2 추출 프로세스

```python
async def extract_value_mappings(
    question: str,
    sql: str,
    result: ExecutionResult,
    schema_info: SchemaSearchResult
) -> list[ValueMapping]:
    """
    1. LLM에게 SQL에서 사용된 WHERE 조건의 값들 추출 요청
    2. 질문의 원문 표현과 SQL의 실제 값을 매핑
    3. 컬럼 FQN과 연결

    예시:
    질문: "본사 프로젝트 수익"
    SQL:  WHERE org_name = '본사영업부'

    추출 결과:
    - natural_value: "본사"
    - db_value: "본사영업부"
    - column_fqn: "public.organizations.org_name"
    - confidence: 0.95
    """
```

### 4.3 Neo4j ValueMapping 노드 생성

```cypher
MERGE (vm:ValueMapping {
    natural_value: $natural_value,
    column_fqn: $column_fqn,
    datasource_id: $datasource_id
})
ON CREATE SET
    vm.db_value = $db_value,
    vm.confidence = $confidence,
    vm.created_at = datetime(),
    vm.source = 'auto_extract'
ON MATCH SET
    vm.confidence = CASE
        WHEN $confidence > vm.confidence THEN $confidence
        ELSE vm.confidence
    END,
    vm.updated_at = datetime()

// 컬럼과 관계 연결
WITH vm
MATCH (c:Column {fqn: $column_fqn})
MERGE (vm)-[:MAPPED_VALUE]->(c)
```

---

## 5. Enum 캐시 부트스트랩

### 5.1 목적

테이블의 카테고리/상태 컬럼(예: process_type, status)의 고유 값을 미리 캐싱하여, NL2SQL 시 값 매핑 정확도를 높인다.

### 5.2 부트스트랩 프로세스

```python
# enum_cache_bootstrap.py (513줄) 기반
async def bootstrap_enum_values(datasource: DataSource):
    """
    서버 시작 시 실행되는 Enum 값 캐싱 프로세스.

    1. Synapse Graph API로 Enum 후보 컬럼 탐색
       - dtype이 VARCHAR/CHAR/TEXT인 컬럼
       - description에 "코드", "유형", "상태" 등 키워드 포함
    2. 각 컬럼의 DISTINCT 값 조회 (Target DB)
       - SELECT DISTINCT {column} FROM {table} LIMIT 100
    3. 값이 100개 이하면 Enum으로 판단
    4. ValueMapping 노드로 Synapse 백엔드 그래프에 저장
    """
```

### 5.3 부트스트랩 설정

| 설정 | 값 | 설명 |
|------|-----|------|
| 실행 시점 | 서버 시작 시 | `@app.on_event("startup")` |
| Enum 최대 값 수 | 100 | 100개 초과 시 Enum이 아닌 것으로 판단 |
| 대상 dtype | VARCHAR, CHAR, TEXT | 숫자/날짜 컬럼은 제외 |
| 배치 크기 | 50 | 한 번에 처리하는 컬럼 수 |

### 5.4 Enum 캐시 갱신

```python
async def refresh_enum_cache(
    datasource: DataSource,
    table_name: str | None = None
):
    """
    Enum 캐시 수동 갱신.
    - table_name 지정 시: 해당 테이블 컬럼만 갱신
    - table_name 미지정 시: 전체 갱신
    """
```

---

## 6. 백그라운드 워커 관리

### 6.1 워커 라이프사이클

```python
# main.py
@app.on_event("startup")
async def startup():
    # Enum 캐시 부트스트랩 (비동기 백그라운드)
    asyncio.create_task(bootstrap_enum_values(config.datasource))

@app.on_event("shutdown")
async def shutdown():
    # 진행 중인 캐시 작업 완료 대기
    await cache_postprocessor.shutdown(timeout=30)
    # 커넥션 풀 종료
    await sql_executor.close_all()
```

### 6.2 에러 격리

| 워커 | 에러 전파 | 처리 |
|------|----------|------|
| 캐시 후처리 | 사용자 요청에 전파 안 됨 | 로그 기록, 다음 요청 시 재시도 |
| Enum 부트스트랩 | 서비스 시작에 전파 안 됨 | 로그 기록, 부분 실패 허용 |
| 이벤트 스케줄러 | 서비스에 전파 안 됨 | 로그 기록, 다음 스케줄에 재시도 |

---

## 결정 사항

| 결정 | 근거 | 관련 ADR |
|------|------|---------|
| 2회 LLM 심사 | 비용과 정확도의 균형 | [ADR-005](../99_decisions/ADR-005-quality-gate.md) |
| 신뢰도 0.90 임계값 | 거짓 캐시의 피해가 캐시 미스보다 큼 | [ADR-005](../99_decisions/ADR-005-quality-gate.md) |
| Enum 100개 제한 | 값이 너무 많으면 범주형이 아님 | - |
| 백그라운드 에러 격리 | 캐시 실패가 사용자 요청을 실패시키면 안 됨 | - |

## 관련 문서

- [06_data/neo4j-schema.md](../06_data/neo4j-schema.md): Query, ValueMapping 노드 상세
- [06_data/value-mapping.md](../06_data/value-mapping.md): 값 매핑 전략
- [99_decisions/ADR-005-quality-gate.md](../99_decisions/ADR-005-quality-gate.md): 품질 게이트 결정
- Core 성능·모니터링 종합 (`services/core/docs/08_operations/performance-monitoring.md`): 캐시 히트율 메트릭, 멀티레이어 캐시 아키텍처, Redis 모니터링
