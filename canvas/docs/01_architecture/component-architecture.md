# 컴포넌트 계층 구조

<!-- affects: frontend -->
<!-- requires-update: 04_frontend/directory-structure.md -->

## 이 문서가 답하는 질문

- Canvas의 컴포넌트는 어떤 계층 구조로 조직되는가?
- Pages, Features, Shared 컴포넌트의 경계는 어디인가?
- K-AIR의 40+ Vue 컴포넌트는 React에서 어떻게 재배치되는가?
- 컴포넌트 간 데이터 흐름 규칙은 무엇인가?

---

## 1. 3계층 컴포넌트 모델

### 1.1 계층 정의

```
┌─────────────────────────────────────────────────────────────┐
│  Pages (페이지 컴포넌트)                                     │
│  - 라우트와 1:1 대응                                        │
│  - React.lazy()로 코드 분할                                 │
│  - Feature 컴포넌트를 조합하여 화면 구성                    │
│  - 데이터 페칭의 진입점 (Suspense boundary)                 │
│                                                              │
│  예: CaseDashboardPage, DocumentListPage, OlapPivotPage     │
├─────────────────────────────────────────────────────────────┤
│  Features (기능 컴포넌트)                                    │
│  - 특정 비즈니스 기능에 종속                                 │
│  - 자체 상태 관리 (hooks)                                    │
│  - 해당 기능 내에서만 사용                                   │
│  - 다른 Feature를 import하지 않음                            │
│                                                              │
│  예: CaseTable, DocumentEditor, PivotBuilder, GraphViewer   │
├─────────────────────────────────────────────────────────────┤
│  Shared (공유 컴포넌트)                                      │
│  - 비즈니스 로직 없음 (순수 UI)                              │
│  - 어떤 Feature에서든 사용 가능                              │
│  - Shadcn/ui 기반 확장 + 커스텀 공용 컴포넌트                │
│                                                              │
│  예: DataTable, Chart, Modal, Toast, StatusBadge             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 의존성 방향

```
Pages ──────→ Features ──────→ Shared
  │               │               │
  │               │               └──→ Shadcn/ui primitives
  │               │
  │               └──→ Hooks (useCase, useDocument, ...)
  │                       │
  │                       └──→ API Services
  │
  └──→ Layout (Sidebar, Header, Breadcrumb)
```

#### 금지됨
- `Feature A` -> `Feature B` 직접 import
- `Shared` -> `Feature` import (역방향)
- `Page` -> API Service 직접 호출 (hook을 통해야 함)

#### 허용됨
- Feature 간 통신은 **Zustand store** 또는 **URL 파라미터**를 통해서만 가능
- 같은 Feature 내 하위 컴포넌트 간 props 전달

---

## 2. Feature 모듈 상세 구조

### 2.1 Feature 내부 파일 구성 (컨벤션)

```
src/features/case-dashboard/
├── components/           # Feature 전용 UI 컴포넌트
│   ├── CaseTable.tsx
│   ├── CaseCard.tsx
│   ├── CaseTimeline.tsx
│   ├── StatsCard.tsx
│   └── CaseFilters.tsx
├── hooks/                # Feature 전용 커스텀 훅
│   ├── useCases.ts       # TanStack Query wrapper
│   ├── useCaseStats.ts
│   └── useCaseFilters.ts
├── api/                  # Feature 전용 API 함수
│   ├── caseApi.ts
│   └── caseApi.types.ts
├── stores/               # Feature 전용 Zustand 스토어 (필요시)
│   └── caseFilterStore.ts
├── utils/                # Feature 전용 유틸리티
│   └── caseFormatter.ts
├── types/                # Feature 전용 타입
│   └── case.types.ts
└── index.ts              # Public API (배럴 파일)
```

### 2.2 8대 Feature 모듈 맵

```
src/features/
├── case-dashboard/       # 1. 케이스 대시보드
│   └── (위 구조 참조)
│
├── document-management/  # 2. 문서 관리 + HITL 리뷰
│   ├── components/
│   │   ├── DocumentList.tsx
│   │   ├── DocumentEditor.tsx      # Monaco Editor 기반
│   │   ├── DocumentDiffViewer.tsx   # AI 원본 vs 수정본
│   │   ├── ReviewPanel.tsx          # HITL 리뷰 패널
│   │   ├── InlineComment.tsx
│   │   └── ApprovalWorkflow.tsx
│   ├── hooks/
│   │   ├── useDocuments.ts
│   │   ├── useReviews.ts
│   │   └── useDocumentEditor.ts
│   └── ...
│
├── what-if-builder/      # 3. What-if 시나리오 빌더
│   ├── components/
│   │   ├── ScenarioPanel.tsx
│   │   ├── ParameterSlider.tsx
│   │   ├── TornadoChart.tsx
│   │   ├── ScenarioComparison.tsx
│   │   └── SensitivityMatrix.tsx
│   ├── hooks/
│   │   ├── useScenarios.ts
│   │   └── useSensitivity.ts
│   └── ...
│
├── olap-pivot/           # 4. OLAP 피벗 테이블
│   ├── components/
│   │   ├── PivotBuilder.tsx        # DnD 영역
│   │   ├── PivotTable.tsx          # 결과 테이블
│   │   ├── DimensionPalette.tsx    # 차원/측정값 팔레트
│   │   ├── DrilldownBreadcrumb.tsx
│   │   ├── ChartSwitcher.tsx       # 테이블 <-> 차트 전환
│   │   └── PivotFilters.tsx
│   ├── hooks/
│   │   ├── useOlapQuery.ts
│   │   ├── useCubes.ts
│   │   └── usePivotConfig.ts
│   └── ...
│
├── ontology-browser/     # 5. 온톨로지 브라우저
│   ├── components/
│   │   ├── GraphViewer.tsx          # React Force Graph
│   │   ├── NodeDetail.tsx
│   │   ├── LayerFilter.tsx          # 4계층 필터
│   │   ├── PathHighlighter.tsx
│   │   └── SearchPanel.tsx
│   ├── hooks/
│   │   ├── useOntologyGraph.ts
│   │   └── useNodeSearch.ts
│   └── ...
│
├── nl2sql-chat/          # 6. NL2SQL 대화형 쿼리
│   ├── components/
│   │   ├── ChatInterface.tsx
│   │   ├── MessageBubble.tsx
│   │   ├── SqlPreview.tsx           # SQL 구문 강조
│   │   ├── ResultTable.tsx
│   │   ├── QueryHistory.tsx
│   │   └── ChartRecommender.tsx
│   ├── hooks/
│   │   ├── useNl2sql.ts
│   │   ├── useQueryStream.ts       # SSE 스트리밍
│   │   └── useQueryHistory.ts
│   └── ...
│
├── watch-alerts/         # 7. Watch 알림 대시보드
│   ├── components/
│   │   ├── AlertFeed.tsx
│   │   ├── AlertCard.tsx
│   │   ├── AlertRuleEditor.tsx
│   │   ├── EventTimeline.tsx
│   │   └── PriorityFilter.tsx
│   ├── hooks/
│   │   ├── useAlerts.ts
│   │   ├── useWebSocket.ts         # WS 연결 관리
│   │   └── useAlertRules.ts
│   └── ...
│
├── process-designer/     # 8. 비즈니스 프로세스 디자이너
│   ├── components/
│   │   ├── ProcessDesigner.tsx        # 최상위 페이지 컴포넌트
│   │   ├── ProcessCanvas/             # react-konva 캔버스 (vue-konva 대체)
│   │   │   ├── ProcessCanvas.tsx      # Stage + Layer 구성
│   │   │   ├── CanvasItem.tsx         # 개별 노드 렌더링 (8종 비즈니스 + 3종 확장)
│   │   │   ├── ConnectionLine.tsx     # 연결선 (triggers, reacts_to, produces, binds_to)
│   │   │   ├── ContextBox.tsx         # Business Domain 영역 (부서/사업부)
│   │   │   └── CollaboratorCursors.tsx # Yjs awareness 기반 커서 표시
│   │   ├── ProcessToolbox/            # 노드 팔레트 (좌측)
│   │   │   ├── ProcessToolbox.tsx
│   │   │   ├── ToolboxItem.tsx        # 드래그 가능한 노드 아이콘
│   │   │   └── toolboxConfig.ts       # 노드 타입 정의 (색상, 아이콘, 단축키)
│   │   ├── ProcessPropertyPanel/      # 속성 패널 (우측)
│   │   │   ├── ProcessPropertyPanel.tsx
│   │   │   ├── TemporalProperties.tsx # 시간축 속성 (duration, SLA)
│   │   │   ├── MeasureBinding.tsx     # KPI/측정값 바인딩
│   │   │   └── EventLogBinding.tsx    # 이벤트 로그 소스 바인딩
│   │   ├── ProcessMinimap/            # 보드 전체 미니맵
│   │   │   └── ProcessMinimap.tsx
│   │   └── ProcessVariantPanel/       # 프로세스 마이닝 적합도 결과
│   │       ├── ProcessVariantPanel.tsx
│   │       ├── ConformanceOverlay.tsx # 병목/이탈 오버레이
│   │       └── VariantList.tsx        # 프로세스 변형 목록
│   ├── hooks/
│   │   ├── useProcessBoard.ts         # 보드 CRUD (TanStack Query)
│   │   ├── useYjsCollaboration.ts     # Yjs CRDT 동기화 + awareness
│   │   ├── useCanvasInteraction.ts    # 선택, 이동, 연결 인터랙션
│   │   ├── useProcessMining.ts        # Synapse 프로세스 마이닝 API
│   │   └── useCanvasKeyboard.ts       # 단축키 (B, E, R 등)
│   ├── api/
│   │   ├── processApi.ts              # Synapse 프로세스 마이닝 API
│   │   └── processApi.types.ts
│   ├── stores/
│   │   └── processDesignerStore.ts    # Zustand: toolMode, selectedItems, collaborators
│   ├── types/
│   │   ├── canvasItem.types.ts        # 11종 노드 타입 정의
│   │   ├── connection.types.ts        # 연결선 타입 정의
│   │   └── board.types.ts             # 보드 상태 타입
│   └── index.ts
│
└── datasource-manager/   # + 데이터소스 관리
    ├── components/
    │   ├── DatasourceList.tsx
    │   ├── ConnectionForm.tsx
    │   ├── SchemaExplorer.tsx
    │   ├── SyncProgress.tsx         # SSE 진행률
    │   └── MetadataTree.tsx
    ├── hooks/
    │   ├── useDatasources.ts
    │   ├── useMetadataSync.ts
    │   └── useSchemaExplore.ts
    └── ...
```

---

## 3. K-AIR Vue 컴포넌트 -> Canvas React 컴포넌트 매핑

### 3.1 process-gpt-vue3 (SpikeAdmin) 전환

| Vue 컴포넌트 (디렉토리) | Canvas Feature | React 컴포넌트 | 전환 노트 |
|--------------------------|---------------|----------------|-----------|
| `admin/` | 시스템 관리 (Phase 2) | - | 우선순위 낮음 |
| `apps/chats/` | nl2sql-chat | ChatInterface, MessageBubble | Socket.io -> TanStack Query + SSE |
| `designer/` (BPMN) | 대상 외 | - | Canvas 범위 밖 |
| `dmn/` | 대상 외 | - | Canvas 범위 밖 |
| `analytics/` | case-dashboard | StatsCard, CaseTimeline | ApexCharts -> Recharts |
| `dashboard/` | case-dashboard | CaseDashboardPage | Vuetify 카드 -> Shadcn/ui Card |

### 3.2 robo-data-fabric/frontend 전환

| Vue 뷰 | Canvas Feature | React 컴포넌트 | 전환 노트 |
|---------|---------------|----------------|-----------|
| `Dashboard.vue` | datasource-manager | DatasourceList | Headless UI -> Shadcn/ui |
| `DataSources.vue` | datasource-manager | ConnectionForm | Pinia -> Zustand |
| `QueryEditor.vue` | nl2sql-chat | SqlPreview | 에디터 유지 |
| `MaterializedTables.vue` | datasource-manager | MetadataTree | 트리 구조 유지 |

### 3.3 data-platform-olap/frontend 전환

| Vue 컴포넌트 | Canvas Feature | React 컴포넌트 | 전환 노트 |
|--------------|---------------|----------------|-----------|
| `PivotEditor.vue` | olap-pivot | PivotBuilder | DnD: vue-draggable -> @dnd-kit |
| `PivotTable.vue` | olap-pivot | PivotTable | TanStack Table 활용 |
| `NaturalQuery.vue` | nl2sql-chat | ChatInterface | i18n 유지 (ko/en) |
| `CubeModeler.vue` | olap-pivot | DimensionPalette | cubeStore -> Zustand |
| `DataLineage.vue` | ontology-browser | GraphViewer | Mermaid -> React Force Graph |
| `ETLManager.vue` | 데이터소스 관리 | SyncProgress | Airflow 연동 |

### 3.4 eventstorming-tool (핵심 이식) 전환

| Vue 컴포넌트 | Canvas Feature | React 컴포넌트 | 전환 노트 |
|--------------|---------------|----------------|-----------|
| `CanvasBoard.vue` | process-designer | ProcessCanvas | vue-konva -> react-konva (동일 Konva.js 엔진) |
| `StickyNote.vue` | process-designer | CanvasItem | EventStorming 노드 -> Business Process 노드 개념 확장 |
| `ContextBox.vue` | process-designer | ContextBox | Business Domain 영역으로 의미 확장 |
| `Toolbox.vue` | process-designer | ProcessToolbox | 7종 EventStorming -> 8종 비즈니스 + 3종 확장 |
| `PropertyPanel.vue` | process-designer | ProcessPropertyPanel | 시간축, 측정값 바인딩, 이벤트 로그 바인딩 패널 추가 |
| `Minimap.vue` | process-designer | ProcessMinimap | 구조 유지 |
| Yjs 동기화 로직 | process-designer | useYjsCollaboration | Yjs는 프레임워크 무관 -- 로직 그대로 이식 |

---

## 4. 컴포넌트 통신 패턴

### 4.1 패턴 분류

```
┌─────────────────────────────────────────────────────────┐
│  1. Props 전달 (부모 -> 자식)                            │
│     Page -> Feature -> Sub-component                     │
│     사용: 동일 Feature 내 데이터 전달                    │
│                                                          │
│  2. Callback 전달 (자식 -> 부모)                         │
│     onSelect, onChange, onSubmit                         │
│     사용: 이벤트 상향 전달                                │
│                                                          │
│  3. Zustand Store (전역 상태)                            │
│     authStore, uiStore, themeStore                       │
│     사용: Feature 간 공유 상태                            │
│                                                          │
│  4. TanStack Query 캐시 (서버 상태)                     │
│     queryClient.invalidateQueries(['cases'])             │
│     사용: Feature A의 mutation이 Feature B의 쿼리 무효화 │
│                                                          │
│  5. URL 파라미터 (네비게이션 상태)                       │
│     /cases/:caseId/documents/:docId                     │
│     사용: 페이지 간 컨텍스트 전달                        │
└─────────────────────────────────────────────────────────┘
```

### 4.2 통신 패턴 선택 기준

| 조건 | 패턴 | 예시 |
|------|------|------|
| 같은 Feature 내, 부모-자식 | Props/Callback | PivotBuilder -> DimensionPalette |
| 같은 Feature 내, 형제 | 공통 부모의 state 또는 Feature store | PivotTable <-> ChartSwitcher |
| Feature 간 상태 공유 | Zustand store | authStore의 currentUser |
| Feature 간 데이터 연동 | TanStack Query invalidation | 문서 승인 -> 케이스 상태 갱신 |
| 페이지 간 컨텍스트 | URL 파라미터 | 케이스 선택 -> 문서 목록 |
| 일회성 알림 | Toast (Sonner) | "저장되었습니다" |

---

## 5. Shared 컴포넌트 카탈로그

### 5.1 Shadcn/ui 기반 (직접 사용)

```
shared/ui/          # Shadcn/ui 컴포넌트 (npx shadcn-ui add 로 추가)
├── button.tsx
├── card.tsx
├── dialog.tsx
├── dropdown-menu.tsx
├── input.tsx
├── label.tsx
├── select.tsx
├── separator.tsx
├── sheet.tsx       # 모바일 사이드 패널
├── skeleton.tsx    # 로딩 플레이스홀더
├── table.tsx
├── tabs.tsx
├── textarea.tsx
├── toast.tsx       # Sonner 기반
└── tooltip.tsx
```

### 5.2 커스텀 확장 컴포넌트

```
shared/components/
├── DataTable/              # TanStack Table 래퍼
│   ├── DataTable.tsx       # 정렬, 필터, 페이지네이션
│   ├── ColumnHeader.tsx
│   └── Pagination.tsx
├── Chart/                  # Recharts 래퍼
│   ├── BarChart.tsx
│   ├── LineChart.tsx
│   ├── PieChart.tsx
│   └── TornadoChart.tsx    # 커스텀
├── StatusBadge.tsx         # 상태 배지 (active, pending, closed)
├── EmptyState.tsx          # 데이터 없음 화면
├── LoadingSkeleton.tsx     # 스켈레톤 UI 조합
├── ErrorFallback.tsx       # 에러 바운더리 fallback
├── ConfirmDialog.tsx       # 확인 다이얼로그
├── SearchInput.tsx         # 디바운스 검색
├── DateRangePicker.tsx     # 날짜 범위 선택
├── FileUpload.tsx          # 파일 업로드
└── Breadcrumb.tsx          # 경로 표시
```

---

## 결정 사항 (Decisions)

- Feature 기반 디렉토리 구조 (기술 기반이 아님)
  - 근거: K-AIR가 기술 기반 구조(`components/`, `views/`, `stores/`)로 인해 관련 파일이 흩어져 있었음
  - 참조: ADR-001

- Feature 간 직접 import 금지
  - 근거: 순환 의존 방지, Feature 독립 배포 가능성 확보
  - 재평가: Feature 공유 로직이 3개 이상 발생 시 `shared/features/` 계층 검토

## 사실 (Facts)

- K-AIR 기존 컴포넌트: Vue 40+ 디렉토리 (eventstorming-tool 포함)
- Canvas 목표 Feature 모듈: 9개 (8 기능 + 데이터소스)
- Shared 컴포넌트: Shadcn/ui 15+ primitives + 커스텀 10+ 컴포넌트
- 비즈니스 프로세스 디자이너: react-konva 기반, Yjs CRDT 실시간 협업

---

## 변경 이력

| 날짜 | 버전 | 작성자 | 내용 |
|------|------|--------|------|
| 2026-02-20 | 1.1 | Axiom Team | 비즈니스 프로세스 디자이너(process-designer) Feature 모듈 추가, eventstorming-tool 전환 매핑 추가 |
| 2026-02-19 | 1.0 | Axiom Team | 초기 작성 |
