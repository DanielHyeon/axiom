# 프론트엔드 UI/UX 미구현·갭 현황

> **기준**: `apps/canvas/docs/04_frontend/` 설계 vs `apps/canvas/src/` 실제 구현  
> **갱신일**: 2026-02-22 (코드베이스 검증 반영)

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

### 2.3 레이아웃·공통 UI (Medium)

| 항목 | 설계 | 현재 | 갭 |
|------|------|------|-----|
| RootLayout | 계층적 Root → Dashboard/Auth | MainLayout이 사실상 루트 레이아웃 | **RootLayout 개념 없음** |
| Sidebar 모듈화 | Sidebar.tsx, SidebarNav, SidebarItem | ✅ **해소** — `layouts/Sidebar.tsx` 분리, MainLayout에서 사용 | |
| Header / UserMenu | 상단 헤더, 유저 메뉴 | ✅ **해소** — `Header`(NotificationBell + UserMenu), 로그아웃·설정 링크 | |
| Design Tokens·다크 모드 | 전역 토큰, 테마 전환 | 미적용 (gray/white 등 하드코딩), Monaco만 vs-dark | **디자인 토큰·다크 모드 전역 미구현** |

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

### 2.6 인프라·공통 (Medium)

| 항목 | 설계 | 현재 | 갭 |
|------|------|------|-----|
| i18n | react-i18next, ko/en | 없음 | **i18n 미도입** — 문자열 하드코딩 |
| 페이지 단위 ErrorBoundary | 라우트/페이지별 | GlobalErrorBoundary 만 | **페이지 단위 ErrorBoundary** 미적용 |
| 폼 표준 | React Hook Form + Zod | 사용처 제한적 | **폼 표준** 적용 범위 확인 필요 |
| TanStack Query 전역 옵션 | retry, staleTime, mutation onError | 설정 미확인 | **queryClient 옵션** 설계 대비 확인 |
| wsManager / sseManager 표준화 | 공통 매니저 | watch 등에서 API·EventSource 사용 | **표준화 여부** 확인 |

### 2.7 테스트·문서 (Low)

| 항목 | 설계 | 현재 | 갭 |
|------|------|------|-----|
| Vitest + RTL 단위·통합 | 테스트 피라미드 | E2E 스펙 일부 (Playwright) | **단위/통합 테스트** 설정·커버리지 |
| 설계 문서 동기화 | directory-structure, routing 등 | routing.md에 createBrowserRouter 예시 등 일부 불일치 | **문서 ↔ 코드** 동기화 |

---

## 3. 우선순위별 정리

### 높음 (UX 일관성·필수 화면)
- **Header/UserMenu**: MainLayout 상단에 헤더·유저 메뉴 추가 시 네비게이션·로그아웃 등 접근성 향상.
- **ErrorPage 연동**: GlobalErrorBoundary fallback을 ErrorPage 컴포넌트로 렌더하면 에러 UI 일관.

### 중간 (설계 정합성·재사용)
- **Sidebar 모듈화**: MainLayout의 nav를 Sidebar.tsx 등으로 분리.
- **PathHighlighter, ScenarioComparison**: 온톨로지·What-if 설계 대비 보완.
- **설정 /logs, /config**: 설계에 포함된 경우 해당 탭·라우트 추가.
- **i18n**: 다국어 필요 시 react-i18next 도입.
- **디자인 토큰·다크 모드**: 전역 테마 적용 시.

### 낮음 (구조·품질)
- **app/ 디렉터리 구조**: 진입·라우터를 app/ 아래로 이동 (선택).
- **shared/ui vs components/ui**: 경로 통일 (선택).
- **createBrowserRouter**: data loader 등 필요 시 전환.
- **단위/통합 테스트**: Vitest·RTL 확대.

---

## 4. 참조

- 상세 갭 원본: `docs/frontend-design-gap-analysis.md`
- 라우트·설계: `apps/canvas/docs/04_frontend/routing.md`, `directory-structure.md`, `feature-priority-matrix.md`
