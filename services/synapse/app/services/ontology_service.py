import re
import uuid
import asyncio
from collections import deque
from datetime import datetime, timezone
from typing import Any

import structlog

logger = structlog.get_logger()
_ALNUM_UNDERSCORE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _safe_graph_name(value: str, default: str) -> str:
    candidate = (value or "").strip()
    return candidate if _ALNUM_UNDERSCORE.match(candidate) else default


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class OntologyService:
    def __init__(self, neo4j_client):
        self._neo4j = neo4j_client
        self._case_nodes: dict[str, dict[str, dict[str, Any]]] = {}
        self._case_relations: dict[str, dict[str, dict[str, Any]]] = {}
        self._node_case_index: dict[str, str] = {}
        self._relation_case_index: dict[str, str] = {}

    def clear(self) -> None:
        self._case_nodes.clear()
        self._case_relations.clear()
        self._node_case_index.clear()
        self._relation_case_index.clear()

    def _nodes(self, case_id: str) -> dict[str, dict[str, Any]]:
        return self._case_nodes.setdefault(case_id, {})

    def _relations(self, case_id: str) -> dict[str, dict[str, Any]]:
        return self._case_relations.setdefault(case_id, {})

    async def _sync_node_to_neo4j(self, case_id: str, node: dict[str, Any]) -> None:
        label = _safe_graph_name(str(node.get("labels", ["Entity"])[0]), "Entity")
        properties = dict(node.get("properties") or {})
        try:
            async with self._neo4j.session() as session:
                await asyncio.wait_for(
                    session.run(
                    f"""
                    MERGE (n:{label} {{case_id: $case_id, node_id: $node_id}})
                    SET n += $properties
                    """,
                    case_id=case_id,
                    node_id=node["id"],
                    properties=properties,
                )
                , timeout=0.8)
        except Exception as exc:
            logger.warning("ontology_node_sync_failed", error=str(exc), case_id=case_id, node_id=node["id"])

    async def _sync_relation_to_neo4j(self, case_id: str, rel: dict[str, Any]) -> None:
        rel_type = _safe_graph_name(str(rel.get("type") or "RELATED_TO"), "RELATED_TO")
        properties = dict(rel.get("properties") or {})
        try:
            async with self._neo4j.session() as session:
                await asyncio.wait_for(
                    session.run(
                    f"""
                    MATCH (a {{case_id: $case_id, node_id: $source_id}})
                    MATCH (b {{case_id: $case_id, node_id: $target_id}})
                    MERGE (a)-[r:{rel_type} {{id: $relation_id}}]->(b)
                    SET r += $properties
                    """,
                    case_id=case_id,
                    source_id=rel["source_id"],
                    target_id=rel["target_id"],
                    relation_id=rel["id"],
                    properties=properties,
                )
                , timeout=0.8)
        except Exception as exc:
            logger.warning("ontology_relation_sync_failed", error=str(exc), case_id=case_id, relation_id=rel["id"])

    def _normalize_node(self, tenant_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        case_id = str(payload.get("case_id") or "").strip()
        node_id = str(payload.get("id") or payload.get("node_id") or f"node-{uuid.uuid4()}").strip()
        if not case_id:
            raise ValueError("case_id is required")
        if not node_id:
            raise ValueError("node_id is required")
        layer = str(payload.get("layer") or "resource").lower()
        labels = payload.get("labels") if isinstance(payload.get("labels"), list) else [layer.capitalize()]
        properties = payload.get("properties") if isinstance(payload.get("properties"), dict) else {}
        properties.setdefault("updated_at", _iso_now())
        properties.setdefault("verified", False)
        properties.setdefault("tenant_id", tenant_id)
        return {
            "id": node_id,
            "case_id": case_id,
            "layer": layer,
            "labels": [str(item) for item in labels if str(item).strip()],
            "properties": properties,
        }

    def _normalize_relation(self, tenant_id: str, payload: dict[str, Any], relation_id: str | None = None) -> dict[str, Any]:
        case_id = str(payload.get("case_id") or "").strip()
        source_id = str(payload.get("source_id") or payload.get("from") or payload.get("source") or "").strip()
        target_id = str(payload.get("target_id") or payload.get("to") or payload.get("target") or "").strip()
        rel_type = _safe_graph_name(str(payload.get("type") or "RELATED_TO"), "RELATED_TO")
        if not case_id:
            raise ValueError("case_id is required")
        if not source_id or not target_id:
            raise ValueError("source_id and target_id are required")
        properties = payload.get("properties") if isinstance(payload.get("properties"), dict) else {}
        properties.setdefault("updated_at", _iso_now())
        properties.setdefault("tenant_id", tenant_id)
        return {
            "id": relation_id or str(payload.get("id") or f"rel-{uuid.uuid4()}"),
            "case_id": case_id,
            "source_id": source_id,
            "target_id": target_id,
            "type": rel_type,
            "properties": properties,
        }

    async def extract_ontology(self, tenant_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        case_id = str(payload.get("case_id") or "").strip()
        entities = payload.get("entities") or []
        relations = payload.get("relations") or []
        if not case_id:
            raise ValueError("case_id is required")
        if not isinstance(entities, list) or not isinstance(relations, list):
            raise ValueError("entities/relations must be list")

        task_id = f"onto-{uuid.uuid4()}"
        created_nodes = 0
        created_relations = 0

        for entity in entities:
            if not isinstance(entity, dict):
                continue
            node_payload = {
                "id": entity.get("id") or entity.get("node_id"),
                "case_id": case_id,
                "layer": entity.get("layer") or entity.get("label") or "resource",
                "labels": [entity.get("label")] if entity.get("label") else entity.get("labels"),
                "properties": entity.get("properties") or {},
            }
            node = await self.create_node(tenant_id=tenant_id, payload=node_payload)
            if node:
                created_nodes += 1

        for rel in relations:
            if not isinstance(rel, dict):
                continue
            rel_payload = {
                "case_id": case_id,
                "source_id": rel.get("source_id") or rel.get("from") or rel.get("source"),
                "target_id": rel.get("target_id") or rel.get("to") or rel.get("target"),
                "type": rel.get("type") or "RELATED_TO",
                "properties": rel.get("properties") or {},
            }
            relation = await self.create_relation(tenant_id=tenant_id, payload=rel_payload)
            if relation:
                created_relations += 1

        return {
            "task_id": task_id,
            "status": "completed",
            "case_id": case_id,
            "stats": {"nodes": created_nodes, "relations": created_relations},
        }

    async def create_node(self, tenant_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        node = self._normalize_node(tenant_id=tenant_id, payload=payload)
        nodes = self._nodes(node["case_id"])
        existing = nodes.get(node["id"])
        if existing:
            existing["layer"] = node["layer"]
            existing["labels"] = node["labels"]
            existing["properties"].update(node["properties"])
            await self._sync_node_to_neo4j(case_id=node["case_id"], node=existing)
            return existing
        nodes[node["id"]] = node
        self._node_case_index[node["id"]] = node["case_id"]
        await self._sync_node_to_neo4j(case_id=node["case_id"], node=node)
        return node

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        case_id = self._node_case_index.get(node_id)
        if not case_id:
            return None
        return self._nodes(case_id).get(node_id)

    async def update_node(self, tenant_id: str, node_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        current = self.get_node(node_id)
        if not current:
            raise KeyError("node not found")
        merged = {
            "id": node_id,
            "case_id": current["case_id"],
            "layer": payload.get("layer", current["layer"]),
            "labels": payload.get("labels", current["labels"]),
            "properties": {**current["properties"], **(payload.get("properties") or {})},
        }
        node = self._normalize_node(tenant_id=tenant_id, payload=merged)
        self._nodes(current["case_id"])[node_id] = node
        await self._sync_node_to_neo4j(case_id=current["case_id"], node=node)
        return node

    async def delete_node(self, node_id: str) -> dict[str, Any]:
        case_id = self._node_case_index.get(node_id)
        if not case_id:
            raise KeyError("node not found")
        nodes = self._nodes(case_id)
        del nodes[node_id]
        del self._node_case_index[node_id]
        relations = self._relations(case_id)
        stale_ids = [
            rel_id
            for rel_id, rel in relations.items()
            if rel["source_id"] == node_id or rel["target_id"] == node_id
        ]
        for rel_id in stale_ids:
            del relations[rel_id]
            self._relation_case_index.pop(rel_id, None)
        return {"deleted": True, "node_id": node_id, "deleted_relations": len(stale_ids)}

    async def create_relation(self, tenant_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        relation = self._normalize_relation(tenant_id=tenant_id, payload=payload)
        nodes = self._nodes(relation["case_id"])
        if relation["source_id"] not in nodes or relation["target_id"] not in nodes:
            raise ValueError("source/target node not found in case")
        relations = self._relations(relation["case_id"])
        relations[relation["id"]] = relation
        self._relation_case_index[relation["id"]] = relation["case_id"]
        await self._sync_relation_to_neo4j(case_id=relation["case_id"], rel=relation)
        return relation

    async def delete_relation(self, relation_id: str) -> dict[str, Any]:
        case_id = self._relation_case_index.get(relation_id)
        if not case_id:
            raise KeyError("relation not found")
        relations = self._relations(case_id)
        del relations[relation_id]
        del self._relation_case_index[relation_id]
        return {"deleted": True, "relation_id": relation_id}

    async def get_case_ontology(
        self,
        case_id: str,
        layer: str = "all",
        include_relations: bool = True,
        verified_only: bool = False,
        limit: int = 500,
        offset: int = 0,
    ) -> dict[str, Any]:
        nodes = list(self._nodes(case_id).values())
        if layer != "all":
            nodes = [n for n in nodes if n["layer"] == layer]
        if verified_only:
            nodes = [n for n in nodes if bool(n["properties"].get("verified", False))]

        total = len(nodes)
        safe_limit = min(max(limit, 1), 1000)
        safe_offset = max(offset, 0)
        paged_nodes = nodes[safe_offset : safe_offset + safe_limit]
        node_ids = {n["id"] for n in paged_nodes}

        rel_items: list[dict[str, Any]] = []
        if include_relations:
            for rel in self._relations(case_id).values():
                if rel["source_id"] in node_ids and rel["target_id"] in node_ids:
                    rel_items.append(rel)

        by_layer: dict[str, int] = {}
        for item in nodes:
            by_layer[item["layer"]] = by_layer.get(item["layer"], 0) + 1

        return {
            "case_id": case_id,
            "summary": {
                "total_nodes": len(nodes),
                "total_relations": len(rel_items),
                "by_layer": by_layer,
            },
            "nodes": paged_nodes,
            "relations": rel_items,
            "pagination": {
                "total": total,
                "limit": safe_limit,
                "offset": safe_offset,
                "has_more": (safe_offset + safe_limit) < total,
            },
        }

    async def get_case_summary(self, case_id: str) -> dict[str, Any]:
        nodes = list(self._nodes(case_id).values())
        relations = list(self._relations(case_id).values())

        node_counts: dict[str, dict[str, Any]] = {}
        verification = {"verified": 0, "unverified": 0, "pending_review": 0}
        for node in nodes:
            layer = node["layer"]
            node_counts.setdefault(layer, {"total": 0, "by_type": {}})
            node_counts[layer]["total"] += 1
            typ = node["labels"][0] if node["labels"] else "Entity"
            node_counts[layer]["by_type"][typ] = node_counts[layer]["by_type"].get(typ, 0) + 1
            verified = node["properties"].get("verified")
            if verified is True:
                verification["verified"] += 1
            elif verified == "pending_review":
                verification["pending_review"] += 1
            else:
                verification["unverified"] += 1

        rel_counts: dict[str, int] = {}
        for rel in relations:
            rel_counts[rel["type"]] = rel_counts.get(rel["type"], 0) + 1

        return {
            "case_id": case_id,
            "node_counts": node_counts,
            "relation_counts": rel_counts,
            "verification_status": verification,
            "last_updated": _iso_now(),
        }

    async def get_neighbors(self, node_id: str, limit: int = 100) -> dict[str, Any]:
        case_id = self._node_case_index.get(node_id)
        if not case_id:
            raise KeyError("node not found")
        rels = self._relations(case_id).values()
        neighbors: list[dict[str, Any]] = []
        for rel in rels:
            if rel["source_id"] == node_id:
                neighbor = self.get_node(rel["target_id"])
                if neighbor:
                    neighbors.append({"relation": rel, "node": neighbor})
            elif rel["target_id"] == node_id:
                neighbor = self.get_node(rel["source_id"])
                if neighbor:
                    neighbors.append({"relation": rel, "node": neighbor})
            if len(neighbors) >= limit:
                break
        return {"node_id": node_id, "neighbors": neighbors, "total": len(neighbors)}

    async def path_to(self, source_id: str, target_id: str, max_depth: int = 6) -> dict[str, Any]:
        case_id = self._node_case_index.get(source_id)
        if not case_id or self._node_case_index.get(target_id) != case_id:
            raise KeyError("source or target node not found")
        graph: dict[str, list[tuple[str, str]]] = {}
        for rel in self._relations(case_id).values():
            graph.setdefault(rel["source_id"], []).append((rel["target_id"], rel["id"]))
            graph.setdefault(rel["target_id"], []).append((rel["source_id"], rel["id"]))

        queue = deque([(source_id, [source_id], [])])
        visited = {source_id}
        while queue:
            current, path_nodes, path_rels = queue.popleft()
            if current == target_id:
                return {"source_id": source_id, "target_id": target_id, "path": path_nodes, "relations": path_rels}
            if len(path_nodes) > max_depth:
                continue
            for neighbor, rel_id in graph.get(current, []):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                queue.append((neighbor, [*path_nodes, neighbor], [*path_rels, rel_id]))
        return {"source_id": source_id, "target_id": target_id, "path": [], "relations": []}
