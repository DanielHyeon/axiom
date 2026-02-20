# 메타데이터 카탈로그 API

<!-- affects: api, frontend -->
<!-- requires-update: 04_frontend/datasource-manager.md (Canvas), 06_data/neo4j-schema.md -->

> **상태**: Planned (Experimental Spec)
> **구현 상태**: 계약/스키마 정의 완료, 런타임 구현은 Sprint 수행 후 활성화
> **정합성 기준**: `01_architecture/metadata-service.md`의 Business Glossary 상태와 동기화

## 이 문서가 답하는 질문

- 메타데이터 카탈로그 API의 전체 엔드포인트 목록은?
- 비즈니스 용어 사전 API는 어떻게 동작하는가?
- 패브릭 스냅샷 API는 어떻게 동작하는가?
- 테이블/컬럼 태깅 API는?
- 메타데이터 검색 API는?
- 메타데이터 통계 API는?

---

## 1. API 개요

### 1.1 기존 API vs 신규 API

Weaver는 "Data Fabric"에서 **"Data Fabric + Metadata Service"**로 승격된다. 기존 메타데이터 추출 API(스키마 인트로스펙션)에 더해, 카탈로그 기능을 제공하는 신규 API를 추가한다.

| 구분 | 기존 (`metadata-api.md`) | 신규 (이 문서) |
|------|--------------------------|---------------|
| **목적** | 스키마 인트로스펙션 (추출) | 메타데이터 카탈로그 (관리) |
| **방식** | SSE 스트리밍 실시간 추출 | REST CRUD + 검색 |
| **Base URL** | `/api/datasources/{name}/extract-metadata` | `/api/v1/metadata/...` |
| **주요 기능** | DB 직접 연결 -> 스키마/테이블/컬럼/FK 추출 | 비즈니스 용어 사전, 태깅, 스냅샷, 검색, 통계 |
| **저장소** | Neo4j (메타데이터 그래프) | Neo4j + PostgreSQL (용어 사전, 태그) |
| **인증** | JWT (`require_auth`) | JWT (`require_auth`, tenant_id 기반 격리) |

### 1.2 Base URL

```
/api/v1/metadata
```

**인증 요구사항**:
- 모든 엔드포인트는 JWT Bearer 인증을 요구한다.
- `tenant_id`는 JWT payload에서 추출한다 (요청 파라미터로 받지 않는다).
- `case_id`는 경로 파라미터 또는 쿼리 파라미터로 지정한다.
- DataSource `name`은 `(tenant_id, case_id)` 범위 내에서 고유하다.

```python
# JWT payload 구조 (Core auth-model.md 참조)
{
    "sub": "user-uuid",
    "tenant_id": "tenant-uuid",
    "role": "manager",
    "permissions": ["case:read", "case:write", "metadata:read", "metadata:write"],
    "iat": 1708300000,
    "exp": 1708300900
}
```

### 1.3 멀티테넌시 격리

```
[필수] tenant_id는 JWT에서만 추출한다 (사용자 입력 금지).
[필수] 모든 카탈로그 데이터는 tenant_id로 격리한다.
[필수] case_id는 경로 파라미터 또는 쿼리 파라미터로 명시한다.
[필수] 용어 사전(glossary)은 테넌트 전체 범위에서 공유한다 (case_id 무관).
[금지] 한 테넌트의 카탈로그 데이터를 다른 테넌트가 조회/수정할 수 없다.
```

### 1.4 전체 엔드포인트 목록

| 메서드 | 경로 | 설명 | 권한 |
|--------|------|------|------|
| **패브릭 스냅샷** |
| `POST` | `/api/v1/metadata/cases/{case_id}/datasources/{ds_name}/snapshots` | 스냅샷 생성 | `metadata:write` |
| `GET` | `/api/v1/metadata/cases/{case_id}/datasources/{ds_name}/snapshots` | 스냅샷 목록 조회 | `metadata:read` |
| `GET` | `/api/v1/metadata/cases/{case_id}/datasources/{ds_name}/snapshots/{snapshot_id}` | 스냅샷 상세 조회 | `metadata:read` |
| `GET` | `/api/v1/metadata/cases/{case_id}/datasources/{ds_name}/snapshots/diff` | 스냅샷 Diff | `metadata:read` |
| `POST` | `/api/v1/metadata/cases/{case_id}/datasources/{ds_name}/snapshots/{snapshot_id}/restore` | 스냅샷 복원 | `admin` |
| `DELETE` | `/api/v1/metadata/cases/{case_id}/datasources/{ds_name}/snapshots/{snapshot_id}` | 스냅샷 삭제 | `admin` |
| **비즈니스 용어 사전** |
| `POST` | `/api/v1/metadata/glossary` | 용어 생성 (Planned) | `metadata:write` |
| `GET` | `/api/v1/metadata/glossary` | 용어 목록 조회 (Planned) | `metadata:read` |
| `GET` | `/api/v1/metadata/glossary/{term_id}` | 용어 상세 조회 (Planned) | `metadata:read` |
| `PUT` | `/api/v1/metadata/glossary/{term_id}` | 용어 수정 (Planned) | `metadata:write` |
| `DELETE` | `/api/v1/metadata/glossary/{term_id}` | 용어 삭제 (Planned) | `metadata:write` |
| `GET` | `/api/v1/metadata/glossary/search` | 용어 검색 (Planned) | `metadata:read` |
| **테이블/컬럼 태깅** |
| `POST` | `/api/v1/metadata/cases/{case_id}/datasources/{ds_name}/tables/{table_name}/tags` | 테이블 태그 추가 | `metadata:write` |
| `GET` | `/api/v1/metadata/cases/{case_id}/datasources/{ds_name}/tables/{table_name}/tags` | 테이블 태그 조회 | `metadata:read` |
| `DELETE` | `/api/v1/metadata/cases/{case_id}/datasources/{ds_name}/tables/{table_name}/tags/{tag}` | 테이블 태그 삭제 | `metadata:write` |
| `POST` | `/api/v1/metadata/cases/{case_id}/datasources/{ds_name}/tables/{table_name}/columns/{column_name}/tags` | 컬럼 태그 추가 | `metadata:write` |
| `GET` | `/api/v1/metadata/cases/{case_id}/datasources/{ds_name}/tables/{table_name}/columns/{column_name}/tags` | 컬럼 태그 조회 | `metadata:read` |
| `DELETE` | `/api/v1/metadata/cases/{case_id}/datasources/{ds_name}/tables/{table_name}/columns/{column_name}/tags/{tag}` | 컬럼 태그 삭제 | `metadata:write` |
| `GET` | `/api/v1/metadata/tags/{tag}/entities` | 태그별 엔티티 검색 | `metadata:read` |
| **메타데이터 검색** |
| `GET` | `/api/v1/metadata/search` | 통합 검색 | `metadata:read` |
| `GET` | `/api/v1/metadata/cases/{case_id}/datasources/{ds_name}/schemas` | 스키마 목록 | `metadata:read` |
| `GET` | `/api/v1/metadata/cases/{case_id}/datasources/{ds_name}/schemas/{schema_name}/tables` | 테이블 목록 | `metadata:read` |
| `GET` | `/api/v1/metadata/cases/{case_id}/datasources/{ds_name}/schemas/{schema_name}/tables/{table_name}/columns` | 컬럼 목록 | `metadata:read` |
| **메타데이터 통계** |
| `GET` | `/api/v1/metadata/cases/{case_id}/datasources/{ds_name}/stats` | 데이터소스별 통계 | `metadata:read` |
| `GET` | `/api/v1/metadata/stats` | 테넌트 전체 통계 | `metadata:read` |

---

## 2. 패브릭 스냅샷 API

패브릭 스냅샷은 특정 시점의 **메타데이터 그래프 전체 상태**를 캡처한 것이다. DB 마이그레이션 전후 비교, 스키마 변경 이력 추적, 문제 발생 시 메타데이터 롤백에 사용한다.

### 2.1 스냅샷 생성

```
POST /api/v1/metadata/cases/{case_id}/datasources/{ds_name}/snapshots
Content-Type: application/json
Authorization: Bearer {jwt_token}
```

**경로 파라미터**:

| 파라미터 | 타입 | 설명 |
|---------|------|------|
| `case_id` | `UUID` | 케이스 ID |
| `ds_name` | `string` | 데이터소스 이름 |

**요청 본문**:

```json
{
  "description": "ERP 마이그레이션 전 스냅샷"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `description` | `string` | 선택 | 스냅샷 설명 (최대 500자) |

**성공 응답** (202 Accepted):

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "datasource": "erp_db",
  "case_id": "case-uuid-1234",
  "version": 3,
  "status": "creating",
  "description": "ERP 마이그레이션 전 스냅샷",
  "created_by": "user-uuid",
  "created_at": "2026-02-20T09:00:00Z",
  "summary": null
}
```

**동작 방식**:
- **비동기 작업**: 요청 즉시 202를 반환하고, 백그라운드에서 Neo4j 그래프 순회를 실행한다.
- `version`은 해당 데이터소스 내에서 자동 증가한다.
- `status`는 `creating` -> `ready` 또는 `creating` -> `failed`로 전이한다.
- 스냅샷 데이터는 Neo4j의 별도 서브그래프 또는 PostgreSQL JSON 컬럼에 저장한다.

**에러 응답**:

| HTTP 코드 | 에러 코드 | 설명 |
|-----------|----------|------|
| 404 | `DATASOURCE_NOT_FOUND` | 지정한 데이터소스가 존재하지 않음 |
| 409 | `SNAPSHOT_IN_PROGRESS` | 이미 스냅샷 생성이 진행 중 |
| 422 | `NO_METADATA` | 해당 데이터소스에 추출된 메타데이터가 없음 |

### 2.2 스냅샷 목록 조회

```
GET /api/v1/metadata/cases/{case_id}/datasources/{ds_name}/snapshots
Authorization: Bearer {jwt_token}
```

**쿼리 파라미터**:

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `page` | `integer` | 선택 | `1` | 페이지 번호 (1-based) |
| `size` | `integer` | 선택 | `20` | 페이지 크기 (최대 100) |
| `sort_by` | `string` | 선택 | `created_at` | 정렬 기준 (`version`, `created_at`) |
| `sort_order` | `string` | 선택 | `desc` | 정렬 방향 (`asc`, `desc`) |

**성공 응답** (200 OK):

```json
{
  "items": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "version": 3,
      "status": "ready",
      "description": "ERP 마이그레이션 전 스냅샷",
      "created_by": "user-uuid",
      "created_at": "2026-02-20T09:00:00Z",
      "summary": {
        "schemas": 3,
        "tables": 45,
        "columns": 312,
        "fk_relations": 28
      }
    },
    {
      "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "version": 2,
      "status": "ready",
      "description": "정기 스냅샷",
      "created_by": "user-uuid",
      "created_at": "2026-02-13T09:00:00Z",
      "summary": {
        "schemas": 3,
        "tables": 43,
        "columns": 298,
        "fk_relations": 26
      }
    }
  ],
  "total": 3,
  "page": 1,
  "size": 20,
  "pages": 1
}
```

### 2.3 스냅샷 상세 조회

```
GET /api/v1/metadata/cases/{case_id}/datasources/{ds_name}/snapshots/{snapshot_id}
Authorization: Bearer {jwt_token}
```

**성공 응답** (200 OK):

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "datasource": "erp_db",
  "case_id": "case-uuid-1234",
  "version": 3,
  "status": "ready",
  "description": "ERP 마이그레이션 전 스냅샷",
  "created_by": "user-uuid",
  "created_at": "2026-02-20T09:00:00Z",
  "completed_at": "2026-02-20T09:00:05Z",
  "summary": {
    "schemas": 3,
    "tables": 45,
    "columns": 312,
    "fk_relations": 28,
    "tags_count": 15,
    "descriptions_count": 38
  },
  "graph_data": {
    "schemas": [
      {
        "name": "public",
        "tables_count": 25,
        "tables": [
          {
            "name": "processes",
            "description": "비즈니스 프로세스 정보",
            "row_count": 15420,
            "columns_count": 12,
            "tags": ["core", "audit-required"]
          },
          {
            "name": "organizations",
            "description": "대상 조직 정보",
            "row_count": 8750,
            "columns_count": 8,
            "tags": ["pii"]
          }
        ]
      },
      {
        "name": "operations",
        "tables_count": 12,
        "tables": []
      }
    ]
  }
}
```

**에러 응답**:

| HTTP 코드 | 에러 코드 | 설명 |
|-----------|----------|------|
| 404 | `SNAPSHOT_NOT_FOUND` | 지정한 스냅샷이 존재하지 않음 |

### 2.4 스냅샷 Diff

두 스냅샷 버전 간의 메타데이터 변경 사항을 비교한다.

```
GET /api/v1/metadata/cases/{case_id}/datasources/{ds_name}/snapshots/diff?from={v1}&to={v2}
Authorization: Bearer {jwt_token}
```

**쿼리 파라미터**:

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| `from` | `integer` | 필수 | 비교 기준 버전 (이전) |
| `to` | `integer` | 필수 | 비교 대상 버전 (이후) |

**성공 응답** (200 OK):

```json
{
  "datasource": "erp_db",
  "from_version": 2,
  "to_version": 3,
  "from_snapshot_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
  "to_snapshot_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "diff": {
    "schemas_added": [],
    "schemas_removed": [],
    "tables_added": [
      {
        "schema": "public",
        "name": "audit_logs",
        "columns_count": 8
      },
      {
        "schema": "public",
        "name": "process_comments",
        "columns_count": 6
      }
    ],
    "tables_removed": [],
    "columns_added": [
      {
        "fqn": "public.processes.priority_level",
        "dtype": "VARCHAR(20)",
        "nullable": true
      },
      {
        "fqn": "public.processes.updated_by",
        "dtype": "BIGINT",
        "nullable": true
      }
    ],
    "columns_removed": [
      {
        "fqn": "public.stakeholders.legacy_code",
        "dtype": "VARCHAR(50)"
      }
    ],
    "columns_modified": [
      {
        "fqn": "public.organizations.business_number",
        "changes": {
          "dtype": {
            "from": "VARCHAR(10)",
            "to": "VARCHAR(13)"
          }
        }
      },
      {
        "fqn": "public.transactions.amount",
        "changes": {
          "dtype": {
            "from": "DECIMAL(12,2)",
            "to": "DECIMAL(18,2)"
          },
          "nullable": {
            "from": true,
            "to": false
          }
        }
      }
    ],
    "fk_added": [
      {
        "source": "public.process_comments.process_id",
        "target": "public.processes.id"
      }
    ],
    "fk_removed": [],
    "tags_added": [
      {
        "entity_fqn": "public.audit_logs",
        "tag": "audit-required"
      }
    ],
    "tags_removed": []
  },
  "summary": {
    "tables_added": 2,
    "tables_removed": 0,
    "columns_added": 2,
    "columns_removed": 1,
    "columns_modified": 2,
    "fk_added": 1,
    "fk_removed": 0,
    "total_changes": 8
  }
}
```

**에러 응답**:

| HTTP 코드 | 에러 코드 | 설명 |
|-----------|----------|------|
| 400 | `INVALID_VERSION_RANGE` | `from` >= `to` 또는 유효하지 않은 버전 번호 |
| 404 | `SNAPSHOT_VERSION_NOT_FOUND` | 지정한 버전의 스냅샷이 존재하지 않음 |

### 2.5 스냅샷 복원

특정 스냅샷의 메타데이터 그래프 상태로 복원한다.

```
POST /api/v1/metadata/cases/{case_id}/datasources/{ds_name}/snapshots/{snapshot_id}/restore
Authorization: Bearer {jwt_token}
```

**성공 응답** (202 Accepted):

```json
{
  "restore_id": "r1a2b3c4-d5e6-7890-abcd-ef1234567890",
  "snapshot_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "snapshot_version": 3,
  "status": "restoring",
  "initiated_by": "admin-user-uuid",
  "initiated_at": "2026-02-20T11:00:00Z"
}
```

**주의사항**:

```
[주의] 메타데이터 그래프만 복원한다. 실제 데이터베이스 스키마에는 영향을 주지 않는다.
[필수] admin 역할만 실행할 수 있다.
[필수] 복원 완료 후 change_propagation 이벤트를 발행한다.
[필수] 복원 전 현재 상태의 자동 스냅샷을 생성한다 (안전장치).
```

**에러 응답**:

| HTTP 코드 | 에러 코드 | 설명 |
|-----------|----------|------|
| 403 | `ADMIN_REQUIRED` | admin 역할이 아닌 사용자의 요청 |
| 404 | `SNAPSHOT_NOT_FOUND` | 지정한 스냅샷이 존재하지 않음 |
| 409 | `RESTORE_IN_PROGRESS` | 이미 복원이 진행 중 |

### 2.6 스냅샷 삭제

```
DELETE /api/v1/metadata/cases/{case_id}/datasources/{ds_name}/snapshots/{snapshot_id}
Authorization: Bearer {jwt_token}
```

**성공 응답** (200 OK):

```json
{
  "message": "Snapshot v2 deleted successfully",
  "deleted_snapshot_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
  "deleted_version": 2
}
```

**제약사항**:

```
[금지] 최신(latest) 스냅샷은 삭제할 수 없다.
[필수] admin 역할만 삭제할 수 있다.
```

**에러 응답**:

| HTTP 코드 | 에러 코드 | 설명 |
|-----------|----------|------|
| 403 | `ADMIN_REQUIRED` | admin 역할이 아닌 사용자의 요청 |
| 404 | `SNAPSHOT_NOT_FOUND` | 지정한 스냅샷이 존재하지 않음 |
| 409 | `CANNOT_DELETE_LATEST` | 최신 스냅샷은 삭제 불가 |

---

## 3. 비즈니스 용어 사전 API

비즈니스 용어 사전(glossary)은 조직에서 사용하는 비즈니스 용어와 그 정의, 동의어, 관련 데이터 엔티티 간의 매핑을 관리한다. 용어 사전은 **테넌트 전체** 범위에서 공유한다 (특정 case_id에 종속되지 않는다).

### 3.1 용어 생성

```
POST /api/v1/metadata/glossary
Content-Type: application/json
Authorization: Bearer {jwt_token}
```

**요청 본문**:

```json
{
  "term": "매출액",
  "definition": "기업의 주요 영업활동으로 인한 수익 총액. 상품 판매, 서비스 제공 등에서 발생하는 총수입을 의미한다.",
  "synonyms": ["매출", "revenue", "sales", "총매출"],
  "category": "financial",
  "owner": "finance-team",
  "related_columns": [
    "erp_db.public.revenue_summary.total_revenue",
    "finance_db.accounting.monthly_report.revenue_amount"
  ],
  "related_terms": [],
  "tags": ["kpi", "financial"]
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `term` | `string` | 필수 | 용어명 (테넌트 내 고유, 최대 100자) |
| `definition` | `string` | 필수 | 용어 정의 (최대 2000자) |
| `synonyms` | `string[]` | 선택 | 동의어/영문 표현 목록 |
| `category` | `string` | 선택 | 분류 (`financial`, `operational`, `legal`, `technical`, `general`) |
| `owner` | `string` | 선택 | 용어 관리 책임자/팀 |
| `related_columns` | `string[]` | 선택 | 관련 컬럼 FQN (형식: `{ds_name}.{schema}.{table}.{column}`) |
| `related_terms` | `UUID[]` | 선택 | 관련 용어 ID 목록 |
| `tags` | `string[]` | 선택 | 태그 목록 |

**성공 응답** (201 Created):

```json
{
  "id": "g1a2b3c4-d5e6-7890-abcd-ef1234567890",
  "tenant_id": "tenant-uuid",
  "term": "매출액",
  "definition": "기업의 주요 영업활동으로 인한 수익 총액. 상품 판매, 서비스 제공 등에서 발생하는 총수입을 의미한다.",
  "synonyms": ["매출", "revenue", "sales", "총매출"],
  "category": "financial",
  "owner": "finance-team",
  "related_columns": [
    "erp_db.public.revenue_summary.total_revenue",
    "finance_db.accounting.monthly_report.revenue_amount"
  ],
  "related_terms": [],
  "tags": ["kpi", "financial"],
  "created_by": "user-uuid",
  "created_at": "2026-02-20T09:30:00Z",
  "updated_at": "2026-02-20T09:30:00Z"
}
```

**에러 응답**:

| HTTP 코드 | 에러 코드 | 설명 |
|-----------|----------|------|
| 400 | `INVALID_CATEGORY` | 허용되지 않는 카테고리 값 |
| 409 | `DUPLICATE_TERM` | 테넌트 내에 동일한 용어명이 이미 존재 |
| 422 | `INVALID_COLUMN_FQN` | `related_columns`의 FQN 형식이 올바르지 않음 |

### 3.2 용어 목록 조회

```
GET /api/v1/metadata/glossary
Authorization: Bearer {jwt_token}
```

**쿼리 파라미터**:

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `page` | `integer` | 선택 | `1` | 페이지 번호 |
| `size` | `integer` | 선택 | `20` | 페이지 크기 (최대 100) |
| `category` | `string` | 선택 | 전체 | 카테고리 필터 |
| `tag` | `string` | 선택 | 전체 | 태그 필터 |
| `search` | `string` | 선택 | - | 전문 검색 (용어명, 정의, 동의어) |

**성공 응답** (200 OK):

```json
{
  "items": [
    {
      "id": "g1a2b3c4-d5e6-7890-abcd-ef1234567890",
      "term": "매출액",
      "definition": "기업의 주요 영업활동으로 인한 수익 총액...",
      "synonyms": ["매출", "revenue", "sales", "총매출"],
      "category": "financial",
      "owner": "finance-team",
      "related_columns_count": 2,
      "tags": ["kpi", "financial"],
      "updated_at": "2026-02-20T09:30:00Z"
    },
    {
      "id": "g2b3c4d5-e6f7-8901-bcde-f12345678901",
      "term": "이해관계자",
      "definition": "비즈니스 프로세스에 직간접적으로 관여하는 개인 또는 단체...",
      "synonyms": ["stakeholder", "관계자", "관련자"],
      "category": "operational",
      "owner": "bpm-team",
      "related_columns_count": 5,
      "tags": ["core"],
      "updated_at": "2026-02-19T14:00:00Z"
    }
  ],
  "total": 45,
  "page": 1,
  "size": 20,
  "pages": 3
}
```

### 3.3 용어 상세 조회

```
GET /api/v1/metadata/glossary/{term_id}
Authorization: Bearer {jwt_token}
```

**성공 응답** (200 OK):

```json
{
  "id": "g1a2b3c4-d5e6-7890-abcd-ef1234567890",
  "tenant_id": "tenant-uuid",
  "term": "매출액",
  "definition": "기업의 주요 영업활동으로 인한 수익 총액. 상품 판매, 서비스 제공 등에서 발생하는 총수입을 의미한다.",
  "synonyms": ["매출", "revenue", "sales", "총매출"],
  "category": "financial",
  "owner": "finance-team",
  "related_columns": [
    {
      "fqn": "erp_db.public.revenue_summary.total_revenue",
      "datasource": "erp_db",
      "schema": "public",
      "table": "revenue_summary",
      "column": "total_revenue",
      "dtype": "DECIMAL(18,2)",
      "exists": true
    },
    {
      "fqn": "finance_db.accounting.monthly_report.revenue_amount",
      "datasource": "finance_db",
      "schema": "accounting",
      "table": "monthly_report",
      "column": "revenue_amount",
      "dtype": "DECIMAL(15,2)",
      "exists": true
    }
  ],
  "related_terms": [
    {
      "id": "g3c4d5e6-f7a8-9012-cdef-123456789012",
      "term": "영업이익"
    }
  ],
  "tags": ["kpi", "financial"],
  "created_by": "user-uuid",
  "created_at": "2026-02-20T09:30:00Z",
  "updated_at": "2026-02-20T09:30:00Z"
}
```

### 3.4 용어 수정

```
PUT /api/v1/metadata/glossary/{term_id}
Content-Type: application/json
Authorization: Bearer {jwt_token}
```

**요청 본문**:

```json
{
  "definition": "기업의 주요 영업활동으로 인한 수익 총액. 상품 판매, 서비스 제공 등에서 발생하는 총수입을 의미하며, 부가세를 포함한 금액이다.",
  "synonyms": ["매출", "revenue", "sales", "총매출", "매출총액"],
  "related_columns": [
    "erp_db.public.revenue_summary.total_revenue",
    "finance_db.accounting.monthly_report.revenue_amount",
    "finance_db.accounting.annual_report.total_sales"
  ]
}
```

전체 교체(full replace) 방식이다. 전달하지 않은 필드는 기존 값을 유지하지 않으므로, 기존 값을 포함하여 전체를 전송해야 한다.

**성공 응답** (200 OK): 용어 상세 조회와 동일 형식.

**에러 응답**:

| HTTP 코드 | 에러 코드 | 설명 |
|-----------|----------|------|
| 404 | `TERM_NOT_FOUND` | 지정한 용어가 존재하지 않음 |
| 409 | `DUPLICATE_TERM` | 변경된 용어명이 기존 다른 용어와 중복 |

### 3.5 용어 삭제

```
DELETE /api/v1/metadata/glossary/{term_id}
Authorization: Bearer {jwt_token}
```

**성공 응답** (200 OK):

```json
{
  "message": "Glossary term '매출액' deleted successfully",
  "deleted_term_id": "g1a2b3c4-d5e6-7890-abcd-ef1234567890"
}
```

### 3.6 용어 검색

```
GET /api/v1/metadata/glossary/search?q={query}
Authorization: Bearer {jwt_token}
```

**쿼리 파라미터**:

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| `q` | `string` | 필수 | 검색어 (2글자 이상) |
| `category` | `string` | 선택 | 카테고리 필터 |
| `limit` | `integer` | 선택 | 최대 결과 수 (기본 10, 최대 50) |

**성공 응답** (200 OK):

```json
{
  "query": "매출",
  "results": [
    {
      "id": "g1a2b3c4-d5e6-7890-abcd-ef1234567890",
      "term": "매출액",
      "definition": "기업의 주요 영업활동으로 인한 수익 총액...",
      "category": "financial",
      "relevance_score": 0.95,
      "matched_on": ["term", "synonyms"],
      "related_columns": [
        "erp_db.public.revenue_summary.total_revenue",
        "finance_db.accounting.monthly_report.revenue_amount"
      ]
    },
    {
      "id": "g4d5e6f7-a8b9-0123-defg-234567890123",
      "term": "매출원가",
      "definition": "매출을 실현하기 위해 직접적으로 투입된 비용의 총합...",
      "category": "financial",
      "relevance_score": 0.72,
      "matched_on": ["term"],
      "related_columns": [
        "finance_db.accounting.cost_summary.cogs_amount"
      ]
    }
  ],
  "total": 2
}
```

검색은 다음 필드에 대해 수행된다: 용어명(`term`), 정의(`definition`), 동의어(`synonyms`). PostgreSQL의 `tsvector`/`tsquery` 전문 검색을 사용한다.

---

## 4. 테이블/컬럼 태깅 API

태그는 테이블/컬럼에 분류 레이블을 부여하여 검색, 필터링, 정책 적용을 가능하게 한다. 예: `pii`, `financial`, `audit-required`, `deprecated`.

### 4.1 테이블 태그 추가

```
POST /api/v1/metadata/cases/{case_id}/datasources/{ds_name}/tables/{table_name}/tags
Content-Type: application/json
Authorization: Bearer {jwt_token}
```

**경로 파라미터**:

| 파라미터 | 타입 | 설명 |
|---------|------|------|
| `case_id` | `UUID` | 케이스 ID |
| `ds_name` | `string` | 데이터소스 이름 |
| `table_name` | `string` | 테이블 이름 (형식: `{schema}.{table}`, 예: `public.processes`) |

**요청 본문**:

```json
{
  "tags": ["pii", "financial", "audit-required"]
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `tags` | `string[]` | 필수 | 추가할 태그 목록. 각 태그는 영문 소문자, 숫자, 하이픈만 허용 (최대 50자) |

**성공 응답** (200 OK):

```json
{
  "entity_type": "table",
  "entity_fqn": "erp_db.public.processes",
  "tags": ["pii", "financial", "audit-required", "core"],
  "added": ["pii", "financial", "audit-required"],
  "already_existed": ["core"],
  "updated_at": "2026-02-20T10:00:00Z"
}
```

**동작 방식**: 기존 태그에 **추가(append)**한다. 이미 존재하는 태그는 무시한다.

**에러 응답**:

| HTTP 코드 | 에러 코드 | 설명 |
|-----------|----------|------|
| 400 | `INVALID_TAG_FORMAT` | 태그 형식 불일치 (영문 소문자, 숫자, 하이픈만) |
| 404 | `TABLE_NOT_FOUND` | 지정한 테이블이 메타데이터 그래프에 존재하지 않음 |

### 4.2 테이블 태그 조회

```
GET /api/v1/metadata/cases/{case_id}/datasources/{ds_name}/tables/{table_name}/tags
Authorization: Bearer {jwt_token}
```

**성공 응답** (200 OK):

```json
{
  "entity_type": "table",
  "entity_fqn": "erp_db.public.processes",
  "tags": ["pii", "financial", "audit-required", "core"],
  "updated_at": "2026-02-20T10:00:00Z"
}
```

### 4.3 테이블 태그 삭제

```
DELETE /api/v1/metadata/cases/{case_id}/datasources/{ds_name}/tables/{table_name}/tags/{tag}
Authorization: Bearer {jwt_token}
```

**성공 응답** (200 OK):

```json
{
  "entity_type": "table",
  "entity_fqn": "erp_db.public.processes",
  "removed_tag": "financial",
  "remaining_tags": ["pii", "audit-required", "core"],
  "updated_at": "2026-02-20T10:05:00Z"
}
```

**에러 응답**:

| HTTP 코드 | 에러 코드 | 설명 |
|-----------|----------|------|
| 404 | `TAG_NOT_FOUND` | 해당 엔티티에 지정한 태그가 존재하지 않음 |

### 4.4 컬럼 레벨 태깅

컬럼 태깅은 테이블 태깅과 동일한 패턴이며, URL에 `columns/{column_name}`이 추가된다.

**태그 추가**:

```
POST /api/v1/metadata/cases/{case_id}/datasources/{ds_name}/tables/{table_name}/columns/{column_name}/tags
Content-Type: application/json
Authorization: Bearer {jwt_token}
```

```json
{
  "tags": ["pii-name", "encrypted"]
}
```

**태그 조회**:

```
GET /api/v1/metadata/cases/{case_id}/datasources/{ds_name}/tables/{table_name}/columns/{column_name}/tags
```

**태그 삭제**:

```
DELETE /api/v1/metadata/cases/{case_id}/datasources/{ds_name}/tables/{table_name}/columns/{column_name}/tags/{tag}
```

요청/응답 형식은 테이블 태깅과 동일하며, `entity_type`이 `"column"`으로 반환된다.

```json
{
  "entity_type": "column",
  "entity_fqn": "erp_db.public.organizations.business_number",
  "tags": ["pii-name", "encrypted", "sensitive"],
  "added": ["pii-name", "encrypted"],
  "already_existed": ["sensitive"],
  "updated_at": "2026-02-20T10:10:00Z"
}
```

### 4.5 태그별 엔티티 검색

특정 태그가 부여된 모든 테이블/컬럼을 테넌트 범위에서 조회한다.

```
GET /api/v1/metadata/tags/{tag}/entities
Authorization: Bearer {jwt_token}
```

**쿼리 파라미터**:

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `case_id` | `UUID` | 선택 | 전체 | 특정 케이스로 필터 |
| `entity_type` | `string` | 선택 | 전체 | `table` 또는 `column` |
| `page` | `integer` | 선택 | `1` | 페이지 번호 |
| `size` | `integer` | 선택 | `20` | 페이지 크기 |

**성공 응답** (200 OK):

```json
{
  "tag": "pii",
  "entities": [
    {
      "type": "table",
      "fqn": "erp_db.public.organizations",
      "datasource": "erp_db",
      "case_id": "case-uuid-1234",
      "schema": "public",
      "table": "organizations",
      "column": null,
      "all_tags": ["pii", "core"]
    },
    {
      "type": "column",
      "fqn": "erp_db.public.stakeholders.email",
      "datasource": "erp_db",
      "case_id": "case-uuid-1234",
      "schema": "public",
      "table": "stakeholders",
      "column": "email",
      "all_tags": ["pii", "pii-email", "encrypted"]
    },
    {
      "type": "column",
      "fqn": "finance_db.accounting.vendors.tax_id",
      "datasource": "finance_db",
      "case_id": "case-uuid-1234",
      "schema": "accounting",
      "table": "vendors",
      "column": "tax_id",
      "all_tags": ["pii", "sensitive"]
    }
  ],
  "total": 3,
  "page": 1,
  "size": 20,
  "pages": 1
}
```

---

## 5. 메타데이터 검색 API

### 5.1 통합 검색

테넌트 범위 내 모든 데이터소스의 메타데이터를 통합 검색한다. 테이블명, 컬럼명, 설명(description), 태그, 용어 사전을 대상으로 한다.

```
GET /api/v1/metadata/search?q={query}&case_id={case_id}
Authorization: Bearer {jwt_token}
```

**쿼리 파라미터**:

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `q` | `string` | 필수 | - | 검색어 (2글자 이상) |
| `case_id` | `UUID` | 선택 | 전체 | 특정 케이스로 필터 |
| `ds_name` | `string` | 선택 | 전체 | 특정 데이터소스로 필터 |
| `entity_types` | `string` | 선택 | 전체 | 검색 대상 (`tables`, `columns`, `glossary` 쉼표 구분) |
| `tags` | `string` | 선택 | 전체 | 태그 필터 (쉼표 구분) |
| `limit` | `integer` | 선택 | `20` | 카테고리당 최대 결과 수 |

**성공 응답** (200 OK):

```json
{
  "query": "매출",
  "tables": [
    {
      "fqn": "erp_db.public.revenue_summary",
      "datasource": "erp_db",
      "case_id": "case-uuid-1234",
      "schema": "public",
      "name": "revenue_summary",
      "description": "조직별 매출 요약 정보. 월/분기/연간 매출 집계 테이블이다.",
      "row_count": 4500,
      "columns_count": 12,
      "tags": ["financial", "kpi"],
      "relevance_score": 0.92
    },
    {
      "fqn": "finance_db.accounting.monthly_report",
      "datasource": "finance_db",
      "case_id": "case-uuid-1234",
      "schema": "accounting",
      "name": "monthly_report",
      "description": "월별 재무 보고서. 매출, 비용, 이익 항목을 포함한다.",
      "row_count": 2400,
      "columns_count": 18,
      "tags": ["financial"],
      "relevance_score": 0.78
    }
  ],
  "columns": [
    {
      "fqn": "erp_db.public.revenue_summary.total_revenue",
      "datasource": "erp_db",
      "schema": "public",
      "table": "revenue_summary",
      "name": "total_revenue",
      "dtype": "DECIMAL(18,2)",
      "description": "총 매출액 (원)",
      "tags": ["kpi"],
      "relevance_score": 0.98
    },
    {
      "fqn": "finance_db.accounting.monthly_report.revenue_amount",
      "datasource": "finance_db",
      "schema": "accounting",
      "table": "monthly_report",
      "name": "revenue_amount",
      "dtype": "DECIMAL(15,2)",
      "description": "매출 금액 (원)",
      "tags": [],
      "relevance_score": 0.85
    }
  ],
  "glossary_terms": [
    {
      "id": "g1a2b3c4-d5e6-7890-abcd-ef1234567890",
      "term": "매출액",
      "definition": "기업의 주요 영업활동으로 인한 수익 총액...",
      "category": "financial",
      "relevance_score": 0.95
    }
  ],
  "total_results": {
    "tables": 2,
    "columns": 2,
    "glossary_terms": 1
  }
}
```

### 5.2 스키마 탐색

계층형 메타데이터 탐색을 위한 엔드포인트이다.

#### 5.2.1 스키마 목록

```
GET /api/v1/metadata/cases/{case_id}/datasources/{ds_name}/schemas
Authorization: Bearer {jwt_token}
```

**성공 응답** (200 OK):

```json
{
  "datasource": "erp_db",
  "case_id": "case-uuid-1234",
  "schemas": [
    {
      "name": "public",
      "tables_count": 25,
      "columns_count": 178,
      "description": null
    },
    {
      "name": "operations",
      "tables_count": 12,
      "columns_count": 89,
      "description": null
    },
    {
      "name": "audit",
      "tables_count": 3,
      "columns_count": 24,
      "description": null
    }
  ]
}
```

#### 5.2.2 특정 스키마의 테이블 목록

```
GET /api/v1/metadata/cases/{case_id}/datasources/{ds_name}/schemas/{schema_name}/tables
Authorization: Bearer {jwt_token}
```

**성공 응답** (200 OK):

```json
{
  "datasource": "erp_db",
  "schema": "public",
  "tables": [
    {
      "name": "processes",
      "description": "비즈니스 프로세스 정보",
      "table_type": "BASE TABLE",
      "row_count": 15420,
      "columns_count": 12,
      "fk_count": 2,
      "tags": ["core", "audit-required"]
    },
    {
      "name": "organizations",
      "description": "대상 조직 정보",
      "table_type": "BASE TABLE",
      "row_count": 8750,
      "columns_count": 8,
      "fk_count": 0,
      "tags": ["pii"]
    },
    {
      "name": "stakeholders",
      "description": "이해관계자 정보",
      "table_type": "BASE TABLE",
      "row_count": 87650,
      "columns_count": 8,
      "fk_count": 1,
      "tags": ["pii"]
    }
  ]
}
```

#### 5.2.3 특정 테이블의 컬럼 목록

```
GET /api/v1/metadata/cases/{case_id}/datasources/{ds_name}/schemas/{schema_name}/tables/{table_name}/columns
Authorization: Bearer {jwt_token}
```

**성공 응답** (200 OK):

```json
{
  "datasource": "erp_db",
  "schema": "public",
  "table": "processes",
  "description": "비즈니스 프로세스 정보",
  "columns": [
    {
      "name": "id",
      "dtype": "BIGINT",
      "nullable": false,
      "is_primary_key": true,
      "default_value": "nextval('processes_id_seq'::regclass)",
      "description": "프로세스 고유 ID",
      "tags": [],
      "foreign_key": null
    },
    {
      "name": "process_code",
      "dtype": "VARCHAR(50)",
      "nullable": false,
      "is_primary_key": false,
      "default_value": null,
      "description": "프로세스 코드 (예: PROC-2026-001)",
      "tags": [],
      "foreign_key": null
    },
    {
      "name": "org_id",
      "dtype": "BIGINT",
      "nullable": false,
      "is_primary_key": false,
      "default_value": null,
      "description": "대상 조직 FK",
      "tags": [],
      "foreign_key": {
        "target_schema": "public",
        "target_table": "organizations",
        "target_column": "id"
      }
    },
    {
      "name": "process_type",
      "dtype": "VARCHAR(20)",
      "nullable": false,
      "is_primary_key": false,
      "default_value": null,
      "description": "프로세스 유형 (procurement/sales/hr/finance)",
      "tags": ["enum-type"],
      "foreign_key": null
    }
  ],
  "foreign_keys": [
    {
      "constraint_name": "fk_processes_org",
      "source_column": "org_id",
      "target_schema": "public",
      "target_table": "organizations",
      "target_column": "id"
    },
    {
      "constraint_name": "fk_processes_dept",
      "source_column": "dept_id",
      "target_schema": "public",
      "target_table": "departments",
      "target_column": "id"
    }
  ],
  "tags": ["core", "audit-required"]
}
```

---

## 6. 메타데이터 통계 API

### 6.1 데이터소스별 통계

```
GET /api/v1/metadata/cases/{case_id}/datasources/{ds_name}/stats
Authorization: Bearer {jwt_token}
```

**성공 응답** (200 OK):

```json
{
  "datasource": "erp_db",
  "case_id": "case-uuid-1234",
  "engine": "postgresql",
  "stats": {
    "schemas": 3,
    "tables": 45,
    "columns": 312,
    "fk_relations": 28,
    "views": 5,
    "primary_keys": 45,
    "nullable_columns": 198,
    "described_tables": 38,
    "described_columns": 275,
    "description_coverage": {
      "tables_percent": 84.4,
      "columns_percent": 88.1
    }
  },
  "tags": {
    "total_tags": 15,
    "tagged_tables": 12,
    "tagged_columns": 8,
    "top_tags": [
      {"tag": "pii", "count": 7},
      {"tag": "financial", "count": 5},
      {"tag": "audit-required", "count": 4},
      {"tag": "core", "count": 3},
      {"tag": "deprecated", "count": 1}
    ]
  },
  "snapshots": {
    "total": 5,
    "latest_version": 5,
    "latest_created_at": "2026-02-20T09:00:00Z"
  },
  "last_extracted": "2026-02-19T10:00:12Z",
  "last_enriched": "2026-02-19T10:05:30Z"
}
```

### 6.2 테넌트 전체 통계

```
GET /api/v1/metadata/stats
Authorization: Bearer {jwt_token}
```

**쿼리 파라미터**:

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `case_id` | `UUID` | 선택 | 전체 | 특정 케이스로 필터 |

**성공 응답** (200 OK):

```json
{
  "tenant_id": "tenant-uuid",
  "overview": {
    "total_datasources": 8,
    "total_schemas": 14,
    "total_tables": 234,
    "total_columns": 1890,
    "total_fk_relations": 112,
    "total_snapshots": 23
  },
  "glossary": {
    "total_terms": 45,
    "categories": {
      "financial": 18,
      "operational": 15,
      "legal": 5,
      "technical": 4,
      "general": 3
    },
    "linked_columns": 89
  },
  "tags": {
    "total_unique_tags": 12,
    "tagged_tables": 45,
    "tagged_columns": 32,
    "top_tags": [
      {"tag": "pii", "count": 23},
      {"tag": "financial", "count": 18},
      {"tag": "audit-required", "count": 15}
    ]
  },
  "quality": {
    "description_coverage": {
      "tables_described": 198,
      "tables_total": 234,
      "tables_percent": 84.6,
      "columns_described": 1654,
      "columns_total": 1890,
      "columns_percent": 87.5
    },
    "datasources_with_metadata": 7,
    "datasources_without_metadata": 1
  },
  "by_datasource": [
    {
      "name": "erp_db",
      "case_id": "case-uuid-1234",
      "engine": "postgresql",
      "tables": 45,
      "columns": 312,
      "last_extracted": "2026-02-19T10:00:12Z"
    },
    {
      "name": "finance_db",
      "case_id": "case-uuid-1234",
      "engine": "mysql",
      "tables": 28,
      "columns": 215,
      "last_extracted": "2026-02-18T14:30:00Z"
    }
  ]
}
```

---

## 7. Pydantic 모델

### 7.1 패브릭 스냅샷 모델

```python
# app/schemas/metadata_catalog.py

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ─── 패브릭 스냅샷 ───

class FabricSnapshotCreate(BaseModel):
    """스냅샷 생성 요청"""
    description: Optional[str] = Field(
        None, max_length=500, description="스냅샷 설명"
    )


class FabricSnapshotSummary(BaseModel):
    """스냅샷 요약 통계"""
    schemas: int
    tables: int
    columns: int
    fk_relations: int
    tags_count: Optional[int] = None
    descriptions_count: Optional[int] = None


class FabricSnapshotResponse(BaseModel):
    """스냅샷 응답"""
    id: UUID
    datasource: str
    case_id: UUID
    version: int
    status: str = Field(
        ..., description="스냅샷 상태: creating, ready, failed"
    )
    description: Optional[str] = None
    created_by: UUID
    created_at: datetime
    completed_at: Optional[datetime] = None
    summary: Optional[FabricSnapshotSummary] = None


class FabricSnapshotListResponse(BaseModel):
    """스냅샷 목록 응답 (페이지네이션)"""
    items: list[FabricSnapshotResponse]
    total: int
    page: int
    size: int
    pages: int


class ColumnChange(BaseModel):
    """컬럼 속성 변경 상세"""
    field: str = Field(..., description="변경된 속성명 (dtype, nullable 등)")
    from_value: str = Field(..., alias="from")
    to_value: str = Field(..., alias="to")

    model_config = {"populate_by_name": True}


class FabricSnapshotDiffEntry(BaseModel):
    """Diff 내 개별 변경 항목"""
    fqn: str = Field(..., description="정규화된 엔티티 이름 (schema.table.column)")
    changes: Optional[dict[str, dict[str, str]]] = None
    dtype: Optional[str] = None
    nullable: Optional[bool] = None


class FabricSnapshotDiffResponse(BaseModel):
    """스냅샷 Diff 응답"""
    datasource: str
    from_version: int
    to_version: int
    from_snapshot_id: UUID
    to_snapshot_id: UUID
    diff: dict = Field(
        ...,
        description="변경 사항 (tables_added, tables_removed, columns_added, "
                    "columns_removed, columns_modified, fk_added, fk_removed, "
                    "tags_added, tags_removed)"
    )
    summary: dict = Field(
        ...,
        description="변경 요약 통계"
    )


class FabricSnapshotRestoreResponse(BaseModel):
    """스냅샷 복원 응답"""
    restore_id: UUID
    snapshot_id: UUID
    snapshot_version: int
    status: str = Field(
        ..., description="복원 상태: restoring, restored, failed"
    )
    initiated_by: UUID
    initiated_at: datetime
```

### 7.2 비즈니스 용어 사전 모델

```python
from enum import Enum


class GlossaryCategory(str, Enum):
    """용어 분류 카테고리"""
    FINANCIAL = "financial"
    OPERATIONAL = "operational"
    LEGAL = "legal"
    TECHNICAL = "technical"
    GENERAL = "general"


class GlossaryTermCreate(BaseModel):
    """용어 생성 요청"""
    term: str = Field(
        ..., min_length=1, max_length=100, description="용어명 (테넌트 내 고유)"
    )
    definition: str = Field(
        ..., min_length=1, max_length=2000, description="용어 정의"
    )
    synonyms: list[str] = Field(
        default_factory=list, description="동의어/영문 표현 목록"
    )
    category: Optional[GlossaryCategory] = Field(
        None, description="분류 카테고리"
    )
    owner: Optional[str] = Field(
        None, max_length=100, description="용어 관리 책임자/팀"
    )
    related_columns: list[str] = Field(
        default_factory=list,
        description="관련 컬럼 FQN 목록 (형식: ds_name.schema.table.column)"
    )
    related_terms: list[UUID] = Field(
        default_factory=list, description="관련 용어 ID 목록"
    )
    tags: list[str] = Field(
        default_factory=list, description="태그 목록"
    )


class GlossaryTermUpdate(BaseModel):
    """용어 수정 요청 — 전체 교체 (full replace)"""
    term: Optional[str] = Field(
        None, min_length=1, max_length=100
    )
    definition: Optional[str] = Field(
        None, min_length=1, max_length=2000
    )
    synonyms: Optional[list[str]] = None
    category: Optional[GlossaryCategory] = None
    owner: Optional[str] = Field(None, max_length=100)
    related_columns: Optional[list[str]] = None
    related_terms: Optional[list[UUID]] = None
    tags: Optional[list[str]] = None


class RelatedColumnDetail(BaseModel):
    """연결된 컬럼 상세 (상세 조회 시)"""
    fqn: str
    datasource: str
    schema_name: str = Field(..., alias="schema")
    table: str
    column: str
    dtype: Optional[str] = None
    exists: bool = Field(
        ..., description="메타데이터 그래프에 실제 존재하는지 여부"
    )

    model_config = {"populate_by_name": True}


class RelatedTermSummary(BaseModel):
    """관련 용어 요약"""
    id: UUID
    term: str


class GlossaryTermResponse(BaseModel):
    """용어 상세 응답"""
    id: UUID
    tenant_id: UUID
    term: str
    definition: str
    synonyms: list[str]
    category: Optional[GlossaryCategory] = None
    owner: Optional[str] = None
    related_columns: list[RelatedColumnDetail]
    related_terms: list[RelatedTermSummary]
    tags: list[str]
    created_by: UUID
    created_at: datetime
    updated_at: datetime


class GlossaryTermListItem(BaseModel):
    """용어 목록 항목 (축약)"""
    id: UUID
    term: str
    definition: str
    synonyms: list[str]
    category: Optional[GlossaryCategory] = None
    owner: Optional[str] = None
    related_columns_count: int
    tags: list[str]
    updated_at: datetime


class GlossaryTermListResponse(BaseModel):
    """용어 목록 응답 (페이지네이션)"""
    items: list[GlossaryTermListItem]
    total: int
    page: int
    size: int
    pages: int


class GlossarySearchResult(BaseModel):
    """용어 검색 결과 항목"""
    id: UUID
    term: str
    definition: str
    category: Optional[GlossaryCategory] = None
    relevance_score: float = Field(
        ..., ge=0.0, le=1.0, description="검색 관련도 점수"
    )
    matched_on: list[str] = Field(
        ..., description="매칭된 필드 목록 (term, definition, synonyms)"
    )
    related_columns: list[str]


class GlossarySearchResponse(BaseModel):
    """용어 검색 응답"""
    query: str
    results: list[GlossarySearchResult]
    total: int
```

### 7.3 태깅 모델

```python
import re
from pydantic import field_validator


TAG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9\-]{0,49}$")


class TagRequest(BaseModel):
    """태그 추가 요청"""
    tags: list[str] = Field(
        ..., min_length=1, description="추가할 태그 목록"
    )

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        for tag in v:
            if not TAG_PATTERN.match(tag):
                raise ValueError(
                    f"태그 '{tag}' 형식 불일치: 영문 소문자, 숫자, "
                    f"하이픈만 허용 (1-50자)"
                )
        return v


class TagResponse(BaseModel):
    """태그 조회/추가 응답"""
    entity_type: str = Field(
        ..., description="엔티티 유형: table 또는 column"
    )
    entity_fqn: str = Field(
        ..., description="엔티티 FQN (datasource.schema.table[.column])"
    )
    tags: list[str]
    added: Optional[list[str]] = Field(
        None, description="새로 추가된 태그 (추가 요청 시)"
    )
    already_existed: Optional[list[str]] = Field(
        None, description="이미 존재하던 태그 (추가 요청 시)"
    )
    updated_at: datetime


class TagDeleteResponse(BaseModel):
    """태그 삭제 응답"""
    entity_type: str
    entity_fqn: str
    removed_tag: str
    remaining_tags: list[str]
    updated_at: datetime


class TaggedEntity(BaseModel):
    """태그 검색 결과 항목"""
    type: str = Field(..., description="table 또는 column")
    fqn: str
    datasource: str
    case_id: UUID
    schema_name: str = Field(..., alias="schema")
    table: str
    column: Optional[str] = None
    all_tags: list[str]

    model_config = {"populate_by_name": True}


class TagEntitiesResponse(BaseModel):
    """태그별 엔티티 목록"""
    tag: str
    entities: list[TaggedEntity]
    total: int
    page: int
    size: int
    pages: int
```

### 7.4 검색/통계 모델

```python
class MetadataSearchTableResult(BaseModel):
    """검색 결과 - 테이블"""
    fqn: str
    datasource: str
    case_id: UUID
    schema_name: str = Field(..., alias="schema")
    name: str
    description: Optional[str] = None
    row_count: Optional[int] = None
    columns_count: int
    tags: list[str]
    relevance_score: float

    model_config = {"populate_by_name": True}


class MetadataSearchColumnResult(BaseModel):
    """검색 결과 - 컬럼"""
    fqn: str
    datasource: str
    schema_name: str = Field(..., alias="schema")
    table: str
    name: str
    dtype: str
    description: Optional[str] = None
    tags: list[str]
    relevance_score: float

    model_config = {"populate_by_name": True}


class MetadataSearchResponse(BaseModel):
    """통합 검색 응답"""
    query: str
    tables: list[MetadataSearchTableResult]
    columns: list[MetadataSearchColumnResult]
    glossary_terms: list[GlossarySearchResult]
    total_results: dict[str, int]


class DataSourceStats(BaseModel):
    """데이터소스 통계"""
    datasource: str
    case_id: UUID
    engine: str
    stats: dict = Field(..., description="스키마/테이블/컬럼/FK 통계")
    tags: dict = Field(..., description="태그 통계")
    snapshots: dict = Field(..., description="스냅샷 통계")
    last_extracted: Optional[datetime] = None
    last_enriched: Optional[datetime] = None


class TenantMetadataStats(BaseModel):
    """테넌트 전체 메타데이터 통계"""
    tenant_id: UUID
    overview: dict
    glossary: dict
    tags: dict
    quality: dict
    by_datasource: list[dict]
```

---

## 8. 권한 매트릭스

Core의 RBAC 모델(`07_security/auth-model.md`)을 확장하여 메타데이터 카탈로그 전용 권한을 정의한다.

### 8.1 신규 권한

| 권한 | 설명 |
|------|------|
| `metadata:read` | 메타데이터 카탈로그 조회 (검색, 목록, 상세, 통계) |
| `metadata:write` | 메타데이터 카탈로그 쓰기 (용어 생성/수정, 태그 추가/삭제, 스냅샷 생성) |
| `metadata:admin` | 메타데이터 관리 (스냅샷 복원/삭제) |

### 8.2 역할별 권한 매트릭스

| 엔드포인트 | viewer | staff | attorney | manager | admin |
|-----------|:------:|:-----:|:--------:|:-------:|:-----:|
| **패브릭 스냅샷** |
| 스냅샷 생성 | X | X | X | O | O |
| 스냅샷 목록/상세 조회 | O | O | O | O | O |
| 스냅샷 Diff | O | O | O | O | O |
| 스냅샷 복원 | X | X | X | X | O |
| 스냅샷 삭제 | X | X | X | X | O |
| **비즈니스 용어 사전** |
| 용어 생성 | X | X | O | O | O |
| 용어 목록/상세 조회 | O | O | O | O | O |
| 용어 검색 | O | O | O | O | O |
| 용어 수정 | X | X | O | O | O |
| 용어 삭제 | X | X | X | O | O |
| **태깅** |
| 태그 추가 | X | X | O | O | O |
| 태그 조회 | O | O | O | O | O |
| 태그 삭제 | X | X | O | O | O |
| 태그별 검색 | O | O | O | O | O |
| **검색/통계** |
| 통합 검색 | O | O | O | O | O |
| 스키마 탐색 | O | O | O | O | O |
| 통계 조회 | O | O | O | O | O |

### 8.3 구현 예시

```python
# app/api/metadata_catalog.py

from axiom_core.security import require_auth, require_permission
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/api/v1/metadata", tags=["metadata-catalog"])


@router.post("/cases/{case_id}/datasources/{ds_name}/snapshots")
@require_permission("metadata:write")
async def create_snapshot(
    case_id: UUID,
    ds_name: str,
    body: FabricSnapshotCreate,
    current_user: dict = Depends(require_auth),
):
    """패브릭 스냅샷 생성 — manager 이상"""
    tenant_id = current_user["tenant_id"]
    ...


@router.post(
    "/cases/{case_id}/datasources/{ds_name}/snapshots/{snapshot_id}/restore"
)
@require_permission("metadata:admin")
async def restore_snapshot(
    case_id: UUID,
    ds_name: str,
    snapshot_id: UUID,
    current_user: dict = Depends(require_auth),
):
    """패브릭 스냅샷 복원 — admin 전용"""
    tenant_id = current_user["tenant_id"]
    ...


@router.get("/search")
@require_permission("metadata:read")
async def search_metadata(
    q: str,
    case_id: Optional[UUID] = None,
    current_user: dict = Depends(require_auth),
):
    """통합 메타데이터 검색 — 모든 인증된 사용자"""
    tenant_id = current_user["tenant_id"]
    ...
```

---

## 9. 에러 코드

모든 에러 응답은 Weaver의 공통 에러 형식을 따른다 (`datasource-api.md` 섹션 4 참조).

```json
{
  "error": {
    "code": "SNAPSHOT_NOT_FOUND",
    "message": "Snapshot with id 'a1b2c3d4...' not found for datasource 'erp_db'",
    "details": {
      "datasource": "erp_db",
      "snapshot_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    }
  }
}
```

### 9.1 스냅샷 관련 에러

| 코드 | HTTP 상태 | 설명 |
|------|----------|------|
| `DATASOURCE_NOT_FOUND` | 404 | 지정한 데이터소스가 존재하지 않음 |
| `SNAPSHOT_NOT_FOUND` | 404 | 지정한 스냅샷이 존재하지 않음 |
| `SNAPSHOT_VERSION_NOT_FOUND` | 404 | 지정한 버전의 스냅샷이 존재하지 않음 |
| `SNAPSHOT_IN_PROGRESS` | 409 | 이미 스냅샷 생성이 진행 중 |
| `RESTORE_IN_PROGRESS` | 409 | 이미 복원이 진행 중 |
| `CANNOT_DELETE_LATEST` | 409 | 최신 스냅샷은 삭제 불가 |
| `NO_METADATA` | 422 | 해당 데이터소스에 추출된 메타데이터가 없음 |
| `INVALID_VERSION_RANGE` | 400 | 유효하지 않은 버전 범위 (from >= to) |
| `SNAPSHOT_FAILED` | 500 | 스냅샷 생성 중 내부 오류 |

### 9.2 용어 사전 관련 에러

| 코드 | HTTP 상태 | 설명 |
|------|----------|------|
| `TERM_NOT_FOUND` | 404 | 지정한 용어가 존재하지 않음 |
| `DUPLICATE_TERM` | 409 | 테넌트 내에 동일한 용어명이 이미 존재 |
| `INVALID_CATEGORY` | 400 | 허용되지 않는 카테고리 값 |
| `INVALID_COLUMN_FQN` | 422 | 컬럼 FQN 형식 불일치 (예상: `ds.schema.table.column`) |
| `TERM_SEARCH_TOO_SHORT` | 400 | 검색어가 2글자 미만 |

### 9.3 태깅 관련 에러

| 코드 | HTTP 상태 | 설명 |
|------|----------|------|
| `TABLE_NOT_FOUND` | 404 | 메타데이터 그래프에 해당 테이블이 없음 |
| `COLUMN_NOT_FOUND` | 404 | 메타데이터 그래프에 해당 컬럼이 없음 |
| `TAG_NOT_FOUND` | 404 | 해당 엔티티에 지정한 태그가 없음 |
| `INVALID_TAG_FORMAT` | 400 | 태그 형식 불일치 (영문 소문자/숫자/하이픈, 1-50자) |

### 9.4 검색/통계 관련 에러

| 코드 | HTTP 상태 | 설명 |
|------|----------|------|
| `SEARCH_QUERY_TOO_SHORT` | 400 | 검색어가 2글자 미만 |
| `INVALID_ENTITY_TYPE` | 400 | 잘못된 entity_type 값 |

### 9.5 공통 에러

| 코드 | HTTP 상태 | 설명 |
|------|----------|------|
| `UNAUTHORIZED` | 401 | 유효하지 않은 JWT 토큰 |
| `FORBIDDEN` | 403 | 권한 부족 |
| `ADMIN_REQUIRED` | 403 | admin 역할 필요 |
| `INTERNAL_ERROR` | 500 | 서버 내부 오류 |

---

## 10. 처리 흐름

### 10.1 스냅샷 생성 흐름

```
POST /snapshots
        │
        ▼
┌─ 1. 요청 검증 ──────────────────────┐
│  JWT 검증 → tenant_id 추출           │
│  case_id, ds_name 유효성 확인         │
│  진행 중인 스냅샷 존재 여부 확인      │
└────────────┬─────────────────────────┘
             │
             ▼
┌─ 2. 스냅샷 레코드 생성 ─────────────┐
│  status = "creating"                  │
│  version = max(version) + 1           │
│  → 202 Accepted 즉시 반환             │
└────────────┬─────────────────────────┘
             │ (비동기 백그라운드 태스크)
             ▼
┌─ 3. Neo4j 그래프 순회 ──────────────┐
│  MATCH (ds:DataSource {name: $name}) │
│  -[:HAS_SCHEMA]->(s)                 │
│  -[:HAS_TABLE]->(t)                  │
│  -[:HAS_COLUMN]->(c)                 │
│  전체 그래프 데이터 직렬화            │
└────────────┬─────────────────────────┘
             │
             ▼
┌─ 4. 스냅샷 데이터 저장 ─────────────┐
│  graph_data를 JSON으로 PostgreSQL에   │
│  저장 (또는 Neo4j 별도 서브그래프)    │
│  summary 통계 계산                    │
│  status = "ready"                     │
└────────────┬─────────────────────────┘
             │
             ▼
┌─ 5. 이벤트 발행 ────────────────────┐
│  metadata.snapshot.created            │
│  { tenant_id, case_id, ds_name,      │
│    snapshot_id, version }             │
└──────────────────────────────────────┘
```

### 10.2 통합 검색 흐름

```
GET /search?q=매출
        │
        ▼
┌─ 1. 요청 검증 ──────────────────────┐
│  JWT 검증 → tenant_id 추출           │
│  검색어 최소 길이 확인                │
└────────────┬─────────────────────────┘
             │
             ▼
┌─ 2. 병렬 검색 실행 ─────────────────┐
│                                       │
│  ┌─ Neo4j ─────────────────────────┐ │
│  │ 테이블 검색: name, description  │ │
│  │ MATCH (t:Table) WHERE           │ │
│  │   t.name CONTAINS $q OR         │ │
│  │   t.description CONTAINS $q     │ │
│  └─────────────────────────────────┘ │
│                                       │
│  ┌─ Neo4j ─────────────────────────┐ │
│  │ 컬럼 검색: name, description    │ │
│  │ MATCH (c:Column) WHERE ...      │ │
│  └─────────────────────────────────┘ │
│                                       │
│  ┌─ PostgreSQL ────────────────────┐ │
│  │ 용어 검색: tsvector 전문 검색   │ │
│  │ WHERE tsv @@ to_tsquery($q)     │ │
│  └─────────────────────────────────┘ │
│                                       │
└────────────┬─────────────────────────┘
             │
             ▼
┌─ 3. 결과 통합 + 랭킹 ──────────────┐
│  tenant_id 기반 필터링 확인           │
│  relevance_score 기준 정렬            │
│  카테고리별 limit 적용                │
└────────────┬─────────────────────────┘
             │
             ▼
┌─ 4. 응답 반환 ──────────────────────┐
│  { tables: [...], columns: [...],    │
│    glossary_terms: [...] }           │
└──────────────────────────────────────┘
```

---

## 11. Neo4j 스키마 확장

카탈로그 기능을 지원하기 위해 기존 Neo4j 그래프 스키마(`06_data/neo4j-schema.md`)에 다음을 추가한다.

### 11.1 태그 속성

Table 노드와 Column 노드에 `tags` 속성을 추가한다.

```cypher
-- Table 노드에 tags 속성 추가
(:Table {
    name: "processes",
    description: "비즈니스 프로세스 정보",
    row_count: 15420,
    table_type: "BASE TABLE",
    tags: ["core", "audit-required"]      -- 신규 추가
})

-- Column 노드에 tags 속성 추가
(:Column {
    name: "business_number",
    dtype: "VARCHAR(13)",
    nullable: true,
    description: "사업자등록번호",
    is_primary_key: false,
    tags: ["pii", "sensitive"]            -- 신규 추가
})
```

### 11.2 인덱스 추가

```cypher
-- 태그 검색을 위한 인덱스 (리스트 속성)
CREATE INDEX table_tags_idx IF NOT EXISTS
    FOR (t:Table) ON (t.tags);

CREATE INDEX column_tags_idx IF NOT EXISTS
    FOR (c:Column) ON (c.tags);
```

### 11.3 테넌트/케이스 속성

멀티테넌시를 위해 DataSource 노드에 `tenant_id`와 `case_id` 속성을 추가한다.

```cypher
(:DataSource {
    name: "erp_db",
    engine: "postgresql",
    tenant_id: "tenant-uuid",            -- 신규 추가
    case_id: "case-uuid-1234",           -- 신규 추가
    host: "erp-db.internal",
    port: 5432,
    database: "enterprise_ops",
    user: "reader",
    last_extracted: datetime()
})
```

```cypher
-- 테넌트+케이스 복합 인덱스
CREATE INDEX ds_tenant_case_idx IF NOT EXISTS
    FOR (ds:DataSource) ON (ds.tenant_id, ds.case_id);
```

---

## 12. 관련 문서

| 문서 | 설명 |
|------|------|
| `02_api/metadata-api.md` | 메타데이터 추출 API (SSE 스트리밍) — 기존 API |
| `02_api/datasource-api.md` | 데이터소스 CRUD API |
| `02_api/query-api.md` | SQL 쿼리 실행 API |
| `06_data/neo4j-schema.md` | Neo4j 메타데이터 그래프 스키마 |
| `03_backend/neo4j-metadata.md` | Neo4j 메타데이터 CRUD 구현 |
| `05_llm/metadata-enrichment.md` | LLM 기반 메타데이터 보강 |
| `01_architecture/data-fabric.md` | 데이터 패브릭 설계 |
| `07_security/connection-security.md` | DB 연결 보안 |
| Core `07_security/auth-model.md` | JWT 인증 및 RBAC 모델 |
| Core `07_security/data-isolation.md` | 멀티테넌트 데이터 격리 |
| Core `99_decisions/ADR-003-contextvar-multitenancy.md` | ContextVar 멀티테넌트 결정 |
