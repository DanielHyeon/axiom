"""Impact Analysis Service — O4: Cross-domain BFS traversal for change impact."""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import structlog

from app.core.neo4j_client import neo4j_client

logger = structlog.get_logger()

_REL_ALLOWLIST = frozenset({
    "BELONGS_TO", "HAS_MEASURE", "HAS_KPI", "IMPACTS",
    "DEPENDS_ON", "INTERACTS_WITH", "FK_TO", "MAPS_TO",
    "DERIVED_FROM", "DEFINES",
})

_MAX_DEPTH_LIMIT = 5
_MAX_AFFECTED_NODES = 200


@dataclass
class ImpactPathStep:
    node_id: str
    node_label: str
    rel_type: str = ""


@dataclass
class ImpactNode:
    id: str
    element_id: str
    label: str
    labels: list[str]
    layer: str
    depth: int
    path: list[ImpactPathStep] = field(default_factory=list)


@dataclass
class ImpactResult:
    root_id: str
    root_label: str
    root_layer: str
    affected_nodes: list[ImpactNode]
    total_affected: int
    max_depth_reached: int
    analysis_time_ms: int


_LABEL_TO_LAYER: dict[str, str] = {
    "KPI": "kpi",
    "Measure": "measure",
    "Process": "process",
    "Resource": "resource",
    "Table": "table",
    "Column": "column",
    "Schema": "schema",
    "DataSource": "datasource",
}


class ImpactAnalysisService:
    """Cross-domain BFS traversal using iterative 1-hop expansion (no APOC)."""

    def __init__(self) -> None:
        self._neo4j = neo4j_client

    async def _read(self, cypher: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        async with self._neo4j.session() as session:
            result = await session.run(cypher, params or {})
            return [dict(record) async for record in result]

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
    def _node_name(node: Any) -> str:
        if hasattr(node, "items"):
            props = dict(node.items())
        elif isinstance(node, dict):
            props = node
        else:
            props = {}
        return str(props.get("name", props.get("id", "unknown")))

    @staticmethod
    def _node_layer(labels: list[str]) -> str:
        for lbl in labels:
            if lbl in _LABEL_TO_LAYER:
                return _LABEL_TO_LAYER[lbl]
        return "unknown"

    async def impact_analysis(
        self,
        start_node_id: str,
        case_id: str,
        max_depth: int = 3,
    ) -> ImpactResult:
        """Multi-hop BFS from a starting node across _REL_ALLOWLIST relationships."""
        started = time.perf_counter()
        safe_depth = max(1, min(max_depth, _MAX_DEPTH_LIMIT))
        rel_filter = "|".join(_REL_ALLOWLIST)

        # 1) Find start node
        root_rows = await self._read(
            "MATCH (n {id: $node_id, case_id: $case_id}) "
            "RETURN n, elementId(n) AS eid LIMIT 1",
            {"node_id": start_node_id, "case_id": case_id},
        )
        if not root_rows:
            # Try without case_id (for schema nodes like Table)
            root_rows = await self._read(
                "MATCH (n {id: $node_id}) RETURN n, elementId(n) AS eid LIMIT 1",
                {"node_id": start_node_id},
            )
        if not root_rows:
            elapsed = int((time.perf_counter() - started) * 1000)
            return ImpactResult(
                root_id=start_node_id, root_label="not found", root_layer="unknown",
                affected_nodes=[], total_affected=0, max_depth_reached=0,
                analysis_time_ms=max(1, elapsed),
            )

        root_node = root_rows[0]["n"]
        root_eid = str(root_rows[0]["eid"])
        root_label = self._node_name(root_node)
        root_layer = self._node_layer(self._node_labels(root_node))

        # 2) BFS
        queue: deque[tuple[str, int, list[ImpactPathStep]]] = deque()
        queue.append((
            root_eid,
            0,
            [ImpactPathStep(node_id=start_node_id, node_label=root_label)],
        ))
        visited: set[str] = {root_eid}
        affected: list[ImpactNode] = []
        max_depth_reached = 0

        while queue and len(affected) < _MAX_AFFECTED_NODES:
            current_eid, current_depth, current_path = queue.popleft()
            if current_depth >= safe_depth:
                continue

            neighbors = await self._read(
                f"MATCH (start) WHERE elementId(start) = $eid "
                f"MATCH (start)-[r:{rel_filter}]-(neighbor) "
                f"RETURN neighbor, type(r) AS rel_type, elementId(neighbor) AS neighbor_eid "
                f"LIMIT 50",
                {"eid": current_eid},
            )

            for row in neighbors:
                n_eid = str(row["neighbor_eid"])
                if n_eid in visited:
                    continue
                visited.add(n_eid)

                n_node = row["neighbor"]
                n_labels = self._node_labels(n_node)
                n_name = self._node_name(n_node)
                n_layer = self._node_layer(n_labels)
                n_depth = current_depth + 1
                n_id = str(
                    n_node.get("id", n_eid) if isinstance(n_node, dict) else n_eid
                )

                new_path = [
                    *current_path,
                    ImpactPathStep(
                        node_id=n_id,
                        node_label=n_name,
                        rel_type=row["rel_type"],
                    ),
                ]

                affected.append(ImpactNode(
                    id=n_id,
                    element_id=n_eid,
                    label=n_name,
                    labels=n_labels,
                    layer=n_layer,
                    depth=n_depth,
                    path=new_path,
                ))
                max_depth_reached = max(max_depth_reached, n_depth)

                if n_depth < safe_depth:
                    queue.append((n_eid, n_depth, new_path))

        elapsed = int((time.perf_counter() - started) * 1000)
        return ImpactResult(
            root_id=start_node_id,
            root_label=root_label,
            root_layer=root_layer,
            affected_nodes=affected,
            total_affected=len(affected),
            max_depth_reached=max_depth_reached,
            analysis_time_ms=max(1, elapsed),
        )


impact_analysis_service = ImpactAnalysisService()
