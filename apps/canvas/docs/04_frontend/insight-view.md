# Insight View 기능 문서

<!-- affects: frontend, weaver-api -->
<!-- requires-update: 04_frontend/routing.md, 04_frontend/directory-structure.md -->

## 이 문서가 답하는 질문

- Insight View(`/analysis/insight`)의 역할과 구조는 무엇인가?
- KPI Impact Graph와 NL2SQL Query Subgraph는 어떻게 다른가?
- Weaver API와 어떻게 연동하는가?
- 202 비동기 패턴은 어떻게 처리하는가?

---

## 1. 개요

Insight View는 KPI 중심 영향 분석(Impact Graph)을 시각화하는 전용 페이지다.
NL2SQL 페이지의 Graph 탭은 SQL 쿼리 구조를 서브그래프로 시각화한다.

| 기능 | 위치 | 목적 | API |
| --- | --- | --- | --- |
| Impact Graph | `/analysis/insight` | KPI → Driver 영향 경로 분석 | `POST /api/insight/impact` |
| Query Subgraph | NL2SQL Graph 탭 | SQL 테이블/컬럼/조건 구조 시각화 | `POST /api/insight/query-subgraph` |

---

## 2. 라우트 및 진입점

```text
/analysis/insight  →  InsightPage  (MainLayout, ProtectedRoute)
```

- 라우트 상수: `ROUTES.ANALYSIS.INSIGHT = '/analysis/insight'`
- 사이드바: 분석 섹션 `Lightbulb` 아이콘 → Insight 항목
- `pages/insight/InsightPage.tsx` — 메인 페이지 컴포넌트

---

## 3. 파일 구조

```text
features/insight/
├── api/
│   └── insightApi.ts           # Weaver API 클라이언트 함수
├── components/
│   ├── DriverRankingPanel.tsx  # Driver/Dimension 순위 목록 (검색 + hover 연동)
│   ├── ImpactGraphViewer.tsx   # Cytoscape.js Impact Graph 렌더러
│   ├── KpiSelector.tsx         # KPI fingerprint 입력 컴포넌트
│   ├── NodeDetailPanel.tsx     # 노드 상세 + Breakdown + Evidence 패널
│   ├── PathComparisonPanel.tsx # Top 3 경로 비교 체크박스 토글
│   ├── QuerySubgraphViewer.tsx # SQL → 서브그래프 렌더러
│   └── TimeRangeSelector.tsx   # 기간 필터 세그먼트 버튼 (7d/30d/90d)
├── hooks/
│   ├── useDriverDetail.ts      # 노드 close 핸들러 (Phase 3에서 API 연결 예정)
│   └── useImpactGraph.ts       # 202 async 폴링 + paths/evidence 파싱 훅
├── store/
│   └── useInsightStore.ts      # Zustand 상태 관리
├── types/
│   └── insight.ts              # GraphData, GraphNode, GraphEdge, CompactEvidence 등
└── utils/
    ├── fingerprintUtils.ts     # fingerprint URL 딥링크 인코딩/디코딩
    ├── graphTransformer.ts     # API 응답 → Cytoscape elements 변환
    └── scoreCalculator.ts      # 그래프 파생 Driver 순위 계산 유틸

pages/insight/
├── InsightPage.tsx             # 메인 페이지 (3컬럼 레이아웃 + URL 동기화)
└── components/
    ├── InsightHeader.tsx       # 상단 바 (TimeRangeSelector 포함)
    └── InsightSidebar.tsx      # 좌측 패널 (KpiSelector + DriverRankingPanel)

pages/nl2sql/components/
└── QueryGraphPanel.tsx         # NL2SQL Graph 탭 → QuerySubgraphViewer 래퍼
```

---

## 4. API 연동

### 4.1 Impact Graph (202 비동기 패턴)

```typescript
// POST /api/insight/impact
// 캐시 히트 → 200 + { graph }
// 캐시 미스 → 202 + { job_id }

const result = await requestImpact({ kpi_fingerprint, datasource_id });
if (isJobResponse(result)) {
  // 폴링: GET /api/insight/jobs/{job_id}
  // useImpactGraph 훅이 자동 처리 (2초 간격)
}
```

### 4.2 Query Subgraph

```typescript
// POST /api/insight/query-subgraph
// 요청: { sql, datasource? }
// 응답: { parse_result: { mode, confidence, tables, ... }, graph, trace_id }

const res = await postQuerySubgraph({ sql });
// res.graph → { nodes: [...], edges: [...] }
// res.parse_result.mode → 'primary' | 'fallback' | 'failed'
// res.parse_result.confidence → 0.0 ~ 1.0
```

---

## 5. 그래프 노드/엣지 타입

### Impact Graph 노드

| 노드 타입 | 형태/색상 | 설명 |
| --- | --- | --- |
| `KPI` | star / 파랑 | 핵심 성과 지표 |
| `DRIVER` | round-rect / 에메랄드 | KPI에 영향을 주는 변수; 크기는 score에 비례 |
| `DIMENSION` | octagon / 보라 | 분류 축 (GROUP BY); 크기는 score에 비례 |
| `TRANSFORM` | diamond / 노랑 | 중간 집계/변환 |
| `TABLE` | rectangle / 회색 | 테이블 |
| `COLUMN` | ellipse / 청록 | 컬럼 |

### Impact Graph 엣지

| 엣지 타입 | 스타일 | 설명 |
| --- | --- | --- |
| `INFLUENCES` | 실선 빨강 3px | Driver → KPI 직접 영향 |
| `COUPLED` | 점선 회색 1.5px | 노드 간 상관 관계 |
| `EXPLAINS_BY` | 점선 보라 1.5px | 파생/설명 관계 |
| `AGGREGATE` | 실선 초록 3px | 집계 |
| `GROUP_BY` | 실선 보라 2px | 그룹화 |
| `WHERE_FILTER` | 점선 주황 2px | 필터 조건 |
| `DERIVE` | 점선 보라 2px | 파생 |

### Query Subgraph 노드

| 노드 타입 | 색상 | 설명 |
| --- | --- | --- |
| `TABLE` | 파랑 | FROM/JOIN 테이블 |
| `COLUMN` | 초록 | SELECT 컬럼 |
| `PREDICATE` | 주황 | WHERE 조건식 |

### Query Subgraph 엣지

| 엣지 타입 | 설명 |
| --- | --- |
| `DERIVE` | TABLE → COLUMN |
| `JOIN` | TABLE ↔ TABLE |
| `WHERE_FILTER` | PREDICATE → TABLE |
| `GROUP_BY` | COLUMN → TABLE |

---

## 6. Cytoscape 레이아웃

| 그래프 | 레이아웃 | 설정 |
| --- | --- | --- |
| Impact Graph | `cose-bilkent` | 물리 기반, depth 방향 top-down |
| Query Subgraph | `dagre` | 방향 그래프, `rankDir: 'LR'` |

레이아웃 선택: `graphTransformer.ts`의 `getLayoutConfig(type)` 함수.

---

## 7. 상태 관리 (Zustand)

`useInsightStore`가 관리하는 상태:

```typescript
{
  // KPI 선택
  selectedKpiFingerprint: string | null;
  selectedKpiId: string | null;

  // 기간 필터
  timeRange: '7d' | '30d' | '90d';

  // 그래프 데이터 (Impact Graph 응답에서 파싱)
  impactGraph: GraphData | null;
  impactGraphLoading: boolean;
  impactEvidence: Record<string, CompactEvidence[]> | null; // job 응답 evidence 맵
  impactPaths: ImpactPath[];                                // 변환된 경로 목록

  // 노드/경로 선택 상태
  selectedDriverId: string | null;  // 선택된 노드 → NodeDetailPanel 열림
  hoveredNodeId: string | null;     // DriverRankingPanel hover → Cytoscape 황색 링
  nodeDetailOpen: boolean;          // NodeDetailPanel 표시 여부
  highlightedPaths: string[];       // 체크된 경로 ID 목록

  // Actions
  selectKpi: (kpiId: string, fingerprint: string) => void;
  selectDriver: (driverId: string | null) => void;
  setTimeRange: (tr: TimeRange) => void;
  setHoveredNodeId: (nodeId: string | null) => void;
  togglePath: (pathId: string) => void;
  setImpactEvidence: (ev: Record<string, CompactEvidence[]> | null) => void;
  setImpactPaths: (paths: ImpactPath[]) => void;
}
```

---

## 8. UX 상태별 동작

### Impact Graph 페이지 상태

| 상태 | UI |
| --- | --- |
| KPI 미선택 | 그래프 영역 빈 안내 문구 |
| 로딩 중 | 그래프 영역 스피너 |
| 오류 | AlertCircle + 오류 메시지 + 재시도 버튼 |
| 노드 없음 | Network 아이콘 + "그래프 노드가 없습니다" |
| 정상 | Cytoscape 캔버스 + MetaBar (하단 정보 표시) |
| 노드 선택 | 우측 NodeDetailPanel 열림 (w-72) |
| 경로 하이라이트 | 선택 경로 강조, 나머지 dim (opacity 0.2) |
| DriverPanel hover | 해당 Cytoscape 노드에 황색 링 |

MetaBar: `mode · Queries: {n} · Cached ({ttl}s) · trace: {id}`

### URL 딥링크 파라미터

| 파라미터 | 의미 | 갱신 방식 |
| --- | --- | --- |
| `fp` | KPI fingerprint | replaceState |
| `tr` | time range | replaceState |
| `node` | 선택된 노드 ID | replaceState |

---

## 9. Phase 2 구현 결과

2026-02-27 기준으로 아래 항목이 모두 구현 완료됐다.

| 컴포넌트/유틸 | 구현 방식 |
| --- | --- |
| `DriverRankingPanel` | 그래프 파생(`deriveDriverRankings`), 검색 필터, hover 연동 |
| `NodeDetailPanel` | `GraphNode.meta` breakdown + `CompactEvidence` 쿼리 목록 |
| `PathComparisonPanel` | `ImpactPath[]` Top 3, 체크박스 toggle, Tailwind 색상 클래스 |
| `TimeRangeSelector` | `InsightHeader`에 포함된 세그먼트 버튼 |
| `useDriverDetail` | close 핸들러 stub (Phase 3 API 연결 시 교체 예정) |
| `scoreCalculator.ts` | `deriveDriverRankings(graph, impactEvidence)` 구현 |
| `fingerprintUtils.ts` | `getFingerprintFromParams` + URL 동기화 (`useSearchParams`) |

> Phase 3 예정: `GET /api/insight/nodes/{node_id}` Weaver endpoint 구현 후
> `useDriverDetail`을 전용 API 호출로 교체하면 Evidence 상세화 가능.

---

## 관련 문서

- 전체 설계: [`docs/insight-view-implementation.md`](../../../../docs/insight-view-implementation.md)
- Phase 2 구현 계획: [`04_frontend/insight-view-phase2-plan.md`](./insight-view-phase2-plan.md)
- API SSOT: [`docs/02_api/service-endpoints-ssot.md`](../../../../docs/02_api/service-endpoints-ssot.md)
- 라우트: [`04_frontend/routing.md`](./routing.md)
- 디렉토리: [`04_frontend/directory-structure.md`](./directory-structure.md)

---

## 변경 이력

| 날짜 | 버전 | 작성자 | 내용 |
| --- | --- | --- | --- |
| 2026-02-26 | 1.0 | Axiom Team | 초기 작성 (Phase 1 + Phase 2 핵심 구현 반영) |
| 2026-02-27 | 2.0 | Axiom Team | Phase 2 전체 구현 완료 반영 (파일 구조, 상태, 타입, UX 업데이트) |
