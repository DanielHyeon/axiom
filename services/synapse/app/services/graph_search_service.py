import re
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import structlog

from app.core.neo4j_client import neo4j_client

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# O3: Ontology Context v2 data contracts
# ---------------------------------------------------------------------------

_REL_ALLOWLIST = frozenset({
    "BELONGS_TO", "HAS_MEASURE", "HAS_KPI", "IMPACTS",
    "DEPENDS_ON", "INTERACTS_WITH", "FK_TO", "MAPS_TO", "DERIVED_FROM",
})

_SCORE_THRESHOLD = 0.5


@dataclass
class SearchCandidate:
    element_id: str
    labels: list[str]
    name: str
    score: float
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class ContextTermMapping:
    term: str
    matched_node: str
    layer: str
    confidence: float
    tables: list[str] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)


@dataclass
class OntologyContextV1:
    version: str = "1"
    term_mappings: list[ContextTermMapping] = field(default_factory=list)
    preferred_tables: list[str] = field(default_factory=list)
    preferred_columns: list[str] = field(default_factory=list)


class GraphSearchService:
    def __init__(self) -> None:
        self._neo4j = neo4j_client

    async def add_query_cache(self, question: str, sql: str, confidence: float, datasource_id: str = "") -> None:
        """Oracle reflect_cache 호출 시 Query 노드로 Neo4j MERGE."""
        question = (question or "").strip()
        sql = (sql or "").strip()
        if not question or not sql:
            return
        confidence = max(0.0, min(1.0, float(confidence)))
        try:
            await self._read(
                """MERGE (q:Query {question: $question})
                SET q.sql = $sql, q.score = $confidence, q.verified = true,
                    q.datasource_id = $ds, q.updated_at = datetime()""",
                {"question": question, "sql": sql, "confidence": round(confidence, 2), "ds": datasource_id or ""},
            )
        except Exception as exc:
            logger.warning("add_query_cache_error", error=str(exc))

    async def vector_search(self, query: str, target: str = "all", top_k: int = 5, min_score: float = 0.7) -> dict[str, Any]:
        started = time.perf_counter()
        safe_target = target if target in {"table", "column", "query", "all"} else "all"
        safe_top_k = max(1, min(top_k, 50))
        safe_min = min(max(min_score, 0.0), 1.0)

        results: list[dict[str, Any]] = []

        # Table / Column via schema_fulltext
        if safe_target in {"table", "column", "all"}:
            try:
                rows = await self._read(
                    """CALL db.index.fulltext.queryNodes('schema_fulltext', $q)
                    YIELD node, score
                    WHERE score >= $min_score
                    RETURN node, score, labels(node) AS labels
                    ORDER BY score DESC LIMIT $limit""",
                    {"q": query, "min_score": safe_min, "limit": safe_top_k * 3},
                )
                for r in rows:
                    node = r["node"]
                    labels = r.get("labels", self._node_labels(node))
                    props = self._node_props(node)
                    name = props.get("name", "")
                    desc = props.get("description", "")
                    sc = round(float(r["score"]), 2)
                    if "Table" in labels and safe_target in {"table", "all"}:
                        results.append({"node_type": "Table", "name": name, "description": desc, "score": sc})
                    elif "Column" in labels and safe_target in {"column", "all"}:
                        tbl = props.get("table_name", "")
                        col_name = f"{tbl}.{name}" if tbl else name
                        results.append({"node_type": "Column", "name": col_name, "description": desc, "score": sc})
            except Exception as exc:
                logger.warning("vector_search_fulltext_error", error=str(exc))

        # Query nodes
        if safe_target in {"query", "all"}:
            try:
                rows = await self._read(
                    """MATCH (q:Query)
                    WHERE q.question IS NOT NULL
                    RETURN q.question AS question, q.sql AS sql, q.score AS score
                    ORDER BY q.score DESC LIMIT $limit""",
                    {"limit": safe_top_k},
                )
                tokens = self._tokens(query)
                for r in rows:
                    q_text = str(r.get("question", ""))
                    q_tokens = self._tokens(q_text)
                    overlap = len(tokens & q_tokens) / max(len(tokens), 1) if tokens else 0.0
                    if overlap >= safe_min:
                        results.append({"node_type": "Query", "name": q_text, "description": str(r.get("sql", "")), "score": round(overlap, 2)})
            except Exception as exc:
                logger.warning("vector_search_query_error", error=str(exc))

        results.sort(key=lambda x: x["score"], reverse=True)
        results = results[:safe_top_k]
        elapsed = int((time.perf_counter() - started) * 1000)
        return {"results": results, "total": len(results), "search_time_ms": max(1, elapsed)}

    async def fk_path(self, start_table: str, max_hops: int = 3, direction: str = "both") -> dict[str, Any]:
        safe_hops = max(1, min(max_hops, 5))
        safe_direction = direction if direction in {"out", "in", "both"} else "both"

        # Verify start table exists
        check = await self._read(
            "MATCH (t:Table {name: $name}) RETURN t.name AS name LIMIT 1",
            {"name": start_table},
        )
        if not check:
            raise ValueError("start_table not found")

        # Build direction-aware Cypher
        if safe_direction == "out":
            rel_pattern = "-[r:FK_TO]->"
        elif safe_direction == "in":
            rel_pattern = "<-[r:FK_TO]-"
        else:
            rel_pattern = "-[r:FK_TO]-"

        try:
            rows = await self._read(
                f"""MATCH (start:Table {{name: $table}})
                MATCH path = (start){rel_pattern}(related:Table)
                WHERE length(path) <= $max_hops
                RETURN DISTINCT related.name AS name, related.description AS description,
                       length(path) AS hop_distance
                ORDER BY hop_distance ASC""",
                {"table": start_table, "max_hops": safe_hops},
            )
        except Exception as exc:
            logger.warning("fk_path_error", error=str(exc))
            rows = []

        related = [
            {"name": str(r["name"]), "description": str(r.get("description", "")), "hop_distance": int(r.get("hop_distance", 1)), "join_path": []}
            for r in rows
        ]
        return {"start_table": start_table, "related_tables": related}

    async def search(self, payload: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        query = str(payload.get("query") or "").strip()
        if not query:
            raise ValueError("query is required")
        options = payload.get("options") if isinstance(payload.get("options"), dict) else {}
        vector_opt = options.get("vector_search") if isinstance(options.get("vector_search"), dict) else {}
        fk_opt = options.get("fk_traversal") if isinstance(options.get("fk_traversal"), dict) else {}

        vector_enabled = bool(vector_opt.get("enabled", True))
        fk_enabled = bool(fk_opt.get("enabled", True))

        vector_tables: list[dict[str, Any]] = []
        similar_queries: list[dict[str, Any]] = []
        if vector_enabled:
            min_score = float(vector_opt.get("min_score", 0.1))
            vs = await self.vector_search(query=query, target="all", top_k=int(vector_opt.get("table_top_k", 10)), min_score=min_score)
            for item in vs["results"]:
                if item["node_type"] == "Table":
                    # Fetch columns for matched tables
                    cols = await self._read(
                        """MATCH (t:Table {name: $name})-[:HAS_COLUMN]->(c:Column)
                        RETURN c.name AS name, c.data_type AS data_type,
                               c.description AS description, c.nullable AS nullable,
                               c.is_pk AS is_pk, c.is_fk AS is_fk
                        LIMIT $limit""",
                        {"name": item["name"], "limit": int(vector_opt.get("column_top_k", 10))},
                    )
                    vector_tables.append({
                        "name": item["name"],
                        "description": item["description"],
                        "score": item["score"],
                        "match_type": "vector",
                        "columns": [dict(c) for c in cols],
                    })
                elif item["node_type"] == "Query":
                    similar_queries.append({
                        "question": item["name"],
                        "sql": item["description"],
                        "score": item["score"],
                        "verified": True,
                    })

        fk_related: list[dict[str, Any]] = []
        if fk_enabled and vector_tables:
            max_hops = int(fk_opt.get("max_hops", 3))
            seen = {t["name"] for t in vector_tables}
            for vt in vector_tables:
                try:
                    out = await self.fk_path(start_table=vt["name"], max_hops=max_hops)
                    for tbl in out["related_tables"]:
                        if tbl["name"] not in seen:
                            seen.add(tbl["name"])
                            fk_related.append(tbl)
                except ValueError:
                    pass

        # Value mappings from Neo4j (Column nodes with value_mappings property)
        value_mappings: list[dict[str, Any]] = []
        include_value_mappings = bool(options.get("include_value_mappings", True))
        if include_value_mappings:
            try:
                rows = await self._read(
                    """MATCH (c:Column) WHERE c.value_mappings IS NOT NULL
                    RETURN c.table_name + '.' + c.name AS column, c.value_mappings AS mappings
                    LIMIT 20""",
                )
                for r in rows:
                    value_mappings.append({"column": str(r.get("column", "")), "mappings": r.get("mappings", {})})
            except Exception:
                pass

        elapsed = int((time.perf_counter() - started) * 1000)
        return {
            "query": query,
            "search_time_ms": max(1, elapsed),
            "tables": {"vector_matched": vector_tables, "fk_related": fk_related},
            "similar_queries": similar_queries if vector_enabled else [],
            "value_mappings": value_mappings,
        }

    async def tables_related(self, table_name: str, max_hops: int = 2) -> dict[str, Any]:
        out = await self.fk_path(start_table=table_name, max_hops=max_hops)
        return {"table": table_name, "related": out["related_tables"], "total": len(out["related_tables"])}

    async def stats(self) -> dict[str, Any]:
        try:
            rows = await self._read(
                """OPTIONAL MATCH (t:Table) WITH count(t) AS tc
                OPTIONAL MATCH ()-[f:FK_TO]->() WITH tc, count(f) AS fc
                OPTIONAL MATCH (q:Query) WITH tc, fc, count(q) AS qc
                RETURN tc AS table_count, fc AS fk_edge_count, qc AS sample_queries_count""",
            )
            if rows:
                r = rows[0]
                return {
                    "table_count": int(r.get("table_count", 0)),
                    "fk_edge_count": int(r.get("fk_edge_count", 0)),
                    "sample_queries_count": int(r.get("sample_queries_count", 0)),
                    "value_mappings_count": 0,
                }
        except Exception as exc:
            logger.warning("stats_error", error=str(exc))
        return {"table_count": 0, "fk_edge_count": 0, "sample_queries_count": 0, "value_mappings_count": 0}

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return {t for t in re.split(r"[^a-zA-Z0-9가-힣_]+", (text or "").lower()) if t}

    def ontology_path(self, payload: dict[str, Any], ontology_nodes: list[dict[str, Any]]) -> dict[str, Any]:
        case_id = payload.get("case_id")
        query = str(payload.get("query") or "").strip().lower()
        max_depth = int(payload.get("max_depth", 4))
        safe_depth = max(1, min(max_depth, 8))
        matched = []
        for node in ontology_nodes:
            text = f"{node.get('id', '')} {node.get('layer', '')} {node.get('labels', [])} {node.get('properties', {})}".lower()
            if not query or query in text:
                matched.append(node)
        matched = matched[:safe_depth]
        paths = []
        for idx in range(len(matched) - 1):
            paths.append({"source_id": matched[idx]["id"], "target_id": matched[idx + 1]["id"], "length": 1})
        return {"case_id": case_id, "paths": paths, "matched_nodes": len(matched)}

    # ------------------------------------------------------------------
    # O3: Async Neo4j context_v2
    # ------------------------------------------------------------------

    async def _read(self, cypher: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        async with self._neo4j.session() as session:
            result = await session.run(cypher, params or {})
            return [dict(record) async for record in result]

    async def _fulltext_candidates(self, query: str, case_id: str) -> list[SearchCandidate]:
        """ontology_fulltext + schema_fulltext 병합, score threshold 적용."""
        candidates: list[SearchCandidate] = []
        seen_ids: set[str] = set()

        # 1) ontology_fulltext (Resource, Process, Measure, KPI)
        try:
            rows = await self._read(
                """CALL db.index.fulltext.queryNodes('ontology_fulltext', $q)
                YIELD node, score
                WHERE score >= $threshold AND node.case_id = $cid
                RETURN node, score ORDER BY score DESC LIMIT 20""",
                {"q": query, "threshold": _SCORE_THRESHOLD, "cid": case_id},
            )
            for r in rows:
                node = r["node"]
                eid = self._safe_element_id(node)
                if eid and eid not in seen_ids:
                    seen_ids.add(eid)
                    candidates.append(SearchCandidate(
                        element_id=eid,
                        labels=self._node_labels(node),
                        name=self._node_props(node).get("name", eid),
                        score=float(r["score"]),
                        properties=self._node_props(node),
                    ))
        except Exception as exc:
            logger.warning("fulltext_ontology_error", error=str(exc))

        # 2) schema_fulltext (Table, Column)
        try:
            rows = await self._read(
                """CALL db.index.fulltext.queryNodes('schema_fulltext', $q)
                YIELD node, score
                WHERE score >= $threshold
                RETURN node, score ORDER BY score DESC LIMIT 20""",
                {"q": query, "threshold": _SCORE_THRESHOLD},
            )
            for r in rows:
                node = r["node"]
                eid = self._safe_element_id(node)
                if eid and eid not in seen_ids:
                    seen_ids.add(eid)
                    candidates.append(SearchCandidate(
                        element_id=eid,
                        labels=self._node_labels(node),
                        name=self._node_props(node).get("name", eid),
                        score=float(r["score"]),
                        properties=self._node_props(node),
                    ))
        except Exception as exc:
            logger.warning("fulltext_schema_error", error=str(exc))

        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates[:15]

    async def _expand_neighbors_limited(self, element_id: str, hops: int = 1) -> list[dict[str, Any]]:
        """1-hop BFS, _REL_ALLOWLIST 관계만 탐색."""
        rel_filter = "|".join(_REL_ALLOWLIST)
        try:
            rows = await self._read(
                f"""MATCH (start) WHERE elementId(start) = $eid
                MATCH (start)-[r:{rel_filter}]-(neighbor)
                RETURN neighbor, type(r) as rel_type LIMIT 50""",
                {"eid": element_id},
            )
            return rows
        except Exception as exc:
            logger.warning("expand_neighbors_error", error=str(exc), element_id=element_id)
            return []

    @staticmethod
    def _extract_tables(neighbors: list[dict[str, Any]]) -> list[str]:
        tables: list[str] = []
        for n in neighbors:
            node = n.get("neighbor")
            if node is None:
                continue
            labels = GraphSearchService._node_labels(node)
            if "Table" in labels:
                name = GraphSearchService._node_props(node).get("name", "")
                if name:
                    tables.append(name)
        return tables

    @staticmethod
    def _extract_columns(neighbors: list[dict[str, Any]]) -> list[str]:
        columns: list[str] = []
        for n in neighbors:
            node = n.get("neighbor")
            if node is None:
                continue
            labels = GraphSearchService._node_labels(node)
            if "Column" in labels:
                name = GraphSearchService._node_props(node).get("name", "")
                if name:
                    columns.append(name)
        return columns

    @staticmethod
    def _build_term_mappings(
        candidates: list[SearchCandidate],
        tables: list[str],
        columns: list[str],
    ) -> list[ContextTermMapping]:
        mappings: list[ContextTermMapping] = []
        for c in candidates:
            layer = ""
            for lbl in c.labels:
                if lbl in {"Resource", "Process", "Measure", "KPI"}:
                    layer = lbl.lower()
                    break
            mappings.append(ContextTermMapping(
                term=c.name,
                matched_node=c.element_id,
                layer=layer or "schema",
                confidence=min(c.score, 1.0),
                tables=list(dict.fromkeys(tables)),
                columns=list(dict.fromkeys(columns)),
            ))
        return mappings

    @staticmethod
    def _safe_element_id(node: Any) -> str:
        if hasattr(node, "element_id"):
            return str(node.element_id)
        if isinstance(node, dict):
            return str(node.get("element_id", node.get("id", "")))
        return ""

    @staticmethod
    def _node_labels(node: Any) -> list[str]:
        if hasattr(node, "labels"):
            return list(node.labels)
        if isinstance(node, dict):
            return list(node.get("labels", []))
        return []

    @staticmethod
    def _node_props(node: Any) -> dict[str, Any]:
        if hasattr(node, "items"):
            return dict(node.items())
        if isinstance(node, dict):
            return node
        return {}

    async def context_v2(self, case_id: str, query: str) -> OntologyContextV1:
        """Neo4j fulltext 기반 ontology context 반환."""
        candidates = await self._fulltext_candidates(query, case_id)
        if not candidates:
            return OntologyContextV1()

        all_tables: list[str] = []
        all_columns: list[str] = []
        for c in candidates:
            neighbors = await self._expand_neighbors_limited(c.element_id, hops=1)
            all_tables.extend(self._extract_tables(neighbors))
            all_columns.extend(self._extract_columns(neighbors))

        term_mappings = self._build_term_mappings(candidates, all_tables, all_columns)
        return OntologyContextV1(
            term_mappings=term_mappings,
            preferred_tables=list(dict.fromkeys(all_tables)),
            preferred_columns=list(dict.fromkeys(all_columns)),
        )


graph_search_service = GraphSearchService()
