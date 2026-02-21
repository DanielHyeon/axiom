# 그래프 탐색 API

> 구현 상태 태그: `Implemented`
> 기준일: 2026-02-22

## 이 문서가 답하는 질문

- 벡터 유사도 검색 API를 어떻게 호출하는가?
- FK 그래프 경로 탐색 API의 파라미터는?
- Oracle이 Synapse 검색을 호출할 때의 인터페이스는?
- 온톨로지 경로 탐색 API는?

<!-- affects: backend, frontend -->
<!-- requires-update: 01_architecture/graph-search.md -->

---

## 1. 기본 정보

| 항목 | 값 |
|------|---|
| Base URL | `/api/v3/synapse/graph` |
| 인증 | JWT Bearer Token (Core 경유) 또는 Service Token (서비스 간 호출) |
| 주요 호출자 | Oracle (Text2SQL), Canvas (온톨로지 브라우저) |

---

## 2. 엔드포인트 목록

| Method | Path | 설명 |
|--------|------|------|
| POST | `/search` | 통합 검색 (벡터 + FK 경로) |
| POST | `/vector-search` | 벡터 유사도 검색만 |
| POST | `/fk-path` | FK 경로 탐색만 |
| POST | `/ontology-path` | 온톨로지 계층 경로 탐색 |
| GET | `/tables/{table_name}/related` | 테이블의 관련 테이블 목록 |
| GET | `/stats` | 그래프 통계 |

---

## 3. 엔드포인트 상세

### 3.1 POST /search (통합 검색)

벡터 유사도 검색과 FK 경로 탐색을 결합한 통합 검색이다. Oracle Text2SQL의 주요 호출 대상이다.

#### Request

```json
POST /api/v3/synapse/graph/search
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "query": "ABC 제조의 프로세스 효율성 현황",
  "case_id": "550e8400-e29b-41d4-a716-446655440001",
  "options": {
    "vector_search": {
      "enabled": true,
      "table_top_k": 5,
      "column_top_k": 10,
      "query_top_k": 5,
      "min_score": 0.7
    },
    "fk_traversal": {
      "enabled": true,
      "max_hops": 3,
      "include_join_paths": true
    },
    "include_sample_data": false,
    "include_value_mappings": true
  }
}
```

| 필드 | 타입 | 필수 | 기본값 | 설명 |
|------|------|------|-------|------|
| `query` | string | Y | - | 검색 질의 (자연어) |
| `case_id` | uuid | N | - | 케이스 범위 제한 (없으면 전체) |
| `options.vector_search.enabled` | bool | N | true | 벡터 검색 활성화 |
| `options.vector_search.table_top_k` | int | N | 5 | 테이블 검색 결과 수 |
| `options.vector_search.column_top_k` | int | N | 10 | 컬럼 검색 결과 수 |
| `options.vector_search.query_top_k` | int | N | 5 | 유사 쿼리 검색 결과 수 |
| `options.vector_search.min_score` | float | N | 0.7 | 최소 유사도 점수 |
| `options.fk_traversal.enabled` | bool | N | true | FK 경로 탐색 활성화 |
| `options.fk_traversal.max_hops` | int | N | 3 | 최대 홉 수 (1-3) |
| `options.fk_traversal.include_join_paths` | bool | N | true | JOIN 경로 포함 |
| `options.include_sample_data` | bool | N | false | 샘플 데이터 포함 |
| `options.include_value_mappings` | bool | N | true | 값 매핑 포함 |

#### Response (200 OK)

```json
{
  "success": true,
  "data": {
    "query": "ABC 제조의 프로세스 효율성 현황",
    "search_time_ms": 245,
    "tables": {
      "vector_matched": [
        {
          "name": "processes",
          "description": "프로세스 실행 내역...",
          "score": 0.92,
          "match_type": "vector",
          "columns": [
            {
              "name": "org_id",
              "data_type": "uuid",
              "description": "소속 조직 ID",
              "nullable": false,
              "is_pk": false,
              "is_fk": true,
              "score": 0.85
            },
            {
              "name": "efficiency_rate",
              "data_type": "numeric",
              "description": "프로세스 효율성 비율 (%)",
              "nullable": true,
              "is_pk": false,
              "is_fk": false,
              "score": 0.90
            }
          ]
        }
      ],
      "fk_related": [
        {
          "name": "organizations",
          "description": "이해관계자 정보...",
          "hop_distance": 1,
          "join_path": [
            {
              "from_table": "processes",
              "from_column": "org_id",
              "to_table": "organizations",
              "to_column": "id",
              "relation": "FK_TO"
            }
          ]
        },
        {
          "name": "metrics",
          "description": "프로세스 지표 정보...",
          "hop_distance": 2,
          "join_path": [
            {
              "from_table": "processes",
              "from_column": "case_id",
              "to_table": "cases",
              "to_column": "id",
              "relation": "FK_TO"
            },
            {
              "from_table": "cases",
              "from_column": "id",
              "to_table": "metrics",
              "to_column": "case_id",
              "relation": "FK_TO"
            }
          ]
        }
      ]
    },
    "similar_queries": [
      {
        "question": "조직별 프로세스 효율성을 조회하시오",
        "sql": "SELECT o.name, p.efficiency_rate FROM processes p JOIN organizations o ON p.org_id = o.id WHERE p.case_id = '...'",
        "score": 0.88,
        "verified": true
      }
    ],
    "value_mappings": [
      {
        "column": "processes.process_type",
        "mappings": {
          "collection": "데이터 수집",
          "analysis": "프로세스 분석",
          "optimization": "최적화",
          "execution": "실행"
        }
      }
    ]
  }
}
```

---

### 3.2 POST /vector-search

벡터 유사도 검색만 수행한다.

#### Request

```json
POST /api/v3/synapse/graph/vector-search
Content-Type: application/json

{
  "query": "프로세스 효율성",
  "target": "table",
  "top_k": 5,
  "min_score": 0.7
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `query` | string | Y | 검색 질의 |
| `target` | string | N | table, column, query, all (기본: all) |
| `top_k` | int | N | 결과 수 (기본: 5) |
| `min_score` | float | N | 최소 점수 (기본: 0.7) |

#### Response (200 OK)

```json
{
  "success": true,
  "data": {
    "results": [
      {
        "node_type": "Table",
        "name": "processes",
        "description": "프로세스 실행 내역...",
        "score": 0.92
      }
    ],
    "total": 3,
    "search_time_ms": 85
  }
}
```

---

### 3.3 POST /fk-path

특정 테이블에서 FK 관계를 따라 관련 테이블을 탐색한다.

#### Request

```json
POST /api/v3/synapse/graph/fk-path
Content-Type: application/json

{
  "start_table": "processes",
  "max_hops": 3,
  "direction": "both"
}
```

#### Response (200 OK)

```json
{
  "success": true,
  "data": {
    "start_table": "processes",
    "related_tables": [
      {
        "table": "organizations",
        "hop_distance": 1,
        "path": ["processes.org_id -> organizations.id"]
      },
      {
        "table": "cases",
        "hop_distance": 1,
        "path": ["processes.case_id -> cases.id"]
      },
      {
        "table": "assets",
        "hop_distance": 2,
        "path": ["processes.case_id -> cases.id", "cases.id -> assets.case_id"]
      }
    ],
    "total_related": 8
  }
}
```

---

### 3.4 POST /ontology-path

온톨로지 4계층 내 경로를 탐색한다. KPI 역추적 분석에 사용된다.

#### Request

```json
POST /api/v3/synapse/graph/ontology-path
Content-Type: application/json

{
  "case_id": "550e8400-e29b-41d4-a716-446655440001",
  "start_node_id": "node-uuid-001",
  "target_layer": "kpi",
  "max_depth": 4
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `case_id` | uuid | Y | 프로젝트 ID |
| `start_node_id` | uuid | N | 시작 노드 (없으면 target_node_id 필수) |
| `target_node_id` | uuid | N | 도착 노드 |
| `target_layer` | string | N | 도착 계층 (resource, process, measure, kpi) |
| `max_depth` | int | N | 최대 탐색 깊이 (기본: 4) |

#### Response (200 OK)

```json
{
  "success": true,
  "data": {
    "paths": [
      {
        "nodes": [
          {"id": "node-uuid-001", "layer": "resource", "type": "Company", "name": "ABC 제조"},
          {"id": "node-uuid-020", "layer": "process", "type": "ProcessAnalysis", "name": "프로세스 분석"},
          {"id": "node-uuid-030", "layer": "measure", "type": "Revenue", "name": "매출"},
          {"id": "node-uuid-040", "layer": "kpi", "type": "ProcessEfficiency", "name": "프로세스 효율성"}
        ],
        "relations": [
          {"type": "PARTICIPATES_IN", "properties": {"role": "subject_organization"}},
          {"type": "PRODUCES", "properties": {}},
          {"type": "CONTRIBUTES_TO", "properties": {"weight": 1.0}}
        ],
        "total_hops": 3
      }
    ],
    "total_paths": 3
  }
}
```

---

### 3.5 GET /stats

그래프 전체 통계를 반환한다.

#### Response (200 OK)

```json
{
  "success": true,
  "data": {
    "node_counts": {
      "Table": 25,
      "Column": 350,
      "Query": 120,
      "ValueMapping": 890,
      "Resource": 45,
      "Process": 30,
      "Measure": 25,
      "KPI": 15
    },
    "relation_counts": {
      "FK_TO": 48,
      "BELONGS_TO": 350,
      "REFERENCES": 180,
      "PARTICIPATES_IN": 65,
      "PRODUCES": 40,
      "CONTRIBUTES_TO": 55
    },
    "vector_indexes": {
      "table_vector": {"status": "ONLINE", "populated": true, "count": 25},
      "column_vector": {"status": "ONLINE", "populated": true, "count": 350},
      "query_vector": {"status": "ONLINE", "populated": true, "count": 120}
    }
  }
}
```

---

## 4. 에러 코드

| HTTP Status | Code | 의미 |
|------------|------|------|
| 400 | `EMPTY_QUERY` | 빈 검색 질의 |
| 400 | `INVALID_MAX_HOPS` | max_hops 범위 초과 (1-3) |
| 400 | `INVALID_TARGET` | 잘못된 검색 대상 |
| 404 | `TABLE_NOT_FOUND` | 테이블 없음 |
| 404 | `NODE_NOT_FOUND` | 노드 없음 |
| 503 | `NEO4J_UNAVAILABLE` | Neo4j 연결 불가 |
| 503 | `EMBEDDING_SERVICE_UNAVAILABLE` | 임베딩 서비스 불가 |

---

## 5. 권한

| 엔드포인트 | 필요 역할 |
|----------|---------|
| 모든 검색 API | case_viewer 이상 |
| /stats | admin |

Oracle -> Synapse 서비스 간 호출 시에는 Service Token으로 인증하며, case_id 기반으로 접근 범위가 제한된다.

---

## 근거 문서

- `01_architecture/graph-search.md` (검색 아키텍처)
- `06_data/vector-indexes.md` (벡터 인덱스 설계)
- K-AIR `app/core/graph_search.py` 원본
