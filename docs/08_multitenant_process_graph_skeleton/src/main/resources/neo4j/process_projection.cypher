// 예시 Projection 규칙
MERGE (t:Tenant {id: $tenantId})
MERGE (w:Workspace {id: $workspaceId})
MERGE (p:Process {id: $processId})
SET p.name = $processName,
    p.processKey = $processKey,
    p.status = $status
MERGE (t)-[:OWNS]->(w)
MERGE (w)-[:CONTAINS]->(p);

// 프로세스 간 의존 관계 예시
MATCH (source:Process {id: $sourceProcessId})
MATCH (target:Process {id: $targetProcessId})
MERGE (source)-[r:DEPENDS_ON {relationType: $relationType}]->(target)
SET r.weight = $weight,
    r.interfaceCode = $interfaceCode,
    r.updatedAt = datetime();
