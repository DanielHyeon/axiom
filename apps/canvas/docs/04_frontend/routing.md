# React Router v6 라우트 정의

<!-- affects: frontend -->
<!-- requires-update: 07_security/auth-flow.md -->

## 이 문서가 답하는 질문

- Canvas의 라우트 구조는 어떻게 되어 있는가?
- 인증이 필요한 라우트와 공개 라우트는 어떻게 구분되는가?
- 코드 분할(lazy loading)은 어떤 단위로 이루어지는가?
- K-AIR의 Vue Router 구조에서 무엇이 달라지는가?

---

## 1. 전체 라우트 맵

현재 구현: **Data Router** — `createBrowserRouter` in `src/lib/routes/routeConfig.tsx`, `App.tsx`에서 `RouterProvider`로 주입. 최상위 `RootLayout` → 인증 구간 `ProtectedRoute` → 대시보드 `MainLayout` (사이드바·헤더). (Phase G 완료)

```
/                                    → 리다이렉트 → /dashboard
│
├── /login                           (RootLayout, 사이드바 없음) → LoginPage
├── /auth/callback                   → CallbackPage (OAuth 콜백)
│
├── /dashboard                       (MainLayout - 사이드바 있음)
│   └── index                        → CaseDashboardPage          [Core API]
│
├── /cases                           (MainLayout)
│   ├── index                        → CaseListPage               [Core API]
│   └── /:caseId
│       ├── index                    → CaseDetailPage              [Core API]
│       ├── /documents
│       │   ├── index                → CaseDocumentsListPage      [Core API]
│       │   ├── /:docId              → CaseDocumentEditorPage     [Core API]
│       │   └── /:docId/review       → DocumentReviewPage         [Core API]
│       └── /scenarios               → WhatIfPage                 [Vision API]
│
├── /analysis                        (MainLayout)
│   ├── /olap                        → OlapPivotPage              [Vision API]
│   ├── /nl2sql                      → Nl2SqlPage                 [Oracle API]
│   └── /insight                     → InsightPage                [Weaver API]
│
├── /data                            (MainLayout)
│   ├── /ontology                    → OntologyBrowser            [Synapse API]
│   └── /datasources                 → DatasourcePage             [Weaver API]
│
├── /process-designer                (MainLayout)
│   ├── index                        → ProcessDesignerListPage     [Synapse API]
│   └── /:boardId                    → ProcessDesignerPage         [Synapse API + Yjs WS]
│
├── /watch                           (MainLayout)
│   └── index                        → WatchDashboardPage         [Core SSE]
│
├── /settings                        (MainLayout)
│   ├── index                        → 리다이렉트 → /settings/system
│   ├── /system                      → SettingsSystemPage
│   ├── /logs                        → SettingsLogsPage
│   ├── /users                       → SettingsUsersPage
│   └── /config                      → SettingsConfigPage
│
└── /*                               → NotFoundPage (404)
```

---

## 2. 라우트 설정 코드

구현 위치: **`src/lib/routes/routeConfig.tsx`** (라우트 정의), **`src/App.tsx`** (`RouterProvider router={router}`). `createBrowserRouter` 사용, 페이지 단위 `React.lazy` + `Suspense` 조합.

- **RootLayout**: 최상위, `<Outlet />`만 렌더. Auth/Protected 자식 분기.
- **ProtectedRoute**: 인증 검사 후 자식 렌더 또는 로그인 리다이렉트.
- **MainLayout**: 사이드바 + 헤더 + `<Outlet />` (페이지 영역에 PageErrorBoundary 적용).

```typescript
// src/App.tsx (요지)
<GlobalErrorBoundary>
  <RouterProvider router={router} />
</GlobalErrorBoundary>

// src/lib/routes/routeConfig.tsx (요지)
export const router = createBrowserRouter([
  { path: '/', element: <RootLayout />,
    children: [
      { path: 'auth/login', element: <SuspensePage><LoginPage /></SuspensePage> },
      { path: 'auth/callback', element: <SuspensePage><CallbackPage /></SuspensePage> },
      { element: <ProtectedRoute />,
        children: [
          { element: <MainLayout />,
            children: [
              { index: true, element: <Navigate to={ROUTES.DASHBOARD} replace /> },
              { path: 'dashboard', element: <SuspensePage><CaseDashboardPage /></SuspensePage> },
              { path: 'cases', children: [...] },
              { path: 'analysis/olap', ... }, { path: 'analysis/nl2sql', ... }, { path: 'analysis/insight', ... },
              { path: 'data/ontology', ... }, { path: 'data/datasources', ... },
              { path: 'process-designer', children: [...] },
              { path: 'watch', ... },
              { path: 'settings', element: <SuspensePage><SettingsPage /></SuspensePage>,
                children: [
                  { index: true, element: <Navigate to={ROUTES.SETTINGS_SYSTEM} replace /> },
                  { path: 'system', ... }, { path: 'logs', ... }, { path: 'users', ... }, { path: 'config', ... }
                ]
              },
              { path: '*', element: <NotFoundPage /> },
            ],
          },
        ],
      },
    ],
  },
]);
```

페이지 컴포넌트는 `React.lazy()`로 로드하며, `SuspensePage`(Suspense + fallback)로 감쌌다. 라우트 상수는 `lib/routes/routes.ts`의 `ROUTES` 사용.

---

## 3. K-AIR Vue Router -> Canvas React Router 전환

### 3.1 라우트 매핑

| K-AIR 라우트 | K-AIR 컴포넌트 | Canvas 라우트 | Canvas 페이지 |
|-------------|---------------|--------------|--------------|
| `/auth/login` | Login.vue | `/auth/login` | LoginPage |
| `/tenant/:id` | TenantView.vue | (삭제) | X-Tenant-Id 헤더로 대체 |
| `/dashboard` | Dashboard.vue | `/dashboard` | CaseDashboardPage |
| `/analytics` | Analytics.vue | `/analysis/*` | OlapPivotPage, Nl2SqlPage |
| `/designer` | Designer.vue | `/process-designer` | ProcessDesignerListPage, ProcessDesignerPage |
| `/chats` | Chats.vue | `/analysis/nl2sql` | Nl2SqlPage |
| `/admin/*` | Admin*.vue | `/settings` | SettingsPage |

### 3.2 전환 패턴 차이

```
// === K-AIR (Vue Router 4) ===
const routes = [
  {
    path: '/dashboard',
    component: () => import('./views/Dashboard.vue'),
    meta: { requiresAuth: true, layout: 'default' }
  }
];

// Navigation Guard
router.beforeEach((to, from, next) => {
  if (to.meta.requiresAuth && !isAuthenticated()) {
    next('/auth/login');
  } else {
    next();
  }
});

// === Canvas (React Router v6) ===
// 1. 라우트 중첩으로 레이아웃 자동 적용 (RootLayout → MainLayout)
// 2. ProtectedRoute가 navigation guard 대체
// 3. lazy() + Suspense로 코드 분할 (동일 패턴)
```

---

## 4. 사이드바 네비게이션 구조

```
┌───────────────────────────┐
│  Axiom Canvas              │
│                            │
│  ┌──────────────────────┐ │
│  │ 📊 대시보드           │ │  → /dashboard
│  ├──────────────────────┤ │
│  │ 📁 케이스             │ │  → /cases
│  ├──────────────────────┤ │
│  │ 📈 분석               │ │
│  │   ├ OLAP 피벗         │ │  → /analysis/olap
│  │   ├ 자연어 쿼리       │ │  → /analysis/nl2sql
│  │   └ Insight          │ │  → /analysis/insight
│  ├──────────────────────┤ │
│  │ 🔗 데이터             │ │
│  │   ├ 온톨로지          │ │  → /data/ontology
│  │   └ 데이터소스        │ │  → /data/datasources
│  ├──────────────────────┤ │
│  │ 🔄 프로세스            │ │  → /process-designer
│  ├──────────────────────┤ │
│  │ 🔔 Watch              │ │  → /watch
│  ├──────────────────────┤ │
│  │ ⚙ 설정               │ │  → /settings
│  └──────────────────────┘ │
│                            │
│  ┌──────────────────────┐ │
│  │ 사용자 메뉴           │ │
│  │ 프로필 | 로그아웃     │ │
│  └──────────────────────┘ │
└───────────────────────────┘
```

---

## 5. 라우트 파라미터 타입 안전성

### 5.1 파라미터 타입 정의

```typescript
// lib/routes/params.ts

import { z } from 'zod';
import { useParams } from 'react-router-dom';

/** UUID v4 형식 검증 */
const uuidSchema = z.string().uuid();

/** 타입 안전한 라우트 파라미터 훅 */
export function useCaseParams() {
  const { caseId } = useParams<{ caseId: string }>();
  return { caseId: uuidSchema.parse(caseId) };
}

export function useDocumentParams() {
  const { caseId, docId } = useParams<{ caseId: string; docId: string }>();
  return {
    caseId: uuidSchema.parse(caseId),
    docId: uuidSchema.parse(docId),
  };
}

export function useBoardParams() {
  const { boardId } = useParams<{ boardId: string }>();
  return { boardId: uuidSchema.parse(boardId) };
}
```

### 5.2 파라미터 → 엔드포인트 매핑

| 파라미터 | 타입 | 사용 라우트 | API 경로 |
|----------|------|------------|---------|
| `:caseId` | UUID v4 | `/cases/:caseId/*` | `/api/v1/cases/{caseId}/*` |
| `:docId` | UUID v4 | `/cases/:caseId/documents/:docId` | `/api/v1/cases/{caseId}/documents/{docId}` |
| `:boardId` | UUID v4 | `/process-designer/:boardId` | Yjs `board:{boardId}` + Synapse API |

> **규칙**: Zod 파싱에 실패하면 ErrorBoundary가 잡고 404 페이지를 표시한다. 페이지 컴포넌트에서 `useParams` 직접 사용 대신 타입 안전한 래퍼 훅을 사용한다.

---

## 6. 라우트 상수 관리

```typescript
// lib/routes/routes.ts

export const ROUTES = {
  HOME: '/',
  AUTH: {
    LOGIN: '/auth/login',
    CALLBACK: '/auth/callback',
  },
  DASHBOARD: '/dashboard',
  CASES: {
    LIST: '/cases',
    DETAIL: (caseId: string) => `/cases/${caseId}`,
    DOCUMENTS: (caseId: string) => `/cases/${caseId}/documents`,
    DOCUMENT: (caseId: string, docId: string) => `/cases/${caseId}/documents/${docId}`,
    DOCUMENT_REVIEW: (caseId: string, docId: string) => `/cases/${caseId}/documents/${docId}/review`,
    SCENARIOS: (caseId: string) => `/cases/${caseId}/scenarios`,
  },
  ANALYSIS: {
    OLAP: '/analysis/olap',
    NL2SQL: '/analysis/nl2sql',
    INSIGHT: '/analysis/insight',
  },
  DATA: {
    ONTOLOGY: '/data/ontology',
    DATASOURCES: '/data/datasources',
  },
  PROCESS_DESIGNER: {
    LIST: '/process-designer',
    BOARD: (boardId: string) => `/process-designer/${boardId}`,
  },
  WATCH: '/watch',
  SETTINGS: '/settings',
  SETTINGS_SYSTEM: '/settings/system',
  SETTINGS_LOGS: '/settings/logs',
  SETTINGS_USERS: '/settings/users',
  SETTINGS_CONFIG: '/settings/config',
} as const;
```

---

## 결정 사항 (Decisions)

- 라우트별 코드 분할 (React.lazy per page)
  - 근거: 초기 번들 최소화, 사용하지 않는 기능 로딩 방지
  - K-AIR도 동적 import 사용했으나 일부 컴포넌트는 정적 import

- 케이스 중첩 라우트 (`/cases/:caseId/documents/:docId`)
  - 근거: 문서는 항상 케이스 컨텍스트에서 접근, Breadcrumb 자동 생성 가능
  - K-AIR는 플랫 라우트 (`/documents/:docId`) 사용

- 라우트 파라미터는 Zod UUID 검증을 거쳐 타입 안전하게 사용한다
  - 근거: 잘못된 URL 파라미터로 인한 API 400 에러 방지, 타입 추론 자동화

## 금지됨 (Forbidden)

- 라우트 컴포넌트(pages)에 비즈니스 로직 직접 작성 (Feature 컴포넌트에 위임)
- 하드코딩된 라우트 경로 사용 (상수로 관리: `ROUTES.CASES.DETAIL(id)`)
- `useParams` 직접 사용 (타입 안전한 래퍼 훅 사용: `useCaseParams()`, `useDocumentParams()` 등)

## 필수 (Required)

- 모든 인증 필요 라우트는 `ProtectedRoute` 내부에 배치
- 모든 페이지는 `React.lazy()`로 동적 import
- URL 파라미터 변경 시 문서 업데이트 필수

---

## 관련 문서

- [04_frontend/admin-dashboard.md](./admin-dashboard.md) (/settings 하위 관리자 라우트: /system, /logs, /users, /config)

---

## 변경 이력

| 날짜 | 버전 | 작성자 | 내용 |
|------|------|--------|------|
| 2026-02-19 | 1.0 | Axiom Team | 초기 작성 |
| 2026-02-20 | 1.1 | Axiom Team | process-designer 라우트 추가 |
| 2026-02-20 | 1.2 | Axiom Team | 라우트 파라미터 타입 안전성(§5), 라우트 상수 관리(§6) 추가 |
| 2026-02-22 | 1.3 | Axiom Team | 현재 구현 반영: RootLayout/MainLayout/ProtectedRoute, BrowserRouter, 설정 하위 /system·/logs·/users·/config, 페이지명(CaseDocumentsListPage 등) |
| 2026-02-26 | 1.4 | Axiom Team | /analysis/insight 라우트 추가 (InsightPage, ROUTES.ANALYSIS.INSIGHT) |
