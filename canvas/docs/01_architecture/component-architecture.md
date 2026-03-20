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

```text
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

```text
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

```text
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

### 2.2 22개 Feature 모듈 맵

> **역사적 참고**: 초기 설계 문서에서는 `nl2sql-chat`, `olap-pivot`, `ontology-browser`, `what-if-builder`, `watch-alerts` 등의 이름을 사용했으나, 실제 구현에서는 `nl2sql`, `olap`, `ontology`, `whatif`, `watch`로 간결하게 명명되었다. 아래는 **실제 디렉토리 이름** 기준이다.

#### A. 핵심 분석 (Core Analysis) -- 5개

```text
src/features/
├── nl2sql/               # NL2SQL 대화형 쿼리 (Oracle API)
│   ├── api/, components/, hooks/, types/
│
├── olap/                 # OLAP 피벗 테이블 (Vision API)
│   ├── api/, components/, hooks/, store/, types/
│
├── insight/              # KPI 임팩트 분석 — 3패널 (Vision API)
│   ├── api/, components/, hooks/, store/, types/, utils/
│
├── whatif/               # What-if DAG 시뮬레이션 (Vision API)
│   ├── api/, components/, hooks/, store/, types/
│
└── whatif-wizard/        # What-if 5단계 위자드 (Vision API)
    ├── api/, components/, hooks/, store/, types/
```

#### B. 온톨로지 및 시맨틱 (Ontology & Semantic) -- 5개

```text
src/features/
├── ontology/             # 온톨로지 5계층 그래프 브라우저 (Synapse API)
│   ├── api/, components/, hooks/, store/, types/
│
├── domain/               # 도메인 레이어 — GWT 엔진 (Synapse API)
│   ├── api/, components/, hooks/, store/, types/
│
├── domain-modeler/       # 도메인 모델러 UI (Synapse API)
│   ├── api/, components/, hooks/, store/, types/
│
├── glossary/             # 비즈니스 글로서리 (Weaver API)
│   ├── api/, components/, hooks/, store/, types/
│
└── object-explorer/      # 오브젝트 탐색기 (Synapse API)
    ├── api/, components/, hooks/, store/, types/
```

#### C. 데이터 관리 (Data Management) -- 4개

```text
src/features/
├── datasource/           # 데이터소스 관리 (Weaver API)
│   ├── api/, components/, hooks/, schemas/, types/, utils/
│
├── ingestion/            # 데이터 수집/파이프라인 (Weaver API)
│   ├── api/, components/, hooks/, store/, types/
│
├── data-quality/         # 데이터 품질 (Weaver API)
│   ├── api/, components/, hooks/, store/, types/
│
└── lineage/              # 데이터 리니지 시각화 (Synapse API)
    ├── api/, components/, hooks/, store/, types/
```

#### D. 프로세스 및 워크플로 (Process & Workflow) -- 2개

```text
src/features/
├── process-designer/     # 비즈니스 프로세스 디자이너 (Synapse API)
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
│   ├── store/
│   │   ├── useProcessDesignerStore.ts # Zustand: toolMode, selectedItems, collaborators
│   │   └── canvasDataStore.ts         # Zustand: 캔버스 데이터 상태
│   ├── types/
│   │   ├── canvasItem.types.ts        # 11종 노드 타입 정의
│   │   ├── connection.types.ts        # 연결선 타입 정의
│   │   └── board.types.ts             # 보드 상태 타입
│   ├── utils/                         # Feature 전용 유틸리티
│   └── index.ts
│
└── workflow-editor/      # 워크플로 에디터 (Core API)
    ├── components/, store/, types/
```

#### E. 케이스 및 문서 (Case & Document) -- 2개

```text
src/features/
├── case-dashboard/       # 케이스 대시보드 (Core API)
│   ├── api/, components/, hooks/, stores/, types/
│
└── document-management/  # 문서 관리 + HITL 리뷰 (Core API)
    ├── api/, components/, hooks/, stores/, types/
```

#### F. 관리 및 모니터링 (Admin & Monitoring) -- 4개

```text
src/features/
├── auth/                 # 인증/인가 (Core API)
│   ├── api/, components/, stores/, types/
│
├── security/             # 보안 관리 UI (Core API)
│   ├── api/, components/, hooks/, store/, types/
│
├── watch/                # 알림 규칙 및 이벤트 모니터링 (Core API)
│   ├── components/, hooks/, store/, types/
│
└── feedback/             # 피드백 대시보드 (Oracle API)
    ├── api/, components/, hooks/, types/
```

---

## 3. K-AIR Vue 컴포넌트 -> Canvas React 컴포넌트 매핑

### 3.1 process-gpt-vue3 (SpikeAdmin) 전환

| Vue 컴포넌트 (디렉토리) | Canvas Feature | React 컴포넌트 | 전환 노트 |
| ------------------------ | ------------- | -------------- | --------- |
| `admin/` | 시스템 관리 (Phase 2) | - | 우선순위 낮음 |
| `apps/chats/` | nl2sql | ChatInterface, MessageBubble | Socket.io -> TanStack Query + SSE |
| `designer/` (BPMN) | 대상 외 | - | Canvas 범위 밖 |
| `dmn/` | 대상 외 | - | Canvas 범위 밖 |
| `analytics/` | case-dashboard | StatsCard, CaseTimeline | ApexCharts -> Recharts |
| `dashboard/` | case-dashboard | CaseDashboardPage | Vuetify 카드 -> Shadcn/ui Card |

### 3.2 robo-data-fabric/frontend 전환

| Vue 뷰 | Canvas Feature | React 컴포넌트 | 전환 노트 |
| ------- | ------------- | -------------- | --------- |
| `Dashboard.vue` | datasource | DatasourceList | Headless UI -> Shadcn/ui |
| `DataSources.vue` | datasource | ConnectionForm | Pinia -> Zustand |
| `QueryEditor.vue` | nl2sql | SqlPreview | 에디터 유지 |
| `MaterializedTables.vue` | datasource | MetadataTree | 트리 구조 유지 |

### 3.3 data-platform-olap/frontend 전환

| Vue 컴포넌트 | Canvas Feature | React 컴포넌트 | 전환 노트 |
| ------------ | ------------- | -------------- | --------- |
| `PivotEditor.vue` | olap | PivotBuilder | DnD: vue-draggable -> @dnd-kit |
| `PivotTable.vue` | olap | PivotTable | TanStack Table 활용 |
| `NaturalQuery.vue` | nl2sql | ChatInterface | i18n 유지 (ko/en) |
| `CubeModeler.vue` | olap | DimensionPalette | cubeStore -> Zustand |
| `DataLineage.vue` | ontology | GraphViewer | Mermaid -> React Force Graph |
| `ETLManager.vue` | datasource | SyncProgress | Airflow 연동 |

### 3.4 eventstorming-tool (핵심 이식) 전환

| Vue 컴포넌트 | Canvas Feature | React 컴포넌트 | 전환 노트 |
| ------------ | ------------- | -------------- | --------- |
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

```text
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
| ---- | ---- | ---- |
| 같은 Feature 내, 부모-자식 | Props/Callback | PivotBuilder -> DimensionPalette |
| 같은 Feature 내, 형제 | 공통 부모의 state 또는 Feature store | PivotTable <-> ChartSwitcher |
| Feature 간 상태 공유 | Zustand store | authStore의 currentUser |
| Feature 간 데이터 연동 | TanStack Query invalidation | 문서 승인 -> 케이스 상태 갱신 |
| 페이지 간 컨텍스트 | URL 파라미터 | 케이스 선택 -> 문서 목록 |
| 일회성 알림 | Toast (Sonner) | "저장되었습니다" |

---

## 5. Shared 컴포넌트 카탈로그

### 5.1 Shadcn/ui 기반 (직접 사용)

```text
components/ui/      # Shadcn/ui 컴포넌트 (npx shadcn-ui add 로 추가)
├── badge.tsx
├── button.tsx
├── card.tsx
├── checkbox.tsx
├── input.tsx
├── label.tsx
├── popover.tsx
├── select.tsx
├── slider.tsx
├── table.tsx
└── textarea.tsx
```

> **참고**: 설계 시 `shared/ui/`에 배치 예정이었으나, 실제 구현에서는 `components/ui/`에 위치한다 (Shadcn/ui CLI 기본 경로).

### 5.2 커스텀 공유 컴포넌트 (현재 구현)

```text
shared/components/
├── AuthGuard.tsx           # 인증 가드
├── EmptyState.tsx          # 데이터 없음 화면
├── ErrorState.tsx          # 에러 상태 표시
├── ListSkeleton.tsx        # 목록 스켈레톤
├── LoadingSpinner.tsx      # 로딩 스피너
├── MermaidERDRenderer.tsx  # ERD 시각화 (Mermaid.js)
└── RoleGuard.tsx           # 역할 기반 접근 제어

shared/hooks/
├── useApiError.ts          # API 에러 핸들링
├── useObjectTypes.ts       # 오브젝트 타입
├── usePermission.ts        # 권한 체크
└── useRole.ts              # 역할 체크
```

> **미구현 설계 항목**: DataTable 래퍼, Chart 래퍼, StatusBadge, ConfirmDialog, SearchInput, DateRangePicker, FileUpload, Breadcrumb — 향후 공통 패턴 추출 시 추가 예정.

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
- Canvas 현재 Feature 모듈: 22개 (auth, case-dashboard, data-quality, datasource, document-management, domain, domain-modeler, feedback, glossary, ingestion, insight, lineage, nl2sql, object-explorer, olap, ontology, process-designer, security, watch, whatif, whatif-wizard, workflow-editor)
- Shared 컴포넌트: Shadcn/ui 11 primitives (badge, button, card, checkbox, input, label, popover, select, slider, table, textarea) + 커스텀 11 컴포넌트 (AuthGuard, EmptyState, ErrorState, ListSkeleton, LoadingSpinner, MermaidERDRenderer, RoleGuard 등)
- 전역 Zustand 스토어: 3개 (authStore, themeStore, processDesignerStore)
- Feature 전용 Zustand 스토어: 19개 (useDQStore, useDomainStore, useDomainModelerStore, useGlossaryStore, useIngestionStore, useInsightStore, useLineageStore, useObjectExplorerStore, useOntologyStore, useOntologyWizardStore, usePivotConfig, canvasDataStore, useProcessDesignerStore, useSecurityStore, useWatchStore, useWhatIfStore, useWhatIfWizardStore[whatif], useWhatIfWizardStore[whatif-wizard], useWorkflowEditorStore)
- 비즈니스 프로세스 디자이너: react-konva 기반, Yjs CRDT 실시간 협업

---

## 변경 이력

| 날짜 | 버전 | 작성자 | 내용 |
| ---- | ---- | ------ | ---- |
| 2026-02-20 | 1.1 | Axiom Team | 비즈니스 프로세스 디자이너(process-designer) Feature 모듈 추가, eventstorming-tool 전환 매핑 추가 |
| 2026-02-19 | 1.0 | Axiom Team | 초기 작성 |
| 2026-03-21 | 2.0 | Axiom Team | Feature 모듈 22개로 전면 현행화 (KAIR 갭 해소: glossary, lineage, object-explorer, domain-modeler, data-quality, ingestion, security, whatif-wizard, workflow-editor, feedback, domain 추가). Zustand 스토어 18개 + 전역 3개. Shared 컴포넌트 실제 파일 목록 반영 |
| 2026-03-21 | 2.1 | Axiom Team | 서브폴더 정확도 보정 (insight에 utils/ 추가, case-dashboard에서 utils/ 제거, document-management에 stores/ 추가, process-designer에 utils/ 추가 및 store/ 파일 목록 현행화). Zustand 스토어 수 18→19개로 정정 (usePivotConfig, canvasDataStore 누락분 추가) |
