# 프론트엔드 구성 설계 대비 갭 분석

설계 문서 기준: `apps/canvas/docs/04_frontend/` (directory-structure, routing, feature-priority-matrix, implementation-guide, case-dashboard 등)  
대상 구현: `apps/canvas/src/`  
작성일: 2026-02-22

---

## 1. 디렉토리·구조 갭

| 설계 | 실제 | 갭 |
|------|------|-----|
| `src/app/` (App.tsx, router.tsx, providers.tsx, queryClient.ts) | `src/App.tsx`, `src/main.tsx`만 존재, `app/` 디렉터리 없음 | **구조 불일치**: app 진입/라우터/프로바이더가 설계와 다름 |
| `src/shared/ui/` (Shadcn) | `src/components/ui/` | **경로 불일치**: Shadcn 컴포넌트가 `shared/ui`가 아닌 `components/ui`에 위치 |
| `src/shared/components/` | `src/shared/components/` + `src/components/shared/` 혼재 (DataTable 등) | **이중 위치**: 공유 컴포넌트가 shared/와 components/shared/에 분산 |
| Feature별 `components/`, `hooks/`, `api/`, `stores/`, `types/` | case-dashboard, watch, ontology, olap, whatif, nl2sql은 일부 feature 구조. document/process 등은 pages 내부에 컴포넌트 | **Feature 모듈화 불완전**: 문서·프로세스는 feature 폴더 없이 page 중심 |
| `pages/dashboard/`, `pages/cases/`, `pages/documents/` 등 | `pages/dashboard/`, `pages/documents/`, `pages/analytics/`, `pages/ontology/`, `pages/watch/`, `pages/nl2sql/`, `pages/process/`, `pages/olap/`, `pages/whatif/` | **cases/ 없음**, analysis vs analytics, 페이지 분리 방식 상이 |
| `lib/routes/routes.ts`, `lib/routes/params.ts` | 없음 | **라우트 상수·타입 안전 파라미터 훅 미구현** |
| `lib/i18n/` (ko.json, en.json) | 없음 | **i18n 미도입**: 문자열 하드코딩 |

---

## 2. 라우팅 갭

| 설계 라우트 | 실제 | 갭 |
|-------------|------|-----|
| `/auth/login`, `/auth/callback` | `/login` 만 존재 | **auth prefix 없음**, **CallbackPage 없음** (OAuth 미지원) |
| `/` → `/dashboard` 리다이렉트 | `/` = 대시보드 (index), `/dashboard` 라우트 없음 | **/dashboard 경로 없음** |
| `/dashboard` | `/` (index) | 동일 기능, 경로만 상이 |
| `/cases`, `/cases/:caseId`, `/cases/:caseId/documents`, `/:docId`, `/:docId/review`, `/cases/:caseId/scenarios` | 없음. `/documents` 플랫, `/analytics/what-if` 존재 | **케이스 중첩 라우트 전부 없음**: 케이스 컨텍스트 기반 문서/시나리오 경로 미구현 |
| `/analysis/olap`, `/analysis/nl2sql` | `/analytics/pivot`, `/nl2sql` | **경로 명칭 불일치** (analysis vs analytics, olap vs pivot) |
| `/data/ontology`, `/data/datasources` | `/ontology` 만 존재 | **/data prefix 없음**, **데이터소스 전용 페이지/라우트 없음** |
| `/process-designer`, `/process-designer/:boardId` | `/process` 단일 | **process-designer 명칭·보드 ID 라우트 없음** (다중 보드 진입 불가) |
| `/watch` | `/watch` | 일치 |
| `/settings` | 없음 | **설정 페이지·라우트 없음** |
| 404: `NotFoundPage`, Error: `ErrorPage` | 404: `<div>Page Not Found</div>`, 전역 `GlobalErrorBoundary` 존재 | **NotFound/Error 전용 페이지 컴포넌트 미사용** |
| 모든 페이지 `React.lazy()` + Suspense | 전부 정적 import | **코드 분할 미적용** |
| `createBrowserRouter` (data router) | `BrowserRouter` + `Routes` | **선언적 라우터만 사용**, data router 미사용 |

---

## 3. 레이아웃·공통 UI 갭

| 설계 | 실제 | 갭 |
|------|------|-----|
| RootLayout, DashboardLayout, AuthLayout | MainLayout(사이드바+콘텐츠), DashboardLayout(별도 파일), AuthLayout 존재 | **RootLayout 개념 없음**, MainLayout이 사실상 Dashboard 레이아웃 |
| Sidebar/ (Sidebar.tsx, SidebarNav, SidebarItem) | MainLayout 내 인라인 nav, Sidebar 컴포넌트 분리 없음 | **Sidebar 모듈화 없음** |
| Header/ (Header, UserMenu, NotificationBell) | DashboardLayout에 NotificationBell 등 일부 있으나 MainLayout에는 헤더/유저메뉴 없음 | **Header/UserMenu 미통합** (일부만 별도 파일) |
| AuthGuard, RoleGuard | ProtectedRoute (AuthGuard 역할), RoleGuard 있음 | **이름만 상이**, 기능적으로 유사 |
| Design Tokens, 다크 모드 전환 | 미적용 (MainLayout gray/white), Monaco만 vs-dark | **전역 디자인 토큰·다크 모드 미구현** |

---

## 4. 기능(Feature)별 갭

### 4.1 케이스 대시보드 (P0)

| 설계 | 실제 | 갭 |
|------|------|-----|
| StatsCard x4, CaseFilters, CaseTable, CaseTimeline, CaseDistributionChart | CaseDashboardPage·useCases로 목록 표시 수준 | **StatsCard/필터/테이블/타임라인/차트** 설계 대비 단순 구현 |
| DashboardComposer, 역할별 패널 (MyWorkitemsPanel, ApprovalQueuePanel 등) | 없음 | **역할별 대시보드 합성·전용 패널 미구현** |
| QuickActionsPanel, RoleGreeting | 없음 | **바로가기·역할별 인사 미구현** |
| CaseListPage, CaseDetailPage (별도 페이지) | 케이스 목록이 대시보드 내부에만 존재 | **케이스 목록/상세 전용 페이지·라우트 없음** |

### 4.2 문서 관리 + HITL (P0)

| 설계 | 실제 | 갭 |
|------|------|-----|
| DocumentListPage, DocumentEditorPage, DocumentReviewPage | DocumentManager, DocumentListPage, DocumentEditorPage | **DocumentReviewPage(리뷰 전용)·케이스 중첩 경로 없음** |
| ReviewPanel, InlineComment, DocumentDiffViewer, ApprovalWorkflow | 미확인/부분 | **HITL 리뷰 패널·Diff 뷰어·승인 워크플로우** 설계 대비 부족 가능성 |
| 케이스 컨텍스트 (`/cases/:caseId/documents`) | `/documents` 플랫 | **문서가 케이스에 묶인 라우트 아님** |

### 4.3 NL2SQL (P1)

| 설계 | 실제 | 갭 |
|------|------|-----|
| ChatInterface, MessageBubble, SqlPreview, ResultTable, ChartRecommender, QueryHistory | Nl2SqlPage, MessageBubble, SqlPreview, ChartRecommender 등 존재 | **QueryHistory·전체 채팅 UI** 완성도·실 API 연동 여부 확인 필요 |
| SSE 스트리밍, useNl2sql 훅 | useNl2sqlMock 등 mock 사용 | **실제 Oracle API·SSE 연동** 대체 mock 가능성 |

### 4.4 OLAP 피벗 (P1)

| 설계 | 실제 | 갭 |
|------|------|-----|
| OlapPivotPage, PivotBuilder, DimensionPalette, PivotTable, DrilldownBreadcrumb, ChartSwitcher | OlapPivotPage, PivotBuilder, DimensionPalette, DroppableZone, DraggableItem 등 | **DrilldownBreadcrumb·ChartSwitcher·드릴다운 URL 동기화** 등 일부 누락 가능 |
| useOlapQuery, pivotConfigStore | usePivotConfig, useOlapMock | **실 Vision API 연동** 대체 mock 가능성 |

### 4.5 Watch 알림 (P1)

| 설계 | 실제 | 갭 |
|------|------|-----|
| WatchDashboardPage, AlertFeed, AlertCard, AlertRuleEditor, EventTimeline, PriorityFilter | WatchDashboardPage, AlertFeed, AlertStats, PriorityFilter 등 | **AlertRuleEditor·EventTimeline** 등 일부 컴포넌트 갭 |
| NotificationBell (Popover, 최근 5건, 전체 읽음) | NotificationBell, useNotificationBell 존재 | 일부 구현됨 |
| WebSocket 연동, 심각도별 토스트 | useAlerts 등에서 CustomEvent 등 사용 | **실제 Core WebSocket 프로토콜** 연동 여부 확인 필요 |

### 4.6 데이터소스 관리 (P2)

| 설계 | 실제 | 갭 |
|------|------|-----|
| DatasourcePage, DatasourceList, ConnectionForm, SchemaExplorer, SyncProgress | **라우트·전용 페이지 없음** | **데이터소스 관리 기능 미구현** |

### 4.7 프로세스 디자이너 (P2)

| 설계 | 실제 | 갭 |
|------|------|-----|
| ProcessDesignerListPage + ProcessDesignerPage(:boardId) | ProcessDesigner 단일, ProcessDesignerPage 별도 파일 있음 | **보드 목록 페이지·/:boardId 라우트 없음** |
| ProcessCanvas (react-konva), ProcessToolbox, ProcessPropertyPanel, ProcessMinimap, Yjs 협업 | ProcessDesignerPage에 툴박스·드래그 등 있음, store 있음 | **react-konva·Yjs·Minimap·PropertyPanel** 등 설계 대비 완성도 갭 |
| ConformanceOverlay, VariantList | 미구현 가능성 | **프로세스 마이닝 오버레이·변형 패널** 갭 |

### 4.8 What-if 시나리오 (P2)

| 설계 | 실제 | 갭 |
|------|------|-----|
| WhatIfPage, ScenarioPanel, ParameterSlider, TornadoChart, ScenarioComparison | WhatIfPage, ScenarioPanel, ParameterSlider, TornadoChart 등 | **ScenarioComparison·실 Vision API** 연동 여부 확인 |

### 4.9 온톨로지 브라우저 (P2)

| 설계 | 실제 | 갭 |
|------|------|-----|
| OntologyPage, GraphViewer, NodeDetail, LayerFilter, PathHighlighter, SearchPanel | OntologyPage, GraphViewer, NodeDetail, LayerFilter, SearchPanel 등 | **PathHighlighter·프로세스 디자이너 상호 네비게이션** 등 일부 갭 |

### 4.10 설정 (설계: admin-dashboard·routing)

| 설계 | 실제 | 갭 |
|------|------|-----|
| SettingsPage, /settings, (하위 /system, /logs, /users, /config) | **없음** | **설정 페이지·라우트 전부 미구현** |

---

## 5. 인프라·공통 구현 갭

| 설계 | 실제 | 갭 |
|------|------|-----|
| createApiClient, 5개 서비스 클라이언트 (core, vision, oracle, synapse, weaver) | createApiClient, clients.ts에 5개 export | **일치** |
| AppError, 인터셉터 (401 로그아웃 등) | createApiClient·errors.ts 존재 | **일치에 가깝음** |
| wsManager, sseManager (또는 streamManager) | watch.ts 등에서 API 호출, WebSocket 전용 매니저 미확인 | **wsManager/sseManager(또는 streamManager) 표준화 여부 확인** |
| TanStack Query 기본 옵션 (retry, staleTime, mutation onError) | queryClient 설정 미확인 | **전역 queryClient 옵션** 설계 대비 확인 필요 |
| ROUTES 상수, useCaseParams 등 타입 안전 파라미터 | 없음 | **라우트 상수·Zod 기반 파라미터 훅 미구현** |
| i18n (react-i18next, ko/en) | 없음 | **i18n 미도입**, 문자열 하드코딩 |
| ErrorBoundary per page | GlobalErrorBoundary 만 | **페이지 단위 ErrorBoundary** 미적용 |
| React.lazy + Suspense per route | 없음 | **라우트별 코드 분할 미적용** |
| React Hook Form + Zod (폼 표준) | 사용처 제한적 가능성 | **폼 표준** 적용 범위 확인 필요 |
| Vitest + RTL + Playwright 테스트 피라미드 | E2E 스펙 일부 존재 (smoke, nl2sql 등) | **단위/통합 테스트** 설정·커버리지 확인 필요 |

---

## 6. 요약·우선순위 제안

### Critical (설계와 구조·라우트 수준 불일치)

1. **케이스 중심 라우트 부재**: `/cases`, `/cases/:caseId`, `/cases/:caseId/documents`, `/cases/:caseId/scenarios` 미구현 → 문서·시나리오가 케이스에 묶이지 않음.
2. **데이터소스 관리 없음**: 라우트·페이지·Feature 전부 없음.
3. **설정 없음**: `/settings` 및 하위 라우트 없음.
4. **디렉토리/경로 불일치**: `app/` 부재, `shared/ui` vs `components/ui`, 공유 컴포넌트 이중 위치.

### High (핵심 기능·인프라)

5. **케이스 대시보드**: StatsCard, CaseTable, CaseTimeline, 역할별 패널, CaseList/CaseDetail 페이지 부족.
6. **문서 HITL**: 리뷰 전용 페이지, Diff 뷰어, 승인 워크플로우, 케이스 중첩 경로.
7. **라우트 정리**: `/auth/login`, `/dashboard`, `/analysis/*`, `/data/*`, `/process-designer`, `/process-designer/:boardId` 등 설계와 정렬.
8. **코드 분할·에러 UI**: React.lazy per page, NotFoundPage/ErrorPage 전용 컴포넌트.

### Medium (품질·일관성)

9. **i18n**: react-i18next 도입 및 문자열 외부화.
10. **디자인 시스템**: Design Tokens, 다크 모드 전역 적용.
11. **라우트 상수·타입 안전 파라미터**: ROUTES, useCaseParams 등.
12. **프로세스 디자이너**: 보드 목록·:boardId 라우트, Yjs·react-konva·마이닝 오버레이 완성도.

### Low (문서·테스트)

13. **테스트**: Vitest/RTL 단위·통합, Playwright E2E 범위 정리.
14. **문서 동기화**: directory-structure, routing 등 설계 문서를 현재 구조에 맞게 수정하거나, 구현을 설계에 맞추는 방향 결정.

---

이 문서는 설계 문서와 `apps/canvas/src` 구현을 비교한 갭 목록이며, 우선순위는 P0/P1 Feature 및 라우트 정합성 기준으로 제안한 것이다. 실제 스프린트 반영 시 리소스에 따라 Critical → High 순으로 처리하는 것을 권장한다.
