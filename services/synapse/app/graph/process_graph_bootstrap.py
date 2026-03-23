"""
프로세스 그래프 Neo4j 스키마 초기화.

Phase 3: 프로세스 그래프 노드/엣지용 제약 및 인덱스 생성.
Neo4jBootstrap.initialize() 이후 호출한다.
"""
from __future__ import annotations

import structlog

from app.core.neo4j_client import Neo4jClient

logger = structlog.get_logger()

PROCESS_GRAPH_CONSTRAINTS = [
    "CREATE CONSTRAINT process_def_id IF NOT EXISTS FOR (n:ProcessDefinition) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT process_ver_id IF NOT EXISTS FOR (n:ProcessVersion) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT step_def_id IF NOT EXISTS FOR (n:StepDefinition) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT interface_id IF NOT EXISTS FOR (n:InterfaceContract) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT rule_def_id IF NOT EXISTS FOR (n:RuleDefinition) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT kpi_def_id IF NOT EXISTS FOR (n:KpiDefinition) REQUIRE n.id IS UNIQUE",
]

PROCESS_GRAPH_INDEXES = [
    "CREATE INDEX process_def_tenant IF NOT EXISTS FOR (n:ProcessDefinition) ON (n.tenantId)",
    "CREATE INDEX step_def_tenant IF NOT EXISTS FOR (n:StepDefinition) ON (n.tenantId)",
    "CREATE INDEX process_def_workspace IF NOT EXISTS FOR (n:ProcessDefinition) ON (n.workspaceId)",
]


async def initialize_process_graph_schema(neo4j: Neo4jClient) -> None:
    """프로세스 그래프 Neo4j 스키마 생성 (멱등)."""
    logger.info("process_graph_schema_init_start")
    async with neo4j.session() as session:
        for cypher in PROCESS_GRAPH_CONSTRAINTS + PROCESS_GRAPH_INDEXES:
            await session.run(cypher)
    logger.info("process_graph_schema_init_complete", constraints=len(PROCESS_GRAPH_CONSTRAINTS), indexes=len(PROCESS_GRAPH_INDEXES))
