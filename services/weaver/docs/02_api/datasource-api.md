# 데이터소스 API

> 구현 상태 태그: `Partial`
> 기준일: 2026-02-21

<!-- affects: frontend, backend, data -->
<!-- requires-update: 04_frontend/ (Canvas 데이터소스 관리 UI) -->

## 이 문서가 답하는 질문

- 데이터소스를 어떻게 생성/조회/삭제하는가?
- 각 필드의 nullable 여부와 타입은 무엇인가?
- 어떤 권한이 필요한가?
- 에러 코드의 의미는 무엇인가?

---

## 1. 엔드포인트 목록

| 메서드 | 경로 | 설명 | 상태 | 근거(구현/티켓) |
|--------|------|------|------|------------------|
| `GET` | `/api/datasources/types` | 지원 DB 타입 목록 + 설정 스키마 | Planned | `docs/implementation-plans/weaver/95_sprint2-ticket-board.md` |
| `GET` | `/api/datasources/supported-engines` | 메타데이터 추출 지원 엔진 목록 | Planned | `docs/implementation-plans/weaver/95_sprint2-ticket-board.md` |
| `GET` | `/api/datasources` | 등록된 데이터소스 목록 조회 | Planned | `docs/implementation-plans/weaver/95_sprint2-ticket-board.md` |
| `POST` | `/api/datasources` | 새 데이터소스 생성 | Planned | `docs/implementation-plans/weaver/95_sprint2-ticket-board.md` |
| `GET` | `/api/datasources/{name}` | 특정 데이터소스 상세 조회 | Planned | `docs/implementation-plans/weaver/95_sprint2-ticket-board.md` |
| `DELETE` | `/api/datasources/{name}` | 데이터소스 삭제 | Planned | `docs/implementation-plans/weaver/95_sprint2-ticket-board.md` |
| `PUT` | `/api/datasources/{name}/connection` | 연결 정보 업데이트 | Planned | `docs/implementation-plans/weaver/95_sprint2-ticket-board.md` |
| `GET` | `/api/datasources/{name}/health` | 데이터소스 연결 상태 확인 | Planned | `docs/implementation-plans/weaver/95_sprint2-ticket-board.md` |
| `POST` | `/api/datasources/{name}/test` | 연결 테스트 (생성 전 검증) | Planned | `docs/implementation-plans/weaver/95_sprint2-ticket-board.md` |
| `GET` | `/api/datasources/{name}/schemas` | 스키마 목록 조회 | Planned | `docs/implementation-plans/weaver/95_sprint2-ticket-board.md` |
| `GET` | `/api/datasources/{name}/tables` | 테이블 목록 조회 | Planned | `docs/implementation-plans/weaver/95_sprint2-ticket-board.md` |
| `GET` | `/api/datasources/{name}/tables/{table}/schema` | 테이블 스키마 조회 | Planned | `docs/implementation-plans/weaver/95_sprint2-ticket-board.md` |
| `GET` | `/api/datasources/{name}/tables/{table}/sample` | 샘플 데이터 조회 | Planned | `docs/implementation-plans/weaver/95_sprint2-ticket-board.md` |

---

## 2. 데이터 모델

### 2.1 DataSourceCreate (생성 요청)

```json
{
  "name": "erp_db",
  "engine": "postgresql",
  "connection": {
    "host": "erp-db.internal",
    "port": 5432,
    "database": "enterprise_ops",
    "user": "reader",
    "password": "secure_password_123"
  },
  "description": "ERP 운영 데이터베이스"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `name` | `string` | 필수 | 데이터소스 고유 이름 (영문, 숫자, 언더스코어만 허용) |
| `engine` | `string` | 필수 | DB 엔진 타입 (`postgresql`, `mysql`, `mongodb`, `redis`, `elasticsearch`, `web`, `openai`, `neo4j`) |
| `connection` | `object` | 필수 | 엔진별 연결 파라미터 (아래 참조) |
| `description` | `string` | 선택 | 데이터소스 설명 (nullable) |

### 2.2 DataSourceResponse (응답)

```json
{
  "name": "erp_db",
  "engine": "postgresql",
  "connection": {
    "host": "erp-db.internal",
    "port": 5432,
    "database": "enterprise_ops",
    "user": "reader"
  },
  "description": "ERP 운영 데이터베이스",
  "status": "connected",
  "created_at": "2026-02-19T10:00:00Z",
  "metadata_extracted": true,
  "tables_count": 25,
  "schemas_count": 3
}
```

| 필드 | 타입 | nullable | 설명 |
|------|------|----------|------|
| `name` | `string` | No | 데이터소스 이름 |
| `engine` | `string` | No | DB 엔진 타입 |
| `connection` | `object` | No | 연결 파라미터 (**password 제외**) |
| `description` | `string` | Yes | 설명 |
| `status` | `string` | No | `connected` / `disconnected` / `error` |
| `created_at` | `datetime` | No | 생성 시각 (ISO 8601) |
| `metadata_extracted` | `boolean` | No | 메타데이터 추출 완료 여부 |
| `tables_count` | `integer` | Yes | 추출된 테이블 수 (미추출 시 null) |
| `schemas_count` | `integer` | Yes | 추출된 스키마 수 (미추출 시 null) |

**보안 규칙**: 응답에 `password`를 **절대 포함하지 않는다**.

---

## 3. 엔드포인트 상세

### 3.1 GET /api/datasources/types

지원하는 DB 엔진 타입과 각 엔진의 연결 설정 스키마를 반환한다.

**요청**: 파라미터 없음

**응답 예시**:

```json
{
  "types": [
    {
      "engine": "postgresql",
      "label": "PostgreSQL",
      "icon": "postgresql",
      "connection_schema": {
        "host": {"type": "string", "required": true, "placeholder": "localhost"},
        "port": {"type": "integer", "required": false, "default": 5432},
        "database": {"type": "string", "required": true},
        "user": {"type": "string", "required": true},
        "password": {"type": "string", "required": true, "secret": true},
        "sslmode": {"type": "string", "required": false, "enum": ["disable", "require", "verify-ca", "verify-full"]}
      },
      "supports_metadata_extraction": true
    },
    {
      "engine": "mysql",
      "label": "MySQL",
      "icon": "mysql",
      "connection_schema": {
        "host": {"type": "string", "required": true},
        "port": {"type": "integer", "required": false, "default": 3306},
        "database": {"type": "string", "required": true},
        "user": {"type": "string", "required": true},
        "password": {"type": "string", "required": true, "secret": true}
      },
      "supports_metadata_extraction": true
    },
    {
      "engine": "mongodb",
      "label": "MongoDB",
      "icon": "mongodb",
      "connection_schema": {
        "host": {"type": "string", "required": true},
        "port": {"type": "integer", "required": false, "default": 27017},
        "database": {"type": "string", "required": true},
        "username": {"type": "string", "required": false},
        "password": {"type": "string", "required": false, "secret": true}
      },
      "supports_metadata_extraction": false
    }
  ]
}
```

---

### 3.2 GET /api/datasources/supported-engines

메타데이터 추출(스키마 인트로스펙션)을 지원하는 엔진 목록.

**응답 예시**:

```json
{
  "supported_engines": ["postgresql", "mysql", "oracle"]
}
```

---

### 3.3 POST /api/datasources

새 데이터소스를 생성한다.

**요청**:

```json
{
  "name": "erp_db",
  "engine": "postgresql",
  "connection": {
    "host": "erp-db.internal",
    "port": 5432,
    "database": "enterprise_ops",
    "user": "reader",
    "password": "secure_password_123"
  },
  "description": "ERP 운영 데이터베이스"
}
```

**처리 순서**:

1. 입력 검증 (Pydantic)
2. 이름 중복 확인 (MindsDB `SHOW DATABASES`)
3. MindsDB에 `CREATE DATABASE` 실행
4. Neo4j에 `:DataSource` 노드 생성
5. 연결 테스트
6. 응답 반환

**성공 응답** (201 Created):

```json
{
  "name": "erp_db",
  "engine": "postgresql",
  "connection": {
    "host": "erp-db.internal",
    "port": 5432,
    "database": "enterprise_ops",
    "user": "reader"
  },
  "status": "connected",
  "created_at": "2026-02-19T10:00:00Z",
  "metadata_extracted": false
}
```

**에러 응답**:

| HTTP 코드 | 에러 코드 | 설명 |
|-----------|----------|------|
| 400 | `INVALID_ENGINE` | 지원하지 않는 엔진 타입 |
| 400 | `INVALID_NAME` | 이름 형식 불일치 (영문/숫자/언더스코어만) |
| 409 | `DUPLICATE_NAME` | 이미 존재하는 데이터소스 이름 |
| 422 | `MISSING_PARAM` | 필수 연결 파라미터 누락 |
| 502 | `MINDSDB_ERROR` | MindsDB 데이터소스 생성 실패 |
| 503 | `MINDSDB_UNAVAILABLE` | MindsDB 서버 접근 불가 |

---

### 3.4 GET /api/datasources

등록된 모든 데이터소스 목록을 반환한다.

**응답 예시**:

```json
{
  "datasources": [
    {
      "name": "erp_db",
      "engine": "postgresql",
      "status": "connected",
      "description": "ERP 운영 데이터베이스",
      "tables_count": 25,
      "metadata_extracted": true
    },
    {
      "name": "finance_db",
      "engine": "mysql",
      "status": "connected",
      "description": "재무 시스템 데이터",
      "tables_count": 12,
      "metadata_extracted": true
    }
  ],
  "total": 2
}
```

---

### 3.5 GET /api/datasources/{name}

특정 데이터소스의 상세 정보를 반환한다.

**에러**: 404 `NOT_FOUND` - 존재하지 않는 데이터소스

---

### 3.6 DELETE /api/datasources/{name}

데이터소스를 삭제한다.

**처리 순서**:

1. MindsDB에서 `DROP DATABASE {name}` 실행
2. Neo4j에서 해당 DataSource 노드와 하위 노드(Schema, Table, Column) 모두 삭제
3. 성공 응답 반환

**응답** (200 OK):

```json
{
  "message": "DataSource 'erp_db' deleted successfully",
  "deleted_metadata": {
    "schemas": 3,
    "tables": 25,
    "columns": 150
  }
}
```

---

### 3.7 PUT /api/datasources/{name}/connection

연결 정보를 업데이트한다. 비밀번호 변경 시 사용.

**요청**:

```json
{
  "host": "new-erp-db.internal",
  "port": 5432,
  "password": "new_password"
}
```

**참고**: 부분 업데이트 지원. 전달하지 않은 필드는 기존 값 유지.

---

### 3.8 GET /api/datasources/{name}/health

데이터소스의 현재 연결 상태를 확인한다.

**응답 예시** (정상):

```json
{
  "name": "erp_db",
  "status": "healthy",
  "response_time_ms": 23,
  "checked_at": "2026-02-19T10:05:00Z"
}
```

**응답 예시** (비정상):

```json
{
  "name": "erp_db",
  "status": "unhealthy",
  "error": "Connection timed out",
  "checked_at": "2026-02-19T10:05:00Z"
}
```

---

### 3.9 POST /api/datasources/{name}/test

데이터소스 생성 전 연결 테스트. MindsDB를 경유하지 않고 직접 연결한다.

**요청**: DataSourceCreate와 동일 형식

**응답 예시**:

```json
{
  "success": true,
  "engine": "postgresql",
  "server_version": "15.4",
  "response_time_ms": 45
}
```

---

### 3.10 GET /api/datasources/{name}/schemas

데이터소스의 스키마 목록을 반환한다.

**응답 예시**:

```json
{
  "datasource": "erp_db",
  "schemas": [
    {"name": "public", "tables_count": 15},
    {"name": "operations", "tables_count": 8},
    {"name": "audit", "tables_count": 2}
  ]
}
```

---

### 3.11 GET /api/datasources/{name}/tables

데이터소스의 테이블 목록을 반환한다.

**쿼리 파라미터**:

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| `schema` | `string` | 선택 | 특정 스키마로 필터링 |

**응답 예시**:

```json
{
  "datasource": "erp_db",
  "tables": [
    {
      "schema": "public",
      "name": "processes",
      "type": "BASE TABLE",
      "comment": "비즈니스 프로세스 정보",
      "row_count": 15420,
      "columns_count": 12
    },
    {
      "schema": "public",
      "name": "stakeholders",
      "type": "BASE TABLE",
      "comment": "이해관계자 정보",
      "row_count": 87650,
      "columns_count": 8
    }
  ]
}
```

---

### 3.12 GET /api/datasources/{name}/tables/{table}/schema

특정 테이블의 컬럼 정보와 FK 관계를 반환한다.

**쿼리 파라미터**:

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| `schema` | `string` | 선택 | 스키마 이름 (기본값: `public`) |

**응답 예시**:

```json
{
  "datasource": "erp_db",
  "schema": "public",
  "table": "processes",
  "comment": "비즈니스 프로세스 정보",
  "row_count": 15420,
  "columns": [
    {
      "name": "id",
      "type": "bigint",
      "nullable": false,
      "primary_key": true,
      "default": "nextval('processes_id_seq'::regclass)",
      "description": "프로세스 고유 ID"
    },
    {
      "name": "process_code",
      "type": "character varying",
      "nullable": false,
      "primary_key": false,
      "max_length": 50,
      "description": "프로세스 코드 (예: PROC-2026-001)"
    },
    {
      "name": "org_id",
      "type": "bigint",
      "nullable": false,
      "primary_key": false,
      "foreign_key": {
        "target_schema": "public",
        "target_table": "organizations",
        "target_column": "id"
      },
      "description": "대상 조직 FK"
    },
    {
      "name": "process_type",
      "type": "character varying",
      "nullable": false,
      "primary_key": false,
      "max_length": 20,
      "description": "프로세스 유형 (procurement/sales/hr/finance)"
    },
    {
      "name": "started_at",
      "type": "timestamp with time zone",
      "nullable": true,
      "primary_key": false,
      "description": "시작일"
    }
  ],
  "foreign_keys": [
    {
      "constraint_name": "fk_processes_org",
      "source_column": "org_id",
      "target_schema": "public",
      "target_table": "organizations",
      "target_column": "id"
    }
  ]
}
```

---

### 3.13 GET /api/datasources/{name}/tables/{table}/sample

테이블의 샘플 데이터를 반환한다.

**쿼리 파라미터**:

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `schema` | `string` | 선택 | `public` | 스키마 이름 |
| `limit` | `integer` | 선택 | `5` | 반환 행 수 (최대 100) |

**응답 예시**:

```json
{
  "datasource": "erp_db",
  "schema": "public",
  "table": "processes",
  "columns": ["id", "process_code", "org_id", "process_type", "started_at"],
  "rows": [
    [1, "PROC-2026-001", 42, "procurement", "2026-01-15T09:00:00Z"],
    [2, "PROC-2026-002", 43, "sales", "2026-01-16T10:30:00Z"],
    [3, "PROC-2026-003", 44, "finance", "2026-01-17T14:00:00Z"]
  ],
  "total_rows": 15420,
  "returned_rows": 3
}
```

---

## 4. 공통 에러 형식

모든 에러 응답은 아래 형식을 따른다.

```json
{
  "error": {
    "code": "DUPLICATE_NAME",
    "message": "DataSource with name 'erp_db' already exists",
    "details": null
  }
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `error.code` | `string` | 에러 코드 (프로그래밍용) |
| `error.message` | `string` | 사람이 읽을 수 있는 에러 설명 |
| `error.details` | `object` | 추가 정보 (nullable) |

---

## 5. 권한

| 작업 | 필요 권한 | 비고 |
|------|----------|------|
| 목록 조회 | `datasource:read` | 모든 인증된 사용자 |
| 상세 조회 | `datasource:read` | - |
| 생성 | `datasource:write` | 관리자 |
| 삭제 | `datasource:delete` | 관리자 |
| 연결 업데이트 | `datasource:write` | 관리자 |
| 스키마/테이블 조회 | `datasource:read` | - |
| 샘플 데이터 | `datasource:read` | 민감 데이터 마스킹 필요 |

---

## 6. 관련 문서

| 문서 | 설명 |
|------|------|
| `02_api/metadata-api.md` | 메타데이터 추출 API (SSE 스트리밍) |
| `02_api/query-api.md` | SQL 쿼리 실행 API |
| `06_data/datasource-config.md` | 엔진별 연결 설정 파라미터 상세 |
| `07_security/connection-security.md` | 연결 보안 정책 |
