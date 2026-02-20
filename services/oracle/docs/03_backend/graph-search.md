# Synapse Graph API 기반 벡터 검색 + FK 그래프 경로 탐색

## 이 문서가 답하는 질문

- graph_search.py는 Synapse API를 통해 어떤 그래프 검색 요청을 수행하는가?
- 5축 벡터 검색의 각 축은 어떻게 구현되는가?
- FK 경로 탐색은 어떤 알고리즘을 사용하는가?
- 결과 융합(Rank Fusion)은 어떻게 동작하는가?

<!-- affects: 05_llm, 06_data -->
<!-- requires-update: 06_data/neo4j-schema.md -->

---

## 1. 모듈 개요

`graph_search.py`는 K-AIR 352줄 구현을 기반으로, 사용자 질문에 가장 관련 있는 데이터베이스 스키마(테이블, 컬럼, FK 관계)를 **Synapse Graph API 경유**로 검색하는 역할을 한다.

> 참고: 아래 Cypher 예시는 Synapse 내부 Graph Layer에서 실행되는 서버측 쿼리 기준이다. Oracle 서비스는 직접 Cypher를 실행하지 않는다.

### 1.1 입출력

```python
async def search_relevant_schema(
    question: str,
    question_vector: list[float],
    datasource_id: str,
    top_k: int = 10,
    max_fk_hops: int = 3
) -> SchemaSearchResult:
    """
    입력:
    - question: 원본 자연어 질문
    - question_vector: 질문의 임베딩 벡터 (1536차원)
    - datasource_id: 대상 데이터소스 ID
    - top_k: 각 축 검색 상위 결과 수 (기본: 10)
    - max_fk_hops: FK 그래프 탐색 최대 홉 수 (기본: 3)

    출력:
    - SchemaSearchResult
      ├ tables: list[TableInfo]       # 관련 테이블
      ├ columns: list[ColumnInfo]     # 관련 컬럼
      ├ fk_paths: list[FKPath]        # FK 조인 경로
      ├ cached_queries: list[CachedQuery]  # 유사 기존 쿼리
      └ value_mappings: list[ValueMapping] # 값 매핑
    """
```

---

## 2. 5축 벡터 검색 구현

### 2.1 축 1: Question Vector (직접 유사도)

```cypher
// 테이블 벡터 검색
CALL db.index.vector.queryNodes(
    'table_vector',      // 인덱스 이름
    $top_k,              // 상위 K개
    $question_vector     // 질문 벡터
)
YIELD node AS table, score
WHERE table.datasource_id = $datasource_id
  AND table.text_to_sql_is_valid = true
RETURN table.name AS name,
       table.description AS description,
       table.schema AS schema,
       score
ORDER BY score DESC
```

```cypher
// 컬럼 벡터 검색
CALL db.index.vector.queryNodes(
    'column_vector',
    $top_k,
    $question_vector
)
YIELD node AS col, score
WHERE col.datasource_id = $datasource_id
RETURN col.fqn AS fqn,
       col.name AS name,
       col.dtype AS data_type,
       col.nullable AS nullable,
       col.description AS description,
       score
ORDER BY score DESC
```

### 2.2 축 2: HyDE Vector (가상 문서 임베딩)

```python
async def generate_hyde_vector(question: str) -> list[float]:
    """
    HyDE (Hypothetical Document Embedding):
    1. LLM에게 "이 질문에 답하는 테이블/컬럼 구조를 설명해줘" 요청
    2. LLM의 설명을 임베딩
    3. 이 임베딩으로 벡터 검색 (질문 자체보다 스키마와 더 가까운 벡터)
    """
    hyde_prompt = f"""
    다음 질문에 답하기 위해 필요한 데이터베이스 테이블과 컬럼 구조를 설명하세요.
    테이블 이름, 컬럼 이름, 데이터 타입, 관계를 포함하세요.

    질문: {question}
    """
    hyde_text = await llm_factory.generate(hyde_prompt)
    hyde_vector = await embed_text(hyde_text)
    return hyde_vector
```

HyDE 벡터도 축 1과 동일한 검색 경로를 사용하되, `$question_vector` 대신 `$hyde_vector`를 전달한다.

### 2.3 축 3: Regex (키워드 직접 매칭)

```python
def extract_keywords(question: str) -> list[str]:
    """
    질문에서 테이블/컬럼 이름 후보 키워드를 추출.
    - 한글 용어 사전 매칭 (매출 -> revenue, 부서 -> department)
    - 영문 식별자 패턴 감지 ([a-z_]+)
    - 숫자 패턴 제거 (연도, 금액 등)
    """
```

```cypher
// 키워드 기반 테이블 검색
MATCH (t:Table)
WHERE t.datasource_id = $datasource_id
  AND t.text_to_sql_is_valid = true
  AND (t.name CONTAINS $keyword
       OR t.description CONTAINS $keyword)
RETURN t.name AS name,
       t.description AS description,
       1.0 AS score
```

```cypher
// 키워드 기반 컬럼 검색
MATCH (t:Table)-[:HAS_COLUMN]->(c:Column)
WHERE t.datasource_id = $datasource_id
  AND (c.name CONTAINS $keyword
       OR c.description CONTAINS $keyword)
RETURN c.fqn AS fqn,
       c.name AS name,
       c.description AS description,
       1.0 AS score
```

### 2.4 축 4: Intent Vector (질문 의도 분류)

```python
async def classify_intent(question: str) -> tuple[str, list[float]]:
    """
    질문의 의도를 분류하고 의도 벡터를 생성.

    의도 카테고리:
    - aggregation: "건수", "합계", "평균" 등 집계
    - filter: "~인", "~에서", "~기간" 등 필터
    - comparison: "대비", "변동", "차이" 등 비교
    - trend: "추이", "변화", "증감" 등 추세
    - detail: "상세", "목록", "리스트" 등 목록 조회
    - ranking: "TOP", "순위", "가장" 등 순위
    """
    intent_prompt = f"""
    다음 질문의 SQL 쿼리 패턴을 설명하세요:
    - 집계(COUNT/SUM/AVG), 필터(WHERE), 비교(CASE WHEN),
      추세(시계열), 목록(SELECT *), 순위(ORDER BY)
    질문: {question}
    """
    intent_text = await llm_factory.generate(intent_prompt)
    intent_vector = await embed_text(intent_text)
    return intent_text, intent_vector
```

### 2.5 축 5: PRF (Pseudo Relevance Feedback)

```python
async def pseudo_relevance_feedback(
    initial_results: list[SearchResult],
    question_vector: list[float],
    alpha: float = 0.7
) -> list[float]:
    """
    초기 검색 결과(축 1~4)의 상위 문서 벡터로 질문 벡터를 보강.

    Rocchio 알고리즘 변형:
    new_vector = alpha * question_vector + (1-alpha) * mean(top_doc_vectors)

    이 보강된 벡터로 재검색하여 정밀도를 높임.
    """
    top_vectors = [r.vector for r in initial_results[:5]]
    mean_vector = np.mean(top_vectors, axis=0)
    prf_vector = alpha * np.array(question_vector) + (1 - alpha) * mean_vector
    return prf_vector.tolist()
```

---

## 3. FK 그래프 경로 탐색

### 3.1 알고리즘

벡터 검색으로 찾은 테이블들을 시작점으로, FK(Foreign Key) 관계를 따라 JOIN에 필요한 중간 테이블을 발견한다.

```cypher
// FK 경로 탐색 Cypher
MATCH (start:Table {name: $start_table, datasource_id: $datasource_id})
  -[:HAS_COLUMN]->(sc:Column)-[:FK_TO]-(tc:Column)<-[:HAS_COLUMN]-
  (hop1:Table)
WITH start, hop1, sc, tc
OPTIONAL MATCH (hop1)-[:HAS_COLUMN]->(h1c:Column)-[:FK_TO]-(h2c:Column)
  <-[:HAS_COLUMN]-(hop2:Table)
WHERE hop2 <> start
WITH start, hop1, hop2, sc, tc, h1c, h2c
OPTIONAL MATCH (hop2)-[:HAS_COLUMN]->(h2c2:Column)-[:FK_TO]-(h3c:Column)
  <-[:HAS_COLUMN]-(hop3:Table)
WHERE hop3 <> start AND hop3 <> hop1
RETURN
    start.name AS start_table,
    collect(DISTINCT {
        hop1: hop1.name,
        hop2: hop2.name,
        hop3: hop3.name,
        join_columns: [
            {from: sc.fqn, to: tc.fqn},
            {from: h1c.fqn, to: h2c.fqn},
            {from: h2c2.fqn, to: h3c.fqn}
        ]
    }) AS paths
```

### 3.2 경로 선택 전략

```python
def select_best_fk_paths(
    source_tables: list[str],
    all_paths: list[FKPath]
) -> list[FKPath]:
    """
    여러 FK 경로 중 최적 경로 선택.

    우선순위:
    1. 검색된 테이블 간 직접 FK → 최고 우선
    2. 1홉 중간 테이블 → 중간 우선
    3. 2홉 이상 → 낮은 우선 (경고 포함)

    중복 경로 제거 및 최단 경로 선택.
    """
```

---

## 4. 결과 융합 (Reciprocal Rank Fusion)

5축 검색 결과를 하나의 순위로 합치기 위해 **Reciprocal Rank Fusion (RRF)** 알고리즘을 사용한다.

```python
def reciprocal_rank_fusion(
    results_by_axis: dict[str, list[SearchResult]],
    k: int = 60
) -> list[SearchResult]:
    """
    Reciprocal Rank Fusion (RRF):

    각 축(axis)에서의 순위(rank)를 기반으로 통합 점수 계산:
    score(d) = sum over axes of ( 1 / (k + rank(d, axis)) )

    k=60은 RRF 논문의 권장값.

    예시:
    - 테이블 A: 축1에서 1위, 축2에서 3위, 축3에서 미포함
      score = 1/(60+1) + 1/(60+3) + 0 = 0.0164 + 0.0159 = 0.0323

    - 테이블 B: 축1에서 5위, 축2에서 1위, 축3에서 2위
      score = 1/(60+5) + 1/(60+1) + 1/(60+2) = 0.0154 + 0.0164 + 0.0161 = 0.0479

    → 테이블 B가 더 높은 통합 점수 (더 많은 축에서 발견됨)
    """
    fused_scores = defaultdict(float)

    for axis, results in results_by_axis.items():
        for rank, result in enumerate(results, start=1):
            fused_scores[result.id] += 1.0 / (k + rank)

    sorted_results = sorted(
        fused_scores.items(),
        key=lambda x: x[1],
        reverse=True
    )

    return [
        SearchResult(id=id, rrf_score=score)
        for id, score in sorted_results
    ]
```

---

## 5. 캐시된 쿼리 검색

벡터 검색 결과에 기존에 검증된 유사 쿼리가 포함될 수 있다.

```cypher
// 검증된 유사 쿼리 검색
CALL db.index.vector.queryNodes(
    'query_vector',
    5,
    $question_vector
)
YIELD node AS query, score
WHERE query.verified = true
  AND query.datasource_id = $datasource_id
  AND score >= 0.85
RETURN query.question AS original_question,
       query.sql AS sql,
       query.summary AS summary,
       score
ORDER BY score DESC
```

---

## 6. 값 매핑 검색

자연어 값을 DB 실제 값으로 매핑하는 노드를 검색한다.

```cypher
// 값 매핑 검색
MATCH (vm:ValueMapping)
WHERE vm.datasource_id = $datasource_id
  AND (vm.natural_value CONTAINS $keyword
       OR vm.db_value CONTAINS $keyword)
  AND vm.confidence >= 0.8
RETURN vm.natural_value AS natural_value,
       vm.db_value AS db_value,
       vm.column_fqn AS column_fqn,
       vm.confidence AS confidence
ORDER BY vm.confidence DESC
LIMIT 20
```

---

## 7. 성능 고려사항

| 항목 | 전략 |
|------|------|
| 벡터 검색 속도 | Synapse 백엔드 Neo4j 벡터 인덱스 (HNSW) 사용, O(log n) |
| FK 탐색 속도 | 3홉 제한으로 조합 폭발 방지 |
| 5축 병렬 실행 | asyncio.gather()로 5축 동시 검색 |
| 결과 캐싱 | 동일 질문 벡터의 검색 결과를 Redis에 단기 캐시 (TTL: 5분) |

---

## 관련 문서

- [01_architecture/nl2sql-pipeline.md](../01_architecture/nl2sql-pipeline.md): 파이프라인 내 위치
- [06_data/neo4j-schema.md](../06_data/neo4j-schema.md): Synapse 백엔드 그래프 스키마 상세
- [06_data/value-mapping.md](../06_data/value-mapping.md): 값 매핑 상세
- [99_decisions/ADR-004-multi-axis-search.md](../99_decisions/ADR-004-multi-axis-search.md): 5축 검색 결정
