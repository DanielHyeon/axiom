# 상태 관리 전략

<!-- affects: frontend, api -->
<!-- requires-update: 06_data/state-schema.md, 06_data/cache-strategy.md -->

## 이 문서가 답하는 질문

- Canvas에서 "상태"란 무엇이며, 어떻게 분류되는가?
- 왜 Zustand과 TanStack Query를 함께 사용하는가?
- K-AIR의 Pinia + mitt() 패턴에서 무엇이 달라지는가?
- 어떤 데이터를 어느 저장소에 두어야 하는가?

---

## 1. 상태 분류 체계

### 1.1 4종 상태 분류

```
┌─────────────────────────────────────────────────────────────────┐
│                        Canvas 상태 분류                          │
│                                                                  │
│  ┌─────────────────────┐  ┌─────────────────────────────────┐  │
│  │  서버 상태           │  │  클라이언트 상태                  │  │
│  │  (Server State)     │  │  (Client State)                  │  │
│  │                      │  │                                  │  │
│  │  "진실의 원천이      │  │  "브라우저에만 존재하는          │  │
│  │   서버에 있는 데이터"│  │   일시적 데이터"                 │  │
│  │                      │  │                                  │  │
│  │  -> TanStack Query  │  │  -> Zustand                     │  │
│  │                      │  │                                  │  │
│  │  예:                 │  │  예:                             │  │
│  │  - 케이스 목록       │  │  - 사이드바 열림/닫힘            │  │
│  │  - 문서 내용         │  │  - 선택된 탭                     │  │
│  │  - OLAP 쿼리 결과   │  │  - 모달 표시 여부                │  │
│  │  - 온톨로지 노드     │  │  - 현재 테마 (다크/라이트)      │  │
│  └─────────────────────┘  └─────────────────────────────────┘  │
│                                                                  │
│  ┌─────────────────────┐  ┌─────────────────────────────────┐  │
│  │  URL 상태            │  │  폼 상태                         │  │
│  │  (URL State)        │  │  (Form State)                   │  │
│  │                      │  │                                  │  │
│  │  "북마크/공유 가능한 │  │  "입력 중인 미완성 데이터"       │  │
│  │   네비게이션 상태"   │  │                                  │  │
│  │                      │  │                                  │  │
│  │  -> React Router    │  │  -> React Hook Form             │  │
│  │                      │  │                                  │  │
│  │  예:                 │  │  예:                             │  │
│  │  - 현재 케이스 ID    │  │  - 데이터소스 연결 폼           │  │
│  │  - OLAP 필터 조건   │  │  - 알림 규칙 편집                │  │
│  │  - 검색어            │  │  - 시나리오 매개변수             │  │
│  │  - 페이지 번호       │  │                                  │  │
│  └─────────────────────┘  └─────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 상태 배치 결정 플로우차트

```
데이터가 서버에서 오는가?
├── YES: 다른 탭/기기에서도 동일한 값이어야 하는가?
│   ├── YES ──→ TanStack Query (서버 상태)
│   └── NO  ──→ Zustand (서버에서 왔지만 로컬 변형)
│
└── NO: URL에 반영되어야 하는가? (북마크/공유)
    ├── YES ──→ React Router (URL 파라미터/검색 파라미터)
    └── NO: 폼 입력 중인 데이터인가?
        ├── YES ──→ React Hook Form (폼 상태)
        └── NO  ──→ Zustand (UI 상태) 또는 useState (로컬)
```

---

## 2. Zustand 스토어 설계

### 2.1 스토어 분리 원칙

| 원칙 | 설명 |
|------|------|
| **관심사 분리** | 도메인별로 별도 스토어 (auth, ui, theme은 각각 독립) |
| **최소 범위** | Feature 전용 상태는 Feature store에, 전역 상태만 공유 store에 |
| **불변성** | Immer 미들웨어로 불변 업데이트 보장 |
| **영속성** | 테마, 사이드바 등 사용자 선호는 persist 미들웨어 |
| **셀렉터** | 구독 최적화를 위해 항상 셀렉터 사용 |

### 2.2 전역 스토어 목록

```typescript
// stores/authStore.ts
interface AuthStore {
  // 상태
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;

  // 액션
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => void;
  refreshAccessToken: () => Promise<string>;
  updateUser: (updates: Partial<User>) => void;
}

// stores/uiStore.ts
interface UiStore {
  // 상태
  sidebarOpen: boolean;
  sidebarCollapsed: boolean;
  commandPaletteOpen: boolean;
  activeNotifications: Notification[];

  // 액션
  toggleSidebar: () => void;
  collapseSidebar: () => void;
  openCommandPalette: () => void;
  addNotification: (notification: Notification) => void;
  removeNotification: (id: string) => void;
}

// stores/themeStore.ts (persist)
interface ThemeStore {
  // 상태
  mode: 'light' | 'dark' | 'system';
  accentColor: string;

  // 액션
  setMode: (mode: ThemeMode) => void;
  setAccentColor: (color: string) => void;
}
```

### 2.3 비즈니스 프로세스 디자이너 스토어

```typescript
// features/process-designer/stores/processDesignerStore.ts
// K-AIR eventstorming-tool의 boardStore 대응 (Pinia -> Zustand)
// Yjs CRDT와 연동되는 클라이언트 상태만 관리 (캔버스 데이터 자체는 Yjs Document에 저장)

interface ProcessDesignerStore {
  // 보드 상태
  currentBoard: BoardState | null;

  // 캔버스 인터랙션 상태
  selectedItems: CanvasItem[];
  toolMode: 'select' | 'connect' | CanvasItemType;
  // CanvasItemType: 'businessAction' | 'businessEvent' | 'businessEntity'
  //               | 'businessRule' | 'stakeholder' | 'businessReport'
  //               | 'measure' | 'contextBox'
  //               | 'eventLogBinding' | 'temporalAnnotation'

  // Yjs 협업 상태
  collaborators: CollaboratorInfo[];
  // CollaboratorInfo: { userId, name, color, cursor: {x, y}, selectedItemIds }

  // 프로세스 마이닝 오버레이
  miningOverlayVisible: boolean;
  activeVariantId: string | null;

  // 액션
  setCurrentBoard: (board: BoardState) => void;
  selectItems: (items: CanvasItem[]) => void;
  clearSelection: () => void;
  setToolMode: (mode: ProcessDesignerStore['toolMode']) => void;
  updateCollaborators: (collaborators: CollaboratorInfo[]) => void;
  toggleMiningOverlay: () => void;
  setActiveVariant: (variantId: string | null) => void;
}

// 사용 예시 (셀렉터 필수)
const toolMode = useProcessDesignerStore((s) => s.toolMode);
const selectedItems = useProcessDesignerStore((s) => s.selectedItems);
```

### 2.4 기타 Feature 스토어 예시

```typescript
// features/olap-pivot/stores/pivotConfigStore.ts
// K-AIR cubeStore 대응 (Pinia -> Zustand)
interface PivotConfigStore {
  // 상태 (K-AIR cubeStore.pivotConfig 대응)
  rows: Dimension[];
  columns: Dimension[];
  measures: Measure[];
  filters: Filter[];
  currentCubeId: string | null;

  // 액션
  addToRows: (dim: Dimension) => void;
  addToColumns: (dim: Dimension) => void;
  addMeasure: (measure: Measure) => void;
  addFilter: (filter: Filter) => void;
  removeDimension: (id: string) => void;
  swapRowsAndColumns: () => void;
  resetConfig: () => void;
}
```

### 2.5 K-AIR Pinia -> Zustand 전환 패턴

```
// === K-AIR (Pinia Composition Store) ===
// robo-data-fabric: useDatasourcesStore
export const useDatasourcesStore = defineStore('datasources', () => {
  const datasources = ref<DataSource[]>([]);
  const loading = ref(false);

  async function fetchDatasources() {
    loading.value = true;
    try {
      datasources.value = await datasourcesApi.getAll();
    } finally {
      loading.value = false;
    }
  }

  return { datasources, loading, fetchDatasources };
});

// === Canvas (Zustand + TanStack Query) ===
// 서버 상태는 TanStack Query로 분리
// hooks/useDatasources.ts
export function useDatasources() {
  return useQuery({
    queryKey: ['datasources'],
    queryFn: () => datasourcesApi.getAll(),
  });
  // loading, error, data 자동 관리
}

// 클라이언트 상태만 Zustand
// stores/datasourceUiStore.ts
export const useDatasourceUiStore = create<DatasourceUiStore>((set) => ({
  selectedId: null,
  filterType: 'all',
  setSelectedId: (id) => set({ selectedId: id }),
  setFilterType: (type) => set({ filterType: type }),
}));
```

---

## 3. TanStack Query 전략

### 3.1 쿼리 키 컨벤션

```typescript
// 쿼리 키 팩토리 패턴
export const caseKeys = {
  all:     ['cases'] as const,
  lists:   () => [...caseKeys.all, 'list'] as const,
  list:    (filters: CaseFilters) => [...caseKeys.lists(), filters] as const,
  details: () => [...caseKeys.all, 'detail'] as const,
  detail:  (id: string) => [...caseKeys.details(), id] as const,
};

export const documentKeys = {
  all:     ['documents'] as const,
  lists:   () => [...documentKeys.all, 'list'] as const,
  list:    (caseId: string) => [...documentKeys.lists(), { caseId }] as const,
  detail:  (id: string) => [...documentKeys.all, 'detail', id] as const,
};

// 사용
useQuery({ queryKey: caseKeys.detail(caseId), ... });

// 무효화
queryClient.invalidateQueries({ queryKey: caseKeys.lists() });
```

### 3.2 기본 옵션

```typescript
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,      // 5분 fresh
      gcTime: 30 * 60 * 1000,         // 30분 후 GC
      retry: 3,                        // 3회 재시도
      retryDelay: (attempt) =>         // 지수 백오프
        Math.min(1000 * 2 ** attempt, 30000),
      refetchOnWindowFocus: true,      // 탭 전환 시 재조회
      refetchOnReconnect: true,        // 네트워크 복구 시
    },
    mutations: {
      retry: 1,                        // mutation은 1회만
    },
  },
});
```

### 3.3 기능별 캐싱 전략

| 기능 | staleTime | gcTime | 전략 | 근거 |
|------|-----------|--------|------|------|
| 케이스 목록 | 1분 | 10분 | 짧은 fresh + WS 무효화 | 실시간 상태 변경 |
| 문서 상세 | 5분 | 30분 | 표준 | 편집 중 자주 변경 안됨 |
| OLAP 쿼리 결과 | 10분 | 1시간 | 긴 캐시 | 같은 쿼리 반복 가능 |
| 온톨로지 그래프 | 30분 | 2시간 | 매우 긴 캐시 | 거의 변경 안됨 |
| NL2SQL 히스토리 | 5분 | 30분 | 표준 | 대화 중 갱신 |
| 알림 목록 | 0 (항상 stale) | 5분 | WS 기반 실시간 | WebSocket이 주도 |
| 프로세스 보드 목록 | 5분 | 30분 | 표준 | 목록 자체는 자주 변경 안됨 |
| 프로세스 마이닝 결과 | 10분 | 1시간 | 긴 캐시 | 마이닝 결과는 요청 시에만 갱신 |
| 데이터소스 목록 | 5분 | 30분 | 표준 | 변경 빈도 낮음 |

### 3.4 낙관적 업데이트 패턴

```typescript
// 문서 상태 변경 (HITL 승인)
const approveDocument = useMutation({
  mutationFn: (docId: string) => documentApi.approve(docId),

  // 낙관적: UI 즉시 반영
  onMutate: async (docId) => {
    await queryClient.cancelQueries({ queryKey: documentKeys.detail(docId) });
    const previous = queryClient.getQueryData(documentKeys.detail(docId));

    queryClient.setQueryData(documentKeys.detail(docId), (old: Document) => ({
      ...old,
      status: 'approved',
      approvedAt: new Date().toISOString(),
    }));

    return { previous };
  },

  // 실패 시 롤백
  onError: (_err, docId, context) => {
    queryClient.setQueryData(documentKeys.detail(docId), context?.previous);
    toast.error('승인에 실패했습니다. 다시 시도해 주세요.');
  },

  // 성공/실패 무관하게 서버 데이터로 동기화
  onSettled: (_data, _error, docId) => {
    queryClient.invalidateQueries({ queryKey: documentKeys.detail(docId) });
    queryClient.invalidateQueries({ queryKey: caseKeys.all });
  },
});
```

---

## 4. 상태 동기화 패턴

### 4.1 WebSocket -> TanStack Query 연동

```typescript
// WebSocket 이벤트 수신 시 관련 쿼리 무효화
function useWebSocketSync() {
  const queryClient = useQueryClient();

  useEffect(() => {
    const ws = wsManager.connect();

    ws.on('case:updated', (data: { caseId: string }) => {
      queryClient.invalidateQueries({ queryKey: caseKeys.detail(data.caseId) });
      queryClient.invalidateQueries({ queryKey: caseKeys.lists() });
    });

    ws.on('document:created', (data: { caseId: string }) => {
      queryClient.invalidateQueries({
        queryKey: documentKeys.list(data.caseId)
      });
    });

    ws.on('alert:new', (data: Alert) => {
      // 알림은 직접 캐시에 추가 (서버 재조회 불필요)
      queryClient.setQueryData(['alerts', 'feed'], (old: Alert[]) => {
        return [data, ...(old || [])];
      });
    });

    return () => ws.disconnect();
  }, [queryClient]);
}
```

### 4.2 Yjs CRDT -> 캔버스 상태 동기화 (비즈니스 프로세스 디자이너)

```typescript
// 프로세스 디자이너에서 캔버스 데이터는 Yjs Document에 저장된다.
// Zustand store는 UI 상태(선택, 도구 모드)만 관리한다.
// 이 분리가 중요한 이유: Yjs가 CRDT로 충돌을 자동 해소하므로,
// 캔버스 데이터를 Zustand에 중복 저장하면 동기화 버그가 발생한다.

function useYjsCollaboration(boardId: string) {
  const ydoc = useMemo(() => new Y.Doc(), []);
  const provider = useMemo(
    () => new WebsocketProvider(YJS_WS_URL, `board:${boardId}`, ydoc),
    [boardId, ydoc]
  );

  // Yjs awareness -> Zustand collaborators 동기화
  useEffect(() => {
    const awareness = provider.awareness;

    awareness.on('change', () => {
      const collaborators = Array.from(awareness.getStates().entries())
        .filter(([clientId]) => clientId !== ydoc.clientID)
        .map(([, state]) => state as CollaboratorInfo);

      useProcessDesignerStore.getState().updateCollaborators(collaborators);
    });

    return () => { provider.disconnect(); ydoc.destroy(); };
  }, [provider, ydoc]);

  return { ydoc, provider };
}
```

**상태 저장소 분리 원칙 (프로세스 디자이너)**

| 데이터 | 저장소 | 이유 |
|--------|--------|------|
| 캔버스 노드/연결선 | Yjs Document (Y.Map) | 다중 사용자 CRDT 동기화 필요 |
| 노드 위치 | Yjs Document (Y.Map) | 동시 이동 충돌 해소 |
| 선택된 아이템 | Zustand | 로컬 UI 상태, 사용자별 독립 |
| 도구 모드 | Zustand | 로컬 UI 상태 |
| 협업자 커서 | Yjs Awareness -> Zustand | Awareness에서 수신 후 Zustand로 전달 |
| 보드 메타데이터 | TanStack Query (Core API) | 서버 상태 (이름, 소유자, 권한) |
| 프로세스 마이닝 결과 | TanStack Query (Synapse API) | 서버 상태 (적합도, 병목) |

### 4.3 K-AIR mitt() 이벤트 버스 -> Canvas 대체 패턴

```
// === K-AIR ===
// mitt() 이벤트 버스 (추적 어려움)
emitter.emit('case-updated', { id: '123' });
emitter.on('case-updated', (data) => { ... });

// === Canvas ===
// 패턴 1: TanStack Query invalidation (서버 상태)
queryClient.invalidateQueries({ queryKey: caseKeys.detail('123') });

// 패턴 2: Zustand subscribe (클라이언트 상태)
const unsubscribe = useAuthStore.subscribe(
  (state) => state.isAuthenticated,
  (isAuth) => {
    if (!isAuth) router.navigate('/login');
  }
);

// 패턴 3: React Effect (컴포넌트 로컬)
useEffect(() => {
  if (caseUpdated) { refreshTimeline(); }
}, [caseUpdated]);
```

---

## 결정 사항 (Decisions)

- 서버 상태와 클라이언트 상태를 엄격히 분리
  - 근거: K-AIR에서 Pinia store에 서버 데이터 + UI 상태가 혼재되어 캐시 무효화 복잡
  - 참조: ADR-003, ADR-004

- mitt() 이벤트 버스 제거, 대안 패턴 3종으로 대체
  - 근거: 이벤트 흐름 추적 불가, 디버깅 어려움, 메모리 누수 위험

## 금지됨 (Forbidden)

- 컴포넌트에서 Axios 직접 호출 (반드시 TanStack Query 또는 Zustand action을 통해)
- useEffect 안에서 Zustand store 전체를 구독 (셀렉터 사용 필수)
- TanStack Query 캐시를 전역 상태 대용으로 사용 (서버 데이터만)

## 필수 (Required)

- 모든 서버 API 호출은 TanStack Query의 useQuery 또는 useMutation을 통해야 함
- Zustand store는 셀렉터와 함께 사용: `useAuthStore((s) => s.user)` (전체 store 구독 금지)
- 폼 상태는 React Hook Form으로 관리 (Zustand에 폼 데이터 저장 금지)

---

## 변경 이력

| 날짜 | 버전 | 작성자 | 내용 |
|------|------|--------|------|
| 2026-02-20 | 1.1 | Axiom Team | 비즈니스 프로세스 디자이너 Zustand 스토어 추가, Yjs CRDT 상태 동기화 패턴 추가, 프로세스 보드/마이닝 캐싱 전략 추가 |
| 2026-02-19 | 1.0 | Axiom Team | 초기 작성 |
