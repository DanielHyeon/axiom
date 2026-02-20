# Neo4j 메타데이터 스키마 v2

<!-- affects: backend, data -->
<!-- requires-update: 03_backend/neo4j-metadata.md, 02_api/metadata-api.md -->

## 이 문서가 답하는 질문

- 멀티테넌트 환경에서 Neo4j 노드는 어떻게 격리되는가?
- 패브릭 스냅샷 노드의 구조는 어떠한가?
- v1 대비 v2 스키마의 변경점은 무엇인가?
- Oracle/Synapse가 읽는 노드와 Weaver가 쓰는 노드의 경계는?

---

## 1. v1 -> v2 주요 변경

### 1.1 변경 요약

| 항목 | v1 | v2 | 변경 근거 |
|------|----|----|----------|
| 테넌트 격리 | 없음 (글로벌 네임스페이스) | 모든 노드에 `tenant_id` 필수 | Core의 4중 격리 원칙 확장 |
| 케이스 스코프 | 없음 | DataSource, FabricSnapshot에 `case_id` 필수 | 프로젝트(케이스)별 데이터소스 분리 |
| DataSource 고유 제약 | `name` UNIQUE (글로벌) | `(tenant_id, case_id, name)` UNIQUE | 테넌트 A와 B가 동일 이름 데이터소스 사용 가능 |
| 노드 식별자 | `name` 기반 | `id` (UUID) + 복합 제약 | 서비스 간 참조 안정성 |
| 스냅샷 | 없음 | `:FabricSnapshot`, `:SnapshotDiff` 추가 | 메타데이터 변경 이력 추적 |
| 용어집 | 없음 | `:GlossaryTerm` 추가 (Planned, Experimental Spec) | 비즈니스 용어 매핑 |
| Oracle 벡터 속성 | 별도 관리 | Table/Column 노드에 co-locate | 단일 노드에서 메타데이터+벡터 조회 |
| FK 관계 속성 | 없음 | `constraint_name` 속성 추가 | 제약조건 식별 |
| password 저장 | v1도 미저장 | v2도 미저장 (변동 없음) | connection-security.md 정책 유지 |

### 1.2 테넌트 계층 구조

```
tenant_id (UUID, JWT에서 추출)
  |
  +-- case_id (UUID, 프로젝트/케이스 스코프)
        |
        +-- DataSource (name은 tenant+case 내 고유)
              |
              +-- Schema (name은 DataSource 내 고유)
                    |
                    +-- Table (name은 Schema 내 고유)
                          |
                          +-- Column (name은 Table 내 고유)
```

**원칙**: `tenant_id`는 JWT 페이로드에서만 추출한다. 사용자 입력으로 받지 않는다 (Core `data-isolation.md` 정책).

### 1.3 그래프 모델 개요

```
(:DataSource {tenant_id, case_id, name, ...})
    |
    | :HAS_SCHEMA
    v
(:Schema {tenant_id, name, ...})
    |
    | :HAS_TABLE
    v
(:Table {tenant_id, name, ...})                    (:Table)
    |                                                  ^
    | :HAS_COLUMN                                      | :FK_TO_TABLE
    v                                                  |
(:Column {tenant_id, name, ...}) --:FK_TO--> (:Column)

(:DataSource)--:HAS_SNAPSHOT-->(:FabricSnapshot)--:DIFF_TO-->(:SnapshotDiff)

(:GlossaryTerm)--:DESCRIBES-->(:Table) 또는 (:Column)
```

---

## 2. 노드 정의

### 2.1 :DataSource

데이터소스(외부 DB 연결)를 나타낸다. Weaver가 생성/관리하며, `tenant_id + case_id`로 격리된다.

```cypher
(:DataSource {
    id: "550e8400-e29b-41d4-a716-446655440000",   -- STRING (UUID), NOT NULL
    tenant_id: "a1b2c3d4-...",                      -- STRING (UUID), NOT NULL
    case_id: "e5f6a7b8-...",                        -- STRING (UUID), NOT NULL
    name: "erp_db",                                 -- STRING, NOT NULL
    engine: "postgresql",                           -- STRING, NOT NULL (enum: postgresql, mysql, oracle, mongodb, redis, elasticsearch, web, openai)
    host: "erp-db.internal",                        -- STRING, nullable
    port: 5432,                                     -- INTEGER, nullable
    database: "enterprise_ops",                     -- STRING, nullable
    user: "reader",                                 -- STRING, nullable
    status: "active",                               -- STRING, NOT NULL (enum: active, inactive, error)
    last_extracted: datetime("2026-02-20T10:00:00Z"), -- DATETIME, nullable
    created_at: datetime("2026-02-20T09:00:00Z"),    -- DATETIME, NOT NULL
    updated_at: datetime("2026-02-20T10:00:00Z")     -- DATETIME, nullable
})
```

| 속성 | 타입 | nullable | 설명 |
|------|------|----------|------|
| `id` | STRING (UUID) | No | 노드 고유 식별자 |
| `tenant_id` | STRING (UUID) | No | 테넌트 ID (JWT에서 추출) |
| `case_id` | STRING (UUID) | No | 케이스(프로젝트) ID |
| `name` | STRING | No | 데이터소스 이름 |
| `engine` | STRING | No | DB 엔진 타입 (`postgresql`, `mysql`, `oracle`, `mongodb`, `redis`, `elasticsearch`, `web`, `openai`) |
| `host` | STRING | Yes | 호스트 주소 |
| `port` | INTEGER | Yes | 포트 번호 |
| `database` | STRING | Yes | 데이터베이스 이름 |
| `user` | STRING | Yes | 접속 사용자 |
| `status` | STRING | No | 상태 (`active`: 정상, `inactive`: 비활성, `error`: 연결 오류) |
| `last_extracted` | DATETIME | Yes | 마지막 메타데이터 추출 시각 |
| `created_at` | DATETIME | No | 생성 시각 |
| `updated_at` | DATETIME | Yes | 수정 시각 |

**고유 제약**: `(tenant_id, case_id, name)`

**보안**: `password`는 **절대 Neo4j에 저장하지 않는다** (`connection-security.md` 참조). 비밀번호는 MindsDB가 내부 관리한다.

---

### 2.2 :Schema

데이터베이스 스키마(네임스페이스)를 나타낸다.

```cypher
(:Schema {
    id: "660e8400-...",                             -- STRING (UUID), NOT NULL
    tenant_id: "a1b2c3d4-...",                      -- STRING (UUID), NOT NULL
    name: "public",                                 -- STRING, NOT NULL
    datasource_id: "550e8400-..."                   -- STRING (UUID), NOT NULL
})
```

| 속성 | 타입 | nullable | 설명 |
|------|------|----------|------|
| `id` | STRING (UUID) | No | 노드 고유 식별자 |
| `tenant_id` | STRING (UUID) | No | 테넌트 ID |
| `name` | STRING | No | 스키마 이름 |
| `datasource_id` | STRING (UUID) | No | 소속 DataSource의 `id` (역정규화, 빠른 조회용) |

**고유 제약**: `(datasource_id, name)`

**tenant_id 전파**: Schema의 `tenant_id`는 상위 DataSource에서 상속된다. 저장 시 명시적으로 설정하며, HAS_SCHEMA 관계를 통해 암묵적으로 보장되지만 인덱스 쿼리 성능을 위해 직접 보유한다.

---

### 2.3 :Table

데이터베이스 테이블(또는 뷰)을 나타낸다.

```cypher
(:Table {
    id: "770e8400-...",                             -- STRING (UUID), NOT NULL
    tenant_id: "a1b2c3d4-...",                      -- STRING (UUID), NOT NULL
    name: "processes",                              -- STRING, NOT NULL
    description: "비즈니스 프로세스 정보",            -- STRING, nullable (LLM 보강)
    row_count: 15420,                               -- INTEGER, nullable
    table_type: "BASE TABLE",                       -- STRING, nullable (BASE TABLE / VIEW)
    schema_id: "660e8400-...",                      -- STRING (UUID), NOT NULL

    // ---- Oracle co-located 속성 (Oracle이 쓰기, Weaver는 터치하지 않음) ----
    vector: [0.0123, -0.0456, ...],                 -- LIST<FLOAT> (1536차원), nullable
    text_to_sql_is_valid: true,                     -- BOOLEAN, nullable (기본: true)
    column_count: 12                                -- INTEGER, nullable
})
```

| 속성 | 타입 | nullable | 소유자 | 설명 |
|------|------|----------|--------|------|
| `id` | STRING (UUID) | No | Weaver | 노드 고유 식별자 |
| `tenant_id` | STRING (UUID) | No | Weaver | 테넌트 ID |
| `name` | STRING | No | Weaver | 테이블 이름 |
| `description` | STRING | Yes | Weaver | 테이블 설명 (LLM 보강 가능) |
| `row_count` | INTEGER | Yes | Weaver | 행 수 (추정치) |
| `table_type` | STRING | Yes | Weaver | `BASE TABLE` 또는 `VIEW` |
| `schema_id` | STRING (UUID) | No | Weaver | 소속 Schema의 `id` |
| `vector` | LIST\<FLOAT\> | Yes | **Oracle** | 설명의 임베딩 벡터 (1536차원, text-embedding-3-small) |
| `text_to_sql_is_valid` | BOOLEAN | Yes | **Oracle** | NL2SQL 사용 가능 여부 |
| `column_count` | INTEGER | Yes | **Oracle** | 컬럼 수 (Oracle이 계산) |

**고유 제약**: `(schema_id, name)`

**속성 소유권 분리**: `vector`, `text_to_sql_is_valid`, `column_count`는 Oracle이 관리한다. Weaver가 메타데이터를 재추출할 때 이 속성들은 덮어쓰지 않는다 (MERGE 시 해당 속성 제외).

---

### 2.4 :Column

테이블의 컬럼을 나타낸다.

```cypher
(:Column {
    id: "880e8400-...",                             -- STRING (UUID), NOT NULL
    tenant_id: "a1b2c3d4-...",                      -- STRING (UUID), NOT NULL
    fqn: "public.processes.process_code",           -- STRING, NOT NULL
    name: "process_code",                           -- STRING, NOT NULL
    dtype: "character varying",                     -- STRING, NOT NULL
    nullable: false,                                -- BOOLEAN, NOT NULL
    description: "프로세스 코드 (예: PROC-2026-001)", -- STRING, nullable (LLM 보강)
    is_primary_key: false,                          -- BOOLEAN, NOT NULL (기본: false)
    default_value: null,                            -- STRING, nullable
    table_id: "770e8400-...",                       -- STRING (UUID), NOT NULL

    // ---- Oracle co-located 속성 ----
    vector: [0.0789, -0.0321, ...],                 -- LIST<FLOAT> (1536차원), nullable
    sample_values: ["PROC-2026-001", "PROC-2026-002"] -- LIST<STRING>, nullable
})
```

| 속성 | 타입 | nullable | 소유자 | 설명 |
|------|------|----------|--------|------|
| `id` | STRING (UUID) | No | Weaver | 노드 고유 식별자 |
| `tenant_id` | STRING (UUID) | No | Weaver | 테넌트 ID |
| `fqn` | STRING | No | Weaver | Fully Qualified Name (`schema.table.column`) |
| `name` | STRING | No | Weaver | 컬럼 이름 |
| `dtype` | STRING | No | Weaver | 데이터 타입 |
| `nullable` | BOOLEAN | No | Weaver | NULL 허용 여부 |
| `description` | STRING | Yes | Weaver | 컬럼 설명 (LLM 보강 가능) |
| `is_primary_key` | BOOLEAN | No | Weaver | PK 여부 (기본: `false`) |
| `default_value` | STRING | Yes | Weaver | 기본값 |
| `table_id` | STRING (UUID) | No | Weaver | 소속 Table의 `id` |
| `vector` | LIST\<FLOAT\> | Yes | **Oracle** | 설명의 임베딩 벡터 (1536차원) |
| `sample_values` | LIST\<STRING\> | Yes | **Oracle** | 샘플 값 목록 |

**고유 제약**: `(table_id, name)`

**fqn 규칙**: `{schema_name}.{table_name}.{column_name}` 형식이다. 동일 테넌트 내 DataSource 간에 fqn이 중복될 수 있으므로 (`erp_db`와 `hr_db` 모두 `public.users.id`를 가질 수 있음), fqn 단독으로는 유니크 제약을 걸지 않는다. `(table_id, name)`이 실제 유니크 키이다.

---

### 2.5 :FabricSnapshot

메타데이터 그래프의 특정 시점 스냅샷을 나타낸다. 메타데이터 재추출 전후의 상태를 비교하고, 변경 이력을 추적하는 데 사용한다.

```cypher
(:FabricSnapshot {
    id: "990e8400-...",                             -- STRING (UUID), NOT NULL
    tenant_id: "a1b2c3d4-...",                      -- STRING (UUID), NOT NULL
    case_id: "e5f6a7b8-...",                        -- STRING (UUID), NOT NULL
    datasource_id: "550e8400-...",                  -- STRING (UUID), NOT NULL
    datasource_name: "erp_db",                      -- STRING, NOT NULL (사람이 읽기 위한 역정규화)
    version: 3,                                     -- INTEGER, NOT NULL (auto-increment per datasource)
    trigger_type: "auto",                           -- STRING, NOT NULL (enum: manual, auto, scheduled)
    status: "completed",                            -- STRING, NOT NULL (enum: in_progress, completed, failed)
    created_at: datetime("2026-02-20T10:00:00Z"),    -- DATETIME, NOT NULL
    created_by: "user-uuid-...",                    -- STRING, NOT NULL (사용자 또는 시스템 ID)
    summary: {                                      -- MAP, nullable
        schemas: 3,
        tables: 25,
        columns: 150,
        fks: 18
    },
    graph_data: "{...}"                             -- STRING (JSON), nullable (전체 서브그래프 직렬화)
})
```

| 속성 | 타입 | nullable | 설명 |
|------|------|----------|------|
| `id` | STRING (UUID) | No | 스냅샷 고유 식별자 |
| `tenant_id` | STRING (UUID) | No | 테넌트 ID |
| `case_id` | STRING (UUID) | No | 케이스 ID |
| `datasource_id` | STRING (UUID) | No | 대상 DataSource의 `id` |
| `datasource_name` | STRING | No | 대상 DataSource의 이름 (역정규화) |
| `version` | INTEGER | No | 버전 번호 (DataSource별 자동 증가) |
| `trigger_type` | STRING | No | 트리거 유형: `manual` (사용자 요청), `auto` (메타데이터 재추출 시 자동), `scheduled` (스케줄러) |
| `status` | STRING | No | 상태: `in_progress`, `completed`, `failed` |
| `created_at` | DATETIME | No | 생성 시각 |
| `created_by` | STRING | No | 생성자 ID (사용자 UUID 또는 `system`) |
| `summary` | MAP | Yes | 요약 통계: `{schemas: INT, tables: INT, columns: INT, fks: INT}` |
| `graph_data` | STRING | Yes | 전체 서브그래프의 JSON 직렬화 (복원용) |

**고유 제약**: `(datasource_id, version)`

**생성 시점**: 메타데이터 재추출(`POST /extract-metadata`) 실행 시, 기존 메타데이터를 삭제하기 **전에** 현재 상태를 스냅샷으로 저장한다.

**graph_data 형식**:
```json
{
  "schemas": [
    {
      "name": "public",
      "tables": [
        {
          "name": "processes",
          "description": "비즈니스 프로세스 정보",
          "row_count": 15420,
          "table_type": "BASE TABLE",
          "columns": [
            {
              "name": "id",
              "dtype": "bigint",
              "nullable": false,
              "is_primary_key": true,
              "description": "프로세스 고유 ID"
            }
          ]
        }
      ]
    }
  ],
  "foreign_keys": [
    {
      "source": "public.processes.org_id",
      "target": "public.organizations.id",
      "constraint_name": "fk_processes_org"
    }
  ]
}
```

---

### 2.6 :SnapshotDiff

두 스냅샷 간의 차이를 나타낸다.

```cypher
(:SnapshotDiff {
    id: "aa0e8400-...",                             -- STRING (UUID), NOT NULL
    snapshot_from_id: "990e8400-...",                -- STRING (UUID), NOT NULL
    snapshot_to_id: "990e8401-...",                  -- STRING (UUID), NOT NULL
    diff_data: "{...}",                             -- STRING (JSON), NOT NULL
    created_at: datetime("2026-02-20T10:01:00Z")     -- DATETIME, NOT NULL
})
```

| 속성 | 타입 | nullable | 설명 |
|------|------|----------|------|
| `id` | STRING (UUID) | No | 차이 고유 식별자 |
| `snapshot_from_id` | STRING (UUID) | No | 이전 스냅샷 ID |
| `snapshot_to_id` | STRING (UUID) | No | 이후 스냅샷 ID |
| `diff_data` | STRING (JSON) | No | 차이 데이터 |
| `created_at` | DATETIME | No | 생성 시각 |

**diff_data 형식**:
```json
{
  "tables_added": [
    {"schema": "public", "name": "audit_logs", "column_count": 8}
  ],
  "tables_removed": [
    {"schema": "public", "name": "temp_imports"}
  ],
  "columns_added": [
    {"table": "public.processes", "name": "priority", "dtype": "integer"}
  ],
  "columns_removed": [
    {"table": "public.processes", "name": "legacy_code"}
  ],
  "columns_modified": [
    {
      "table": "public.processes",
      "name": "status",
      "changes": {"dtype": {"from": "varchar(20)", "to": "varchar(50)"}}
    }
  ],
  "fks_added": [
    {"source": "public.audit_logs.process_id", "target": "public.processes.id"}
  ],
  "fks_removed": []
}
```

---

### 2.7 :GlossaryTerm (Planned, Experimental Spec)

> 상태 정합성: 본 섹션은 계약/스키마 정의이며, 운영 런타임 구현은 스프린트 완료 후 활성화된다.
> 참조: `services/weaver/docs/01_architecture/metadata-service.md`, `services/weaver/docs/02_api/metadata-catalog-api.md`

비즈니스 용어를 정의하고 테이블/컬럼과 연결한다. Oracle의 NL2SQL에서 비즈니스 용어를 DB 컬럼으로 매핑할 때 사용한다.

```cypher
(:GlossaryTerm {
    id: "bb0e8400-...",                             -- STRING (UUID), NOT NULL
    tenant_id: "a1b2c3d4-...",                      -- STRING (UUID), NOT NULL
    term: "매출액",                                  -- STRING, NOT NULL
    definition: "특정 기간 동안 발생한 총 판매 금액",  -- STRING, NOT NULL
    synonyms: ["매출", "수익", "revenue"],             -- LIST<STRING>, nullable
    category: "재무",                                -- STRING, nullable
    created_at: datetime("2026-02-20T09:00:00Z"),    -- DATETIME, NOT NULL
    updated_at: datetime("2026-02-20T09:00:00Z")     -- DATETIME, nullable
})
```

| 속성 | 타입 | nullable | 설명 |
|------|------|----------|------|
| `id` | STRING (UUID) | No | 용어 고유 식별자 |
| `tenant_id` | STRING (UUID) | No | 테넌트 ID |
| `term` | STRING | No | 비즈니스 용어 |
| `definition` | STRING | No | 용어 정의 |
| `synonyms` | LIST\<STRING\> | Yes | 동의어 목록 |
| `category` | STRING | Yes | 카테고리 (`재무`, `인사`, `영업` 등) |
| `created_at` | DATETIME | No | 생성 시각 |
| `updated_at` | DATETIME | Yes | 수정 시각 |

**고유 제약**: `(tenant_id, term)`

---

### 2.8 Oracle 소유 노드 (Weaver 관할 아님)

다음 노드들은 Weaver가 아닌 Oracle 서비스가 생성/관리한다. 동일한 Neo4j 인스턴스에 공존하지만, Weaver는 이 노드들을 읽거나 쓰지 않는다.

#### :Query (Oracle 소유)

```cypher
(:Query {
    id: "cc0e8400-...",                             -- STRING (UUID), NOT NULL
    tenant_id: "a1b2c3d4-...",                      -- STRING (UUID), NOT NULL
    datasource_id: "550e8400-...",                  -- STRING (UUID), NOT NULL
    question: "지난 분기 매출이 가장 높은 부서는?",   -- STRING, NOT NULL
    sql: "SELECT department, SUM(revenue)...",       -- STRING, NOT NULL
    summary: "재무팀이 120억원으로 1위",              -- STRING, nullable
    vector: [0.0123, ...],                          -- LIST<FLOAT> (1536차원), NOT NULL
    verified: false,                                -- BOOLEAN, NOT NULL
    confidence: 0.85,                               -- FLOAT, NOT NULL (0.0-1.0)
    usage_count: 5,                                 -- INTEGER, nullable
    created_at: datetime(),                         -- DATETIME, NOT NULL
    last_used_at: datetime()                        -- DATETIME, nullable
})
```

#### :ValueMapping (Oracle 소유)

```cypher
(:ValueMapping {
    natural_value: "본사",                          -- STRING, NOT NULL
    db_value: "본사영업부",                          -- STRING, NOT NULL
    column_fqn: "public.departments.name",          -- STRING, NOT NULL
    datasource_id: "550e8400-...",                  -- STRING (UUID), NOT NULL
    tenant_id: "a1b2c3d4-...",                      -- STRING (UUID), NOT NULL
    confidence: 0.92,                               -- FLOAT, NOT NULL
    source: "auto_extract",                         -- STRING, NOT NULL
    created_at: datetime()                          -- DATETIME, NOT NULL
})
```

#### 향후 Oracle 확장 노드 (계획)

| 노드 | 설명 | 상태 |
|------|------|------|
| `:Synonym` | 컬럼/테이블 동의어 관계 | 계획 |
| `:Domain` | 비즈니스 도메인 용어 사전 | 계획 |
| `:SQLTemplate` | 재사용 가능 SQL 템플릿 | 계획 |

---

## 3. 관계 정의

### 3.1 관계 전체 목록

| 관계 | 시작 노드 | 끝 노드 | 속성 | 소유자 | 설명 |
|------|----------|---------|------|--------|------|
| `HAS_SCHEMA` | :DataSource | :Schema | - | Weaver | 데이터소스가 스키마를 포함 |
| `HAS_TABLE` | :Schema | :Table | - | Weaver | 스키마가 테이블을 포함 |
| `HAS_COLUMN` | :Table | :Column | - | Weaver | 테이블이 컬럼을 포함 |
| `FK_TO` | :Column | :Column | `constraint_name` | Weaver | 외래 키 참조 (컬럼 레벨) |
| `FK_TO_TABLE` | :Table | :Table | - | Weaver | 외래 키 참조 요약 (테이블 레벨) |
| `HAS_SNAPSHOT` | :DataSource | :FabricSnapshot | - | Weaver | 데이터소스의 스냅샷 |
| `DIFF_TO` | :FabricSnapshot | :SnapshotDiff | - | Weaver | 스냅샷 간 차이 |
| `DESCRIBES` | :GlossaryTerm | :Table 또는 :Column | - | Weaver | 용어가 테이블/컬럼을 설명 |
| `USES_TABLE` | :Query | :Table | - | Oracle | 쿼리가 테이블을 사용 |
| `SIMILAR_TO` | :Query | :Query | `score` (FLOAT) | Oracle | 유사 쿼리 관계 |
| `MAPPED_VALUE` | :ValueMapping | :Column | - | Oracle | 값 매핑 대상 컬럼 |

### 3.2 Weaver 관계 다이어그램

```cypher
// Weaver가 관리하는 관계 패턴
(:DataSource)-[:HAS_SCHEMA]->(:Schema)
(:Schema)-[:HAS_TABLE]->(:Table)
(:Table)-[:HAS_COLUMN]->(:Column)
(:Column)-[:FK_TO {constraint_name: "fk_processes_org"}]->(:Column)
(:Table)-[:FK_TO_TABLE]->(:Table)
(:DataSource)-[:HAS_SNAPSHOT]->(:FabricSnapshot)
(:FabricSnapshot)-[:DIFF_TO]->(:SnapshotDiff)
(:GlossaryTerm)-[:DESCRIBES]->(:Table)
(:GlossaryTerm)-[:DESCRIBES]->(:Column)
```

### 3.3 Oracle 관계 다이어그램

```cypher
// Oracle이 관리하는 관계 패턴
(:Query)-[:USES_TABLE]->(:Table)
(:Query)-[:SIMILAR_TO {score: 0.92}]->(:Query)
(:ValueMapping)-[:MAPPED_VALUE]->(:Column)
```

### 3.4 FK_TO 관계 상세

```cypher
// FK_TO: 컬럼 레벨 외래 키
// processes.org_id -> organizations.id
(:Column {name: "org_id", table_id: $processes_table_id})
  -[:FK_TO {constraint_name: "fk_processes_org"}]->
(:Column {name: "id", table_id: $organizations_table_id})

// FK_TO_TABLE: 테이블 레벨 요약 관계
// 컬럼 노드를 경유하지 않으므로 조인 경로 탐색 시 성능 우수
(:Table {name: "processes"})
  -[:FK_TO_TABLE]->
(:Table {name: "organizations"})
```

---

## 4. 제약 조건 및 인덱스

### 4.1 고유 제약 조건 (Unique Constraints)

```cypher
// ─── DataSource: tenant_id + case_id + name 조합 유일 ───
CREATE CONSTRAINT ds_tenant_case_name IF NOT EXISTS
    FOR (ds:DataSource)
    REQUIRE (ds.tenant_id, ds.case_id, ds.name) IS UNIQUE;

// ─── Schema: datasource_id + name 조합 유일 ───
CREATE CONSTRAINT schema_ds_name IF NOT EXISTS
    FOR (s:Schema)
    REQUIRE (s.datasource_id, s.name) IS UNIQUE;

// ─── Table: schema_id + name 조합 유일 ───
CREATE CONSTRAINT table_schema_name IF NOT EXISTS
    FOR (t:Table)
    REQUIRE (t.schema_id, t.name) IS UNIQUE;

// ─── Column: table_id + name 조합 유일 ───
CREATE CONSTRAINT column_table_name IF NOT EXISTS
    FOR (c:Column)
    REQUIRE (c.table_id, c.name) IS UNIQUE;

// ─── FabricSnapshot: datasource_id + version 조합 유일 ───
CREATE CONSTRAINT snapshot_ds_version IF NOT EXISTS
    FOR (fs:FabricSnapshot)
    REQUIRE (fs.datasource_id, fs.version) IS UNIQUE;

// ─── GlossaryTerm: tenant_id + term 조합 유일 ───
CREATE CONSTRAINT glossary_tenant_term IF NOT EXISTS
    FOR (gt:GlossaryTerm)
    REQUIRE (gt.tenant_id, gt.term) IS UNIQUE;

// ─── 모든 노드의 id는 전역 고유 (UUID) ───
CREATE CONSTRAINT ds_id_unique IF NOT EXISTS
    FOR (ds:DataSource) REQUIRE ds.id IS UNIQUE;

CREATE CONSTRAINT schema_id_unique IF NOT EXISTS
    FOR (s:Schema) REQUIRE s.id IS UNIQUE;

CREATE CONSTRAINT table_id_unique IF NOT EXISTS
    FOR (t:Table) REQUIRE t.id IS UNIQUE;

CREATE CONSTRAINT column_id_unique IF NOT EXISTS
    FOR (c:Column) REQUIRE c.id IS UNIQUE;

CREATE CONSTRAINT snapshot_id_unique IF NOT EXISTS
    FOR (fs:FabricSnapshot) REQUIRE fs.id IS UNIQUE;

CREATE CONSTRAINT diff_id_unique IF NOT EXISTS
    FOR (sd:SnapshotDiff) REQUIRE sd.id IS UNIQUE;

CREATE CONSTRAINT glossary_id_unique IF NOT EXISTS
    FOR (gt:GlossaryTerm) REQUIRE gt.id IS UNIQUE;
```

### 4.2 NOT NULL 제약 조건

```cypher
// ─── 모든 노드에 tenant_id 필수 ───
CREATE CONSTRAINT ds_tenant_not_null IF NOT EXISTS
    FOR (ds:DataSource) REQUIRE ds.tenant_id IS NOT NULL;

CREATE CONSTRAINT schema_tenant_not_null IF NOT EXISTS
    FOR (s:Schema) REQUIRE s.tenant_id IS NOT NULL;

CREATE CONSTRAINT table_tenant_not_null IF NOT EXISTS
    FOR (t:Table) REQUIRE t.tenant_id IS NOT NULL;

CREATE CONSTRAINT column_tenant_not_null IF NOT EXISTS
    FOR (c:Column) REQUIRE c.tenant_id IS NOT NULL;

CREATE CONSTRAINT snapshot_tenant_not_null IF NOT EXISTS
    FOR (fs:FabricSnapshot) REQUIRE fs.tenant_id IS NOT NULL;

CREATE CONSTRAINT glossary_tenant_not_null IF NOT EXISTS
    FOR (gt:GlossaryTerm) REQUIRE gt.tenant_id IS NOT NULL;

// ─── DataSource/FabricSnapshot에 case_id 필수 ───
CREATE CONSTRAINT ds_case_not_null IF NOT EXISTS
    FOR (ds:DataSource) REQUIRE ds.case_id IS NOT NULL;

CREATE CONSTRAINT snapshot_case_not_null IF NOT EXISTS
    FOR (fs:FabricSnapshot) REQUIRE fs.case_id IS NOT NULL;
```

### 4.3 복합 인덱스 (테넌트 격리 쿼리 성능)

```cypher
// ─── DataSource 인덱스 ───
CREATE INDEX ds_tenant_idx IF NOT EXISTS
    FOR (ds:DataSource) ON (ds.tenant_id);

CREATE INDEX ds_tenant_case_idx IF NOT EXISTS
    FOR (ds:DataSource) ON (ds.tenant_id, ds.case_id);

CREATE INDEX ds_tenant_case_status_idx IF NOT EXISTS
    FOR (ds:DataSource) ON (ds.tenant_id, ds.case_id, ds.status);

// ─── Schema 인덱스 ───
CREATE INDEX schema_tenant_idx IF NOT EXISTS
    FOR (s:Schema) ON (s.tenant_id);

CREATE INDEX schema_ds_idx IF NOT EXISTS
    FOR (s:Schema) ON (s.datasource_id);

// ─── Table 인덱스 ───
CREATE INDEX table_tenant_idx IF NOT EXISTS
    FOR (t:Table) ON (t.tenant_id);

CREATE INDEX table_schema_idx IF NOT EXISTS
    FOR (t:Table) ON (t.schema_id);

CREATE INDEX table_name_idx IF NOT EXISTS
    FOR (t:Table) ON (t.name);

// ─── Column 인덱스 ───
CREATE INDEX column_tenant_idx IF NOT EXISTS
    FOR (c:Column) ON (c.tenant_id);

CREATE INDEX column_table_idx IF NOT EXISTS
    FOR (c:Column) ON (c.table_id);

CREATE INDEX column_fqn_idx IF NOT EXISTS
    FOR (c:Column) ON (c.fqn);

// ─── FabricSnapshot 인덱스 ───
CREATE INDEX snapshot_tenant_case_idx IF NOT EXISTS
    FOR (fs:FabricSnapshot) ON (fs.tenant_id, fs.case_id);

CREATE INDEX snapshot_ds_idx IF NOT EXISTS
    FOR (fs:FabricSnapshot) ON (fs.datasource_id);

// ─── GlossaryTerm 인덱스 ───
CREATE INDEX glossary_tenant_idx IF NOT EXISTS
    FOR (gt:GlossaryTerm) ON (gt.tenant_id);

CREATE INDEX glossary_tenant_category_idx IF NOT EXISTS
    FOR (gt:GlossaryTerm) ON (gt.tenant_id, gt.category);
```

### 4.4 벡터 인덱스 (Oracle 관리)

Oracle이 생성하고 관리하는 벡터 인덱스이다. Weaver는 이 인덱스를 직접 다루지 않는다.

```cypher
// ─── Table 벡터 인덱스 (테이블 설명 임베딩) ───
CREATE VECTOR INDEX table_vector IF NOT EXISTS
FOR (t:Table) ON (t.vector)
OPTIONS {
    indexConfig: {
        `vector.dimensions`: 1536,
        `vector.similarity_function`: 'cosine'
    }
};

// ─── Column 벡터 인덱스 (컬럼 설명 임베딩) ───
CREATE VECTOR INDEX column_vector IF NOT EXISTS
FOR (c:Column) ON (c.vector)
OPTIONS {
    indexConfig: {
        `vector.dimensions`: 1536,
        `vector.similarity_function`: 'cosine'
    }
};

// ─── Query 벡터 인덱스 (자연어 질문 임베딩) ───
CREATE VECTOR INDEX query_vector IF NOT EXISTS
FOR (q:Query) ON (q.vector)
OPTIONS {
    indexConfig: {
        `vector.dimensions`: 1536,
        `vector.similarity_function`: 'cosine'
    }
};
```

### 4.5 전문 검색 인덱스

```cypher
// ─── 테이블/컬럼 설명 전문 검색 ───
CREATE FULLTEXT INDEX metadata_fulltext IF NOT EXISTS
FOR (n:Table|Column) ON EACH [n.name, n.description];

// ─── 용어집 전문 검색 ───
CREATE FULLTEXT INDEX glossary_fulltext IF NOT EXISTS
FOR (gt:GlossaryTerm) ON EACH [gt.term, gt.definition];
```

---

## 5. 테넌트 격리 쿼리 패턴

### 5.1 원칙: 모든 쿼리에 tenant_id 필수

Neo4j에는 PostgreSQL의 RLS(Row Level Security)가 없다. 따라서 **모든 Cypher 쿼리에 `tenant_id` 조건을 명시적으로 포함**해야 한다. 이것은 Core의 4중 격리 모델에서 Layer 4(명시적 WHERE 조건)에 해당한다.

```cypher
// 올바른 패턴: tenant_id를 항상 첫 번째 조건으로
MATCH (ds:DataSource {tenant_id: $tenant_id, case_id: $case_id})
    -[:HAS_SCHEMA]->(s:Schema)
    -[:HAS_TABLE]->(t:Table)
    -[:HAS_COLUMN]->(c:Column)
RETURN ds.name, s.name, t.name,
       collect({
           name: c.name,
           type: c.dtype,
           nullable: c.nullable,
           description: c.description
       }) AS columns
ORDER BY s.name, t.name
```

### 5.2 데이터소스 전체 메타데이터 조회

```cypher
// 특정 테넌트+케이스의 데이터소스 메타데이터 전체 조회
MATCH (ds:DataSource {tenant_id: $tenant_id, case_id: $case_id, name: $datasource_name})
    -[:HAS_SCHEMA]->(s:Schema)
    -[:HAS_TABLE]->(t:Table)
    -[:HAS_COLUMN]->(c:Column)
WITH ds, s, t, collect({
    name: c.name,
    dtype: c.dtype,
    nullable: c.nullable,
    description: c.description,
    is_primary_key: c.is_primary_key,
    default_value: c.default_value
}) AS columns
WITH ds, s, collect({
    name: t.name,
    description: t.description,
    row_count: t.row_count,
    table_type: t.table_type,
    columns: columns
}) AS tables
RETURN ds.name AS datasource,
       ds.engine AS engine,
       ds.status AS status,
       ds.last_extracted AS last_extracted,
       collect({
           name: s.name,
           tables: tables
       }) AS schemas
```

### 5.3 FK 관계 전체 조회

```cypher
// 특정 데이터소스의 외래 키 관계 전체
MATCH (ds:DataSource {tenant_id: $tenant_id, case_id: $case_id, name: $datasource_name})
    -[:HAS_SCHEMA]->(s1:Schema)
    -[:HAS_TABLE]->(t1:Table)
    -[:HAS_COLUMN]->(c1:Column)
    -[fk:FK_TO]->(c2:Column)
    <-[:HAS_COLUMN]-(t2:Table)
    <-[:HAS_TABLE]-(s2:Schema)
RETURN t1.name AS source_table,
       c1.name AS source_column,
       t2.name AS target_table,
       c2.name AS target_column,
       fk.constraint_name AS constraint_name,
       s1.name AS source_schema,
       s2.name AS target_schema
```

### 5.4 테이블 간 조인 경로 (최대 3홉)

```cypher
// FK 기반 조인 경로 탐색 (Oracle NL2SQL에서 사용)
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

### 5.5 설명 누락 노드 조회 (LLM 보강 대상)

```cypher
// description이 NULL인 테이블/컬럼 목록
MATCH (ds:DataSource {tenant_id: $tenant_id, case_id: $case_id, name: $datasource_name})
    -[:HAS_SCHEMA]->(s:Schema)
    -[:HAS_TABLE]->(t:Table)
    -[:HAS_COLUMN]->(c:Column)
WHERE t.description IS NULL OR c.description IS NULL
RETURN t.name AS table_name,
       t.description IS NULL AS table_needs_description,
       collect(CASE WHEN c.description IS NULL THEN c.name END) AS undescribed_columns
```

### 5.6 스냅샷 이력 조회

```cypher
// 데이터소스의 스냅샷 이력 (최신순)
MATCH (ds:DataSource {tenant_id: $tenant_id, case_id: $case_id, name: $datasource_name})
    -[:HAS_SNAPSHOT]->(fs:FabricSnapshot)
RETURN fs.id AS snapshot_id,
       fs.version AS version,
       fs.trigger_type AS trigger_type,
       fs.status AS status,
       fs.created_at AS created_at,
       fs.created_by AS created_by,
       fs.summary AS summary
ORDER BY fs.version DESC
LIMIT $limit
```

### 5.7 케이스별 데이터소스 목록

```cypher
// 특정 케이스의 모든 활성 데이터소스
MATCH (ds:DataSource {tenant_id: $tenant_id, case_id: $case_id, status: 'active'})
RETURN ds.id AS id,
       ds.name AS name,
       ds.engine AS engine,
       ds.host AS host,
       ds.database AS database,
       ds.last_extracted AS last_extracted,
       ds.created_at AS created_at
ORDER BY ds.name
```

### 5.8 금지 사항

| 규칙 | 설명 | 위반 시 결과 |
|------|------|-------------|
| `tenant_id` 없는 쿼리 금지 | 모든 MATCH 절에 `tenant_id` 조건 필수 | 다른 테넌트 데이터 노출 (보안 사고) |
| 사용자 입력으로 `tenant_id` 받기 금지 | JWT에서만 추출 | 테넌트 스푸핑 |
| `MATCH (n) RETURN n` 패턴 금지 | 전체 노드 조회는 테넌트 격리 위반 | 전체 데이터 노출 |
| Oracle 속성 덮어쓰기 금지 | Weaver가 `vector`, `text_to_sql_is_valid` 등을 수정 불가 | Oracle 데이터 손실 |

**올바르지 않은 쿼리 예시**:

```cypher
// [금지] tenant_id 없음
MATCH (ds:DataSource {name: $name})
    -[:HAS_SCHEMA]->(s:Schema)
RETURN s.name

// [금지] 전체 노드 조회
MATCH (t:Table)
RETURN t.name, t.description
```

**올바른 쿼리로 수정**:

```cypher
// [필수] tenant_id + case_id 포함
MATCH (ds:DataSource {tenant_id: $tenant_id, case_id: $case_id, name: $name})
    -[:HAS_SCHEMA]->(s:Schema)
RETURN s.name

// [필수] tenant_id 필터
MATCH (t:Table {tenant_id: $tenant_id})
RETURN t.name, t.description
```

---

## 6. 노드 소유권 매트릭스

### 6.1 SSOT (Single Source of Truth) 원칙

- **Weaver**: 스키마 메타데이터 노드(DataSource, Schema, Table, Column)의 **핵심 속성**과 스냅샷/용어집의 SSOT
- **Oracle**: 벡터 속성, Query, ValueMapping의 SSOT
- **Synapse**: Neo4j 내 온톨로지 노드(Resource, Process, Measure, KPI)의 SSOT (별도 문서 참조)

### 6.2 전체 소유권 표

| 노드 | 레이블 | 쓰기 소유자 | 읽기 소비자 | 스코프 키 |
|------|--------|------------|------------|-----------|
| DataSource | `:DataSource` | Weaver | Oracle, Canvas | `tenant_id + case_id` |
| Schema | `:Schema` | Weaver | Oracle, Canvas | `tenant_id` (DataSource 경유) |
| Table (핵심) | `:Table` | Weaver | Oracle, Synapse, Canvas | `tenant_id` |
| Table (벡터) | `:Table` | **Oracle** | Oracle, Synapse | `tenant_id` |
| Column (핵심) | `:Column` | Weaver | Oracle, Synapse, Canvas | `tenant_id` |
| Column (벡터) | `:Column` | **Oracle** | Oracle, Synapse | `tenant_id` |
| FabricSnapshot | `:FabricSnapshot` | Weaver | Canvas | `tenant_id + case_id` |
| SnapshotDiff | `:SnapshotDiff` | Weaver | Canvas | FabricSnapshot 경유 |
| GlossaryTerm | `:GlossaryTerm` | Weaver | Oracle, Synapse, Vision, Canvas | `tenant_id` |
| Query | `:Query` | **Oracle** | Canvas | `datasource_id + tenant_id` |
| ValueMapping | `:ValueMapping` | **Oracle** | Oracle | `datasource_id + tenant_id` |

### 6.3 속성 레벨 소유권 (Table/Column 혼합 소유)

Table과 Column 노드는 Weaver와 Oracle이 **속성 레벨에서 소유권을 분리**한다.

```
:Table 노드
  ├── Weaver 소유: id, tenant_id, name, description, row_count, table_type, schema_id
  └── Oracle 소유: vector, text_to_sql_is_valid, column_count

:Column 노드
  ├── Weaver 소유: id, tenant_id, fqn, name, dtype, nullable, description, is_primary_key, default_value, table_id
  └── Oracle 소유: vector, sample_values
```

**Weaver 메타데이터 재추출 시 MERGE 패턴**:

```cypher
// Weaver는 자신이 소유한 속성만 갱신 (Oracle 속성은 건드리지 않음)
MERGE (t:Table {schema_id: $schema_id, name: $table_name})
ON CREATE SET
    t.id = $id,
    t.tenant_id = $tenant_id,
    t.description = $description,
    t.row_count = $row_count,
    t.table_type = $table_type
ON MATCH SET
    t.description = COALESCE($description, t.description),
    t.row_count = $row_count,
    t.table_type = $table_type
// vector, text_to_sql_is_valid, column_count는 의도적으로 SET하지 않음
```

---

## 7. CRUD 쿼리 모음

### 7.1 DataSource 생성

```cypher
CREATE (ds:DataSource {
    id: $id,
    tenant_id: $tenant_id,
    case_id: $case_id,
    name: $name,
    engine: $engine,
    host: $host,
    port: $port,
    database: $database,
    user: $user,
    status: 'active',
    last_extracted: null,
    created_at: datetime(),
    updated_at: null
})
RETURN ds.id AS id
```

### 7.2 메타데이터 일괄 저장 (추출 후)

```cypher
// Step 1: DataSource 업데이트
MATCH (ds:DataSource {tenant_id: $tenant_id, case_id: $case_id, name: $datasource_name})
SET ds.last_extracted = datetime(),
    ds.updated_at = datetime(),
    ds.status = 'active'

// Step 2: Schema 생성
MATCH (ds:DataSource {tenant_id: $tenant_id, case_id: $case_id, name: $datasource_name})
MERGE (s:Schema {datasource_id: ds.id, name: $schema_name})
ON CREATE SET
    s.id = $schema_id,
    s.tenant_id = $tenant_id
CREATE (ds)-[:HAS_SCHEMA]->(s)

// Step 3: Table 배치 생성
MATCH (ds:DataSource {tenant_id: $tenant_id, case_id: $case_id, name: $datasource_name})
    -[:HAS_SCHEMA]->(s:Schema {name: $schema_name})
UNWIND $tables AS tbl
MERGE (t:Table {schema_id: s.id, name: tbl.name})
ON CREATE SET
    t.id = tbl.id,
    t.tenant_id = $tenant_id,
    t.description = tbl.description,
    t.row_count = tbl.row_count,
    t.table_type = tbl.table_type
ON MATCH SET
    t.description = COALESCE(tbl.description, t.description),
    t.row_count = tbl.row_count,
    t.table_type = tbl.table_type
CREATE (s)-[:HAS_TABLE]->(t)

// Step 4: Column 배치 생성
MATCH (ds:DataSource {tenant_id: $tenant_id, case_id: $case_id, name: $datasource_name})
    -[:HAS_SCHEMA]->(s:Schema {name: $schema_name})
    -[:HAS_TABLE]->(t:Table {name: $table_name})
UNWIND $columns AS col
CREATE (c:Column {
    id: col.id,
    tenant_id: $tenant_id,
    fqn: $schema_name + '.' + $table_name + '.' + col.name,
    name: col.name,
    dtype: col.data_type,
    nullable: col.nullable,
    description: col.description,
    is_primary_key: col.is_primary_key,
    default_value: col.default_value,
    table_id: t.id
})
CREATE (t)-[:HAS_COLUMN]->(c)

// Step 5: FK 관계 생성
MATCH (ds:DataSource {tenant_id: $tenant_id, case_id: $case_id, name: $datasource_name})
    -[:HAS_SCHEMA]->(ss:Schema {name: $source_schema})
    -[:HAS_TABLE]->(st:Table {name: $source_table})
    -[:HAS_COLUMN]->(sc:Column {name: $source_column})
MATCH (ds)
    -[:HAS_SCHEMA]->(ts:Schema {name: $target_schema})
    -[:HAS_TABLE]->(tt:Table {name: $target_table})
    -[:HAS_COLUMN]->(tc:Column {name: $target_column})
MERGE (sc)-[:FK_TO {constraint_name: $constraint_name}]->(tc)
MERGE (st)-[:FK_TO_TABLE]->(tt)
```

### 7.3 메타데이터 삭제 (CASCADE)

```cypher
// 데이터소스 하위 전체 노드 삭제 (스냅샷은 보존)
MATCH (ds:DataSource {tenant_id: $tenant_id, case_id: $case_id, name: $datasource_name})
    -[:HAS_SCHEMA]->(s:Schema)
    -[:HAS_TABLE]->(t:Table)
    -[:HAS_COLUMN]->(c:Column)
DETACH DELETE c

// 테이블 노드 삭제
MATCH (ds:DataSource {tenant_id: $tenant_id, case_id: $case_id, name: $datasource_name})
    -[:HAS_SCHEMA]->(s:Schema)
    -[:HAS_TABLE]->(t:Table)
DETACH DELETE t

// 스키마 노드 삭제
MATCH (ds:DataSource {tenant_id: $tenant_id, case_id: $case_id, name: $datasource_name})
    -[:HAS_SCHEMA]->(s:Schema)
DETACH DELETE s
```

### 7.4 DataSource 완전 삭제 (스냅샷 포함)

```cypher
// 스냅샷 차이 삭제
MATCH (ds:DataSource {tenant_id: $tenant_id, case_id: $case_id, name: $datasource_name})
    -[:HAS_SNAPSHOT]->(fs:FabricSnapshot)
    -[:DIFF_TO]->(sd:SnapshotDiff)
DETACH DELETE sd

// 스냅샷 삭제
MATCH (ds:DataSource {tenant_id: $tenant_id, case_id: $case_id, name: $datasource_name})
    -[:HAS_SNAPSHOT]->(fs:FabricSnapshot)
DETACH DELETE fs

// 메타데이터 삭제 (7.3 실행)
// ...

// DataSource 노드 삭제
MATCH (ds:DataSource {tenant_id: $tenant_id, case_id: $case_id, name: $datasource_name})
DETACH DELETE ds
```

### 7.5 스냅샷 생성

```cypher
// 현재 메타데이터 스냅샷 저장
MATCH (ds:DataSource {tenant_id: $tenant_id, case_id: $case_id, name: $datasource_name})
OPTIONAL MATCH (ds)-[:HAS_SNAPSHOT]->(prev:FabricSnapshot)
WITH ds, COALESCE(max(prev.version), 0) + 1 AS next_version

// 현재 메타데이터를 graph_data로 직렬화 (애플리케이션 레이어에서 처리)
CREATE (fs:FabricSnapshot {
    id: $snapshot_id,
    tenant_id: ds.tenant_id,
    case_id: ds.case_id,
    datasource_id: ds.id,
    datasource_name: ds.name,
    version: next_version,
    trigger_type: $trigger_type,
    status: 'in_progress',
    created_at: datetime(),
    created_by: $created_by,
    summary: null,
    graph_data: null
})
CREATE (ds)-[:HAS_SNAPSHOT]->(fs)
RETURN fs.id AS snapshot_id, fs.version AS version
```

### 7.6 테이블/컬럼 설명 업데이트 (LLM 보강)

```cypher
// 테이블 설명 업데이트
MATCH (ds:DataSource {tenant_id: $tenant_id, case_id: $case_id, name: $datasource_name})
    -[:HAS_SCHEMA]->(s:Schema {name: $schema_name})
    -[:HAS_TABLE]->(t:Table {name: $table_name})
SET t.description = $description

// 컬럼 설명 배치 업데이트
MATCH (ds:DataSource {tenant_id: $tenant_id, case_id: $case_id, name: $datasource_name})
    -[:HAS_SCHEMA]->(s:Schema {name: $schema_name})
    -[:HAS_TABLE]->(t:Table {name: $table_name})
    -[:HAS_COLUMN]->(c:Column)
WHERE c.name IN $column_names
UNWIND $descriptions AS desc
WITH c, desc WHERE c.name = desc.name
SET c.description = desc.description
```

---

## 8. 예시 데이터

```cypher
// ─── 테넌트/케이스 컨텍스트 ───
// tenant_id: "t-alpha-001" (분석법인 알파 컨설팅)
// case_id: "c-proj-2026-001" (2026년 1분기 ERP 분석 프로젝트)

// ─── DataSource ───
CREATE (ds:DataSource {
    id: "ds-erp-001",
    tenant_id: "t-alpha-001",
    case_id: "c-proj-2026-001",
    name: "erp_db",
    engine: "postgresql",
    host: "erp-db.internal",
    port: 5432,
    database: "enterprise_ops",
    user: "reader",
    status: "active",
    last_extracted: datetime("2026-02-20T10:00:00Z"),
    created_at: datetime("2026-02-01T09:00:00Z"),
    updated_at: datetime("2026-02-20T10:00:00Z")
})

// ─── Schema ───
CREATE (s:Schema {
    id: "sch-public-001",
    tenant_id: "t-alpha-001",
    name: "public",
    datasource_id: "ds-erp-001"
})
CREATE (ds)-[:HAS_SCHEMA]->(s)

// ─── Tables ───
CREATE (t1:Table {
    id: "tbl-proc-001",
    tenant_id: "t-alpha-001",
    name: "processes",
    description: "비즈니스 프로세스 정보",
    row_count: 15420,
    table_type: "BASE TABLE",
    schema_id: "sch-public-001"
})
CREATE (t2:Table {
    id: "tbl-org-001",
    tenant_id: "t-alpha-001",
    name: "organizations",
    description: "대상 조직 정보",
    row_count: 8750,
    table_type: "BASE TABLE",
    schema_id: "sch-public-001"
})
CREATE (t3:Table {
    id: "tbl-stake-001",
    tenant_id: "t-alpha-001",
    name: "stakeholders",
    description: "이해관계자 정보",
    row_count: 87650,
    table_type: "BASE TABLE",
    schema_id: "sch-public-001"
})

CREATE (s)-[:HAS_TABLE]->(t1)
CREATE (s)-[:HAS_TABLE]->(t2)
CREATE (s)-[:HAS_TABLE]->(t3)

// ─── Columns (processes 테이블) ───
CREATE (c1:Column {
    id: "col-proc-id-001",
    tenant_id: "t-alpha-001",
    fqn: "public.processes.id",
    name: "id",
    dtype: "bigint",
    nullable: false,
    is_primary_key: true,
    description: "프로세스 고유 ID",
    default_value: null,
    table_id: "tbl-proc-001"
})
CREATE (c2:Column {
    id: "col-proc-code-001",
    tenant_id: "t-alpha-001",
    fqn: "public.processes.process_code",
    name: "process_code",
    dtype: "varchar(50)",
    nullable: false,
    is_primary_key: false,
    description: "프로세스 코드 (예: PROC-2026-001)",
    default_value: null,
    table_id: "tbl-proc-001"
})
CREATE (c3:Column {
    id: "col-proc-orgid-001",
    tenant_id: "t-alpha-001",
    fqn: "public.processes.org_id",
    name: "org_id",
    dtype: "bigint",
    nullable: false,
    is_primary_key: false,
    description: "대상 조직 ID (FK)",
    default_value: null,
    table_id: "tbl-proc-001"
})

CREATE (t1)-[:HAS_COLUMN]->(c1)
CREATE (t1)-[:HAS_COLUMN]->(c2)
CREATE (t1)-[:HAS_COLUMN]->(c3)

// ─── Columns (organizations 테이블) ───
CREATE (d1:Column {
    id: "col-org-id-001",
    tenant_id: "t-alpha-001",
    fqn: "public.organizations.id",
    name: "id",
    dtype: "bigint",
    nullable: false,
    is_primary_key: true,
    description: "조직 고유 ID",
    default_value: null,
    table_id: "tbl-org-001"
})
CREATE (d2:Column {
    id: "col-org-name-001",
    tenant_id: "t-alpha-001",
    fqn: "public.organizations.name",
    name: "name",
    dtype: "varchar(100)",
    nullable: false,
    is_primary_key: false,
    description: "조직명/상호",
    default_value: null,
    table_id: "tbl-org-001"
})

CREATE (t2)-[:HAS_COLUMN]->(d1)
CREATE (t2)-[:HAS_COLUMN]->(d2)

// ─── FK 관계 ───
CREATE (c3)-[:FK_TO {constraint_name: "fk_processes_org_id"}]->(d1)
CREATE (t1)-[:FK_TO_TABLE]->(t2)

// ─── FabricSnapshot (이전 추출 기록) ───
CREATE (fs:FabricSnapshot {
    id: "snap-001",
    tenant_id: "t-alpha-001",
    case_id: "c-proj-2026-001",
    datasource_id: "ds-erp-001",
    datasource_name: "erp_db",
    version: 1,
    trigger_type: "manual",
    status: "completed",
    created_at: datetime("2026-02-15T10:00:00Z"),
    created_by: "user-admin-001",
    summary: {schemas: 1, tables: 3, columns: 5, fks: 1},
    graph_data: null
})
CREATE (ds)-[:HAS_SNAPSHOT]->(fs)
```

---

## 9. 마이그레이션 (v1 -> v2)

### 9.1 마이그레이션 전략

v1에서 v2로의 마이그레이션은 다음 순서로 실행한다. 마이그레이션 기간 동안 기존 데이터에는 기본 `tenant_id`와 `case_id`를 할당한다.

#### Step 1: 기존 제약 조건 삭제

```cypher
// v1의 글로벌 UNIQUE 제약 삭제
DROP CONSTRAINT ds_name_unique IF EXISTS;
```

#### Step 2: 모든 노드에 tenant_id, case_id 추가

```cypher
// 기본 테넌트/케이스 할당 (마이그레이션 전용)
// $default_tenant_id: 기존 데이터를 소유할 테넌트 UUID
// $default_case_id: 기존 데이터를 소유할 케이스 UUID

// DataSource
MATCH (ds:DataSource)
WHERE ds.tenant_id IS NULL
SET ds.id = randomUUID(),
    ds.tenant_id = $default_tenant_id,
    ds.case_id = $default_case_id,
    ds.status = COALESCE(ds.status, 'active'),
    ds.created_at = COALESCE(ds.created_at, datetime()),
    ds.updated_at = datetime();

// Schema
MATCH (ds:DataSource)-[:HAS_SCHEMA]->(s:Schema)
WHERE s.tenant_id IS NULL
SET s.id = randomUUID(),
    s.tenant_id = ds.tenant_id,
    s.datasource_id = ds.id;

// Table
MATCH (ds:DataSource)-[:HAS_SCHEMA]->(s:Schema)-[:HAS_TABLE]->(t:Table)
WHERE t.tenant_id IS NULL
SET t.id = randomUUID(),
    t.tenant_id = ds.tenant_id,
    t.schema_id = s.id;

// Column
MATCH (ds:DataSource)-[:HAS_SCHEMA]->(s:Schema)-[:HAS_TABLE]->(t:Table)-[:HAS_COLUMN]->(c:Column)
WHERE c.tenant_id IS NULL
SET c.id = randomUUID(),
    c.tenant_id = ds.tenant_id,
    c.table_id = t.id,
    c.fqn = s.name + '.' + t.name + '.' + c.name,
    c.is_primary_key = COALESCE(c.is_primary_key, false);
```

#### Step 3: 새 제약 조건 생성

```cypher
// 4.1절의 모든 제약 조건 생성
// 4.2절의 모든 NOT NULL 제약 조건 생성
// 4.3절의 모든 인덱스 생성
// (전체 스크립트는 4절 참조)
```

#### Step 4: 검증

```cypher
// tenant_id가 NULL인 노드가 없는지 확인
MATCH (n)
WHERE n:DataSource OR n:Schema OR n:Table OR n:Column
  AND n.tenant_id IS NULL
RETURN labels(n) AS label, count(n) AS null_tenant_count;
// 결과가 0이어야 함

// 모든 DataSource에 case_id가 있는지 확인
MATCH (ds:DataSource)
WHERE ds.case_id IS NULL
RETURN count(ds) AS null_case_count;
// 결과가 0이어야 함

// 중복 제약 위반 없는지 확인
MATCH (ds:DataSource)
WITH ds.tenant_id AS tid, ds.case_id AS cid, ds.name AS name, count(*) AS cnt
WHERE cnt > 1
RETURN tid, cid, name, cnt;
// 결과가 비어 있어야 함
```

### 9.2 하위 호환성

| 항목 | 전략 |
|------|------|
| 기존 API 호출 | `tenant_id`/`case_id`가 없는 호출은 400 에러 반환 (JWT 미들웨어에서 차단) |
| 기존 데이터 | 기본 tenant/case에 할당 후 관리자가 올바른 소속으로 재할당 |
| Oracle 연동 | Oracle도 모든 쿼리에 `tenant_id` 추가 필수 (동시 마이그레이션) |
| 개발 환경 | 단일 테넌트 모드: 환경 변수로 `DEFAULT_TENANT_ID` 설정 가능 |

### 9.3 마이그레이션 체크리스트

```
[  ] v1 데이터 백업 (Neo4j dump)
[  ] 기본 tenant_id, case_id UUID 생성
[  ] Step 1: 기존 제약 조건 삭제
[  ] Step 2: 모든 노드에 tenant_id, case_id, id 추가
[  ] Step 3: 새 제약 조건 및 인덱스 생성
[  ] Step 4: 검증 쿼리 실행
[  ] Weaver MetadataStore 코드 업데이트 (모든 쿼리에 tenant_id 추가)
[  ] Oracle 서비스 코드 업데이트 (모든 쿼리에 tenant_id 추가)
[  ] API 엔드포인트에 tenant_id/case_id 파라미터 추가
[  ] 통합 테스트 실행
[  ] 성능 테스트 (인덱스 적중 확인)
```

---

## 10. 초기화 스크립트

새로운 Neo4j 인스턴스에 v2 스키마를 설정하는 전체 초기화 스크립트이다.

```cypher
// ================================================================
// Axiom Weaver - Neo4j Schema v2 Bootstrap Script
// ================================================================

// ─── 1. Unique Constraints ───────────────────────────────────────

CREATE CONSTRAINT ds_id_unique IF NOT EXISTS
    FOR (ds:DataSource) REQUIRE ds.id IS UNIQUE;
CREATE CONSTRAINT ds_tenant_case_name IF NOT EXISTS
    FOR (ds:DataSource) REQUIRE (ds.tenant_id, ds.case_id, ds.name) IS UNIQUE;

CREATE CONSTRAINT schema_id_unique IF NOT EXISTS
    FOR (s:Schema) REQUIRE s.id IS UNIQUE;
CREATE CONSTRAINT schema_ds_name IF NOT EXISTS
    FOR (s:Schema) REQUIRE (s.datasource_id, s.name) IS UNIQUE;

CREATE CONSTRAINT table_id_unique IF NOT EXISTS
    FOR (t:Table) REQUIRE t.id IS UNIQUE;
CREATE CONSTRAINT table_schema_name IF NOT EXISTS
    FOR (t:Table) REQUIRE (t.schema_id, t.name) IS UNIQUE;

CREATE CONSTRAINT column_id_unique IF NOT EXISTS
    FOR (c:Column) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT column_table_name IF NOT EXISTS
    FOR (c:Column) REQUIRE (c.table_id, c.name) IS UNIQUE;

CREATE CONSTRAINT snapshot_id_unique IF NOT EXISTS
    FOR (fs:FabricSnapshot) REQUIRE fs.id IS UNIQUE;
CREATE CONSTRAINT snapshot_ds_version IF NOT EXISTS
    FOR (fs:FabricSnapshot) REQUIRE (fs.datasource_id, fs.version) IS UNIQUE;

CREATE CONSTRAINT diff_id_unique IF NOT EXISTS
    FOR (sd:SnapshotDiff) REQUIRE sd.id IS UNIQUE;

CREATE CONSTRAINT glossary_id_unique IF NOT EXISTS
    FOR (gt:GlossaryTerm) REQUIRE gt.id IS UNIQUE;
CREATE CONSTRAINT glossary_tenant_term IF NOT EXISTS
    FOR (gt:GlossaryTerm) REQUIRE (gt.tenant_id, gt.term) IS UNIQUE;

// ─── 2. NOT NULL Constraints ─────────────────────────────────────

CREATE CONSTRAINT ds_tenant_not_null IF NOT EXISTS
    FOR (ds:DataSource) REQUIRE ds.tenant_id IS NOT NULL;
CREATE CONSTRAINT ds_case_not_null IF NOT EXISTS
    FOR (ds:DataSource) REQUIRE ds.case_id IS NOT NULL;

CREATE CONSTRAINT schema_tenant_not_null IF NOT EXISTS
    FOR (s:Schema) REQUIRE s.tenant_id IS NOT NULL;

CREATE CONSTRAINT table_tenant_not_null IF NOT EXISTS
    FOR (t:Table) REQUIRE t.tenant_id IS NOT NULL;

CREATE CONSTRAINT column_tenant_not_null IF NOT EXISTS
    FOR (c:Column) REQUIRE c.tenant_id IS NOT NULL;

CREATE CONSTRAINT snapshot_tenant_not_null IF NOT EXISTS
    FOR (fs:FabricSnapshot) REQUIRE fs.tenant_id IS NOT NULL;
CREATE CONSTRAINT snapshot_case_not_null IF NOT EXISTS
    FOR (fs:FabricSnapshot) REQUIRE fs.case_id IS NOT NULL;

CREATE CONSTRAINT glossary_tenant_not_null IF NOT EXISTS
    FOR (gt:GlossaryTerm) REQUIRE gt.tenant_id IS NOT NULL;

// ─── 3. Composite Indexes ────────────────────────────────────────

CREATE INDEX ds_tenant_idx IF NOT EXISTS
    FOR (ds:DataSource) ON (ds.tenant_id);
CREATE INDEX ds_tenant_case_idx IF NOT EXISTS
    FOR (ds:DataSource) ON (ds.tenant_id, ds.case_id);
CREATE INDEX ds_tenant_case_status_idx IF NOT EXISTS
    FOR (ds:DataSource) ON (ds.tenant_id, ds.case_id, ds.status);

CREATE INDEX schema_tenant_idx IF NOT EXISTS
    FOR (s:Schema) ON (s.tenant_id);
CREATE INDEX schema_ds_idx IF NOT EXISTS
    FOR (s:Schema) ON (s.datasource_id);

CREATE INDEX table_tenant_idx IF NOT EXISTS
    FOR (t:Table) ON (t.tenant_id);
CREATE INDEX table_schema_idx IF NOT EXISTS
    FOR (t:Table) ON (t.schema_id);
CREATE INDEX table_name_idx IF NOT EXISTS
    FOR (t:Table) ON (t.name);

CREATE INDEX column_tenant_idx IF NOT EXISTS
    FOR (c:Column) ON (c.tenant_id);
CREATE INDEX column_table_idx IF NOT EXISTS
    FOR (c:Column) ON (c.table_id);
CREATE INDEX column_fqn_idx IF NOT EXISTS
    FOR (c:Column) ON (c.fqn);

CREATE INDEX snapshot_tenant_case_idx IF NOT EXISTS
    FOR (fs:FabricSnapshot) ON (fs.tenant_id, fs.case_id);
CREATE INDEX snapshot_ds_idx IF NOT EXISTS
    FOR (fs:FabricSnapshot) ON (fs.datasource_id);

CREATE INDEX glossary_tenant_idx IF NOT EXISTS
    FOR (gt:GlossaryTerm) ON (gt.tenant_id);
CREATE INDEX glossary_tenant_category_idx IF NOT EXISTS
    FOR (gt:GlossaryTerm) ON (gt.tenant_id, gt.category);

// ─── 4. Vector Indexes (Oracle 관리) ─────────────────────────────

CREATE VECTOR INDEX table_vector IF NOT EXISTS
FOR (t:Table) ON (t.vector)
OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}};

CREATE VECTOR INDEX column_vector IF NOT EXISTS
FOR (c:Column) ON (c.vector)
OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}};

CREATE VECTOR INDEX query_vector IF NOT EXISTS
FOR (q:Query) ON (q.vector)
OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}};

// ─── 5. Fulltext Indexes ─────────────────────────────────────────

CREATE FULLTEXT INDEX metadata_fulltext IF NOT EXISTS
FOR (n:Table|Column) ON EACH [n.name, n.description];

CREATE FULLTEXT INDEX glossary_fulltext IF NOT EXISTS
FOR (gt:GlossaryTerm) ON EACH [gt.term, gt.definition];
```

---

## 11. 관련 문서

| 문서 | 설명 |
|------|------|
| `03_backend/neo4j-metadata.md` | Neo4j 메타데이터 CRUD 구현 (v2 업데이트 필요) |
| `02_api/metadata-api.md` | 메타데이터 추출 API (v2 업데이트 필요) |
| `05_llm/metadata-enrichment.md` | LLM 기반 메타데이터 보강 |
| `06_data/data-flow.md` | 데이터 흐름 |
| `06_data/datasource-config.md` | 엔진별 연결 설정 |
| `06_data/neo4j-schema.md` | v1 스키마 (본 문서로 대체) |
| `07_security/connection-security.md` | DB 연결 보안 (password 미저장 정책) |
| `99_decisions/ADR-003-neo4j-metadata.md` | Neo4j 선택 근거 |
| `(Core) 07_security/data-isolation.md` | 4중 격리 모델 원칙 |
| `(Core) 99_decisions/ADR-003-contextvar-multitenancy.md` | ContextVar 기반 멀티테넌트 결정 |
| `(Oracle) 06_data/neo4j-schema.md` | Oracle 소유 노드 상세 |
| `(Synapse) 06_data/neo4j-schema.md` | Synapse 온톨로지 노드 상세 |
| `(Core) 06_data/database-operations.md` | Neo4j 백업/복구, FabricSnapshot 관리, DR 전략 |
