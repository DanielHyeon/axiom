"""Unit tests for ImpactAnalysisService (O4)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.impact_analysis_service import ImpactAnalysisService


def _make_node(node_id: str, name: str, labels: list[str], case_id: str = "case-1"):
    """Create a mock Neo4j node dict."""
    return {
        "id": node_id,
        "name": name,
        "labels": labels,
        "case_id": case_id,
        "element_id": f"eid:{node_id}",
    }


def _make_mock_node(node_id: str, name: str, labels: list[str], case_id: str = "case-1"):
    """Create a mock Neo4j node with .element_id and .labels attributes."""
    node = MagicMock()
    node.element_id = f"eid:{node_id}"
    node.labels = labels
    node.items.return_value = [
        ("id", node_id),
        ("name", name),
        ("case_id", case_id),
    ]
    node.get = lambda k, d=None: {"id": node_id, "name": name, "case_id": case_id}.get(k, d)
    node.__getitem__ = lambda _, k: {"id": node_id, "name": name, "case_id": case_id}[k]
    return node


@pytest.fixture
def service():
    svc = ImpactAnalysisService()
    svc._neo4j = MagicMock()
    return svc


@pytest.mark.asyncio
async def test_empty_result_when_node_not_found(service: ImpactAnalysisService):
    """Non-existent start node returns empty result."""
    service._read = AsyncMock(return_value=[])

    result = await service.impact_analysis("nonexistent", "case-1", max_depth=3)

    assert result.root_label == "not found"
    assert result.root_layer == "unknown"
    assert result.total_affected == 0
    assert result.affected_nodes == []


@pytest.mark.asyncio
async def test_bfs_finds_neighbors(service: ImpactAnalysisService):
    """BFS from root finds 1-hop neighbors."""
    root_node = _make_mock_node("node-root", "Root KPI", ["KPI"])
    neighbor_node = _make_mock_node("node-m1", "Measure A", ["Measure"])

    call_count = 0

    async def mock_read(cypher: str, params=None):
        nonlocal call_count
        call_count += 1

        # First call: find root
        if "RETURN n, elementId(n)" in cypher and params.get("case_id"):
            return [{"n": root_node, "eid": "eid:node-root"}]
        if "RETURN n, elementId(n)" in cypher and not params.get("case_id"):
            return []

        # BFS expansion calls
        if "MATCH (start)-[r:" in cypher:
            eid = params.get("eid", "")
            if eid == "eid:node-root":
                return [{
                    "neighbor": neighbor_node,
                    "rel_type": "HAS_MEASURE",
                    "neighbor_eid": "eid:node-m1",
                }]
            # No more neighbors for node-m1
            return []

        return []

    service._read = mock_read

    result = await service.impact_analysis("node-root", "case-1", max_depth=1)

    assert result.root_id == "node-root"
    assert result.root_label == "Root KPI"
    assert result.root_layer == "kpi"
    assert result.total_affected == 1
    assert result.affected_nodes[0].label == "Measure A"
    assert result.affected_nodes[0].layer == "measure"
    assert result.affected_nodes[0].depth == 1


@pytest.mark.asyncio
async def test_max_depth_respected(service: ImpactAnalysisService):
    """BFS stops at max_depth."""
    root_node = _make_mock_node("node-root", "Root", ["Process"])
    neighbor1 = _make_mock_node("node-1", "N1", ["Measure"])
    neighbor2 = _make_mock_node("node-2", "N2", ["KPI"])

    async def mock_read(cypher: str, params=None):
        if "RETURN n, elementId(n)" in cypher and params.get("case_id"):
            return [{"n": root_node, "eid": "eid:node-root"}]
        if "RETURN n, elementId(n)" in cypher:
            return []

        if "MATCH (start)-[r:" in cypher:
            eid = params.get("eid", "")
            if eid == "eid:node-root":
                return [{
                    "neighbor": neighbor1,
                    "rel_type": "HAS_MEASURE",
                    "neighbor_eid": "eid:node-1",
                }]
            if eid == "eid:node-1":
                return [{
                    "neighbor": neighbor2,
                    "rel_type": "HAS_KPI",
                    "neighbor_eid": "eid:node-2",
                }]
            return []
        return []

    service._read = mock_read

    # max_depth=1: should only find N1
    result = await service.impact_analysis("node-root", "case-1", max_depth=1)
    assert result.total_affected == 1
    assert result.affected_nodes[0].label == "N1"

    # max_depth=2: should find N1 and N2
    result = await service.impact_analysis("node-root", "case-1", max_depth=2)
    assert result.total_affected == 2
    labels = {n.label for n in result.affected_nodes}
    assert labels == {"N1", "N2"}


@pytest.mark.asyncio
async def test_cycle_detection(service: ImpactAnalysisService):
    """BFS does not revisit already-visited nodes (cycle prevention)."""
    node_a = _make_mock_node("a", "NodeA", ["Process"])
    node_b = _make_mock_node("b", "NodeB", ["Resource"])

    async def mock_read(cypher: str, params=None):
        if "RETURN n, elementId(n)" in cypher and params.get("case_id"):
            return [{"n": node_a, "eid": "eid:a"}]
        if "RETURN n, elementId(n)" in cypher:
            return []

        if "MATCH (start)-[r:" in cypher:
            eid = params.get("eid", "")
            if eid == "eid:a":
                return [{
                    "neighbor": node_b,
                    "rel_type": "INTERACTS_WITH",
                    "neighbor_eid": "eid:b",
                }]
            if eid == "eid:b":
                # B links back to A (cycle) and no new nodes
                return [{
                    "neighbor": node_a,
                    "rel_type": "INTERACTS_WITH",
                    "neighbor_eid": "eid:a",
                }]
            return []
        return []

    service._read = mock_read

    result = await service.impact_analysis("a", "case-1", max_depth=5)
    # Despite max_depth=5, only NodeB is found (NodeA already visited)
    assert result.total_affected == 1
    assert result.affected_nodes[0].label == "NodeB"


@pytest.mark.asyncio
async def test_path_chain_built_correctly(service: ImpactAnalysisService):
    """Path chain includes root → ... → target with relationship types."""
    root = _make_mock_node("r", "Root", ["KPI"])
    n1 = _make_mock_node("n1", "N1", ["Measure"])
    n2 = _make_mock_node("n2", "N2", ["Table"])

    async def mock_read(cypher: str, params=None):
        if "RETURN n, elementId(n)" in cypher and params.get("case_id"):
            return [{"n": root, "eid": "eid:r"}]
        if "RETURN n, elementId(n)" in cypher:
            return []

        if "MATCH (start)-[r:" in cypher:
            eid = params.get("eid", "")
            if eid == "eid:r":
                return [{"neighbor": n1, "rel_type": "HAS_MEASURE", "neighbor_eid": "eid:n1"}]
            if eid == "eid:n1":
                return [{"neighbor": n2, "rel_type": "MAPS_TO", "neighbor_eid": "eid:n2"}]
            return []
        return []

    service._read = mock_read

    result = await service.impact_analysis("r", "case-1", max_depth=3)
    assert result.total_affected == 2

    # N2 (depth=2) should have full path: Root → HAS_MEASURE → N1 → MAPS_TO → N2
    n2_result = next(n for n in result.affected_nodes if n.label == "N2")
    assert len(n2_result.path) == 3
    assert n2_result.path[0].node_label == "Root"
    assert n2_result.path[1].node_label == "N1"
    assert n2_result.path[1].rel_type == "HAS_MEASURE"
    assert n2_result.path[2].node_label == "N2"
    assert n2_result.path[2].rel_type == "MAPS_TO"


@pytest.mark.asyncio
async def test_layer_detection():
    """_node_layer correctly maps Neo4j labels to layer names."""
    svc = ImpactAnalysisService()
    assert svc._node_layer(["KPI"]) == "kpi"
    assert svc._node_layer(["Measure"]) == "measure"
    assert svc._node_layer(["Process"]) == "process"
    assert svc._node_layer(["Resource"]) == "resource"
    assert svc._node_layer(["Table"]) == "table"
    assert svc._node_layer(["Column"]) == "column"
    assert svc._node_layer(["UnknownLabel"]) == "unknown"
    assert svc._node_layer([]) == "unknown"
