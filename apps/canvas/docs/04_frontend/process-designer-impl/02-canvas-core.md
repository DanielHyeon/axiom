# Phase 2: Canvas Core — 연결선 + 키보드 단축키 + 줌/패닝

> 예상 기간: 3-4일
> 선행 조건: Phase 1 완료
> 설계 문서 섹션: §3 연결선, §8 키보드 단축키, §9 컴포넌트 구조

---

## 목표

1. 4종 연결선(triggers, reacts_to, produces, binds_to) 생성·렌더링·삭제
2. 16+ 키보드 단축키 구현
3. 줌(스크롤) / 패닝(Space+드래그) 구현
4. 드래그 선택 영역(rubber band) 구현
5. 인라인 라벨 편집 (더블클릭)

---

## Step 2.1: 연결선 렌더링

**파일**: `features/process-designer/components/canvas/ConnectionLine.tsx`

### 작업 내용

K-AIR의 `<v-arrow>` 패턴을 react-konva `<Arrow>`로 이식한다.

```typescript
import { Arrow } from 'react-konva';
import type { Connection, CanvasItem } from '../../types/processDesigner';

interface ConnectionLineProps {
  connection: Connection;
  sourceItem: CanvasItem;
  targetItem: CanvasItem;
  selected: boolean;
  onClick: (connId: string) => void;
}
```

핵심 구현:
- **엣지 포인트 계산**: K-AIR의 `getEdgePoint()` — 노드 중심 간 각도로 상/하/좌/우 엣지 결정
- **스타일 분기**: `CONNECTION_CONFIGS`에서 stroke, dashArray 참조
- **선택 상태**: 선택 시 파란색 + 두꺼운 선

**파일**: `features/process-designer/utils/edgePoints.ts`

```typescript
/**
 * 두 노드 사이의 연결선 시작/끝 좌표를 계산한다.
 * K-AIR eventstorming-tool의 getEdgePoint() 알고리즘 이식.
 *
 * @returns [sourceX, sourceY, targetX, targetY]
 */
export function computeEdgePoints(
  source: { x: number; y: number; width: number; height: number },
  target: { x: number; y: number; width: number; height: number },
): [number, number, number, number] {
  const sCx = source.x + source.width / 2;
  const sCy = source.y + source.height / 2;
  const tCx = target.x + target.width / 2;
  const tCy = target.y + target.height / 2;

  const getEdgePoint = (
    cx: number, cy: number,
    w: number, h: number, x: number, y: number,
    targetCx: number, targetCy: number,
  ) => {
    const dx = targetCx - cx;
    const dy = targetCy - cy;
    const angle = Math.atan2(dy, dx);
    if (angle > -Math.PI / 4 && angle <= Math.PI / 4) return { x: x + w, y: cy };       // 오른쪽
    if (angle > Math.PI / 4 && angle <= (3 * Math.PI) / 4) return { x: cx, y: y + h };   // 아래
    if (angle > (3 * Math.PI) / 4 || angle <= -(3 * Math.PI) / 4) return { x, y: cy };   // 왼쪽
    return { x: cx, y };                                                                    // 위
  };

  const sp = getEdgePoint(sCx, sCy, source.width, source.height, source.x, source.y, tCx, tCy);
  const tp = getEdgePoint(tCx, tCy, target.width, target.height, target.x, target.y, sCx, sCy);

  return [sp.x, sp.y, tp.x, tp.y];
}
```

### 통과 기준

| # | 기준 | 검증 |
|:-:|------|------|
| 2.1.1 | `triggers` 연결선이 파란색 실선 화살표로 렌더링 | 브라우저 확인 |
| 2.1.2 | `reacts_to` 연결선이 핑크색 점선 화살표로 렌더링 | 브라우저 확인 |
| 2.1.3 | `produces` 연결선이 주황색 실선 화살표로 렌더링 | 브라우저 확인 |
| 2.1.4 | `binds_to` 연결선이 회색 파선 화살표로 렌더링 | 브라우저 확인 |
| 2.1.5 | 연결선이 노드 엣지에서 시작/끝 (중앙이 아닌 가장자리) | 브라우저 확인 |
| 2.1.6 | 노드 이동 시 연결선이 실시간 업데이트 | 브라우저 드래그 |
| 2.1.7 | 연결선 클릭 시 선택 상태 표시 (파란색+두꺼움) | 브라우저 확인 |

---

## Step 2.2: 연결선 생성 모드

**파일**: `features/process-designer/hooks/useConnectionDraw.ts`

### 작업 내용

'연결선 모드(C)' 진입 후 소스→타겟 노드를 순서대로 클릭하여 연결선을 생성하는 UX.

**흐름:**
1. 도구 모드 `'connect'` 진입 (C키 또는 툴박스 버튼)
2. 소스 노드 클릭 → `pendingConnection.sourceId` 설정
3. 마우스 이동 → 임시 점선 화살표 표시 (소스 → 커서 위치)
4. 타겟 노드 클릭 → 연결선 생성, 도구 모드 `'select'`로 복귀
5. ESC → 연결선 모드 취소

**연결선 타입 자동 결정 (설계 §3.1 규칙):**

| 소스 타입 | 타겟 타입 | 연결선 타입 |
|-----------|-----------|------------|
| businessAction | businessEvent | `triggers` |
| businessRule | businessEvent | `reacts_to` |
| businessEvent | businessEntity | `produces` |
| eventLogBinding | businessEvent | `binds_to` |
| 그 외 | 그 외 | `triggers` (기본값) |

**파일**: `features/process-designer/components/canvas/ConnectionPoint.tsx`

노드 hover 시 상하좌우에 작은 원(연결 포인트)을 표시한다.

```typescript
interface ConnectionPointProps {
  nodeX: number;
  nodeY: number;
  nodeWidth: number;
  nodeHeight: number;
  visible: boolean;
  onPointClick: (position: 'top' | 'right' | 'bottom' | 'left') => void;
}
```

### 통과 기준

| # | 기준 | 검증 |
|:-:|------|------|
| 2.2.1 | C키 누르면 연결선 모드 진입 (커서 변경) | 브라우저 확인 |
| 2.2.2 | 소스 노드 클릭 후 마우스까지 임시 점선 표시 | 브라우저 확인 |
| 2.2.3 | 타겟 노드 클릭 시 올바른 타입의 연결선 자동 생성 | Action→Event = triggers 확인 |
| 2.2.4 | ESC로 연결선 모드 취소 | 브라우저 확인 |
| 2.2.5 | 노드 hover 시 연결 포인트 4개 표시 | 브라우저 확인 |
| 2.2.6 | 연결선 소스/타겟 노드 삭제 시 연결선도 자동 삭제 | 노드 삭제 후 확인 |

---

## Step 2.3: 키보드 단축키

**파일**: `features/process-designer/hooks/useCanvasKeyboard.ts`

### 작업 내용

설계 §8의 16+ 단축키를 구현한다. K-AIR의 `handleKeyDown` 패턴 참조.

```typescript
export function useCanvasKeyboard(options: {
  toolMode: ToolMode;
  setToolMode: (mode: ToolMode) => void;
  selectedItemIds: string[];
  selectAll: () => void;
  clearSelection: () => void;
  deleteSelected: () => void;
  duplicateSelected: () => void;
  undo: () => void;
  redo: () => void;
}) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // input/textarea/select에 포커스 시 스킵 (K-AIR 패턴)
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement ||
        e.target instanceof HTMLSelectElement
      ) return;

      // ... 단축키 처리
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [/* deps */]);
}
```

**단축키 매핑 (설계 §8):**

| 단축키 | 동작 | 구현 세부 |
|--------|------|-----------|
| B | Business Action 노드 추가 모드 | `setToolMode('businessAction')` |
| E | Business Event 노드 추가 모드 | `setToolMode('businessEvent')` |
| N | Business Entity 노드 추가 모드 | `setToolMode('businessEntity')` |
| R | Business Rule 노드 추가 모드 | `setToolMode('businessRule')` |
| S | Stakeholder 노드 추가 모드 | `setToolMode('stakeholder')` |
| T | Business Report 노드 추가 모드 | `setToolMode('businessReport')` |
| M | Measure 노드 추가 모드 | `setToolMode('measure')` |
| D | Business Domain 추가 모드 | `setToolMode('contextBox')` |
| C | 연결선 모드 | `setToolMode('connect')` |
| V | 선택 모드 (기본) | `setToolMode('select')` |
| Escape | 선택 해제 / 모드 취소 | 연결선 모드 시 취소, 아니면 선택 해제 |
| Delete / Backspace | 선택된 아이템 삭제 | 확인 없이 삭제 (Undo로 복구) |
| Ctrl+Z | 되돌리기 | Phase 4의 Yjs UndoManager, 임시: 스택 기반 |
| Ctrl+Shift+Z | 다시 실행 | 상동 |
| Ctrl+A | 전체 선택 | `e.preventDefault()` 필수 |
| Ctrl+D | 선택 복제 | 선택된 노드를 오프셋(+20,+20)으로 복사 |

### 통과 기준

| # | 기준 | 검증 |
|:-:|------|------|
| 2.3.1 | B/E/N/R/S/T/M/D 키로 노드 추가 모드 진입 | 각 키 입력 후 커서 변경 확인 |
| 2.3.2 | 노드 추가 모드에서 캔버스 클릭 시 해당 타입 노드 생성 | 브라우저 확인 |
| 2.3.3 | C키로 연결선 모드 진입, V키로 선택 모드 복귀 | 브라우저 확인 |
| 2.3.4 | Delete/Backspace로 선택된 노드 삭제 | 브라우저 확인 |
| 2.3.5 | Ctrl+A로 모든 노드 선택 | 브라우저 확인 |
| 2.3.6 | Ctrl+D로 선택 노드 복제 | 브라우저 확인 |
| 2.3.7 | input/textarea 포커스 시 단축키 비활성 | 속성 패널 입력 중 B키 → 동작 안 함 확인 |
| 2.3.8 | 브라우저 기본 단축키와 충돌 없음 | Ctrl+A가 페이지 전체 선택이 아닌 노드 전체 선택 확인 |

---

## Step 2.4: 줌 / 패닝

**파일**: `features/process-designer/hooks/useCanvasInteraction.ts`

### 작업 내용

캔버스 줌과 패닝을 구현한다.

**줌 (Ctrl + 스크롤):**
```typescript
const handleWheel = (e: KonvaEventObject<WheelEvent>) => {
  e.evt.preventDefault();
  const stage = e.target.getStage();
  if (!stage) return;

  const oldScale = stageView.scale;
  const pointer = stage.getPointerPosition();
  if (!pointer) return;

  const scaleBy = 1.1;
  const newScale = e.evt.deltaY > 0
    ? oldScale / scaleBy
    : oldScale * scaleBy;

  // 최소 0.1, 최대 3.0 클램핑
  const clampedScale = Math.max(0.1, Math.min(3.0, newScale));

  // 포인터 위치를 중심으로 줌
  const mousePointTo = {
    x: (pointer.x - stageView.x) / oldScale,
    y: (pointer.y - stageView.y) / oldScale,
  };
  const newPos = {
    x: pointer.x - mousePointTo.x * clampedScale,
    y: pointer.y - mousePointTo.y * clampedScale,
  };

  setStageView({ x: newPos.x, y: newPos.y, scale: clampedScale });
};
```

**패닝 (Space + 드래그):**
- Space 키 누른 상태에서 마우스 드래그 시 캔버스 이동
- 마우스 중간 버튼 드래그로도 패닝 가능
- 커서를 `grab` / `grabbing`으로 변경

### 통과 기준

| # | 기준 | 검증 |
|:-:|------|------|
| 2.4.1 | Ctrl + 스크롤 업 → 줌 인 | 브라우저 확인 |
| 2.4.2 | Ctrl + 스크롤 다운 → 줌 아웃 | 브라우저 확인 |
| 2.4.3 | 줌이 마우스 포인터 위치를 중심으로 동작 | 브라우저 확인 |
| 2.4.4 | 줌 범위 0.1 ~ 3.0 클램핑 | 극단 값 테스트 |
| 2.4.5 | Space + 드래그로 캔버스 패닝 | 브라우저 확인 |
| 2.4.6 | 패닝 중 커서가 grab → grabbing으로 변경 | 브라우저 확인 |
| 2.4.7 | 미니맵이 줌/패닝 상태를 실시간 반영 | 브라우저 확인 |

---

## Step 2.5: 드래그 선택 영역 (Rubber Band)

### 작업 내용

빈 캔버스 영역에서 마우스 드래그 시 선택 사각형(rubber band)을 표시하고, 영역 내 노드를 다중 선택한다.

**파일**: `features/process-designer/components/canvas/SelectionRect.tsx`

```typescript
<Rect
  x={rect.x}
  y={rect.y}
  width={rect.width}
  height={rect.height}
  fill="rgba(59, 130, 246, 0.1)"
  stroke="#3b82f6"
  strokeWidth={1}
  dash={[4, 4]}
/>
```

K-AIR 패턴: `mousedown` (빈 영역) → `mousemove` (사각형 업데이트) → `mouseup` (교차 노드 선택)

### 통과 기준

| # | 기준 | 검증 |
|:-:|------|------|
| 2.5.1 | 빈 영역 드래그 시 파란 점선 선택 사각형 표시 | 브라우저 확인 |
| 2.5.2 | 선택 사각형과 교차하는 노드 다중 선택 | 브라우저 확인 |
| 2.5.3 | Shift 클릭으로 선택 추가/제거 | 브라우저 확인 |
| 2.5.4 | 노드 위 드래그 시 선택 사각형이 아닌 노드 이동 | 브라우저 확인 |

---

## Step 2.6: 인라인 라벨 편집

### 작업 내용

캔버스 노드를 더블클릭하면 `<Html>` (react-konva-utils) 또는 `<foreignObject>`로 텍스트 입력을 오버레이한다.

**흐름:**
1. 노드 더블클릭 → `editingNodeId` 설정
2. 노드 위치에 `<input>` 오버레이 표시
3. Enter 또는 포커스 아웃 → 라벨 업데이트, 편집 종료
4. Escape → 편집 취소

### 통과 기준

| # | 기준 | 검증 |
|:-:|------|------|
| 2.6.1 | 노드 더블클릭 시 인라인 텍스트 입력 표시 | 브라우저 확인 |
| 2.6.2 | Enter로 라벨 확정 | 브라우저 확인 |
| 2.6.3 | Escape로 편집 취소 (원래 라벨 복원) | 브라우저 확인 |
| 2.6.4 | 포커스 아웃 시 라벨 확정 | 브라우저 확인 |
| 2.6.5 | 편집 중 다른 단축키(B, E 등) 비활성 | 브라우저 확인 |

---

## Phase 2 완료 체크리스트

| # | 항목 | 완료 |
|:-:|------|:----:|
| 1 | `ConnectionLine.tsx` + `edgePoints.ts` 연결선 렌더링 | [ ] |
| 2 | `ConnectionPoint.tsx` 연결 포인트 (hover) | [ ] |
| 3 | `useConnectionDraw.ts` 연결선 생성 모드 | [ ] |
| 4 | 소스/타겟 타입 기반 연결선 타입 자동 결정 | [ ] |
| 5 | 소스/타겟 노드 삭제 시 연결선 자동 삭제 | [ ] |
| 6 | `useCanvasKeyboard.ts` 16+ 단축키 | [ ] |
| 7 | 줌 인/아웃 (Ctrl + 스크롤) | [ ] |
| 8 | 패닝 (Space + 드래그) | [ ] |
| 9 | `SelectionRect.tsx` 드래그 선택 영역 | [ ] |
| 10 | 인라인 라벨 편집 (더블클릭) | [ ] |
| 11 | `tsc --noEmit` 빌드 에러 0건 | [ ] |
