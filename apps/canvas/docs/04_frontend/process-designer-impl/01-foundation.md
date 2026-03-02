# Phase 1: Foundation — 타입 시스템 + 스토어 리팩터링 + 11종 노드

> 예상 기간: 3-4일
> 선행 조건: 없음 (첫 페이즈)
> 설계 문서 섹션: §2 노드 타입, §9.1 컴포넌트 구조, Forbidden/Required 규칙

---

## 목표

1. 설계 문서의 11종 노드 타입을 완전한 TypeScript 타입으로 정의
2. Zustand 스토어를 UI 전용으로 리팩터링 (설계 위반 해소 준비)
3. 캔버스에 11종 노드를 모두 렌더링할 수 있도록 구현
4. 컴포넌트를 설계 문서의 구조로 분리

---

## Step 1.1: 타입 시스템 정의

**파일**: `features/process-designer/types/processDesigner.ts`

### 작업 내용

설계 §2.3의 `CanvasItem` 인터페이스와 §3.2의 `Connection` 인터페이스를 구현한다.

```typescript
// === 노드 타입 (8종 기본 + 3종 확장 = 11종) ===
export type CanvasItemType =
  // 8종 비즈니스 노드
  | 'contextBox'
  | 'businessAction'
  | 'businessEvent'
  | 'businessEntity'
  | 'businessRule'
  | 'stakeholder'
  | 'businessReport'
  | 'measure'
  // 3종 확장 노드
  | 'eventLogBinding'
  | 'temporalAnnotation';

// === 연결선 타입 (4종) ===
export type ConnectionType = 'triggers' | 'reacts_to' | 'produces' | 'binds_to';

// === 시간축 속성 ===
export interface TemporalData {
  expectedDuration?: number;   // 분
  sla?: number;                // 분
  actualAvg?: number;          // 분 (프로세스 마이닝 결과, 읽기전용)
  status?: 'ok' | 'warning' | 'violation';
}

// === 측정값 바인딩 ===
export interface MeasureBindingData {
  kpiId?: string;
  formula?: string;
  unit?: string;
}

// === 이벤트 로그 바인딩 ===
export interface EventLogBindingData {
  sourceTable: string;
  timestampColumn: string;
  caseIdColumn: string;
  activityColumn?: string;
  filter?: string;
}

// === 캔버스 아이템 ===
export interface CanvasItem {
  id: string;
  type: CanvasItemType;
  x: number;
  y: number;
  width: number;
  height: number;
  label: string;
  description?: string;
  color: string;
  parentContextBoxId?: string | null;

  temporal?: TemporalData;
  measureBinding?: MeasureBindingData;
  eventLogBinding?: EventLogBindingData;
}

// === 연결선 ===
export interface Connection {
  id: string;
  type: ConnectionType;
  sourceId: string;
  targetId: string;
  label?: string;
  style: ConnectionStyle;
}

export interface ConnectionStyle {
  stroke: string;
  strokeWidth: number;
  dashArray?: string;
  arrowSize: number;
}

// === 도구 모드 ===
export type ToolMode =
  | 'select'
  | 'connect'
  | CanvasItemType;  // 노드 추가 모드 (예: 'businessEvent')
```

### 통과 기준

| # | 기준 | 검증 |
|:-:|------|------|
| 1.1.1 | 11종 `CanvasItemType` 리터럴 타입 정의 | `tsc --noEmit` |
| 1.1.2 | `CanvasItem` 인터페이스에 설계 §2.3의 모든 필드 포함 | 코드 리뷰 |
| 1.1.3 | `Connection` 인터페이스에 설계 §3.2의 모든 필드 포함 | 코드 리뷰 |
| 1.1.4 | `ToolMode` 유니온이 'select', 'connect', 11종 노드 타입 포함 | `tsc --noEmit` |

---

## Step 1.2: 노드 설정 유틸리티

**파일**: `features/process-designer/utils/nodeConfig.ts`

### 작업 내용

설계 §2.1의 색상·단축키 매핑과 K-AIR `colorMap` 패턴을 통합하여 노드 메타데이터 SSOT를 정의한다.

```typescript
import type { CanvasItemType } from '../types/processDesigner';

export interface NodeTypeConfig {
  type: CanvasItemType;
  label: string;           // 영문 라벨
  labelKo: string;         // 한국어 라벨
  color: string;           // 배경 색상
  shortcut: string | null; // 키보드 단축키 (null = 단축키 없음)
  defaultWidth: number;
  defaultHeight: number;
  category: 'basic' | 'extended';
}

export const NODE_CONFIGS: Record<CanvasItemType, NodeTypeConfig> = {
  contextBox:         { type: 'contextBox',         label: 'Domain',       labelKo: '부서/사업부',     color: '#e9ecef', shortcut: 'D', defaultWidth: 400, defaultHeight: 300, category: 'basic' },
  businessAction:     { type: 'businessAction',     label: 'Action',       labelKo: '업무 행위',       color: '#87ceeb', shortcut: 'B', defaultWidth: 160, defaultHeight: 90,  category: 'basic' },
  businessEvent:      { type: 'businessEvent',      label: 'Event',        labelKo: '업무 사건',       color: '#ffb703', shortcut: 'E', defaultWidth: 160, defaultHeight: 90,  category: 'basic' },
  businessEntity:     { type: 'businessEntity',     label: 'Entity',       labelKo: '업무 객체',       color: '#ffff99', shortcut: 'N', defaultWidth: 160, defaultHeight: 90,  category: 'basic' },
  businessRule:       { type: 'businessRule',       label: 'Rule',         labelKo: '업무 규칙',       color: '#ffc0cb', shortcut: 'R', defaultWidth: 160, defaultHeight: 90,  category: 'basic' },
  stakeholder:        { type: 'stakeholder',        label: 'Stakeholder',  labelKo: '이해관계자',      color: '#d0f4de', shortcut: 'S', defaultWidth: 160, defaultHeight: 90,  category: 'basic' },
  businessReport:     { type: 'businessReport',     label: 'Report',       labelKo: '업무 보고서',     color: '#90ee90', shortcut: 'T', defaultWidth: 160, defaultHeight: 90,  category: 'basic' },
  measure:            { type: 'measure',            label: 'Measure',      labelKo: 'KPI/측정값',      color: '#9b59b6', shortcut: 'M', defaultWidth: 160, defaultHeight: 90,  category: 'basic' },
  eventLogBinding:    { type: 'eventLogBinding',    label: 'Log Binding',  labelKo: '로그 바인딩',     color: '#607d8b', shortcut: null, defaultWidth: 140, defaultHeight: 80,  category: 'extended' },
  temporalAnnotation: { type: 'temporalAnnotation', label: 'Temporal',     labelKo: '시간 주석',       color: '#ffffff', shortcut: null, defaultWidth: 140, defaultHeight: 60,  category: 'extended' },
};

// 연결선 설정 (설계 §3.1)
export const CONNECTION_CONFIGS: Record<ConnectionType, { stroke: string; dashArray?: string; label: string }> = {
  triggers:  { stroke: '#3b82f6', label: 'triggers' },
  reacts_to: { stroke: '#ec4899', dashArray: '10,5', label: 'reacts to' },
  produces:  { stroke: '#f97316', label: 'produces' },
  binds_to:  { stroke: '#9ca3af', dashArray: '5,5', label: 'binds to' },
};

// 단축키 → 노드 타입 역매핑
export const SHORTCUT_TO_TYPE: Record<string, CanvasItemType> = Object.fromEntries(
  Object.values(NODE_CONFIGS)
    .filter(c => c.shortcut !== null)
    .map(c => [c.shortcut!.toLowerCase(), c.type])
) as Record<string, CanvasItemType>;
```

### 통과 기준

| # | 기준 | 검증 |
|:-:|------|------|
| 1.2.1 | 11종 노드 모두 `NODE_CONFIGS`에 정의 | 코드 리뷰 |
| 1.2.2 | 색상 값이 설계 §2.1 표와 일치 | 설계 문서 대조 |
| 1.2.3 | 단축키가 설계 §8 표와 일치 (D/B/E/N/R/S/T/M) | 설계 문서 대조 |
| 1.2.4 | 4종 연결선 설정이 설계 §3.1과 일치 | 설계 문서 대조 |

---

## Step 1.3: Zustand 스토어 리팩터링

**파일**: `features/process-designer/store/useProcessDesignerStore.ts`

### 작업 내용

기존 `stores/processDesignerStore.ts`를 feature slice로 이동하고, **UI 상태만** 관리하도록 리팩터링한다. 캔버스 데이터(nodes, connections)는 별도 데이터 레이어(Step 1.4)로 분리하여 Phase 4에서 Yjs로 교체 가능하게 한다.

```typescript
// UI 상태만 관리 — 캔버스 데이터(nodes, connections)는 별도 레이어
interface ProcessDesignerUIState {
  // 도구 모드
  toolMode: ToolMode;
  setToolMode: (mode: ToolMode) => void;

  // 선택 상태
  selectedItemIds: string[];
  selectedConnectionIds: string[];
  selectItem: (id: string, multi?: boolean) => void;
  selectConnection: (id: string) => void;
  clearSelection: () => void;

  // 스테이지 뷰
  stageView: { x: number; y: number; scale: number };
  setStageView: (view: Partial<StageViewState>) => void;

  // 연결선 그리기 임시 상태
  pendingConnection: { sourceId: string; mousePos: { x: number; y: number } } | null;
  setPendingConnection: (conn: PendingConnection | null) => void;
}
```

### 중간 데이터 레이어 (Yjs 전환 전 임시)

**파일**: `features/process-designer/store/canvasDataStore.ts`

Phase 4 전까지는 Zustand로 캔버스 데이터를 관리하되, API를 Yjs와 동일한 인터페이스로 설계한다.

```typescript
// Phase 4에서 이 인터페이스를 Yjs 구현으로 교체
interface CanvasDataStore {
  items: CanvasItem[];
  connections: Connection[];

  addItem: (item: Omit<CanvasItem, 'id'>) => void;
  updateItem: (id: string, updates: Partial<CanvasItem>) => void;
  updateItemPosition: (id: string, x: number, y: number) => void;
  deleteItems: (ids: string[]) => void;

  addConnection: (conn: Omit<Connection, 'id'>) => void;
  updateConnection: (id: string, updates: Partial<Connection>) => void;
  deleteConnections: (ids: string[]) => void;

  // 보드 영속화
  loadBoard: (boardId: string) => Promise<void>;
  saveBoard: (boardId: string) => Promise<void>;
}
```

### 기존 `stores/processDesignerStore.ts` 처리

- deprecated 주석 추가, import를 새 경로로 리다이렉트하는 re-export 파일로 전환
- `ProcessDesignerPage.tsx` 등 기존 import를 새 경로로 변경

### 통과 기준

| # | 기준 | 검증 |
|:-:|------|------|
| 1.3.1 | UI 스토어에 nodes/connections 데이터 없음 | 코드 리뷰 |
| 1.3.2 | `canvasDataStore`가 Yjs 교체 가능한 인터페이스 | 코드 리뷰 |
| 1.3.3 | 기존 `stores/processDesignerStore.ts`에 deprecation 표시 | 코드 리뷰 |
| 1.3.4 | 기존 페이지가 새 스토어로 정상 동작 | 브라우저 확인 |
| 1.3.5 | `tsc --noEmit` 에러 없음 | CI |

---

## Step 1.4: 컴포넌트 분리

### 1.4a ProcessToolbox 분리

**파일**: `features/process-designer/components/toolbox/ProcessToolbox.tsx`

기존 `ProcessDesignerPage.tsx` 내 인라인 툴박스를 별도 컴포넌트로 추출하고, 11종 노드를 모두 표시한다.

```typescript
interface ProcessToolboxProps {
  disabled?: boolean;  // RBAC: 읽기 전용 시 비활성
  toolMode: ToolMode;
  onToolModeChange: (mode: ToolMode) => void;
  onDragStart: (e: React.DragEvent, type: CanvasItemType) => void;
}
```

UI 구조 (K-AIR 참조):
- 기본 노드 8종: 색상 카드 + 타입 라벨 + 단축키 뱃지
- 구분선
- 확장 노드 3종: 색상 카드 + 타입 라벨
- 구분선
- 연결선 모드 버튼 (`C` 단축키)
- 선택 모드 버튼 (`V` 단축키, 기본값)

### 1.4b CanvasNode 분리

**파일**: `features/process-designer/components/canvas/CanvasNode.tsx`

개별 노드 렌더링 컴포넌트. K-AIR의 `EventItem.vue` 패턴을 React로 이식.

```typescript
interface CanvasNodeProps {
  item: CanvasItem;
  selected: boolean;
  onSelect: (id: string, multi: boolean) => void;
  onDragEnd: (id: string, x: number, y: number) => void;
  onDoubleClick: (id: string) => void;
}
```

렌더링 구조 (react-konva Group):
- `<Rect>`: 배경 (color, cornerRadius, stroke)
- `<Text>`: 타입 라벨 (상단, fontSize 11, bold) — 접근성 §10.4
- `<Text>`: 인스턴스 이름 (중앙, fontSize 14)
- `<Circle>` x4: 연결 포인트 (상하좌우, hover 시 표시) — Phase 2에서 활성화

### 1.4c ContextBoxNode 분리

**파일**: `features/process-designer/components/canvas/ContextBoxNode.tsx`

Business Domain (contextBox) 타입은 영역 컨테이너로 별도 렌더링한다.
K-AIR의 `ContextBox` 패턴: 큰 Rect + 상단 라벨, 자식 노드 그룹핑.

```typescript
interface ContextBoxNodeProps {
  item: CanvasItem;  // type === 'contextBox'
  selected: boolean;
  childItems: CanvasItem[];  // parentContextBoxId === item.id
  onSelect: (id: string, multi: boolean) => void;
  onDragEnd: (id: string, x: number, y: number) => void;
  onResize: (id: string, width: number, height: number) => void;
}
```

### 1.4d ProcessCanvas 분리

**파일**: `features/process-designer/components/canvas/ProcessCanvas.tsx`

기존 `ProcessDesignerPage.tsx`의 Stage/Layer 부분을 별도 컴포넌트로 추출.

```typescript
interface ProcessCanvasProps {
  items: CanvasItem[];
  connections: Connection[];
  stageView: StageViewState;
  selectedItemIds: string[];
  toolMode: ToolMode;
  // 이벤트 핸들러
  onItemSelect: (id: string, multi: boolean) => void;
  onItemDragEnd: (id: string, x: number, y: number) => void;
  onItemDoubleClick: (id: string) => void;
  onCanvasClick: () => void;
  onDrop: (type: CanvasItemType, x: number, y: number) => void;
}
```

### 1.4e ProcessDesignerPage 리팩터링

기존 `pages/process/ProcessDesignerPage.tsx`를 분리된 컴포넌트로 조립하는 셸로 변경.

```tsx
export function ProcessDesignerPage() {
  return (
    <div className="flex flex-col h-[calc(100vh-4rem)]">
      <ProcessDesignerToolbar />
      <div className="flex flex-1 min-h-0">
        <ProcessToolbox />
        <ProcessCanvas />
        <ProcessPropertyPanel />
      </div>
    </div>
  );
}
```

### 통과 기준

| # | 기준 | 검증 |
|:-:|------|------|
| 1.4.1 | 툴박스에 11종 노드 모두 표시 (8종 기본 + 3종 확장 구분선) | 브라우저 스크린샷 |
| 1.4.2 | 11종 노드 모두 캔버스에 드래그 앤 드롭 배치 가능 | 브라우저 조작 |
| 1.4.3 | 각 노드에 타입 라벨(Event, Action 등) 상단 표시 | 브라우저 확인 |
| 1.4.4 | `contextBox` 노드가 영역 컨테이너로 렌더링 | 브라우저 확인 |
| 1.4.5 | 노드 드래그 이동 정상 동작 | 브라우저 조작 |
| 1.4.6 | 노드 클릭 시 선택 상태(흰색 테두리) 표시 | 브라우저 확인 |
| 1.4.7 | 빈 영역 클릭 시 선택 해제 | 브라우저 확인 |
| 1.4.8 | `ProcessDesignerPage`가 분리된 컴포넌트 조립 구조 | 코드 리뷰 |
| 1.4.9 | 미니맵 정상 동작 유지 | 브라우저 확인 |
| 1.4.10 | 레거시 `ProcessDesigner.tsx` (mock) 삭제 | 코드 리뷰 |

---

## Step 1.5: 보드 목록 페이지 개선

**파일**: `pages/process-designer/ProcessDesignerListPage.tsx`

### 작업 내용

설계 §11의 UX 상태 패턴 적용:
- 로딩: `ListSkeleton` 사용 (기존 텍스트 → 스켈레톤 교체)
- 빈 상태: `EmptyState` 사용 (아이콘 + 안내 + 버튼)
- 에러: `ErrorState` 사용

```tsx
import { EmptyState } from '@/shared/components/EmptyState';
import { ErrorState } from '@/shared/components/ErrorState';
import { ListSkeleton } from '@/shared/components/ListSkeleton';

// 로딩
if (loading) return <ListSkeleton rows={5} />;
// 에러
if (error) return <ErrorState message={error} onRetry={loadBoards} />;
// 빈 상태
if (boards.length === 0) return (
  <EmptyState
    icon={Workflow}
    title="아직 프로세스 보드가 없습니다"
    description="새 보드를 만들어 비즈니스 프로세스를 설계하세요."
    actionLabel="새 보드 만들기"
    onAction={handleCreateBoard}
  />
);
```

### 통과 기준

| # | 기준 | 검증 |
|:-:|------|------|
| 1.5.1 | 로딩 시 스켈레톤 표시 | 브라우저 (느린 네트워크 시뮬레이션) |
| 1.5.2 | 에러 시 ErrorState + 재시도 버튼 | API 에러 시뮬레이션 |
| 1.5.3 | 보드 없을 때 EmptyState + 새 보드 버튼 | 빈 목록 상태 |
| 1.5.4 | 공유 컴포넌트(`EmptyState`, `ErrorState`, `ListSkeleton`) 사용 | 코드 리뷰 |

---

## Phase 1 완료 체크리스트

| # | 항목 | 완료 |
|:-:|------|:----:|
| 1 | `types/processDesigner.ts` 생성 (11종 노드 + 4종 연결선 타입) | [ ] |
| 2 | `utils/nodeConfig.ts` 생성 (색상/단축키/크기 SSOT) | [ ] |
| 3 | `store/useProcessDesignerStore.ts` UI 전용 리팩터링 | [ ] |
| 4 | `store/canvasDataStore.ts` 데이터 레이어 분리 | [ ] |
| 5 | `components/toolbox/ProcessToolbox.tsx` 11종 노드 팔레트 | [ ] |
| 6 | `components/canvas/CanvasNode.tsx` 개별 노드 렌더링 | [ ] |
| 7 | `components/canvas/ContextBoxNode.tsx` 영역 노드 | [ ] |
| 8 | `components/canvas/ProcessCanvas.tsx` Stage 래퍼 | [ ] |
| 9 | `ProcessDesignerPage.tsx` 조립 구조 리팩터링 | [ ] |
| 10 | `ProcessDesignerListPage.tsx` UX 상태 적용 | [ ] |
| 11 | 레거시 `ProcessDesigner.tsx` 삭제 | [ ] |
| 12 | 기존 `stores/processDesignerStore.ts` deprecation 처리 | [ ] |
| 13 | `tsc --noEmit` 빌드 에러 0건 | [ ] |
| 14 | 브라우저에서 11종 노드 드래그 앤 드롭 동작 | [ ] |
