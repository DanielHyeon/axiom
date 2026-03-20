# Zustand 스토어 스키마 전체

<!-- affects: frontend -->
<!-- requires-update: 01_architecture/state-management.md -->

## 이 문서가 답하는 질문

- Canvas의 모든 Zustand 스토어는 어떤 형태인가?
- 각 스토어의 필드는 어떤 타입이며, 초기값은 무엇인가?
- 스토어 간 의존 관계는 무엇인가?
- K-AIR Pinia 스토어에서 무엇이 전환되었는가?

---

## 1. 스토어 전체 맵

```
┌──────────────────────────────────────────────────────────────┐
│  전역 스토어 (stores/)                                        │
│                                                               │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────────┐│
│  │  authStore     │  │  uiStore      │  │  themeStore       ││
│  │  (인증 상태)   │  │  (UI 상태)    │  │  (테마 상태)      ││
│  │  persist: ○    │  │  persist: ○   │  │  persist: ●       ││
│  └───────────────┘  └───────────────┘  └───────────────────┘│
│                                                               │
│  Feature 스토어 (features/*/stores/)                          │
│                                                               │
│  ┌───────────────────┐  ┌─────────────────────────────────┐ │
│  │  caseFilterStore   │  │  pivotConfigStore               │ │
│  │  (케이스 필터)     │  │  (OLAP 피벗 설정)               │ │
│  │  persist: ○        │  │  persist: ○                     │ │
│  └───────────────────┘  └─────────────────────────────────┘ │
│                                                               │
│  ● = localStorage에 영속  ○ = 메모리만 (새로고침 시 초기화)  │
└──────────────────────────────────────────────────────────────┘
```

---

## 2. 전역 스토어 상세

### 2.1 authStore

```typescript
// stores/authStore.ts

interface User {
  id: string;
  email: string;
  name: string;
  role: 'admin' | 'manager' | 'attorney' | 'analyst' | 'engineer' | 'staff' | 'viewer';
  tenantId: string;
  avatar: string | null;
  permissions: string[];
  preferences: {
    language: 'ko' | 'en';
    pageSize: number;
    notificationsEnabled: boolean;
  };
}

interface AuthStore {
  // === 상태 ===
  user: User | null;                    // 초기값: null
  accessToken: string | null;           // 초기값: null
  refreshToken: string | null;          // 초기값: null
  isAuthenticated: boolean;             // 파생: user !== null
  isLoading: boolean;                   // 초기값: true (초기 인증 확인 중)

  // === 액션 ===
  login: (credentials: { email: string; password: string }) => Promise<void>;
  loginWithOAuth: (provider: 'google' | 'microsoft') => Promise<void>;
  logout: () => void;
  refreshAccessToken: () => Promise<string>;
  updateUser: (updates: Partial<User>) => void;
  setLoading: (loading: boolean) => void;
}

// persist 설정:
// - accessToken, refreshToken: sessionStorage (탭 종료 시 소멸)
// - user: 메모리만 (API로 재조회)
```

### 2.2 uiStore

```typescript
// stores/uiStore.ts

interface Notification {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  title: string;
  message?: string;
  duration?: number;        // ms, 기본 5000
  action?: {
    label: string;
    onClick: () => void;
  };
  actionUrl?: string;       // Watch 알림의 네비게이션 URL (예: /cases/uuid/meetings)
}

interface UiStore {
  // === 상태 ===
  sidebarOpen: boolean;                 // 초기값: true
  sidebarCollapsed: boolean;            // 초기값: false
  commandPaletteOpen: boolean;          // 초기값: false
  globalSearchQuery: string;            // 초기값: ''
  unreadAlertCount: number;             // 초기값: 0
  notificationPopoverOpen: boolean;     // 초기값: false (헤더 알림 벨 Popover 상태)
  isOffline: boolean;                   // 초기값: false

  // === 액션 ===
  toggleSidebar: () => void;
  collapseSidebar: () => void;
  expandSidebar: () => void;
  openCommandPalette: () => void;
  closeCommandPalette: () => void;
  setGlobalSearch: (query: string) => void;
  setUnreadAlertCount: (count: number) => void;
  incrementUnreadAlerts: () => void;
  toggleNotificationPopover: () => void;
  closeNotificationPopover: () => void;
  setOffline: (offline: boolean) => void;
}
```

### 2.3 themeStore

```typescript
// stores/themeStore.ts (persist: localStorage)

type ThemeMode = 'light' | 'dark' | 'system';

interface ThemeStore {
  // === 상태 ===
  mode: ThemeMode;                      // 초기값: 'system'
  resolved: 'light' | 'dark';          // 초기값: 시스템 감지 결과
  accentColor: string;                  // 초기값: 'blue'

  // === 액션 ===
  setMode: (mode: ThemeMode) => void;
  setAccentColor: (color: string) => void;
}

// persist 설정:
// - mode, accentColor: localStorage ('axiom-theme')
```

---

## 3. Feature 스토어 상세

### 3.1 caseFilterStore

```typescript
// features/case-dashboard/stores/caseFilterStore.ts

interface CaseFilterStore {
  // === 상태 ===
  status: CaseStatus | 'all';          // 초기값: 'all'
  type: 'analysis' | 'optimization' | 'all';  // 초기값: 'all'
  dateFrom: string | null;             // 초기값: null
  dateTo: string | null;               // 초기값: null
  search: string;                      // 초기값: ''
  page: number;                        // 초기값: 1
  pageSize: number;                    // 초기값: 20
  sort: string;                        // 초기값: 'createdAt'
  order: 'asc' | 'desc';              // 초기값: 'desc'

  // === 액션 ===
  setStatus: (status: CaseStatus | 'all') => void;
  setType: (type: string) => void;
  setDateRange: (from: string | null, to: string | null) => void;
  setSearch: (search: string) => void;
  setPage: (page: number) => void;
  setPageSize: (size: number) => void;
  setSort: (sort: string, order: 'asc' | 'desc') => void;
  resetFilters: () => void;
}
```

### 3.2 pivotConfigStore

```typescript
// features/olap-pivot/stores/pivotConfigStore.ts
// K-AIR cubeStore.pivotConfig 대응

interface Dimension {
  id: string;
  name: string;
  type: 'time' | 'category' | 'hierarchy';
  levels?: string[];
}

interface Measure {
  id: string;
  name: string;
  aggregation: 'sum' | 'avg' | 'count' | 'min' | 'max';
  format: 'number' | 'currency' | 'percent';
}

interface OlapFilter {
  dimensionId: string;
  operator: 'eq' | 'in' | 'between' | 'gt' | 'lt';
  value: unknown;
}

interface DrilldownStep {
  dimensionId: string;
  value: string;
  level: number;
}

interface PivotConfigStore {
  // === 상태 ===
  cubeId: string | null;               // 초기값: null
  rows: Dimension[];                   // 초기값: []
  columns: Dimension[];                // 초기값: []
  measures: Measure[];                 // 초기값: []
  filters: OlapFilter[];              // 초기값: []
  drilldownPath: DrilldownStep[];     // 초기값: []

  // === 액션 ===
  setCube: (cubeId: string) => void;
  addToRows: (dim: Dimension) => void;
  addToColumns: (dim: Dimension) => void;
  removeFromRows: (dimId: string) => void;
  removeFromColumns: (dimId: string) => void;
  addMeasure: (measure: Measure) => void;
  removeMeasure: (measureId: string) => void;
  addFilter: (filter: OlapFilter) => void;
  removeFilter: (dimId: string) => void;
  swapRowsAndColumns: () => void;
  drilldown: (step: DrilldownStep) => void;
  drillup: () => void;                // drilldownPath.pop()
  resetConfig: () => void;
}
```

---

## 4. K-AIR Pinia -> Zustand 매핑

| K-AIR Pinia Store | Canvas Zustand Store | 전환 노트 |
|-------------------|---------------------|-----------|
| `appStore` (앱 전역) | `uiStore` | 서버 데이터 제거, UI만 남김 |
| `authStore` (인증) | `authStore` | Keycloak -> JWT 기반 |
| `useDatasourcesStore` | TanStack Query `useDatasources()` | 서버 상태는 Query로 이동 |
| `useQueryStore` | TanStack Query `useNl2sql()` | 서버 상태 분리 |
| `cubeStore` | `pivotConfigStore` | pivotConfig 부분만 Zustand, 쿼리 결과는 Query |

---

## 결정 사항 (Decisions)

- 전역 스토어는 3개로 제한 (auth, ui, theme)
  - 근거: 전역 상태 최소화, Feature 스토어로 분산
  - 재평가: 전역 스토어 4개 이상 필요 시 구조 재검토

- authStore의 토큰은 sessionStorage (localStorage 아님)
  - 근거: 탭 종료 시 토큰 소멸 -> 보안 강화

---

## 변경 이력

| 날짜 | 버전 | 작성자 | 내용 |
|------|------|--------|------|
| 2026-02-19 | 1.0 | Axiom Team | 초기 작성 |
