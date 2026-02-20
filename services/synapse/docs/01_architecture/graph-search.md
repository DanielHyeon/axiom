# 벡터 검색 + 그래프 경로 탐색

## 이 문서가 답하는 질문

- Synapse의 그래프 검색은 어떤 방식으로 동작하는가?
- 벡터 유사도 검색과 FK 그래프 경로 탐색을 어떻게 결합하는가?
- K-AIR text2sql의 검색 로직을 어떻게 이식했는가?
- Oracle 모듈이 Synapse 검색을 어떻게 활용하는가?

<!-- affects: backend, api -->
<!-- requires-update: 02_api/graph-api.md, 06_data/vector-indexes.md -->

---

## 1. 검색 아키텍처 개요

Synapse의 그래프 검색은 두 단계로 구성된다:

```
┌──────────────────────────────────────────────────────────────┐
│  Stage 1: 벡터 유사도 검색 (Vector Similarity Search)         │
│                                                                │
│  사용자 질의 → 임베딩 → Neo4j 벡터 인덱스 검색                 │
│  결과: Top-K 유사 노드 (Table, Column, Query)                 │
│                                                                │
├──────────────────────────────────────────────────────────────┤
│  Stage 2: FK 그래프 경로 탐색 (Graph Path Traversal)          │
│                                                                │
│  Stage 1 결과 노드 → FK 관계 따라 3홉 탐색                    │
│  결과: 연관 테이블/컬럼 + 조인 경로                           │
│                                                                │
└──────────────────────────────────────────────────────────────┘
```

---

## 2. K-AIR 이식 원본

### 2.1 원본: `app/core/graph_search.py`

K-AIR text2sql의 그래프 검색은 다음 기능을 제공했다:

| 기능 | 설명 | Synapse 이식 상태 |
|------|------|------------------|
| 벡터 유사도 검색 | 질의 임베딩 → 코사인 유사도 Top-K | 직접 이식 |
| FK 경로 탐색 | 결과 테이블에서 FK 관계 최대 3홉 | 직접 이식 |
| 5축 벡터 검색 | question/hyde/regex/intent/PRF | Oracle로 이관 |

> **결정**: 5축 벡터 검색(question, hyde, regex, intent, PRF)은 Text2SQL 특화 기능이므로 Oracle로 이관하고, Synapse는 기본 벡터 검색 + 그래프 탐색만 담당한다.

### 2.2 원본 Neo4j 노드 구조

```
(:Table {name, description, embedding, row_count, sample_data})
(:Column {name, table_name, data_type, description, embedding, nullable, is_pk, is_fk})
(:Query {question, sql, description, embedding, verified})
(:ValueMapping {column_name, table_name, original_value, mapped_value})
```

### 2.3 원본 관계

```
(:Column)-[:FK_TO]->(:Column)         // FK 참조 관계
(:Column)-[:BELONGS_TO]->(:Table)     // 컬럼 → 테이블 소속
(:Query)-[:REFERENCES]->(:Table)      // 쿼리 → 참조 테이블
(:ValueMapping)-[:MAPS_TO]->(:Column) // 값 매핑 → 컬럼
```

---

## 3. Stage 1: 벡터 유사도 검색

### 3.1 벡터 인덱스

| 인덱스명 | 대상 노드 | 임베딩 속성 | 차원 | 유사도 함수 |
|---------|----------|-----------|------|-----------|
| `table_vector` | `:Table` | `embedding` | 1536 | cosine |
| `column_vector` | `:Column` | `embedding` | 1536 | cosine |
| `query_vector` | `:Query` | `embedding` | 1536 | cosine |

### 3.2 인덱스 생성 Cypher

```cypher
// Table 벡터 인덱스
CREATE VECTOR INDEX table_vector IF NOT EXISTS
FOR (t:Table)
ON (t.embedding)
OPTIONS {
  indexConfig: {
    `vector.dimensions`: 1536,
    `vector.similarity_function`: 'cosine'
  }
};

// Column 벡터 인덱스
CREATE VECTOR INDEX column_vector IF NOT EXISTS
FOR (c:Column)
ON (c.embedding)
OPTIONS {
  indexConfig: {
    `vector.dimensions`: 1536,
    `vector.similarity_function`: 'cosine'
  }
};

// Query 벡터 인덱스
CREATE VECTOR INDEX query_vector IF NOT EXISTS
FOR (q:Query)
ON (q.embedding)
OPTIONS {
  indexConfig: {
    `vector.dimensions`: 1536,
    `vector.similarity_function`: 'cosine'
  }
};
```

### 3.3 벡터 검색 Cypher

```cypher
// Table 벡터 검색 (Top-5)
CALL db.index.vector.queryNodes('table_vector', 5, $query_embedding)
YIELD node AS table_node, score
WHERE score >= $min_score
RETURN table_node.name AS table_name,
       table_node.description AS description,
       score
ORDER BY score DESC
```

```cypher
// Column 벡터 검색 (Top-10)
CALL db.index.vector.queryNodes('column_vector', 10, $query_embedding)
YIELD node AS col_node, score
WHERE score >= $min_score
RETURN col_node.name AS column_name,
       col_node.table_name AS table_name,
       col_node.data_type AS data_type,
       col_node.description AS description,
       score
ORDER BY score DESC
```

### 3.4 검색 파라미터

| 파라미터 | 기본값 | 설명 |
|---------|-------|------|
| `top_k` | 5 (Table), 10 (Column) | 반환할 최대 결과 수 |
| `min_score` | 0.7 | 최소 유사도 점수 임계값 |
| `embedding_model` | text-embedding-3-small | 임베딩 모델 |
| `embedding_dim` | 1536 | 임베딩 차원 |

---

## 4. Stage 2: FK 그래프 경로 탐색

### 4.1 탐색 알고리즘

Stage 1에서 찾은 테이블/컬럼 노드를 시작점으로, FK 관계를 따라 최대 3홉 탐색한다.

```cypher
// FK 기반 관련 테이블 탐색 (최대 3홉)
MATCH (start_col:Column {table_name: $table_name})
MATCH path = (start_col)-[:FK_TO*1..3]-(related_col:Column)
WITH DISTINCT related_col.table_name AS related_table,
     min(length(path)) AS hop_distance,
     collect(DISTINCT [n IN nodes(path) | n.name]) AS join_columns
RETURN related_table, hop_distance, join_columns
ORDER BY hop_distance ASC
```

### 4.2 경로 탐색 결과 구조

```json
{
  "source_table": "processes",
  "related_tables": [
    {
      "table": "organizations",
      "hop_distance": 1,
      "join_path": [
        {"from": "processes.org_id", "to": "organizations.id", "type": "FK_TO"}
      ]
    },
    {
      "table": "projects",
      "hop_distance": 1,
      "join_path": [
        {"from": "processes.project_id", "to": "projects.id", "type": "FK_TO"}
      ]
    },
    {
      "table": "resources",
      "hop_distance": 2,
      "join_path": [
        {"from": "processes.project_id", "to": "projects.id", "type": "FK_TO"},
        {"from": "projects.id", "to": "resources.project_id", "type": "FK_TO"}
      ]
    }
  ]
}
```

### 4.3 3홉 제한 근거

| 홉 수 | 의미 | 예시 |
|-------|------|------|
| 1홉 | 직접 참조 | processes → organizations |
| 2홉 | 간접 참조 | processes → projects → resources |
| 3홉 | 원거리 참조 | processes → projects → resources → evaluations |
| 4홉+ | 노이즈 증가 | 관련성 급격히 감소, 성능 저하 |

> **결정**: K-AIR에서 3홉이 최적 균형점으로 검증되었다. 4홉 이상에서는 무관한 테이블이 다수 포함되어 Text2SQL 정확도가 하락한다.

---

## 5. 통합 검색 흐름

### 5.1 전체 검색 파이프라인

```python
async def graph_search(query: str, case_id: str) -> GraphSearchResult:
    # 1. Generate query embedding
    query_embedding = await embed(query)

    # 2. Stage 1: Vector similarity search
    similar_tables = await vector_search_tables(query_embedding, top_k=5)
    similar_columns = await vector_search_columns(query_embedding, top_k=10)

    # 3. Stage 2: FK graph path traversal
    related_tables = set()
    join_paths = []
    for table in similar_tables:
        fk_results = await fk_path_search(table.name, max_hops=3)
        related_tables.update(fk_results.tables)
        join_paths.extend(fk_results.paths)

    # 4. Merge results (deduplicate, rank)
    all_tables = rank_tables(similar_tables, related_tables)

    # 5. Enrich with column metadata
    enriched = await enrich_with_columns(all_tables)

    return GraphSearchResult(
        tables=enriched,
        join_paths=join_paths,
        query_embedding=query_embedding
    )
```

### 5.2 Oracle 연동 시나리오

```
사용자: "ABC 제조의 프로세스 효율성 현황을 알려줘"

1. Oracle이 Synapse에 검색 요청
   POST /api/v3/graph/search
   {"query": "ABC 제조 프로세스 효율성 현황", "case_id": "..."}

2. Synapse 벡터 검색
   - table_vector 검색: processes(0.92), organizations(0.85), metrics(0.88)
   - column_vector 검색: processes.efficiency_rate(0.90), metrics.type(0.87)

3. Synapse FK 경로 탐색
   - processes → organizations (1홉)
   - processes → projects (1홉)
   - processes → metrics (via project) (2홉)

4. Oracle이 결과를 받아 SQL 생성
   SELECT o.name, p.efficiency_rate, m.value
   FROM processes p
   JOIN organizations o ON p.org_id = o.id
   JOIN metrics m ON p.project_id = m.project_id
   WHERE p.case_id = '...'
   AND m.type = 'efficiency'
```

---

## 6. 온톨로지 계층 검색 (확장)

4계층 온톨로지 도입 후, 기존 벡터 검색에 온톨로지 탐색을 추가한다.

### 6.1 온톨로지 경로 탐색

```cypher
// 특정 Resource에서 영향받는 KPI까지 경로 탐색
MATCH (r:Resource {case_id: $case_id, name: $resource_name})
MATCH path = (r)-[:PARTICIPATES_IN|CONTRIBUTES_TO|PRODUCES|CONTRIBUTES_TO*1..4]->(k:KPI)
RETURN path, length(path) AS depth
ORDER BY depth ASC
LIMIT 10
```

### 6.2 하이브리드 검색: 벡터 + 온톨로지

```python
async def hybrid_search(query: str, case_id: str) -> HybridSearchResult:
    # 1. Traditional vector + FK search
    graph_result = await graph_search(query, case_id)

    # 2. Ontology path search (if ontology nodes exist)
    ontology_result = await ontology_path_search(query, case_id)

    # 3. Merge and rank
    return merge_results(graph_result, ontology_result)
```

---

## 금지 규칙

- 4홉 이상의 FK 경로 탐색을 수행하지 않는다
- case_id 없이 벡터 검색을 수행하지 않는다 (전체 그래프 검색 금지)
- Oracle이 Neo4j에 직접 Cypher 쿼리를 보내지 않는다

## 필수 규칙

- 벡터 검색 결과에 유사도 점수를 항상 포함한다
- FK 경로 탐색 결과에 조인 경로 정보를 포함한다
- 검색 결과는 relevance score로 정렬한다

---

## 근거 문서

- K-AIR `app/core/graph_search.py` 원본 코드
- K-AIR 역설계 분석 보고서 섹션 2.2, 4.3.3
- `06_data/vector-indexes.md` (벡터 인덱스 설계)
- `02_api/graph-api.md` (검색 API 명세)
