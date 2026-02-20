# Neo4j 그래프 스키마

> **최종 수정일**: 2026-02-20
> **상태**: Active
> **변경 이력**: 2026-02-20 Weaver v2 스키마 정합성 업데이트 (UUID 기반 식별, tenant_id 필수화, 속성 소유권 명시)

## 이 문서가 답하는 질문

- Synapse가 관리하는 Neo4j에 어떤 노드(Node)와 관계(Relationship)가 존재하는가?
- Oracle 관점에서 사용하는 노드/속성과 Weaver가 소유하는 노드/속성의 경계는?
- 벡터 인덱스는 어떻게 구성되는가?
- 데이터의 생성-사용-폐기 라이프사이클은?

<!-- affects: 03_backend, 05_llm -->
<!-- requires-update: 03_backend/graph-search.md, 03_backend/cache-system.md -->

---

## 1. 스키마 개요

Oracle은 **Synapse API 경유로** Neo4j 데이터를 3가지 목적에 사용한다:

| 목적 | 저장 대상 | 노드 유형 | 소유권 |
|------|----------|----------|--------|
| **스키마 메타데이터** | Target DB의 테이블/컬럼 구조 | Table, Column | **Weaver 소유** (Oracle은 벡터 속성만 관리) |
| **쿼리 캐시** | 검증된 NL2SQL 결과 | Query | **Synapse 저장소 / Oracle 논리 소유** |
| **값 매핑** | 자연어-DB값 매핑 | ValueMapping | **Synapse 저장소 / Oracle 논리 소유** |

> **SSOT 원칙**: Table/Column 노드의 핵심 속성(id, tenant_id, name, dtype 등)은 Weaver가 관리한다. Oracle은 이 노드에 벡터 속성(`vector`, `text_to_sql_is_valid`, `column_count`, `sample_values`)만 쓴다. 상세 구조는 `(Weaver) 06_data/neo4j-schema-v2.md`를 참조한다.

```
┌────────────────────────────────────────────────────────────────┐
│  Neo4j Graph Schema (Oracle 관점)                               │
│                                                                 │
│  ┌─────────────┐  HAS_COLUMN  ┌──────────────┐  FK_TO         │
│  │ :Table      │─────────────>│ :Column      │────────>(:Col) │
│  │ (Weaver 소유)│              │ (Weaver 소유) │                │
│  │ +vector     │              │ +vector      │                │
│  │ (Oracle 쓰기)│              │ (Oracle 쓰기) │                │
│  └──────┬──────┘              └──────┬───────┘                │
│         │                            │                         │
│         │ USES_TABLE                 │ MAPPED_VALUE            │
│         │                            │                         │
│  ┌──────▼──────┐              ┌──────▼──────────┐             │
│  │ :Query      │              │ :ValueMapping   │             │
│  │ (Oracle 소유)│              │ (Oracle 소유)    │             │
│  └──────┬──────┘              └─────────────────┘             │
│         │                                                      │
│         │ SIMILAR_TO                                           │
│         │                                                      │
│  ┌──────▼──────┐                                              │
│  │ :Query      │                                              │
│  └─────────────┘                                              │
└────────────────────────────────────────────────────────────────┘
```

---

## 2. 노드 상세

### 2.1 :Table (Weaver 소유, Oracle이 벡터 속성 관리)

Table 노드는 **Weaver가 생성/관리**한다. Oracle은 다음 속성만 읽기/쓰기한다.

#### Oracle이 읽는 속성 (Weaver 소유)

| 속성 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `id` | String (UUID) | Yes | 노드 고유 식별자 |
| `tenant_id` | String (UUID) | Yes | 테넌트 ID (JWT에서 추출) |
| `name` | String | Yes | 테이블 이름 (예: "process_metrics") |
| `description` | String | No | 테이블 설명 (한글) |
| `row_count` | Integer | No | 추정 행 수 |
| `schema_id` | String (UUID) | Yes | 소속 Schema의 id |

#### Oracle이 쓰는 속성 (Oracle 소유)

| 속성 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `vector` | List[Float] | No | 설명의 임베딩 벡터 (1536차원, text-embedding-3-small) |
| `text_to_sql_is_valid` | Boolean | No | NL2SQL 사용 가능 여부 (기본: true) |
| `column_count` | Integer | No | 컬럼 수 (Oracle이 계산) |

**고유 제약**: `(schema_id, name)` — Weaver v2 기준. 모든 쿼리에 `tenant_id` 필터 필수.

> **참조**: Table 노드 전체 스키마는 `(Weaver) 06_data/neo4j-schema-v2.md` §2.3 참조.

### 2.2 :Column (Weaver 소유, Oracle이 벡터 속성 관리)

Column 노드는 **Weaver가 생성/관리**한다. Oracle은 다음 속성만 읽기/쓰기한다.

#### Oracle이 읽는 속성 (Weaver 소유)

| 속성 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `id` | String (UUID) | Yes | 노드 고유 식별자 |
| `tenant_id` | String (UUID) | Yes | 테넌트 ID |
| `fqn` | String | Yes | Fully Qualified Name (예: "public.process_metrics.metric_id") |
| `name` | String | Yes | 컬럼 이름 |
| `dtype` | String | Yes | 데이터 타입 (예: "bigint", "varchar(50)") |
| `nullable` | Boolean | Yes | NULL 허용 여부 |
| `is_primary_key` | Boolean | Yes | PK 여부 (기본: false) |
| `description` | String | No | 컬럼 설명 (한글) |
| `table_id` | String (UUID) | Yes | 소속 Table의 id |

#### Oracle이 쓰는 속성 (Oracle 소유)

| 속성 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `vector` | List[Float] | No | 설명의 임베딩 벡터 (1536차원) |
| `sample_values` | List[String] | No | 샘플 값 목록 |

**고유 제약**: `(table_id, name)` — Weaver v2 기준. `fqn` 단독으로는 유니크가 아님 (동일 테넌트 내 다른 DataSource에서 동일 fqn 가능).

> **참조**: Column 노드 전체 스키마는 `(Weaver) 06_data/neo4j-schema-v2.md` §2.4 참조.

### 2.3 :Query (Oracle 소유)

| 속성 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `id` | String (UUID) | Yes | 쿼리 고유 ID |
| `tenant_id` | String (UUID) | Yes | 테넌트 ID (JWT에서 추출) |
| `datasource_id` | String (UUID) | Yes | 데이터소스 ID (Weaver DataSource.id 참조) |
| `question` | String | Yes | 원본 자연어 질문 |
| `sql` | String | Yes | 생성된 SQL |
| `summary` | String | No | 결과 요약 |
| `vector` | List[Float] | Yes | 질문의 임베딩 벡터 (1536차원) |
| `verified` | Boolean | Yes | 사용자 검증 여부 (기본: false) |
| `confidence` | Float | Yes | 품질 게이트 신뢰도 (0.0~1.0) |
| `feedback_count` | Integer | No | 피드백 수 |
| `positive_count` | Integer | No | 긍정 피드백 수 |
| `negative_count` | Integer | No | 부정 피드백 수 |
| `usage_count` | Integer | No | 캐시 히트 횟수 |
| `created_at` | DateTime | Yes | 생성 시각 |
| `last_used_at` | DateTime | No | 마지막 사용 시각 |

**고유 제약**: `id` 가 유일

### 2.4 :ValueMapping (Oracle 소유)

| 속성 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `natural_value` | String | Yes | 자연어 표현 (예: "본사") |
| `db_value` | String | Yes | DB 실제 값 (예: "본사영업부") |
| `column_fqn` | String | Yes | 대상 컬럼 FQN |
| `datasource_id` | String (UUID) | Yes | 데이터소스 ID (Weaver DataSource.id 참조) |
| `tenant_id` | String (UUID) | Yes | 테넌트 ID (JWT에서 추출) |
| `confidence` | Float | Yes | 신뢰도 (0.0~1.0) |
| `source` | String | Yes | 생성 출처 ("auto_extract" / "enum_bootstrap" / "user_feedback") |
| `created_at` | DateTime | Yes | 생성 시각 |
| `updated_at` | DateTime | No | 수정 시각 |

**고유 제약**: `(natural_value, column_fqn, datasource_id)` 조합이 유일

---

## 3. 관계(Relationship) 상세

### 3.1 Oracle이 읽는 관계 (Weaver 소유)

| 관계 | 시작 노드 | 끝 노드 | 속성 | 설명 |
|------|----------|---------|------|------|
| `HAS_SCHEMA` | :DataSource | :Schema | - | 데이터소스가 스키마를 포함 |
| `HAS_TABLE` | :Schema | :Table | - | 스키마가 테이블을 포함 |
| `HAS_COLUMN` | :Table | :Column | - | 테이블이 컬럼을 소유 |
| `FK_TO` | :Column | :Column | `constraint_name` | FK 관계 (컬럼 레벨) |
| `FK_TO_TABLE` | :Table | :Table | - | FK 요약 (테이블 레벨, 조인 경로 탐색용) |

### 3.2 Oracle이 쓰는 관계 (Oracle 소유)

| 관계 | 시작 노드 | 끝 노드 | 속성 | 설명 |
|------|----------|---------|------|------|
| `USES_TABLE` | :Query | :Table | - | 쿼리가 사용하는 테이블 |
| `SIMILAR_TO` | :Query | :Query | `score` (Float) | 유사 쿼리 간 관계 |
| `MAPPED_VALUE` | :ValueMapping | :Column | - | 값 매핑이 속한 컬럼 |

### 3.3 관계 다이어그램

```cypher
// Oracle이 읽는 Weaver 관계 (그래프 탐색용)
(:DataSource)-[:HAS_SCHEMA]->(:Schema)
(:Schema)-[:HAS_TABLE]->(:Table)
(:Table)-[:HAS_COLUMN]->(:Column)
(:Column)-[:FK_TO {constraint_name: String}]->(:Column)
(:Table)-[:FK_TO_TABLE]->(:Table)

// Oracle이 쓰는 관계
(:Query)-[:USES_TABLE]->(:Table)
(:Query)-[:SIMILAR_TO {score: Float}]->(:Query)
(:ValueMapping)-[:MAPPED_VALUE]->(:Column)
```

---

## 4. 벡터 인덱스

Oracle이 생성하고 관리하는 벡터 인덱스이다.

| 인덱스 이름 | 대상 노드 | 속성 | 차원 | 유사도 함수 | 용도 |
|------------|----------|------|------|-----------|------|
| `table_vector` | :Table | `vector` | 1536 | cosine | 테이블 벡터 검색 |
| `column_vector` | :Column | `vector` | 1536 | cosine | 컬럼 벡터 검색 |
| `query_vector` | :Query | `vector` | 1536 | cosine | 유사 쿼리 검색 |

### 4.1 인덱스 생성 Cypher

```cypher
// 벡터 인덱스 생성 (Oracle이 관리)
CREATE VECTOR INDEX table_vector IF NOT EXISTS
FOR (t:Table) ON (t.vector)
OPTIONS {
    indexConfig: {
        `vector.dimensions`: 1536,
        `vector.similarity_function`: 'cosine'
    }
};

CREATE VECTOR INDEX column_vector IF NOT EXISTS
FOR (c:Column) ON (c.vector)
OPTIONS {
    indexConfig: {
        `vector.dimensions`: 1536,
        `vector.similarity_function`: 'cosine'
    }
};

CREATE VECTOR INDEX query_vector IF NOT EXISTS
FOR (q:Query) ON (q.vector)
OPTIONS {
    indexConfig: {
        `vector.dimensions`: 1536,
        `vector.similarity_function`: 'cosine'
    }
};
```

### 4.2 Oracle 소유 노드 인덱스

```cypher
// Query 인덱스
CREATE CONSTRAINT query_id_unique IF NOT EXISTS
    FOR (q:Query) REQUIRE q.id IS UNIQUE;

CREATE INDEX query_tenant_idx IF NOT EXISTS
    FOR (q:Query) ON (q.tenant_id);

CREATE INDEX query_ds_idx IF NOT EXISTS
    FOR (q:Query) ON (q.datasource_id);

CREATE INDEX query_tenant_ds_idx IF NOT EXISTS
    FOR (q:Query) ON (q.tenant_id, q.datasource_id);

// ValueMapping 인덱스
CREATE INDEX vm_tenant_idx IF NOT EXISTS
    FOR (vm:ValueMapping) ON (vm.tenant_id);

CREATE INDEX vm_ds_idx IF NOT EXISTS
    FOR (vm:ValueMapping) ON (vm.datasource_id);

CREATE INDEX vm_natural_ds_idx IF NOT EXISTS
    FOR (vm:ValueMapping) ON (vm.natural_value, vm.datasource_id);
```

---

## 5. 테넌트 격리 쿼리 패턴

### 5.1 원칙: 모든 쿼리에 tenant_id 필수

Core의 4중 격리 모델 Layer 4(명시적 WHERE 조건)에 따라, **모든 Cypher 쿼리에 `tenant_id` 조건을 포함**해야 한다.

```cypher
// 올바른 패턴: tenant_id + datasource 경유 그래프 탐색
MATCH (ds:DataSource {tenant_id: $tenant_id, case_id: $case_id, name: $datasource_name})
    -[:HAS_SCHEMA]->(s:Schema)
    -[:HAS_TABLE]->(t:Table)
    -[:HAS_COLUMN]->(c:Column)
RETURN t.name, collect({name: c.name, dtype: c.dtype, description: c.description})

// 올바른 패턴: Oracle 소유 노드도 tenant_id 필수
MATCH (q:Query {tenant_id: $tenant_id, datasource_id: $datasource_id})
RETURN q.question, q.sql, q.confidence
```

### 5.2 벡터 검색 패턴

```cypher
// 테이블 벡터 검색 (tenant_id 필터 필수)
CALL db.index.vector.queryNodes('table_vector', $k, $query_vector)
YIELD node AS t, score
WHERE t.tenant_id = $tenant_id
RETURN t.name, t.description, score
ORDER BY score DESC

// 유사 쿼리 검색 (캐시 히트)
CALL db.index.vector.queryNodes('query_vector', $k, $query_vector)
YIELD node AS q, score
WHERE q.tenant_id = $tenant_id AND q.datasource_id = $datasource_id
RETURN q.question, q.sql, q.confidence, score
ORDER BY score DESC
```

### 5.3 FK 기반 조인 경로 탐색

```cypher
// FK_TO_TABLE 관계를 통한 조인 경로 (NL2SQL에서 사용)
MATCH (ds:DataSource {tenant_id: $tenant_id, case_id: $case_id, name: $datasource_name})
    -[:HAS_SCHEMA]->(:Schema)
    -[:HAS_TABLE]->(t1:Table {name: $table1})
MATCH (ds)
    -[:HAS_SCHEMA]->(:Schema)
    -[:HAS_TABLE]->(t2:Table {name: $table2})
MATCH path = shortestPath((t1)-[:FK_TO_TABLE*1..3]-(t2))
RETURN [n IN nodes(path) | n.name] AS join_path,
       length(path) AS hops
```

### 5.4 금지 사항

| 규칙 | 설명 |
|------|------|
| `tenant_id` 없는 쿼리 금지 | 모든 MATCH 절에 `tenant_id` 조건 필수 |
| `MATCH (n) RETURN n` 패턴 금지 | 전체 노드 조회는 테넌트 격리 위반 |
| Weaver 소유 속성 덮어쓰기 금지 | Oracle은 `vector`, `text_to_sql_is_valid`, `column_count`, `sample_values`만 쓰기 가능 |
| 벡터 검색 후 tenant_id 미필터 금지 | 벡터 인덱스는 tenant_id로 파티셔닝되지 않으므로 결과에 WHERE 필수 |

---

## 6. 데이터 라이프사이클

### 6.1 Table/Column 노드

```
생성: Weaver(데이터 패브릭)가 메타데이터 추출 시
갱신: Oracle이 벡터 속성 쓰기 (임베딩, text_to_sql_is_valid, sample_values)
      Weaver가 메타데이터 재동기화 시 핵심 속성만 갱신 (Oracle 속성 보존)
삭제: Weaver가 데이터소스 삭제 시 cascade

라이프사이클:
  Weaver 추출 → Oracle 벡터 인덱싱 → Oracle NL2SQL 검색 사용
                → Weaver 설명 수정 → Oracle 벡터 재인덱싱
                → Weaver 데이터소스 삭제 → cascade 삭제
```

### 6.2 Query 노드

```
생성: 품질 게이트 통과 시 (cache_postprocess.py)
갱신: 피드백 수신 시 (confidence, verified 변경)
       캐시 히트 시 (usage_count 증가)
삭제: 부정 피드백 누적 → 자동 비활성화
       수동 삭제 (관리자)

라이프사이클:
  NL2SQL 실행 → 품질 게이트 심사 → [APPROVE] → Neo4j 영속화
                                  → [REJECT] → 폐기

  영속화 후:
  캐시 히트 → usage_count++ → 재활용
  긍정 피드백 → verified=true, confidence++
  부정 피드백 → confidence--, 임계값 이하 시 비활성화
```

### 6.3 ValueMapping 노드

```
생성: cache_postprocess.py (자동 추출)
       enum_cache_bootstrap.py (Enum 캐싱)
       사용자 피드백 (수동 등록)
갱신: 더 높은 confidence 발견 시 갱신
삭제: 수동 삭제만 (자동 삭제 없음)

라이프사이클:
  Enum 부트스트랩 → 초기 값 매핑 대량 생성
  NL2SQL 실행 → 자동 추출 → confidence 기반 MERGE
  사용자 피드백 → 수동 매핑 추가 (source='user_feedback')
```

---

## 7. 비즈니스 도메인 확장

K-AIR 원본 스키마에 비즈니스 프로세스 인텔리전스 도메인 특화 노드를 추가한다.

```
미정 / 향후 결정:
- :Domain (비즈니스 프로세스 도메인 용어 사전)
- :Synonym (동의어 관계)
- :Template (SQL 템플릿)
```

> Weaver v2에서 `:GlossaryTerm` 노드가 추가되었다. Oracle의 :Domain/:Synonym과 역할이 겹칠 수 있으므로, 구현 시 Weaver GlossaryTerm과의 관계를 정리해야 한다.

---

## 결정 사항

| 결정 | 근거 |
|------|------|
| Neo4j를 메타+캐시 통합 저장소로 | 그래프 탐색과 벡터 검색을 단일 DB에서 수행 |
| 벡터 차원 1536 | OpenAI text-embedding-3-small 기본 차원 |
| cosine 유사도 | 방향 기반 유사도가 텍스트 검색에 적합 |
| MERGE 기반 ValueMapping | 중복 방지, confidence 자동 갱신 |
| 속성 레벨 소유권 분리 | Weaver가 핵심 속성, Oracle이 벡터/NL2SQL 속성 관리 (Weaver v2 §6.3) |
| `tenant_id` 필수 (v2) | Core 4중 격리 모델 확장, 모든 Oracle 소유 노드에도 tenant_id 추가 |

## 관련 문서

- [03_backend/graph-search.md](../03_backend/graph-search.md): 그래프 검색 구현
- [03_backend/cache-system.md](../03_backend/cache-system.md): 캐시 후처리
- [06_data/value-mapping.md](./value-mapping.md): 값 매핑 전략
- [99_decisions/ADR-002-neo4j-vector.md](../99_decisions/ADR-002-neo4j-vector.md): Neo4j 벡터 인덱스 결정
- [(Weaver) 06_data/neo4j-schema-v2.md](../../../weaver/docs/06_data/neo4j-schema-v2.md): Weaver Neo4j v2 스키마 (Table/Column SSOT)
- [(Weaver) 06_data/neo4j-schema-v2.md §6](../../../weaver/docs/06_data/neo4j-schema-v2.md): 노드 소유권 매트릭스
