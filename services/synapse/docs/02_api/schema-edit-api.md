# 스키마 편집 API

## 이 문서가 답하는 질문

- 테이블/컬럼의 설명(description)을 어떻게 편집하는가?
- FK 관계를 수동으로 추가/수정/삭제하는 API는?
- 스키마 편집이 Oracle Text2SQL에 어떤 영향을 미치는가?
- K-AIR text2sql의 스키마 편집 API에서 무엇이 변경되었는가?

<!-- affects: backend, frontend -->
<!-- requires-update: 03_backend/neo4j-bootstrap.md -->

---

## 1. 기본 정보

| 항목 | 값 |
|------|---|
| Base URL | `/api/v3/synapse/schema-edit` |
| 인증 | JWT Bearer Token (Core 경유) |
| K-AIR 원본 | `/schema-edit/tables/*/description`, `/schema-edit/relationships` |

---

## 2. 엔드포인트 목록

| Method | Path | 설명 | K-AIR 대응 |
|--------|------|------|-----------|
| GET | `/tables` | 전체 테이블 목록 | (이식) |
| GET | `/tables/{table_name}` | 테이블 상세 + 컬럼 | (이식) |
| PUT | `/tables/{table_name}/description` | 테이블 설명 수정 | `/schema-edit/tables/{name}/description` |
| PUT | `/columns/{table_name}/{column_name}/description` | 컬럼 설명 수정 | (이식) |
| GET | `/relationships` | FK 관계 목록 | `/schema-edit/relationships` |
| POST | `/relationships` | FK 관계 추가 | `/schema-edit/relationships` |
| DELETE | `/relationships/{rel_id}` | FK 관계 삭제 | (이식) |
| POST | `/tables/{table_name}/embedding` | 테이블 임베딩 재생성 | 신규 |
| POST | `/batch-update-embeddings` | 전체 임베딩 일괄 재생성 | 신규 |

---

## 3. 엔드포인트 상세

### 3.1 GET /tables

전체 테이블 목록을 반환한다.

#### Response (200 OK)

```json
{
  "success": true,
  "data": {
    "tables": [
      {
        "name": "processes",
        "description": "프로세스 실행 내역. 각 프로세스의 유형, 지표, 상태를 기록한다.",
        "row_count": 1250,
        "column_count": 15,
        "has_embedding": true,
        "last_updated": "2024-06-01T09:00:00Z"
      },
      {
        "name": "organizations",
        "description": "이해관계자 정보. 기업/기관 이해관계자의 기본 정보와 연락처를 관리한다.",
        "row_count": 320,
        "column_count": 12,
        "has_embedding": true,
        "last_updated": "2024-06-01T09:00:00Z"
      }
    ],
    "total": 25
  }
}
```

---

### 3.2 PUT /tables/{table_name}/description

테이블의 자연어 설명을 수정한다. 설명 변경 시 임베딩이 자동으로 재생성된다.

**이 API가 중요한 이유**: Oracle Text2SQL이 벡터 검색 시 테이블 설명의 임베딩을 사용한다. 설명이 정확할수록 SQL 생성 정확도가 올라간다.

#### Request

```json
PUT /api/v3/synapse/schema-edit/tables/processes/description
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "description": "프로세스 실행 내역. 비즈니스 프로세스에서 각 단계의 유형(데이터 수집/분석/최적화/실행), 입력 지표, 출력 지표, 상태를 기록한다. case_id로 프로젝트별 격리된다."
}
```

| 필드 | 타입 | 필수 | nullable | 설명 |
|------|------|------|----------|------|
| `description` | string | Y | N | 테이블 설명 (한국어 권장, 최대 500자) |

#### Response (200 OK)

```json
{
  "success": true,
  "data": {
    "table_name": "processes",
    "description": "프로세스 실행 내역. 비즈니스 프로세스에서 각 단계의 유형...",
    "embedding_updated": true,
    "updated_at": "2024-06-16T10:00:00Z"
  }
}
```

#### 부수 효과

- Neo4j Table 노드의 `description` 속성 업데이트
- `embedding` 속성 자동 재생성 (text-embedding-3-small)
- `table_vector` 인덱스 자동 갱신

---

### 3.3 PUT /columns/{table_name}/{column_name}/description

컬럼의 자연어 설명을 수정한다.

#### Request

```json
PUT /api/v3/synapse/schema-edit/columns/processes/efficiency_rate/description
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "description": "프로세스 효율성 비율. 해당 프로세스의 입력 대비 출력 비율 (%). NULL이면 미측정 프로세스."
}
```

---

### 3.4 POST /relationships

FK 관계를 수동으로 추가한다. 물리적 FK가 없지만 논리적으로 연관된 테이블 간의 관계를 정의할 때 사용한다.

#### Request

```json
POST /api/v3/synapse/schema-edit/relationships
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "source_table": "processes",
  "source_column": "org_id",
  "target_table": "organizations",
  "target_column": "id",
  "relationship_type": "FK_TO",
  "description": "프로세스의 소속 조직 참조"
}
```

| 필드 | 타입 | 필수 | nullable | 설명 |
|------|------|------|----------|------|
| `source_table` | string | Y | N | FK가 있는 테이블 |
| `source_column` | string | Y | N | FK 컬럼 |
| `target_table` | string | Y | N | 참조 대상 테이블 |
| `target_column` | string | Y | N | 참조 대상 컬럼 (보통 id) |
| `relationship_type` | string | N | N | FK_TO (기본값) |
| `description` | string | N | Y | 관계 설명 |

#### Cypher (내부 실행)

```cypher
MATCH (src:Column {table_name: $source_table, name: $source_column})
MATCH (tgt:Column {table_name: $target_table, name: $target_column})
MERGE (src)-[r:FK_TO]->(tgt)
SET r.description = $description,
    r.created_at = datetime(),
    r.source = 'manual'
RETURN r
```

#### Response (201 Created)

```json
{
  "success": true,
  "data": {
    "id": "rel-uuid",
    "source": "processes.org_id",
    "target": "organizations.id",
    "type": "FK_TO",
    "description": "프로세스의 소속 조직 참조"
  }
}
```

---

### 3.5 POST /batch-update-embeddings

모든 테이블/컬럼의 임베딩을 일괄 재생성한다. 초기 설정이나 대량 설명 변경 후 사용한다.

#### Request

```json
POST /api/v3/synapse/schema-edit/batch-update-embeddings
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "target": "all",
  "force": false
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `target` | string | N | all, tables, columns (기본: all) |
| `force` | bool | N | true면 기존 임베딩 있어도 재생성 |

#### Response (202 Accepted)

```json
{
  "success": true,
  "data": {
    "task_id": "task-uuid",
    "target": "all",
    "estimated_count": 350,
    "status": "processing"
  }
}
```

---

## 4. 에러 코드

| HTTP Status | Code | 의미 |
|------------|------|------|
| 400 | `INVALID_TABLE_NAME` | 존재하지 않는 테이블 |
| 400 | `INVALID_COLUMN_NAME` | 존재하지 않는 컬럼 |
| 400 | `DUPLICATE_RELATIONSHIP` | 이미 존재하는 FK 관계 |
| 400 | `SELF_REFERENCE` | 자기 참조 (동일 테이블-컬럼) |
| 404 | `RELATIONSHIP_NOT_FOUND` | FK 관계 없음 |
| 403 | `ACCESS_DENIED` | 편집 권한 없음 |

---

## 5. 권한

| 엔드포인트 | 필요 역할 |
|----------|---------|
| GET (조회) | schema_viewer, schema_editor, admin |
| PUT, POST, DELETE (편집) | schema_editor, admin |
| batch-update-embeddings | admin |

---

## 6. K-AIR 이식 변경점

| 항목 | K-AIR 원본 | Axiom Synapse |
|------|-----------|--------------|
| URL 접두어 | `/schema-edit/` | `/api/v3/synapse/schema-edit/` |
| 인증 | Supabase Auth | JWT (Core 경유) |
| 임베딩 재생성 | 수동 트리거 필요 | 설명 변경 시 자동 |
| 배치 임베딩 | 없음 | 신규 추가 |
| 에러 형식 | 비표준 | Axiom 표준 에러 형식 |

---

## 근거 문서

- K-AIR `app/routers/schema_edit.py` 원본 코드
- `06_data/vector-indexes.md` (벡터 인덱스 설계)
- `01_architecture/graph-search.md` (검색과의 연관)
