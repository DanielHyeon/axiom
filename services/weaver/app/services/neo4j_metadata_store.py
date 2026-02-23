from __future__ import annotations

import json
from typing import Any

from app.core.config import settings
from app.services.resilience import CircuitBreakerOpenError, SimpleCircuitBreaker, with_retry


class Neo4jStoreUnavailableError(RuntimeError):
    pass


class Neo4jMetadataStore:
    def __init__(self) -> None:
        self._driver = None
        self._breaker = SimpleCircuitBreaker(failure_threshold=3, reset_timeout_seconds=20.0)

    async def _get_driver(self):
        try:
            self._breaker.preflight()
        except CircuitBreakerOpenError as exc:
            raise Neo4jStoreUnavailableError(str(exc)) from exc
        if self._driver is not None:
            return self._driver
        if not settings.neo4j_password:
            raise Neo4jStoreUnavailableError("NEO4J_PASSWORD is required for metadata external mode")
        try:
            from neo4j import AsyncGraphDatabase  # type: ignore
        except Exception as exc:
            raise Neo4jStoreUnavailableError("neo4j package is not installed") from exc
        self._driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        return self._driver

    async def health_check(self) -> None:
        await self._read("RETURN 1 AS ok", {})

    async def _read(self, query: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        async def _call() -> list[dict[str, Any]]:
            driver = await self._get_driver()
            async with driver.session() as session:
                result = await session.run(query, params)
                return [dict(record) async for record in result]
        try:
            rows = await with_retry(_call, retries=2, base_delay_seconds=0.05)
            self._breaker.on_success()
            return rows
        except CircuitBreakerOpenError as exc:
            raise Neo4jStoreUnavailableError(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            self._breaker.on_failure()
            raise Neo4jStoreUnavailableError(str(exc)) from exc

    async def _write(self, query: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        return await self._read(query, params)

    async def save_snapshot(self, item: dict[str, Any], tenant_id: str | None = None) -> None:
        await self._write(
            """
            MERGE (s:MetadataSnapshot {tenant_id: $tenant_id, snapshot_id: $snapshot_id})
            SET s.tenant_id = $tenant_id,
                s.case_id = $case_id,
                s.datasource = $datasource,
                s.version = $version,
                s.status = $status,
                s.description = $description,
                s.created_by = $created_by,
                s.created_at = $created_at,
                s.completed_at = $completed_at,
                s.summary_json = $summary_json,
                s.graph_data_json = $graph_data_json
            """,
            {
                "snapshot_id": item["id"],
                "tenant_id": tenant_id if tenant_id is not None else str(item.get("tenant_id") or ""),
                "case_id": item["case_id"],
                "datasource": item["datasource"],
                "version": item["version"],
                "status": item["status"],
                "description": item.get("description"),
                "created_by": item["created_by"],
                "created_at": item["created_at"],
                "completed_at": item.get("completed_at"),
                "summary_json": json.dumps(item.get("summary", {}), ensure_ascii=True),
                "graph_data_json": json.dumps(item.get("graph_data", {}), ensure_ascii=True),
            },
        )

    async def list_snapshots(self, case_id: str, datasource: str, tenant_id: str | None = None) -> list[dict[str, Any]]:
        rows = await self._read(
            """
            MATCH (s:MetadataSnapshot {tenant_id: $tenant_id, case_id: $case_id, datasource: $datasource})
            RETURN s
            ORDER BY s.version DESC
            """,
            {"tenant_id": tenant_id or "", "case_id": case_id, "datasource": datasource},
        )
        return [self._snapshot_row_to_item(r["s"]) for r in rows]

    async def get_snapshot(self, case_id: str, datasource: str, snapshot_id: str, tenant_id: str | None = None) -> dict[str, Any] | None:
        rows = await self._read(
            """
            MATCH (s:MetadataSnapshot {tenant_id: $tenant_id, case_id: $case_id, datasource: $datasource, snapshot_id: $snapshot_id})
            RETURN s
            """,
            {"tenant_id": tenant_id or "", "case_id": case_id, "datasource": datasource, "snapshot_id": snapshot_id},
        )
        if not rows:
            return None
        return self._snapshot_row_to_item(rows[0]["s"])

    async def delete_snapshot(self, case_id: str, datasource: str, snapshot_id: str, tenant_id: str | None = None) -> bool:
        rows = await self._write(
            """
            MATCH (s:MetadataSnapshot {tenant_id: $tenant_id, case_id: $case_id, datasource: $datasource, snapshot_id: $snapshot_id})
            WITH s, count(s) as c
            DETACH DELETE s
            RETURN c
            """,
            {"tenant_id": tenant_id or "", "case_id": case_id, "datasource": datasource, "snapshot_id": snapshot_id},
        )
        return bool(rows and int(rows[0]["c"]) > 0)

    async def save_glossary_term(self, item: dict[str, Any], tenant_id: str | None = None) -> None:
        await self._write(
            """
            MERGE (g:GlossaryTerm {tenant_id: $tenant_id, term_id: $term_id})
            SET g.tenant_id = $tenant_id,
                g.term = $term,
                g.definition = $definition,
                g.synonyms_json = $synonyms_json,
                g.created_at = $created_at,
                g.updated_at = $updated_at
            """,
            {
                "term_id": item["id"],
                "tenant_id": tenant_id if tenant_id is not None else str(item.get("tenant_id") or ""),
                "term": item["term"],
                "definition": item["definition"],
                "synonyms_json": json.dumps(item.get("synonyms", []), ensure_ascii=True),
                "created_at": item["created_at"],
                "updated_at": item["updated_at"],
            },
        )

    async def list_glossary_terms(self, tenant_id: str | None = None) -> list[dict[str, Any]]:
        rows = await self._read(
            "MATCH (g:GlossaryTerm {tenant_id: $tenant_id}) RETURN g ORDER BY g.created_at DESC",
            {"tenant_id": tenant_id or ""},
        )
        return [self._glossary_row_to_item(r["g"]) for r in rows]

    async def get_glossary_term(self, term_id: str, tenant_id: str | None = None) -> dict[str, Any] | None:
        rows = await self._read(
            "MATCH (g:GlossaryTerm {tenant_id: $tenant_id, term_id: $term_id}) RETURN g",
            {"tenant_id": tenant_id or "", "term_id": term_id},
        )
        if not rows:
            return None
        return self._glossary_row_to_item(rows[0]["g"])

    async def delete_glossary_term(self, term_id: str, tenant_id: str | None = None) -> bool:
        rows = await self._write(
            """
            MATCH (g:GlossaryTerm {tenant_id: $tenant_id, term_id: $term_id})
            WITH g, count(g) as c
            DETACH DELETE g
            RETURN c
            """,
            {"tenant_id": tenant_id or "", "term_id": term_id},
        )
        return bool(rows and int(rows[0]["c"]) > 0)

    async def search_glossary_terms(self, q: str, tenant_id: str | None = None) -> list[dict[str, Any]]:
        rows = await self._read(
            """
            MATCH (g:GlossaryTerm {tenant_id: $tenant_id})
            WHERE toLower(g.term) CONTAINS toLower($q) OR toLower(g.definition) CONTAINS toLower($q)
            RETURN g
            ORDER BY g.created_at DESC
            """,
            {"tenant_id": tenant_id or "", "q": q},
        )
        return [self._glossary_row_to_item(r["g"]) for r in rows]

    async def add_entity_tag(self, entity_key: str, entity_type: str, metadata: dict[str, Any], tag: str) -> list[str]:
        rows = await self._write(
            """
            MERGE (e:TaggedEntity {entity_key: $entity_key})
            ON CREATE SET e.entity_type = $entity_type,
                          e.tenant_id = $tenant_id,
                          e.case_id = $case_id,
                          e.datasource = $datasource,
                          e.table_name = $table_name,
                          e.column_name = $column_name,
                          e.tags_json = "[]"
            RETURN e.tags_json as tags_json
            """,
            {
                "entity_key": entity_key,
                "entity_type": entity_type,
                "tenant_id": metadata.get("tenant_id"),
                "case_id": metadata.get("case_id"),
                "datasource": metadata.get("datasource"),
                "table_name": metadata.get("table_name"),
                "column_name": metadata.get("column_name"),
            },
        )
        tags = self._decode_json(rows[0]["tags_json"], [])
        if tag not in tags:
            tags.append(tag)
        await self._write(
            "MATCH (e:TaggedEntity {entity_key: $entity_key}) SET e.tags_json = $tags_json",
            {"entity_key": entity_key, "tags_json": json.dumps(tags, ensure_ascii=True)},
        )
        return sorted(tags)

    async def list_entity_tags(self, entity_key: str) -> list[str]:
        rows = await self._read(
            "MATCH (e:TaggedEntity {entity_key: $entity_key}) RETURN e.tags_json as tags_json",
            {"entity_key": entity_key},
        )
        if not rows:
            return []
        return sorted(self._decode_json(rows[0]["tags_json"], []))

    async def remove_entity_tag(self, entity_key: str, tag: str) -> bool:
        rows = await self._read(
            "MATCH (e:TaggedEntity {entity_key: $entity_key}) RETURN e.tags_json as tags_json",
            {"entity_key": entity_key},
        )
        if not rows:
            return False
        tags = self._decode_json(rows[0]["tags_json"], [])
        if tag in tags:
            tags.remove(tag)
            await self._write(
                "MATCH (e:TaggedEntity {entity_key: $entity_key}) SET e.tags_json = $tags_json",
                {"entity_key": entity_key, "tags_json": json.dumps(tags, ensure_ascii=True)},
            )
        return True

    async def entities_by_tag(self, tag: str, tenant_id: str | None = None) -> list[dict[str, Any]]:
        rows = await self._read("MATCH (e:TaggedEntity {tenant_id: $tenant_id}) RETURN e", {"tenant_id": tenant_id or ""})
        results = []
        for row in rows:
            node = row["e"]
            tags = self._decode_json(node.get("tags_json"), [])
            if tag in tags:
                results.append(
                    {
                        "entity_type": node.get("entity_type"),
                        "case_id": node.get("case_id"),
                        "datasource": node.get("datasource"),
                        "table": node.get("table_name"),
                        "column": node.get("column_name"),
                    }
                )
        return results

    async def stats(self, tenant_id: str | None = None) -> dict[str, int]:
        rows = await self._read(
            """
            OPTIONAL MATCH (d:DataSource {tenant_id: $tenant_id})
            WITH count(d) AS datasources
            OPTIONAL MATCH (g:GlossaryTerm {tenant_id: $tenant_id})
            WITH datasources, count(g) AS glossary_terms
            OPTIONAL MATCH (s:MetadataSnapshot {tenant_id: $tenant_id})
            RETURN datasources, glossary_terms, count(s) AS snapshots
            """,
            {"tenant_id": tenant_id or ""},
        )
        if not rows:
            return {"datasources": 0, "glossary_terms": 0, "snapshots": 0}
        row = rows[0]
        return {
            "datasources": int(row.get("datasources", 0)),
            "glossary_terms": int(row.get("glossary_terms", 0)),
            "snapshots": int(row.get("snapshots", 0)),
        }

    async def upsert_datasource(self, name: str, engine: str, tenant_id: str | None = None) -> None:
        await self._write(
            """
            MERGE (d:DataSource {tenant_id: $tenant_id, name: $name})
            SET d.tenant_id = $tenant_id,
                d.engine = $engine
            """,
            {"tenant_id": tenant_id or "", "name": name, "engine": engine},
        )

    async def delete_datasource(self, name: str, tenant_id: str | None = None) -> None:
        await self._write(
            "MATCH (d:DataSource {tenant_id: $tenant_id, name: $name}) DETACH DELETE d",
            {"tenant_id": tenant_id or "", "name": name},
        )

    async def save_extracted_catalog(
        self,
        tenant_id: str,
        datasource_name: str,
        catalog: dict[str, dict[str, list[dict[str, Any]]]],
        engine: str = "postgresql",
        *,
        foreign_keys: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        추출된 카탈로그를 Neo4j에 DataSource-Schema-Table-Column 구조로 저장.
        catalog: { schema_name: { table_name: [ {name, data_type, nullable} ] } }
        foreign_keys: [{ source_schema, source_table, source_column, target_schema, target_table, target_column, constraint_name }]
        반환: { "nodes_created": int, "relationships_created": int, "duration_ms": int }
        """
        fk_list = foreign_keys if foreign_keys is not None else []
        import time
        start = time.perf_counter()
        tid = tenant_id or ""
        # 1) 기존 Schema 하위 그래프 제거 (Column -> Table -> Schema 순)
        await self._write(
            """
            MATCH (s:Schema {tenant_id: $tenant_id, datasource_name: $name})-[:HAS_TABLE]->(t)-[:HAS_COLUMN]->(c)
            DETACH DELETE c
            """,
            {"tenant_id": tid, "name": datasource_name},
        )
        await self._write(
            """
            MATCH (s:Schema {tenant_id: $tenant_id, datasource_name: $name})-[:HAS_TABLE]->(t)
            DETACH DELETE t
            """,
            {"tenant_id": tid, "name": datasource_name},
        )
        await self._write(
            """
            MATCH (s:Schema {tenant_id: $tenant_id, datasource_name: $name})
            DETACH DELETE s
            """,
            {"tenant_id": tid, "name": datasource_name},
        )
        # 2) DataSource MERGE
        await self._write(
            """
            MERGE (d:DataSource {tenant_id: $tenant_id, name: $name})
            SET d.engine = $engine, d.last_extracted = datetime()
            """,
            {"tenant_id": tid, "name": datasource_name, "engine": engine},
        )
        nodes_created = 0
        rels_created = 0
        # 2) Schema -> Table -> Column 생성 (tenant_id 포함해 스키마 노드 식별)
        for schema_name, tables in catalog.items():
            if not isinstance(tables, dict):
                continue
            schema_name = str(schema_name).strip()
            if not schema_name:
                continue
            await self._write(
                """
                MATCH (d:DataSource {tenant_id: $tenant_id, name: $name})
                MERGE (s:Schema {tenant_id: $tenant_id, datasource_name: $datasource_name, name: $schema_name})
                MERGE (d)-[:HAS_SCHEMA]->(s)
                """,
                {
                    "tenant_id": tid,
                    "name": datasource_name,
                    "datasource_name": datasource_name,
                    "schema_name": schema_name,
                },
            )
            nodes_created += 1
            rels_created += 1
            for table_name, columns in tables.items():
                if not isinstance(columns, list):
                    continue
                table_name = str(table_name).strip()
                if not table_name:
                    continue
                await self._write(
                    """
                    MATCH (s:Schema {tenant_id: $tenant_id, datasource_name: $datasource_name, name: $schema_name})
                    MERGE (t:Table {tenant_id: $tenant_id, datasource_name: $datasource_name, schema_name: $schema_name, name: $table_name})
                    MERGE (s)-[:HAS_TABLE]->(t)
                    """,
                    {
                        "tenant_id": tid,
                        "datasource_name": datasource_name,
                        "schema_name": schema_name,
                        "table_name": table_name,
                    },
                )
                nodes_created += 1
                rels_created += 1
                for col in columns:
                    if not isinstance(col, dict):
                        continue
                    col_name = str(col.get("name") or "").strip()
                    if not col_name:
                        continue
                    dtype = str(col.get("data_type") or col.get("type") or "string")
                    nullable = bool(col.get("nullable", True))
                    await self._write(
                        """
                        MATCH (t:Table {tenant_id: $tenant_id, datasource_name: $datasource_name, schema_name: $schema_name, name: $table_name})
                        MERGE (c:Column {tenant_id: $tenant_id, datasource_name: $datasource_name, schema_name: $schema_name, table_name: $table_name, name: $col_name})
                        SET c.dtype = $dtype, c.nullable = $nullable
                        MERGE (t)-[:HAS_COLUMN]->(c)
                        """,
                        {
                            "tenant_id": tid,
                            "datasource_name": datasource_name,
                            "schema_name": schema_name,
                            "table_name": table_name,
                            "col_name": col_name,
                            "dtype": dtype,
                            "nullable": nullable,
                        },
                    )
                    nodes_created += 1
                    rels_created += 1
        # 3) FK_TO (Column->Column), FK_TO_TABLE (Table->Table) 생성
        for fk in fk_list:
            if not isinstance(fk, dict):
                continue
            src_schema = str(fk.get("source_schema") or "").strip()
            src_table = str(fk.get("source_table") or "").strip()
            src_col = str(fk.get("source_column") or "").strip()
            tgt_schema = str(fk.get("target_schema") or "").strip()
            tgt_table = str(fk.get("target_table") or "").strip()
            tgt_col = str(fk.get("target_column") or "").strip()
            cname = str(fk.get("constraint_name") or "").strip() or "fk"
            if not all([src_schema, src_table, src_col, tgt_schema, tgt_table, tgt_col]):
                continue
            try:
                await self._write(
                    """
                    MATCH (sc:Column {tenant_id: $tid, datasource_name: $ds, schema_name: $src_schema, table_name: $src_table, name: $src_col})
                    MATCH (tc:Column {tenant_id: $tid, datasource_name: $ds, schema_name: $tgt_schema, table_name: $tgt_table, name: $tgt_col})
                    MERGE (sc)-[r:FK_TO]->(tc)
                    SET r.constraint_name = $cname
                    """,
                    {
                        "tid": tid,
                        "ds": datasource_name,
                        "src_schema": src_schema,
                        "src_table": src_table,
                        "src_col": src_col,
                        "tgt_schema": tgt_schema,
                        "tgt_table": tgt_table,
                        "tgt_col": tgt_col,
                        "cname": cname,
                    },
                )
                rels_created += 1
                await self._write(
                    """
                    MATCH (st:Table {tenant_id: $tid, datasource_name: $ds, schema_name: $src_schema, name: $src_table})
                    MATCH (tt:Table {tenant_id: $tid, datasource_name: $ds, schema_name: $tgt_schema, name: $tgt_table})
                    MERGE (st)-[:FK_TO_TABLE]->(tt)
                    """,
                    {
                        "tid": tid,
                        "ds": datasource_name,
                        "src_schema": src_schema,
                        "src_table": src_table,
                        "tgt_schema": tgt_schema,
                        "tgt_table": tgt_table,
                    },
                )
                rels_created += 1
            except Exception:
                pass
        duration_ms = int((time.perf_counter() - start) * 1000)
        return {"nodes_created": nodes_created, "relationships_created": rels_created, "duration_ms": duration_ms}

    def _snapshot_row_to_item(self, node: Any) -> dict[str, Any]:
        return {
            "id": node.get("snapshot_id"),
            "tenant_id": node.get("tenant_id"),
            "datasource": node.get("datasource"),
            "case_id": node.get("case_id"),
            "version": int(node.get("version", 0)),
            "status": node.get("status"),
            "description": node.get("description"),
            "created_by": node.get("created_by"),
            "created_at": node.get("created_at"),
            "completed_at": node.get("completed_at"),
            "summary": self._decode_json(node.get("summary_json"), {}),
            "graph_data": self._decode_json(node.get("graph_data_json"), {}),
        }

    def _glossary_row_to_item(self, node: Any) -> dict[str, Any]:
        return {
            "id": node.get("term_id"),
            "tenant_id": node.get("tenant_id"),
            "term": node.get("term"),
            "definition": node.get("definition"),
            "synonyms": self._decode_json(node.get("synonyms_json"), []),
            "created_at": node.get("created_at"),
            "updated_at": node.get("updated_at"),
        }

    @staticmethod
    def _decode_json(value: Any, default: Any) -> Any:
        if value is None:
            return default
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(str(value))
        except Exception:
            return default


neo4j_metadata_store = Neo4jMetadataStore()
