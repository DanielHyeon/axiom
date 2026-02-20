# Neo4j 메타데이터 저장/관리

<!-- affects: backend, data, llm -->
<!-- requires-update: 06_data/neo4j-schema.md -->

## 이 문서가 답하는 질문

- 메타데이터는 Neo4j에 어떻게 저장되는가?
- CRUD 작업은 어떤 Cypher 쿼리를 사용하는가?
- K-AIR의 neo4j_service.py (297줄)에서 무엇을 이식하는가?
- 메타데이터 삭제/재생성 전략은 무엇인가?

---

## 1. K-AIR 원본 분석

K-AIR의 `backend/app/services/neo4j_service.py` (297줄)에서 이식하는 핵심 기능:

| K-AIR 메서드 | Weaver 대응 | 설명 |
|-------------|------------|------|
| `create_datasource_node(...)` | `save_datasource(...)` | DataSource 노드 생성/업데이트 |
| `create_schema_node(...)` | `save_schema(...)` | Schema 노드 생성 |
| `create_table_node(...)` | `save_table(...)` | Table 노드 생성 |
| `create_column_node(...)` | `save_column(...)` | Column 노드 생성 |
| `create_fk_relationship(...)` | `save_foreign_key(...)` | FK 관계 생성 |
| `delete_datasource_metadata(...)` | `delete_metadata(...)` | 전체 메타데이터 삭제 |

---

## 2. Neo4j 클라이언트

```python
# app/neo4j/client.py
from neo4j import AsyncGraphDatabase, AsyncDriver
import logging

logger = logging.getLogger(__name__)


class Neo4jClient:
    """Neo4j Driver Wrapper

    단일 드라이버 인스턴스를 관리하고, 세션 생성을 제공한다.
    """

    def __init__(self, uri: str, user: str, password: str):
        self.driver: AsyncDriver = AsyncGraphDatabase.driver(
            uri, auth=(user, password)
        )

    async def verify_connectivity(self):
        """Verify Neo4j connection on startup"""
        await self.driver.verify_connectivity()
        logger.info("Neo4j connection verified")

    async def close(self):
        """Close driver on shutdown"""
        await self.driver.close()

    async def execute_query(self, query: str, parameters: dict = None) -> list:
        """Execute a Cypher query and return results"""
        async with self.driver.session() as session:
            result = await session.run(query, parameters or {})
            return [record.data() async for record in result]

    async def execute_write(self, query: str, parameters: dict = None):
        """Execute a write Cypher query"""
        async with self.driver.session() as session:
            await session.run(query, parameters or {})
```

---

## 3. 메타데이터 저장소

```python
# app/neo4j/metadata_store.py
import logging
from typing import Optional
from app.neo4j.client import Neo4jClient

logger = logging.getLogger(__name__)


class MetadataStore:
    """Neo4j Metadata CRUD

    DataSource → Schema → Table → Column 계층 구조를
    Neo4j 그래프에 저장/조회/삭제한다.

    K-AIR 원본: backend/app/services/neo4j_service.py (297줄)
    """

    def __init__(self, neo4j: Neo4jClient):
        self.neo4j = neo4j

    # ─── Save Operations (Batch) ─────────────────────────

    async def save_datasource_metadata(
        self,
        datasource_name: str,
        engine: str,
        connection_params: dict,
        tables: list[dict],
        foreign_keys: list[dict],
    ) -> dict:
        """Save complete datasource metadata to Neo4j

        1. Delete existing metadata for this datasource
        2. Create DataSource node
        3. Batch create Schema, Table, Column nodes
        4. Create FK relationships

        Returns:
            dict with nodes_created, relationships_created, duration_ms
        """
        import time
        start = time.monotonic()

        # Step 1: Delete existing metadata
        await self._delete_datasource_metadata(datasource_name)

        # Step 2: Create DataSource node
        # password is excluded from stored params
        safe_params = {k: v for k, v in connection_params.items() if k != "password"}
        await self._create_datasource_node(datasource_name, engine, safe_params)

        # Step 3: Batch create schemas, tables, columns
        schemas_set = set()
        nodes_created = 1  # DataSource node
        relationships_created = 0

        for table_data in tables:
            schema = table_data["schema"]
            table = table_data["table"]
            columns = table_data["columns"]

            # Schema node (deduplicated)
            if schema not in schemas_set:
                await self._create_schema_node(datasource_name, schema)
                schemas_set.add(schema)
                nodes_created += 1
                relationships_created += 1  # HAS_SCHEMA

            # Table node
            await self._create_table_node(
                datasource_name, schema, table.table_name,
                description=table.comment,
                row_count=table.row_count,
            )
            nodes_created += 1
            relationships_created += 1  # HAS_TABLE

            # Column nodes (batch)
            if columns:
                await self._batch_create_columns(
                    datasource_name, schema, table.table_name, columns
                )
                nodes_created += len(columns)
                relationships_created += len(columns)  # HAS_COLUMN

        # Step 4: FK relationships
        for fk_data in foreign_keys:
            fk = fk_data["fk"]
            await self._create_fk_relationship(
                datasource_name,
                fk_data["schema"],
                fk_data["table"],
                fk.source_column,
                fk.target_schema,
                fk.target_table,
                fk.target_column,
            )
            relationships_created += 2  # FK_TO + FK_TO_TABLE

        elapsed = int((time.monotonic() - start) * 1000)

        return {
            "nodes_created": nodes_created,
            "relationships_created": relationships_created,
            "duration_ms": elapsed,
        }

    # ─── Individual Node Creation ────────────────────────

    async def _create_datasource_node(
        self, name: str, engine: str, params: dict
    ):
        query = """
            MERGE (ds:DataSource {name: $name})
            SET ds.engine = $engine,
                ds.host = $host,
                ds.port = $port,
                ds.database = $database,
                ds.user = $user,
                ds.last_extracted = datetime()
        """
        await self.neo4j.execute_write(query, {
            "name": name,
            "engine": engine,
            "host": params.get("host", ""),
            "port": params.get("port", 0),
            "database": params.get("database", ""),
            "user": params.get("user", ""),
        })

    async def _create_schema_node(self, datasource: str, schema: str):
        query = """
            MATCH (ds:DataSource {name: $datasource})
            MERGE (s:Schema {name: $schema})<-[:HAS_SCHEMA]-(ds)
        """
        await self.neo4j.execute_write(query, {
            "datasource": datasource,
            "schema": schema,
        })

    async def _create_table_node(
        self, datasource: str, schema: str, table: str,
        description: Optional[str] = None, row_count: Optional[int] = None,
    ):
        query = """
            MATCH (ds:DataSource {name: $datasource})-[:HAS_SCHEMA]->(s:Schema {name: $schema})
            MERGE (t:Table {name: $table})<-[:HAS_TABLE]-(s)
            SET t.description = $description,
                t.row_count = $row_count
        """
        await self.neo4j.execute_write(query, {
            "datasource": datasource,
            "schema": schema,
            "table": table,
            "description": description,
            "row_count": row_count,
        })

    async def _batch_create_columns(
        self, datasource: str, schema: str, table: str, columns: list
    ):
        """Batch create column nodes using UNWIND"""
        query = """
            MATCH (ds:DataSource {name: $datasource})-[:HAS_SCHEMA]->(s:Schema {name: $schema})-[:HAS_TABLE]->(t:Table {name: $table})
            UNWIND $columns as col
            CREATE (c:Column {
                name: col.name,
                dtype: col.data_type,
                nullable: col.nullable,
                description: col.comment,
                is_primary_key: col.is_primary_key,
                default_value: col.default_value
            })
            CREATE (t)-[:HAS_COLUMN]->(c)
        """
        await self.neo4j.execute_write(query, {
            "datasource": datasource,
            "schema": schema,
            "table": table,
            "columns": [
                {
                    "name": c.name,
                    "data_type": c.data_type,
                    "nullable": c.nullable,
                    "comment": c.comment,
                    "is_primary_key": c.is_primary_key,
                    "default_value": c.default_value,
                }
                for c in columns
            ],
        })

    async def _create_fk_relationship(
        self, datasource: str,
        source_schema: str, source_table: str, source_column: str,
        target_schema: str, target_table: str, target_column: str,
    ):
        """Create FK_TO relationship between columns and FK_TO_TABLE between tables"""

        # Column-level FK
        query_col = """
            MATCH (ds:DataSource {name: $datasource})
                -[:HAS_SCHEMA]->(ss:Schema {name: $source_schema})
                -[:HAS_TABLE]->(st:Table {name: $source_table})
                -[:HAS_COLUMN]->(sc:Column {name: $source_column})
            MATCH (ds)
                -[:HAS_SCHEMA]->(ts:Schema {name: $target_schema})
                -[:HAS_TABLE]->(tt:Table {name: $target_table})
                -[:HAS_COLUMN]->(tc:Column {name: $target_column})
            MERGE (sc)-[:FK_TO]->(tc)
        """
        await self.neo4j.execute_write(query_col, {
            "datasource": datasource,
            "source_schema": source_schema,
            "source_table": source_table,
            "source_column": source_column,
            "target_schema": target_schema,
            "target_table": target_table,
            "target_column": target_column,
        })

        # Table-level FK (summary)
        query_table = """
            MATCH (ds:DataSource {name: $datasource})
                -[:HAS_SCHEMA]->(ss:Schema {name: $source_schema})
                -[:HAS_TABLE]->(st:Table {name: $source_table})
            MATCH (ds)
                -[:HAS_SCHEMA]->(ts:Schema {name: $target_schema})
                -[:HAS_TABLE]->(tt:Table {name: $target_table})
            MERGE (st)-[:FK_TO_TABLE]->(tt)
        """
        await self.neo4j.execute_write(query_table, {
            "datasource": datasource,
            "source_schema": source_schema,
            "source_table": source_table,
            "target_schema": target_schema,
            "target_table": target_table,
        })

    # ─── Delete Operations ───────────────────────────────

    async def _delete_datasource_metadata(self, datasource: str):
        """Delete all metadata nodes under a datasource

        Cascade delete: DataSource -> Schema -> Table -> Column
        """
        query = """
            MATCH (ds:DataSource {name: $datasource})-[*]->(n)
            DETACH DELETE n
        """
        await self.neo4j.execute_write(query, {"datasource": datasource})
        logger.info(f"Deleted existing metadata for datasource: {datasource}")

    async def delete_datasource_completely(self, datasource: str):
        """Delete datasource node AND all related metadata"""
        await self._delete_datasource_metadata(datasource)
        query = "MATCH (ds:DataSource {name: $datasource}) DETACH DELETE ds"
        await self.neo4j.execute_write(query, {"datasource": datasource})

    # ─── Query Operations ────────────────────────────────

    async def get_datasource_metadata(self, datasource: str) -> dict:
        """Get complete metadata tree for a datasource"""
        query = """
            MATCH (ds:DataSource {name: $datasource})-[:HAS_SCHEMA]->(s:Schema)-[:HAS_TABLE]->(t:Table)-[:HAS_COLUMN]->(c:Column)
            WITH ds, s, t, collect({
                name: c.name,
                dtype: c.dtype,
                nullable: c.nullable,
                description: c.description,
                is_primary_key: c.is_primary_key
            }) as columns
            WITH ds, s, collect({
                name: t.name,
                description: t.description,
                row_count: t.row_count,
                columns: columns
            }) as tables
            RETURN ds.name as datasource,
                   ds.engine as engine,
                   collect({
                       name: s.name,
                       tables: tables
                   }) as schemas
        """
        results = await self.neo4j.execute_query(query, {"datasource": datasource})
        return results[0] if results else None

    async def get_table_relationships(self, datasource: str, table: str) -> list:
        """Get FK relationships for a specific table"""
        query = """
            MATCH (ds:DataSource {name: $datasource})-[:HAS_SCHEMA]->(s:Schema)-[:HAS_TABLE]->(t:Table {name: $table})-[:HAS_COLUMN]->(c:Column)-[:FK_TO]->(tc:Column)<-[:HAS_COLUMN]-(tt:Table)
            RETURN c.name as source_column,
                   tt.name as target_table,
                   tc.name as target_column
        """
        return await self.neo4j.execute_query(query, {
            "datasource": datasource,
            "table": table,
        })

    async def find_join_path(
        self, datasource: str, table1: str, table2: str, max_hops: int = 3
    ) -> list:
        """Find FK-based join path between two tables (max N hops)

        Oracle(NL2SQL) 모듈이 자동 조인 경로 탐색에 사용한다.
        """
        query = """
            MATCH (ds:DataSource {name: $datasource})-[:HAS_SCHEMA]->(:Schema)-[:HAS_TABLE]->(t1:Table {name: $table1}),
                  (ds)-[:HAS_SCHEMA]->(:Schema)-[:HAS_TABLE]->(t2:Table {name: $table2})
            MATCH path = shortestPath((t1)-[:FK_TO_TABLE*1..{max_hops}]-(t2))
            RETURN [n IN nodes(path) | n.name] as tables,
                   length(path) as hops
        """.replace("{max_hops}", str(max_hops))
        return await self.neo4j.execute_query(query, {
            "datasource": datasource,
            "table1": table1,
            "table2": table2,
        })

    async def update_column_description(
        self, datasource: str, schema: str, table: str, column: str, description: str
    ):
        """Update column description (LLM enrichment result)"""
        query = """
            MATCH (ds:DataSource {name: $datasource})
                -[:HAS_SCHEMA]->(s:Schema {name: $schema})
                -[:HAS_TABLE]->(t:Table {name: $table})
                -[:HAS_COLUMN]->(c:Column {name: $column})
            SET c.description = $description
        """
        await self.neo4j.execute_write(query, {
            "datasource": datasource,
            "schema": schema,
            "table": table,
            "column": column,
            "description": description,
        })

    async def update_table_description(
        self, datasource: str, schema: str, table: str, description: str
    ):
        """Update table description (LLM enrichment result)"""
        query = """
            MATCH (ds:DataSource {name: $datasource})
                -[:HAS_SCHEMA]->(s:Schema {name: $schema})
                -[:HAS_TABLE]->(t:Table {name: $table})
            SET t.description = $description
        """
        await self.neo4j.execute_write(query, {
            "datasource": datasource,
            "schema": schema,
            "table": table,
            "description": description,
        })
```

---

## 4. Neo4j 인덱스

성능을 위해 다음 인덱스를 생성해야 한다.

```cypher
-- Unique constraint
CREATE CONSTRAINT ds_name IF NOT EXISTS FOR (ds:DataSource) REQUIRE ds.name IS UNIQUE;

-- Index for fast lookups
CREATE INDEX schema_name IF NOT EXISTS FOR (s:Schema) ON (s.name);
CREATE INDEX table_name IF NOT EXISTS FOR (t:Table) ON (t.name);
CREATE INDEX column_name IF NOT EXISTS FOR (c:Column) ON (c.name);
```

---

## 5. 관련 문서

| 문서 | 설명 |
|------|------|
| `06_data/neo4j-schema.md` | Neo4j 그래프 스키마 상세 |
| `03_backend/schema-introspection.md` | 인트로스펙션 서비스 |
| `05_llm/metadata-enrichment.md` | LLM 기반 메타데이터 보강 |
| `99_decisions/ADR-003-neo4j-metadata.md` | Neo4j 선택 근거 |
| `03_backend/metadata-propagation.md` | 메타데이터 변경 전파 메커니즘 |
| `06_data/neo4j-schema-v2.md` | Neo4j 메타데이터 스키마 v2 (멀티테넌트, 패브릭 스냅샷) |
