# Phase 4: Yjs 실시간 협업

> 예상 기간: 4-5일
> 선행 조건: Phase 1 완료 (canvasDataStore 인터페이스 확정)
> 설계 문서 섹션: §6 Yjs 실시간 협업, §결정 사항

---

## 목표

1. Yjs Y.Doc으로 캔버스 데이터 SSOT 전환 (설계 위반 VIOLATION-1 해소)
2. WebSocket Provider 연결 (y-websocket)
3. Awareness 기반 커서 공유 + CollaboratorCursors 렌더링
4. UndoManager 기반 Undo/Redo
5. 오프라인 지원 (y-indexeddb)

---

## Step 4.1: 의존성 설치

```bash
npm install yjs y-websocket y-indexeddb
npm install -D @types/yjs  # 필요 시
```

### 통과 기준

| # | 기준 | 검증 |
|:-:|------|------|
| 4.1.1 | `yjs`, `y-websocket`, `y-indexeddb` 설치 확인 | `package.json` |
| 4.1.2 | 빌드 에러 없음 | `npm run build` |

---

## Step 4.2: Yjs 헬퍼 유틸리티

**파일**: `features/process-designer/utils/yjs-helpers.ts`

### 작업 내용

K-AIR `store.ts`의 `toYMap()`, `toYArray()` 패턴을 TypeScript로 이식.

```typescript
import * as Y from 'yjs';

/**
 * JS 객체를 Y.Map으로 변환. Yjs CRDT 동기화에 필요.
 * K-AIR eventstorming-tool store.ts의 toYMap() 이식.
 */
export function toYMap(obj: Record<string, unknown>): Y.Map<unknown> { ... }

/**
 * JS 배열을 Y.Array로 변환.
 */
export function toYArray(arr: unknown[]): Y.Array<unknown> { ... }

/**
 * Y.Map에서 특정 키만 업데이트 (전체 교체 대신 diff 적용).
 */
export function updateYMap(yMap: Y.Map<unknown>, updates: Record<string, unknown>): void { ... }
```

### 통과 기준

| # | 기준 | 검증 |
|:-:|------|------|
| 4.2.1 | `toYMap({ id: '1', label: 'test', nested: { a: 1 } })` 정상 변환 | 단위 테스트 |
| 4.2.2 | `toYArray([1, 'a', { x: 1 }])` 정상 변환 | 단위 테스트 |
| 4.2.3 | `updateYMap` diff 적용 정상 | 단위 테스트 |

---

## Step 4.3: useYjsCollaboration Hook

**파일**: `features/process-designer/hooks/useYjsCollaboration.ts`

### 작업 내용

K-AIR `store.ts`의 `loadBoard()` 패턴을 React hook으로 재구현한다.
기존 `features/process-designer/collaborationStub.ts`를 대체한다.

```typescript
interface UseYjsCollaborationOptions {
  boardId: string | undefined;
  userId: string;
  userName: string;
}

interface UseYjsCollaborationReturn {
  // 데이터
  items: CanvasItem[];
  connections: Connection[];

  // CRDT 조작
  addItem: (item: Omit<CanvasItem, 'id'>) => void;
  updateItem: (id: string, updates: Partial<CanvasItem>) => void;
  updateItemPosition: (id: string, x: number, y: number) => void;
  deleteItems: (ids: string[]) => void;
  addConnection: (conn: Omit<Connection, 'id'>) => void;
  deleteConnections: (ids: string[]) => void;

  // Undo/Redo
  undo: () => void;
  redo: () => void;
  canUndo: boolean;
  canRedo: boolean;

  // 협업
  collaborators: Collaborator[];
  connected: boolean;

  // 상태
  synced: boolean;
  error: string | null;
}
```

**Y.Doc 구조 (설계 §6.1):**

```typescript
const ydoc = new Y.Doc();

// 캔버스 아이템 (Y.Array<Y.Map>)
const yItems = ydoc.getArray<Y.Map<unknown>>('items');

// 연결선 (Y.Array<Y.Map>)
const yConnections = ydoc.getArray<Y.Map<unknown>>('connections');

// 노드 위치 분리 (설계: "드래그 중 빈번한 업데이트가 속성 변경과 충돌하지 않도록 격리")
const yPositions = ydoc.getMap<{ x: number; y: number }>('positions');
```

**WebSocket Provider:**

```typescript
const provider = new WebsocketProvider(
  WS_URL,           // 환경 변수에서 가져옴
  `board:${boardId}`,  // 방 이름 = 보드 ID
  ydoc,
);

provider.on('synced', (synced: boolean) => { ... });
provider.on('status', ({ status }: { status: string }) => { ... });
```

**Awareness (커서 공유, 설계 §6.2):**

```typescript
provider.awareness.setLocalState({
  userId,
  name: userName,
  color: assignedColor,
  cursor: null as { x: number; y: number } | null,
  selectedItemIds: [] as string[],
});

// 마우스 이동 시 커서 위치 업데이트
const updateCursor = (x: number, y: number) => {
  provider.awareness.setLocalStateField('cursor', { x, y });
};

// 다른 사용자 상태 수신
provider.awareness.on('change', () => {
  const states = Array.from(provider.awareness.getStates().entries());
  setCollaborators(states.filter(([id]) => id !== ydoc.clientID).map(...));
});
```

**React 연동 (reactive mirror, K-AIR 패턴):**

```typescript
// Y.Array 변경 감지 → React state 업데이트
useEffect(() => {
  const observer = () => {
    setItems(yItems.toJSON() as CanvasItem[]);
    setConnections(yConnections.toJSON() as Connection[]);
  };

  yItems.observe(observer);
  yConnections.observe(observer);
  yPositions.observe(() => { ... });

  return () => {
    yItems.unobserve(observer);
    yConnections.unobserve(observer);
  };
}, [ydoc]);
```

**UndoManager (설계 §6):**

```typescript
const undoManager = new Y.UndoManager([yItems, yConnections]);
```

### canvasDataStore 교체

Phase 1에서 만든 `canvasDataStore.ts`의 인터페이스를 이 hook이 구현하므로, `ProcessCanvas` 등에서 canvasDataStore 대신 `useYjsCollaboration`의 반환값을 사용하도록 교체한다.

### 통과 기준

| # | 기준 | 검증 |
|:-:|------|------|
| 4.3.1 | boardId 전달 시 Y.Doc 생성 + WS 연결 | DevTools Network WS 확인 |
| 4.3.2 | `addItem()` 호출 시 Y.Array에 추가 → React state 반영 | 브라우저 확인 |
| 4.3.3 | `updateItemPosition()` 호출 시 yPositions 업데이트 | 브라우저 확인 |
| 4.3.4 | `deleteItems()` 호출 시 Y.Array에서 삭제 + 연결선 자동 삭제 | 브라우저 확인 |
| 4.3.5 | Undo/Redo 정상 동작 (Ctrl+Z / Ctrl+Shift+Z) | 노드 추가 → Undo → 사라짐 |
| 4.3.6 | 컴포넌트 unmount 시 cleanup (provider 해제, observer 해제) | Memory leak 없음 |
| 4.3.7 | 기존 `canvasDataStore.ts` 사용처 모두 교체 | `grep` 확인 |
| 4.3.8 | `collaborationStub.ts` 제거 또는 unused 처리 | 코드 리뷰 |

---

## Step 4.4: CollaboratorCursors 컴포넌트

**파일**: `features/process-designer/components/canvas/CollaboratorCursors.tsx`

### 작업 내용

다른 사용자의 커서 위치를 캔버스 위에 표시한다.

```typescript
interface Collaborator {
  clientId: number;
  userId: string;
  name: string;
  color: string;
  cursor: { x: number; y: number } | null;
  selectedItemIds: string[];
}

interface CollaboratorCursorsProps {
  collaborators: Collaborator[];
}
```

각 커서는 react-konva로 렌더링:
- 삼각형 화살표 아이콘 (사용자 색상)
- 이름 태그 (작은 둥근 사각형 + 텍스트)
- 선택 중인 노드에 사용자 색상 테두리 표시

### 통과 기준

| # | 기준 | 검증 |
|:-:|------|------|
| 4.4.1 | 다른 탭/브라우저에서 접속 시 커서 표시 | 2개 탭 테스트 |
| 4.4.2 | 커서에 사용자 이름 태그 표시 | 브라우저 확인 |
| 4.4.3 | 사용자별 고유 색상 적용 | 브라우저 확인 |
| 4.4.4 | 사용자가 선택한 노드에 해당 색상 테두리 표시 | 2개 탭 테스트 |
| 4.4.5 | 사용자 연결 해제 시 커서 사라짐 | 탭 닫기 후 확인 |

---

## Step 4.5: 협업 인디케이터

### 작업 내용

설계 §1 와이어프레임의 "👥 3명 협업 중" 표시를 캔버스 상단에 구현한다.

```tsx
<div className="flex items-center gap-1.5">
  {collaborators.map(c => (
    <div
      key={c.clientId}
      className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold"
      style={{ backgroundColor: c.color }}
      title={c.name}
    >
      {c.name[0]}
    </div>
  ))}
  <span className="text-xs text-neutral-400">
    {collaborators.length + 1}명 협업 중
  </span>
</div>
```

### 연결 상태 배너 (설계 §11.1)

```tsx
{!connected && (
  <div className="bg-amber-900/50 border-b border-amber-700 px-3 py-1.5 text-xs text-amber-300">
    ⚠ 실시간 동기화 연결이 끊어졌습니다. 재연결 중...
  </div>
)}
```

### 통과 기준

| # | 기준 | 검증 |
|:-:|------|------|
| 4.5.1 | 협업 참여자 아바타 표시 | 2개 탭 테스트 |
| 4.5.2 | 참여자 수 텍스트 실시간 업데이트 | 탭 열기/닫기 |
| 4.5.3 | WS 연결 끊김 시 경고 배너 표시 | 네트워크 차단 시뮬레이션 |
| 4.5.4 | 재연결 시 배너 사라짐 | 네트워크 복원 |

---

## Step 4.6: 오프라인 지원 (y-indexeddb)

### 작업 내용

설계 §6.4 — 네트워크 단절 시 로컬 변경 큐잉, 재연결 시 자동 동기화.

```typescript
import { IndexeddbPersistence } from 'y-indexeddb';

// WebSocket Provider와 함께 사용
const persistence = new IndexeddbPersistence(`board:${boardId}`, ydoc);

persistence.on('synced', () => {
  // IndexedDB에서 기존 데이터 로드 완료
});
```

### 통과 기준

| # | 기준 | 검증 |
|:-:|------|------|
| 4.6.1 | 오프라인 상태에서 노드 추가/이동 가능 | DevTools offline 모드 |
| 4.6.2 | 온라인 복구 시 오프라인 변경사항 자동 동기화 | offline → online 후 확인 |
| 4.6.3 | 페이지 새로고침 후 데이터 유지 (IndexedDB) | 새로고침 후 확인 |

---

## Step 4.7: 백엔드 WebSocket 서버 (별도)

> 이 단계는 백엔드 작업이며 프론트엔드 구현 범위 밖이나, 참고를 위해 기술한다.

K-AIR의 `server.js` 패턴:

```javascript
const { WebSocketServer } = require('ws');
const { setupWSConnection } = require('y-websocket/bin/utils');

const wss = new WebSocketServer({ server });
wss.on('connection', setupWSConnection);
```

**옵션:**
- (a) 기존 서비스(Core/Synapse)에 y-websocket 엔드포인트 추가
- (b) 별도 Yjs 서버 프로세스 (가장 단순)
- (c) y-redis 등 영속화 어댑터 사용

### 통과 기준

| # | 기준 | 검증 |
|:-:|------|------|
| 4.7.1 | WS 서버가 `ws://host/yjs` 엔드포인트 제공 | WebSocket 연결 테스트 |
| 4.7.2 | 2개 클라이언트의 변경사항이 양방향 동기화 | 2개 탭 테스트 |

---

## Phase 4 완료 체크리스트

| # | 항목 | 완료 |
|:-:|------|:----:|
| 1 | yjs, y-websocket, y-indexeddb 설치 | [ ] |
| 2 | `yjs-helpers.ts` (toYMap, toYArray, updateYMap) | [ ] |
| 3 | `useYjsCollaboration.ts` — Y.Doc + WS Provider | [ ] |
| 4 | items/connections/positions 3개 Y 컬렉션 | [ ] |
| 5 | Awareness 커서 공유 | [ ] |
| 6 | UndoManager (Ctrl+Z / Ctrl+Shift+Z) | [ ] |
| 7 | `CollaboratorCursors.tsx` 커서 렌더링 | [ ] |
| 8 | 협업 인디케이터 (아바타 + N명 협업 중) | [ ] |
| 9 | WS 연결 끊김 경고 배너 | [ ] |
| 10 | y-indexeddb 오프라인 지원 | [ ] |
| 11 | `canvasDataStore.ts` → Yjs 교체 완료 | [ ] |
| 12 | `collaborationStub.ts` 제거 | [ ] |
| 13 | **VIOLATION-1 해소**: Zustand에 캔버스 데이터 없음 | [ ] |
| 14 | 2개 탭 동시 편집 테스트 통과 | [ ] |
