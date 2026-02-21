# OLAP 피벗 분석 API

> **최종 수정일**: 2026-02-21
> **상태**: Active
> **구현 상태 태그**: `Implemented`
> **Phase**: 3.6
> **근거**: 01_architecture/olap-engine.md, ADR-002, ADR-003

---

## 이 문서가 답하는 질문

- OLAP 큐브를 관리하는 API는?
- 피벗 쿼리를 실행하는 방법은?
- 자연어 질의를 피벗으로 변환하는 API는?
- ETL 동기화를 트리거하는 방법은?
- 큐브 스키마를 업로드/관리하는 방법은?

---

## 기본 정보

| 항목 | 값 |
|------|-----|
| **Base URL** | `/api/v3` |
| **인증** | Bearer JWT (Authorization 헤더) |
| **Content-Type** | `application/json` (피벗), `multipart/form-data` (스키마 업로드) |

---

## 엔드포인트 목록

| Method | Path | 설명 | 상태 | 근거(구현/티켓) |
|--------|------|------|------|------------------|
| POST | `/cubes/schema/upload` | 큐브 스키마 XML 업로드 | Implemented | `docs/implementation-plans/vision/92_sprint5-ticket-board.md` |
| GET | `/cubes` | 사용 가능한 큐브 목록 | Implemented | `docs/implementation-plans/vision/92_sprint5-ticket-board.md` |
| GET | `/cubes/{cube_name}` | 큐브 메타데이터 상세 | Implemented | `docs/implementation-plans/vision/92_sprint5-ticket-board.md` |
| POST | `/pivot/query` | 피벗 쿼리 실행 | Implemented | `docs/implementation-plans/vision/92_sprint5-ticket-board.md` |
| POST | `/pivot/nl-query` | 자연어 → 피벗 쿼리 | Implemented | `docs/implementation-plans/vision/92_sprint5-ticket-board.md` |
| GET | `/pivot/drillthrough` | 드릴스루 (원본 레코드) | Implemented | `docs/implementation-plans/vision/92_sprint5-ticket-board.md` |
| POST | `/etl/analyze` | ETL 대상 분석 | Implemented | `docs/implementation-plans/vision/92_sprint5-ticket-board.md` |
| POST | `/etl/sync` | ETL 동기화 실행 | Implemented | `docs/implementation-plans/vision/92_sprint5-ticket-board.md` |
| GET | `/etl/status` | ETL 동기화 상태 | Implemented | `docs/implementation-plans/vision/92_sprint5-ticket-board.md` |
| POST | `/etl/airflow/trigger-dag` | Airflow DAG 트리거 | Implemented | `docs/implementation-plans/vision/92_sprint5-ticket-board.md` |

---

## 1. 큐브 스키마 업로드

### POST `/api/v3/cubes/schema/upload`

Mondrian XML 형식의 큐브 정의 파일을 업로드한다.

#### Request (multipart/form-data)

```
Content-Type: multipart/form-data

file: business_analysis_cube.xml
```

#### Response (201 Created)

```json
{
  "cube_name": "BusinessAnalysisCube",
  "fact_table": "mv_business_fact",
  "dimensions": ["CaseType", "Organization", "Time", "Stakeholder"],
  "measures": ["CaseCount", "TotalAmount", "AvgPerformanceRate"],
  "dimension_count": 4,
  "measure_count": 6,
  "uploaded_at": "2026-02-19T10:00:00Z",
  "validation": {
    "is_valid": true,
    "warnings": ["Dimension 'Stakeholder' has no AmountBand level data yet"]
  }
}
```

---

## 2. 큐브 목록 조회

### GET `/api/v3/cubes`

#### Response (200 OK)

```json
{
  "cubes": [
    {
      "name": "BusinessAnalysisCube",
      "fact_table": "mv_business_fact",
      "dimension_count": 4,
      "measure_count": 6,
      "last_refreshed": "2026-02-19T03:00:00Z",
      "row_count": 15423
    },
    {
      "name": "CashflowCube",
      "fact_table": "mv_cashflow_fact",
      "dimension_count": 3,
      "measure_count": 3,
      "last_refreshed": "2026-02-19T03:05:00Z",
      "row_count": 8721
    }
  ]
}
```

---

## 3. 큐브 메타데이터 상세

### GET `/api/v3/cubes/{cube_name}`

#### Response (200 OK)

```json
{
  "name": "BusinessAnalysisCube",
  "fact_table": "mv_business_fact",
  "dimensions": [
    {
      "name": "CaseType",
      "foreign_key": "case_type_id",
      "table": "dim_case_type",
      "levels": [
        {"name": "CaseCategory", "column": "category", "type": "String", "cardinality": 3},
        {"name": "CaseType", "column": "type_name", "type": "String", "cardinality": 8},
        {"name": "CaseStatus", "column": "status", "type": "String", "cardinality": 10}
      ]
    },
    {
      "name": "Time",
      "foreign_key": "time_id",
      "table": "dim_time",
      "levels": [
        {"name": "Year", "column": "filing_year", "type": "Numeric", "cardinality": 10},
        {"name": "Quarter", "column": "quarter", "type": "String", "cardinality": 4},
        {"name": "Month", "column": "month", "type": "Numeric", "cardinality": 12}
      ]
    }
  ],
  "measures": [
    {"name": "CaseCount", "column": "case_id", "aggregator": "distinct-count", "format": "#,###"},
    {"name": "TotalObligationAmount", "column": "obligation_amount", "aggregator": "sum", "format": "#,###"},
    {"name": "AdmittedRatio", "column": "admitted_ratio", "aggregator": "avg", "format": "0.00%"},
    {"name": "AvgPerformanceRate", "column": "performance_rate", "aggregator": "avg", "format": "0.00%"},
    {"name": "AvgCaseDuration", "column": "case_duration_days", "aggregator": "avg", "format": "#,###"},
    {"name": "StakeholderSatisfactionRate", "column": "satisfaction_rate", "aggregator": "avg", "format": "0.00%"}
  ]
}
```

---

## 4. 피벗 쿼리 실행

### POST `/api/v3/pivot/query`

#### Request

```json
{
  "cube_name": "BusinessAnalysisCube",
  "rows": ["CaseType.CaseCategory", "Organization.Industry"],
  "columns": ["Time.Year"],
  "measures": ["CaseCount", "AvgPerformanceRate"],
  "filters": [
    {
      "dimension_level": "CaseType.CaseStatus",
      "operator": "in",
      "values": ["COMPLETED", "IN_PROGRESS"]
    },
    {
      "dimension_level": "Time.Year",
      "operator": ">=",
      "values": [2022]
    }
  ],
  "sort_by": "CaseCount",
  "sort_order": "DESC",
  "limit": 100,
  "offset": 0
}
```

#### 필드 명세

| 필드 | 타입 | 필수 | Nullable | 설명 |
|------|------|:----:|:--------:|------|
| `cube_name` | string | Y | N | 큐브 이름 |
| `rows` | string[] | Y | N | 행 차원 (Dimension.Level 형식) |
| `columns` | string[] | N | Y | 열 차원 (없으면 집계만) |
| `measures` | string[] | Y | N | 측도 (1개 이상) |
| `filters` | array | N | Y | 필터 조건 |
| `filters[].dimension_level` | string | Y | N | 필터 대상 (Dimension.Level) |
| `filters[].operator` | string | Y | N | =, !=, in, not_in, >=, <=, between |
| `filters[].values` | array | Y | N | 필터 값 |
| `sort_by` | string | N | Y | 정렬 기준 측도 이름 |
| `sort_order` | string | N | Y | ASC 또는 DESC (기본 DESC) |
| `limit` | integer | N | N | 최대 행 수 (기본 1000, 최대 10000) |
| `offset` | integer | N | N | 오프셋 (기본 0) |

#### Response (200 OK)

```json
{
  "cube_name": "BusinessAnalysisCube",
  "generated_sql": "SELECT ct.category AS ...",
  "execution_time_ms": 245,
  "total_rows": 24,
  "columns": [
    {"name": "CaseType.CaseCategory", "type": "string"},
    {"name": "Organization.Industry", "type": "string"},
    {"name": "Time.Year", "type": "number"},
    {"name": "CaseCount", "type": "number"},
    {"name": "AvgPerformanceRate", "type": "number"}
  ],
  "rows": [
    {
      "CaseType.CaseCategory": "구조조정",
      "Organization.Industry": "제조업",
      "Time.Year": 2024,
      "CaseCount": 45,
      "AvgPerformanceRate": 0.32
    },
    {
      "CaseType.CaseCategory": "성장전략",
      "Organization.Industry": "서비스업",
      "Time.Year": 2024,
      "CaseCount": 28,
      "AvgPerformanceRate": 0.58
    }
  ],
  "aggregations": {
    "CaseCount_total": 156,
    "AvgPerformanceRate_overall": 0.41
  }
}
```

---

## 5. 자연어 → 피벗 쿼리

### POST `/api/v3/pivot/nl-query`

자연어 질의를 LLM이 피벗 파라미터로 변환하여 실행한다.

#### Request

```json
{
  "query": "2024년 제조업 비즈니스의 이해관계자별 성과 분석을 보여줘",
  "cube_name": "BusinessAnalysisCube",
  "include_sql": true
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|:----:|------|
| `query` | string | Y | 자연어 질의 (한국어/영어) |
| `cube_name` | string | N | 큐브 지정 (없으면 자동 선택) |
| `include_sql` | boolean | N | true면 생성된 SQL 포함 반환 |

#### Response (200 OK)

```json
{
  "original_query": "2024년 제조업 비즈니스의 이해관계자별 성과 분석을 보여줘",
  "interpreted_as": {
    "cube_name": "BusinessAnalysisCube",
    "rows": ["Stakeholder.StakeholderType"],
    "columns": [],
    "measures": ["AvgPerformanceRate", "CaseCount"],
    "filters": [
      {"dimension_level": "Time.Year", "operator": "=", "values": [2024]},
      {"dimension_level": "Organization.Industry", "operator": "=", "values": ["제조업"]},
      {"dimension_level": "CaseType.CaseCategory", "operator": "=", "values": ["구조조정"]}
    ]
  },
  "generated_sql": "SELECT stk_type.stakeholder_type, AVG(f.performance_rate), COUNT(DISTINCT f.case_id) FROM mv_business_fact f ...",
  "result": {
    "columns": [
      {"name": "Stakeholder.StakeholderType", "type": "string"},
      {"name": "AvgPerformanceRate", "type": "number"},
      {"name": "CaseCount", "type": "number"}
    ],
    "rows": [
      {"Stakeholder.StakeholderType": "금융기관", "AvgPerformanceRate": 0.78, "CaseCount": 45},
      {"Stakeholder.StakeholderType": "거래처", "AvgPerformanceRate": 0.22, "CaseCount": 45},
      {"Stakeholder.StakeholderType": "핵심 이해관계자", "AvgPerformanceRate": 0.95, "CaseCount": 38}
    ]
  },
  "confidence": 0.92,
  "execution_time_ms": 3200
}
```

---

## 6. 드릴스루

### GET `/api/v3/pivot/drillthrough`

피벗 셀 클릭 시 원본 레코드를 조회한다.

#### Query Parameters

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|:----:|------|
| `cube_name` | string | Y | 큐브 이름 |
| `CaseType.CaseCategory` | string | N | 차원 필터 (피벗 셀 좌표) |
| `Time.Year` | integer | N | 차원 필터 |
| `limit` | integer | N | 기본 50 |

#### Response (200 OK)

```json
{
  "total_count": 45,
  "records": [
    {
      "case_id": "uuid-1",
      "case_number": "2024-BIZ-101",
      "company_name": "ABC 주식회사",
      "case_type": "구조조정",
      "filing_date": "2024-03-15",
      "total_obligations": 5000000000,
      "performance_rate": 0.32
    }
  ]
}
```

---

## 7. ETL 동기화

### POST `/api/v3/etl/sync`

OLTP → Materialized View 동기화를 트리거한다.

#### Request

```json
{
  "sync_type": "incremental",
  "target_views": ["mv_business_fact"],
  "force": false
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|:----:|------|
| `sync_type` | enum | Y | `full` (전체 REFRESH) 또는 `incremental` (변경분만) |
| `target_views` | string[] | N | 대상 MV (없으면 전체) |
| `force` | boolean | N | true면 동시 실행 중이어도 강제 실행 |

#### Response (202 Accepted)

```json
{
  "sync_id": "550e8400-e29b-41d4-a716-446655440020",
  "sync_type": "incremental",
  "target_views": ["mv_business_fact"],
  "status": "RUNNING",
  "started_at": "2026-02-19T10:40:00Z"
}
```

### GET `/api/v3/etl/status`

```json
{
  "sync_id": "550e8400-e29b-41d4-a716-446655440020",
  "status": "COMPLETED",
  "started_at": "2026-02-19T10:40:00Z",
  "completed_at": "2026-02-19T10:40:45Z",
  "duration_seconds": 45,
  "rows_affected": {
    "mv_business_fact": 1523
  }
}
```

---

## 8. Airflow DAG 트리거

### POST `/api/v3/etl/airflow/trigger-dag`

#### Request

```json
{
  "dag_id": "vision_olap_full_sync",
  "conf": {
    "target_views": ["mv_business_fact", "mv_cashflow_fact"]
  }
}
```

#### Response (200 OK)

```json
{
  "dag_id": "vision_olap_full_sync",
  "dag_run_id": "manual__2026-02-19T10:45:00+00:00",
  "state": "queued"
}
```

---

## 에러 코드

| HTTP | 코드 | 의미 | 사용자 표시 |
|:----:|------|------|-----------|
| 400 | `INVALID_CUBE_NAME` | 존재하지 않는 큐브 | "큐브 '{name}'을(를) 찾을 수 없습니다" |
| 400 | `INVALID_DIMENSION` | 큐브에 없는 차원/레벨 | "'{dim}'은(는) 유효하지 않은 차원입니다" |
| 400 | `INVALID_MEASURE` | 큐브에 없는 측도 | "'{measure}'은(는) 유효하지 않은 측도입니다" |
| 400 | `INVALID_XML` | 파싱 불가능한 XML | "큐브 스키마 XML이 유효하지 않습니다" |
| 422 | `SQL_VALIDATION_FAILED` | 생성된 SQL 검증 실패 | "질의를 처리할 수 없습니다. 다시 시도해 주세요" |
| 504 | `QUERY_TIMEOUT` | 쿼리 타임아웃 (30초) | "쿼리 실행 시간이 초과되었습니다. 필터를 추가해 보세요" |
| 503 | `ETL_IN_PROGRESS` | ETL 진행 중 재요청 | "데이터 동기화가 진행 중입니다" |

---

## 권한 (Permissions)

| 작업 | 필요 역할 | 비고 |
|------|----------|------|
| 피벗 쿼리 실행 | VIEWER 이상 | org_id 기반 데이터 격리 |
| NL 질의 | VIEWER 이상 | |
| 큐브 스키마 업로드 | ADMIN | |
| ETL 동기화 트리거 | ADMIN | |
| Airflow DAG 트리거 | ADMIN | |

<!-- affects: 04_frontend, 03_backend/mondrian-parser.md -->
<!-- requires-update: 06_data/cube-definitions.md -->
