# Neo4j 메타데이터 그래프 스키마

> **참고**: 이 문서는 v1 스키마입니다. 멀티테넌트 지원과 패브릭 스냅샷을 포함하는 v2 스키마는 `06_data/neo4j-schema-v2.md`를 참조하세요.

<!-- affects: backend, llm, data -->
<!-- requires-update: 03_backend/neo4j-metadata.md -->

## 이 문서가 답하는 질문

- Neo4j에 어떤 노드와 관계가 저장되는가?
- 각 노드의 속성(property)은 무엇인가?
- 각 속성의 nullable 여부와 타입은?
- 인덱스와 제약조건은 무엇인가?

---

## 1. 그래프 모델 개요

```
(:DataSource)
    │
    │ :HAS_SCHEMA
    ▼
(:Schema)
    │
    │ :HAS_TABLE
    ▼
(:Table)
    │                        (:Table)
    │ :HAS_COLUMN              ▲
    ▼                          │ :FK_TO_TABLE
(:Column) ──:FK_TO──▶ (:Column)
```

---

## 2. 노드 상세

### 2.1 DataSource 노드

데이터소스(외부 DB 연결)를 나타낸다.

```cypher
(:DataSource {
    name: "erp_db",                -- String, UNIQUE, NOT NULL
    engine: "postgresql",          -- String, NOT NULL
    host: "erp-db.internal",       -- String, nullable
    port: 5432,                    -- Integer, nullable
    database: "enterprise_ops",    -- String, nullable
    user: "reader",                -- String, nullable
    last_extracted: datetime()     -- DateTime, nullable
})
```

| 속성 | 타입 | nullable | 인덱스 | 설명 |
|------|------|----------|--------|------|
| `name` | String | No | UNIQUE | 데이터소스 고유 이름 |
| `engine` | String | No | - | DB 엔진 타입 |
| `host` | String | Yes | - | 호스트 주소 |
| `port` | Integer | Yes | - | 포트 번호 |
| `database` | String | Yes | - | 데이터베이스 이름 |
| `user` | String | Yes | - | 접속 사용자 |
| `last_extracted` | DateTime | Yes | - | 마지막 메타데이터 추출 시각 |

**보안**: `password`는 **절대 Neo4j에 저장하지 않는다**.

### 2.2 Schema 노드

데이터베이스 스키마(네임스페이스)를 나타낸다.

```cypher
(:Schema {
    name: "public"                 -- String, NOT NULL
})
```

| 속성 | 타입 | nullable | 인덱스 | 설명 |
|------|------|----------|--------|------|
| `name` | String | No | INDEX | 스키마 이름 |

### 2.3 Table 노드

데이터베이스 테이블(또는 뷰)을 나타낸다.

```cypher
(:Table {
    name: "processes",                       -- String, NOT NULL
    description: "비즈니스 프로세스 정보",    -- String, nullable (LLM 보강)
    row_count: 15420,                        -- Integer, nullable
    table_type: "BASE TABLE"                 -- String, nullable
})
```

| 속성 | 타입 | nullable | 인덱스 | 설명 |
|------|------|----------|--------|------|
| `name` | String | No | INDEX | 테이블 이름 |
| `description` | String | Yes | - | 테이블 설명 (LLM 보강 가능) |
| `row_count` | Integer | Yes | - | 행 수 (추정치) |
| `table_type` | String | Yes | - | `BASE TABLE` / `VIEW` |

### 2.4 Column 노드

테이블의 컬럼을 나타낸다.

```cypher
(:Column {
    name: "process_code",                        -- String, NOT NULL
    dtype: "character varying",                  -- String, NOT NULL
    nullable: false,                             -- Boolean, NOT NULL
    description: "프로세스 코드 (예: PROC-2026-001)", -- String, nullable (LLM 보강)
    is_primary_key: false,                       -- Boolean, nullable
    default_value: null                          -- String, nullable
})
```

| 속성 | 타입 | nullable | 인덱스 | 설명 |
|------|------|----------|--------|------|
| `name` | String | No | INDEX | 컬럼 이름 |
| `dtype` | String | No | - | 데이터 타입 |
| `nullable` | Boolean | No | - | NULL 허용 여부 |
| `description` | String | Yes | - | 컬럼 설명 (LLM 보강 가능) |
| `is_primary_key` | Boolean | Yes | - | PK 여부 |
| `default_value` | String | Yes | - | 기본값 |

---

## 3. 관계 상세

### 3.1 HAS_SCHEMA

```
(:DataSource)-[:HAS_SCHEMA]->(:Schema)
```

| 속성 | 없음 |

**의미**: 데이터소스가 해당 스키마를 포함한다.

### 3.2 HAS_TABLE

```
(:Schema)-[:HAS_TABLE]->(:Table)
```

| 속성 | 없음 |

**의미**: 스키마가 해당 테이블을 포함한다.

### 3.3 HAS_COLUMN

```
(:Table)-[:HAS_COLUMN]->(:Column)
```

| 속성 | 없음 |

**의미**: 테이블이 해당 컬럼을 포함한다.

### 3.4 FK_TO

```
(:Column)-[:FK_TO]->(:Column)
```

| 속성 | 없음 |

**의미**: 소스 컬럼이 타겟 컬럼을 외래 키로 참조한다.

**예시**:
```cypher
-- processes.org_id → organizations.id
(:Column {name: "org_id"})-[:FK_TO]->(:Column {name: "id"})
```

### 3.5 FK_TO_TABLE

```
(:Table)-[:FK_TO_TABLE]->(:Table)
```

| 속성 | 없음 |

**의미**: 소스 테이블이 타겟 테이블에 대한 FK 관계를 가진다. 컬럼 레벨 FK_TO의 **요약 관계**이다.

**예시**:
```cypher
-- processes 테이블이 organizations 테이블을 참조
(:Table {name: "processes"})-[:FK_TO_TABLE]->(:Table {name: "organizations"})
```

**용도**: 테이블 간 조인 경로 탐색 시 FK_TO_TABLE을 사용하면 더 빠르다 (컬럼 노드를 경유하지 않으므로).

---

## 4. 인덱스와 제약조건

```cypher
-- UNIQUE constraint
CREATE CONSTRAINT ds_name_unique IF NOT EXISTS
    FOR (ds:DataSource) REQUIRE ds.name IS UNIQUE;

-- Composite lookups (performance)
CREATE INDEX schema_name_idx IF NOT EXISTS
    FOR (s:Schema) ON (s.name);

CREATE INDEX table_name_idx IF NOT EXISTS
    FOR (t:Table) ON (t.name);

CREATE INDEX column_name_idx IF NOT EXISTS
    FOR (c:Column) ON (c.name);
```

---

## 5. 예시 데이터 (엔터프라이즈 도메인)

```cypher
-- DataSource
CREATE (ds:DataSource {
    name: "erp_db",
    engine: "postgresql",
    host: "erp-db.internal",
    port: 5432,
    database: "enterprise_ops",
    user: "reader",
    last_extracted: datetime("2026-02-19T10:00:00Z")
})

-- Schema
CREATE (s:Schema {name: "public"})
CREATE (ds)-[:HAS_SCHEMA]->(s)

-- Tables
CREATE (t1:Table {name: "processes", description: "비즈니스 프로세스 정보", row_count: 15420})
CREATE (t2:Table {name: "organizations", description: "대상 조직 정보", row_count: 8750})
CREATE (t3:Table {name: "stakeholders", description: "이해관계자 정보", row_count: 87650})
CREATE (t4:Table {name: "transactions", description: "거래 내역", row_count: 125000})
CREATE (t5:Table {name: "metrics", description: "성과 지표 목록", row_count: 45000})

CREATE (s)-[:HAS_TABLE]->(t1)
CREATE (s)-[:HAS_TABLE]->(t2)
CREATE (s)-[:HAS_TABLE]->(t3)
CREATE (s)-[:HAS_TABLE]->(t4)
CREATE (s)-[:HAS_TABLE]->(t5)

-- Columns (processes 테이블)
CREATE (c1:Column {name: "id", dtype: "bigint", nullable: false, is_primary_key: true, description: "프로세스 고유 ID"})
CREATE (c2:Column {name: "process_code", dtype: "varchar(50)", nullable: false, description: "프로세스 코드 (예: PROC-2026-001)"})
CREATE (c3:Column {name: "org_id", dtype: "bigint", nullable: false, description: "대상 조직 ID (FK)"})
CREATE (c4:Column {name: "process_type", dtype: "varchar(20)", nullable: false, description: "프로세스 유형 (procurement/sales/hr/finance)"})
CREATE (c5:Column {name: "process_status", dtype: "varchar(20)", nullable: false, description: "프로세스 상태 (active/closed/pending)"})
CREATE (c6:Column {name: "started_at", dtype: "timestamptz", nullable: true, description: "시작일"})

CREATE (t1)-[:HAS_COLUMN]->(c1)
CREATE (t1)-[:HAS_COLUMN]->(c2)
CREATE (t1)-[:HAS_COLUMN]->(c3)
CREATE (t1)-[:HAS_COLUMN]->(c4)
CREATE (t1)-[:HAS_COLUMN]->(c5)
CREATE (t1)-[:HAS_COLUMN]->(c6)

-- Columns (organizations 테이블)
CREATE (d1:Column {name: "id", dtype: "bigint", nullable: false, is_primary_key: true, description: "조직 고유 ID"})
CREATE (d2:Column {name: "name", dtype: "varchar(100)", nullable: false, description: "조직명/상호"})
CREATE (d3:Column {name: "business_number", dtype: "varchar(12)", nullable: true, description: "사업자등록번호"})

CREATE (t2)-[:HAS_COLUMN]->(d1)
CREATE (t2)-[:HAS_COLUMN]->(d2)
CREATE (t2)-[:HAS_COLUMN]->(d3)

-- FK relationships
CREATE (c3)-[:FK_TO]->(d1)  -- processes.org_id → organizations.id
CREATE (t1)-[:FK_TO_TABLE]->(t2)  -- processes → organizations
```

---

## 6. 활용 쿼리 모음

### 6.1 데이터소스 전체 메타데이터 조회

```cypher
MATCH (ds:DataSource {name: $name})
    -[:HAS_SCHEMA]->(s:Schema)
    -[:HAS_TABLE]->(t:Table)
    -[:HAS_COLUMN]->(c:Column)
RETURN ds.name, s.name, t.name, t.description,
       collect({name: c.name, type: c.dtype, nullable: c.nullable, description: c.description})
ORDER BY s.name, t.name
```

### 6.2 FK 관계 전체 조회

```cypher
MATCH (ds:DataSource {name: $name})
    -[:HAS_SCHEMA]->(s1:Schema)
    -[:HAS_TABLE]->(t1:Table)
    -[:HAS_COLUMN]->(c1:Column)
    -[:FK_TO]->(c2:Column)
    <-[:HAS_COLUMN]-(t2:Table)
RETURN t1.name as source_table, c1.name as source_column,
       t2.name as target_table, c2.name as target_column
```

### 6.3 테이블 간 조인 경로 (최대 3홉)

```cypher
MATCH (ds:DataSource {name: $name})
    -[:HAS_SCHEMA]->(:Schema)
    -[:HAS_TABLE]->(t1:Table {name: $table1})
MATCH (ds)
    -[:HAS_SCHEMA]->(:Schema)
    -[:HAS_TABLE]->(t2:Table {name: $table2})
MATCH path = shortestPath((t1)-[:FK_TO_TABLE*1..3]-(t2))
RETURN [n IN nodes(path) | n.name] as join_path
```

### 6.4 설명이 없는 테이블/컬럼 조회 (LLM 보강 대상)

```cypher
MATCH (ds:DataSource {name: $name})
    -[:HAS_SCHEMA]->(s:Schema)
    -[:HAS_TABLE]->(t:Table)
    -[:HAS_COLUMN]->(c:Column)
WHERE t.description IS NULL OR c.description IS NULL
RETURN t.name, collect(c.name) as undescribed_columns
```

---

## 7. K-AIR 원본 대비 변경사항

| 항목 | K-AIR | Weaver | 변경 이유 |
|------|-------|--------|----------|
| password 저장 | 평문 저장 (TODO) | 저장하지 않음 | 보안 |
| Table 속성 | name, description | name, description, row_count, table_type | 추가 정보 |
| Column 속성 | name, dtype, nullable, description | + is_primary_key, default_value | PK 정보 필요 |
| FK 관계 | FK_TO만 | FK_TO + FK_TO_TABLE | 경로 탐색 성능 |
| 인덱스 | 없음 | UNIQUE + INDEX | 성능 |

---

## 8. 관련 문서

| 문서 | 설명 |
|------|------|
| `03_backend/neo4j-metadata.md` | Neo4j 메타데이터 CRUD 구현 |
| `05_llm/metadata-enrichment.md` | LLM 기반 메타데이터 보강 |
| `06_data/data-flow.md` | 데이터 흐름 |
| `99_decisions/ADR-003-neo4j-metadata.md` | Neo4j 선택 근거 |
