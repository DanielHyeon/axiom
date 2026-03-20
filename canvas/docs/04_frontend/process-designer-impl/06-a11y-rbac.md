# Phase 6: 접근성 (A11y) + RBAC

> 예상 기간: 2-3일
> 선행 조건: Phase 1-5 기능 구현 완료
> 설계 문서 섹션: §10 접근성, §12 RBAC

---

## 목표

1. WCAG 2.1 AA 접근성 준수 (트리 뷰, 키보드 모드, 스크린 리더, 시각 대체)
2. RBAC 기반 읽기 전용 모드 및 기능 제한

---

## Step 6.1: 트리/리스트 대체 뷰

**파일**: `features/process-designer/components/TreeView.tsx`

### 작업 내용

설계 §10.1 — 캔버스와 병렬로 프로세스 모델을 트리 구조로 열람하는 패널.

```typescript
interface TreeViewProps {
  items: CanvasItem[];
  connections: Connection[];
  selectedItemIds: string[];
  onSelectItem: (id: string) => void;
  onFocusCanvas: (id: string) => void;  // 캔버스를 해당 노드로 줌
}
```

**트리 구조:**
```
[캔버스 뷰 ●] [트리 뷰]
─────────────────────────
▼ 물류관리부 (Domain)
  ├── 입고 접수 (Event)
  │   ├── → 검수 시작 (triggers → Action)
  │   └── → 입고전표 (produces → Entity)
  ├── 검수 시작 (Action)
  └── 3일내 처리 (Rule)
      └── ← 입고 접수 (reacts_to ← Event)

▸ 출고관리부 (Domain)
```

기능:
- Business Domain → 하위 노드를 트리 구조로 표시
- 연결 관계를 "→ 도착 (관계 유형)" 형태로 표시
- 노드 클릭 시 캔버스가 해당 노드로 포커스+줌
- 동일 Yjs Document 사용 (캔버스와 데이터 동기)

### 통과 기준

| # | 기준 | 검증 |
|:-:|------|------|
| 6.1.1 | 캔버스 뷰 / 트리 뷰 탭 전환 가능 | 브라우저 확인 |
| 6.1.2 | 트리 뷰에 모든 노드가 계층적으로 표시 | 브라우저 확인 |
| 6.1.3 | 연결 관계가 노드 하위에 표시 | 브라우저 확인 |
| 6.1.4 | 트리에서 노드 클릭 시 캔버스가 해당 노드로 이동 | 브라우저 확인 |
| 6.1.5 | 키보드(Tab, Enter, Arrow)로 트리 탐색 가능 | 키보드 테스트 |

---

## Step 6.2: 캔버스 키보드 모드

### 작업 내용

설계 §10.2 — `useCanvasKeyboard.ts`에 접근성 키보드 모드 추가.

| 키 | 동작 |
|----|------|
| `Tab` | 다음 노드로 포커스 이동 (생성 순서) |
| `Shift+Tab` | 이전 노드로 포커스 이동 |
| `Enter` | 포커스된 노드 선택 → 속성 패널 열기 |
| `Arrow Keys` | 선택된 노드 이동 (10px 단위) |
| `Shift+Arrow Keys` | 선택된 노드 이동 (1px 단위, 정밀 조작) |
| `+` / `-` | 줌 인/아웃 |
| `Ctrl+Arrow Keys` | 캔버스 패닝 |
| `Shift+?` | 키보드 단축키 도움말 패널 열기 |

**포커스 링 표시:**
현재 포커스된 노드에 점선 파란색 테두리 표시 (선택 상태의 흰색 실선과 구분).

### 통과 기준

| # | 기준 | 검증 |
|:-:|------|------|
| 6.2.1 | Tab으로 노드 간 포커스 이동 (포커스 링 표시) | 키보드 테스트 |
| 6.2.2 | Enter로 포커스된 노드 선택 | 키보드 테스트 |
| 6.2.3 | Arrow Keys로 선택된 노드 이동 (10px) | 키보드 테스트 |
| 6.2.4 | Shift+Arrow Keys로 정밀 이동 (1px) | 키보드 테스트 |
| 6.2.5 | Shift+?로 단축키 도움말 패널 표시 | 키보드 테스트 |
| 6.2.6 | 포커스 링이 선택 테두리와 시각적으로 구분됨 | 브라우저 확인 |

---

## Step 6.3: 스크린 리더 ARIA 지원

### 작업 내용

설계 §10.3 — react-konva 캔버스에 ARIA 속성 추가.

```tsx
// 캔버스 컨테이너
<div
  role="application"
  aria-label={`프로세스 디자이너 캔버스. 노드 ${items.length}개, 연결 ${connections.length}개`}
  aria-roledescription="프로세스 디자이너"
>
  <Stage>...</Stage>
</div>

// 스크린 리더 라이브 영역 (모드 전환 알림)
<div aria-live="assertive" className="sr-only">
  {modeAnnouncement}  {/* "연결선 모드 활성화", "선택 모드" 등 */}
</div>

// 협업 동작 알림
<div aria-live="polite" className="sr-only">
  {collaborationAnnouncement}  {/* "김분석가이(가) '입고접수' 노드를 이동함" */}
</div>
```

### 통과 기준

| # | 기준 | 검증 |
|:-:|------|------|
| 6.3.1 | 캔버스에 `role="application"` + `aria-label` | DOM 검사 |
| 6.3.2 | 노드 수/연결 수가 aria-label에 반영 | 노드 추가 후 확인 |
| 6.3.3 | 모드 전환 시 `aria-live="assertive"` 발표 | 스크린 리더 테스트 |
| 6.3.4 | 협업 동작 시 `aria-live="polite"` 발표 | 스크린 리더 테스트 |

---

## Step 6.4: 시각 대체

### 작업 내용

설계 §10.4 — 색상에만 의존하지 않는 구분.

1. **노드 유형 텍스트 라벨**: 모든 캔버스 노드 상단에 "Event", "Action" 등 타입 텍스트 표시 (Phase 1에서 이미 구현)
2. **병목 하이라이트**: 빨간 배경 + ⚠ 아이콘 + "병목" 텍스트 병기
3. **SLA 상태**: 색상 + 아이콘 병기 (✓ ok, ⚠ warning, ✕ violation)

### 통과 기준

| # | 기준 | 검증 |
|:-:|------|------|
| 6.4.1 | 노드 유형이 색상 + 텍스트 라벨로 이중 표시 | 브라우저 확인 |
| 6.4.2 | 병목 구간이 색상 + ⚠ + "병목" 텍스트로 표시 | 브라우저 확인 |
| 6.4.3 | 그레이스케일 모드에서도 노드 유형 구분 가능 | 크롬 DevTools 그레이스케일 에뮬레이션 |

---

## Step 6.5: RBAC 적용

### 작업 내용

설계 §12 — 역할별 접근 제어.

#### (a) 라우트 가드

`routeConfig.tsx`의 process-designer 라우트에 `RoleGuard` 추가:

```tsx
{
  path: 'process-designer',
  children: [
    {
      index: true,
      element: (
        <RoleGuard roles={['admin', 'manager', 'attorney', 'analyst', 'engineer', 'staff', 'viewer']}>
          <SuspensePage><ProcessDesignerListPage /></SuspensePage>
        </RoleGuard>
      ),
    },
    {
      path: ':boardId',
      element: (
        <RoleGuard roles={['admin', 'manager', 'attorney', 'analyst', 'engineer', 'staff', 'viewer']}>
          <SuspensePage><ProcessDesignerPage /></SuspensePage>
        </RoleGuard>
      ),
    },
  ],
}
```

#### (b) 읽기 전용 모드

```typescript
const { hasPermission } = usePermission();
const canEdit = hasPermission('process:initiate');
const canRunAI = canEdit && hasPermission('agent:chat');
```

적용 포인트:
- `ProcessToolbox`: `disabled={!canEdit}` — 드래그 불가
- 캔버스 노드: `draggable={canEdit}` — 이동 불가
- 연결선 생성: `connect` 모드 진입 차단
- 속성 패널: 읽기전용 표시 (input → 텍스트)
- AI 역공학 버튼: `canRunAI`일 때만 표시
- 보드 생성 버튼: `canEdit`일 때만 표시
- 삭제 키(Delete): `canEdit`일 때만 동작

#### (c) Yjs 쓰기 차단 (설계 §12 비고)

읽기 전용 사용자도 Yjs WebSocket에 연결되어 실시간으로 다른 사용자 편집을 볼 수 있다.
단, 로컬에서 Yjs Document에 대한 쓰기를 프론트엔드에서 차단한다.

```typescript
const yjs = useYjsCollaboration({
  boardId,
  userId,
  userName,
  readOnly: !canEdit,  // true면 addItem/updateItem 등이 no-op
});
```

### 통과 기준

| # | 기준 | 검증 |
|:-:|------|------|
| 6.5.1 | 모든 인증 역할이 보드 목록/캔버스 조회 가능 | viewer 계정 테스트 |
| 6.5.2 | `process:initiate` 없는 역할(analyst, engineer, staff, viewer)은 편집 불가 | analyst 계정 테스트 |
| 6.5.3 | 읽기 전용 시 툴박스 비활성(회색) | 브라우저 확인 |
| 6.5.4 | 읽기 전용 시 노드 드래그 불가 | 브라우저 확인 |
| 6.5.5 | 읽기 전용 시 속성 패널 input → 텍스트 표시 | 브라우저 확인 |
| 6.5.6 | 읽기 전용 사용자도 다른 사용자의 실시간 편집 확인 가능 | 2개 계정 테스트 |
| 6.5.7 | AI 역공학 버튼이 `agent:chat` 권한 있을 때만 표시 | 역할별 테스트 |
| 6.5.8 | 보드 생성 버튼이 `process:initiate` 권한 있을 때만 표시 | viewer 계정 확인 |

---

## Phase 6 완료 체크리스트

| # | 항목 | 완료 |
|:-:|------|:----:|
| 1 | `TreeView.tsx` — 트리 대체 뷰 | [ ] |
| 2 | 캔버스 뷰 / 트리 뷰 탭 전환 | [ ] |
| 3 | 접근성 키보드 모드 (Tab/Enter/Arrow) | [ ] |
| 4 | 포커스 링 시각적 표시 | [ ] |
| 5 | 단축키 도움말 패널 (Shift+?) | [ ] |
| 6 | ARIA 속성 (role, aria-label, aria-live) | [ ] |
| 7 | 시각 대체 (타입 텍스트, 병목 아이콘+텍스트) | [ ] |
| 8 | 그레이스케일 모드 구분 가능 | [ ] |
| 9 | RoleGuard 라우트 가드 적용 | [ ] |
| 10 | `usePermission` 기반 읽기 전용 모드 | [ ] |
| 11 | 읽기 전용 시 모든 편집 UI 비활성 | [ ] |
| 12 | 읽기 전용 + Yjs 실시간 뷰 동시 동작 | [ ] |
| 13 | WCAG 2.1 AA 자가 점검 통과 | [ ] |
