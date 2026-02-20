# 값 매핑 캐시

## 이 문서가 답하는 질문

- 값 매핑이란 무엇이고, 왜 필요한가?
- 값 매핑은 어떤 경로로 생성되는가?
- Enum 캐싱과 자동 추출의 차이는?
- 매핑 충돌은 어떻게 해결하는가?

<!-- affects: 03_backend, 05_llm -->
<!-- requires-update: 05_llm/prompt-engineering.md -->

---

## 1. 값 매핑이란

사용자는 자연어로 질문하지만, DB에는 정규화된 값이 저장되어 있다. 값 매핑은 이 간극을 메우는 사전(dictionary)이다.

```
사용자 입력          값 매핑               DB 실제 값
─────────────    ──────────────    ──────────────────
"본사"          →  org_name      → "본사영업부"
"성공"          →  status        → "SUCCESS"
"실패"          →  status        → "FAILED"
"작년"          →  year          → "2023" (현재 기준)
"디지털사업부"   →  org_name      → "디지털사업본부"
```

### 1.1 왜 필요한가

| 문제 | 값 매핑 없이 | 값 매핑 있을 때 |
|------|------------|-------------|
| 약칭/정식 명칭 | LLM이 추측 (오답 가능) | 정확한 매핑 제공 |
| 코드값 | LLM이 코드 체계를 모름 | 코드-의미 매핑 제공 |
| 동의어 | LLM이 하나만 선택 (확률적) | 모든 동의어 매핑 |
| 도메인 관행 | LLM이 도메인 관행을 모름 | 관행 기반 매핑 |

---

## 2. 값 매핑 생성 경로

```
┌──────────────────────────────────────────────────────────┐
│  값 매핑 생성 경로 (3가지)                                │
│                                                           │
│  ┌───────────────────┐                                   │
│  │ 1. Enum Bootstrap │  서버 시작 시                     │
│  │   - DB DISTINCT   │  Target DB에서 고유 값 조회       │
│  │   - 자동 대량 생성 │  confidence: 1.0                  │
│  │   - source: enum  │                                   │
│  └─────────┬─────────┘                                   │
│            │                                              │
│  ┌─────────▼─────────┐                                   │
│  │ 2. Auto Extract   │  NL2SQL 실행 후 (백그라운드)      │
│  │   - SQL WHERE절   │  LLM이 값 매핑 추출               │
│  │   - 품질게이트통과 │  confidence: LLM 판단             │
│  │   - source: auto  │                                   │
│  └─────────┬─────────┘                                   │
│            │                                              │
│  ┌─────────▼─────────┐                                   │
│  │ 3. User Feedback  │  사용자 수동 등록                  │
│  │   - 관리자 입력    │  가장 높은 신뢰도                 │
│  │   - 수정 제안      │  confidence: 1.0                  │
│  │   - source: user   │                                   │
│  └───────────────────┘                                   │
│                                                           │
│  모든 경로 → Neo4j :ValueMapping 노드로 MERGE             │
└──────────────────────────────────────────────────────────┘
```

---

## 3. Enum 캐싱 상세

### 3.1 Enum 후보 선정

```python
async def find_enum_candidates(datasource_id: str) -> list[ColumnInfo]:
    """
    Enum 캐싱 대상 컬럼 탐색.

    조건:
    1. dtype이 VARCHAR, CHAR, TEXT 중 하나
    2. description에 다음 키워드 포함:
       - "코드", "유형", "상태", "구분", "분류"
       - "type", "status", "category", "code"
    3. DISTINCT 값 수 <= 100
    """
```

### 3.2 비즈니스 프로세스 도메인 Enum 예시

| 컬럼 FQN | 자연어 | DB 값 |
|----------|--------|-------|
| `process_metrics.status` | 성공 | SUCCESS |
| `process_metrics.status` | 실패 | FAILED |
| `process_metrics.status` | 진행중 | IN_PROGRESS |
| `process_metrics.status` | 대기 | PENDING |
| `process_metrics.status` | 완료 | COMPLETED |
| `process_metrics.status` | 취소 | CANCELLED |
| `organizations.region` | 수도권 | METROPOLITAN |
| `organizations.region` | 영남권 | YEONGNAM |
| `kpi_results.kpi_type` | 재무지표 | FINANCIAL_KPI |
| `kpi_results.kpi_type` | 운영지표 | OPERATIONAL_KPI |
| `kpi_results.kpi_type` | 성장지표 | GROWTH_KPI |

### 3.3 Enum 캐싱 SQL

```python
async def fetch_enum_values(
    datasource: DataSource,
    table_name: str,
    column_name: str,
    limit: int = 100
) -> list[str]:
    """
    Target DB에서 컬럼의 DISTINCT 값 조회.
    """
    sql = f"""
        SELECT DISTINCT {column_name}
        FROM {table_name}
        WHERE {column_name} IS NOT NULL
        ORDER BY {column_name}
        LIMIT {limit}
    """
    # SQL Guard 적용 (안전한 SQL이지만 규칙 준수)
    result = await sql_executor.execute_sql(sql, datasource)
    return [row[0] for row in result.rows]
```

---

## 4. 자동 추출 상세

### 4.1 추출 프롬프트

```python
VALUE_EXTRACT_PROMPT = """
다음 질문과 SQL을 보고, 질문에서 사용된 자연어 표현이
SQL에서 어떤 DB 값으로 매핑되었는지 추출하세요.

질문: {question}
SQL: {sql}

출력 형식 (JSON 배열):
[
    {{
        "natural_value": "사용자가 사용한 표현",
        "db_value": "SQL에서 사용된 실제 값",
        "column_fqn": "테이블.컬럼 (정확한 FQN)"
    }}
]

추출할 수 없으면 빈 배열을 반환하세요.
"""
```

### 4.2 추출 예시

```
질문: "본사의 2024년 프로세스 성공 건수"
SQL:  SELECT COUNT(*) FROM process_metrics pm
      JOIN organizations o ON pm.org_id = o.org_id
      WHERE o.org_name = '본사영업부'
      AND pm.status = 'SUCCESS'
      AND EXTRACT(YEAR FROM pm.measured_date) = 2024

추출 결과:
[
    {
        "natural_value": "본사",
        "db_value": "본사영업부",
        "column_fqn": "public.organizations.org_name"
    },
    {
        "natural_value": "성공",
        "db_value": "SUCCESS",
        "column_fqn": "public.process_metrics.status"
    }
]
```

---

## 5. 매핑 충돌 해결

### 5.1 동일 자연어, 다른 DB 값

```
"성공" → status = 'SUCCESS'          (confidence: 0.95)
"성공" → result_type = 'SUCCESSFUL'  (confidence: 0.90)
```

**해결**: column_fqn을 포함하여 구분한다. 같은 자연어라도 다른 컬럼이면 별개 매핑이다.

### 5.2 동일 자연어, 같은 컬럼, 다른 DB 값

```
"본사" → org_name = '본사영업부'      (confidence: 0.85)
"본사" → org_name = '본사마케팅부'    (confidence: 0.70)
```

**해결**: confidence가 높은 것을 우선 사용한다. 프롬프트에 "모호한 값은 사용자에게 확인 요청" 규칙을 포함한다.

### 5.3 MERGE 전략

```cypher
MERGE (vm:ValueMapping {
    natural_value: $natural_value,
    column_fqn: $column_fqn,
    datasource_id: $datasource_id
})
ON CREATE SET
    vm.db_value = $db_value,
    vm.confidence = $confidence,
    vm.source = $source,
    vm.created_at = datetime()
ON MATCH SET
    // 더 높은 confidence만 갱신
    vm.db_value = CASE WHEN $confidence > vm.confidence
                       THEN $db_value
                       ELSE vm.db_value END,
    vm.confidence = CASE WHEN $confidence > vm.confidence
                         THEN $confidence
                         ELSE vm.confidence END,
    vm.updated_at = datetime()
```

---

## 결정 사항

| 결정 | 근거 |
|------|------|
| 3가지 생성 경로 | 자동+수동으로 커버리지 최대화 |
| confidence 기반 우선순위 | user(1.0) > enum(1.0) > auto(LLM판단) |
| MERGE 전략 | 중복 방지 + 품질 자동 개선 |
| column_fqn 기반 구분 | 동일 자연어의 다른 의미를 구별 |

## 관련 문서

- [06_data/neo4j-schema.md](./neo4j-schema.md): ValueMapping 노드 상세
- [03_backend/cache-system.md](../03_backend/cache-system.md): Enum 부트스트랩
- [05_llm/prompt-engineering.md](../05_llm/prompt-engineering.md): 프롬프트에 매핑 포함
