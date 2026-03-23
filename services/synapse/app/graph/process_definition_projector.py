"""
프로세스 그래프 Neo4j Projector.

Phase 3: PostgreSQL 이벤트를 기반으로 Neo4j에 프로세스 그래프 노드/엣지를 MERGE.
관계 타입은 반드시 화이트리스트를 통과해야 한다.
"""
from __future__ import annotations

from typing import Any

import structlog

from app.core.neo4j_client import Neo4jClient
from app.graph.relation_whitelist import validate_relation_type

logger = structlog.get_logger()


class ProcessDefinitionProjector:
    """프로세스 정의/버전/Step/관계를 Neo4j에 투영한다."""

    def __init__(self, neo4j: Neo4jClient):
        self.neo4j = neo4j

    # ── ProcessDefinition 노드 ─────────────────────────────

    async def upsert_definition(self, data: dict[str, Any]) -> None:
        """프로세스 정의 노드 upsert."""
        cypher = """
        MERGE (p:ProcessDefinition {id: $id})
        SET p.tenantId = $tenantId,
            p.workspaceId = $workspaceId,
            p.code = $code,
            p.name = $name,
            p.namespace = $namespace,
            p.processType = $processType,
            p.lifecycleStatus = $lifecycleStatus,
            p.updatedAt = datetime($updatedAt)
        """
        async with self.neo4j.session() as session:
            await session.run(cypher, **data)
        logger.info("projected_process_definition", id=data.get("id"))

    # ── ProcessVersion 노드 + HAS_VERSION 관계 ─────────────

    async def upsert_version(self, data: dict[str, Any]) -> None:
        """프로세스 버전 노드 + HAS_VERSION 관계 upsert."""
        cypher = """
        MERGE (v:ProcessVersion {id: $id})
        SET v.tenantId = $tenantId,
            v.versionNo = $versionNo,
            v.status = $status,
            v.updatedAt = datetime($updatedAt)
        WITH v
        MATCH (p:ProcessDefinition {id: $processDefinitionId})
        MERGE (p)-[:HAS_VERSION]->(v)
        """
        async with self.neo4j.session() as session:
            await session.run(cypher, **data)
        logger.info("projected_process_version", id=data.get("id"))

    # ── StepDefinition 노드 + HAS_STEP 관계 ────────────────

    async def upsert_steps(self, version_id: str, tenant_id: str, steps: list[dict]) -> None:
        """Step 노드 + HAS_STEP 관계 일괄 upsert."""
        cypher = """
        UNWIND $steps AS s
        MERGE (st:StepDefinition {id: s.id})
        SET st.tenantId = $tenantId,
            st.code = s.code,
            st.name = s.name,
            st.stepType = s.stepType,
            st.displayOrder = s.displayOrder
        WITH st, s
        MATCH (v:ProcessVersion {id: $versionId})
        MERGE (v)-[:HAS_STEP]->(st)
        """
        async with self.neo4j.session() as session:
            await session.run(cypher, steps=steps, versionId=version_id, tenantId=tenant_id)
        logger.info("projected_steps", version_id=version_id, count=len(steps))

    # ── 전이 관계 (NEXT/YES/NO/ERROR 등) ───────────────────

    async def upsert_transitions(self, tenant_id: str, transitions: list[dict]) -> None:
        """Step 간 전이 관계 upsert — 관계 타입별 분리 MERGE."""
        # 관계 타입별로 그룹핑 (Cypher에서는 관계 타입을 파라미터로 쓸 수 없으므로)
        by_type: dict[str, list[dict]] = {}
        for t in transitions:
            rel_type = validate_relation_type(t["transitionType"])
            by_type.setdefault(rel_type, []).append(t)

        async with self.neo4j.session() as session:
            for rel_type, items in by_type.items():
                cypher = f"""
                UNWIND $items AS t
                MATCH (from:StepDefinition {{id: t.fromStepId}})
                MATCH (to:StepDefinition {{id: t.toStepId}})
                MERGE (from)-[r:{rel_type} {{edgeId: t.edgeId}}]->(to)
                SET r.tenantId = $tenantId,
                    r.isDefault = t.isDefault
                """
                await session.run(cypher, items=items, tenantId=tenant_id)
        logger.info("projected_transitions", count=len(transitions))

    # ── 프로세스 관계 엣지 (TRIGGERS, BLOCKS 등) ────────────

    async def upsert_relation(self, data: dict[str, Any]) -> None:
        """프로세스 간 관계 엣지 upsert."""
        rel_type = validate_relation_type(data["relationType"])
        # 소스/타겟 노드 라벨은 범용으로 처리
        cypher = f"""
        MATCH (s {{id: $sourceId}})
        MATCH (t {{id: $targetId}})
        MERGE (s)-[r:{rel_type} {{edgeId: $edgeId}}]->(t)
        SET r.tenantId = $tenantId,
            r.workspaceId = $workspaceId,
            r.weight = $weight,
            r.criticality = $criticality,
            r.updatedAt = datetime($updatedAt)
        """
        async with self.neo4j.session() as session:
            await session.run(cypher, **data)
        logger.info("projected_relation", edge_id=data.get("edgeId"), type=rel_type)

    async def soft_delete_relation(self, edge_id: str, tenant_id: str) -> None:
        """관계 엣지 soft-delete (active=false)."""
        cypher = """
        MATCH ()-[r {edgeId: $edgeId, tenantId: $tenantId}]->()
        SET r.active = false, r.deletedAt = datetime()
        """
        async with self.neo4j.session() as session:
            await session.run(cypher, edgeId=edge_id, tenantId=tenant_id)
        logger.info("soft_deleted_relation", edge_id=edge_id)
