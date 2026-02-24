# Ontology Phase O1-O2: FE-BE 연동 + Concept-Schema 매핑

> **상위 문서**: [04d_nl2sql-ontology-gap-analysis.md](04d_nl2sql-ontology-gap-analysis.md)
> **해결 항목**: I1-I8

---

## Phase O1: FE-BE 연동 (I1-I5)

### O1-1: 라우팅 교체

**문제 (I1)**: `routeConfig.tsx:81` → `OntologyBrowser`(stub, 3개 mock 노드). 완성된 `OntologyPage`(78 lines, ForceGraph2D)는 dead code

**수정 파일**: `apps/canvas/src/lib/routes/routeConfig.tsx`

**작업**:
- Line 22: lazy import `OntologyBrowser` → `OntologyPage`로 변경
- Line 81: element를 `<OntologyPage />` 로 변경

```typescript
// Before
const OntologyBrowser = lazy(() => import('@/pages/ontology/OntologyBrowser'));

// After
const OntologyPage = lazy(() => import('@/pages/ontology/OntologyPage'));
```

### O1-2: Synapse Ontology API 클라이언트 생성

**문제 (I2)**: `synapseApi` 인스턴스 존재(`clients.ts:21`)하나 ontology 함수 0개. `useOntologyMock`이 14개 하드코딩 노드 반환

**신규 파일**: `apps/canvas/src/features/ontology/api/ontologyApi.ts`

**구현할 함수** (`synapseApi` 래핑):

| 함수 | HTTP | Synapse Endpoint | 비고 |
| --- | --- | --- | --- |
| `getCaseOntology(caseId, options?)` | GET | `/api/v3/synapse/ontology/cases/{caseId}/ontology` | layer, verified_only, limit, offset |
| `getCaseSummary(caseId)` | GET | `/api/v3/synapse/ontology/cases/{caseId}/ontology/summary` | 통계 |
| `getNodeNeighbors(nodeId, limit?)` | GET | `/api/v3/synapse/ontology/nodes/{nodeId}/neighbors` | default limit=100 |
| `findPath(sourceId, targetId, maxDepth?)` | GET | `/api/v3/synapse/ontology/nodes/{sourceId}/path-to/{targetId}` | default maxDepth=6 |
| `createNode(payload)` | POST | `/api/v3/synapse/ontology/nodes` | case_id, layer, labels, properties |
| `updateNode(nodeId, payload)` | PUT | `/api/v3/synapse/ontology/nodes/{nodeId}` | layer, labels, properties |
| `deleteNode(nodeId)` | DELETE | `/api/v3/synapse/ontology/nodes/{nodeId}` | 관계 cascade |
| `searchOntology(query)` | POST | `/api/v3/synapse/graph/search` | 서버사이드 fulltext |

### O1-3: useOntologyData hook 생성

**문제 (I3)**: BE 응답 타입과 FE 타입 불일치
- BE: `{nodes[].layer, relations[].source_id, relations[].target_id}`
- FE: `OntologyNode.label, OntologyEdge.source (string|OntologyNode)`

**신규 파일**: `apps/canvas/src/features/ontology/hooks/useOntologyData.ts`

**핵심 로직**:

```typescript
// BE 응답 → FE 타입 변환
function transformNode(beNode: SynapseNode): OntologyNode {
  return {
    id: beNode.id,
    label: beNode.properties?.name || beNode.labels?.[0] || beNode.id,
    layer: beNode.layer as OntologyLayer,
    type: beNode.properties?.type || beNode.labels?.[0],
    properties: beNode.properties || {},
  };
}

function transformEdge(beRel: SynapseRelation): OntologyEdge {
  return {
    source: beRel.source_id,
    target: beRel.target_id,
    type: mapRelationType(beRel.type),
    label: beRel.type,
    properties: beRel.properties || {},
  };
}
```

**교체 대상**:
- `OntologyPage.tsx:3` — `useOntologyMock` → `useOntologyData`
- `NodeDetail.tsx:2` — mock 데이터 → 실 데이터

### O1-4: Case Context 전달

**문제 (I4)**: BE `OntologyService` 모든 메서드가 `case_id` 필수. FE `OntologyPage`에 case_id 개념 없음

**수정 파일**:
- `apps/canvas/src/features/ontology/store/useOntologyStore.ts` — `caseId: string | null` 상태 추가
- `apps/canvas/src/pages/ontology/OntologyPage.tsx` — URL query param `?caseId=xxx` 파싱 또는 case selector 추가

**구현 방식**: URL searchParams에서 caseId 추출 → store 저장 → API 호출 시 전달

```typescript
const [searchParams] = useSearchParams();
const caseId = searchParams.get('caseId');
useEffect(() => { if (caseId) setCaseId(caseId); }, [caseId]);
```

### O1-5: SearchPanel 서버사이드 전환

**문제 (I16 관련)**: `SearchPanel.tsx`는 클라이언트사이드 필터만 수행. Neo4j `ontology_fulltext` + `schema_fulltext` 인덱스 미활용

**수정 파일**: `apps/canvas/src/pages/ontology/components/SearchPanel.tsx`

**작업**: 기존 300ms debounce 유지하되, `ontologyApi.searchOntology(query)` 서버 호출로 전환

### Phase O1 수정 파일 요약

| 파일 | 변경 | 위험도 |
| --- | --- | --- |
| `apps/canvas/src/lib/routes/routeConfig.tsx` | MODIFY (라우팅) | LOW |
| `apps/canvas/src/features/ontology/api/ontologyApi.ts` | CREATE | LOW |
| `apps/canvas/src/features/ontology/hooks/useOntologyData.ts` | CREATE | MEDIUM |
| `apps/canvas/src/features/ontology/store/useOntologyStore.ts` | MODIFY (caseId) | LOW |
| `apps/canvas/src/pages/ontology/OntologyPage.tsx` | MODIFY (hook 교체) | MEDIUM |
| `apps/canvas/src/pages/ontology/components/NodeDetail.tsx` | MODIFY (hook 교체) | LOW |
| `apps/canvas/src/pages/ontology/components/SearchPanel.tsx` | MODIFY (API 호출) | LOW |

### Gate O1 판정 기준

- [x] `/data/ontology?caseId=xxx` 접속 시 ForceGraph2D에 **실제** 그래프 렌더링 (3 mock 노드가 아님)
- [x] `ontologyApi.getCaseOntology(caseId)` 호출 시 Synapse API 200 응답
- [x] LayerFilter "Process" 해제 시 Process 노드 그래프에서 제거
- [x] 2 노드 순서 클릭 → BE `path-to` API 호출 → 경로 하이라이트
- [x] Synapse 503 시 에러 메시지 표시 (빈 화면 아님)
- [x] 빈 ontology (노드 0개) 시 "데이터가 없습니다" EmptyState 표시

---

## Phase O2: Concept-Schema 매핑 (I6-I8)

> **리스크 경고**: ConceptMapView UI 복잡도 (리스크 3). 2단계 점진적 구현 적용.

### O2-1: Neo4j 스키마 확장 (Schema v2.1.0)

**문제 (I6, I7)**: GlossaryTerm↔Table 관계(edge) 없음. Ontology(case_id)와 Schema(tenant_id)가 별도 그래프 영역

**수정 파일**: `services/synapse/app/graph/neo4j_bootstrap.py`

**추가할 스키마**:

```cypher
-- 관계 인덱스
CREATE INDEX maps_to_index IF NOT EXISTS
  FOR ()-[r:MAPS_TO]-() ON (r.created_at)

CREATE INDEX derived_from_index IF NOT EXISTS
  FOR ()-[r:DERIVED_FROM]-() ON (r.created_at)

CREATE INDEX defines_index IF NOT EXISTS
  FOR ()-[r:DEFINES]-() ON (r.created_at)
```

**3-hop 브릿지 관계 모델** (리스크 2 완화):

```cypher
(g:GlossaryTerm {tenant_id: $tid})
  -[:DEFINES]->
(o:Resource|Process|Measure|KPI {case_id: $cid})
  -[:MAPS_TO]->
(t:Table {tenant_id: $tid, datasource: $ds})
```

`SCHEMA_VERSION`을 `"2.1.0"`으로 업데이트.

### O2-2: MetadataGraphService concept mapping CRUD

**수정 파일**: `services/synapse/app/services/metadata_graph_service.py`

**추가할 메서드**:

| 메서드 | 설명 | Cypher |
| --- | --- | --- |
| `create_concept_mapping(source_id, target_id, rel_type, props)` | 매핑 관계 생성 | `MATCH (a) WHERE a.id=$src MATCH (b) WHERE b.id=$tgt CREATE (a)-[r:{rel_type}]->(b)` |
| `list_concept_mappings(case_id, tenant_id)` | 특정 case의 모든 매핑 조회 | `MATCH (o)-[r:MAPS_TO]->(t:Table) WHERE o.case_id=$cid RETURN o, r, t` |
| `delete_concept_mapping(rel_id)` | 매핑 삭제 | `MATCH ()-[r]-() WHERE id(r)=$rid DELETE r` |
| `list_schema_concepts(tenant_id, datasource)` | 매핑 가능한 Table 목록 | `MATCH (t:Table) WHERE t.tenant_id=$tid RETURN t` |
| `auto_suggest_mappings(query, tenant_id)` | fulltext 기반 자동 후보 | `CALL db.index.fulltext.queryNodes('schema_fulltext', $q) YIELD node, score` |

### O2-3: Synapse concept-mapping API

**신규 파일**: `services/synapse/app/api/concept_mapping.py`

**Router prefix**: `/api/v3/synapse/ontology/concept-mappings`

| Method | Route | 설명 |
| --- | --- | --- |
| POST | `/` | 매핑 생성 (source_id, target_id, rel_type) |
| GET | `/` | 매핑 목록 (case_id, tenant_id) |
| DELETE | `/{rel_id}` | 매핑 삭제 |
| GET | `/suggest?q={query}` | fulltext 기반 자동 후보 |
| GET | `/schema-entities` | 매핑 가능한 Table/Column 목록 |

**수정 파일**: `services/synapse/app/main.py` — router 등록

### O2-4: Canvas ConceptMapView (Phase A — CRUD 리스트)

> 리스크 3 완화: 1차는 CRUD 리스트 UI. 시각 연결선은 Phase B (O4와 병합).

**신규 파일**: `apps/canvas/src/pages/ontology/components/ConceptMapView.tsx`

**Phase A UI 구성**:
- 좌측: GlossaryTerm 검색 + 목록
- 우측: Table 드롭다운 선택
- 중앙: "매핑 추가" 버튼 → API POST
- 하단: 기존 매핑 리스트 (삭제 가능)
- 상단: "자동 후보 제안" 버튼 → `/suggest` API 호출

**Phase B (후순위)**: ForceGraph2D bipartite layout 또는 Sankey 다이어그램

### O2-5: OntologyPage 뷰 모드 확장

**수정 파일**: `apps/canvas/src/pages/ontology/OntologyPage.tsx`

**변경**: 기존 `isTableMode: boolean` → 3-mode 전환

```typescript
type ViewMode = 'graph' | 'conceptMap' | 'table';
```

**수정 파일**: `apps/canvas/src/features/ontology/store/useOntologyStore.ts` — viewMode 상태 추가

### O2-6: ontologyApi 확장

**수정 파일**: `apps/canvas/src/features/ontology/api/ontologyApi.ts`

**추가할 함수**:
- `getConceptMappings(caseId)`
- `createConceptMapping(sourceId, targetId, relType)`
- `deleteConceptMapping(relId)`
- `suggestMappings(query)`
- `getSchemaEntities(datasource?)`

### Phase O2 수정 파일 요약

| 파일 | 변경 | 위험도 |
| --- | --- | --- |
| `services/synapse/app/graph/neo4j_bootstrap.py` | MODIFY (v2.1.0) | MEDIUM |
| `services/synapse/app/services/metadata_graph_service.py` | MODIFY (+5 메서드) | MEDIUM |
| `services/synapse/app/api/concept_mapping.py` | CREATE | LOW |
| `services/synapse/app/main.py` | MODIFY (router) | LOW |
| `apps/canvas/src/features/ontology/api/ontologyApi.ts` | MODIFY (+5 함수) | LOW |
| `apps/canvas/src/pages/ontology/components/ConceptMapView.tsx` | CREATE (Phase A) | MEDIUM |
| `apps/canvas/src/pages/ontology/OntologyPage.tsx` | MODIFY (3-mode) | LOW |
| `apps/canvas/src/features/ontology/store/useOntologyStore.ts` | MODIFY (viewMode) | LOW |

### Gate O2 판정 기준

- [x] Neo4j Schema v2.1.0: `MAPS_TO`, `DERIVED_FROM`, `DEFINES` 관계 인덱스 존재
- [x] `POST /concept-mappings` 후 Neo4j에 `MAPS_TO` 관계 존재 (Cypher 검증)
- [x] 특정 Table에 매핑된 GlossaryTerm 역조회 정확
- [x] "매출" 검색 시 "revenue" 테이블 자동 후보 제안 (fulltext)
- [x] ConceptMapView: GlossaryTerm 목록 + Table 드롭다운 렌더링 (Phase A)
- [x] 매핑 생성/삭제 후 목록 즉시 반영
- [x] OntologyPage에서 Graph / Concept Map / Table 3-mode 전환 동작
