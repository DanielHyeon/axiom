# Insight View Phase 2 — 구현 완료 보고

<!-- affects: frontend, weaver-api -->
<!-- status: COMPLETED -->
<!-- created: 2026-02-27 -->
<!-- completed: 2026-02-27 -->

## 이 문서의 목적

[`insight-view.md`](./insight-view.md)의 **Phase 2 미구현 항목** 7개의
구현 계획 및 실제 구현 결과를 기록한다.

---

## 0. 항목별 구현 결과

| # | 항목 | 파일 경로 | 결과 |
| --- | --- | --- | --- |
| 1 | TimeRangeSelector | `features/insight/components/TimeRangeSelector.tsx` | 완료 |
| 2 | DriverRankingPanel | `features/insight/components/DriverRankingPanel.tsx` | 완료 |
| 3 | NodeDetailPanel | `features/insight/components/NodeDetailPanel.tsx` | 완료 |
| 4 | PathComparisonPanel | `features/insight/components/PathComparisonPanel.tsx` | 완료 |
| 5 | useDriverDetail | `features/insight/hooks/useDriverDetail.ts` | 완료 (stub) |
| 6 | scoreCalculator.ts | `features/insight/utils/scoreCalculator.ts` | 완료 |
| 7 | fingerprintUtils.ts | `features/insight/utils/fingerprintUtils.ts` | 완료 |

---

## 1. 화면 레이아웃

계획대로 3컬럼 + 상단바 구조로 확장됐다.

```text
┌───────────────────────────────────────────────────────────┐
│  InsightHeader  (TimeRangeSelector)                        │  ← 상단 바
├─────────────────┬──────────────────────┬───────────────────┤
│                 │                      │                   │
│  InsightSidebar │  ImpactGraphViewer   │  NodeDetailPanel  │
│  - KpiSelector  │                      │  (선택 시 열림)   │
│  - DriverRanking│  + PathComparison    │  (w-72)           │
│  Panel (w-60)   │    Panel (하단)      │                   │
│                 │  + MetaBar           │                   │
└─────────────────┴──────────────────────┴───────────────────┘
```

---

## 2. Zustand 스토어 확장 결과

계획 대비 실제 구현된 상태:

```typescript
// 계획과 다른 점:
// - driverRankings, driverRankingLoading, driverRankingError → 제거 (그래프에서 직접 파생)
// - nodeDetail, nodeDetailLoading, nodeDetailError → 제거 (GraphNode + CompactEvidence 직접 사용)
// - topPaths, pathCompareMode → 제거 (impactPaths + highlightedPaths로 대체)
// - selectedNodeId → selectedDriverId 로 명칭 변경

{
  // 신규 추가된 상태
  impactEvidence: Record<string, CompactEvidence[]> | null;
  impactPaths: ImpactPath[];
  hoveredNodeId: string | null;
  highlightedPaths: string[];

  // 신규 추가된 액션
  setImpactEvidence, setImpactPaths, setHoveredNodeId, togglePath
}
```

---

## 3. 신규 타입 정의 결과

`features/insight/types/insight.ts`에 추가된 타입:

```typescript
// 실제 추가 (계획의 NodeDetail, ImpactPathSummary 대신 더 간결한 구조 채택)

export interface CompactEvidence {
  query_hash: string;
  snippet?: string;
  tables?: string[];
  score?: number;
}

export interface BackendPath {
  nodes: string[];
  score?: number;
  why?: string;
}

export interface DriverRankItem {
  node_id: string;
  label: string;
  node_type: 'DRIVER' | 'DIMENSION';
  score: number;
  evidence_count: number;
}

// ImpactPath (기존 타입 유지, path_id + strength 필드 추가)
// EdgeType: INFLUENCES | COUPLED | EXPLAINS_BY 추가
// GraphNode: meta?: Record<string, unknown> 추가
// GraphEdge: id?: string, meta?: Record<string, unknown> 추가
// JobStatusResponse.graph: evidence?: Record<string, CompactEvidence[]> 추가
```

---

## 4. Sprint별 구현 내용

### Sprint A — 기반 (fingerprintUtils + TimeRangeSelector)

**구현 내용:**

- `fingerprintUtils.ts`: `getFingerprintFromParams(searchParams)` — URL `?fp=` 파라미터 추출
- `TimeRangeSelector.tsx`: 7d / 30d / 90d 세그먼트 버튼, `useInsightStore.setTimeRange` 연결
- `InsightHeader.tsx`: TimeRangeSelector 포함한 상단 바
- `InsightPage.tsx` URL 동기화: `useSearchParams` + `useEffect([selectedKpiFingerprint, timeRange, selectedDriverId])`

**계획 대비 차이점:**

- `syncStoreFromUrl` / `syncUrlFromStore` 대신 `useSearchParams` + `useEffect`로 직접 구현
- `kpi` 파라미터 대신 `fp` 파라미터 사용 (기존 KpiSelector 방식 유지)
- `path` 파라미터는 구현하지 않음 (경로 선택은 세션 상태로만 유지)

---

### Sprint B — 탐색 (scoreCalculator + DriverRankingPanel)

**구현 내용:**

- `scoreCalculator.ts`: `deriveDriverRankings(graph, impactEvidence)` — DRIVER/DIMENSION 노드를 score 내림차순으로 정렬, evidence_count 포함
- `DriverRankingPanel.tsx`: 검색 필터, DRIVER(TrendingUp)/DIMENSION(Layers) 아이콘 구분, hover → `onHoverDriver?.(nodeId)`
- `ImpactGraphViewer.tsx`: `hoveredNodeId` prop 추가 + `useEffect`로 Cytoscape `hovered` CSS 클래스 토글
- `graphTransformer.ts`: `node.hovered` 스타일 추가 (황색 링, 3px)

**계획 대비 차이점:**

- 정렬 토글(score/evidence_count) 미구현 (score desc 고정)
- delta(전기간 대비 변화) 미구현 — API가 제공하지 않음

---

### Sprint C — 근거 (useDriverDetail + NodeDetailPanel)

**구현 내용:**

- `useDriverDetail.ts`: close 핸들러만 반환하는 stub (`() => selectDriver(null)`)
  - 이유: `GET /api/insight/nodes/{node_id}` Weaver endpoint 미구현
  - 노드 데이터는 `impactGraph.nodes`에서, Evidence는 `impactEvidence`에서 직접 읽음
- `NodeDetailPanel.tsx`: GraphNode + CompactEvidence 기반으로 완전 재작성
  - 노드 type 아이콘/색상 (KPI: Target, DRIVER: TrendingUp, DIMENSION: Layers)
  - score 표시
  - Breakdown: `GraphNode.meta`를 `Record<string, number>`로 해석, 8개 키 한글 레이블 매핑
  - Evidence: `CompactEvidence[]` 쿼리 목록 (snippet 있으면 표시)
  - CSS custom property `--bar-w`로 progress bar 너비 (inline style lint 우회)

**BREAKDOWN_LABELS 매핑:**

| key | 한글 레이블 |
| --- | --- |
| usage | 사용 빈도 |
| kpi_connection | KPI 연결 강도 |
| centrality | 중심성 |
| discriminative | 판별력 |
| volatility | 변동성 |
| cardinality_adjust | 카디널리티 보정 |
| sample_size_guard | 샘플 크기 보정 |
| cooccur_with_kpi | KPI 동시 출현 |

---

### Sprint D — 비교 (PathComparisonPanel + useImpactGraph 확장)

**구현 내용:**

- `useImpactGraph.ts`: `transformPaths()` 추가
  - `BackendPath[]` → `ImpactPath[]` 변환 (path_id는 `path_0`, `path_1` 형식으로 생성, score → strength 매핑)
  - job 완료 시 `store.setImpactPaths()`, `store.setImpactEvidence()` 호출
- `PathComparisonPanel.tsx`: 완전 재작성
  - `strength` 기준 Top 3 정렬
  - 체크박스 toggle → `store.highlightedPaths` 업데이트
  - 색상: `bg-rose-500 / bg-blue-500 / bg-violet-400` (Tailwind 클래스, inline style 미사용)
  - `nodeLabels` prop으로 노드 ID → 레이블 변환
- `InsightPage.tsx`: `nodeLabels` 맵 생성 후 PathComparisonPanel에 전달

**계획 대비 차이점:**

- `derivePaths(graph, rawPaths)` 대신 `transformPaths(paths, kpiFingerprint)` 방식으로 구현
- 경로 점수는 backend `score` 값 그대로 사용 (calcPathScore 미구현)

---

### Sprint E — API 교체 (예정)

Weaver에 `GET /api/insight/nodes/{node_id}` endpoint 구현 후 진행.

- `useDriverDetail.ts` stub → 전용 API 호출로 교체
- Evidence 상세화: snippet, timestamp, confidence 등 추가

---

## 5. 파일 변경 실제 결과

| 파일 | 변경 종류 | 실제 내용 |
| --- | --- | --- |
| `features/insight/types/insight.ts` | 수정 | CompactEvidence, BackendPath, DriverRankItem 추가; EdgeType INFLUENCES/COUPLED/EXPLAINS_BY 추가; GraphNode.meta, GraphEdge.id 추가 |
| `features/insight/store/useInsightStore.ts` | 수정 | impactEvidence, impactPaths, hoveredNodeId, highlightedPaths 추가 |
| `features/insight/utils/scoreCalculator.ts` | 수정 | deriveDriverRankings(graph, impactEvidence) 추가 |
| `features/insight/utils/fingerprintUtils.ts` | 수정 | getFingerprintFromParams 추가 |
| `features/insight/utils/graphTransformer.ts` | 수정 | INFLUENCES/COUPLED/EXPLAINS_BY 엣지 스타일 추가; DRIVER 노드 크기 버그 수정 (38 + score * 52); hovered CSS 클래스 추가 |
| `features/insight/components/TimeRangeSelector.tsx` | 신규 | 7d/30d/90d 세그먼트 버튼 |
| `features/insight/components/DriverRankingPanel.tsx` | 재작성 | 검색, hover, DRIVER/DIMENSION 구분 |
| `features/insight/components/NodeDetailPanel.tsx` | 재작성 | GraphNode + CompactEvidence 기반, Breakdown 바 |
| `features/insight/components/PathComparisonPanel.tsx` | 재작성 | ImpactPath Top 3, 체크박스 토글, Tailwind 색상 |
| `features/insight/hooks/useDriverDetail.ts` | 재작성 | close 핸들러 stub |
| `features/insight/hooks/useImpactGraph.ts` | 수정 | transformPaths 추가; evidence/paths 스토어 저장 |
| `features/insight/components/ImpactGraphViewer.tsx` | 수정 | hoveredNodeId prop; hovered CSS 클래스 토글 |
| `pages/insight/InsightPage.tsx` | 재작성 | 3컬럼 레이아웃, URL 동기화, 모든 패널 연결 |
| `pages/insight/components/InsightHeader.tsx` | 신규 | 상단 바 (TimeRangeSelector 포함) |
| `pages/insight/components/InsightSidebar.tsx` | 수정 | impactEvidence, onHoverDriver props 추가 |
| `services/weaver/app/services/impact_graph_builder.py` | 수정 | 중복 노드 ID 버그 수정 (score 비교로 DRIVER/DIMENSION 단독 할당) |

---

## 6. 버그 수정 이력

### 중복 Cytoscape 노드 ID

- **원인**: `score_candidates()` 결과에서 동일 컬럼이 DRIVER/DIMENSION 양쪽에 모두 포함
- **수정**: `impact_graph_builder.py` — score가 높은 쪽 role로만 단독 할당
- **결과**: 11 nodes (1 KPI + 4 DRIVER + 6 DIMENSION), 29 edges, 3 paths, 중복 0

### DRIVER 노드 크기 거의 동일

- **원인**: `score/100 * 60` 계산 — score가 0~1이므로 실질적으로 ~0.6px 차이
- **수정**: `38 + score * 52` — score=0이면 38px, score=1이면 90px

### INFLUENCES/COUPLED/EXPLAINS_BY 엣지 스타일 미적용

- **원인**: `EDGE_STYLES` 맵에 해당 타입 누락 → JOIN 스타일 fallback (회색 실선)
- **수정**: `graphTransformer.ts`에 3개 타입 명시적 추가

---

## 관련 문서

- 기능 문서: [`insight-view.md`](./insight-view.md)
- 전체 설계: [`docs/insight-view-implementation.md`](../../../../docs/insight-view-implementation.md)
- API SSOT: [`docs/02_api/service-endpoints-ssot.md`](../../../../docs/02_api/service-endpoints-ssot.md)

---

## 변경 이력

| 날짜 | 버전 | 작성자 | 내용 |
| --- | --- | --- | --- |
| 2026-02-27 | 1.0 | Axiom Team | Phase 2 잔여 항목 구현 계획 초안 |
| 2026-02-27 | 2.0 | Axiom Team | Phase 2 전체 구현 완료 — 계획 대비 실제 결과 업데이트 |
