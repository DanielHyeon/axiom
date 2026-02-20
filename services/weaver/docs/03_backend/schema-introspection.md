# 스키마 인트로스펙션 엔진

<!-- affects: backend, data -->
<!-- requires-update: 02_api/metadata-api.md, 06_data/neo4j-schema.md -->

## 이 문서가 답하는 질문

- 인트로스펙션 서비스는 어떤 순서로 메타데이터를 추출하는가?
- SSE 이벤트 생성은 어떻게 구현하는가?
- K-AIR의 schema_introspection.py (880줄)에서 무엇을 이식하는가?
- 대규모 DB (수백 테이블)에서의 성능은 어떻게 보장하는가?

---

## 1. K-AIR 원본 분석

K-AIR의 `backend/app/services/schema_introspection.py` (880줄)은 단일 파일에 PostgreSQL, MySQL 어댑터를 모두 포함하고 있었다.

### 이식 시 변경사항

| K-AIR | Weaver | 변경 이유 |
|-------|--------|----------|
| 단일 파일 880줄 | 어댑터별 분리 | 유지보수성 + 새 엔진 추가 용이 |
| Oracle 미지원 | Oracle 어댑터 추가 | 엔터프라이즈 요구 (대형 기관 DB) |
| 동기 연결 | 비동기 우선 (asyncpg, aiomysql) | FastAPI 비동기 특성 활용 |
| SSE 진행률 미흡 | 단계별 상세 SSE 이벤트 | Canvas UI 프로그레스 바 지원 |

---

## 2. 인트로스펙션 서비스

```python
# app/services/introspection_service.py
import logging
from typing import AsyncGenerator, Optional
from app.adapters.factory import AdapterFactory
from app.neo4j.metadata_store import MetadataStore
from app.schemas.metadata import ProgressEvent, MetadataResult

logger = logging.getLogger(__name__)


class IntrospectionService:
    """Schema Introspection Orchestrator

    어댑터를 사용하여 대상 DB에서 메타데이터를 추출하고,
    Neo4j에 저장하며, SSE 이벤트를 생성한다.

    K-AIR 원본: backend/app/services/schema_introspection.py (880줄)
    """

    def __init__(self, metadata_store: MetadataStore):
        self.metadata_store = metadata_store

    async def extract_metadata(
        self,
        datasource_name: str,
        engine: str,
        connection_params: dict,
        target_schemas: Optional[list[str]] = None,
        include_sample_data: bool = False,
        sample_limit: int = 5,
        include_row_counts: bool = True,
    ) -> AsyncGenerator[ProgressEvent, None]:
        """Extract metadata from datasource and yield SSE events

        This is an async generator that yields ProgressEvent objects.
        The API layer converts these to SSE format.

        Args:
            datasource_name: Registered datasource name
            engine: DB engine type (postgresql, mysql, oracle)
            connection_params: Connection parameters for the adapter
            target_schemas: Specific schemas to extract (None = all)
            include_sample_data: Whether to include sample rows
            sample_limit: Number of sample rows per table
            include_row_counts: Whether to include row counts

        Yields:
            ProgressEvent objects for SSE streaming
        """

        # 1. Create adapter
        adapter = AdapterFactory.get_adapter(engine, connection_params)

        try:
            # 2. Connect to database
            await adapter.connect()
            yield ProgressEvent(
                event="started",
                data={
                    "datasource": datasource_name,
                    "engine": engine,
                },
            )

            # 3. Get schemas
            all_schemas = await adapter.get_schemas()
            schemas = (
                [s for s in all_schemas if s in target_schemas]
                if target_schemas
                else all_schemas
            )

            for i, schema in enumerate(schemas, 1):
                yield ProgressEvent(
                    event="schema_found",
                    data={
                        "schema": schema,
                        "index": i,
                        "total_schemas": len(schemas),
                    },
                )

            yield ProgressEvent(
                event="progress",
                data={
                    "phase": "schemas",
                    "completed": len(schemas),
                    "total": len(schemas),
                    "percent": 100,
                },
            )

            # 4. Collect all tables and columns
            all_tables = []
            all_columns = []
            all_fks = []
            total_tables = 0

            # First pass: count total tables
            for schema in schemas:
                tables = await adapter.get_tables(schema)
                total_tables += len(tables)

            # Second pass: extract details
            table_index = 0
            for schema in schemas:
                tables = await adapter.get_tables(schema)

                for table in tables:
                    table_index += 1

                    yield ProgressEvent(
                        event="table_found",
                        data={
                            "schema": schema,
                            "table": table.table_name,
                            "type": table.table_type,
                            "row_count": table.row_count,
                            "index": table_index,
                            "total_tables": total_tables,
                        },
                    )

                    # Get columns
                    columns = await adapter.get_columns(schema, table.table_name)
                    primary_keys = [c.name for c in columns if c.is_primary_key]

                    yield ProgressEvent(
                        event="columns_extracted",
                        data={
                            "schema": schema,
                            "table": table.table_name,
                            "columns_count": len(columns),
                            "primary_keys": primary_keys,
                        },
                    )

                    # Get foreign keys
                    fks = await adapter.get_foreign_keys(schema, table.table_name)

                    if fks:
                        yield ProgressEvent(
                            event="fk_extracted",
                            data={
                                "schema": schema,
                                "table": table.table_name,
                                "fk_count": len(fks),
                                "targets": list(set(fk.target_table for fk in fks)),
                            },
                        )

                    # Get sample data (optional)
                    sample_data = None
                    if include_sample_data:
                        try:
                            sample_data = await adapter.get_sample_data(
                                schema, table.table_name, sample_limit
                            )
                        except Exception as e:
                            logger.warning(
                                f"Failed to get sample data for {schema}.{table.table_name}: {e}"
                            )

                    all_tables.append({
                        "schema": schema,
                        "table": table,
                        "columns": columns,
                        "sample_data": sample_data,
                    })
                    all_columns.extend(
                        {"schema": schema, "table": table.table_name, "column": col}
                        for col in columns
                    )
                    all_fks.extend(
                        {"schema": schema, "table": table.table_name, "fk": fk}
                        for fk in fks
                    )

                    # Progress update
                    percent = int((table_index / total_tables) * 100)
                    yield ProgressEvent(
                        event="progress",
                        data={
                            "phase": "tables",
                            "completed": table_index,
                            "total": total_tables,
                            "percent": percent,
                            "current_schema": schema,
                            "current_table": table.table_name,
                        },
                    )

            # 5. Save to Neo4j
            save_result = await self.metadata_store.save_datasource_metadata(
                datasource_name=datasource_name,
                engine=engine,
                connection_params=connection_params,
                tables=all_tables,
                foreign_keys=all_fks,
            )

            yield ProgressEvent(
                event="neo4j_saved",
                data=save_result,
            )

            # 6. Complete
            yield ProgressEvent(
                event="complete",
                data={
                    "datasource": datasource_name,
                    "schemas": len(schemas),
                    "tables": total_tables,
                    "columns": len(all_columns),
                    "foreign_keys": len(all_fks),
                },
            )

        except Exception as e:
            logger.error(f"Metadata extraction failed for {datasource_name}: {e}")
            yield ProgressEvent(
                event="error",
                data={
                    "error": str(e),
                    "phase": "extraction",
                },
            )

        finally:
            await adapter.disconnect()
```

---

## 3. SSE 라우터 통합

```python
# app/api/metadata.py
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

router = APIRouter()


@router.post("/datasources/{name}/extract-metadata")
async def extract_metadata(
    name: str,
    request: Request,
    body: MetadataRequest,
):
    """Extract metadata from datasource via SSE streaming"""

    # Get datasource info from MindsDB
    mindsdb: MindsDBClient = request.app.state.mindsdb
    neo4j: Neo4jClient = request.app.state.neo4j

    # Validate engine supports introspection
    datasource = await get_datasource_details(name, mindsdb)
    if not AdapterFactory.is_supported(datasource.engine):
        raise UnsupportedEngineError(datasource.engine)

    metadata_store = MetadataStore(neo4j)
    service = IntrospectionService(metadata_store)

    async def event_generator():
        async for event in service.extract_metadata(
            datasource_name=name,
            engine=datasource.engine,
            connection_params=datasource.connection,
            target_schemas=body.schemas,
            include_sample_data=body.include_sample_data,
            sample_limit=body.sample_limit,
            include_row_counts=body.include_row_counts,
        ):
            yield f"event: {event.event}\ndata: {event.to_json()}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Nginx SSE support
        },
    )
```

---

## 4. 성능 최적화

### 4.1 대규모 DB 처리

| 전략 | 설명 |
|------|------|
| **커넥션 풀** | 어댑터별 최소 1 / 최대 5 커넥션 |
| **행 수 추정치** | PostgreSQL `reltuples`, MySQL `TABLE_ROWS`, Oracle `num_rows` |
| **시스템 스키마 제외** | `pg_catalog`, `information_schema`, `sys` 등 |
| **타임아웃** | 어댑터 명령별 30초 타임아웃 |
| **배치 Neo4j 저장** | `UNWIND` 배치 처리 (개별 CREATE 아닌) |

### 4.2 예상 처리 시간

| DB 규모 | 테이블 수 | 예상 시간 |
|--------|----------|----------|
| 소규모 | ~20 | 5-10초 |
| 중규모 | ~100 | 30-60초 |
| 대규모 | ~500 | 2-5분 |

---

## 5. 관련 문서

| 문서 | 설명 |
|------|------|
| `01_architecture/adapter-pattern.md` | 어댑터 패턴 설계 |
| `02_api/metadata-api.md` | 메타데이터 추출 API (SSE) |
| `03_backend/neo4j-metadata.md` | Neo4j 메타데이터 저장 |
| `06_data/neo4j-schema.md` | Neo4j 그래프 스키마 |
