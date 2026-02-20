# 메타데이터 추출 API

> **참고**: 이 문서는 메타데이터 추출(SSE 스트리밍) API만 다룹니다. 패브릭 스냅샷, 비즈니스 용어 사전, 태깅 등 카탈로그 API는 `02_api/metadata-catalog-api.md`를 참조하세요.

<!-- affects: frontend, backend, data, llm -->
<!-- requires-update: 03_backend/schema-introspection.md, 06_data/neo4j-schema.md -->

## 이 문서가 답하는 질문

- 메타데이터 추출은 어떻게 시작하는가?
- SSE 스트리밍으로 진행률을 어떻게 받는가?
- 추출 결과는 어디에 저장되는가?
- Oracle(NL2SQL) 모듈은 메타데이터를 어떻게 활용하는가?

---

## 1. 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `POST` | `/api/datasources/{name}/extract-metadata` | 메타데이터 추출 시작 (SSE 스트리밍) |

---

## 2. POST /api/datasources/{name}/extract-metadata

### 2.1 개요

지정한 데이터소스에 직접 연결하여 스키마, 테이블, 컬럼, FK 관계를 추출하고 Neo4j 그래프에 저장한다. 이 과정은 **SSE(Server-Sent Events)**로 진행률을 실시간 전송한다.

**주의**: MindsDB를 경유하지 않고 **대상 DB에 직접 연결**한다 (어댑터 패턴 사용). MindsDB는 스키마 인트로스펙션 기능이 제한적이기 때문이다.

### 2.2 지원 엔진

메타데이터 추출이 지원되는 엔진만 이 API를 사용할 수 있다.

| 엔진 | 지원 | 어댑터 |
|------|------|--------|
| PostgreSQL | 지원 | `PostgreSQLAdapter` |
| MySQL | 지원 | `MySQLAdapter` |
| Oracle | 지원 (신규) | `OracleAdapter` |
| MongoDB | 미지원 | - |
| Redis | 미지원 | - |
| Elasticsearch | 미지원 | - |

### 2.3 요청

```
POST /api/datasources/erp_db/extract-metadata
Content-Type: application/json
Accept: text/event-stream

{
  "schemas": ["public", "operations"],
  "include_sample_data": true,
  "sample_limit": 5,
  "include_row_counts": true
}
```

| 필드 | 타입 | 필수 | 기본값 | 설명 |
|------|------|------|--------|------|
| `schemas` | `string[]` | 선택 | 전체 | 추출할 스키마 목록 (null이면 전체) |
| `include_sample_data` | `boolean` | 선택 | `false` | 샘플 데이터 포함 여부 |
| `sample_limit` | `integer` | 선택 | `5` | 샘플 데이터 행 수 (최대 100) |
| `include_row_counts` | `boolean` | 선택 | `true` | 테이블 행 수 포함 여부 |

### 2.4 SSE 응답 스트림

응답은 `text/event-stream` 형식이며, 각 이벤트는 추출 진행 단계를 나타낸다.

#### 이벤트 타입

| 이벤트 | 데이터 | 설명 |
|--------|--------|------|
| `started` | 초기 정보 | 추출 시작 |
| `schema_found` | 스키마 정보 | 스키마 발견 |
| `table_found` | 테이블 정보 | 테이블 발견 |
| `columns_extracted` | 컬럼 정보 | 컬럼 추출 완료 |
| `fk_extracted` | FK 정보 | 외래 키 추출 완료 |
| `progress` | 진행률 | 전체 진행률 업데이트 |
| `neo4j_saved` | 저장 정보 | Neo4j 저장 완료 |
| `complete` | 최종 결과 | 추출 완료 |
| `error` | 에러 정보 | 에러 발생 |

#### SSE 스트림 예시

```
event: started
data: {"datasource": "erp_db", "engine": "postgresql", "timestamp": "2026-02-19T10:00:00Z"}

event: schema_found
data: {"schema": "public", "index": 1, "total_schemas": 3}

event: schema_found
data: {"schema": "operations", "index": 2, "total_schemas": 3}

event: schema_found
data: {"schema": "audit", "index": 3, "total_schemas": 3}

event: progress
data: {"phase": "schemas", "completed": 3, "total": 3, "percent": 100}

event: table_found
data: {"schema": "public", "table": "processes", "type": "BASE TABLE", "row_count": 15420, "index": 1, "total_tables": 25}

event: columns_extracted
data: {"schema": "public", "table": "processes", "columns_count": 12, "primary_keys": ["id"]}

event: fk_extracted
data: {"schema": "public", "table": "processes", "fk_count": 2, "targets": ["organizations", "departments"]}

event: progress
data: {"phase": "tables", "completed": 1, "total": 25, "percent": 4, "current_schema": "public", "current_table": "processes"}

event: table_found
data: {"schema": "public", "table": "stakeholders", "type": "BASE TABLE", "row_count": 87650, "index": 2, "total_tables": 25}

event: columns_extracted
data: {"schema": "public", "table": "stakeholders", "columns_count": 8, "primary_keys": ["id"]}

event: fk_extracted
data: {"schema": "public", "table": "stakeholders", "fk_count": 1, "targets": ["processes"]}

event: progress
data: {"phase": "tables", "completed": 2, "total": 25, "percent": 8, "current_schema": "public", "current_table": "stakeholders"}

... (나머지 테이블들)

event: neo4j_saved
data: {"nodes_created": 190, "relationships_created": 175, "duration_ms": 450}

event: complete
data: {"datasource": "erp_db", "schemas": 3, "tables": 25, "columns": 150, "foreign_keys": 18, "duration_ms": 12500, "timestamp": "2026-02-19T10:00:12Z"}
```

### 2.5 추출 처리 흐름

```
POST /extract-metadata
        │
        ▼
┌─ 1. 어댑터 선택 ──────────────────────┐
│  engine = "postgresql"                  │
│  adapter = PostgreSQLAdapter(conn)      │
└────────────┬────────────────────────────┘
             │
             ▼
┌─ 2. 스키마 수집 ──────────────────────┐
│  schemas = adapter.get_schemas()       │
│  → SSE: schema_found (각 스키마)       │
└────────────┬────────────────────────────┘
             │
             ▼
┌─ 3. 테이블 수집 (스키마별) ────────────┐
│  for schema in schemas:                 │
│    tables = adapter.get_tables(schema)  │
│    for table in tables:                 │
│      → SSE: table_found                 │
│      columns = adapter.get_columns(...) │
│      → SSE: columns_extracted           │
│      fks = adapter.get_foreign_keys(...)│
│      → SSE: fk_extracted                │
│      → SSE: progress                    │
└────────────┬────────────────────────────┘
             │
             ▼
┌─ 4. Neo4j 저장 ───────────────────────┐
│  기존 메타데이터 삭제 (해당 DS)        │
│  DataSource 노드 생성/업데이트         │
│  Schema 노드 생성 + HAS_SCHEMA 관계    │
│  Table 노드 생성 + HAS_TABLE 관계      │
│  Column 노드 생성 + HAS_COLUMN 관계    │
│  FK_TO 관계 생성                        │
│  FK_TO_TABLE 관계 생성                  │
│  → SSE: neo4j_saved                     │
└────────────┬────────────────────────────┘
             │
             ▼
┌─ 5. 완료 ─────────────────────────────┐
│  → SSE: complete                        │
│  연결 해제                               │
└─────────────────────────────────────────┘
```

### 2.6 에러 처리

추출 중 에러 발생 시 SSE `error` 이벤트를 전송하고 스트림을 종료한다.

```
event: error
data: {"phase": "tables", "schema": "public", "table": "large_table", "error": "Connection timed out", "partial_result": {"schemas": 3, "tables_completed": 15, "tables_failed": 1}}
```

| 에러 상황 | 동작 |
|-----------|------|
| 대상 DB 연결 실패 | 즉시 에러 이벤트, 스트림 종료 |
| 개별 테이블 조회 실패 | 해당 테이블 건너뛰고 계속, 에러 로그 |
| Neo4j 저장 실패 | 에러 이벤트, 이미 추출한 데이터는 반환 |
| 미지원 엔진 | 400 에러 (SSE 시작 전 거부) |

---

## 3. Neo4j 저장 전략

### 3.1 멱등성

동일한 데이터소스에 대해 메타데이터 추출을 반복 실행하면, **기존 메타데이터를 삭제하고 새로 생성**한다.

```cypher
-- 기존 메타데이터 삭제
MATCH (ds:DataSource {name: $datasource_name})-[*]->(n)
DETACH DELETE n

-- DataSource 노드는 업데이트
MERGE (ds:DataSource {name: $datasource_name})
SET ds.engine = $engine,
    ds.last_extracted = datetime()
```

### 3.2 배치 저장

대량의 노드/관계 생성을 위해 Cypher `UNWIND` 배치 처리를 사용한다.

```cypher
-- 컬럼 노드 배치 생성
UNWIND $columns as col
MATCH (t:Table {name: col.table_name})<-[:HAS_TABLE]-(s:Schema {name: col.schema_name})<-[:HAS_SCHEMA]-(ds:DataSource {name: $datasource_name})
CREATE (c:Column {
    name: col.name,
    dtype: col.data_type,
    nullable: col.nullable,
    description: col.description
})
CREATE (t)-[:HAS_COLUMN]->(c)
```

---

## 4. 클라이언트 연동 예시

### 4.1 JavaScript (Canvas React)

```javascript
const extractMetadata = async (datasourceName) => {
  const eventSource = new EventSource(
    `/api/datasources/${datasourceName}/extract-metadata`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        include_sample_data: false,
        include_row_counts: true,
      }),
    }
  );

  eventSource.addEventListener('progress', (event) => {
    const data = JSON.parse(event.data);
    console.log(`[${data.phase}] ${data.completed}/${data.total} (${data.percent}%)`);
    // UI 프로그레스 바 업데이트
  });

  eventSource.addEventListener('complete', (event) => {
    const result = JSON.parse(event.data);
    console.log(`Extraction complete: ${result.tables} tables, ${result.columns} columns`);
    eventSource.close();
  });

  eventSource.addEventListener('error', (event) => {
    const error = JSON.parse(event.data);
    console.error(`Extraction error: ${error.error}`);
    eventSource.close();
  });
};
```

### 4.2 Python (내부 서비스 호출)

```python
import httpx

async def extract_metadata(datasource_name: str):
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            f"http://weaver:8000/api/datasources/{datasource_name}/extract-metadata",
            json={"include_row_counts": True},
            headers={"Accept": "text/event-stream"},
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("event:"):
                    event_type = line.split(":", 1)[1].strip()
                elif line.startswith("data:"):
                    data = json.loads(line.split(":", 1)[1].strip())
                    if event_type == "complete":
                        return data
                    elif event_type == "error":
                        raise Exception(data["error"])
```

---

## 5. 권한

| 작업 | 필요 권한 |
|------|----------|
| 메타데이터 추출 | `datasource:write` (관리자) |

---

## 6. 관련 문서

| 문서 | 설명 |
|------|------|
| `01_architecture/adapter-pattern.md` | 어댑터 패턴 설계 |
| `03_backend/schema-introspection.md` | 인트로스펙션 서비스 구현 |
| `03_backend/neo4j-metadata.md` | Neo4j 메타데이터 저장/관리 |
| `06_data/neo4j-schema.md` | Neo4j 그래프 스키마 상세 |
| `05_llm/metadata-enrichment.md` | LLM 기반 메타데이터 보강 |
