# 쿼리 실행 API

> 구현 상태 태그: `Implemented`
> 기준일: 2026-02-21

<!-- affects: frontend, backend, llm -->
<!-- requires-update: 03_backend/mindsdb-client.md -->

## 이 문서가 답하는 질문

- SQL 쿼리를 어떻게 실행하는가?
- MindsDB를 통한 크로스 DB 쿼리는 어떻게 동작하는가?
- 물리화 테이블은 무엇이며 어떻게 생성하는가?
- ML 모델, 작업, 지식 베이스 목록은 어떻게 조회하는가?
- 타임아웃과 에러 처리는 어떻게 동작하는가?

---

## 1. 엔드포인트 목록

| 메서드 | 경로 | 설명 | 상태 | 근거(구현/티켓) |
|--------|------|------|------|------------------|
| `POST` | `/api/query` | MindsDB SQL 쿼리 실행 | Implemented | `docs/implementation-plans/weaver/82_sprint3-ticket-board.md` |
| `GET` | `/api/query/status` | MindsDB 서버 상태 확인 | Implemented | `docs/implementation-plans/weaver/82_sprint3-ticket-board.md` |
| `POST` | `/api/query/materialized-table` | 쿼리 결과를 물리화 테이블로 생성 | Implemented | `docs/implementation-plans/weaver/82_sprint3-ticket-board.md` |
| `GET` | `/api/query/models` | MindsDB ML 모델 목록 | Implemented | `docs/implementation-plans/weaver/82_sprint3-ticket-board.md` |
| `GET` | `/api/query/jobs` | MindsDB 스케줄 작업 목록 | Implemented | `docs/implementation-plans/weaver/82_sprint3-ticket-board.md` |
| `GET` | `/api/query/knowledge-bases` | MindsDB 지식 베이스 목록 | Implemented | `docs/implementation-plans/weaver/82_sprint3-ticket-board.md` |

---

## 2. 엔드포인트 상세

### 2.1 POST /api/query

MindsDB를 통해 SQL 쿼리를 실행한다. 단일 DB 쿼리뿐 아니라, **크로스 DB 조인 쿼리**도 지원한다.

**요청**:

```json
{
  "sql": "SELECT p.process_code, p.org_name, f.total_revenue FROM erp_db.public.processes p JOIN finance_db.accounting.revenue_summary f ON p.org_id = f.org_id WHERE p.process_status = 'active' LIMIT 100",
  "database": null
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `sql` | `string` | 필수 | 실행할 SQL 쿼리 |
| `database` | `string` | 선택 | 기본 데이터베이스 (nullable). 지정 시 테이블 이름에 DB 접두사 생략 가능 |

**성공 응답** (200 OK):

```json
{
  "success": true,
  "columns": ["process_code", "org_name", "total_revenue"],
  "column_types": ["varchar", "varchar", "decimal"],
  "data": [
    ["PROC-2026-001", "주식회사 가나다", 1500000000],
    ["PROC-2026-002", "주식회사 라마바", 800000000]
  ],
  "row_count": 2,
  "execution_time_ms": 234
}
```

| 필드 | 타입 | nullable | 설명 |
|------|------|----------|------|
| `success` | `boolean` | No | 실행 성공 여부 |
| `columns` | `string[]` | No | 컬럼 이름 배열 |
| `column_types` | `string[]` | Yes | 컬럼 타입 배열 |
| `data` | `any[][]` | No | 결과 데이터 (2차원 배열) |
| `row_count` | `integer` | No | 반환된 행 수 |
| `execution_time_ms` | `integer` | No | 실행 시간 (밀리초) |

**에러 응답**:

| HTTP 코드 | 에러 코드 | 설명 |
|-----------|----------|------|
| 400 | `INVALID_SQL` | SQL 문법 오류 |
| 400 | `EMPTY_QUERY` | 빈 쿼리 |
| 404 | `DATABASE_NOT_FOUND` | 지정한 데이터베이스가 MindsDB에 없음 |
| 500 | `EXECUTION_ERROR` | 쿼리 실행 중 에러 |
| 503 | `MINDSDB_UNAVAILABLE` | MindsDB 서버 접근 불가 |

### 쿼리 실행 예시

#### 단일 DB 쿼리

```json
{
  "sql": "SELECT * FROM erp_db.public.processes WHERE process_type = 'procurement' LIMIT 10"
}
```

#### 크로스 DB 조인

```json
{
  "sql": "SELECT p.process_code, s.name as stakeholder_name, s.engagement_score FROM erp_db.public.processes p JOIN crm_db.contacts.stakeholder_list s ON p.process_id = s.process_id WHERE p.started_at > '2026-01-01'"
}
```

#### MindsDB ML 모델 예측

```json
{
  "sql": "SELECT process_code, outcome_prediction, confidence FROM process_predictor WHERE process_type = 'procurement' AND total_value > 1000000000"
}
```

---

### 2.2 GET /api/query/status

MindsDB 서버의 현재 상태를 확인한다.

- `models_count`는 현재 테넌트 기준 모델 수를 집계한다.
- `uptime_seconds`와 `response_time_ms`는 Weaver 런타임 기준 계산값이다.

**응답 예시** (정상):

```json
{
  "status": "healthy",
  "mindsdb_version": "24.1.0",
  "databases_count": 5,
  "models_count": 2,
  "uptime_seconds": 86400,
  "response_time_ms": 15
}
```

**응답 예시** (비정상):

```json
{
  "status": "unhealthy",
  "error": "Connection refused to MindsDB at localhost:47334",
  "checked_at": "2026-02-19T10:00:00Z"
}
```

---

### 2.3 POST /api/query/materialized-table

쿼리 결과를 MindsDB 내에 물리화 테이블로 저장한다. 자주 사용하는 복잡한 크로스 DB 조인 결과를 캐싱하는 용도이다.

**요청**:

```json
{
  "table_name": "active_processes_with_revenue",
  "sql": "SELECT p.process_code, p.org_name, f.total_revenue, f.operating_cost, f.net_profit FROM erp_db.public.processes p JOIN finance_db.accounting.revenue_summary f ON p.org_id = f.org_id WHERE p.process_status = 'active'",
  "database": "mindsdb",
  "replace_if_exists": true
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `table_name` | `string` | 필수 | 생성할 테이블 이름 |
| `sql` | `string` | 필수 | 데이터 소스 SQL |
| `database` | `string` | 선택 | 대상 데이터베이스 (기본: `mindsdb`) |
| `replace_if_exists` | `boolean` | 선택 | 기존 테이블 존재 시 교체 여부 (기본: `false`) |

**성공 응답** (201 Created):

```json
{
  "table_name": "active_processes_with_revenue",
  "database": "mindsdb",
  "row_count": 1542,
  "columns": ["process_code", "org_name", "total_revenue", "operating_cost", "net_profit"],
  "created_at": "2026-02-19T10:10:00Z"
}
```

---

### 2.4 GET /api/query/models

MindsDB에 등록된 ML 모델 목록을 반환한다.

**응답 예시**:

```json
{
  "models": [
    {
      "name": "process_predictor",
      "engine": "openai",
      "status": "complete",
      "created_at": "2026-02-01T00:00:00Z",
      "predict_column": "outcome"
    },
    {
      "name": "revenue_classifier",
      "engine": "lightwood",
      "status": "complete",
      "created_at": "2026-02-10T00:00:00Z",
      "predict_column": "category"
    }
  ]
}
```

---

### 2.5 GET /api/query/jobs

MindsDB 스케줄 작업 목록을 반환한다.

- 현재 구현에서는 `POST /api/query/materialized-table` 실행 시 job 이력이 생성되며, 테넌트별로 조회된다.

**응답 예시**:

```json
{
  "jobs": [
    {
      "name": "daily_revenue_sync",
      "query": "INSERT INTO mindsdb.daily_snapshot SELECT * FROM finance_db.accounting.revenue_summary",
      "schedule": "every day",
      "status": "active",
      "last_run": "2026-02-19T00:00:00Z",
      "next_run": "2026-02-20T00:00:00Z"
    }
  ]
}
```

---

### 2.6 GET /api/query/knowledge-bases

MindsDB 지식 베이스 목록을 반환한다.

**응답 예시**:

```json
{
  "knowledge_bases": [
    {
      "name": "business_process_kb",
      "model": "openai_embedding",
      "storage": "chromadb",
      "documents_count": 150,
      "created_at": "2026-02-05T00:00:00Z"
    }
  ]
}
```

---

## 3. 타임아웃 정책

| 항목 | 값 | 설명 |
|------|-----|------|
| MindsDB API 타임아웃 | `MINDSDB_TIMEOUT` 환경변수 (기본 15초) | httpx 클라이언트 타임아웃 |
| 쿼리 SQL 길이 제한 | 20,000자 | 요청 모델에서 강제 |

**금지사항**: 클라이언트에서 타임아웃 값을 지정할 수 없다. 서버 설정만 사용한다.

---

## 4. 보안 규칙

### 금지사항

- DDL 쿼리 (CREATE TABLE, ALTER TABLE, DROP TABLE 등)는 **`/api/query`를 통해 실행할 수 없다**
- MindsDB 관리 명령 (CREATE DATABASE, DROP DATABASE)은 **데이터소스 API를 통해서만** 실행한다
- 쿼리 결과에서 비밀번호, 토큰 등 민감 컬럼은 마스킹한다

### 필수사항

- 모든 쿼리는 감사 로그에 기록한다 (사용자, 쿼리, 시각, 실행 시간)
- write 엔드포인트(`POST /api/query`, `POST /api/query/materialized-table`)는 Idempotency-Key 및 분당 Rate Limit을 적용한다
- 모든 응답은 `X-Request-Id` 헤더를 반환한다 (미지정 시 서버 생성)

---

## 5. 관련 문서

| 문서 | 설명 |
|------|------|
| `02_api/datasource-api.md` | 데이터소스 CRUD API |
| `02_api/metadata-api.md` | 메타데이터 추출 API |
| `03_backend/mindsdb-client.md` | MindsDB 클라이언트 구현 |
| `01_architecture/data-fabric.md` | 데이터 패브릭 설계 |
