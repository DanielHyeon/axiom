"""MetadataGraphService — 메타데이터 그래프 접근 전담 (DDD-P2-05).

Weaver가 직접 Neo4j에 접근하던 메타데이터 카탈로그 연산을
Synapse(Neo4j Primary Owner)로 이관. Weaver는 이 서비스의 API를 사용한다.
"""
from __future__ import annotations

import json
import time
from typing import Any

from app.core.neo4j_client import neo4j_client


def _decode_json(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except Exception:
        return default


class MetadataGraphService:
    """Neo4j 메타데이터 그래프 CRUD. Synapse가 유일한 소유자."""

    async def _read(self, query: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        async with neo4j_client.session() as session:
            result = await session.run(query, params)
            return [dict(record) async for record in result]

    async def _write(self, query: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        return await self._read(query, params)

    # ──── Snapshot ──── #

    async def save_snapshot(self, item: dict[str, Any], tenant_id: str) -> None:
        await self._write(
            """MERGE (s:MetadataSnapshot {tenant_id: $tenant_id, snapshot_id: $snapshot_id})
            SET s.tenant_id=$tenant_id, s.case_id=$case_id, s.datasource=$datasource,
                s.version=$version, s.status=$status, s.description=$description,
                s.created_by=$created_by, s.created_at=$created_at, s.completed_at=$completed_at,
                s.summary_json=$summary_json, s.graph_data_json=$graph_data_json""",
            {"snapshot_id": item["id"], "tenant_id": tenant_id,
             "case_id": item["case_id"], "datasource": item["datasource"],
             "version": item["version"], "status": item["status"],
             "description": item.get("description"), "created_by": item["created_by"],
             "created_at": item["created_at"], "completed_at": item.get("completed_at"),
             "summary_json": json.dumps(item.get("summary", {}), ensure_ascii=True),
             "graph_data_json": json.dumps(item.get("graph_data", {}), ensure_ascii=True)},
        )

    async def list_snapshots(self, case_id: str, datasource: str, tenant_id: str) -> list[dict[str, Any]]:
        rows = await self._read(
            """MATCH (s:MetadataSnapshot {tenant_id:$tenant_id, case_id:$case_id, datasource:$datasource})
            RETURN s ORDER BY s.version DESC""",
            {"tenant_id": tenant_id, "case_id": case_id, "datasource": datasource},
        )
        return [self._snap(r["s"]) for r in rows]

    async def get_snapshot(self, case_id: str, datasource: str, snapshot_id: str, tenant_id: str) -> dict[str, Any] | None:
        rows = await self._read(
            """MATCH (s:MetadataSnapshot {tenant_id:$tenant_id, case_id:$case_id,
            datasource:$datasource, snapshot_id:$snapshot_id}) RETURN s""",
            {"tenant_id": tenant_id, "case_id": case_id, "datasource": datasource, "snapshot_id": snapshot_id},
        )
        return self._snap(rows[0]["s"]) if rows else None

    async def delete_snapshot(self, case_id: str, datasource: str, snapshot_id: str, tenant_id: str) -> bool:
        rows = await self._write(
            """MATCH (s:MetadataSnapshot {tenant_id:$tenant_id, case_id:$case_id,
            datasource:$datasource, snapshot_id:$snapshot_id})
            WITH s, count(s) as c DETACH DELETE s RETURN c""",
            {"tenant_id": tenant_id, "case_id": case_id, "datasource": datasource, "snapshot_id": snapshot_id},
        )
        return bool(rows and int(rows[0]["c"]) > 0)

    # ──── Glossary ──── #

    async def save_glossary_term(self, item: dict[str, Any], tenant_id: str) -> None:
        await self._write(
            """MERGE (g:GlossaryTerm {tenant_id:$tenant_id, term_id:$term_id})
            SET g.tenant_id=$tenant_id, g.term=$term, g.definition=$definition,
                g.synonyms_json=$synonyms_json, g.created_at=$created_at, g.updated_at=$updated_at""",
            {"term_id": item["id"], "tenant_id": tenant_id,
             "term": item["term"], "definition": item["definition"],
             "synonyms_json": json.dumps(item.get("synonyms", []), ensure_ascii=True),
             "created_at": item["created_at"], "updated_at": item["updated_at"]},
        )

    async def list_glossary_terms(self, tenant_id: str) -> list[dict[str, Any]]:
        rows = await self._read(
            "MATCH (g:GlossaryTerm {tenant_id:$tenant_id}) RETURN g ORDER BY g.created_at DESC",
            {"tenant_id": tenant_id},
        )
        return [self._gloss(r["g"]) for r in rows]

    async def get_glossary_term(self, term_id: str, tenant_id: str) -> dict[str, Any] | None:
        rows = await self._read(
            "MATCH (g:GlossaryTerm {tenant_id:$tenant_id, term_id:$term_id}) RETURN g",
            {"tenant_id": tenant_id, "term_id": term_id},
        )
        return self._gloss(rows[0]["g"]) if rows else None

    async def delete_glossary_term(self, term_id: str, tenant_id: str) -> bool:
        rows = await self._write(
            """MATCH (g:GlossaryTerm {tenant_id:$tenant_id, term_id:$term_id})
            WITH g, count(g) as c DETACH DELETE g RETURN c""",
            {"tenant_id": tenant_id, "term_id": term_id},
        )
        return bool(rows and int(rows[0]["c"]) > 0)

    async def search_glossary_terms(self, q: str, tenant_id: str) -> list[dict[str, Any]]:
        rows = await self._read(
            """MATCH (g:GlossaryTerm {tenant_id:$tenant_id})
            WHERE toLower(g.term) CONTAINS toLower($q) OR toLower(g.definition) CONTAINS toLower($q)
            RETURN g ORDER BY g.created_at DESC""",
            {"tenant_id": tenant_id, "q": q},
        )
        return [self._gloss(r["g"]) for r in rows]

    # ──── Entity Tags ──── #

    async def add_entity_tag(self, entity_key: str, entity_type: str, metadata: dict[str, Any], tag: str) -> list[str]:
        rows = await self._write(
            """MERGE (e:TaggedEntity {entity_key:$entity_key})
            ON CREATE SET e.entity_type=$entity_type, e.tenant_id=$tenant_id,
                e.case_id=$case_id, e.datasource=$datasource,
                e.table_name=$table_name, e.column_name=$column_name, e.tags_json="[]"
            RETURN e.tags_json as tags_json""",
            {"entity_key": entity_key, "entity_type": entity_type,
             "tenant_id": metadata.get("tenant_id"), "case_id": metadata.get("case_id"),
             "datasource": metadata.get("datasource"), "table_name": metadata.get("table_name"),
             "column_name": metadata.get("column_name")},
        )
        tags = _decode_json(rows[0]["tags_json"], [])
        if tag not in tags:
            tags.append(tag)
        await self._write(
            "MATCH (e:TaggedEntity {entity_key:$entity_key}) SET e.tags_json=$tags_json",
            {"entity_key": entity_key, "tags_json": json.dumps(tags, ensure_ascii=True)},
        )
        return sorted(tags)

    async def list_entity_tags(self, entity_key: str) -> list[str]:
        rows = await self._read(
            "MATCH (e:TaggedEntity {entity_key:$entity_key}) RETURN e.tags_json as tags_json",
            {"entity_key": entity_key},
        )
        return sorted(_decode_json(rows[0]["tags_json"], [])) if rows else []

    async def remove_entity_tag(self, entity_key: str, tag: str) -> bool:
        rows = await self._read(
            "MATCH (e:TaggedEntity {entity_key:$entity_key}) RETURN e.tags_json as tags_json",
            {"entity_key": entity_key},
        )
        if not rows:
            return False
        tags = _decode_json(rows[0]["tags_json"], [])
        if tag in tags:
            tags.remove(tag)
            await self._write(
                "MATCH (e:TaggedEntity {entity_key:$entity_key}) SET e.tags_json=$tags_json",
                {"entity_key": entity_key, "tags_json": json.dumps(tags, ensure_ascii=True)},
            )
        return True

    async def entities_by_tag(self, tag: str, tenant_id: str) -> list[dict[str, Any]]:
        rows = await self._read(
            "MATCH (e:TaggedEntity {tenant_id:$tenant_id}) RETURN e",
            {"tenant_id": tenant_id},
        )
        results = []
        for row in rows:
            node = row["e"]
            tags = _decode_json(node.get("tags_json"), [])
            if tag in tags:
                results.append({"entity_type": node.get("entity_type"), "case_id": node.get("case_id"),
                                "datasource": node.get("datasource"), "table": node.get("table_name"),
                                "column": node.get("column_name")})
        return results

    # ──── Datasource ──── #

    async def upsert_datasource(self, name: str, engine: str, tenant_id: str) -> None:
        await self._write(
            "MERGE (d:DataSource {tenant_id:$tenant_id, name:$name}) SET d.tenant_id=$tenant_id, d.engine=$engine",
            {"tenant_id": tenant_id, "name": name, "engine": engine},
        )

    async def delete_datasource(self, name: str, tenant_id: str) -> None:
        await self._write(
            "MATCH (d:DataSource {tenant_id:$tenant_id, name:$name}) DETACH DELETE d",
            {"tenant_id": tenant_id, "name": name},
        )

    async def save_extracted_catalog(
        self, tenant_id: str, datasource_name: str,
        catalog: dict[str, dict[str, list[dict[str, Any]]]],
        engine: str = "postgresql", *, foreign_keys: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        fk_list = foreign_keys or []
        start = time.perf_counter()
        tid = tenant_id or ""
        for q in [
            "MATCH (s:Schema {tenant_id:$tid, datasource_name:$ds})-[:HAS_TABLE]->(t)-[:HAS_COLUMN]->(c) DETACH DELETE c",
            "MATCH (s:Schema {tenant_id:$tid, datasource_name:$ds})-[:HAS_TABLE]->(t) DETACH DELETE t",
            "MATCH (s:Schema {tenant_id:$tid, datasource_name:$ds}) DETACH DELETE s",
        ]:
            await self._write(q, {"tid": tid, "ds": datasource_name})
        await self._write(
            "MERGE (d:DataSource {tenant_id:$tid, name:$ds}) SET d.engine=$engine, d.last_extracted=datetime()",
            {"tid": tid, "ds": datasource_name, "engine": engine},
        )
        nodes, rels = 0, 0
        for schema_name, tables in catalog.items():
            if not isinstance(tables, dict):
                continue
            sn = str(schema_name).strip()
            if not sn:
                continue
            await self._write(
                """MATCH (d:DataSource {tenant_id:$tid, name:$ds})
                MERGE (s:Schema {tenant_id:$tid, datasource_name:$ds, name:$sn}) MERGE (d)-[:HAS_SCHEMA]->(s)""",
                {"tid": tid, "ds": datasource_name, "sn": sn},
            )
            nodes += 1; rels += 1
            for tbl_name, columns in tables.items():
                if not isinstance(columns, list):
                    continue
                tn = str(tbl_name).strip()
                if not tn:
                    continue
                await self._write(
                    """MATCH (s:Schema {tenant_id:$tid, datasource_name:$ds, name:$sn})
                    MERGE (t:Table {tenant_id:$tid, datasource_name:$ds, schema_name:$sn, name:$tn})
                    MERGE (s)-[:HAS_TABLE]->(t)""",
                    {"tid": tid, "ds": datasource_name, "sn": sn, "tn": tn},
                )
                nodes += 1; rels += 1
                for col in columns:
                    if not isinstance(col, dict):
                        continue
                    cn = str(col.get("name") or "").strip()
                    if not cn:
                        continue
                    await self._write(
                        """MATCH (t:Table {tenant_id:$tid, datasource_name:$ds, schema_name:$sn, name:$tn})
                        MERGE (c:Column {tenant_id:$tid, datasource_name:$ds, schema_name:$sn, table_name:$tn, name:$cn})
                        SET c.dtype=$dtype, c.nullable=$nullable MERGE (t)-[:HAS_COLUMN]->(c)""",
                        {"tid": tid, "ds": datasource_name, "sn": sn, "tn": tn, "cn": cn,
                         "dtype": str(col.get("data_type") or col.get("type") or "string"),
                         "nullable": bool(col.get("nullable", True))},
                    )
                    nodes += 1; rels += 1
        for fk in fk_list:
            if not isinstance(fk, dict):
                continue
            ss, st, sc = (str(fk.get(k) or "").strip() for k in ("source_schema", "source_table", "source_column"))
            ts, tt, tc = (str(fk.get(k) or "").strip() for k in ("target_schema", "target_table", "target_column"))
            cn = str(fk.get("constraint_name") or "").strip() or "fk"
            if not all([ss, st, sc, ts, tt, tc]):
                continue
            try:
                await self._write(
                    """MATCH (sc:Column {tenant_id:$tid, datasource_name:$ds, schema_name:$ss, table_name:$st, name:$sc_})
                    MATCH (tc:Column {tenant_id:$tid, datasource_name:$ds, schema_name:$ts, table_name:$tt, name:$tc_})
                    MERGE (sc)-[r:FK_TO]->(tc) SET r.constraint_name=$cn""",
                    {"tid": tid, "ds": datasource_name, "ss": ss, "st": st, "sc_": sc,
                     "ts": ts, "tt": tt, "tc_": tc, "cn": cn},
                )
                rels += 1
                await self._write(
                    """MATCH (st:Table {tenant_id:$tid, datasource_name:$ds, schema_name:$ss, name:$st_})
                    MATCH (tt:Table {tenant_id:$tid, datasource_name:$ds, schema_name:$ts, name:$tt_})
                    MERGE (st)-[:FK_TO_TABLE]->(tt)""",
                    {"tid": tid, "ds": datasource_name, "ss": ss, "st_": st, "ts": ts, "tt_": tt},
                )
                rels += 1
            except Exception:
                pass
        return {"nodes_created": nodes, "relationships_created": rels,
                "duration_ms": int((time.perf_counter() - start) * 1000)}

    # ──── Concept Mapping ──── #

    async def create_concept_mapping(self, source_id: str, target_id: str, rel_type: str, tenant_id: str) -> dict[str, Any]:
        valid_types = {"MAPS_TO", "DERIVED_FROM", "DEFINES"}
        safe_type = rel_type if rel_type in valid_types else "MAPS_TO"
        rows = await self._write(
            f"""MATCH (a) WHERE a.id = $src
            MATCH (b:Table) WHERE b.name = $tgt AND b.tenant_id = $tid
            CREATE (a)-[r:{safe_type} {{created_at: datetime(), tenant_id: $tid}}]->(b)
            RETURN id(r) as rel_id, a.id as source_id, b.name as target_id, type(r) as rel_type""",
            {"src": source_id, "tgt": target_id, "tid": tenant_id},
        )
        if not rows:
            return {}
        r = rows[0]
        return {"rel_id": str(r["rel_id"]), "source_id": r["source_id"],
                "target_id": r["target_id"], "rel_type": r["rel_type"]}

    async def list_concept_mappings(self, case_id: str, tenant_id: str) -> list[dict[str, Any]]:
        rows = await self._read(
            """MATCH (o)-[r:MAPS_TO|DERIVED_FROM|DEFINES]->(t:Table)
            WHERE o.case_id = $cid AND t.tenant_id = $tid
            RETURN id(r) as rel_id, o.id as source_id, labels(o)[0] as source_layer,
                   properties(o) as source_props, t.name as target_table,
                   t.schema_name as target_schema, type(r) as rel_type, r.created_at as created_at""",
            {"cid": case_id, "tid": tenant_id},
        )
        return [{"rel_id": str(r["rel_id"]), "source_id": r["source_id"],
                 "source_layer": r["source_layer"],
                 "source_name": (r["source_props"] or {}).get("name", r["source_id"]),
                 "target_table": r["target_table"], "target_schema": r.get("target_schema"),
                 "rel_type": r.get("rel_type", "MAPS_TO"),
                 "created_at": str(r.get("created_at", ""))} for r in rows]

    async def delete_concept_mapping(self, rel_id: str) -> bool:
        rows = await self._write(
            "MATCH ()-[r]->() WHERE id(r) = toInteger($rid) DELETE r RETURN count(r) as c",
            {"rid": rel_id},
        )
        return bool(rows and int(rows[0]["c"]) > 0)

    async def list_schema_entities(self, tenant_id: str, datasource: str | None = None) -> list[dict[str, Any]]:
        if datasource:
            rows = await self._read(
                "MATCH (t:Table {tenant_id:$tid, datasource_name:$ds}) RETURN t ORDER BY t.name",
                {"tid": tenant_id, "ds": datasource},
            )
        else:
            rows = await self._read(
                "MATCH (t:Table {tenant_id:$tid}) RETURN t ORDER BY t.name",
                {"tid": tenant_id},
            )
        return [{"name": r["t"].get("name"), "schema": r["t"].get("schema_name"),
                 "datasource": r["t"].get("datasource_name")} for r in rows]

    async def suggest_mappings(self, query: str, tenant_id: str) -> list[dict[str, Any]]:
        rows = await self._read(
            """CALL db.index.fulltext.queryNodes('schema_fulltext', $q)
            YIELD node, score
            WHERE node.tenant_id = $tid
            RETURN node.name as name, labels(node)[0] as node_type,
                   node.schema_name as schema_name, node.datasource_name as datasource,
                   score ORDER BY score DESC LIMIT 10""",
            {"q": query, "tid": tenant_id},
        )
        return [{"name": r["name"], "type": r["node_type"], "schema": r.get("schema_name"),
                 "datasource": r.get("datasource"), "score": float(r["score"])} for r in rows]

    # ──── Stats ──── #

    async def stats(self, tenant_id: str) -> dict[str, int]:
        rows = await self._read(
            """OPTIONAL MATCH (d:DataSource {tenant_id:$tid}) WITH count(d) AS datasources
            OPTIONAL MATCH (g:GlossaryTerm {tenant_id:$tid}) WITH datasources, count(g) AS glossary_terms
            OPTIONAL MATCH (s:MetadataSnapshot {tenant_id:$tid})
            RETURN datasources, glossary_terms, count(s) AS snapshots""",
            {"tid": tenant_id},
        )
        if not rows:
            return {"datasources": 0, "glossary_terms": 0, "snapshots": 0}
        r = rows[0]
        return {"datasources": int(r.get("datasources", 0)),
                "glossary_terms": int(r.get("glossary_terms", 0)),
                "snapshots": int(r.get("snapshots", 0))}

    # ──── Helpers ──── #

    @staticmethod
    def _snap(node: Any) -> dict[str, Any]:
        return {"id": node.get("snapshot_id"), "tenant_id": node.get("tenant_id"),
                "datasource": node.get("datasource"), "case_id": node.get("case_id"),
                "version": int(node.get("version", 0)), "status": node.get("status"),
                "description": node.get("description"), "created_by": node.get("created_by"),
                "created_at": node.get("created_at"), "completed_at": node.get("completed_at"),
                "summary": _decode_json(node.get("summary_json"), {}),
                "graph_data": _decode_json(node.get("graph_data_json"), {})}

    @staticmethod
    def _gloss(node: Any) -> dict[str, Any]:
        return {"id": node.get("term_id"), "tenant_id": node.get("tenant_id"),
                "term": node.get("term"), "definition": node.get("definition"),
                "synonyms": _decode_json(node.get("synonyms_json"), []),
                "created_at": node.get("created_at"), "updated_at": node.get("updated_at")}


metadata_graph_service = MetadataGraphService()
