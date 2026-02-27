# Insight 프론트엔드 갭 분석 — 검증 보고서

> **검증일**: 2026-02-27
> **검증 대상**: `apps/canvas/src/features/insight/`, `apps/canvas/src/pages/insight/`, `apps/canvas/src/pages/nl2sql/`
> **결론**: 제출된 갭 분석 문서의 내용은 **대부분 사실과 다름** — 프론트엔드 Phase 1·2 구현은 이미 완료되어 있음

---

## 1. 요약

| 구분 | 갭 문서 주장 | 실제 상태 |
|------|------------|---------|
| `features/insight/` 폴더 | ❌ 없음 | ✅ 존재, 15개 파일 구현 완료 |
| `pages/insight/` 폴더 | ❌ 없음 | ✅ 존재, 3개 파일 구현 완료 |
| 라우트 `ROUTES.ANALYSIS.INSIGHT` | ⚠️ 없음 | ✅ `routes.ts`에 정의됨 |
| `/analysis/insight` 라우트 등록 | ⚠️ 없음 | ✅ `routeConfig.tsx`에 등록됨 |
| Sidebar Insight 메뉴 | ⚠️ 없음 | ✅ 존재 (line 65) |
| `QueryGraphPanel.tsx` | ❌ 없음 | ✅ 존재 (16 LOC, 완전한 wrapper) |
| `ResultPanel.tsx` Graph 탭 | ⚠️ 수정 필요 | ✅ Graph 탭 이미 통합됨 |

**Phase 1·2 프론트엔드 구현 완료율: ~95%** (후술하는 실질 갭은 백엔드 API 3개 + Phase 3 컴포넌트)

---

## 2. Phase 1 — NL2SQL Graph 탭 검증 결과

### ✅ 완료된 파일

| 파일 | LOC | 상태 | 비고 |
|------|-----|------|------|
| [features/insight/types/insight.ts](apps/canvas/src/features/insight/types/insight.ts) | 260 | ✅ 완료 | `GraphNode`, `GraphEdge`, `GraphMeta`, `TimeRange` 등 전체 타입 정의 |
| [features/insight/api/insightApi.ts](apps/canvas/src/features/insight/api/insightApi.ts) | 179 | ✅ 완료 | `requestImpact`, `getJobStatus`, `getQuerySubgraph` 구현 |
| [features/insight/utils/graphTransformer.ts](apps/canvas/src/features/insight/utils/graphTransformer.ts) | 302 | ✅ 완료 | API 응답 → Cytoscape 변환, dagre/cose 레이아웃 선택 로직 포함 |
| [features/insight/components/QuerySubgraphViewer.tsx](apps/canvas/src/features/insight/components/QuerySubgraphViewer.tsx) | 174 | ✅ 완료 | SQL 서브그래프 + confidence 배지 |
| [pages/nl2sql/components/QueryGraphPanel.tsx](apps/canvas/src/pages/nl2sql/components/QueryGraphPanel.tsx) | 16 | ✅ 완료 | `QuerySubgraphViewer` wrapper |
| [pages/nl2sql/components/ResultPanel.tsx](apps/canvas/src/pages/nl2sql/components/ResultPanel.tsx) | 253 | ✅ 완료 | Graph 탭 (`TabId = 'chart' \| 'table' \| 'sql' \| 'graph'`) 통합 완료 |

---

## 3. Phase 2 — Insight 메인 페이지 검증 결과

### ✅ 완료된 파일

| 파일 | LOC | 상태 | 비고 |
|------|-----|------|------|
| [lib/routes/routes.ts](apps/canvas/src/lib/routes/routes.ts) | — | ✅ 완료 | `ROUTES.ANALYSIS.INSIGHT = '/analysis/insight'` 정의됨 |
| [lib/routes/routeConfig.tsx](apps/canvas/src/lib/routes/routeConfig.tsx) | — | ✅ 완료 | RoleGuard 포함 `/analysis/insight` 라우트 등록 |
| [layouts/.../Sidebar.tsx](apps/canvas/src/layouts/components/Sidebar.tsx) | — | ✅ 완료 | `ROUTES.ANALYSIS.INSIGHT` 링크 및 "Insight" 레이블 존재 |
| [features/insight/store/useInsightStore.ts](apps/canvas/src/features/insight/store/useInsightStore.ts) | 161 | ✅ 완료 | Zustand store, `selectedKpiFingerprint`, `impactGraph`, `selectedDriverId` 등 |
| [features/insight/hooks/useImpactGraph.ts](apps/canvas/src/features/insight/hooks/useImpactGraph.ts) | 249 | ✅ 완료 | 202 폴링 로직 (MAX_POLL=30, 5분 타임아웃), 취소/재시도 포함 |
| [features/insight/hooks/useDriverDetail.ts](apps/canvas/src/features/insight/hooks/useDriverDetail.ts) | 21 | ⚠️ **스텁** | `close()` 핸들러만 구현. `GET /api/insight/nodes/{id}` 미구현으로 인한 의도적 스텁 |
| [features/insight/components/ImpactGraphViewer.tsx](apps/canvas/src/features/insight/components/ImpactGraphViewer.tsx) | 232 | ✅ 완료 | Cytoscape.js 렌더링, hover/click 이벤트 |
| [features/insight/components/KpiSelector.tsx](apps/canvas/src/features/insight/components/KpiSelector.tsx) | 89 | ⚠️ **하드코딩** | 샘플 KPI 5개 하드코딩. `GET /api/insight/kpis` 미구현으로 인한 workaround |
| [features/insight/components/DriverRankingPanel.tsx](apps/canvas/src/features/insight/components/DriverRankingPanel.tsx) | 148 | ⚠️ **클라이언트 파생** | 그래프 데이터에서 클라이언트사이드 파생. `GET /api/insight/drivers` 미구현으로 인한 workaround |
| [features/insight/components/NodeDetailPanel.tsx](apps/canvas/src/features/insight/components/NodeDetailPanel.tsx) | 226 | ✅ 완료 | 점수 Breakdown + Evidence 표시 |
| [features/insight/components/PathComparisonPanel.tsx](apps/canvas/src/features/insight/components/PathComparisonPanel.tsx) | 103 | ✅ 완료 | Top 3 경로 비교, 체크박스 토글 |
| [features/insight/components/TimeRangeSelector.tsx](apps/canvas/src/features/insight/components/TimeRangeSelector.tsx) | 37 | ✅ 완료 | 7d/30d/90d pill 버튼 |
| [features/insight/utils/scoreCalculator.ts](apps/canvas/src/features/insight/utils/scoreCalculator.ts) | 91 | ✅ 완료 | Breakdown 표시 유틸 |
| [features/insight/utils/fingerprintUtils.ts](apps/canvas/src/features/insight/utils/fingerprintUtils.ts) | 52 | ✅ 완료 | `?fp=` URL 파라미터 딥링크 |
| [pages/insight/InsightPage.tsx](apps/canvas/src/pages/insight/InsightPage.tsx) | 232 | ✅ 완료 | 3-패널 레이아웃, URL 동기화, deeplink 지원 |
| [pages/insight/components/InsightHeader.tsx](apps/canvas/src/pages/insight/components/InsightHeader.tsx) | 32 | ✅ 완료 | 헤더 + TimeRangeSelector |
| [pages/insight/components/InsightSidebar.tsx](apps/canvas/src/pages/insight/components/InsightSidebar.tsx) | 46 | ✅ 완료 | KpiSelector + DriverRankingPanel 조합 |

---

## 4. Phase 3 — 미구현 확인 (실질 갭)

| 파일 | 상태 | 비고 |
|------|------|------|
| `features/insight/hooks/useKpiTimeseries.ts` | ❌ 없음 | KPI 시계열 훅 미구현 |
| `features/insight/components/KpiMiniChart.tsx` | ❌ 없음 | Driver별 미니차트 미구현 |
| `features/ontology/hooks/useNodeDataPreview.ts` | ❌ 없음 | Ontology coverage API 훅 미구현 |

---

## 5. 백엔드 갭 — 검증 결과

### ✅ 구현된 백엔드 API

| 엔드포인트 | 상태 | 비고 |
|-----------|------|------|
| `POST /api/insight/impact` | ✅ 구현됨 | 200(캐시) / 202(신규 job) 패턴 |
| `GET /api/insight/jobs/{job_id}` | ✅ 구현됨 | 폴링 엔드포인트 |
| `POST /api/insight/query-subgraph` | ✅ 구현됨 | SQL → 서브그래프 |
| `POST /api/insight/logs` | ✅ 구현됨 | 실시간 로그 수집 |
| `POST /api/insight/logs:ingest` | ✅ 구현됨 | 배치 로그 수집 |
| Redis 캐시 저장 | ✅ 구현됨 | `impact_task.py`에서 `_build_cache_key`로 결과 저장 (`ex=TTL_DONE`) |

### ❌ 미구현 백엔드 API (실질 갭)

| 엔드포인트 | 상태 | 프론트 영향 |
|-----------|------|-----------|
| `GET /api/insight/kpis` | ❌ 없음 | `KpiSelector`가 하드코딩 샘플 KPI로 대체 운영 중 |
| `GET /api/insight/drivers` | ❌ 없음 | `DriverRankingPanel`이 그래프 데이터 클라이언트 파생으로 대체 운영 중 |
| `GET /api/insight/nodes/{id}` | ❌ 없음 | `useDriverDetail` 스텁, 상세 Evidence는 store에서 직접 조회 |
| Oracle→Weaver 자동 인제스트 | ❌ 없음 | Oracle `sql_exec.py`가 Weaver `/logs`에 자동 POST하지 않음. 수동 ingest만 가능 |

---

## 6. 이전 갭 문서와의 차이 요약

갭 문서는 "Phase 1·2 구현 0%"라고 주장했으나, 실제로는:

- **프론트엔드 구현**: 모든 Phase 1·2 파일 존재, 총 ~2,900 LOC
- **진짜 갭**: 백엔드 API 3개(`/kpis`, `/drivers`, `/nodes/{id}`) + Oracle 자동 인제스트 + Phase 3 컴포넌트 3개

### 실제 작업 우선순위

| 우선순위 | 작업 | 현재 workaround |
|---------|------|----------------|
| P0 | `GET /api/insight/kpis` 백엔드 구현 | 하드코딩 샘플 5개 |
| P0 | `GET /api/insight/drivers` 백엔드 구현 | 클라이언트사이드 파생 |
| P1 | `GET /api/insight/nodes/{id}` 백엔드 구현 | store 직접 조회 |
| P1 | Oracle→Weaver 자동 인제스트 (`sql_exec.py` hook) | 수동 ingest |
| P2 | `useKpiTimeseries` + `KpiMiniChart` 구현 | 없음 |
| P2 | `useNodeDataPreview` (Ontology) 구현 | 없음 |
