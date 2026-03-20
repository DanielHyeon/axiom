# 프론트엔드 UI/UX 미구현·갭 현황

> **기준**: `canvas/docs/04_frontend/` 설계 vs `canvas/src/` 실제 구현
> **갱신일**: 2026-03-21 (KAIR 갭 Phase 1-3 구현 후 전면 검증)

---

## 1. 이미 해소된 항목 (갭 문서 대비 현재 구현됨)

| 설계 항목 | 현재 구현 | 비고 |
|-----------|-----------|------|
| `/settings` 및 하위 라우트 | ✅ `/settings`, `/settings/system`, `/settings/users` | SettingsPage, SettingsSystemPage, SettingsUsersPage |
| 설정 페이지·라우트 | ✅ 설정 탭(시스템/사용자), Outlet 하위 라우트 | |
| `/cases`, `/cases/:caseId`, `/cases/:caseId/documents`, `/:docId/review`, `/cases/:caseId/scenarios` | ✅ App.tsx에 동일 구조 | CaseListPage, CaseDetailPage, CaseDocumentsListPage, CaseDocumentEditorPage, DocumentReviewPage, WhatIf(scenarios) |
| `/dashboard` | ✅ `ROUTES.DASHBOARD` → `/dashboard`, index에서 리다이렉트 | |
| `/auth/login`, `/auth/callback` | ✅ ROUTES.AUTH.LOGIN, CALLBACK, CallbackPage | |
| `/analysis/olap`, `/analysis/nl2sql` | ✅ `/analysis/olap`, `/analysis/nl2sql` | |
| `/analysis/insight` | ✅ `ROUTES.ANALYSIS.INSIGHT` → `/analysis/insight`, InsightPage (KPI Impact Graph + Cytoscape) | Sidebar에 Insight 항목 추가, useInsightStore(Zustand), useImpactGraph(202 폴링), ImpactGraphViewer, KpiSelector, QuerySubgraphViewer 구현 |
| `/data/ontology`, `/data/datasources` | ✅ `/data/ontology`, `/data/datasources` | DatasourcePage 존재 |
| `/process-designer`, `/process-designer/:boardId` | ✅ ProcessDesignerListPage, ProcessDesignerPage(:boardId) | |
| 라우트 상수 | ✅ `lib/routes/routes.ts` ROUTES 객체 | |
| 타입 안전 파라미터 훅 | ✅ `lib/routes/params.ts` useCaseParams, useDocumentParams, useBoardParams | |
| 404 전용 페이지 | ✅ `<Route path="*" element={<NotFoundPage />} />` | |
| React.lazy + Suspense per route | ✅ 모든 페이지 lazy, SuspensePage 래퍼 | |
| 케이스 대시보드: StatsCard, CaseTable, CaseTimeline, CaseDistributionChart | ✅ CaseDashboardPage에서 사용 | |
| 역할별 패널 (MyWorkitemsPanel, ApprovalQueuePanel) | ✅ useDashboardConfig 기반 표시 | |
| QuickActionsPanel, RoleGreeting | ✅ CaseDashboardPage에 포함 | |
| CaseListPage, CaseDetailPage 별도 페이지 | ✅ 라우트·페이지 존재 | |
| CaseFilters | ✅ CaseListPage에서 사용 | (대시보드에는 미사용) |
| DocumentReviewPage, ReviewPanel, DocumentDiffViewer | ✅ DocumentReviewPage에서 사용 | |
| Watch: AlertRuleEditor, EventTimeline | ✅ WatchDashboardPage에서 사용 | |
| 데이터소스 전용 페이지 | ✅ DatasourcePage, `/data/datasources` | |

---

## 2. UI/UX 미구현·갭 (아직 부족한 부분)

### 2.1 구조·경로 (Medium)

| 항목 | 설계 | 현재 | 갭 |
|------|------|------|-----|
| app 디렉터리 | `src/app/` (App, router, providers, queryClient) | `src/App.tsx`, `src/main.tsx` | **app/ 폴더 구조 없음** — 진입/라우터가 루트에 있음 |
| Shadcn 위치 | `src/shared/ui/` | `src/components/ui/` | **경로 불일치** (기능상 문제 없음) |
| 공유 컴포넌트 | 일원화 | `shared/components/` + `components/shared/` 혼재 | **이중 위치** — DataTable 등 분산 |

### 2.2 라우팅·에러 UI (Low)

| 항목 | 설계 | 현재 | 갭 |
|------|------|------|-----|
| Data router | `createBrowserRouter` (data loader 등) | `BrowserRouter` + `Routes` | **선언적 라우터만 사용** |
| ErrorPage 사용 | 라우트 `errorElement` 또는 ErrorBoundary fallback | ✅ **해소** — GlobalErrorBoundary가 에러 시 ErrorPage 렌더 | |

### 2.3 레이아웃·공통 UI (대부분 해소)

| 항목 | 설계 | 현재 | 갭 |
|------|------|------|-----|
| RootLayout | 계층적 Root → Dashboard/Auth | ✅ **해소** — `layouts/RootLayout.tsx` 존재, AuthLayout도 별도 | |
| Sidebar 모듈화 | Sidebar.tsx, SidebarNav, SidebarItem | ✅ **해소** — `layouts/Sidebar.tsx` 분리, 17개 navItems + Settings | |
| Header / UserMenu | 상단 헤더, 유저 메뉴 | ✅ **해소** — `Header`(NotificationBell + UserMenu + LocaleToggle + ThemeToggle + PageTabHeader) | |
| Design Tokens·다크 모드 | 전역 토큰, 테마 전환 | ✅ **해소** — `styles/tokens.css`, `themeStore`, `ThemeProvider`, `.dark` 클래스 | 일부 인라인 hex 혼용 잔존 (P2) |

### 2.4 설정 하위 라우트 (Low)

| 항목 | 설계 | 현재 | 갭 |
|------|------|------|-----|
| 설정 하위 | /system, /logs, /users, /config | ✅ **해소** — /system, /logs, /users, /config 모두 라우트·탭·페이지 존재 | |

### 2.5 Feature별 컴포넌트 갭 (Medium)

| Feature | 설계 | 현재 | 갭 |
|---------|------|------|-----|
| 온톨로지 | PathHighlighter (경로 하이라이트) | ✅ **해소** — `PathHighlighter` 컴포넌트, OntologyPage에서 사용 | |
| What-if | ScenarioComparison (복수 시나리오 열 비교) | ✅ **해소** — `ScenarioComparison` 컴포넌트, WhatIfPage 비교 결과 테이블에 사용 | |
| 케이스 대시보드 | CaseFilters를 대시보드에서도 사용 | CaseFilters는 CaseListPage에만 사용 | **대시보드에 필터** 넣을지 선택 사항 |
| 프로세스 디자이너 | ProcessMinimap, PropertyPanel, Yjs 협업, ConformanceOverlay, VariantList | ProcessDesignerPage에 툴박스·드래그 등 있음 | **Minimap·PropertyPanel·Yjs·마이닝 오버레이·변형 패널** 설계 대비 완성도 갭 가능 |

### 2.6 인프라·공통 (일부 해소)

| 항목 | 설계 | 현재 | 갭 |
|------|------|------|-----|
| i18n | react-i18next, ko/en | ✅ **인프라 해소** — `lib/i18n/`, `LocaleToggle.tsx`, `useTranslation()` 사용 | 번역 리소스 비어있음 (하드코딩 텍스트 100+곳 잔존) |
| 페이지 단위 ErrorBoundary | 라우트/페이지별 | ✅ **해소** — `PageErrorBoundary` 존재, MainLayout에서 적용 | |
| 폼 표준 | React Hook Form + Zod | 부분 적용 | 사용처 제한적 |
| TanStack Query 전역 옵션 | retry, staleTime, mutation onError | ✅ **해소** — `lib/queryClient.ts` 설정 | |
| wsManager / sseManager 표준화 | 공통 매니저 | ✅ **해소** — `lib/api/wsManager.ts`, `lib/api/watchStream.ts`, `lib/api/streamManager.ts` | |

### 2.7 테스트·문서 (Low)

| 항목 | 설계 | 현재 | 갭 |
|------|------|------|-----|
| Vitest + RTL 단위·통합 | 테스트 피라미드 | E2E 스펙 일부 (Playwright) | **단위/통합 테스트** 설정·커버리지 |
| 설계 문서 동기화 | directory-structure, routing 등 | routing.md에 createBrowserRouter 예시 등 일부 불일치 | **문서 ↔ 코드** 동기화 |

---

## 3. 우선순위별 정리 (2026-03-21 기준)

### 해소됨 (이전 우선순위 항목 중 구현 완료)
- ~~Header/UserMenu~~ -- 해소 (Header, UserMenu, NotificationBell, LocaleToggle, ThemeToggle)
- ~~ErrorPage 연동~~ -- 해소 (GlobalErrorBoundary + PageErrorBoundary)
- ~~Sidebar 모듈화~~ -- 해소 (layouts/Sidebar.tsx, 17개 navItems)
- ~~PathHighlighter, ScenarioComparison~~ -- 해소 (둘 다 구현됨)
- ~~설정 /logs, /config~~ -- 해소 (/system, /logs, /users, /config, /feedback, /security 6개 탭)
- ~~i18n 인프라~~ -- 해소 (react-i18next, LocaleToggle)
- ~~디자인 토큰·다크 모드~~ -- 해소 (tokens.css, themeStore, ThemeProvider)
- ~~KAIR 갭 Phase 1-3~~ -- 해소 (보안관리, 도메인모델러, What-if위자드, 데이터수집, DQ, 온톨로지위자드, 글로서리, 리니지, 오브젝트탐색기)

### 남은 높음 (P0/P1)
- **i18n 번역 리소스**: ko.json / en.json 작성 필요 (하드코딩 한국어 100+곳)
- **@ts-nocheck 제거**: InsightPage, Nl2SqlPage, GraphViewer, ReactProgressTimeline 4파일
- **Silent fail 에러 처리**: 8건 (toast 미표시)
- **Insight 백엔드 API 갭**: `GET /api/insight/kpis`, `GET /api/insight/drivers`, `GET /api/insight/nodes/{id}` 미구현

### 남은 중간 (P2)
- **접근성 (a11y)**: aria-label 누락 다수
- **반응형 디자인**: 모바일 미대응 3건
- **테마 일관성**: 인라인 hex와 Tailwind 색상 혼용
- **단위 테스트**: Vitest 설정 + 핵심 함수 테스트 0건

### 남은 낮음 (P3)
- **app/ 디렉터리 구조**: 진입·라우터를 app/ 아래로 이동 (선택).
- **shared/ui vs components/ui**: 경로 통일 (선택).
- **store/ vs stores/ 명명 불일치**: 일부 Feature는 단수, 일부는 복수형 사용

---

## 4. 참조

- 상세 갭 원본: `docs/04_status/frontend-gap-analysis.md`
- 라우트·설계: `canvas/docs/04_frontend/routing.md`, `directory-structure.md`, `feature-priority-matrix.md`
