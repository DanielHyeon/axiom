# Process Designer 갭 분석 (설계 vs 구현)

> 분석일: 2026-02-27
> 설계 문서: `apps/canvas/docs/04_frontend/process-designer.md` (v1.2)
> 구현 대상: `pages/process/`, `pages/process-designer/`, `stores/processDesignerStore.ts`, `features/process-designer/`

---

## 요약

| 구분 | 설계 항목 수 | 구현 완료 | 스텁/부분 | 미구현 | 위반 |
|------|:-----------:|:---------:|:---------:|:------:|:----:|
| §1 화면 와이어프레임 | 7 | 2 | 2 | 3 | 0 |
| §2 노드 타입 (11종) | 11 | 4 | 0 | 7 | 0 |
| §3 연결선 (4종) | 4 | 0 | 0 | 4 | 0 |
| §4 속성 패널 (4영역) | 4 | 1 | 3 | 0 | 0 |
| §5 프로세스 마이닝 오버레이 | 5 | 0 | 2 | 3 | 0 |
| §6 Yjs 실시간 협업 | 5 | 0 | 1 | 4 | 1 |
| §7 AI 역공학 | 3 | 0 | 0 | 3 | 0 |
| §8 키보드 단축키 | 16 | 0 | 0 | 16 | 0 |
| §9 컴포넌트 구조 | 11 | 3 | 3 | 5 | 0 |
| §10 접근성 | 4 | 0 | 1 | 3 | 0 |
| §11 UX 상태 설계 | 12 | 3 | 2 | 7 | 0 |
| §12 RBAC | 4 | 0 | 0 | 4 | 0 |
| **합계** | **86** | **13 (15%)** | **14 (16%)** | **59 (69%)** | **1** |

---

## 위반 사항 (Forbidden/Required 규칙)

### VIOLATION-1: 캔버스 데이터를 Zustand에 직접 저장

| 항목 | 내용 |
|------|------|
| 설계 규칙 | "캔버스 노드/연결선 데이터를 Zustand store에 직접 저장 **금지**" (§결정 사항: Forbidden) |
| 현재 구현 | `processDesignerStore.ts`가 `nodes: CanvasNode[]`를 Zustand에 직접 관리 |
| 설계 의도 | 캔버스 데이터는 Yjs Document가 SSOT, Zustand는 toolMode/selectedItems 등 UI 상태만 |
| 영향도 | **HIGH** — Yjs 협업 도입 시 전면 리팩터링 필요 |
| 해결 방안 | Yjs Y.Map('items'), Y.Map('connections'), Y.Map('positions') 도입 후 Zustand에서 노드 데이터 제거 |

---

## 섹션별 상세 분석

### §1 화면 와이어프레임

| 구성 요소 | 설계 | 구현 상태 | 파일 |
|-----------|------|:---------:|------|
| 협업 인디케이터 (👥 N명 협업 중) | Header 영역 | **미구현** | — |
| 툴박스 (11종 노드 팔레트) | 좌측 패널 | **부분** (4종만) | `ProcessDesignerPage.tsx:114-150` |
| 캔버스 (react-konva Stage) | 중앙 영역 | **구현** | `ProcessDesignerPage.tsx:152-228` |
| 속성 패널 (우측) | 우측 패널 | **부분** (기본 속성만) | `PropertyPanel.tsx` |
| 미니맵 | 캔버스 좌하단 | **구현** | `Minimap.tsx` |
| 프로세스 마이닝 결과 패널 | 하단 | **스텁** | `ConformanceOverlay.tsx`, `VariantList.tsx` |
| 변형 목록 패널 | 우측 하단 | **스텁** | `VariantList.tsx` |

### §2 캔버스 아이템 타입 (11종)

**설계: 8종 기본 + 3종 확장 = 11종**

| 노드 타입 | 한국어 | 색상 | 단축키 | 구현 상태 |
|-----------|--------|------|:------:|:---------:|
| `contextBox` | Business Domain (부서/사업부) | Gray `#e9ecef` | D | **미구현** |
| `businessAction` | Business Action (업무 행위) | Blue `#87ceeb` | B | **구현** |
| `businessEvent` | Business Event (업무 사건) | Orange `#ffb703` | E | **구현** |
| `businessEntity` | Business Entity (업무 객체) | Yellow `#ffff99` | N | **구현** |
| `businessRule` | Business Rule (업무 규칙) | Pink `#ffc0cb` | R | **구현** |
| `stakeholder` | Stakeholder / Role (이해관계자) | Green `#d0f4de` | S | **미구현** |
| `businessReport` | Business Report (업무 보고서) | LightGreen `#90ee90` | T | **미구현** |
| `measure` | KPI/측정값 | Purple `#9b59b6` | M | **미구현** |
| `eventLogBinding` | 이벤트 로그 바인딩 | Blue-gray `#607d8b` | — | **미구현** |
| `temporalAnnotation` | 시간 주석 | Red outline `#e74c3c` | — | **미구현** |

**`CanvasItem` 인터페이스 갭:**

| 필드 | 설계 | 구현 (`CanvasNode`) |
|------|:----:|:-------------------:|
| id, type, x, y, label, color | O | O |
| width, height | O | **미구현** (하드코딩 140x80) |
| description | O | **미구현** |
| parentContextBoxId | O | **미구현** |
| temporal (expectedDuration, sla, actualAvg, status) | O | **미구현** |
| measureBinding (kpiId, formula, unit) | O | **미구현** |
| eventLogBinding (sourceTable, timestampColumn, ...) | O | **미구현** |

### §3 연결선 타입 (4종) — 전체 미구현

| 연결선 타입 | 의미 | 시각 스타일 | 구현 |
|------------|------|------------|:----:|
| `triggers` | Action → Event | 실선 화살표, 파란색 | **미구현** |
| `reacts_to` | Rule → Event | 점선 화살표, 핑크색 | **미구현** |
| `produces` | Event → Entity | 실선 화살표, 주황색 | **미구현** |
| `binds_to` | LogBinding → Event | 파선 화살표, 회색 | **미구현** |

`Connection` 인터페이스, `ConnectionLine` 컴포넌트, 연결 포인트(hover 시 Circle) 모두 미구현.
Zustand store에 `connections` 상태 없음. 연결선 생성/삭제 UX 없음.

### §4 속성 패널

| 속성 영역 | 설계 | 구현 상태 | 비고 |
|-----------|------|:---------:|------|
| 기본 속성 (이름, 설명, 색상) | O | **부분** | 라벨 편집만 가능, 설명/색상 편집 없음 |
| 시간축 속성 (TemporalProperties) | O | **스텁** | "연동 예정" 텍스트만 표시 |
| 측정값 바인딩 (MeasureBinding) | O | **스텁** | "연동 예정" 텍스트만 표시 |
| 이벤트 로그 바인딩 (EventLogBinding) | O | **스텁** | "연동 예정" 텍스트만 표시 |

### §5 프로세스 마이닝 결과 오버레이

| 기능 | 설계 | 구현 |
|------|------|:----:|
| ConformanceOverlay (캔버스 위 오버레이) | BottleneckHighlight + DeviationPath | **스텁** (빈 div) |
| ConformanceScore (적합도 점수) | 78.5% 표시 | **미구현** |
| VariantList (변형 목록) | 빈도별 정렬 + 선택 시 경로 하이라이트 | **스텁** (빈 div) |
| 오버레이 표시 모드 토글 | 드롭다운으로 표시 모드 전환 | **미구현** |
| `useProcessMining` hook | Synapse API 3개 엔드포인트 호출 | **미구현** |

Synapse API 엔드포인트(`/process-mining/discover`, `/conformance`, `/bottleneck`)에 대한 프론트엔드 API 클라이언트도 없음.

### §6 Yjs 실시간 협업

| 기능 | 설계 | 구현 |
|------|------|:----:|
| Y.Doc 구조 (items, connections, positions) | 3개 Y.Map | **미구현** |
| `useYjsCollaboration` hook | Yjs Provider + WebSocket | **스텁** (`collaborationStub.ts` → `{ enabled: false }`) |
| 커서 공유 (Awareness) | 사용자별 커서 + 색상 + 선택 상태 | **미구현** |
| CollaboratorCursors 컴포넌트 | 캔버스 위 커서 마커 | **미구현** |
| 오프라인 지원 (y-indexeddb) | 로컬 변경 큐잉 → 재연결 시 자동 동기화 | **미구현** |

**현재 데이터 저장**: `localStorage` 수동 저장 버튼(`ProcessDesignerPage.tsx:68-71`) — Yjs와 완전히 다른 접근.

### §7 AI 역공학 — 전체 미구현

| 기능 | 설계 | 구현 |
|------|------|:----:|
| "AI 프로세스 발견" 버튼 | 빈 캔버스에서 트리거 | **미구현** |
| 이벤트 로그 소스 선택 UI | Weaver API 데이터소스 셀렉터 | **미구현** |
| pm4py 결과 → Canvas 아이템 변환 | Activity→Event, Transition→Connection | **미구현** |

### §8 키보드 단축키 — 전체 미구현

설계에 16+ 단축키 정의됨 (B/E/N/R/S/T/M/D/C/V + Delete + Ctrl+Z/Shift+Z + Ctrl+A/D + Space+드래그 + Ctrl+스크롤).

`useCanvasKeyboard` hook이 설계에 명시되어 있으나 구현 없음.
현재 캔버스에 `onKeyDown` 핸들러 없음. 줌(onWheel) 처리 없음.

### §9 React Konva 컴포넌트 구조

| 컴포넌트 | 설계 | 구현 상태 |
|----------|------|:---------:|
| `ProcessDesignerPage` | React.lazy 진입점 | **구현** |
| `ProcessToolbox` (별도 컴포넌트) | 좌측 노드 팔레트, 11종 | **인라인** (4종, 별도 컴포넌트 아님) |
| `ProcessCanvas` (별도 컴포넌트) | react-konva Stage | **인라인** (ProcessDesignerPage 내부) |
| `CanvasItem` (별도 컴포넌트) | Group(Rect+Text+Circle) | **인라인** (연결 포인트 Circle 없음) |
| `ConnectionLine` | Arrow shape | **미구현** |
| `ConformanceOverlay` | BottleneckHighlight + DeviationPath | **스텁** |
| `CollaboratorCursors` | CursorMarker (xN) | **미구현** |
| `ProcessPropertyPanel` | 4개 서브 패널 | **부분** (기본 속성만 동작) |
| `ProcessMinimap` | Stage 축소 미러 | **구현** (div 기반 구현, react-konva Stage 아님) |
| `ProcessVariantPanel` | ConformanceScore + VariantList | **스텁** |
| `ContextBox` | Business Domain 영역 그룹 | **미구현** |

**미구현 이벤트 핸들러:**
- `onDblClick` (인라인 편집) — 없음
- `onWheel` (줌) — 없음
- `onMouseDown/Move/Up` (드래그 선택 영역) — 없음

### §10 접근성 (A11y)

| 기능 | 설계 | 구현 |
|------|------|:----:|
| 트리/리스트 대체 뷰 | 캔버스/트리 뷰 전환 탭 | **미구현** |
| 캔버스 키보드 모드 (Tab/Enter/Arrow) | Tab으로 노드 포커스 이동, Enter 선택 | **미구현** |
| 스크린 리더 ARIA 지원 | `role="application"` + aria-label | **부분** (미니맵만 `aria-label` 있음) |
| 시각 대체 (아이콘/텍스트 라벨) | 노드 유형 텍스트 항상 표시 | **미구현** (캔버스 노드에 유형 라벨 없음) |

### §11 UX 상태 설계

**에러 상태:**

| 시나리오 | 설계 | 구현 |
|---------|------|:----:|
| 페이지 로드 실패 | ErrorFallback | **미구현** |
| Yjs WebSocket 연결 실패 | 상단 배너 + 자동 재연결 | **미구현** (Yjs 자체가 없음) |
| AI 역공학 실패 | AiReversePanel 에러 표시 | **미구현** |
| 프로세스 마이닝 API 실패 | 토스트 에러 | **미구현** |
| 보드 저장 실패 | 토스트 에러 | **미구현** |

**빈 상태:**

| 시나리오 | 설계 | 구현 |
|---------|------|:----:|
| 보드 목록 없음 | EmptyState + 새 보드 버튼 | **구현** (`ProcessDesignerListPage:89`) |
| 빈 캔버스 | 중앙 안내 + 가이드 링크 | **부분** (간단 텍스트만, 가이드 링크 없음) |
| 마이닝 데이터 없음 | MiningPanel 안내 | **미구현** |
| 검색 결과 없음 | 쿼리 표시 | **미구현** (검색 기능 자체 없음) |

**로딩 상태:**

| 시나리오 | 설계 | 구현 |
|---------|------|:----:|
| 보드 목록 조회 | BoardListSkeleton | **구현** (텍스트 "로딩 중", 스켈레톤 아님) |
| 캔버스 초기 로드 | 중앙 스피너 + 텍스트 | **미구현** |
| 마이닝 분석 | 스피너 + 진행률 | **미구현** |
| AI 역공학 | 단계별 타임라인 | **미구현** |
| 협업 참여자 로드 | AvatarStack Skeleton | **미구현** |

### §12 RBAC — 전체 미구현

| 기능 | 설계 | 구현 |
|------|------|:----:|
| 라우트 가드 (`RoleGuard`) | `case:read` 이상 | **미구현** (라우트에 RoleGuard 없음) |
| `usePermission` 기반 읽기 전용 모드 | `process:initiate` 권한 체크 | **미구현** |
| 툴박스 비활성 (읽기 전용) | `<ProcessToolbox disabled={!canEdit} />` | **미구현** |
| AI 역공학 버튼 조건부 표시 | `canEdit && hasPermission('agent:chat')` | **미구현** |

---

## 추가 발견 사항

### 1. 사용되지 않는 레거시 파일

`pages/process/ProcessDesigner.tsx`는 HTML div 기반의 단순 mock으로, react-konva 기반 `ProcessDesignerPage.tsx`와 완전히 별개. 라우트에서 사용되지 않으며 정리 대상.

### 2. 데이터 영속성 불일치

| 항목 | 설계 | 현재 |
|------|------|------|
| 캔버스 데이터 저장소 | Yjs Document (CRDT) | Zustand + localStorage 수동 저장 |
| 서버 동기화 | Yjs WebSocket Provider | 없음 (로컬만) |
| 충돌 해소 | Yjs CRDT merge | 해당 없음 (단일 사용자) |

### 3. 보드 목록 ↔ 캔버스 데이터 연결

`ProcessDesignerListPage`는 Core API(`/api/v1/process/definitions`)로 보드 목록을 관리하지만, 캔버스 편집 시 `ProcessDesignerPage`는 `localStorage`에 저장. 서버에 캔버스 노드/연결선 데이터가 영속화되지 않음.

### 4. 미니맵 구현 방식 차이

| 항목 | 설계 | 현재 |
|------|------|------|
| 렌더링 | `<Stage>` (react-konva 축소 미러) | HTML `div` 기반 |
| 기능성 | 동일하게 동작 | 동일하게 동작 |

기능적으로는 동등하나 설계서의 react-konva Stage 미러링과는 다른 접근.

---

## 우선순위별 구현 로드맵 제안

### P0: Critical (설계 위반 해소 + 핵심 기능)

| # | 항목 | 영향 | 예상 작업량 |
|:-:|------|------|:-----------:|
| 1 | Yjs Document 도입 → Zustand에서 캔버스 데이터 분리 | VIOLATION-1 해소, 협업 기반 | L |
| 2 | 나머지 7종 노드 타입 추가 (contextBox, stakeholder, ...) | 핵심 모델링 기능 | M |
| 3 | 연결선(Connection) 4종 구현 | 프로세스 모델링 핵심 | L |
| 4 | RBAC RoleGuard 적용 | 보안 필수 | S |

### P1: High (사용성 핵심)

| # | 항목 | 영향 | 예상 작업량 |
|:-:|------|------|:-----------:|
| 5 | 키보드 단축키 (`useCanvasKeyboard`) | 생산성 | M |
| 6 | 속성 패널 완성 (Temporal, MeasureBinding, EventLogBinding) | 노드 속성 편집 | M |
| 7 | 줌/패닝 (onWheel + Space+드래그) | 캔버스 조작 기본 | S |
| 8 | 인라인 편집 (더블클릭) | 빠른 라벨 수정 | S |
| 9 | 컴포넌트 분리 (ProcessToolbox, ProcessCanvas, CanvasItem) | 유지보수성 | M |

### P2: Medium (협업 + 분석 연동)

| # | 항목 | 영향 | 예상 작업량 |
|:-:|------|------|:-----------:|
| 10 | Yjs Awareness 커서 공유 + CollaboratorCursors | 실시간 협업 | M |
| 11 | `useProcessMining` hook + Synapse API 연동 | 마이닝 오버레이 | L |
| 12 | ConformanceOverlay 실제 구현 (BottleneckHighlight, DeviationPath) | 시각화 | M |
| 13 | VariantList 실제 구현 | 변형 분석 | S |
| 14 | UX 상태 (에러/빈/로딩) 완성 | 사용자 경험 | M |

### P3: Low (고급 기능)

| # | 항목 | 영향 | 예상 작업량 |
|:-:|------|------|:-----------:|
| 15 | AI 역공학 (이벤트 로그 → 프로세스 모델) | 자동화 | L |
| 16 | 접근성 완성 (트리 뷰, 키보드 모드, ARIA) | WCAG 2.1 AA | L |
| 17 | 오프라인 지원 (y-indexeddb) | 안정성 | S |
| 18 | 레거시 `ProcessDesigner.tsx` 정리 | 코드 위생 | XS |

> 범례: XS (<0.5d), S (0.5-1d), M (1-3d), L (3-5d)

---

## 결론

설계 문서 대비 **전체 구현율은 약 15% (13/86 항목)**. 기본적인 react-konva 캔버스, 4종 노드의 드래그 앤 드롭 배치, 미니맵, 기본 속성 패널, 보드 목록 CRUD가 동작하는 수준이다.

**가장 큰 구조적 문제**는 설계가 명시적으로 금지한 "Zustand에 캔버스 데이터 직접 저장" 패턴이 현재 구현의 핵심이라는 점이다. Yjs 협업 도입 시 데이터 레이어 전면 리팩터링이 불가피하므로, 추가 기능 구현 전에 이 구조 문제를 먼저 해결하는 것을 권장한다.
