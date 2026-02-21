# 메타데이터 탐색 API

> 구현 상태 태그: `Planned`
> 기준일: 2026-02-21

## 이 문서가 답하는 질문

- 어떤 테이블과 컬럼이 NL2SQL에 사용 가능한지 어떻게 확인하는가?
- 스키마 메타데이터를 어떻게 탐색하는가?
- 데이터소스 목록은 어떻게 조회하는가?

<!-- affects: 04_frontend -->
<!-- requires-update: 06_data/neo4j-schema.md -->

---

## 1. 엔드포인트 요약

| Method | Path | 설명 | 인증 | 상태 | 근거(구현/티켓) |
|--------|------|------|------|------|------------------|
| GET | `/text2sql/meta/tables` | 테이블 목록 + 검색 | Required | Planned | `docs/implementation-plans/oracle/95_sprint2-ticket-board.md` |
| GET | `/text2sql/meta/tables/{name}/columns` | 특정 테이블 컬럼 상세 | Required | Planned | `docs/implementation-plans/oracle/95_sprint2-ticket-board.md` |
| GET | `/text2sql/meta/datasources` | 데이터소스 목록 | Required | Planned | `docs/implementation-plans/oracle/95_sprint2-ticket-board.md` |
| PUT | `/text2sql/meta/tables/{name}/description` | 테이블 설명 수정 | Required + Admin | Planned | `docs/implementation-plans/oracle/95_sprint2-ticket-board.md` |
| PUT | `/text2sql/meta/columns/{fqn}/description` | 컬럼 설명 수정 | Required + Admin | Planned | `docs/implementation-plans/oracle/95_sprint2-ticket-board.md` |

---

## 2. GET /text2sql/meta/tables

### 2.1 설명

Synapse Graph/Meta API에 등록된 테이블 목록을 반환한다. 키워드 검색과 페이지네이션을 지원한다.

### 2.2 요청 파라미터 (Query String)

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|----------|------|------|--------|------|
| `datasource_id` | string | Yes | - | 데이터소스 ID |
| `search` | string | No | - | 검색 키워드 (테이블명/설명에서 검색) |
| `page` | integer | No | 1 | 페이지 번호 |
| `page_size` | integer | No | 50 | 페이지 크기 (최대 200) |
| `valid_only` | boolean | No | true | NL2SQL 유효 테이블만 필터 |

### 2.3 응답 (200 OK)

```json
{
    "success": true,
    "data": {
        "tables": [
            {
                "name": "sales_records",
                "schema": "public",
                "db": "business_db",
                "description": "매출 실적 데이터 테이블",
                "column_count": 15,
                "is_valid": true,
                "has_vector": true
            },
            {
                "name": "departments",
                "schema": "public",
                "db": "business_db",
                "description": "조직/부서 정보 마스터 테이블",
                "column_count": 5,
                "is_valid": true,
                "has_vector": true
            }
        ],
        "pagination": {
            "page": 1,
            "page_size": 50,
            "total_count": 47,
            "total_pages": 1
        }
    }
}
```

| 필드 | 타입 | Nullable | 설명 |
|------|------|----------|------|
| `tables[].name` | string | No | 테이블 이름 |
| `tables[].schema` | string | Yes | 스키마 이름 (없으면 null) |
| `tables[].db` | string | No | 데이터베이스 이름 |
| `tables[].description` | string | Yes | 테이블 설명 (한글) |
| `tables[].column_count` | integer | No | 컬럼 수 |
| `tables[].is_valid` | boolean | No | NL2SQL 사용 가능 여부 |
| `tables[].has_vector` | boolean | No | 벡터 인덱스 존재 여부 |

---

## 3. GET /text2sql/meta/tables/{name}/columns

### 3.1 설명

특정 테이블의 컬럼 상세 정보를 반환한다. FK 관계 정보를 포함한다.

### 3.2 경로 파라미터

| 파라미터 | 타입 | 설명 |
|----------|------|------|
| `name` | string | 테이블 이름 |

### 3.3 쿼리 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|----------|------|------|--------|------|
| `datasource_id` | string | Yes | - | 데이터소스 ID |

### 3.4 응답 (200 OK)

```json
{
    "success": true,
    "data": {
        "table": {
            "name": "process_metrics",
            "schema": "public",
            "description": "비즈니스 프로세스 성과 지표 테이블"
        },
        "columns": [
            {
                "name": "metric_id",
                "fqn": "public.process_metrics.metric_id",
                "data_type": "bigint",
                "nullable": false,
                "is_primary_key": true,
                "description": "지표 고유 ID",
                "has_vector": true,
                "foreign_keys": []
            },
            {
                "name": "org_id",
                "fqn": "public.process_metrics.org_id",
                "data_type": "integer",
                "nullable": false,
                "is_primary_key": false,
                "description": "조직 ID",
                "has_vector": true,
                "foreign_keys": [
                    {
                        "target_table": "organizations",
                        "target_column": "org_id",
                        "relationship": "MANY_TO_ONE"
                    }
                ]
            },
            {
                "name": "measured_date",
                "fqn": "public.process_metrics.measured_date",
                "data_type": "date",
                "nullable": true,
                "is_primary_key": false,
                "description": "측정일",
                "has_vector": true,
                "foreign_keys": []
            }
        ],
        "value_mappings": [
            {
                "column_fqn": "public.process_metrics.status",
                "mappings": [
                    {"natural_value": "성공", "db_value": "SUCCESS", "confidence": 0.95},
                    {"natural_value": "실패", "db_value": "FAILED", "confidence": 0.93}
                ]
            }
        ]
    }
}
```

---

## 4. GET /text2sql/meta/datasources

### 4.1 설명

사용 가능한 데이터소스 목록을 반환한다.

### 4.2 응답 (200 OK)

```json
{
    "success": true,
    "data": {
        "datasources": [
            {
                "id": "ds_business_main",
                "name": "비즈니스 메인 DB",
                "type": "postgresql",
                "host": "db.axiom.internal",
                "database": "business_db",
                "table_count": 47,
                "status": "active"
            }
        ]
    }
}
```

---

## 5. PUT /text2sql/meta/tables/{name}/description

### 5.1 설명

테이블 설명을 수정한다. 관리자 전용. 수정 시 벡터 인덱스가 자동 재생성된다.

### 5.2 요청

```json
{
    "datasource_id": "ds_business_main",
    "description": "비즈니스 프로세스 성과 지표를 저장하는 핵심 테이블. 프로세스ID, 조직, 측정일, 결과 등의 정보를 포함한다."
}
```

### 5.3 응답 (200 OK)

```json
{
    "success": true,
    "data": {
        "table": "process_metrics",
        "description": "비즈니스 프로세스 성과 지표를 저장하는 핵심 테이블...",
        "vector_updated": true
    }
}
```

---

## 6. PUT /text2sql/meta/columns/{fqn}/description

### 6.1 설명

컬럼 설명을 수정한다. FQN(Fully Qualified Name) 형식: `schema.table.column`

### 6.2 요청

```json
{
    "datasource_id": "ds_business_main",
    "description": "측정일. DATE 타입. NULL이면 미측정 상태."
}
```

### 6.3 응답 (200 OK)

```json
{
    "success": true,
    "data": {
        "column_fqn": "public.process_metrics.measured_date",
        "description": "측정일. DATE 타입. NULL이면 미측정 상태.",
        "vector_updated": true
    }
}
```

---

## 관련 문서

- [06_data/neo4j-schema.md](../06_data/neo4j-schema.md): Neo4j 스키마 상세
- [06_data/value-mapping.md](../06_data/value-mapping.md): 값 매핑 상세
- [03_backend/graph-search.md](../03_backend/graph-search.md): 그래프 검색 구현
