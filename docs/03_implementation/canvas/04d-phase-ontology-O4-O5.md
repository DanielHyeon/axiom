# Ontology Phase O4-O5: Impact Analysis + 고급 기능

> **상위 문서**: [04d_nl2sql-ontology-gap-analysis.md](04d_nl2sql-ontology-gap-analysis.md)
> **해결 항목**: I9-I10 (O4), I15-I20 (O5)

---

## Phase O4: Impact Analysis (I9-I10)

> **리스크 4 완화**: depth default=3, hard cap=5, 응답 노드 수 hard limit=100

### O4-1: ImpactAnalysisService 생성

**신규 파일**: `services/synapse/app/services/impact_analysis_service.py`

**핵심 기능**: cross-domain BFS (Schema ↔ Ontology 영역 간 관계 탐색)

```python
class ImpactAnalysisService:
    DEFAULT_DEPTH = 3
    MAX_DEPTH = 5
    MAX_NODES = 100

    def __init__(self, neo4j_client):
        self.neo4j = neo4j_client

    async def analyze_impact(
        self,
        start_node_id: str,
        direction: str = "downstream",  # "upstream" | "downstream" | "both"
        depth: int = 3,
        tenant_id: str = "",
    ) -> dict:
        """시작 노드에서 영향받는 모든 노드와 경로를 반환."""
        depth = min(depth, self.MAX_DEPTH)
        # cross-domain BFS
        ...

    async def schema_change_impact(
        self,
        table_name: str,
        tenant_id: str = "",
        depth: int = 3,
    ) -> dict:
        """테이블 변경 시 영향받는 Ontology 노드 + Cached Query 목록."""
        depth = min(depth, self.MAX_DEPTH)
        ...
```

### Cross-Domain BFS Cypher

**Downstream** (Table 변경 → 영향받는 Measure/KPI):

```cypher
MATCH path = (start:Table {name: $table_name})<-[:MAPS_TO*..{depth}]-(ontology_node)
WHERE ontology_node.tenant_id = $tenant_id OR ontology_node.case_id IS NOT NULL
WITH ontology_node, path, length(path) AS distance
ORDER BY distance ASC
LIMIT $max_nodes
RETURN
  ontology_node.id AS id,
  ontology_node.name AS name,
  labels(ontology_node) AS labels,
  ontology_node.layer AS layer,
  distance,
  [n IN nodes(path) | n.name] AS path_names
```

**Upstream** (KPI 선택 → 의존하는 Measure→Process→Resource):

```cypher
MATCH path = (start {id: $node_id})-[*..{depth}]->(dep)
WHERE dep.case_id = $case_id
WITH dep, path, length(path) AS distance
ORDER BY distance ASC
LIMIT $max_nodes
RETURN
  dep.id AS id,
  dep.name AS name,
  dep.layer AS layer,
  distance,
  [n IN nodes(path) | n.name] AS path_names
```

**Schema Change → Cached Query 영향**:

```cypher
MATCH (t:Table {name: $table_name})<-[:REFERENCES]-(q:Query)
RETURN
  q.question AS question,
  q.sql AS sql,
  q.confidence AS confidence
```

### O4-2: Graph API 확장

**수정 파일**: `services/synapse/app/api/graph.py`

**추가 엔드포인트**:

| Method | Route | 설명 |
| --- | --- | --- |
| POST | `/impact-analysis` | 노드 영향 분석 |
| POST | `/schema-change-impact` | 테이블 변경 영향 분석 |

**Request/Response**:

```python
# POST /impact-analysis
{
    "node_id": "kpi_revenue_growth",
    "direction": "upstream",
    "depth": 3
}
# Response
{
    "success": true,
    "data": {
        "start_node": {"id": "...", "name": "...", "layer": "kpi"},
        "impacted_nodes": [
            {"id": "...", "name": "...", "layer": "measure", "distance": 1},
            {"id": "...", "name": "...", "layer": "process", "distance": 2},
        ],
        "paths": [...],
        "truncated": false,
        "total_count": 8
    }
}

# POST /schema-change-impact
{
    "table_name": "revenue",
    "depth": 3
}
# Response
{
    "success": true,
    "data": {
        "table": "revenue",
        "impacted_ontology_nodes": [...],
        "impacted_cached_queries": [
            {"question": "매출 추이", "sql": "SELECT...", "confidence": 0.85}
        ],
        "total_impact_count": 5
    }
}
```

### O4-3: Canvas ImpactAnalysisPanel

**신규 파일**: `apps/canvas/src/pages/ontology/components/ImpactAnalysisPanel.tsx`

**UI 구성**:
- **시작 노드**: 현재 선택된 노드 (NodeDetail에서 진입)
- **방향 선택**: upstream / downstream / both (라디오 버튼)
- **깊이 슬라이더**: 1~5 (default 3)
- **결과 영역**: 영향 노드 목록 (layer별 그룹화) + 경로 요약
- **그래프 하이라이트**: 영향 노드를 GraphViewer에서 하이라이트 (PathHighlighter 재사용)

### O4-4: NodeDetail 영향 분석 버튼

**수정 파일**: `apps/canvas/src/pages/ontology/components/NodeDetail.tsx`

**추가**: "변경 영향 분석" 버튼 (기존 "이 노드로 경로 탐색" 아래)

```typescript
<button onClick={() => onAnalyzeImpact(selectedNode.id)}>
  변경 영향 분석
</button>
```

### O4-5: ontologyApi 확장

**수정 파일**: `apps/canvas/src/features/ontology/api/ontologyApi.ts`

```typescript
analyzeImpact(nodeId: string, direction: string, depth: number)
  → POST /api/v3/synapse/graph/impact-analysis

analyzeSchemaChangeImpact(tableName: string, depth: number)
  → POST /api/v3/synapse/graph/schema-change-impact
```

### Phase O4 수정 파일 요약

| 파일 | 변경 | 위험도 |
| --- | --- | --- |
| `services/synapse/app/services/impact_analysis_service.py` | CREATE | MEDIUM |
| `services/synapse/app/api/graph.py` | MODIFY (+2 endpoints) | LOW |
| `apps/canvas/src/features/ontology/api/ontologyApi.ts` | MODIFY (+2 함수) | LOW |
| `apps/canvas/src/pages/ontology/components/ImpactAnalysisPanel.tsx` | CREATE | MEDIUM |
| `apps/canvas/src/pages/ontology/components/NodeDetail.tsx` | MODIFY (버튼) | LOW |
| `apps/canvas/src/pages/ontology/OntologyPage.tsx` | MODIFY (패널 통합) | LOW |

### Gate O4 판정 기준

- [x] Table 변경 → 연결된 Measure/KPI 목록 반환 (depth=3)
- [x] KPI 선택 → 의존하는 Measure→Process→Resource 역추적
- [x] `depth=6` 요청 시 hard cap 5로 제한됨 확인
- [x] 100개 초과 노드 시 `truncated: true` + warning
- [x] ImpactAnalysisPanel UI: 영향 노드 목록 + 경로 하이라이트
- [x] Schema change → 영향받는 cached query 목록 반환

---

## Phase O5: 고급 기능 (I15-I20)

### O5-1: OWL/RDF Export (I19)

**신규 파일**: `services/synapse/app/services/ontology_exporter.py`

**의존성 추가**: `rdflib` (export-only, import 용도 아님)

```python
class OntologyExporter:
    """온톨로지 그래프를 RDF 형식으로 export."""

    async def export_turtle(self, case_id: str, tenant_id: str) -> str:
        """Turtle (.ttl) 형식으로 export."""
        from rdflib import Graph, Namespace, Literal, URIRef
        g = Graph()
        AX = Namespace("http://axiom.ai/ontology/")
        # Neo4j에서 노드/관계 조회 → rdflib 트리플 변환
        ...
        return g.serialize(format="turtle")

    async def export_jsonld(self, case_id: str, tenant_id: str) -> str:
        """JSON-LD 형식으로 export."""
        ...
```

**API 엔드포인트** (graph.py):

```python
@router.get("/export")
async def export_ontology(case_id: str, format: str = "turtle", request: Request):
    if format == "turtle":
        content = await ontology_exporter.export_turtle(case_id, tenant_id)
        return Response(content, media_type="text/turtle")
    elif format == "jsonld":
        content = await ontology_exporter.export_jsonld(case_id, tenant_id)
        return Response(content, media_type="application/ld+json")
```

### O5-2: 데이터 품질 대시보드 (I18)

**신규 파일**: `services/synapse/app/services/quality_service.py`

```python
class OntologyQualityService:
    async def generate_report(self, case_id: str) -> dict:
        return {
            "orphan_count": ...,         # 관계 없는 노드 수
            "low_confidence_count": ..., # verified=false 노드 수
            "missing_description": ...,  # description 없는 노드 수
            "duplicate_names": ...,      # 동일 이름 노드 수
            "total_nodes": ...,
            "total_relations": ...,
            "coverage_by_layer": {       # 계층별 커버리지
                "kpi": {"total": 5, "verified": 3, "orphan": 1},
                ...
            },
        }
```

**FE 컴포넌트**: `apps/canvas/src/pages/ontology/components/QualityDashboard.tsx`
- 품질 지표 카드 (orphan, low confidence, missing description)
- 계층별 커버리지 bar chart

### O5-3: HITL 리뷰 UI (I17)

`ontology-model.md`에 정의된 HITL 생명주기:
1. AI 추출 → `hitl_review_queue` 등록
2. 리뷰어 Approve → `verified=true` 업데이트
3. 리뷰어 Reject → 노드 삭제

**PostgreSQL Migration**: `services/synapse/migrations/` — hitl_review_queue 테이블

```sql
CREATE TABLE hitl_review_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    reviewer_id UUID,
    status TEXT DEFAULT 'pending',  -- pending, approved, rejected
    submitted_at TIMESTAMPTZ DEFAULT now(),
    reviewed_at TIMESTAMPTZ,
    review_comment TEXT
);
```

**FE 컴포넌트**: `apps/canvas/src/pages/ontology/components/HITLReviewQueue.tsx`
- 대기 중인 리뷰 항목 리스트
- Approve / Reject 버튼
- 리뷰 코멘트 입력

### O5-4: 온톨로지 버전 관리 (I20)

**작업**: Neo4j에 `OntologySnapshot` 노드 추가

```cypher
CREATE (s:OntologySnapshot {
    id: $snapshot_id,
    case_id: $case_id,
    created_at: datetime(),
    node_count: $node_count,
    relation_count: $relation_count,
    snapshot_data: $json_blob
})
```

**Diff 기능**:

```python
async def diff_snapshots(self, snapshot_id_a: str, snapshot_id_b: str) -> dict:
    return {
        "added_nodes": [...],
        "removed_nodes": [...],
        "modified_nodes": [...],
        "added_relations": [...],
        "removed_relations": [...],
    }
```

### O5-5: GlossaryTerm ↔ Ontology 브릿지 (I15)

**작업**: GlossaryTerm(tenant_id)과 Ontology 노드(case_id) 간 `DEFINES` 관계 생성

**Neo4j 스키마** (bootstrap v2.2.0):

```cypher
CREATE INDEX glossary_defines IF NOT EXISTS
  FOR ()-[r:DEFINES]-() ON (r.created_at)
```

**자동 후보 매칭**: GlossaryTerm.name과 OntologyNode.name의 fulltext similarity 기반

```cypher
CALL db.index.fulltext.queryNodes('ontology_fulltext', $term_name)
YIELD node, score
WHERE score > 0.5
  AND node.case_id = $case_id
RETURN node.id, node.name, node.layer, score
ORDER BY score DESC
LIMIT 5
```

### Phase O5 수정 파일 요약

| 파일 | 변경 | 위험도 |
| --- | --- | --- |
| `services/synapse/app/services/ontology_exporter.py` | CREATE (O5-1) | LOW |
| `services/synapse/app/services/quality_service.py` | CREATE (O5-2) | LOW |
| `services/synapse/app/api/graph.py` | MODIFY (+export, +quality, +hitl) | LOW |
| `services/synapse/migrations/` | CREATE (hitl_review_queue) | MEDIUM |
| `services/synapse/app/graph/neo4j_bootstrap.py` | MODIFY (v2.2.0 — DEFINES index) | LOW |
| `services/synapse/requirements.txt` | MODIFY (+rdflib) | LOW |
| `apps/canvas/src/pages/ontology/components/QualityDashboard.tsx` | CREATE | LOW |
| `apps/canvas/src/pages/ontology/components/HITLReviewQueue.tsx` | CREATE | MEDIUM |

### Gate O5 판정 기준

- [x] `GET /export?format=turtle&case_id=xxx` → valid Turtle RDF 반환
- [x] `GET /export?format=jsonld&case_id=xxx` → valid JSON-LD 반환
- [x] 품질 리포트: orphan_count, low_confidence_count, missing_description 반환
- [x] 계층별 커버리지 데이터 정확 (total / verified / orphan)
- [x] HITL Approve → Neo4j 노드 `verified=true` 업데이트
- [x] HITL Reject → 노드 삭제 + review_queue 상태 업데이트
- [x] 2개 스냅샷 diff: 추가/삭제/수정 노드 포함
- [x] GlossaryTerm "매출" → Ontology Revenue:Measure 자동 후보 제안
