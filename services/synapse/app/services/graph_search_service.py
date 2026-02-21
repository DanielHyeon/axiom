import re
import time
from collections import deque
from typing import Any


class GraphSearchService:
    def __init__(self) -> None:
        self._tables = {
            "cases": {
                "description": "케이스 마스터 정보",
                "columns": [
                    {"name": "id", "data_type": "uuid", "description": "케이스 ID", "nullable": False, "is_pk": True, "is_fk": False},
                    {"name": "name", "data_type": "text", "description": "케이스명", "nullable": False, "is_pk": False, "is_fk": False},
                ],
            },
            "processes": {
                "description": "프로세스 실행 내역",
                "columns": [
                    {"name": "id", "data_type": "uuid", "description": "프로세스 ID", "nullable": False, "is_pk": True, "is_fk": False},
                    {"name": "case_id", "data_type": "uuid", "description": "케이스 ID", "nullable": False, "is_pk": False, "is_fk": True},
                    {"name": "org_id", "data_type": "uuid", "description": "조직 ID", "nullable": False, "is_pk": False, "is_fk": True},
                    {"name": "efficiency_rate", "data_type": "numeric", "description": "효율성 비율", "nullable": True, "is_pk": False, "is_fk": False},
                ],
            },
            "organizations": {
                "description": "조직/이해관계자 정보",
                "columns": [
                    {"name": "id", "data_type": "uuid", "description": "조직 ID", "nullable": False, "is_pk": True, "is_fk": False},
                    {"name": "name", "data_type": "text", "description": "조직명", "nullable": False, "is_pk": False, "is_fk": False},
                ],
            },
            "metrics": {
                "description": "프로세스 지표 정보",
                "columns": [
                    {"name": "id", "data_type": "uuid", "description": "지표 ID", "nullable": False, "is_pk": True, "is_fk": False},
                    {"name": "case_id", "data_type": "uuid", "description": "케이스 ID", "nullable": False, "is_pk": False, "is_fk": True},
                    {"name": "value", "data_type": "numeric", "description": "지표 값", "nullable": True, "is_pk": False, "is_fk": False},
                ],
            },
        }
        self._fk_edges = [
            ("processes", "cases", {"from_column": "case_id", "to_column": "id"}),
            ("processes", "organizations", {"from_column": "org_id", "to_column": "id"}),
            ("metrics", "cases", {"from_column": "case_id", "to_column": "id"}),
        ]
        self._similar_queries = [
            {
                "question": "조직별 프로세스 효율성을 조회하시오",
                "sql": "SELECT o.name, p.efficiency_rate FROM processes p JOIN organizations o ON p.org_id = o.id",
                "score": 0.88,
                "verified": True,
            }
        ]
        self._value_mappings = [
            {
                "column": "processes.process_type",
                "mappings": {"collection": "데이터 수집", "analysis": "프로세스 분석", "optimization": "최적화", "execution": "실행"},
            }
        ]

    def _tokens(self, text: str) -> set[str]:
        return {t for t in re.split(r"[^a-zA-Z0-9가-힣_]+", (text or "").lower()) if t}

    def _score(self, query: str, candidate: str) -> float:
        q = self._tokens(query)
        if not q:
            return 0.0
        c = self._tokens(candidate)
        overlap = len(q.intersection(c))
        return overlap / max(len(q), 1)

    def vector_search(self, query: str, target: str = "all", top_k: int = 5, min_score: float = 0.7) -> dict[str, Any]:
        started = time.perf_counter()
        safe_target = target if target in {"table", "column", "query", "all"} else "all"
        safe_top_k = max(1, min(top_k, 50))
        safe_min = min(max(min_score, 0.0), 1.0)

        results: list[dict[str, Any]] = []
        for table_name, meta in self._tables.items():
            table_text = f"{table_name} {meta['description']}"
            table_score = self._score(query, table_text)
            if table_score >= safe_min and safe_target in {"table", "all"}:
                results.append({"node_type": "Table", "name": table_name, "description": meta["description"], "score": round(table_score, 2)})
            if safe_target in {"column", "all"}:
                for column in meta["columns"]:
                    col_text = f"{table_name} {column['name']} {column['description']}"
                    col_score = self._score(query, col_text)
                    if col_score >= safe_min:
                        results.append(
                            {
                                "node_type": "Column",
                                "name": f"{table_name}.{column['name']}",
                                "description": column["description"],
                                "score": round(col_score, 2),
                            }
                        )
        if safe_target in {"query", "all"}:
            for item in self._similar_queries:
                q_score = self._score(query, item["question"])
                if q_score >= safe_min:
                    results.append({"node_type": "Query", "name": item["question"], "description": item["sql"], "score": round(q_score, 2)})

        results.sort(key=lambda x: x["score"], reverse=True)
        results = results[:safe_top_k]
        elapsed = int((time.perf_counter() - started) * 1000)
        return {"results": results, "total": len(results), "search_time_ms": max(1, elapsed)}

    def fk_path(self, start_table: str, max_hops: int = 3, direction: str = "both") -> dict[str, Any]:
        if start_table not in self._tables:
            raise ValueError("start_table not found")
        safe_hops = max(1, min(max_hops, 5))
        safe_direction = direction if direction in {"out", "in", "both"} else "both"

        adjacency: dict[str, list[tuple[str, dict[str, Any], str]]] = {}
        for src, dst, join in self._fk_edges:
            adjacency.setdefault(src, []).append((dst, join, "out"))
            adjacency.setdefault(dst, []).append((src, {"from_column": join["to_column"], "to_column": join["from_column"]}, "in"))

        queue = deque([(start_table, [start_table], [])])
        visited = {start_table}
        related: list[dict[str, Any]] = []
        while queue:
            table, path, joins = queue.popleft()
            hop = len(path) - 1
            if hop > safe_hops:
                continue
            if hop > 0:
                related.append({"name": table, "description": self._tables[table]["description"], "hop_distance": hop, "join_path": joins})
            for nxt, join, dir_kind in adjacency.get(table, []):
                if safe_direction == "out" and dir_kind != "out":
                    continue
                if safe_direction == "in" and dir_kind != "in":
                    continue
                if nxt in visited:
                    continue
                visited.add(nxt)
                queue.append(
                    (
                        nxt,
                        [*path, nxt],
                        [
                            *joins,
                            {
                                "from_table": table,
                                "from_column": join["from_column"],
                                "to_table": nxt,
                                "to_column": join["to_column"],
                                "relation": "FK_TO",
                            },
                        ],
                    )
                )
        return {"start_table": start_table, "related_tables": related}

    def search(self, payload: dict[str, Any]) -> dict[str, Any]:
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
        if vector_enabled:
            min_score = float(vector_opt.get("min_score", 0.1))
            vs = self.vector_search(query=query, target="table", top_k=int(vector_opt.get("table_top_k", 5)), min_score=min_score)
            for item in vs["results"]:
                table_name = item["name"]
                vector_tables.append(
                    {
                        "name": table_name,
                        "description": self._tables[table_name]["description"],
                        "score": item["score"],
                        "match_type": "vector",
                        "columns": [
                            {
                                **col,
                                "score": round(self._score(query, f"{table_name} {col['name']} {col['description']}"), 2),
                            }
                            for col in self._tables[table_name]["columns"][: int(vector_opt.get("column_top_k", 10))]
                        ],
                    }
                )

        fk_related: list[dict[str, Any]] = []
        if fk_enabled:
            max_hops = int(fk_opt.get("max_hops", 3))
            seeds = [item["name"] for item in vector_tables] or ["processes"]
            seen = set()
            for seed in seeds:
                out = self.fk_path(start_table=seed, max_hops=max_hops)
                for tbl in out["related_tables"]:
                    if tbl["name"] in seen:
                        continue
                    seen.add(tbl["name"])
                    fk_related.append(tbl)

        elapsed = int((time.perf_counter() - started) * 1000)
        include_value_mappings = bool(options.get("include_value_mappings", True))
        return {
            "query": query,
            "search_time_ms": max(1, elapsed),
            "tables": {"vector_matched": vector_tables, "fk_related": fk_related},
            "similar_queries": self._similar_queries if vector_enabled else [],
            "value_mappings": self._value_mappings if include_value_mappings else [],
        }

    def tables_related(self, table_name: str, max_hops: int = 2) -> dict[str, Any]:
        out = self.fk_path(start_table=table_name, max_hops=max_hops)
        return {"table": table_name, "related": out["related_tables"], "total": len(out["related_tables"])}

    def stats(self) -> dict[str, Any]:
        return {
            "table_count": len(self._tables),
            "fk_edge_count": len(self._fk_edges),
            "sample_queries_count": len(self._similar_queries),
            "value_mappings_count": len(self._value_mappings),
        }

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


graph_search_service = GraphSearchService()
