# NL2SQL 파이프라인: 5축 벡터 검색 + ReAct 추론

## 이 문서가 답하는 질문

- 5축 벡터 검색이란 무엇이고, 각 축은 왜 필요한가?
- NL2SQL 파이프라인의 각 단계는 구체적으로 무엇을 하는가?
- ReAct 에이전트는 어떤 6단계를 거치는가?
- 기존 쿼리 캐시는 파이프라인에서 어떻게 활용되는가?

<!-- affects: 02_api, 05_llm, 06_data -->
<!-- requires-update: 05_llm/prompt-engineering.md, 03_backend/graph-search.md -->

---

## 1. 파이프라인 전체 구조

### 1.1 단일 요청 (Ask) 파이프라인

```
┌──────────────────────────────────────────────────────────────────────┐
│                     NL2SQL Ask Pipeline (8단계)                      │
│                                                                      │
│  "2024년 매출 성장률이 가장 높은 사업부는?"                             │
│        │                                                             │
│  ┌─────▼─────┐    ┌────────────┐    ┌────────────┐    ┌──────────┐ │
│  │ 1.임베딩  │───>│ 2.그래프   │───>│ 3.스키마   │───>│ 4.SQL    │ │
│  │   생성    │    │   검색     │    │   포맷팅   │    │   생성   │ │
│  │           │    │ (5축벡터)  │    │ (DDL변환)  │    │(LangChain│ │
│  └───────────┘    └────────────┘    └────────────┘    └────┬─────┘ │
│                                                            │        │
│  ┌───────────┐    ┌────────────┐    ┌────────────┐    ┌────▼─────┐ │
│  │ 8.캐싱   │<───│ 7.시각화   │<───│ 6.SQL     │<───│ 5.SQL    │ │
│  │ (품질    │    │   추천     │    │   실행     │    │   검증   │ │
│  │  게이트) │    │            │    │(asyncpg)  │    │(SQLGlot) │ │
│  └───────────┘    └────────────┘    └────────────┘    └──────────┘ │
│                                                                      │
│  출력: {sql, data, columns, chart_type, summary}                    │
└──────────────────────────────────────────────────────────────────────┘
```

### 1.2 ReAct 파이프라인 (다단계 추론)

```
┌──────────────────────────────────────────────────────────────────────┐
│                    ReAct Pipeline (6단계)                             │
│                                                                      │
│  "작년 대비 프로세스 성공률 변동이 큰 조직 TOP 5?"                     │
│        │                                                             │
│  ┌─────▼─────┐    ┌────────────┐    ┌────────────┐                  │
│  │ 1.Select  │───>│ 2.Generate │───>│ 3.Validate │──┐              │
│  │ 테이블    │    │ SQL 생성   │    │ SQL 검증   │  │              │
│  │ 선택      │    │            │    │            │  │              │
│  └───────────┘    └────────────┘    └────────────┘  │              │
│                                                      │              │
│                   ┌─────────────────────────────────┘              │
│                   │                                                  │
│                   ▼                                                  │
│  ┌───────────┐    ┌────────────┐    ┌────────────┐                  │
│  │ 6.Triage  │<───│ 5.Quality  │<───│ 4.Fix      │                  │
│  │ 결과분류  │    │ 품질점검   │    │ SQL수정    │                  │
│  │ +라우팅   │    │            │    │ (필요 시)  │                  │
│  └───────────┘    └────────────┘    └────────────┘                  │
│       │                                                              │
│       ├─ 단일결과 → 즉시 반환                                       │
│       ├─ 다단계필요 → 1단계로 루프 (최대 N회)                        │
│       └─ 실패 → 에러 메시지 + 대안 제안                              │
│                                                                      │
│  출력: NDJSON 스트림 (각 단계별 중간 결과 실시간 전송)                │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 2. 5축 벡터 검색 상세

### 2.1 왜 5축인가?

단일 벡터 유사도 검색은 질문의 다양한 측면을 포착하지 못한다. 5가지 서로 다른 관점에서 검색을 수행하고 결과를 융합하여 정밀도를 높인다.

| 축 | 이름 | 설명 | 사용 근거 |
|----|------|------|----------|
| 1 | **question_vector** | 원본 질문 임베딩 | 직접적 의미 유사도 |
| 2 | **hyde_vector** | HyDE(가상 문서) 임베딩 | 질문 -> 가상 SQL 설명 -> 임베딩, 스키마와의 의미적 다리 역할 |
| 3 | **regex** | 정규표현식 기반 키워드 매칭 | 테이블/컬럼 이름 직접 매칭 (벡터로 못잡는 정확한 명칭) |
| 4 | **intent** | 질문 의도 분류 임베딩 | 집계/필터/비교/추이 등 쿼리 패턴 매칭 |
| 5 | **PRF** | Pseudo Relevance Feedback 임베딩 | 1차 검색 결과 기반 쿼리 보강 (재검색) |

### 2.2 검색 흐름

```
질문: "2024년 매출 성장률이 가장 높은 사업부"
    │
    ├─ 축1: question_vector
    │  embed("2024년 매출 성장률이 가장 높은 사업부")
    │  → Neo4j vector similarity → top_k=10 테이블/컬럼
    │
    ├─ 축2: hyde_vector
    │  LLM("이 질문에 답하는 SQL의 스키마를 설명해줘")
    │  → embed(설명) → Neo4j vector similarity
    │
    ├─ 축3: regex
    │  extract_keywords("매출", "성장률", "사업부")
    │  → Neo4j CONTAINS/REGEX 검색
    │
    ├─ 축4: intent
    │  classify("ranking aggregation, filter by year")
    │  → embed(intent) → Neo4j vector similarity
    │
    └─ 축5: PRF (Pseudo Relevance Feedback)
       축1~4 결과의 상위 문서들로 쿼리 벡터 보강
       → 재검색 (정밀도 향상)

    ▼
  결과 융합 (Reciprocal Rank Fusion)
    │
    ├─ 테이블: [sales_records, departments, ...]
    ├─ 컬럼: [dept_id, dept_name, revenue, fiscal_year, ...]
    └─ FK 경로: departments -> sales_records (dept_id)
```

### 2.3 FK 3홉 그래프 탐색

벡터 검색으로 찾은 테이블을 시작점으로, FK(Foreign Key) 관계를 최대 3홉까지 탐색하여 JOIN에 필요한 중간 테이블을 발견한다.

```cypher
// Synapse 내부 Graph Layer에서 실행되는 Cypher (K-AIR graph_search.py 기반)
MATCH path = (start:Table {name: $table_name})
  -[:HAS_COLUMN]->(:Column)-[:FK_TO]-(:Column)<-[:HAS_COLUMN]-
  (related:Table)
WHERE length(path) <= 3 * 2  // 3홉 (각 홉은 2개의 관계)
RETURN DISTINCT related.name AS related_table,
       [r IN relationships(path) | type(r)] AS path_types
```

> Oracle 서비스는 위 Cypher를 직접 실행하지 않고 Synapse API를 통해 탐색 요청을 전달한다.

**3홉 제한 근거**: K-AIR 운영 데이터 분석 결과, 3홉 이상의 JOIN은 쿼리 복잡도 폭발과 성능 저하를 유발하며, 대부분의 유의미한 관계는 2홉 이내에서 발견됨.

### 2.4 설정값

```python
# graph_search.py 기반 설정
VECTOR_TOP_K = 10       # 각 축 벡터 검색 상위 결과 수
MAX_FK_HOPS = 3         # FK 그래프 탐색 최대 홉 수
SIMILARITY_THRESHOLD = 0.7  # 벡터 유사도 최소 임계값
```

---

## 3. 각 파이프라인 단계 상세

### 3.1 단계 1: 임베딩 생성

```python
# embedding.py (55줄) 기반
async def embed_text(text: str, model: str = "text-embedding-3-small") -> list[float]:
    """
    텍스트를 벡터로 변환.
    - 모델: OpenAI text-embedding-3-small (1536 차원)
    - 대안: Google text-embedding-004, 호환 모델
    """
    response = await openai_client.embeddings.create(
        input=text,
        model=model
    )
    return response.data[0].embedding
```

**입력**: 자연어 질문 (문자열)
**출력**: 1536차원 벡터
**의존**: LLM Factory (프로바이더 추상화)

### 3.2 단계 2: 그래프 검색

```python
# graph_search.py (352줄) 기반
async def search_relevant_schema(
    question: str,
    question_vector: list[float],
    datasource_id: str,
    top_k: int = 10,
    max_fk_hops: int = 3
) -> SchemaSearchResult:
    """
    5축 벡터 검색 + FK 그래프 탐색.

    반환:
    - tables: 관련 테이블 목록 (이름, 설명, 점수)
    - columns: 관련 컬럼 목록 (테이블, 이름, 타입, nullable, 설명)
    - fk_paths: FK 경로 목록 (JOIN 힌트)
    - cached_queries: 유사 질문의 기존 검증 쿼리
    - value_mappings: 자연어 -> DB 값 매핑
    """
```

**입력**: 질문, 벡터, 데이터소스 ID
**출력**: `SchemaSearchResult` (테이블, 컬럼, FK 경로, 캐시 쿼리, 값 매핑)
**의존**: Neo4j AsyncSession

### 3.3 단계 3: 스키마 포맷팅

검색된 테이블/컬럼을 LLM이 이해할 수 있는 DDL 형태로 포맷팅한다.

```sql
-- 포맷팅 결과 예시
CREATE TABLE process_metrics (
    metric_id BIGINT PRIMARY KEY,         -- 지표 고유 ID
    org_id INTEGER NOT NULL,              -- 조직 ID (FK: organizations.org_id)
    process_name VARCHAR(100),            -- 프로세스 이름
    measured_date DATE,                   -- 측정일
    status VARCHAR(20),                   -- 상태 (SUCCESS/FAILED/...)
    target_org VARCHAR(100),              -- 대상 조직명
    total_value DECIMAL(15,2)             -- 총 금액 (원)
);

CREATE TABLE organizations (
    org_id INTEGER PRIMARY KEY,           -- 조직 ID
    org_name VARCHAR(100),                -- 조직명
    region VARCHAR(50)                    -- 지역
);

-- FK 관계: process_metrics.org_id -> organizations.org_id
```

### 3.4 단계 4: SQL 생성

```python
# prompt.py (112줄) 기반 LangChain 프롬프트 구성
system_prompt = """
당신은 {dialect} SQL 전문가입니다.
주어진 스키마와 질문을 기반으로 정확한 SQL 쿼리를 작성하세요.

규칙:
1. SELECT 문만 사용 (INSERT, UPDATE, DELETE 금지)
2. 결과는 LIMIT {row_limit}로 제한
3. 테이블/컬럼 이름을 정확히 사용 (별칭 사용 시 AS 키워드 필수)
4. 날짜 필터는 명시적 형변환 사용
5. 집계 쿼리는 반드시 GROUP BY 포함

스키마:
{schema_ddl}

값 매핑:
{value_mappings}

기존 유사 쿼리 (참고용):
{cached_queries}
"""
```

**입력**: 스키마 DDL, 질문, 값 매핑, 캐시 쿼리
**출력**: SQL 문자열
**의존**: LLM Factory (GPT-4o)

### 3.5 단계 5: SQL 검증

SQL Guard에 의한 다층 검증 (상세: [sql-guard.md](./sql-guard.md))

```python
# sql_guard.py (153줄) 기반
def validate_sql(sql: str) -> GuardResult:
    """
    검증 항목:
    1. DML 차단 (INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE)
    2. 위험 함수 차단 (SLEEP, BENCHMARK, LOAD_FILE 등)
    3. JOIN 깊이 <= max_join_depth (기본 5)
    4. 서브쿼리 깊이 <= max_subquery_depth (기본 3)
    5. LIMIT 존재 확인 (없으면 자동 추가)
    6. SQLGlot 파싱 성공 여부
    """
```

### 3.6 단계 6: SQL 실행

```python
# sql_exec.py (380줄) 기반
async def execute_sql(
    sql: str,
    datasource: DataSource,
    timeout: int = 30,
    max_rows: int = 10000
) -> ExecutionResult:
    """
    비동기 SQL 실행.
    - asyncpg (PostgreSQL) 또는 aiomysql (MySQL)
    - 커넥션 풀 기반
    - statement_timeout 설정으로 장시간 쿼리 차단
    - max_rows 초과 시 자동 truncation
    """
```

**입력**: SQL 문자열, 데이터소스 설정
**출력**: `ExecutionResult` (rows, columns, row_count, truncated)
**설정**: timeout=30s, max_rows=10,000, row_limit=1,000

### 3.7 단계 7: 시각화 추천

```python
# viz.py (297줄) 기반
def recommend_visualization(columns: list, data: list) -> VizRecommendation:
    """
    컬럼 타입과 데이터 패턴 분석하여 차트 유형 추천.

    규칙:
    - 시계열 + 숫자 → line chart
    - 카테고리 + 숫자 → bar chart
    - 비율/구성 → pie chart
    - 2개 숫자 → scatter plot
    - 단일 숫자 → KPI card
    """
```

### 3.8 단계 8: 결과 캐싱 (품질 게이트)

```python
# cache_postprocess.py (1977줄) 기반
async def cache_with_quality_gate(
    question: str,
    sql: str,
    result: ExecutionResult,
    judge_rounds: int = 2,
    conf_threshold: float = 0.90
) -> CacheResult:
    """
    1. LLM 심사관이 SQL 품질을 N회 독립 평가
    2. 평균 신뢰도 >= threshold → Neo4j Query 노드로 영속화
    3. 값 매핑 발견 시 ValueMapping 노드 생성
    4. 실패 시 캐싱하지 않음 (거짓 캐시 방지)
    """
```

**품질 게이트 설정**:
- `judge_rounds`: 2 (LLM 심사 횟수)
- `conf_threshold`: 0.90 (최소 신뢰도)

---

## 4. 파이프라인 설정 요약

| 설정 | 기본값 | 설명 |
|------|--------|------|
| `vector_top_k` | 10 | 벡터 검색 상위 결과 수 |
| `max_fk_hops` | 3 | FK 그래프 탐색 최대 홉 |
| `sql_timeout` | 30s | SQL 실행 타임아웃 |
| `max_rows` | 10,000 | SQL 최대 반환 행 수 |
| `row_limit` | 1,000 | API 응답 행 수 제한 |
| `max_join_depth` | 5 | SQL JOIN 최대 깊이 |
| `max_subquery_depth` | 3 | 서브쿼리 최대 깊이 |
| `judge_rounds` | 2 | 품질 게이트 LLM 심사 횟수 |
| `conf_threshold` | 0.90 | 캐시 최소 신뢰도 |

---

## 5. 캐시 활용 전략

### 5.1 캐시 히트 시 파이프라인 단축

기존에 검증된 유사 쿼리가 있으면 파이프라인이 단축된다:

```
질문 → 임베딩 → 그래프 검색 → [캐시 히트!]
                                    │
                                    ▼
                               캐시된 SQL → 검증 → 실행 → 시각화
                               (4단계 -> 3단계로 단축)
```

### 5.2 캐시 미스 시 전체 파이프라인

```
질문 → 임베딩 → 그래프 검색 → 스키마 포맷 → SQL 생성 → 검증 → 실행
                                                              → 시각화 → 캐싱
                                                              (8단계 전체 실행)
```

### 5.3 캐시 품질 관리

```
┌─────────────────────────────────────────────────────────┐
│ 캐시 라이프사이클                                        │
│                                                          │
│  생성 ──→ 심사 ──→ 영속화 ──→ 활용 ──→ 피드백 ──→ 갱신  │
│           │                           │                  │
│           └─ 실패 → 폐기              └─ 부정 → 무효화  │
└─────────────────────────────────────────────────────────┘
```

---

## 결정 사항

| 결정 | 근거 |
|------|------|
| 5축 벡터 검색 채택 | 단일 축 대비 recall 향상 (ADR-004 참조) |
| FK 3홉 제한 | 복잡도-성능 균형 (K-AIR 운영 데이터 분석) |
| 품질 게이트 2회 심사 | 비용-정확도 트레이드오프 (ADR-005 참조) |
| ReAct 패턴 채택 | 다단계 추론이 필요한 복합 질문 대응 |

## 관련 문서

- [01_architecture/sql-guard.md](./sql-guard.md): SQL Guard 검증 상세
- [03_backend/graph-search.md](../03_backend/graph-search.md): 그래프 검색 구현 상세
- [05_llm/prompt-engineering.md](../05_llm/prompt-engineering.md): SQL 생성 프롬프트 설계
- [05_llm/react-agent.md](../05_llm/react-agent.md): ReAct 에이전트 상세
- [99_decisions/ADR-004-multi-axis-search.md](../99_decisions/ADR-004-multi-axis-search.md): 5축 벡터 검색 결정
- [99_decisions/ADR-005-quality-gate.md](../99_decisions/ADR-005-quality-gate.md): 품질 게이트 결정
