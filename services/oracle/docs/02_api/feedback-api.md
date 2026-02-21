# 피드백 + 이력 API

> 구현 상태 태그: `Partially Implemented`
> 기준일: 2026-02-21

## 이 문서가 답하는 질문

- 사용자가 SQL 품질에 대한 피드백을 어떻게 제출하는가?
- 쿼리 이력은 어떻게 조회하는가?
- 피드백은 NL2SQL 품질 개선에 어떻게 활용되는가?

<!-- affects: 06_data -->
<!-- requires-update: 06_data/query-history.md -->

---

## 1. 엔드포인트 요약

| Method | Path | 설명 | 인증 | 상태 | 근거 |
|--------|------|------|------|------|------|
| POST | `/feedback` | SQL 피드백 제출 | Required | Implemented | `services/oracle/app/api/feedback.py` |
| GET | `/text2sql/history` | 쿼리 이력 조회 | Required | Planned | `services/oracle/docs/06_data/query-history.md` |
| GET | `/text2sql/history/{id}` | 특정 이력 상세 | Required | Planned | `services/oracle/docs/06_data/query-history.md` |

---

## 2. POST /feedback

### 2.1 설명

생성된 SQL에 대한 사용자 피드백을 제출한다. 피드백은 Neo4j의 Query 노드에 반영되어 향후 유사 질문의 SQL 품질 개선에 활용된다.

### 2.2 요청

```json
{
    "query_id": "q_20240115_abc123",
    "rating": "positive",
    "corrected_sql": null,
    "comment": "정확한 결과입니다"
}
```

| 필드 | 타입 | 필수 | Nullable | 설명 |
|------|------|------|----------|------|
| `query_id` | string | Yes | No | 대상 쿼리 ID (ask 응답의 metadata에 포함) |
| `rating` | string | Yes | No | 평가 ("positive" / "negative" / "partial") |
| `corrected_sql` | string | No | Yes | 사용자가 수정한 올바른 SQL |
| `comment` | string | No | Yes | 피드백 코멘트 |

### 2.3 응답 (200 OK)

```json
{
    "success": true
}
```

> 주의: 현재 구현은 최소 저장 성공 여부만 반환한다.

### 2.4 피드백 처리 흐름

```
피드백 수신
    │
    ├─ positive → Query 노드의 verified=true, confidence 증가
    │
    ├─ negative → Query 노드의 verified=false, confidence 감소
    │             corrected_sql 있으면 새 Query 노드 생성
    │
    └─ partial → confidence 미변경, comment만 기록
```

---

## 3. GET /text2sql/history (Planned)

### 3.1 설명

사용자의 쿼리 이력을 조회한다. 페이지네이션과 필터링을 지원한다.

### 3.2 요청 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|----------|------|------|--------|------|
| `datasource_id` | string | No | - | 데이터소스 필터 |
| `page` | integer | No | 1 | 페이지 번호 |
| `page_size` | integer | No | 20 | 페이지 크기 (최대 100) |
| `date_from` | string | No | - | 시작일 (ISO 8601) |
| `date_to` | string | No | - | 종료일 (ISO 8601) |
| `status` | string | No | - | 상태 필터 (success/error) |

### 3.3 응답 (200 OK)

```json
{
    "success": true,
    "data": {
        "history": [
            {
                "id": "q_20240115_abc123",
                "question": "2024년 매출 성장률이 가장 높은 사업부는?",
                "sql": "SELECT COUNT(*) ...",
                "status": "success",
                "execution_time_ms": 1247,
                "row_count": 1,
                "datasource_id": "ds_business_main",
                "created_at": "2024-01-15T09:30:00Z",
                "feedback": {
                    "rating": "positive",
                    "comment": "정확한 결과입니다"
                }
            }
        ],
        "pagination": {
            "page": 1,
            "page_size": 20,
            "total_count": 156,
            "total_pages": 8
        }
    }
}
```

| 필드 | 타입 | Nullable | 설명 |
|------|------|----------|------|
| `history[].id` | string | No | 쿼리 ID |
| `history[].question` | string | No | 원본 질문 |
| `history[].sql` | string | No | 생성된 SQL |
| `history[].status` | string | No | 실행 상태 (success/error) |
| `history[].execution_time_ms` | integer | No | 실행 시간 |
| `history[].row_count` | integer | Yes | 결과 행 수 (에러 시 null) |
| `history[].datasource_id` | string | No | 데이터소스 ID |
| `history[].created_at` | string | No | 생성 시각 (ISO 8601) |
| `history[].feedback` | object | Yes | 피드백 (없으면 null) |

---

## 4. GET /text2sql/history/{id} (Planned)

### 4.1 설명

특정 쿼리 이력의 상세 정보를 조회한다. 실행 결과 데이터를 포함한다.

### 4.2 응답 (200 OK)

```json
{
    "success": true,
    "data": {
        "id": "q_20240115_abc123",
        "question": "2024년 매출 성장률이 가장 높은 사업부는?",
        "sql": "SELECT d.dept_name, SUM(s.revenue) AS total_revenue FROM ...",
        "status": "success",
        "result": {
            "columns": [{"name": "dept_name", "type": "varchar"}, {"name": "total_revenue", "type": "decimal"}],
            "rows": [[342]],
            "row_count": 1
        },
        "metadata": {
            "execution_time_ms": 1247,
            "tables_used": ["sales_records", "departments"],
            "cache_hit": false,
            "guard_status": "PASS",
            "pipeline_steps": [
                {"step": "embed", "duration_ms": 120},
                {"step": "graph_search", "duration_ms": 340},
                {"step": "sql_generate", "duration_ms": 650},
                {"step": "sql_guard", "duration_ms": 12},
                {"step": "sql_execute", "duration_ms": 125}
            ]
        },
        "datasource_id": "ds_business_main",
        "created_at": "2024-01-15T09:30:00Z",
        "feedback": null
    }
}
```

---

## 결정 사항

| 결정 | 근거 |
|------|------|
| 이력 저장소는 PostgreSQL 표준으로 운영 | SQLite는 K-AIR 레거시 저장소이며 동시 쓰기에 취약 |
| 피드백은 Synapse API 경유로 그래프 저장소에 반영 | 벡터 검색에서 피드백이 반영된 쿼리가 우선 검색되도록 |

## 관련 문서

- [06_data/query-history.md](../06_data/query-history.md): 이력 스키마
- [03_backend/cache-system.md](../03_backend/cache-system.md): 캐시 시스템
