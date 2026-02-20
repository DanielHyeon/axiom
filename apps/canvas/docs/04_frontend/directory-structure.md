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
│   ├── app/                         # 앱 설정 (진입점, 프로바이더)
│   │   ├── App.tsx                  # 루트 컴포넌트
│   │   ├── providers.tsx            # 프로바이더 조합
│   │   ├── router.tsx               # React Router 설정
│   │   └── queryClient.ts           # TanStack Query 설정
│   │
│   ├── features/                    # ★ 기능별 모듈 (핵심)
│   │   ├── case-dashboard/          # 1. 케이스 대시보드
│   │   │   ├── components/
│   │   │   │   ├── CaseTable.tsx
│   │   │   │   ├── CaseCard.tsx
│   │   │   │   ├── CaseTimeline.tsx
│   │   │   │   ├── StatsCard.tsx
│   │   │   │   └── CaseFilters.tsx
│   │   │   ├── hooks/
│   │   │   │   ├── useCases.ts
│   │   │   │   ├── useCaseStats.ts
│   │   │   │   └── useCaseFilters.ts
│   │   │   ├── api/
│   │   │   │   ├── caseApi.ts
│   │   │   │   └── caseApi.types.ts
│   │   │   ├── stores/
│   │   │   │   └── caseFilterStore.ts
│   │   │   ├── types/
│   │   │   │   └── case.types.ts
│   │   │   └── index.ts
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
│   │   ├── watch-alerts/            # 7. Watch 알림
│   │   │   ├── components/
│   │   │   │   ├── AlertFeed.tsx
│   │   │   │   ├── AlertCard.tsx
│   │   │   │   ├── AlertRuleEditor.tsx
│   │   │   │   ├── EventTimeline.tsx
│   │   │   │   └── PriorityFilter.tsx
│   │   │   ├── hooks/
│   │   │   ├── api/
│   │   │   └── index.ts
│   │   │
│   │   ├── process-designer/          # 8. 비즈니스 프로세스 디자이너
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
│   │   │   ├── stores/
│   │   │   │   └── processDesignerStore.ts
│   │   │   ├── types/
│   │   │   │   ├── canvasItem.types.ts
│   │   │   │   ├── connection.types.ts
│   │   │   │   └── board.types.ts
│   │   │   └── index.ts
│   │   │
│   │   └── datasource-manager/      # + 데이터소스 관리
│   │       ├── components/
│   │       │   ├── DatasourceList.tsx
│   │       │   ├── ConnectionForm.tsx
│   │       │   ├── SchemaExplorer.tsx
│   │       │   ├── SyncProgress.tsx
│   │       │   └── MetadataTree.tsx
│   │       ├── hooks/
│   │       ├── api/
│   │       └── index.ts
│   │
│   ├── pages/                       # 라우트 페이지 (React.lazy)
│   │   ├── dashboard/
│   │   │   └── CaseDashboardPage.tsx
│   │   ├── cases/
│   │   │   ├── CaseListPage.tsx
│   │   │   └── CaseDetailPage.tsx
│   │   ├── documents/
│   │   │   ├── DocumentListPage.tsx
│   │   │   ├── DocumentEditorPage.tsx
│   │   │   └── DocumentReviewPage.tsx
│   │   ├── analysis/
│   │   │   ├── WhatIfPage.tsx
│   │   │   ├── OlapPivotPage.tsx
│   │   │   └── Nl2SqlPage.tsx
│   │   ├── data/
│   │   │   ├── OntologyPage.tsx
│   │   │   └── DatasourcePage.tsx
│   │   ├── process-designer/
│   │   │   ├── ProcessDesignerListPage.tsx
│   │   │   └── ProcessDesignerPage.tsx
│   │   ├── watch/
│   │   │   └── WatchDashboardPage.tsx
│   │   ├── settings/
│   │   │   └── SettingsPage.tsx
│   │   ├── auth/
│   │   │   ├── LoginPage.tsx
│   │   │   └── CallbackPage.tsx
│   │   └── errors/
│   │       ├── NotFoundPage.tsx
│   │       └── ErrorPage.tsx
│   │
│   ├── shared/                      # 공유 컴포넌트/유틸
│   │   ├── ui/                      # Shadcn/ui 컴포넌트
│   │   │   ├── button.tsx
│   │   │   ├── card.tsx
│   │   │   ├── dialog.tsx
│   │   │   ├── dropdown-menu.tsx
│   │   │   ├── input.tsx
│   │   │   ├── select.tsx
│   │   │   ├── sheet.tsx
│   │   │   ├── skeleton.tsx
│   │   │   ├── table.tsx
│   │   │   ├── tabs.tsx
│   │   │   ├── toast.tsx
│   │   │   └── tooltip.tsx
│   │   ├── components/              # 커스텀 공유 컴포넌트
│   │   │   ├── DataTable/
│   │   │   ├── Chart/
│   │   │   ├── StatusBadge.tsx
│   │   │   ├── EmptyState.tsx
│   │   │   ├── LoadingSkeleton.tsx
│   │   │   ├── ErrorFallback.tsx
│   │   │   ├── ConfirmDialog.tsx
│   │   │   ├── SearchInput.tsx
│   │   │   ├── DateRangePicker.tsx
│   │   │   └── Breadcrumb.tsx
│   │   ├── hooks/                   # 공유 훅
│   │   │   ├── useDebounce.ts
│   │   │   ├── useLocalStorage.ts
│   │   │   ├── useMediaQuery.ts
│   │   │   └── useKeyboardShortcut.ts
│   │   └── utils/                   # 공유 유틸리티
│   │       ├── cn.ts                # clsx + twMerge
│   │       ├── format.ts            # 날짜, 숫자, 통화 포맷
│   │       ├── validators.ts        # Zod 스키마
│   │       └── constants.ts         # 상수
│   │
│   ├── layouts/                     # 레이아웃 컴포넌트
│   │   ├── RootLayout.tsx           # 최상위 레이아웃
│   │   ├── DashboardLayout.tsx      # 사이드바 포함 레이아웃
│   │   ├── Sidebar/
│   │   │   ├── Sidebar.tsx
│   │   │   ├── SidebarNav.tsx
│   │   │   └── SidebarItem.tsx
│   │   ├── Header/
│   │   │   ├── Header.tsx
│   │   │   ├── UserMenu.tsx
│   │   │   └── NotificationBell.tsx
│   │   └── AuthLayout.tsx           # 인증 페이지 레이아웃
│   │
│   ├── stores/                      # 전역 Zustand 스토어
│   │   ├── authStore.ts
│   │   ├── uiStore.ts
│   │   └── themeStore.ts
│   │
│   ├── lib/                         # 라이브러리 설정/래퍼
│   │   ├── api/
│   │   │   ├── createApiClient.ts
│   │   │   ├── clients.ts           # 5개 서비스 인스턴스
│   │   │   ├── errors.ts            # AppError
│   │   │   ├── wsManager.ts         # WebSocket
│   │   │   └── sseManager.ts        # SSE
│   │   └── i18n/
│   │       ├── i18n.ts              # 설정
│   │       ├── ko.json              # 한국어
│   │       └── en.json              # 영어
│   │
│   ├── styles/                      # 글로벌 스타일
│   │   ├── globals.css              # Tailwind directives + CSS vars
│   │   └── themes/
│   │       ├── light.css
│   │       └── dark.css
│   │
│   ├── types/                       # 공유 TypeScript 타입
│   │   ├── api.types.ts             # ApiResponse, PaginationMeta
│   │   ├── auth.types.ts            # User, Role, Permission
│   │   └── common.types.ts          # 공용 타입
│   │
│   ├── main.tsx                     # 진입점
│   └── vite-env.d.ts                # Vite 타입 선언
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
| Shadcn/ui 기본 컴포넌트 | `shared/ui/` | `npx shadcn-ui add`로 자동 생성 |
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

- `shared/ui/`와 `shared/components/` 분리
  - 근거: Shadcn/ui 자동 생성 파일과 커스텀 확장을 구분
  - 규칙: `shared/ui/`는 절대 직접 수정하지 않음 (Shadcn CLI로만 관리)

---

## 변경 이력

| 날짜 | 버전 | 작성자 | 내용 |
|------|------|--------|------|
| 2026-02-19 | 1.0 | Axiom Team | 초기 작성 |
| 2026-02-20 | 1.1 | Axiom Team | process-designer feature 모듈 및 페이지 추가 |
