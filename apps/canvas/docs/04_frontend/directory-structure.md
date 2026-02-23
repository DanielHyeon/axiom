# 디렉토리 구조 상세

<!-- affects: frontend -->
<!-- requires-update: 01_architecture/component-architecture.md -->

## 이 문서가 답하는 질문

- Canvas 프로젝트의 파일 구조는 어떻게 되어 있는가?
- 각 디렉토리의 역할과 규칙은 무엇인가?
- 새 파일을 추가할 때 어디에 놓아야 하는가?
- K-AIR의 파일 구조와 무엇이 달라지는가?

---

## 1. 전체 디렉토리 구조

```
apps/canvas/
├── public/                          # 정적 파일 (favicon, robots.txt)
├── src/
│   ├── App.tsx                      # 루트 컴포넌트 (라우트 정의 포함)
│   ├── main.tsx                     # 진입점 (QueryClientProvider 래핑)
│   │
│   ├── features/                    # ★ 기능별 모듈 (핵심)
│   │   ├── case-dashboard/          # 1. 케이스 대시보드 (API: lib/api/casesApi.ts)
│   │   │   ├── components/
│   │   │   │   ├── CaseTable.tsx
│   │   │   │   ├── CaseTimeline.tsx
│   │   │   │   ├── StatsCard.tsx
│   │   │   │   ├── CaseFilters.tsx
│   │   │   │   ├── ApprovalQueuePanel.tsx
│   │   │   │   ├── MyWorkitemsPanel.tsx
│   │   │   │   └── ...
│   │   │   ├── hooks/
│   │   │   │   ├── useCases.ts
│   │   │   │   ├── useCaseStats.ts
│   │   │   │   ├── useCaseFilters.ts
│   │   │   │   ├── useApprovalQueue.ts
│   │   │   │   ├── useMyWorkitems.ts
│   │   │   │   └── useCaseActivities.ts
│   │   │   └── ...
│   │   │
│   │   ├── document-management/     # 2. 문서 관리 + HITL
│   │   │   ├── components/
│   │   │   │   ├── DocumentList.tsx
│   │   │   │   ├── DocumentEditor.tsx
│   │   │   │   ├── DocumentDiffViewer.tsx
│   │   │   │   ├── ReviewPanel.tsx
│   │   │   │   ├── InlineComment.tsx
│   │   │   │   └── ApprovalWorkflow.tsx
│   │   │   ├── hooks/
│   │   │   ├── api/
│   │   │   └── index.ts
│   │   │
│   │   ├── what-if-builder/         # 3. What-if 시나리오
│   │   │   ├── components/
│   │   │   │   ├── ScenarioPanel.tsx
│   │   │   │   ├── ParameterSlider.tsx
│   │   │   │   ├── TornadoChart.tsx
│   │   │   │   ├── ScenarioComparison.tsx
│   │   │   │   └── SensitivityMatrix.tsx
│   │   │   ├── hooks/
│   │   │   ├── api/
│   │   │   └── index.ts
│   │   │
│   │   ├── olap-pivot/              # 4. OLAP 피벗 테이블
│   │   │   ├── components/
│   │   │   │   ├── PivotBuilder.tsx
│   │   │   │   ├── PivotTable.tsx
│   │   │   │   ├── DimensionPalette.tsx
│   │   │   │   ├── DrilldownBreadcrumb.tsx
│   │   │   │   ├── ChartSwitcher.tsx
│   │   │   │   └── PivotFilters.tsx
│   │   │   ├── hooks/
│   │   │   ├── api/
│   │   │   ├── stores/
│   │   │   │   └── pivotConfigStore.ts
│   │   │   └── index.ts
│   │   │
│   │   ├── ontology-browser/        # 5. 온톨로지 브라우저
│   │   │   ├── components/
│   │   │   │   ├── GraphViewer.tsx
│   │   │   │   ├── NodeDetail.tsx
│   │   │   │   ├── LayerFilter.tsx
│   │   │   │   ├── PathHighlighter.tsx
│   │   │   │   └── SearchPanel.tsx
│   │   │   ├── hooks/
│   │   │   ├── api/
│   │   │   └── index.ts
│   │   │
│   │   ├── nl2sql-chat/             # 6. NL2SQL 대화형 쿼리
│   │   │   ├── components/
│   │   │   │   ├── ChatInterface.tsx
│   │   │   │   ├── MessageBubble.tsx
│   │   │   │   ├── SqlPreview.tsx
│   │   │   │   ├── ResultTable.tsx
│   │   │   │   ├── QueryHistory.tsx
│   │   │   │   └── ChartRecommender.tsx
│   │   │   ├── hooks/
│   │   │   ├── api/
│   │   │   └── index.ts
│   │   │
│   │   ├── watch/                   # 7. Watch 알림 (API: lib/api/watch.ts + watchStream.ts)
│   │   │   ├── components/
│   │   │   │   └── WatchToastListener.tsx
│   │   │   ├── hooks/
│   │   │   │   ├── useAlerts.ts
│   │   │   │   └── useWatchRules.ts
│   │   │   ├── store/
│   │   │   │   └── useWatchStore.ts
│   │   │   └── types/
│   │   │       └── watch.ts
│   │   │   (AlertRuleEditor, AlertFeed 등은 pages/watch/ 에 위치)
│   │   │
│   │   ├── process-designer/          # 8. 비즈니스 프로세스 디자이너 (store: stores/processDesignerStore.ts)
│   │   │   ├── components/
│   │   │   │   ├── ProcessCanvas/
│   │   │   │   │   ├── ProcessCanvas.tsx
│   │   │   │   │   ├── CanvasItem.tsx
│   │   │   │   │   ├── ConnectionLine.tsx
│   │   │   │   │   ├── ContextBox.tsx
│   │   │   │   │   └── CollaboratorCursors.tsx
│   │   │   │   ├── ProcessToolbox/
│   │   │   │   │   ├── ProcessToolbox.tsx
│   │   │   │   │   └── ToolboxItem.tsx
│   │   │   │   ├── ProcessPropertyPanel/
│   │   │   │   │   ├── ProcessPropertyPanel.tsx
│   │   │   │   │   ├── TemporalProperties.tsx
│   │   │   │   │   ├── MeasureBinding.tsx
│   │   │   │   │   └── EventLogBinding.tsx
│   │   │   │   ├── ProcessMinimap/
│   │   │   │   │   └── ProcessMinimap.tsx
│   │   │   │   └── ProcessVariantPanel/
│   │   │   │       ├── ConformanceOverlay.tsx
│   │   │   │       └── VariantList.tsx
│   │   │   ├── hooks/
│   │   │   │   ├── useProcessBoard.ts
│   │   │   │   ├── useYjsCollaboration.ts
│   │   │   │   ├── useCanvasInteraction.ts
│   │   │   │   ├── useProcessMining.ts
│   │   │   │   └── useCanvasKeyboard.ts
│   │   │   ├── api/
│   │   │   │   ├── processApi.ts
│   │   │   │   └── processApi.types.ts
│   │   │   ├── types/
│   │   │   │   ├── canvasItem.types.ts
│   │   │   │   ├── connection.types.ts
│   │   │   │   └── board.types.ts
│   │   │   └── ... (store는 src/stores/processDesignerStore.ts)
│   │   │
│   │   └── datasource/              # 데이터소스 관리 (Weaver API)
│   │       ├── components/
│   │       │   ├── SchemaExplorer.tsx
│   │       │   └── SyncProgress.tsx
│   │       ├── hooks/
│   │       │   └── useDatasources.ts
│   │       └── api/
│   │           └── weaverDatasourceApi.ts
│   │
│   ├── pages/                       # 라우트 페이지 (React.lazy)
│   │   ├── dashboard/
│   │   │   └── CaseDashboardPage.tsx
│   │   ├── cases/
│   │   │   ├── CaseListPage.tsx
│   │   │   ├── CaseDetailPage.tsx
│   │   │   ├── CaseDocumentsListPage.tsx
│   │   │   └── CaseDocumentEditorPage.tsx
│   │   ├── documents/
│   │   │   └── DocumentReviewPage.tsx
│   │   ├── whatif/
│   │   │   └── WhatIfPage.tsx
│   │   ├── olap/
│   │   │   └── OlapPivotPage.tsx
│   │   ├── nl2sql/
│   │   │   └── Nl2SqlPage.tsx
│   │   ├── ontology/
│   │   │   └── OntologyBrowser.tsx
│   │   ├── data/
│   │   │   └── DatasourcePage.tsx
│   │   ├── process-designer/
│   │   │   └── ProcessDesignerListPage.tsx
│   │   ├── process/
│   │   │   └── ProcessDesignerPage.tsx
│   │   ├── watch/
│   │   │   └── WatchDashboardPage.tsx
│   │   ├── settings/
│   │   │   ├── SettingsPage.tsx
│   │   │   ├── SettingsSystemPage.tsx
│   │   │   ├── SettingsLogsPage.tsx
│   │   │   ├── SettingsUsersPage.tsx
│   │   │   └── SettingsConfigPage.tsx
│   │   ├── auth/
│   │   │   ├── LoginPage.tsx
│   │   │   └── CallbackPage.tsx
│   │   └── errors/
│   │       ├── NotFoundPage.tsx
│   │       └── ErrorPage.tsx
│   │
│   ├── components/                  # 전역 컴포넌트 (에러 경계, 보호 라우트, UI)
│   │   ├── GlobalErrorBoundary.tsx
│   │   ├── PageErrorBoundary.tsx
│   │   ├── ProtectedRoute.tsx
│   │   ├── ServiceStatusBanner.tsx
│   │   └── ui/                      # Shadcn/ui (button, card, input, select 등)
│   │
│   ├── shared/                      # 공유 컴포넌트/유틸
│   │   ├── components/
│   │   │   ├── EmptyState.tsx
│   │   │   └── RoleGuard.tsx        # 역할 기반 접근 (admin 등)
│   │   └── hooks/
│   │       └── useRole.ts
│   │
│   ├── layouts/                     # 레이아웃
│   │   ├── RootLayout.tsx           # 최상위 (Outlet만)
│   │   ├── MainLayout.tsx           # 사이드바 + 헤더 + Outlet (대시보드용)
│   │   ├── Sidebar.tsx
│   │   ├── DashboardLayout.tsx      # (선택 사용)
│   │   └── components/
│   │       ├── Header.tsx
│   │       ├── UserMenu.tsx
│   │       ├── NotificationBell.tsx
│   │       ├── LocaleToggle.tsx
│   │       └── ThemeToggle.tsx
│   │
│   ├── stores/                      # 전역 Zustand 스토어
│   │   ├── authStore.ts
│   │   ├── themeStore.ts
│   │   └── processDesignerStore.ts
│   │
│   ├── lib/                         # 라이브러리 설정/API
│   │   ├── queryClient.ts
│   │   ├── routes/
│   │   │   ├── routeConfig.tsx      # createBrowserRouter 정의
│   │   │   ├── routes.ts            # ROUTES 상수
│   │   │   └── params.ts
│   │   ├── i18n/                    # 다국어 (locales, index)
│   │   └── api/
│   │       ├── clients.ts           # coreApi, weaverApi, oracleApi 등
│   │       ├── createApiClient.ts
│   │       ├── casesApi.ts           # 케이스/Core API
│   │       ├── processApi.ts
│   │       ├── watch.ts              # Watch 규칙 CRUD
│   │       ├── watchStream.ts        # Watch SSE (EventSource)
│   │       ├── streamManager.ts      # POST 스트림 (LLM/ReAct)
│   │       ├── wsManager.ts
│   │       ├── health.ts
│   │       ├── usersApi.ts
│   │       ├── settingsApi.ts
│   │       └── agentApi.ts
│   │
│   ├── types/                        # 공유 TypeScript 타입
│   │   └── auth.types.ts
│   ├── providers/                   # 앱급 Provider (테마 등)
│   │   └── ThemeProvider.tsx
│   ├── styles/
│   │   └── tokens.css
│   ├── index.css                    # 글로벌 스타일 (Tailwind)
│   └── vite-env.d.ts
│
├── docs/                            # 기술 문서 (현재 디렉토리)
│   ├── 00_overview/
│   ├── 01_architecture/
│   ├── 02_api/
│   ├── 03_backend/
│   ├── 04_frontend/
│   ├── 05_llm/
│   ├── 06_data/
│   ├── 07_security/
│   ├── 08_operations/
│   └── 99_decisions/
│
├── tests/                           # 테스트
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── .env.development
├── .env.staging
├── .env.production
├── index.html
├── package.json
├── tsconfig.json
├── tailwind.config.ts
├── vite.config.ts
├── postcss.config.js
└── components.json                  # Shadcn/ui 설정
```

---

## 2. 디렉토리 규칙

### 2.1 배치 기준

| 파일 유형 | 위치 | 기준 |
|-----------|------|------|
| 특정 Feature 전용 컴포넌트 | `features/{name}/components/` | 해당 Feature 내에서만 사용 |
| 특정 Feature 전용 훅 | `features/{name}/hooks/` | 해당 Feature의 비즈니스 로직 |
| 특정 Feature 전용 API | `features/{name}/api/` | 해당 Feature의 서버 통신 |
| 라우트 페이지 컴포넌트 | `pages/{section}/` | React.lazy로 코드 분할 |
| 2개 이상 Feature에서 사용 | `shared/components/` | 비즈니스 로직 없는 순수 UI |
| Shadcn/ui 기본 컴포넌트 | `components/ui/` | `npx shadcn-ui add`로 자동 생성 |
| 전역 상태 스토어 | `stores/` | Feature 간 공유 상태 |
| Feature 전용 스토어 | `features/{name}/stores/` | 해당 Feature 내부 상태 |
| Axios/WS/SSE 설정 | `lib/api/` | 인프라 계층 |
| 레이아웃 (Sidebar, Header) | `layouts/` | 라우트 레이아웃 |

### 2.2 K-AIR vs Canvas 구조 비교

```
K-AIR (process-gpt-vue3):          Canvas:
src/                                src/
├── components/                     ├── features/           # 기능 중심
│   ├── admin/                      │   ├── case-dashboard/
│   ├── apps/                       │   │   ├── components/
│   │   └── chats/                  │   │   ├── hooks/
│   ├── designer/                   │   │   └── api/
│   ├── analytics/                  │   ├── document-mgmt/
│   └── ...                         │   └── ...
├── views/                          ├── pages/              # 라우트 전용
│   ├── Dashboard.vue               │   ├── dashboard/
│   ├── Login.vue                   │   ├── cases/
│   └── ...                         │   └── ...
├── stores/                         ├── stores/             # 전역만
│   ├── appStore.ts                 │   ├── authStore.ts
│   ├── authStore.ts                │   └── uiStore.ts
│   └── ...                         ├── shared/             # 공용 UI
├── router/                         │   ├── ui/
│   └── index.ts                    │   └── components/
├── plugins/                        ├── lib/                # 인프라
│   └── vuetify.ts                  │   └── api/
└── utils/                          └── layouts/
    └── backend.ts
```

핵심 차이: K-AIR는 **기술 기준**(components, views, stores)으로 분리되어 관련 파일이 흩어져 있었다. Canvas는 **기능 기준**(case-dashboard, document-management)으로 분리되어 관련 파일이 한 곳에 모인다.

---

## 3. 네이밍 컨벤션

| 대상 | 컨벤션 | 예시 |
|------|--------|------|
| 디렉토리 | kebab-case | `case-dashboard`, `shared` |
| React 컴포넌트 파일 | PascalCase.tsx | `CaseTable.tsx` |
| Hook 파일 | camelCase.ts (use 접두어) | `useCases.ts` |
| Store 파일 | camelCase.ts (Store 접미어) | `authStore.ts` |
| API 파일 | camelCase.ts (Api 접미어) | `caseApi.ts` |
| 타입 파일 | camelCase.types.ts | `case.types.ts` |
| 유틸리티 파일 | camelCase.ts | `format.ts` |
| 테스트 파일 | 원본파일.test.tsx | `CaseTable.test.tsx` |
| 상수 | UPPER_SNAKE_CASE | `MAX_PAGE_SIZE` |
| CSS 클래스 | Tailwind 유틸리티 | `className="flex gap-4"` |

---

## 결정 사항 (Decisions)

- Feature-based 디렉토리 구조 (기술 분류 아님)
  - 근거: 관련 파일 co-location, Feature 삭제/추가 용이
  - 재평가: 팀원이 구조에 혼란을 느끼면 가이드 워크숍 진행

- `components/ui/`와 `shared/components/` 분리
  - 근거: Shadcn/ui 자동 생성 파일과 커스텀 확장을 구분
  - 규칙: `components/ui/`는 Shadcn CLI로 추가·갱신, 직접 수정 최소화

---

## 변경 이력

| 날짜 | 버전 | 작성자 | 내용 |
|------|------|--------|------|
| 2026-02-19 | 1.0 | Axiom Team | 초기 작성 |
| 2026-02-20 | 1.1 | Axiom Team | process-designer feature 모듈 및 페이지 추가 |
| 2026-02-22 | 1.2 | Axiom Team | 현재 구현 반영: src/ 직하위 App·main, layouts(RootLayout·MainLayout·Sidebar·components), components/·components/ui/, lib/queryClient·watchStream·streamManager, 설정 하위 페이지, pages 경로 정리 |
| 2026-02-23 | 1.3 | Axiom Team | 현행화: lib/routes/routeConfig.tsx, lib/api 파일 목록(clients·casesApi·watch·watchStream 등), case-dashboard(lib/api/casesApi 사용), watch·datasource·process-designer 구조, shared/RoleGuard·useRole, stores/themeStore·processDesignerStore, providers·styles |
