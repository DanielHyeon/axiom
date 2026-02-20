# Event Log 관리 API

## 이 문서가 답하는 질문

- 이벤트 로그를 어떻게 생성/조회/삭제하는가?
- XES, CSV, DB 소스에서 이벤트 로그를 어떻게 인제스트하는가?
- 이벤트 로그의 컬럼 매핑(case_id, activity, timestamp)은 어떻게 설정하는가?
- pm4py DataFrame으로의 변환 과정은?

<!-- affects: frontend, backend, data -->
<!-- requires-update: 06_data/event-log-schema.md, 01_architecture/process-mining-engine.md -->

---

## 1. 기본 정보

| 항목 | 값 |
|------|---|
| Base URL (Synapse 내부) | `/api/v3/synapse/event-logs` |
| Base URL (Core 게이트웨이 경유) | `/api/v1/event-logs` |
| 인증 | JWT Bearer Token (Core 경유) |
| Content-Type | `application/json` (메타데이터), `multipart/form-data` (파일 업로드) |
| 비동기 작업 | 대용량 인제스트는 task_id 기반 비동기 |

> **라우팅 참고**: 외부 클라이언트는 Core 게이트웨이(`/api/v1/event-logs`)를 통해 접근한다. Core가 Synapse 내부 URL로 프록시한다. 게이트웨이 라우팅 상세는 Core [gateway-api.md](../../../core/docs/02_api/gateway-api.md) §1을 참조한다.

---

## 2. 엔드포인트 목록

| Method | Path | 설명 | 동기/비동기 |
|--------|------|------|-----------|
| POST | `/ingest` | 이벤트 로그 인제스트 (CSV/XES/DB) | 비동기 |
| GET | `/` | 이벤트 로그 목록 조회 | 동기 |
| GET | `/{log_id}` | 이벤트 로그 상세 조회 | 동기 |
| DELETE | `/{log_id}` | 이벤트 로그 삭제 | 동기 |
| GET | `/{log_id}/statistics` | 이벤트 로그 통계 | 동기 |
| GET | `/{log_id}/preview` | 이벤트 로그 미리보기 (상위 100건) | 동기 |
| PUT | `/{log_id}/column-mapping` | 컬럼 매핑 수정 | 동기 |
| POST | `/{log_id}/refresh` | 이벤트 로그 재인제스트 (DB 소스) | 비동기 |

---

## 3. 엔드포인트 상세

### 3.1 POST /ingest

이벤트 로그를 인제스트한다. CSV 파일 업로드, XES 파일 업로드, 또는 DB 테이블 연결을 지원한다.

#### Request: CSV 파일 업로드

```
POST /api/v1/event-logs/ingest
Authorization: Bearer <jwt_token>
Content-Type: multipart/form-data

file: (CSV file binary)
metadata: {
  "case_id": "550e8400-e29b-41d4-a716-446655440001",
  "name": "주문 프로세스 2024년 로그",
  "source_type": "csv",
  "column_mapping": {
    "case_id_column": "order_id",
    "activity_column": "event_type",
    "timestamp_column": "event_time",
    "resource_column": "handler_name",
    "additional_columns": ["department", "priority", "amount"]
  },
  "options": {
    "timestamp_format": "ISO8601",
    "encoding": "utf-8",
    "delimiter": ","
  }
}
```

#### Request: DB 테이블 연결

```json
POST /api/v1/event-logs/ingest
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "case_id": "550e8400-e29b-41d4-a716-446655440001",
  "name": "ERP 주문 이벤트",
  "source_type": "database",
  "source_config": {
    "connection_id": "erp-connection-uuid",
    "table_name": "order_events",
    "schema": "public"
  },
  "column_mapping": {
    "case_id_column": "order_id",
    "activity_column": "event_type",
    "timestamp_column": "event_time",
    "resource_column": "handler_name",
    "additional_columns": ["department", "priority"]
  },
  "filter": {
    "where_clause": "event_time >= '2024-01-01'",
    "max_rows": 1000000
  }
}
```

#### Request: XES 파일 업로드

```
POST /api/v1/event-logs/ingest
Authorization: Bearer <jwt_token>
Content-Type: multipart/form-data

file: (XES file binary)
metadata: {
  "case_id": "550e8400-e29b-41d4-a716-446655440001",
  "name": "주문 프로세스 XES 로그",
  "source_type": "xes"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `case_id` | uuid | Y | Axiom 프로젝트 ID |
| `name` | string | Y | 이벤트 로그 이름 |
| `source_type` | string | Y | csv, xes, database |
| `column_mapping.case_id_column` | string | csv/db시 Y | 케이스 식별 컬럼 |
| `column_mapping.activity_column` | string | csv/db시 Y | 활동명 컬럼 |
| `column_mapping.timestamp_column` | string | csv/db시 Y | 타임스탬프 컬럼 |
| `column_mapping.resource_column` | string | N | 리소스(담당자) 컬럼 |
| `column_mapping.additional_columns` | array | N | 추가 속성 컬럼 |
| `options.timestamp_format` | string | N | ISO8601, epoch, custom |
| `filter.where_clause` | string | db시 N | SQL WHERE 조건 |
| `filter.max_rows` | int | N | 최대 행 수 (기본: 1,000,000) |

#### Response (202 Accepted)

```json
{
  "success": true,
  "data": {
    "task_id": "task-ingest-uuid-001",
    "log_id": "log-uuid-001",
    "name": "주문 프로세스 2024년 로그",
    "source_type": "csv",
    "status": "ingesting",
    "created_at": "2024-06-16T10:00:00Z"
  }
}
```

#### 인제스트 완료 후 상태

```json
{
  "success": true,
  "data": {
    "log_id": "log-uuid-001",
    "status": "completed",
    "statistics": {
      "total_events": 8750,
      "total_cases": 1250,
      "unique_activities": 6,
      "date_range": {
        "start": "2024-01-01T08:00:00Z",
        "end": "2024-06-30T17:30:00Z"
      },
      "ingestion_duration_seconds": 12.5
    }
  }
}
```

---

### 3.2 GET /

이벤트 로그 목록을 조회한다.

#### Request

```
GET /api/v1/event-logs?case_id=550e8400-e29b-41d4-a716-446655440001
Authorization: Bearer <jwt_token>
```

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|-------|------|
| `case_id` | uuid | Y | - | Axiom 프로젝트 ID |
| `limit` | int | N | 20 | 최대 결과 수 |
| `offset` | int | N | 0 | 페이지네이션 오프셋 |

#### Response (200 OK)

```json
{
  "success": true,
  "data": {
    "logs": [
      {
        "log_id": "log-uuid-001",
        "name": "주문 프로세스 2024년 로그",
        "source_type": "csv",
        "total_events": 8750,
        "total_cases": 1250,
        "unique_activities": 6,
        "date_range_start": "2024-01-01T08:00:00Z",
        "date_range_end": "2024-06-30T17:30:00Z",
        "created_at": "2024-06-16T10:00:00Z"
      }
    ],
    "total": 3
  }
}
```

---

### 3.3 GET /{log_id}/statistics

이벤트 로그의 상세 통계를 반환한다.

#### Response (200 OK)

```json
{
  "success": true,
  "data": {
    "log_id": "log-uuid-001",
    "overview": {
      "total_events": 8750,
      "total_cases": 1250,
      "unique_activities": 6,
      "avg_events_per_case": 7.0,
      "date_range_start": "2024-01-01T08:00:00Z",
      "date_range_end": "2024-06-30T17:30:00Z"
    },
    "activities": [
      {
        "name": "주문 접수",
        "frequency": 1250,
        "relative_frequency": 1.0,
        "avg_duration_seconds": 300
      },
      {
        "name": "결제 확인",
        "frequency": 1240,
        "relative_frequency": 0.992,
        "avg_duration_seconds": 1800
      },
      {
        "name": "출하 지시",
        "frequency": 1230,
        "relative_frequency": 0.984,
        "avg_duration_seconds": 7200
      }
    ],
    "case_duration": {
      "avg_seconds": 172800,
      "median_seconds": 145200,
      "min_seconds": 3600,
      "max_seconds": 864000,
      "p25_seconds": 86400,
      "p75_seconds": 259200,
      "p95_seconds": 518400
    },
    "variants": {
      "total_variants": 15,
      "top_3_coverage": 0.936
    },
    "resources": [
      {
        "name": "김영수",
        "event_count": 450,
        "case_count": 320
      }
    ]
  }
}
```

---

### 3.4 GET /{log_id}/preview

이벤트 로그의 상위 이벤트를 미리보기한다. 인제스트 후 데이터 확인에 사용한다.

#### Request

```
GET /api/v1/event-logs/log-uuid-001/preview?limit=10
Authorization: Bearer <jwt_token>
```

#### Response (200 OK)

```json
{
  "success": true,
  "data": {
    "log_id": "log-uuid-001",
    "column_mapping": {
      "case_id_column": "order_id",
      "activity_column": "event_type",
      "timestamp_column": "event_time",
      "resource_column": "handler_name"
    },
    "events": [
      {
        "case_id": "ORD-2024-001",
        "activity": "주문 접수",
        "timestamp": "2024-01-02T09:15:00Z",
        "resource": "김영수",
        "attributes": {
          "department": "영업팀",
          "priority": "normal",
          "amount": 150000
        }
      },
      {
        "case_id": "ORD-2024-001",
        "activity": "결제 확인",
        "timestamp": "2024-01-02T09:45:00Z",
        "resource": "이지은",
        "attributes": {
          "department": "회계팀",
          "priority": "normal"
        }
      }
    ],
    "total_preview": 10
  }
}
```

---

### 3.5 PUT /{log_id}/column-mapping

이벤트 로그의 컬럼 매핑을 수정한다. 매핑 변경 후 내부 데이터가 재변환된다.

#### Request

```json
PUT /api/v1/event-logs/log-uuid-001/column-mapping
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "column_mapping": {
    "case_id_column": "order_number",
    "activity_column": "step_name",
    "timestamp_column": "occurred_at",
    "resource_column": "performer"
  }
}
```

#### Response (200 OK)

```json
{
  "success": true,
  "data": {
    "log_id": "log-uuid-001",
    "column_mapping": {
      "case_id_column": "order_number",
      "activity_column": "step_name",
      "timestamp_column": "occurred_at",
      "resource_column": "performer"
    },
    "reprocessing_status": "completed",
    "updated_statistics": {
      "total_cases": 1250,
      "unique_activities": 6
    }
  }
}
```

---

## 4. pm4py DataFrame 변환 내부 처리

인제스트된 이벤트 로그는 내부적으로 pm4py 표준 형식으로 변환된다.

```python
import pm4py
import pandas as pd

def convert_to_pm4py_dataframe(
    events: list[dict],
    column_mapping: ColumnMapping
) -> pd.DataFrame:
    """
    Convert ingested events to pm4py standard DataFrame.

    pm4py requires:
    - case:concept:name   (case identifier)
    - concept:name        (activity name)
    - time:timestamp      (event timestamp)
    """
    df = pd.DataFrame(events)

    df = pm4py.format_dataframe(
        df,
        case_id=column_mapping.case_id_column,
        activity_key=column_mapping.activity_column,
        timestamp_key=column_mapping.timestamp_column,
    )

    # Sort by case and timestamp
    df = df.sort_values(['case:concept:name', 'time:timestamp'])

    return df
```

---

## 5. 에러 코드

| HTTP Status | Code | 의미 |
|------------|------|------|
| 400 | `INVALID_SOURCE_TYPE` | 지원하지 않는 소스 유형 |
| 400 | `INVALID_CSV_FORMAT` | CSV 파싱 실패 |
| 400 | `INVALID_XES_FORMAT` | XES 파싱 실패 |
| 400 | `MISSING_COLUMN` | 매핑된 컬럼이 데이터에 없음 |
| 400 | `INVALID_TIMESTAMP` | 타임스탬프 파싱 실패 |
| 404 | `LOG_NOT_FOUND` | 이벤트 로그 없음 |
| 413 | `FILE_TOO_LARGE` | 파일 크기 초과 (최대 500MB) |
| 422 | `INGESTION_FAILED` | 인제스트 실패 |
| 503 | `DATABASE_CONNECTION_FAILED` | DB 소스 연결 실패 |

---

## 6. 권한

| 엔드포인트 | 필요 역할 |
|----------|---------|
| POST /ingest | case_editor, admin |
| GET (조회) | case_viewer, case_editor, admin |
| PUT /column-mapping | case_editor, admin |
| DELETE | admin |
| POST /refresh | case_editor, admin |

---

## 근거 문서

- `06_data/event-log-schema.md` (PostgreSQL 이벤트 로그 스키마)
- `01_architecture/process-mining-engine.md` (엔진 아키텍처)
- ADR-005: pm4py 선택 (`99_decisions/ADR-005-pm4py-process-mining.md`)
