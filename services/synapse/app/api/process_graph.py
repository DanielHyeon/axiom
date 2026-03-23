"""
프로세스 그래프 영향도 분석 API — /api/v3/synapse/process-graph/*.

Phase 3: Neo4j 기반 영향도 탐색 5개 엔드포인트.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from app.core.neo4j_client import Neo4jClient

router = APIRouter(
    prefix="/api/v3/synapse/process-graph",
    tags=["process-graph"],
)

# Neo4j 클라이언트 의존성 — Synapse main.py에서 app.state.neo4j로 주입
def get_neo4j():
    from app.main import app
    return app.state.neo4j


def _get_tenant_id(x_tenant_id: str = Header(None, alias="X-Tenant-Id")) -> str:
    """X-Tenant-Id 헤더에서 tenant_id 추출 — query param이 아닌 헤더 기반."""
    if not x_tenant_id or x_tenant_id == "default":
        return "default"
    return x_tenant_id


@router.get("/definitions/{def_id}/impact")
async def get_impact_analysis(
    def_id: str,
    direction: str = Query("DOWNSTREAM", regex="^(UPSTREAM|DOWNSTREAM|BOTH)$"),
    depth: int = Query(3, ge=1, le=10),
    neo4j: Neo4jClient = Depends(get_neo4j),
):
    """영향도 확산 분석 — 지정 방향/깊이로 연결된 프로세스 탐색."""
    if direction == "DOWNSTREAM":
        cypher = f"""
        MATCH p=(root:ProcessDefinition {{id: $rootId, tenantId: $tenantId}})
              -[:TRIGGERS|BLOCKS|DEPENDS_ON|HANDOFF_TO*1..{depth}]->(n)
        WHERE n.tenantId = $tenantId
        RETURN n.id AS id, n.name AS name, n.code AS code,
               n.lifecycleStatus AS status, length(p) AS distance
        """
    elif direction == "UPSTREAM":
        cypher = f"""
        MATCH p=(root:ProcessDefinition {{id: $rootId, tenantId: $tenantId}})
              <-[:TRIGGERS|BLOCKS|DEPENDS_ON|HANDOFF_TO*1..{depth}]-(n)
        WHERE n.tenantId = $tenantId
        RETURN n.id AS id, n.name AS name, n.code AS code,
               n.lifecycleStatus AS status, length(p) AS distance
        """
    else:
        cypher = f"""
        MATCH p=(root:ProcessDefinition {{id: $rootId, tenantId: $tenantId}})
              -[:TRIGGERS|BLOCKS|DEPENDS_ON|HANDOFF_TO*1..{depth}]-(n)
        WHERE n.tenantId = $tenantId AND n.id <> $rootId
        RETURN DISTINCT n.id AS id, n.name AS name, n.code AS code,
               n.lifecycleStatus AS status, min(length(p)) AS distance
        """

    results = await neo4j.execute_read(cypher, {"rootId": def_id, "tenantId": tenant_id})
    return {"success": True, "data": results, "direction": direction, "depth": depth}


@router.get("/definitions/{def_id}/upstream")
async def get_upstream(
    def_id: str,
    tenant_id: str = Depends(_get_tenant_id),
    depth: int = Query(3, ge=1, le=10),
    neo4j: Neo4jClient = Depends(get_neo4j),
):
    """상류 의존 프로세스 목록."""
    cypher = f"""
    MATCH p=(target:ProcessDefinition {{id: $targetId, tenantId: $tenantId}})
          <-[:BLOCKS|DEPENDS_ON|HANDOFF_TO*1..{depth}]-(upstream)
    WHERE upstream.tenantId = $tenantId
    RETURN upstream.id AS id, upstream.name AS name, upstream.code AS code,
           length(p) AS distance
    ORDER BY length(p)
    """
    results = await neo4j.execute_read(cypher, {"targetId": def_id, "tenantId": tenant_id})
    return {"success": True, "data": results}


@router.get("/definitions/{def_id}/downstream")
async def get_downstream(
    def_id: str,
    tenant_id: str = Depends(_get_tenant_id),
    depth: int = Query(3, ge=1, le=10),
    neo4j: Neo4jClient = Depends(get_neo4j),
):
    """하류 영향 프로세스 목록."""
    cypher = f"""
    MATCH p=(source:ProcessDefinition {{id: $sourceId, tenantId: $tenantId}})
          -[:TRIGGERS|BLOCKS|DEPENDS_ON|HANDOFF_TO*1..{depth}]->(downstream)
    WHERE downstream.tenantId = $tenantId
    RETURN downstream.id AS id, downstream.name AS name, downstream.code AS code,
           length(p) AS distance
    ORDER BY length(p)
    """
    results = await neo4j.execute_read(cypher, {"sourceId": def_id, "tenantId": tenant_id})
    return {"success": True, "data": results}


@router.get("/definitions/{def_id}/graph")
async def get_full_graph(
    def_id: str,
    tenant_id: str = Depends(_get_tenant_id),
    depth: int = Query(2, ge=1, le=5),
    neo4j: Neo4jClient = Depends(get_neo4j),
):
    """전체 관계 그래프 — Cytoscape 호환 형식."""
    cypher = f"""
    MATCH p=(root:ProcessDefinition {{id: $rootId, tenantId: $tenantId}})
          -[r*1..{depth}]-(n)
    WHERE n.tenantId = $tenantId
    WITH COLLECT(DISTINCT n) AS nodes, COLLECT(DISTINCT r) AS rels
    UNWIND nodes AS node
    WITH COLLECT(DISTINCT {{
        id: node.id, name: node.name, code: node.code,
        type: labels(node)[0], status: node.lifecycleStatus
    }}) AS nodeList, rels
    UNWIND rels AS relList
    UNWIND relList AS rel
    WITH nodeList, COLLECT(DISTINCT {{
        source: startNode(rel).id, target: endNode(rel).id,
        type: type(rel), weight: rel.weight
    }}) AS edgeList
    RETURN nodeList AS nodes, edgeList AS edges
    """
    results = await neo4j.execute_read(cypher, {"rootId": def_id, "tenantId": tenant_id})
    if results:
        return {"success": True, "data": {"nodes": results[0].get("nodes", []), "edges": results[0].get("edges", [])}}
    return {"success": True, "data": {"nodes": [], "edges": []}}


@router.get("/definitions/{def_id}/critical-path")
async def get_critical_path(
    def_id: str,
    tenant_id: str = Depends(_get_tenant_id),
    neo4j: Neo4jClient = Depends(get_neo4j),
):
    """병목 경로 분석 — BLOCKS/DEPENDS_ON 관계의 최장 체인."""
    cypher = """
    MATCH p=(target:ProcessDefinition {id: $targetId, tenantId: $tenantId})
          <-[:BLOCKS|DEPENDS_ON*1..10]-(upstream)
    WHERE upstream.tenantId = $tenantId
    WITH p, length(p) AS pathLen
    ORDER BY pathLen DESC
    LIMIT 5
    UNWIND nodes(p) AS node
    WITH p, pathLen, COLLECT({id: node.id, name: node.name, code: node.code}) AS pathNodes
    RETURN pathNodes, pathLen
    ORDER BY pathLen DESC
    """
    results = await neo4j.execute_read(cypher, {"targetId": def_id, "tenantId": tenant_id})
    return {"success": True, "data": results}
