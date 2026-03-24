# Canvas 프론트엔드 현황 분석 및 구현 계획서 v1

> **작성일**: 2026-03-23
> **기준**: `feat/semantic-layer-v5.2` 브랜치 Canvas 소스 코드
> **비교 대상**: `canvas/docs/04_frontend/feature-priority-matrix.md` 체크리스트
> **목적**: 현재 구현 상태를 정밀 분석하고, 미구현 항목의 구현 계획을 수립한다.

---

## 1. 전체 현황 요약

### 1.1 코드베이스 규모

| 지표 | 수량 |
|------|------|
| **총 TypeScript/TSX 파일** | 565 |
| **Feature 모듈** | 32개 디렉토리 |
| **Page 컴포넌트** | 68개 (24개 라우트 섹션) |
| **shadcn/ui 컴포넌트** | 15개 |
| **Zustand 스토어** | 8+ (전역 3 + 피처별 5+) |
| **테스트 파일** | 17개 (3% 커버리지) |
| **i18n 언어** | 2 (ko/en) |

### 1.2 인프라 성숙도 평가

| 영역 | 상태 | 비고 |
|------|------|------|
| 디자인 시스템 (shadcn/ui) | ✅ 구축 완료 | 15개 컴포넌트, Tailwind 4.2, 다크모드 |
| API 클라이언트 | ✅ 구축 완료 | Axios + JWT 인터셉터 + 토큰 갱신 + 테넌트 |
| 라우팅 | ✅ 구축 완료 | React Router 7 + lazy loading + SSOT |
| 상태 관리 | ✅ 구축 완료 | Zustand + TanStack Query |
| 인증/인가 | ✅ 구축 완료 | JWT + AuthGuard + RoleGuard + RBAC |
| WebSocket | ✅ 구축 완료 | wsManager + watchStream |
| i18n | ✅ 구축 완료 | i18next ko/en |
| 에러 바운더리 | ✅ 구축 완료 | Global + Page 레벨 |
| 공용 컴포넌트 | ⚠️ 부분 | EmptyState, LoadingSkeleton 있음. DataTable 없음 (각 피처에 인라인) |
| 테스트 인프라 | ⚠️ 미흡 | Vitest 설정만 완료, 17개 테스트 파일 (3% 커버리지) |
| E2E 테스트 | ❌ 없음 | Playwright 미설정 |
| 접근성 | ❌ 미검증 | axe-core 미설치, ARIA 속성 산발적 |

---

## 2. Feature별 상세 갭 분석

### 2.1 공유 인프라 (Sprint 1 범위)

| 체크리스트 항목 | 상태 | 현재 파일 |
|----------------|------|----------|
| 디자인 시스템 (shadcn/ui) | ✅ | `components/ui/` (15개) |
| Design Tokens (CSS 변수, 다크 모드) | ✅ | `index.css` + `themeStore.ts` |
| 레이아웃 (Root/Dashboard/Auth) | ✅ | `layouts/` (11 파일) |
| React Router 라우트 정의 + lazy loading | ✅ | `lib/routes/routeConfig.tsx` |
| API 클라이언트 + 토큰 갱신 인터셉터 | ✅ | `lib/api-client.ts`, `lib/api/` |
| Zustand 전역 스토어 | ✅ | `stores/authStore.ts`, `themeStore.ts` |
| TanStack Query 설정 | ✅ | `lib/queryClient.ts` |
| WebSocket 매니저 | ✅ | `lib/wsManager.ts`, `lib/streamManager.ts` |
| i18n 설정 (ko/en) | ✅ | `lib/i18n/` |
| 공용 컴포넌트 (EmptyState, LoadingSkeleton, DataTable) | ✅ | `shared/DataTable.tsx` (80 LOC, TanStack Table 래퍼) 포함 |
| 에러 바운더리 | ✅ | `components/GlobalErrorBoundary.tsx` |
| Toast 시스템 | ✅ | sonner 사용 |
| 반응형 디자인 | ⚠️ | Tailwind responsive 사용하나 체계적 검증 안됨 |
| 다크 모드 전체 적용 | ⚠️ | 토글 있으나 전 화면 검증 안됨 |
| 접근성 기본 검증 | ❌ | 미실시 |
| 단위 테스트 환경 | ⚠️ | Vitest 설정 완료, 테스트 부족 |
| E2E 테스트 환경 (Playwright) | ❌ | 미설정 |

**갭 요약**: 인프라 핵심은 완료. **공유 DataTable**, **접근성**, **E2E 테스트 환경**이 미비.

---

### 2.2 인증/인가 (Sprint 1 범위)

| 체크리스트 항목 | 상태 | 현재 파일 |
|----------------|------|----------|
| 디렉토리 구조 (`features/auth/`) | ⚠️ | 디렉토리 존재하나 파일 0개 (로직이 `pages/auth/`와 `stores/`에 분산) |
| TypeScript 타입 정의 | ✅ | `stores/authStore.ts` 내 인라인 |
| API 클라이언트 (login, logout, refreshToken) | ✅ | `lib/api-client.ts` + 인터셉터 |
| Zustand authStore | ✅ | `stores/authStore.ts` (sessionStorage 영속) |
| LoginPage | ✅ | `pages/auth/LoginPage.tsx` |
| CallbackPage | ✅ | `pages/auth/CallbackPage.tsx` |
| AuthGuard | ✅ | `shared/AuthGuard.tsx` |
| RoleGuard | ✅ | `shared/RoleGuard.tsx` |
| usePermission, useRole 훅 | ✅ | `shared/hooks/usePermission.ts`, `useRole.ts` |
| 사이드바 메뉴 권한 필터링 | ✅ | `layouts/Sidebar.tsx` |
| 토큰 자동 갱신 | ✅ | 401 인터셉터 |
| 로그아웃 시 상태 클리어 | ✅ | `authStore.logout()` |
| 접근성 검증 (로그인 폼) | ❌ | 미검증 |
| 단위 테스트 | ❌ | 없음 |
| E2E 시나리오 | ❌ | 없음 |

**갭 요약**: 기능은 **100% 구현**. `features/auth/` 정리(리팩토링)와 **테스트**만 부족.

---

### 2.3 케이스 대시보드 (Sprint 2 범위) — 15 파일

| 체크리스트 항목 | 상태 | 현재 파일 |
|----------------|------|----------|
| 디렉토리 구조 | ✅ | `features/case-dashboard/` |
| API 연동 (useCases, useCaseStats) | ✅ | `hooks/useCases.ts`, `useCaseStats.ts` |
| StatsCard | ✅ | `components/StatsCard.tsx` |
| CaseFilters (검색 + URL 동기화) | ✅ | `components/CaseFilters.tsx` |
| CaseTable (정렬 + 페이지네이션) | ✅ | `components/CaseTable.tsx` |
| CaseTimeline | ✅ | `components/CaseTimeline.tsx` |
| CaseDistributionChart | ✅ | `components/CaseDistributionChart.tsx` |
| **역할별 대시보드 합성** | ✅ | `hooks/useDashboardConfig.ts` |
| RoleGreeting | ✅ | `components/RoleGreeting.tsx` |
| QuickActionsPanel | ✅ | `components/QuickActionsPanel.tsx` |
| MyWorkitemsPanel | ✅ | `components/MyWorkitemsPanel.tsx` |
| ApprovalQueuePanel | ✅ | `components/ApprovalQueuePanel.tsx` |
| SystemHealthMiniCard | ❌ | 미구현 |
| DataPipelinePanel (engineer) | ❌ | 미구현 |
| AnalyticsQuickPanel (analyst) | ❌ | 미구현 |
| DashboardComposer | ❌ | 미구현 (역할별 패널 조합기) |
| WebSocket 연동 (case:updated) | ⚠️ | wsManager 있으나 대시보드 연동 미확인 |
| 빈 상태 | ⚠️ | EmptyState 공용 있으나 대시보드 전용 미확인 |
| 접근성 검증 | ❌ | 미검증 |
| 단위/E2E 테스트 | ❌ | 없음 |

**갭 요약**: 핵심 80% 구현. **4개 역할별 패널**(SystemHealth, DataPipeline, Analytics, DashboardComposer)과 **테스트** 미구현.

---

### 2.4 문서 관리 + HITL (Sprint 3 범위) — 4(feature) + 4(pages) = 8 파일

| 체크리스트 항목 | 상태 | 현재 파일 |
|----------------|------|----------|
| 디렉토리 구조 | ✅ | `features/document-management/` + `pages/documents/` |
| TypeScript 타입 정의 | ⚠️ | API 파일 내 인라인 (별도 타입 파일 없음) |
| API 클라이언트 함수 | ⚠️ | `api/documentReviewApi.ts` (리뷰만, 문서 CRUD 미완) |
| TanStack Query hooks | ⚠️ | `hooks/useDocumentReview.ts` (리뷰 mutation 있음) |
| DocumentListPage | ✅ | `pages/documents/DocumentListPage.tsx` (102 LOC, DataTable+필터+AI표시, mock 데이터) |
| DocumentEditorPage (Monaco) | ✅ | `pages/documents/DocumentEditorPage.tsx` (123 LOC, Monaco+ReviewPanel+승인버튼) |
| DocumentReviewPage | ✅ | `pages/documents/DocumentReviewPage.tsx` (130 LOC, approve/reject/requestChanges) |
| DocumentManager | ✅ | `pages/documents/DocumentManager.tsx` (56 LOC, 라우팅 컨테이너) |
| ReviewPanel | ✅ | `features/document-management/components/ReviewPanel.tsx` |
| DocumentDiffViewer | ✅ | `features/document-management/components/DocumentDiffViewer.tsx` |
| **실 API 연동 (mock→real)** | ❌ | 현재 mock 데이터 — Core API 연동 필요 |
| **HITL 상태 머신 (FSM)** | ❌ | 상태 전이 로직 미구현 (버튼은 있으나 FSM 가드 없음) |
| **낙관적 업데이트** | ❌ | mutation 있으나 optimistic update 미적용 |
| AiGeneratedBadge | ⚠️ | DocumentListPage에 AI 표시 있으나 별도 컴포넌트 아님 |
| 테스트 | ❌ | 없음 |

**갭 요약**: **65% 구현** (UI 대부분 존재). 잔여 갭: **실 API 연동, HITL FSM, 낙관적 업데이트, 테스트**.

---

### 2.5 NL2SQL 대화형 쿼리 (Sprint 4 범위) — 38 파일

| 체크리스트 항목 | 상태 | 현재 파일 |
|----------------|------|----------|
| 디렉토리 구조 | ✅ | `features/nl2sql/` (38 파일) |
| TypeScript 타입 정의 | ✅ | `types/nl2sql.ts`, `types/schema.ts` |
| SSE 연결 함수 | ✅ | `api/oracleNl2sqlApi.ts` |
| useNl2sql 훅 | ✅ | `hooks/useNl2SqlChat.ts`, `useConversationState.ts` |
| ChatInterface | ✅ | `pages/nl2sql/` 내 구현 |
| SqlPreview | ⚠️ | `CPipelineProgress.tsx`, `ReactSummaryPanel.tsx` 부분 |
| ResultTable | ⚠️ | 있으나 TanStack Table 연동 미확인 |
| ChartRecommender | ❌ | 미구현 |
| ChatInput (데이터소스 선택) | ⚠️ | 기본 입력 있으나 데이터소스 선택 미확인 |
| QueryHistory | ✅ | `components/QueryHistoryPanel.tsx` |
| SchemaCanvas (Cytoscape) | ✅ | `components/SchemaCanvas.tsx` |
| 대화 컨텍스트 관리 | ✅ | `hooks/useConversationState.ts` |
| HumanInTheLoopInput | ✅ | `components/HumanInTheLoopInput.tsx` |
| QualityBadge | ✅ | `components/QualityBadge.tsx` |
| 빈 상태 | ✅ | `components/SchemaEmptyState.tsx` |
| 테스트 | ⚠️ | 6개 테스트 파일 (훅 위주) |

**갭 요약**: **85% 구현**. 가장 성숙한 피처. **ChartRecommender**와 **접근성** 미비.

---

### 2.6 OLAP 피벗 분석 (Sprint 4 범위) — 7(olap) + 18(olap-studio) = 25 파일

| 체크리스트 항목 | 상태 | 현재 파일 |
|----------------|------|----------|
| TypeScript 타입 정의 | ✅ | `olap/types/olap.ts` |
| API 클라이언트 | ✅ | `olap/api/visionOlapApi.ts`, `olap-studio/api/olapStudioApi.ts` |
| TanStack Query hooks | ✅ | `olap/hooks/useOlapVision.ts`, `olap-studio/hooks/usePivot.ts` |
| Zustand pivotConfigStore | ✅ | `olap/store/usePivotConfig.ts` |
| PivotBuilder (DnD) | ✅ | `olap-studio/components/PivotBuilder.tsx` |
| PivotResultGrid | ✅ | `olap-studio/components/PivotResultGrid.tsx` |
| DrilldownBreadcrumb | ✅ | `olap/components/DrilldownBreadcrumb.tsx` |
| ChartSwitcher | ✅ | `olap/components/ChartSwitcher.tsx` |
| **CubeSelector** | ⚠️ | `olap-studio/pages/CubeManagementPage.tsx` (관리 화면, 선택기 별도 미확인) |
| **DimensionPalette (DnD)** | ⚠️ | PivotBuilder 내 포함 |
| ExportButton (CSV) | ❌ | `lib/csvExport.ts` 유틸 있으나 UI 버튼 미확인 |
| DnD 접근성 (키보드) | ❌ | 미구현 |
| Mondrian XML | ✅ | `olap-studio/components/MondrianXmlEditor.tsx` |
| LineageGraphView | ✅ | `olap-studio/components/LineageGraphView.tsx` |
| ETL 파이프라인 | ✅ | `olap-studio/pages/EtlPipelinesPage.tsx` |
| 테스트 | ⚠️ | 5개 테스트 파일 |

**갭 요약**: **80% 구현**. CSV Export UI, DnD 접근성 부족.

---

### 2.7 Watch 알림 (Sprint 5 범위) — 6(watch) + 3(watch-agent) = 9 파일

| 체크리스트 항목 | 상태 | 현재 파일 |
|----------------|------|----------|
| TypeScript 타입 정의 | ✅ | `watch/types/watch.ts` |
| API 클라이언트 | ⚠️ | `lib/watch.ts` (글로벌) |
| useAlerts 훅 | ✅ | `watch/hooks/useAlerts.ts` |
| useWatchRules 훅 | ✅ | `watch/hooks/useWatchRules.ts` |
| WebSocket 연동 | ✅ | `watch/components/WatchToastListener.tsx` |
| useNotificationBell | ✅ | `watch/hooks/useNotificationBell.ts` |
| WatchStore | ✅ | `watch/store/useWatchStore.ts` |
| **WatchDashboardPage** | ⚠️ | `pages/watch/` 존재 |
| **AlertFeed + AlertCard** | ❌ | 미구현 |
| **AlertStats** | ❌ | 미구현 |
| **PriorityFilter** | ❌ | 미구현 |
| **EventTimeline** | ❌ | 미구현 |
| **AlertRuleEditor (Sheet)** | ❌ | 미구현 |
| **NotificationBell Popover** | ⚠️ | 훅 있으나 Popover UI 미확인 |
| 심각도별 토스트 규칙 | ⚠️ | WatchToastListener 있으나 세분화 미확인 |
| 역할별 기본 구독 | ❌ | 미구현 |
| 테스트 | ❌ | 없음 |

**갭 요약**: **40% 구현** (훅/스토어/타입 중심). **UI 컴포넌트 대부분 미구현**.

---

### 2.8 데이터소스 관리 (Sprint 5 범위) — 12 파일

| 체크리스트 항목 | 상태 | 현재 파일 |
|----------------|------|----------|
| API 클라이언트 | ✅ | `datasource/api/weaverDatasourceApi.ts` |
| useDatasources 훅 | ✅ | `datasource/hooks/useDatasources.ts` |
| SchemaExplorer (트리 뷰) | ✅ | `datasource/components/SchemaExplorer.tsx` |
| SyncProgress | ✅ | `datasource/components/SyncProgress.tsx` |
| ERD 시각화 | ✅ | `datasource/components/ERDiagramPanel.tsx`, `MermaidERDRenderer.tsx` |
| **ConnectionForm (Dialog)** | ⚠️ | Zod 스키마 있으나 (`schemas/datasourceFormSchema.ts`) Dialog UI 미확인 |
| **TestConnectionButton** | ❌ | 미구현 |
| **DatasourceCard** | ❌ | 미구현 (리스트 UI) |
| 테스트 | ⚠️ | 1개 (mermaidCodeGen.test.ts) |

**갭 요약**: **60% 구현**. 스키마 탐색/ERD 강점. **연결 폼 UI, 카드 리스트, 연결 테스트** 미구현.

---

### 2.9 프로세스 디자이너 (Sprint 6-7 범위) — 41 파일

| 체크리스트 항목 | 상태 | 현재 파일 |
|----------------|------|----------|
| 캔버스 렌더링 (react-konva) | ✅ | `components/canvas/ProcessCanvas.tsx` |
| CanvasNode (노드 렌더링) | ✅ | `components/canvas/CanvasNode.tsx` |
| ConnectionLine | ✅ | `components/canvas/ConnectionLine.tsx` |
| ProcessToolbox | ✅ | `components/toolbox/ProcessToolbox.tsx` |
| ProcessPropertyPanel | ✅ | `components/property-panel/` (5 파일) |
| 키보드 단축키 | ✅ | `hooks/useCanvasKeyboard.ts` |
| Undo/Redo (Yjs) | ✅ | `store/slices/yjsInternals.ts` |
| CollaboratorCursors | ✅ | `components/canvas/CollaboratorCursors.tsx` |
| ConformanceOverlay | ✅ | `components/mining/ConformanceOverlay.tsx` |
| MiningPanel + VariantList | ✅ | `components/mining/` (3 파일) |
| AI 역공학 | ✅ | `components/AiDiscoverDialog.tsx` |
| RubberBandSelect | ✅ | `hooks/useRubberBandSelect.ts` |
| **ProcessMinimap** | ❌ | 미구현 |
| **뷰포트 컬링** | ❌ | 미구현 (200노드 30fps 목표) |
| 테스트 | ❌ | 없음 |

**갭 요약**: **90% 구현**. 가장 완성도 높음. **미니맵, 뷰포트 컬링, 테스트**만 부족.

---

### 2.10 What-if 시나리오 (Sprint 8 범위) — 27(whatif) + 14(whatif-wizard) = 41 파일

| 체크리스트 항목 | 상태 | 현재 파일 |
|----------------|------|----------|
| TypeScript 타입 정의 | ✅ | `whatif/types/whatif.ts`, `types/wizard.ts` |
| Zustand 스토어 | ✅ | `whatif/store/useWhatIfStore.ts`, `useWhatIfWizardStore.ts` |
| 9단계 위자드 | ✅ | `components/WizardStepper.tsx`, `StepScenarioDefine.tsx` ~ `StepSimulation.tsx` |
| ParameterSweepChart | ✅ | `components/ParameterSweepChart.tsx` |
| ModelDagViewer | ✅ | `components/ModelDagViewer.tsx` |
| CausalEdgeTable | ✅ | `components/CausalEdgeTable.tsx` |
| SimulationResultPanel | ✅ | `components/SimulationResultPanel.tsx` |
| **TornadoChart** | ❌ | 미구현 (Recharts 커스텀 가로 BarChart) |
| **ScenarioComparison 테이블** | ❌ | 미구현 |
| 테스트 | ❌ | 없음 |

**갭 요약**: **85% 구현**. **TornadoChart, ScenarioComparison** 미구현.

---

### 2.11 온톨로지 브라우저 (Sprint 8 범위) — 15 파일

| 체크리스트 항목 | 상태 | 현재 파일 |
|----------------|------|----------|
| API + 타입 | ✅ | `ontology/api/ontologyApi.ts`, `types/ontology.ts` |
| Zustand 스토어 | ✅ | `ontology/store/useOntologyStore.ts` |
| **GraphViewer (force-graph)** | ⚠️ | Cytoscape 사용 (react-force-graph-2d 아닌 Cytoscape) |
| SchemaBasedGenerator | ✅ | `ontology/components/SchemaBasedGenerator.tsx` |
| OntologyWizard | ✅ | `ontology/components/OntologyWizard.tsx` |
| **SearchPanel (디바운스)** | ❌ | 미구현 |
| **LayerFilter** | ❌ | 미구현 |
| **DepthSelector** | ❌ | 미구현 |
| **NodeDetail** | ❌ | 미구현 |
| **PathHighlighter** | ❌ | 미구현 |
| 프로세스 디자이너 연동 | ❌ | 미구현 |
| 테스트 | ❌ | 없음 |

**갭 요약**: **40% 구현**. API/타입/위자드는 있으나 **그래프 탐색 UI 대부분 미구현**.

---

### 2.12 복원력 UI

| 체크리스트 항목 | 상태 | 현재 파일 |
|----------------|------|----------|
| ServiceStatusBanner | ✅ | `components/ServiceStatusBanner.tsx` |
| 피처 디렉토리 | ❌ | `features/resilience/` 없음 |
| Graceful Degradation UI | ❌ | 미구현 |
| Circuit Breaker 상태 반영 | ❌ | 미구현 |

---

## 3. 종합 갭 매트릭스

| Sprint | Feature | 구현율 | 미구현 주요 항목 | 우선순위 |
|--------|---------|--------|-----------------|----------|
| S1 | 공유 인프라 | **95%** | 접근성 검증, E2E 환경 (DataTable ✅ 확인됨) | P0 |
| S1 | 인증/인가 | **95%** | features/auth 정리, 테스트 | P0 |
| S2 | 케이스 대시보드 | **80%** | 4개 역할별 패널, DashboardComposer, 테스트 | P0 |
| S3 | 문서 관리 + HITL | **65%** | 실 API 연동, HITL FSM, 낙관적 업데이트, 테스트 | P0 |
| S4 | NL2SQL | **85%** | ChartRecommender, 접근성 | P1 |
| S4 | OLAP 피벗 | **80%** | CSV Export UI, DnD 접근성 | P1 |
| S5 | Watch 알림 | **40%** | AlertFeed, AlertStats, AlertRuleEditor, NotificationBell UI | P1 |
| S5 | 데이터소스 관리 | **60%** | ConnectionForm, TestConnection, DatasourceCard | P2 |
| S6-7 | 프로세스 디자이너 | **90%** | Minimap, 뷰포트 컬링 | P2 |
| S8 | What-if 시나리오 | **85%** | TornadoChart, ScenarioComparison | P2 |
| S8 | 온톨로지 브라우저 | **40%** | 그래프 탐색 UI 5개 컴포넌트 | P2 |
| — | 복원력 UI | **20%** | Graceful Degradation, Circuit Breaker 반영 | P1 |
| — | **테스트 전체** | **3%** | E2E 환경, 단위 테스트 대부분 | 전체 |

### 3.2 분석 대상 외 Feature 모듈 (체크리스트 범위 밖, 구현 존재)

> feature-priority-matrix.md 체크리스트에는 없지만 코드베이스에 존재하는 15개 피처 모듈.
> 이들은 별도 요구사항 문서 없이 구현된 것으로, 갭 여부는 개별 검토가 필요하다.

| Feature | 파일 수 | 주요 내용 | 상태 평가 |
|---------|--------|----------|----------|
| `security` | 14 | 사용자/역할 관리, 감사 로그, 테이블 권한 | ⚠️ 체크리스트 없음 |
| `domain` | 16 | 도메인 객체 타입 모델러, 그래프 뷰어, 관계 | ⚠️ 체크리스트 없음 |
| `workflow-editor` | 15 | React Flow 기반 워크플로 캔버스 | ⚠️ 체크리스트 없음 |
| `ingestion` | 13 | 파일 업로드, 파이프라인, **ConnectionTestDialog** 포함 | ✅ 상당 수준 |
| `domain-modeler` | 11 | GWT 규칙 빌더, 정책 에디터 | ⚠️ 체크리스트 없음 |
| `glossary` | 11 | 비즈니스 용어사전, 편집기, import/export | ⚠️ 체크리스트 없음 |
| `object-explorer` | 11 | 인스턴스 테이블, 검색, 그래프, 상세 | ⚠️ 체크리스트 없음 |
| `data-quality` | 10 | DQ 점수 카드, 규칙 테이블, 테스트 러너 | ⚠️ 체크리스트 없음 |
| `lineage` | 10 | 리니지 그래프 뷰어, 검색, 필터, 노드 상세 | ⚠️ 체크리스트 없음 |
| `feedback` | 7 | 피드백 대시보드, 트렌드, 통계 | ⚠️ 체크리스트 없음 |
| `behavior` | 6 | BehaviorModel 실행 패널, 코드 뷰어 | ⚠️ 체크리스트 없음 |
| `explorer` | 6 | 오브젝트 카드 탐색기 | ⚠️ 체크리스트 없음 |
| `ontology-wizard` | 6 | 멀티 레이어 온톨로지 생성 위자드 | ⚠️ 체크리스트 없음 |
| `cep` | 4 | Complex Event Processing 규칙 | ⚠️ 체크리스트 없음 |
| `instance-preview` | 4 | 데이터 프리뷰 패널 | ⚠️ 체크리스트 없음 |
| `materialized-views` | 3 | MV 관리 페이지 | ⚠️ 체크리스트 없음 |

**총 141 파일** — 체크리스트 범위 외이나 실질적 코드 자산. 특히 `ingestion/ConnectionTestDialog`는 데이터소스 관리의 "TestConnectionButton 미구현" 갭을 이미 해소하고 있을 가능성이 높다.

---

## 4. 구현 계획

### 4.1 Phase 별 구현 로드맵

```
Phase A (2주) — P0 갭 해소: 문서 관리 + HITL + 대시보드 완성
  ├─ Sprint A1: 문서 관리 + HITL 전체 구현 (최대 갭)
  └─ Sprint A2: 케이스 대시보드 역할별 패널 + 공유 DataTable

Phase B (2주) — P1 갭 해소: Watch 알림 + 분석 완성
  ├─ Sprint B1: Watch 알림 UI 전체 + 복원력 UI
  └─ Sprint B2: NL2SQL ChartRecommender + OLAP Export + 접근성

Phase C (2주) — P2 갭 해소: 데이터소스 + 온톨로지 + 고급 기능
  ├─ Sprint C1: 데이터소스 ConnectionForm + 온톨로지 그래프 탐색
  └─ Sprint C2: What-if TornadoChart + 프로세스 디자이너 Minimap

Phase D (2주) — 품질 + 테스트
  ├─ Sprint D1: E2E 환경 + 핵심 시나리오 테스트
  └─ Sprint D2: 접근성 감사 + 다크모드 검수 + 성능 최적화
```

### 4.2 Sprint A1: 문서 관리 + HITL 완성 (P0 — mock→real + FSM)

**목표**: "기존 mock 기반 UI를 실 API에 연결하고, HITL 상태 머신으로 안전한 워크플로를 보장한다"

> **리뷰 수정**: DocumentListPage(102L), EditorPage(123L), ReviewPage(130L) 이미 구현됨.
> 잔여 갭은 실 API 연동 + HITL FSM + 낙관적 업데이트 + 테스트.

| # | 작업 | 파일 | 비고 |
|---|------|------|------|
| 1 | TypeScript 타입 정의 (Document, DocumentStatus FSM) | `features/document-management/types/document.ts` | 별도 파일 분리 |
| 2 | API 클라이언트 확장 (문서 CRUD — mock→Core API) | `features/document-management/api/documentApi.ts` | 기존 reviewApi와 통합 |
| 3 | TanStack Query hooks (useDocuments, useDocument) + 실 API 연동 | `features/document-management/hooks/useDocuments.ts` | 신규 |
| 4 | HITL 상태 머신 (draft→in_review→approved/rejected + FSM 가드) | `features/document-management/hooks/useDocumentFSM.ts` | 핵심 갭 |
| 5 | 낙관적 업데이트 적용 (기존 ReviewPage mutation 고도화) | `pages/documents/DocumentReviewPage.tsx` 수정 | onMutate/onError rollback |
| 6 | DocumentListPage mock→실 API 전환 | `pages/documents/DocumentListPage.tsx` 수정 | useDocuments 훅 연결 |
| 7 | AiGeneratedBadge 컴포넌트 분리 | `features/document-management/components/AiGeneratedBadge.tsx` | 소형 컴포넌트 |

**예상 신규 파일**: ~4개, **수정 파일**: ~3개, ~600 LOC

### 4.3 Sprint A2: 케이스 대시보드 역할별 패널 완성

> **리뷰 수정**: 공유 DataTable (`components/shared/DataTable.tsx`, 80 LOC) 이미 존재. 제거.

| # | 작업 | 파일 |
|---|------|------|
| 1 | DashboardComposer (역할별 조건부 패널 렌더링) | `features/case-dashboard/components/DashboardComposer.tsx` |
| 2 | SystemHealthMiniCard (admin, engineer) | `features/case-dashboard/components/SystemHealthMiniCard.tsx` |
| 3 | DataPipelinePanel (engineer) + useDatasourceStatus 훅 | `features/case-dashboard/components/DataPipelinePanel.tsx` |
| 4 | AnalyticsQuickPanel (analyst) + useRecentQueries 훅 | `features/case-dashboard/components/AnalyticsQuickPanel.tsx` |
| 5 | WebSocket case:updated → 쿼리 무효화 연동 | CaseDashboardPage 수정 |

**예상 신규 파일**: ~4개, **수정 파일**: ~1개, ~600 LOC

### 4.4 Sprint B1: Watch 알림 UI + 복원력 UI

| # | 작업 | 파일 |
|---|------|------|
| 1 | AlertFeed + AlertCard (알림 목록 카드) | `features/watch/components/AlertFeed.tsx`, `AlertCard.tsx` |
| 2 | AlertStats (통계 카드 4종) | `features/watch/components/AlertStats.tsx` |
| 3 | PriorityFilter (심각도 필터) | `features/watch/components/PriorityFilter.tsx` |
| 4 | EventTimeline (시간별 이벤트) | `features/watch/components/EventTimeline.tsx` |
| 5 | AlertRuleEditor (Sheet — 조건/대상/채널 설정) | `features/watch/components/AlertRuleEditor.tsx` |
| 6 | NotificationBell Popover (최근 5건 드롭다운) | `layouts/NotificationBell.tsx` |
| 7 | 심각도별 토스트 규칙 세분화 | WatchToastListener 수정 |
| 8 | 복원력 UI (Graceful Degradation, Circuit Breaker 표시) | `features/resilience/` |

**예상 신규 파일**: ~10개, ~1200 LOC

### 4.5 Sprint B2: NL2SQL + OLAP 완성

| # | 작업 | 파일 |
|---|------|------|
| 1 | ChartRecommender (결과 데이터 → 자동 차트 추천) | `features/nl2sql/components/ChartRecommender.tsx` |
| 2 | CSV Export 버튼 (OLAP 피벗) | `features/olap/components/ExportButton.tsx` |
| 3 | DnD 접근성 (키보드 DnD — @dnd-kit announcements) | PivotBuilder 수정 |
| 4 | 드릴다운 URL search params 동기화 | OlapPivotPage 수정 |

**예상 신규 파일**: ~3개, ~500 LOC

### 4.6 Sprint C1: 데이터소스 + 온톨로지

| # | 작업 | 파일 |
|---|------|------|
| 1 | ConnectionForm (Dialog + Zod 검증) | `features/datasource/components/ConnectionForm.tsx` |
| 2 | TestConnectionButton | `features/datasource/components/TestConnectionButton.tsx` |
| 3 | DatasourceCard (리스트 카드 뷰) | `features/datasource/components/DatasourceCard.tsx` |
| 4 | 온톨로지 SearchPanel (디바운스 검색) | `features/ontology/components/SearchPanel.tsx` |
| 5 | 온톨로지 LayerFilter (4계층 체크박스) | `features/ontology/components/LayerFilter.tsx` |
| 6 | 온톨로지 NodeDetail (속성 + 연결) | `features/ontology/components/NodeDetail.tsx` |
| 7 | 온톨로지 PathHighlighter | `features/ontology/components/PathHighlighter.tsx` |
| 8 | 프로세스 디자이너 상호 네비게이션 | URL 파라미터 연동 |

**예상 신규 파일**: ~8개, ~1000 LOC

### 4.7 Sprint C2: What-if + 프로세스 디자이너 고급

| # | 작업 | 파일 |
|---|------|------|
| 1 | TornadoChart (Recharts 가로 BarChart 커스텀) | `features/whatif/components/TornadoChart.tsx` |
| 2 | ScenarioComparison 테이블 | `features/whatif/components/ScenarioComparison.tsx` |
| 3 | ProcessMinimap | `features/process-designer/components/canvas/ProcessMinimap.tsx` |
| 4 | 뷰포트 컬링 (노드 100+ 최적화) | `features/process-designer/hooks/useViewportCulling.ts` |

**예상 신규 파일**: ~4개, ~600 LOC

### 4.8 Sprint D1-D2: 품질 + 테스트

| # | 작업 | 예상 공수 |
|---|------|----------|
| 1 | Playwright 설정 + E2E 환경 구축 | 2일 |
| 2 | 핵심 E2E 시나리오 5개 (로그인→대시보드→문서→분석→프로세스) | 3일 |
| 3 | 단위 테스트 보강 (authStore, HITL hooks, watch hooks) | 2일 |
| 4 | 접근성 감사 (axe-core 전체 스캔) | 1일 |
| 5 | 다크 모드 전체 검수 | 1일 |
| 6 | 반응형 전체 검수 | 1일 |
| 7 | 성능 프로파일링 (Lighthouse, Web Vitals) | 1일 |
| 8 | 번들 최적화 (코드 분할 확인) | 1일 |

---

## 5. 총 구현 규모 추정

| Phase | 신규 파일 | 수정 파일 | 예상 LOC |
|-------|----------|----------|---------|
| Phase A (S-A1 + S-A2) | ~8 | ~4 | ~1,200 |
| Phase B (S-B1 + S-B2) | ~13 | ~4 | ~1,700 |
| Phase C (S-C1 + S-C2) | ~12 | ~3 | ~1,600 |
| Phase D (테스트 + 품질) | ~10 | ~8 | ~1,500 |
| **합계** | **~43** | **~19** | **~6,000** |

> **v1.1 수정**: 리뷰 결과 반영 — Phase A 규모 축소 (DocumentListPage/EditorPage/ReviewPage + 공유 DataTable 이미 존재 확인).

---

## 6. 리스크 & 의존성

| 리스크 | 영향 | 대응 |
|--------|------|------|
| 문서 관리 HITL — Core API 미구현 | P0 기능 동작 불가 | Mock API 우선 → 백엔드 병행 개발 |
| Watch 알림 — WebSocket 이벤트 스키마 불일치 | 실시간 알림 실패 | watchStream.ts 기존 코드 활용, 스키마 확인 |
| 프로세스 디자이너 뷰포트 컬링 — 성능 기준 미달 | 200노드에서 프레임 드롭 | react-konva 가상화 + LOD (Level of Detail) 적용 |
| E2E 테스트 — CI 환경 설정 복잡 | 테스트 자동화 지연 | 로컬 Playwright 먼저, CI 나중 |
| 접근성 — shadcn/ui 기본 ARIA 외 추가 필요 | WCAG 미충족 | axe-core 자동 스캔 + 수동 키보드 테스트 |

---

## 7. 성공 지표

| 지표 | 목표 |
|------|------|
| P0 Feature 구현율 | 100% (인증 + 케이스 + 문서 HITL) |
| 전체 Feature 구현율 | 95%+ |
| 테스트 커버리지 | 30%+ (현재 3%) |
| E2E 시나리오 | 5개 핵심 경로 통과 |
| Lighthouse 성능 | LCP < 2.5s, CLS < 0.1 |
| 접근성 | axe-core Critical/Serious 0건 |
| 번들 크기 | 초기 번들 < 200KB (gzipped) |

---

## 8. KAIR 프론트엔드 대비 갭 분석

> **비교 대상**: `/media/daniel/E/AXIPIENT/projects/KAIR/robo-data-frontend/src/` (Vue 3, 269 파일, 19개 기능 영역)
> **방법론**: KAIR 19개 기능 영역을 Canvas 코드베이스와 1:1 교차 비교

### 8.1 교차 비교 매트릭스

| # | KAIR 기능 | Canvas 상태 | Canvas 위치 | 미구현 항목 |
|---|----------|:-----------:|-------------|------------|
| 1 | 파일 업로드 + 코드 인제스트 | ⚠️ 부분 | `features/ingestion/` | 언어별 파일 타입 감지(Java/Python/PL-SQL/DDL), 폴더 구조 보존 |
| 2 | 스키마 캔버스 ERD | ⚠️ 부분 | `features/nl2sql/SchemaCanvas.tsx` | 인터랙티브 ERD(TableCard 드래그/리사이즈), 관계 소스 추적(DDL/User/Fabric), 듀얼 캔버스 모드 |
| 3 | 데이터 리니지 UI | ⚠️ 부분 | `features/lineage/` | 프로시저→테이블 의존성, 소스코드 클릭→라인 네비게이션 |
| 4 | 그래프 시각화 (Neo4j) | ✅ 완료 | `pages/ontology/GraphViewer.tsx` | PNG/SVG/JSON 내보내기 미비 |
| 5 | **DMN 결정 에디터** | ❌ 없음 | — | **전체 미구현**: 결정 테이블 편집, 조건/액션 정의, 테스트 실행 |
| 6 | **비즈니스 캘린더** | ❌ 없음 | — | **전체 미구현**: 공휴일 DB, 영업일 계산, 회계연도 캘린더 |
| 7 | AI 이벤트 탐지 | ⚠️ 부분 | `features/cep/` (642 LOC CRUD + 평가) | LLM 대화형 규칙 정의, SQL 조건 자동 생성 (기반 CRUD는 완성) |
| 8 | 관찰성 워크플로 빌더 | ⚠️ 부분 | `features/workflow-editor/` (15파일, 1,768 LOC) | API 연동, 순환참조 검증, 스케줄링 (Cytoscape DAG 캔버스+5노드 타입 구현됨) |
| 9 | 파이프라인 제어 | ⚠️ 부분 | `features/ingestion/PipelineControlPanel.tsx` | pause/resume/stop 핸들러 스텁, 백엔드 라이프사이클 미연동 |
| 10 | NDJSON/SSE 스트리밍 진행 UI | ⚠️ 부분 | `UploadProgress.tsx`, `CPipelineProgress` | 실 SSE/NDJSON 미연동 (현재 폴링 기반) |
| 11 | **BPMN 뷰어** | ❌ 없음 | — | 프로세스 디자이너가 Konva 자체 구현. BPMN XML import/export/렌더링 없음 |
| 12 | 그래프 내보내기 | ⚠️ 부분 | ERD → SVG만 | PNG 내보내기, JSON 직렬화, 일괄 내보내기 없음 |
| 13 | 오브젝트 탐색기 + 차트 | ⚠️ 부분 | `features/object-explorer/` | 메트릭 차트 시각화 없음 (key-value 표시만) |
| 14 | 소스코드 뷰어 | ⚠️ 부분 | `features/behavior/CodeViewer.tsx` | 클릭→라인 네비게이션 없음, 프로시저 소스 연동 없음 |
| 15 | 인과 분석 UI | ⚠️ 부분 | `features/whatif/StepEdgeDiscovery` | VAR 모델링 UI, lag 시각화, 신뢰도 점수 시각화 미비 |

### 8.2 갭 유형별 요약

| 유형 | 건수 | 비율 |
|------|:----:|:----:|
| ✅ 완전 구현 | 1 | 7% |
| ⚠️ 부분 구현 | **12** | **80%** |
| ❌ 전체 미구현 | **2** | **13%** |

> **v1.3 리뷰 수정**: workflow-editor(15파일/1,768 LOC)와 CEP(4파일/765 LOC)가 실제 구현 확인됨.
> 전체 미구현 4건 → 2건(DMN, 비즈니스 캘린더)으로 축소. BPMN은 별도 판단(Konva 대체).

### 8.3 전체 미구현 기능 상세 (2건)

#### KG-1: DMN 결정 테이블 에디터

**KAIR 구현**: `DmnEditor.vue`, `BehaviorDialog.vue`, `BehaviorExecuteDialog.vue`
- 결정 테이블 CRUD (조건 컬럼 + 액션 컬럼)
- 적중 정책 선택 (FIRST/COLLECT/PRIORITY)
- 대화형 테스트 실행 (입력값 → 결과 확인)
- BehaviorModel 바인딩 (`READS_FIELD`, `PREDICTS_FIELD`)

**Canvas 갭**: 백엔드(Synapse DMN 엔진)는 구현됨. 프론트엔드 UI 전무.

**구현 계획**:
| 파일 | 역할 | LOC |
|------|------|:---:|
| `features/dmn/types/dmn.ts` | DecisionTable, Rule, HitPolicy 타입 | ~80 |
| `features/dmn/api/dmnApi.ts` | Synapse DMN API 클라이언트 | ~60 |
| `features/dmn/hooks/useDmnTable.ts` | CRUD + 실행 훅 | ~100 |
| `features/dmn/components/DmnTableEditor.tsx` | 결정 테이블 그리드 (조건/액션 컬럼 편집) | ~250 |
| `features/dmn/components/DmnTestRunner.tsx` | 테스트 실행 Dialog (입력→결과) | ~120 |
| `features/dmn/components/HitPolicySelector.tsx` | FIRST/COLLECT/PRIORITY 드롭다운 | ~40 |
| `pages/dmn/DmnEditorPage.tsx` | 페이지 컨테이너 | ~80 |

**예상**: 7 파일, ~730 LOC

#### KG-2: 비즈니스 캘린더

**KAIR 구현**: `BusinessDayCalendar.vue`, `GlossaryTab.vue` (캘린더 서브탭)
- 공휴일 등록/편집/삭제
- 영업일 계산 (주말 + 공휴일 필터)
- 회계연도 오프셋 설정
- 시계열 분석 시 영업일 기준 집계

**Canvas 갭**: 백엔드(Vision BusinessCalendar)는 구현됨. 프론트엔드 UI 전무.

**구현 계획**:
| 파일 | 역할 | LOC |
|------|------|:---:|
| `features/calendar/types/calendar.ts` | Holiday, BusinessCalendar 타입 | ~50 |
| `features/calendar/api/calendarApi.ts` | Vision Calendar API | ~50 |
| `features/calendar/hooks/useBusinessCalendar.ts` | CRUD 훅 | ~80 |
| `features/calendar/components/CalendarGrid.tsx` | 월별 캘린더 그리드 (공휴일 하이라이트) | ~200 |
| `features/calendar/components/HolidayEditor.tsx` | 공휴일 추가/편집 Dialog | ~100 |
| `pages/settings/BusinessCalendarPage.tsx` | 설정 하위 페이지 | ~60 |

**예상**: 6 파일, ~540 LOC

#### KG-3: 관찰성 워크플로 빌더 (Alert DAG) — 부분 갭으로 재분류

> **v1.3 리뷰 수정**: `features/workflow-editor/`에 15파일/1,768 LOC 이미 구현됨.
> Cytoscape DAG 캔버스 + 5개 노드 타입(Trigger/Condition/Action/Policy/Gateway) +
> 속성 폼(Cron/Webhook/KPI threshold/AND-OR-XOR) + Zustand 스토어 + dirty tracking.

**이미 구현됨** (1,768 LOC):
- `WorkflowCanvas.tsx` (315 LOC) — Cytoscape dagre 레이아웃 캔버스
- `WorkflowToolbar.tsx` (197 LOC) — 노드 팔레트 (드래그 추가)
- `WorkflowPropertyPanel.tsx` (164 LOC) — 동적 속성 패널
- `nodes/` — TriggerNode, ConditionNode, ActionNode 시각 컴포넌트
- `property-forms/` — TriggerForm(cron/webhook), ConditionForm(field/op/value), ActionForm(SET/EMIT/NOTIFY), PolicyForm, GatewayForm
- `useWorkflowEditorStore.ts` (191 LOC) — CRUD + save/load + dirty tracking

**잔여 갭**:
| 작업 | LOC |
|------|:---:|
| Core Alert DAG API 연동 (`workflowApi.ts` 확장) | ~60 |
| 순환 참조 검증 로직 | ~50 |
| 스케줄링 UI (cron 표현식 생성기) | ~80 |

**예상**: 수정 2파일 + 신규 1파일, ~190 LOC (기존 대비 80% 절감)

#### KG-4: BPMN XML 뷰어/에디터

**KAIR 구현**: `BpmnViewer.vue`, `CustomBpmnRenderer.js`, `autoLayout/bpmnAutoLayout.js`
- bpmn-js 기반 BPMN 2.0 XML 렌더링
- 커스텀 렌더러 (색상, 스타일)
- 자동 레이아웃 (Sugiyama 계층 알고리즘)

**Canvas 갭**: 프로세스 디자이너가 Konva 자체 캔버스 사용. BPMN XML import/export 없음.

**구현 계획**:
| 파일 | 역할 | LOC |
|------|------|:---:|
| `features/process-designer/components/bpmn/BpmnViewer.tsx` | bpmn-js 뷰어 래퍼 | ~150 |
| `features/process-designer/components/bpmn/BpmnImportDialog.tsx` | BPMN XML 가져오기 Dialog | ~80 |
| `features/process-designer/hooks/useBpmnExport.ts` | Konva→BPMN XML 변환 | ~120 |

**예상**: 3 파일, ~350 LOC. `bpmn-js` 패키지 추가 필요.

### 8.4 주요 부분 구현 갭 (고영향, 6건)

| ID | 기능 | 미구현 항목 | 구현 파일 | LOC |
|----|------|-----------|----------|:---:|
| KG-5 | 스키마 캔버스 고도화 | 인터랙티브 TableCard (드래그/리사이즈), 관계 소스 추적 배지 (듀얼 모드 이미 존재) | `nl2sql/SchemaCanvas.tsx` 수정 + 1 컴포넌트 | ~200 |
| KG-6 | 리니지 소스코드 링크 | 테이블→프로시저 의존성 뷰, 소스파일:라인 클릭 네비게이션 | `features/lineage/` 내 2 컴포넌트 | ~300 |
| KG-7 | 인과 분석 시각화 | VAR 모델링 UI, lag 시각화 차트, 신뢰도 히트맵 | `features/whatif/` 내 3 컴포넌트 | ~400 |
| KG-8 | AI 이벤트 탐지 대화형 | LLM 대화 오버레이 (기반 CRUD 642 LOC 완성) | `features/cep/` 내 1 컴포넌트 추가 | ~200 |
| KG-9 | 그래프 내보내기 | PNG/SVG/JSON 다중 포맷 내보내기, 일괄 다운로드 | 공용 훅 `useGraphExport.ts` | ~120 |
| KG-10 | 파일 언어 감지 | Java/Python/PL-SQL/DDL 파일 타입 자동 분류, 언어별 분석 라우팅 | `features/ingestion/` 수정 | ~200 |

### 8.5 갱신된 구현 로드맵 (Phase F 추가)

기존 Phase A-E에 **Phase F: KAIR 기능 이식**을 추가한다.

```
Phase F-1 (1주) — 전체 미구현 기능 (KG-1 ~ KG-4)
  ├─ Sprint F1-a: DMN 결정 에디터 (KG-1, 730 LOC)
  ├─ Sprint F1-b: 비즈니스 캘린더 (KG-2, 540 LOC) ← 병렬 가능
  └─ Sprint F1-c: 관찰성 워크플로 빌더 (KG-3, 950 LOC)

Phase F-2 (1주) — 주요 부분 갭 (KG-5 ~ KG-10)
  ├─ Sprint F2-a: BPMN 뷰어 (KG-4, 350 LOC) + 스키마 캔버스 고도화 (KG-5, 400 LOC)
  ├─ Sprint F2-b: 리니지 소스코드 링크 (KG-6, 300 LOC) + 인과 분석 시각화 (KG-7, 400 LOC)
  └─ Sprint F2-c: AI 이벤트 탐지 (KG-8, 500 LOC) + 그래프 내보내기 (KG-9, 120 LOC) + 파일 감지 (KG-10, 200 LOC)
```

### 8.6 Phase F 총 규모

| 항목 | 수량 |
|------|:----:|
| 신규 파일 | ~36 |
| 수정 파일 | ~8 |
| 예상 LOC | ~5,240 |
| 추가 패키지 | `bpmn-js`, `@xyflow/react` (React Flow) |

---

## 9. UI/UX 품질 감사 결과

> **감사 기준**: WCAG 2.1 Level AA, Nielsen Heuristics, 디자인 시스템 일관성
> **전체 점수**: **48 / 100** (성숙도 1.5단계 — "기능은 돌아가나 UX가 미성숙")

### 8.1 영역별 점수

| 영역 | 점수 (1-5) | 핵심 문제 |
|------|:----------:|----------|
| 디자인 시스템 일관성 | **2.0** | `tokens.css` 잘 정의됐으나 40+ 파일에서 하드코딩 색상 (195건+) |
| 컴포넌트 품질 | **3.0** | Button/Card/Input 양호. Dialog 접근성 깨짐 (stub 구현) |
| 페이지 수준 UX | **2.5** | CaseDashboard 좋음. 나머지 로딩/에러/빈상태 불균일 |
| 반응형 디자인 | **1.0** | 전체 41개 breakpoint만 사용. 모바일/태블릿 완전 무시 |
| 접근성 (a11y) | **1.5** | Skip link 없음, ARIA 최소 (55건), Dialog focus trap 없음 |
| 애니메이션/인터랙션 | **2.5** | Glass morphism 세련됨. `prefers-reduced-motion` 미지원 |
| 타이포그래피/간격 | **2.0** | 좋은 폰트 선택이나 `font-[Sora]`, `text-[48px]` 하드코딩 만연 |

### 8.2 CRITICAL 이슈 (5건)

#### C1: 다크모드 완전 깨짐 — 하드코딩 색상 195건+

**문제**: `text-black`, `bg-white`, `#5E5E5E`, `#F5F5F5` 등 hex 값이 40+ 파일에 산재. 다크모드에서 텍스트 안 보임.

**최악 파일**: `DatasourcePage.tsx` (35건), `Nl2SqlPage.tsx` (10건+), `InsightPage.tsx` (10건+), `badge.tsx` (4건), `EmptyState.tsx` (3건)

**수정 매핑**:
```
#000000 / text-black  → text-foreground       (이미 tokens.css에 정의됨)
#FFFFFF / bg-white    → bg-card               (이미 정의됨)
#F5F5F5              → bg-muted              (이미 정의됨)
#5E5E5E              → text-muted-foreground  (이미 정의됨)
#E5E5E5              → border-border          (이미 정의됨)
font-[Sora]          → font-heading           (커스텀 확장 필요)
font-[IBM_Plex_Mono] → font-mono              (커스텀 확장 필요)
text-[48px]          → text-2xl sm:text-4xl lg:text-5xl (반응형 동시 적용)
```

**예상 공수**: 2-3일 (전체 파일 체계적 치환 + ESLint 규칙으로 회귀 방지)

#### C2: Skip Navigation 없음

**문제**: 키보드 사용자가 사이드바 17개 항목을 매번 Tab. WCAG 2.4.1 위반.

**수정** (`MainLayout.tsx` 최상단에 추가):
```tsx
<a href="#main-content"
   className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4
              focus:z-[100] focus:rounded-lg focus:bg-primary focus:px-4 focus:py-2
              focus:text-primary-foreground focus:text-sm focus:font-medium focus:shadow-lg">
  Skip to main content
</a>
```

**예상 공수**: 15분

#### C3: Dialog 컴포넌트 접근성 깨짐

**문제**: `components/ui/dialog.tsx`가 shadcn/ui 스텁. focus trap 없음, Escape 키 없음, `role="dialog"` 없음, `aria-modal` 없음.

**수정**: `@radix-ui/react-dialog` 설치 후 shadcn/ui 표준 Dialog로 교체. 자동으로 focus trap + Escape + Portal + ARIA 제공.

**예상 공수**: 30분

#### C4: 죽은 레거시 코드

| 파일 | 문제 |
|------|------|
| `layouts/DashboardLayout.tsx` | MainLayout과 중복. 별도 사이드바/헤더. 다른 스타일. |
| `App.css` | Vite 보일러플레이트. `max-width: 1280px`, `text-align: center` 전체 앱에 영향 가능 |
| `pages/dashboard/DashboardPage.tsx` | `JSON.stringify` 렌더링, `any` 타입, `bg-white` 하드코딩. CaseDashboard와 중복 |
| `layouts/AuthLayout.tsx` | `text-white` 하드코딩. LoginPage가 자체 레이아웃 사용하므로 미사용 가능성 |

**수정**: 사용 여부 확인 후 삭제. **예상 공수**: 1시간

#### C5: 에러 페이지 오타

**문제**: `NotFoundPage.tsx`, `ErrorPage.tsx`에 `text-foreground0` — 존재하지 않는 CSS 클래스. 텍스트 색상 미적용.

**수정**: `text-foreground0` → `text-muted-foreground`, `text-white` → `text-primary-foreground`. **예상 공수**: 5분

### 8.3 HIGH 이슈 (7건)

| # | 문제 | 상세 | 수정 공수 |
|---|------|------|----------|
| H1 | **반응형 디자인 부재** | 전체 41개 breakpoint. `p-12` 고정 패딩 (노트북 1366px에서 96px 낭비). 사이드바 축소 메커니즘 없음 | 3-5일 |
| H2 | **스크린 리더 지원 최소** | `sr-only` 6건, `aria-*` 55건. Sidebar `<aside>` aria-label 없음. KPI 탭에 `role="tablist"` 없음. 닫기 버튼 `aria-label` 없음 | 1-2일 |
| H3 | **페이지 레이아웃 불일치** | 3가지 패딩 (`p-6`/`p-8`/`p-12`), 4가지 제목 크기, 불일치 `max-width`. 공유 `PageShell` 컴포넌트 필요 | 1-2일 |
| H4 | **DashboardPage 깨진 플레이스홀더** | `SELECT 1` 하드코딩 POST, `JSON.stringify` 렌더, `any` 타입. 삭제 또는 리다이렉트 필요 | 15분 |
| H5 | **`prefers-reduced-motion` 미지원** | `animate-spin`, `animate-pulse`, `transition-colors` 다수 사용하나 모션 감소 미대응 | 5분 |
| H6 | **Glass morphism 폴백 없음** | `backdrop-filter: blur()` 미지원 브라우저(Firefox ESR)에서 반투명 배경만 표시 | 15분 |
| H7 | **사이드바 17개 항목 그룹핑 없음** | icon-only 사이드바에 분석/데이터/운영 구분 없음. 인지 부하 과다 | 10분 |

### 8.4 MEDIUM 이슈 (6건)

| # | 문제 | 수정 공수 |
|---|------|----------|
| M1 | 사이드바 툴팁 접근성 깨짐 — CSS-only, 키보드 미지원, `role="tooltip"` 없음 | 30분 |
| M2 | Heading 계층 위반 — CaseDashboard에 `<h1>` 없음, CardTitle 항상 `<h3>` | 30분 |
| M3 | AuthLayout 다크모드 미지원 — `text-white` 하드코딩 | 15분 (또는 삭제) |
| M4 | 폰트 로딩 전략 미확인 — Geist/Sora/JetBrains Mono `@font-face` 또는 패키지 미확인 | 30분 |
| M5 | Toast 사용 불일치 — 일부 페이지 `console.error`만, 일부 `toast.error` | 1시간 |
| M6 | 브라우저 탭 제목 미관리 — 모든 페이지 동일 제목 | 1시간 |

### 8.5 개선 로드맵 (Phase E 추가)

기존 Phase A-D에 **Phase E: UI/UX 품질 개선**을 추가한다. Quick Wins은 Phase A와 병렬 실행 가능.

```
Phase E-1 (1일) — Quick Wins (8건, 수정 즉시 효과)
  ├─ text-foreground0 오타 수정 (5분)
  ├─ Skip navigation link 추가 (15분)
  ├─ prefers-reduced-motion 글로벌 규칙 (5분)
  ├─ App.css 삭제 (2분)
  ├─ ARIA label 추가 — Sidebar aside, PageTabHeader nav (10분)
  ├─ Glass morphism @supports 폴백 (15분)
  ├─ 사이드바 그룹 구분선 추가 (10분)
  └─ LoadingSpinner text-gray → text-muted-foreground (2분)

Phase E-2 (3일) — 구조 개선
  ├─ 하드코딩 색상 퍼지 (195건 → 디자인 토큰 치환) ........... 2일
  ├─ PageShell 공유 컴포넌트 (레이아웃 통일) ................. 0.5일
  ├─ Dialog → @radix-ui/react-dialog 교체 .................. 0.5일
  └─ 죽은 코드 제거 (DashboardLayout, DashboardPage, App.css)

Phase E-3 (5일) — 체계적 UX 개선
  ├─ 반응형 디자인 패스 (전 페이지 sm:/md:/lg: 적용) ......... 3일
  ├─ 접근성 자동화 (axe-core 테스트 통합 + CI) .............. 1일
  ├─ Heading 계층 정리 + 브라우저 탭 제목 관리 ............... 0.5일
  ├─ 사이드바 툴팁 접근성 + 키보드 네비게이션 ................ 0.5일
  └─ ESLint 규칙: 하드코딩 색상 방지 (no-arbitrary-value)
```

### 8.6 수정 우선순위 + 구현 계획 통합

| 기존 Sprint | UI/UX 개선 병합 | 추가 공수 |
|-------------|----------------|----------|
| **Phase A (S-A1)** | + Phase E-1 Quick Wins 병렬 실행 | +1일 |
| **Phase A (S-A2)** | + PageShell 도입 → 대시보드 패널에 적용 | +0.5일 |
| **Phase B (S-B1)** | + Watch UI에 디자인 토큰 적용 (새 코드부터 토큰 사용) | 0 (설계 반영) |
| **Phase C** | + 반응형 디자인 패스 (신규 컴포넌트 포함) | +1일 |
| **Phase D** | + 접근성 감사를 E2E와 통합, axe-core 자동 스캔 | +0.5일 |
| **별도 E-2** | 하드코딩 색상 퍼지 (기존 40+ 파일 일괄 수정) | 2일 |

### 8.7 개선 후 목표 점수

| 영역 | 현재 | Phase E-1 후 | Phase E-2 후 | Phase E-3 후 |
|------|:----:|:----------:|:----------:|:----------:|
| 디자인 시스템 일관성 | 2.0 | 2.5 | **4.0** | **4.5** |
| 컴포넌트 품질 | 3.0 | 3.0 | **3.5** | **4.0** |
| 페이지 수준 UX | 2.5 | 2.5 | **3.5** | **4.0** |
| 반응형 디자인 | 1.0 | 1.0 | 1.0 | **3.5** |
| 접근성 (a11y) | 1.5 | **2.5** | **3.0** | **4.0** |
| 애니메이션/인터랙션 | 2.5 | **3.0** | **3.5** | **3.5** |
| 타이포그래피/간격 | 2.0 | 2.0 | **3.5** | **4.0** |
| **종합** | **48** | **55** | **72** | **82** |

---

## 9. 갱신된 총 구현 규모

| Phase | 신규 파일 | 수정 파일 | 예상 LOC | 비고 |
|-------|----------|----------|---------|------|
| Phase A (기능 P0) | ~8 | ~4 | ~1,200 | 문서 HITL FSM + 대시보드 패널 |
| Phase B (기능 P1) | ~13 | ~4 | ~1,700 | Watch UI + NL2SQL/OLAP 완성 |
| Phase C (기능 P2) | ~12 | ~3 | ~1,600 | 데이터소스 + 온톨로지 + 고급 |
| Phase D (테스트) | ~10 | ~8 | ~1,500 | E2E + 접근성 + 성능 |
| **Phase E (UX 개선)** | **~3** | **~45** | **~1,800** | **색상 퍼지 + PageShell + 반응형 + a11y** |
| **Phase F (KAIR 이식)** | **~36** | **~8** | **~5,240** | **DMN + 캘린더 + 워크플로 + BPMN + 6개 부분갭** |
| **합계** | **~82** | **~72** | **~13,040** | |

---

## 10. 갱신된 리스크 & 의존성

| 리스크 | 영향 | 대응 |
|--------|------|------|
| 문서 관리 HITL — Core API 미구현 | P0 기능 동작 불가 | Mock API 우선 → 백엔드 병행 개발 |
| Watch 알림 — WebSocket 이벤트 스키마 불일치 | 실시간 알림 실패 | watchStream.ts 기존 코드 활용, 스키마 확인 |
| 프로세스 디자이너 뷰포트 컬링 — 성능 기준 미달 | 200노드에서 프레임 드롭 | react-konva 가상화 + LOD 적용 |
| E2E 테스트 — CI 환경 설정 복잡 | 테스트 자동화 지연 | 로컬 Playwright 먼저, CI 나중 |
| **하드코딩 색상 퍼지 — 회귀 위험** | **수정 중 기능 깨짐** | **ESLint 규칙 선행, 파일별 incremental 수정 + visual diff 검증** |
| **다크모드 검증 — 수동 테스트 필요** | **미발견 깨짐** | **Chromatic 또는 스크린샷 비교 자동화** |
| **Radix Dialog 교체 — 기존 Dialog 사용처 깨짐** | **모달 동작 변경** | **사용처 전수 조사 후 일괄 교체** |

---

## 11. 갱신된 성공 지표

| 지표 | 현재 | 목표 |
|------|:----:|:----:|
| P0 Feature 구현율 | 80% | **100%** |
| 전체 Feature 구현율 | 75% | **95%+** |
| 테스트 커버리지 | 3% | **30%+** |
| E2E 시나리오 | 0 | **5개 핵심 경로** |
| Lighthouse 성능 | 미측정 | **LCP < 2.5s, CLS < 0.1** |
| 접근성 (axe-core) | 미측정 | **Critical/Serious 0건** |
| 번들 크기 | 미측정 | **초기 < 200KB (gzipped)** |
| UI/UX 종합 점수 | **48/100** | **82/100** |
| 다크모드 하드코딩 색상 | 195건 | **0건** |
| 반응형 breakpoint 사용 | 41건 | **300건+** |
| ARIA 속성 사용 | 55건 | **200건+** |
| KAIR 기능 커버리지 | 7% 완전 + 67% 부분 | **80%+ 완전** |
| KAIR 전체 미구현 기능 | 4건 (DMN/캘린더/워크플로/BPMN) | **0건** |

---

> **문서 끝** — v1.3. 2026-03-24 기준 Canvas 프론트엔드 현황 분석, 구현 계획, UI/UX 품질 개선, KAIR 대비 갭 분석.
> **v1.3 추가**: KAIR 프론트엔드 19개 기능 교차 비교 (섹션 8), 전체 미구현 4건 + 부분 갭 6건 상세,
> Phase F (KAIR 이식) ~36 신규 파일 + ~5,240 LOC 로드맵 추가. 총 구현 규모 ~13,040 LOC.
> **핵심 메시지**: 기능 갭(Phase A-D) + UI/UX 갭(Phase E) + KAIR 이식 갭(Phase F) 3축 개선 필요.
