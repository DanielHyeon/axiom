# P3: KAIR 대비 갭 기능 구현 상세 계획서

> 작성일: 2026-03-20
> KAIR(Vue.js) 프론트엔드에 있으나 Axiom Canvas(React)에 없는 기능의 이식 계획

---

## 전체 요약

| # | 카테고리 | KAIR LOC | 예상 Axiom LOC | Phase | 우선순위 |
|---|----------|----------|----------------|-------|----------|
| 1 | 보안/감사 관리 | 3,505 | ~2,800 | 1 | P0 |
| 2 | 도메인 레이어 (ObjectType) | 22,832 | ~8,500 | 1 | P1 |
| 3 | What-if 5단계 위자드 | 13,577 | ~5,200 | 1 | P0 |
| 4 | 데이터 수집/파이프라인 | 7,563 | ~4,000 | 2 | P1 |
| 5 | 데이터 품질/관측성 | 7,160 | ~4,500 | 2 | P1 |
| 6 | 온톨로지 위자드 | 5,321 | ~3,200 | 2 | P2 |
| 7 | NL2SQL 고도화 (스키마 캔버스) | 14,672 | ~6,000 | 2 | P1 |
| 8 | 데이터 리니지 | 2,102 | ~2,000 | 3 | P2 |
| 9 | 비즈니스 글로서리 | 3,252 | ~2,400 | 3 | P2 |
| 10 | 오브젝트 탐색기 | 3,254 | ~3,000 | 3 | P2 |
| | **합계** | **83,238** | **~41,600** | | |

---

## Phase 1: 엔터프라이즈 기반

---

### 1. 보안/감사 관리

#### 1-1. KAIR 소스 분석

**핵심 컴포넌트 구조:**
```
components/security/
  SecurityGuardTab.vue    (165 LOC) — 탭 컨테이너, 5개 서브탭 전환
  UserManagement.vue      (652 LOC) — 사용자 CRUD, 역할 할당, 테이블 뷰
  RoleManagement.vue      (629 LOC) — 역할 CRUD, 권한 그룹별 토글, 카드 그리드
  TablePermissions.vue    (977 LOC) — 3레벨 계층 트리 + 캐스케이드 권한 패널
  SecurityPolicies.vue    (545 LOC) — 정책 카드 목록, JSON 편집, 토글 스위치
  AuditLogs.vue           (537 LOC) — 감사 로그 테이블, 필터, 상세 모달
  index.ts                (10 LOC)
```

**주요 기능:**
- RBAC 기반 사용자/역할 관리 (Neo4j 연동)
- 데이터소스 > 스키마 > 테이블 3레벨 계층형 권한 (캐스케이드 상속)
- SQL 감사 로그 조회 (allowed/denied/rewritten 상태 분류)
- 보안 정책 JSON 규칙 편집 (query_limit, column_mask, rate_limit 등)

**API 서비스:** `services/security-api.ts` — `getUsers`, `createUser`, `updateUser`, `deleteUser`, `getRoles`, `createRole`, `deleteRole`, `getPermissions`, `getAuditLogs`

#### 1-2. Axiom 이식 설계

**기존 Axiom 상태:** `/settings/users` 라우트에 `SettingsUsersPage.tsx`가 있으나, KAIR 수준의 세분화된 RBAC/테이블 권한/감사 로그는 없음.

**신규 feature slice 구조:**
```
features/security/
  api/
    coreSecurityApi.ts          — Core 서비스 보안 API 호출
  types/
    security.ts                 — User, Role, Permission, AuditLog, SecurityPolicy 타입
  hooks/
    useUsers.ts                 — TanStack Query: 사용자 목록/CRUD
    useRoles.ts                 — TanStack Query: 역할/권한
    useAuditLogs.ts             — TanStack Query: 감사 로그 조회
    useTablePermissions.ts      — 계층형 권한 계산 로직 (캐스케이드)
  store/
    useSecurityStore.ts         — Zustand: 활성 서브탭, 선택 노드 등 UI 상태
  components/
    SecurityLayout.tsx          — 탭 컨테이너 (Tabs from shadcn/ui)
    UserManagementTab.tsx       — 사용자 테이블 + 생성/수정 Dialog
    RoleManagementTab.tsx       — 역할 카드 그리드 + 권한 편집 Dialog
    TablePermissionsTab.tsx     — 트리 패널(좌) + 권한 패널(우)
    SecurityPoliciesTab.tsx     — 정책 카드 + JSON 편집 Dialog
    AuditLogsTab.tsx            — 감사 로그 DataTable + 상세 Sheet
```

**주요 Props/State 인터페이스:**
```typescript
// types/security.ts
interface User {
  uid: string;
  email: string;
  username: string;
  roles: string[];
  status: 'active' | 'inactive';
  created_at: string;
  last_login_at?: string;
}

interface Role {
  name: string;
  description: string;
  priority: number;
  permissions: string[];
  is_system: boolean;
}

interface Permission {
  action: string;
  resource_type: string;
  description?: string;
}

interface AuditLog {
  log_id: string;
  timestamp: string;
  user_email: string;
  session_id: string;
  original_sql: string;
  rewritten_sql?: string;
  status: 'allowed' | 'denied' | 'rewritten';
  execution_time_ms?: number;
  details?: string;
}

interface SecurityPolicy {
  name: string;
  policy_type: 'query_limit' | 'column_mask' | 'column_filter' | 'query_rewrite' | 'rate_limit';
  description: string;
  rules_json: string;
  priority: number;
  is_active: boolean;
}

// 계층형 권한
type AccessLevel = 'none' | 'read' | 'write' | 'admin' | 'inherited';
interface AccessRule {
  target_type: 'user' | 'role';
  target_name: string;
  level: AccessLevel;
  inherited_from?: string;
}
```

#### 1-3. 백엔드 의존성

| 엔드포인트 | 서비스 | 상태 | 비고 |
|-----------|--------|------|------|
| `GET /api/users` | Core | 기존 (일부) | JWT 기반 사용자 목록 |
| `POST /api/users` | Core | 기존 (일부) | 사용자 생성 |
| `PUT /api/users/:uid` | Core | **신규** | 역할/상태 업데이트 |
| `DELETE /api/users/:uid` | Core | **신규** | 사용자 삭제 |
| `GET /api/roles` | Core | **신규** | 역할 목록 |
| `POST /api/roles` | Core | **신규** | 역할 생성 |
| `DELETE /api/roles/:name` | Core | **신규** | 역할 삭제 |
| `GET /api/permissions` | Core | **신규** | 권한 목록 |
| `GET /api/audit-logs` | Oracle | **신규** | 감사 로그 조회 (status 필터) |
| `GET /api/security-policies` | Core | **신규** | 보안 정책 CRUD |

#### 1-4. 라우트 등록

**routes.ts 추가:**
```typescript
SETTINGS_SECURITY: '/settings/security',
```

**routeConfig.tsx 추가:**
```tsx
const SecurityPage = lazy(() => import('@/pages/settings/SecurityPage').then(...));
// children 내부:
{ path: 'settings/security', element: <SuspensePage><SecurityPage /></SuspensePage> }
```

**Sidebar.tsx:** 기존 Settings 하위 메뉴로 접근 (별도 사이드바 항목 불필요)

#### 1-5. 예상 LOC

| 파일 | LOC |
|------|-----|
| `api/coreSecurityApi.ts` | 120 |
| `types/security.ts` | 80 |
| `hooks/useUsers.ts` | 100 |
| `hooks/useRoles.ts` | 80 |
| `hooks/useAuditLogs.ts` | 60 |
| `hooks/useTablePermissions.ts` | 150 |
| `store/useSecurityStore.ts` | 40 |
| `components/SecurityLayout.tsx` | 80 |
| `components/UserManagementTab.tsx` | 350 |
| `components/RoleManagementTab.tsx` | 350 |
| `components/TablePermissionsTab.tsx` | 500 |
| `components/SecurityPoliciesTab.tsx` | 350 |
| `components/AuditLogsTab.tsx` | 350 |
| `pages/settings/SecurityPage.tsx` | 30 |
| **합계** | **~2,640** |

---

### 2. 도메인 레이어 (ObjectType)

#### 2-1. KAIR 소스 분석

**핵심 컴포넌트 구조:**
```
components/domain/
  MultiLayerOntologyViewer.vue  (14,511 LOC) — 메인 온톨로지 뷰어 (거대 파일)
  CreateObjectTypeDialog.vue     (2,100 LOC)  — OT 생성 다이얼로그
  ObjectTypeModeler.vue          (1,396 LOC)  — OT 모델러 (SchemaCanvas 통합)
  BehaviorDialog.vue             (1,150 LOC)  — Behavior 설정 다이얼로그
  CausalAnalysisPanel.vue        (854 LOC)    — 인과 분석 패널
  BpmnViewer.vue                 (781 LOC)    — BPMN 뷰어
  BehaviorExecuteDialog.vue      (749 LOC)    — Behavior 실행 다이얼로그
  ObjectTypeEditDialog.vue       (549 LOC)    — OT 편집 다이얼로그
  ChartConfigTab.vue             (518 LOC)    — 차트 설정 탭
  DmnEditor.vue                  (224 LOC)    — DMN 에디터
```

**주요 기능:**
- ObjectType 정의: 컬럼, 관계, MV(Materialized View) SQL, Behavior 설정
- Multi-layer 온톨로지 시각화 (Cytoscape 기반, 14K LOC 단일 파일)
- Behavior 실행: REST API, JavaScript, Python, DMN 4가지 유형
- 인과 분석 패널: VAR/Granger/Decomposition 결과 시각화
- BPMN/DMN 편집기 통합

**Axiom 기존 상태:** `features/ontology/` 에 API/타입/훅이 있고, `pages/ontology/OntologyPage.tsx`에 Cytoscape 기반 4계층 뷰어가 구현되어 있음. 그러나 ObjectType 정의/Behavior/MV 등 도메인 레이어 기능은 없음.

#### 2-2. Axiom 이식 설계

**전략:** KAIR의 14K LOC 모놀리스(`MultiLayerOntologyViewer`)를 분해하여 Axiom 패턴에 맞게 재설계. 핵심 기능만 우선 이식.

**신규 feature slice 구조:**
```
features/domain-layer/
  api/
    synapseObjectTypeApi.ts     — Synapse 서비스 ObjectType CRUD
  types/
    objectType.ts               — ObjectType, Column, Behavior, ChartConfig 타입
  hooks/
    useObjectTypes.ts           — TanStack Query: OT 목록/CRUD
    useBehaviors.ts             — TanStack Query: Behavior 실행/관리
  store/
    useDomainLayerStore.ts      — Zustand: 선택된 OT, 편집 모드 등
  components/
    ObjectTypeList.tsx           — OT 목록 사이드바
    CreateObjectTypeDialog.tsx   — OT 생성 (컬럼 정의, SQL, 관계)
    ObjectTypeEditDialog.tsx     — OT 편집
    ObjectTypeModeler.tsx        — 스키마 캔버스 + OT 모델링
    BehaviorDialog.tsx           — Behavior 설정 (4유형)
    BehaviorExecuteDialog.tsx    — Behavior 실행 + 결과
    ChartConfigPanel.tsx         — OT별 차트 설정
    CausalAnalysisPanel.tsx      — 인과 분석 결과 시각화
```

**주요 Props/State:**
```typescript
interface ObjectType {
  id: string;
  name: string;
  description?: string;
  columns: ObjectTypeColumn[];
  materializedViewSql?: string;
  relationships: ObjectTypeRelation[];
  behaviors: Behavior[];
  chartConfig?: ChartConfig;
}

interface ObjectTypeColumn {
  name: string;
  type: string;
  isPrimary?: boolean;
  isForeignKey?: boolean;
  referenceTable?: string;
  referenceColumn?: string;
}

interface Behavior {
  name: string;
  description?: string;
  behaviorType: 'rest_api' | 'javascript' | 'python' | 'dmn';
  config: Record<string, unknown>;
  inputFields?: string[];
  outputField?: string;
}

interface ChartConfig {
  chartType: 'bar' | 'line' | 'pie' | 'map' | 'none';
  xAxis?: string;
  yAxis?: string;
  valueField?: string;
  labelField?: string;
}
```

#### 2-3. 백엔드 의존성

| 엔드포인트 | 서비스 | 상태 | 비고 |
|-----------|--------|------|------|
| `GET /api/object-types` | Synapse | **신규** | OT 목록 |
| `POST /api/object-types` | Synapse | **신규** | OT 생성 (Neo4j 노드) |
| `PUT /api/object-types/:id` | Synapse | **신규** | OT 편집 |
| `DELETE /api/object-types/:id` | Synapse | **신규** | OT 삭제 |
| `POST /api/object-types/:id/behaviors` | Synapse | **신규** | Behavior 등록 |
| `POST /api/object-types/:id/behaviors/:name/execute` | Synapse | **신규** | Behavior 실행 |
| `POST /api/object-types/:id/mv` | Weaver | **신규** | MV 생성 |

#### 2-4. 라우트 등록

기존 `/data/ontology` 페이지 내부에 서브탭 또는 패널로 통합. 별도 라우트 불필요.

#### 2-5. 예상 LOC

| 파일 | LOC |
|------|-----|
| `api/synapseObjectTypeApi.ts` | 150 |
| `types/objectType.ts` | 100 |
| `hooks/useObjectTypes.ts` | 120 |
| `hooks/useBehaviors.ts` | 80 |
| `store/useDomainLayerStore.ts` | 60 |
| `components/ObjectTypeList.tsx` | 250 |
| `components/CreateObjectTypeDialog.tsx` | 600 |
| `components/ObjectTypeEditDialog.tsx` | 400 |
| `components/ObjectTypeModeler.tsx` | 800 |
| `components/BehaviorDialog.tsx` | 500 |
| `components/BehaviorExecuteDialog.tsx` | 400 |
| `components/ChartConfigPanel.tsx` | 300 |
| `components/CausalAnalysisPanel.tsx` | 500 |
| **합계** | **~4,260** |

> 참고: KAIR 22K LOC 대비 크게 줄어드는 이유는 (1) MultiLayerOntologyViewer 14K는 기존 Axiom OntologyPage와 중복 (2) React+shadcn/ui 패턴이 Vue SCSS보다 간결 (3) BPMN/DMN은 Phase 1에서 제외

---

### 3. What-if 5단계 위자드

#### 3-1. KAIR 소스 분석

**두 가지 What-if 시스템이 공존:**

**A. 독립 What-if 시뮬레이터 (`components/whatif/`)**
```
WhatIfSimulator.vue     (1,578 LOC) — 5단계 위자드 메인 (세션 관리 포함)
ScenarioInput.vue       (259 LOC)   — Step1: 시나리오 자연어 입력
DataSelector.vue        (420 LOC)   — Step2: 테이블 선택/SQL 커스텀
CausalDiscovery.vue     (2,473 LOC) — Step3: 인과 관계 발견 (그래프 시각화)
ValidationCompare.vue   (2,327 LOC) — Step4: 모델 검증 + MindsDB/TTM 비교
DataLiteracy.vue        (3,393 LOC) — Step5: 데이터 리터러시 설명 생성
```

**B. 온톨로지 내 What-if 패널 (`components/ontology/whatif/`)**
```
WhatIfPanel.vue          (378 LOC) — 6단계 위자드 패널 (관계발견→모델→학습→검증→시뮬→관리)
StepEdgeDiscovery.vue    (563 LOC) — 엣지/인과관계 발견
StepModelGraph.vue       (185 LOC) — 모델 DAG 구성
StepTrainModels.vue      (254 LOC) — 모델 학습/등록
StepValidation.vue       (292 LOC) — 검증
StepSimulation.vue       (1,042 LOC) — 시뮬레이션 실행
StepModelManager.vue     (221 LOC) — 모델 관리
ModelDagNode.vue         (192 LOC) — DAG 노드 커스텀 렌더러
```

**주요 기능:**
- 시나리오 기반 자연어 → 에이전트 분석 → 관련 테이블 자동 발견
- localStorage 기반 세션 저장/복원 (최대 10개)
- 인과 관계 발견 (Granger/VAR 기반)
- MindsDB/TTM 비교 분석
- 데이터 리터러시 보고서 생성

**Axiom 기존 상태:**
- `features/whatif/` — 타입, store, hooks, API가 이미 있음
- `pages/whatif/WhatIfPage.tsx` — 기본 페이지 존재
- `services/vision/app/engines/whatif_dag_engine.py` — 백엔드 DAG 엔진 구현 완료
- **부족한 것:** 5단계 위자드 UI, 세션 관리, 인과 발견 시각화, 데이터 리터러시

#### 3-2. Axiom 이식 설계

**전략:** KAIR의 두 What-if 시스템(독립 + 온톨로지 내장)을 하나의 통합 위자드로 재설계. Vision 백엔드가 이미 DAG 엔진을 갖추고 있으므로 프론트엔드 위자드에 집중.

**기존 feature slice 확장:**
```
features/whatif/
  (기존 유지)
  api/visionWhatIfApi.ts         — 기존: Vision What-if API
  types/whatif.ts                — 기존: What-if 타입
  store/useWhatIfStore.ts        — 기존: What-if 상태
  hooks/useWhatIfVision.ts       — 기존: Vision 연동 훅

  (신규 추가)
  components/
    WhatIfWizard.tsx             — 5단계 위자드 컨테이너 + 네비게이션
    WizardSidebar.tsx            — 세션 사이드바 (저장/복원/삭제)
    StepScenarioInput.tsx        — Step1: 시나리오 입력
    StepDataSelector.tsx         — Step2: 데이터 선택 (테이블 체크박스 + SQL)
    StepCausalDiscovery.tsx      — Step3: 인과 관계 발견 시각화
    StepValidation.tsx           — Step4: 검증 및 비교 결과
    StepDataLiteracy.tsx         — Step5: 리터러시 보고서
    CausalGraph.tsx              — Cytoscape 기반 인과 그래프
    ComparisonChart.tsx          — 예측 비교 차트 (Recharts)
  hooks/
    useWhatIfSession.ts          — 세션 저장/복원 (localStorage)
    useWhatIfWizard.ts           — 위자드 스텝 로직
```

**주요 Props/State:**
```typescript
interface WhatIfSession {
  id: string;
  scenario: string;
  currentStep: number;
  createdAt: string;
  updatedAt: string;
  data: {
    discoveryResult?: DataDiscoveryResult;
    selectedTables?: string[];
    causalResult?: CausalDiscoveryResult;
    validationResult?: ValidationResult;
    comparisonResult?: ComparisonResult;
    literacyExplanation?: LiteracyExplanation;
  };
}

// WhatIfWizard Props
interface WhatIfWizardProps {
  initialSessionId?: string;
}

// StepCausalDiscovery Props
interface StepCausalDiscoveryProps {
  sessionId: string;
  causalResult: CausalDiscoveryResult | null;
  onRunDiscovery: (methods: string[], maxLag: number) => void;
  loading: boolean;
}
```

#### 3-3. 백엔드 의존성

| 엔드포인트 | 서비스 | 상태 | 비고 |
|-----------|--------|------|------|
| `POST /api/whatif/scenario` | Vision | **신규** | 시나리오 분석 + 테이블 발견 |
| `POST /api/whatif/collect` | Vision | **신규** | 데이터 수집 |
| `POST /api/whatif/causal-discovery` | Vision | **신규** | 인과 관계 발견 |
| `GET /api/whatif/validation/:sid` | Vision | **신규** | 검증 결과 |
| `POST /api/whatif/compare` | Vision | **신규** | 모델 비교 |
| `POST /api/whatif/explanation` | Vision | **신규** | 리터러시 생성 |
| `POST /api/whatif/dag/propagate` | Vision | **기존** | DAG 전파 (구현 완료) |
| `GET /api/whatif/dag/models` | Vision | **기존** | 모델 목록 (구현 완료) |

#### 3-4. 라우트 등록

기존 라우트 유지:
- `/cases/:caseId/scenarios` → `WhatIfPage` (이미 등록됨)

추가 독립 라우트:
```typescript
// routes.ts
ANALYSIS: {
  ...existing,
  WHATIF: '/analysis/whatif',
}
```

#### 3-5. 예상 LOC

| 파일 | LOC |
|------|-----|
| `components/WhatIfWizard.tsx` | 400 |
| `components/WizardSidebar.tsx` | 300 |
| `components/StepScenarioInput.tsx` | 200 |
| `components/StepDataSelector.tsx` | 350 |
| `components/StepCausalDiscovery.tsx` | 600 |
| `components/StepValidation.tsx` | 500 |
| `components/StepDataLiteracy.tsx` | 600 |
| `components/CausalGraph.tsx` | 400 |
| `components/ComparisonChart.tsx` | 250 |
| `hooks/useWhatIfSession.ts` | 150 |
| `hooks/useWhatIfWizard.ts` | 120 |
| **합계** | **~3,870** |

---

## Phase 2: 데이터 관리

---

### 4. 데이터 수집/파이프라인

#### 4-1. KAIR 소스 분석

**핵심 컴포넌트 구조:**
```
components/upload/
  UploadTab.vue               (1,338 LOC) — 메인 탭: 좌측 트리+드롭존, 우측 파일뷰어
  UploadModal.vue             (1,500 LOC) — 업로드 모달: 타입 감지, 소스 선택
  AnalysisProgressModal.vue   (1,138 LOC) — 분석 진행 모달: 단계별 진행률
  DropZone.vue                (292 LOC)   — 드래그&드롭 파일 입력
  PipelineControlPanel.vue    (393 LOC)   — 인제스천 제어 패널
  UploadTree.vue              (177 LOC)   — 파일 트리 뷰
  UploadTreeNode.vue          (212 LOC)   — 트리 노드
  FileList.vue                (109 LOC)   — 파일 목록
  AddMenu.vue                 (144 LOC)   — 추가 메뉴
  JsonViewer.vue              (81 LOC)    — JSON 뷰어

components/datasources/
  DataSourceManager.vue       (2,179 LOC) — 데이터소스 관리: 등록/삭제/헬스체크/메타추출
  DataSourcesTab.vue          (24 LOC)    — 래퍼
```

**주요 기능:**
- 파일 드래그&드롭 업로드 (폴더 업로드 지원)
- 자동 파일 타입 감지 (DDL 자동 분류)
- 파일 뷰어: 코드 하이라이팅, 라인 번호, JSON 뷰어
- 100+ 데이터소스 유형 카탈로그 (DB, NoSQL, DW, API, SaaS, Stream, Vector 등)
- 연결 테스트, 메타데이터 추출 (스키마/테이블/컬럼)
- 헬스 체크 인디케이터

**Axiom 기존 상태:**
- `features/datasource/` — Weaver API 연동, ERD 렌더링 등 이미 존재
- `pages/data/DatasourcePage.tsx` — 기본 데이터소스 페이지 존재
- **부족한 것:** 파일 업로드 UI, 파이프라인 제어, 100+ 데이터소스 카탈로그, 메타데이터 추출 워크플로

#### 4-2. Axiom 이식 설계

**신규 feature slice:**
```
features/data-ingestion/
  api/
    weaverIngestionApi.ts         — Weaver 파일 업로드/파이프라인 API
  types/
    ingestion.ts                  — UploadedFile, PipelineStatus, DetectTypesResponse
  hooks/
    useFileUpload.ts              — 파일 업로드 + 타입 감지
    usePipelineControl.ts         — 파이프라인 시작/중지/상태 폴링
  components/
    DropZone.tsx                  — 드래그&드롭 파일 입력
    UploadDialog.tsx              — 업로드 다이얼로그 (타입 선택, 파일 목록)
    FileTreeView.tsx              — 업로드된 파일 트리
    FileViewer.tsx                — 코드 뷰어 + JSON 뷰어
    PipelineProgressBar.tsx       — 인제스천 진행률 표시

features/datasource/ (기존 확장)
  components/
    DatasourceCatalog.tsx         — 100+ 데이터소스 카탈로그 (카테고리별 그리드)
    DatasourceCard.tsx            — 개별 데이터소스 카드 (헬스 인디케이터)
    ConnectionFormDialog.tsx      — 연결 설정 폼 다이얼로그
    MetadataExtractionDialog.tsx  — 메타데이터 추출 진행 다이얼로그
  hooks/
    useDatasourceCatalog.ts       — 카탈로그 검색/필터
    useMetadataExtraction.ts      — 추출 진행 상태 폴링
```

#### 4-3. 백엔드 의존성

| 엔드포인트 | 서비스 | 상태 | 비고 |
|-----------|--------|------|------|
| `POST /api/datasources` | Weaver | 기존 | 데이터소스 등록 |
| `GET /api/datasources` | Weaver | 기존 | 목록 조회 |
| `DELETE /api/datasources/:name` | Weaver | 기존 | 삭제 |
| `POST /api/datasources/:name/test` | Weaver | **신규** | 연결 테스트 |
| `POST /api/datasources/:name/extract` | Weaver | **신규** | 메타데이터 추출 |
| `GET /api/datasources/:name/health` | Weaver | **신규** | 헬스 체크 |
| `POST /api/upload/files` | Weaver | **신규** | 파일 업로드 |
| `POST /api/upload/detect-types` | Weaver | **신규** | 파일 타입 감지 |
| `POST /api/pipeline/start` | Weaver | **신규** | 파이프라인 시작 |
| `GET /api/pipeline/status` | Weaver | **신규** | 파이프라인 상태 |

#### 4-4. 라우트 등록

기존 `/data/datasources` 라우트 활용. 추가 라우트:
```typescript
DATA: {
  ...existing,
  UPLOAD: '/data/upload',
}
```

#### 4-5. 예상 LOC

| 파일 | LOC |
|------|-----|
| data-ingestion 전체 | ~1,800 |
| datasource 확장분 | ~2,200 |
| **합계** | **~4,000** |

---

### 5. 데이터 품질/관측성

#### 5-1. KAIR 소스 분석

**핵심 컴포넌트 구조:**
```
components/observability/
  DataQuality.vue          (785 LOC) — 메인: 테스트케이스 관리, 통계 도넛차트
  WatchAgent.vue           (3,442 LOC) — 감시 에이전트: VueFlow 기반 조건→액션 워크플로
  EventDetection.vue       (1,242 LOC) — 이벤트 감지: 조건/임계값 설정
  TestCaseModal.vue        (576 LOC) — 테스트 케이스 생성 모달
  AlertForm.vue            (433 LOC) — 알림 규칙 폼
  AlertsPage.vue           (322 LOC) — 알림 목록 페이지
  IncidentManager.vue      (360 LOC) — 인시던트 관리
  nodes/ (VueFlow 커스텀 노드)
    ActionNode.vue, ConditionNode.vue, SqlNode.vue, WhatIfNode.vue
```

**주요 기능:**
- 데이터 품질 테스트: null 체크, unique 체크, range 체크, format 체크
- 테스트 결과 통계 대시보드 (성공률, 정상 자산 비율, 커버리지)
- Watch Agent: 조건부 워크플로 (SQL 노드 → 조건 노드 → 액션 노드)
- 이벤트 감지: 임계값 기반 이상 탐지
- 인시던트 자동 생성 및 관리

**Axiom 기존 상태:**
- `pages/watch/WatchDashboardPage.tsx` 와 `features/watch/` 존재
- WatchRule/WatchAlert 도메인 모델이 Core에 정의됨
- **부족한 것:** DataQuality 테스트 프레임워크, 통계 대시보드, Watch Agent 비주얼 워크플로

#### 5-2. Axiom 이식 설계

**신규 feature slice:**
```
features/data-quality/
  api/
    coreDataQualityApi.ts       — Core 서비스 품질 테스트 API
  types/
    dataQuality.ts              — TestCase, TestSuite, TestResult, QualityStats
  hooks/
    useTestCases.ts             — TanStack Query: 테스트 케이스 CRUD
    useQualityStats.ts          — 통계 계산
  store/
    useDataQualityStore.ts      — 필터, 활성 탭 등 UI 상태
  components/
    DataQualityDashboard.tsx    — 메인 대시보드 (통계 카드 + 테이블)
    TestCaseTable.tsx           — 테스트 케이스 DataTable
    TestCaseCreateDialog.tsx    — 테스트 케이스 생성 모달
    QualityStatsCards.tsx       — 3개 통계 카드 (도넛 차트)
    TestSuitePanel.tsx          — 테스트 스위트 관리

features/watch/ (기존 확장)
  components/
    WatchAgentBuilder.tsx       — 비주얼 워크플로 빌더 (ReactFlow)
    EventDetectionForm.tsx      — 이벤트 감지 조건 폼
    IncidentList.tsx            — 인시던트 목록
    AlertRuleForm.tsx           — 알림 규칙 폼
  nodes/
    SqlNode.tsx                 — SQL 실행 노드
    ConditionNode.tsx           — 조건 분기 노드
    ActionNode.tsx              — 액션 노드 (알림/웹훅)
    WhatIfNode.tsx              — What-if 시뮬레이션 노드
```

#### 5-3. 백엔드 의존성

| 엔드포인트 | 서비스 | 상태 | 비고 |
|-----------|--------|------|------|
| `GET /api/data-quality/test-cases` | Core | **신규** | 테스트 케이스 목록 |
| `POST /api/data-quality/test-cases` | Core | **신규** | 테스트 케이스 생성 |
| `POST /api/data-quality/test-cases/:id/run` | Core | **신규** | 테스트 실행 |
| `GET /api/data-quality/stats` | Core | **신규** | 통계 요약 |
| `GET /api/watch/rules` | Core | 기존 | WatchRule 목록 |
| `POST /api/watch/rules` | Core | 기존 | WatchRule 생성 |
| `GET /api/watch/alerts` | Core | 기존 | WatchAlert 목록 |
| `GET /api/watch/incidents` | Core | **신규** | 인시던트 목록 |

#### 5-4. 라우트 등록

```typescript
// routes.ts 추가
DATA_QUALITY: '/data/quality',

// Sidebar에 추가
{ to: ROUTES.DATA_QUALITY, icon: ShieldCheck, labelKey: 'sidebar.dataQuality' }
```

#### 5-5. 예상 LOC

| 범위 | LOC |
|------|-----|
| data-quality feature 전체 | ~2,500 |
| watch feature 확장 (Agent Builder) | ~2,000 |
| **합계** | **~4,500** |

---

### 6. 온톨로지 위자드

#### 6-1. KAIR 소스 분석

```
components/ontology/
  OntologyWizard.vue          (1,058 LOC) — 3단계 위자드: 입력→검토→바인딩
  OntologyCanvas.vue          (504 LOC)   — 온톨로지 시각화 캔버스
  SchemaBasedGenerator.vue    (488 LOC)   — 스키마 기반 온톨로지 자동 생성
  SchemaSelector.vue          (441 LOC)   — 스키마 선택기
  OntologyTab.vue             (352 LOC)   — 탭 컨테이너
  InstancePanel.vue           (1,370 LOC) — 인스턴스 데이터 패널
  EntityQueryPanel.vue        (792 LOC)   — 엔티티 쿼리 패널
  FeedbackModal.vue           (316 LOC)   — 피드백/수정 요청 모달
```

**주요 기능:**
- 3단계 위자드: (1) PDF/텍스트 입력 → (2) LLM 스키마 생성+검토 → (3) 데이터 소스 바인딩
- 기존 스키마 목록에서 선택 또는 새로 생성
- 스키마 기반 자동 온톨로지 생성 (테이블→노드 매핑)
- MV(Materialized View) 생성 + CDC 모니터링 설정

**Axiom 기존 상태:**
- `features/ontology/` — 기본 API/타입/훅 존재
- `pages/ontology/OntologyPage.tsx` — Cytoscape 4계층 뷰어
- **부족한 것:** 위자드 기반 온톨로지 생성 플로, 스키마 기반 자동 생성, 데이터 바인딩

#### 6-2. Axiom 이식 설계

**기존 feature slice 확장:**
```
features/ontology/ (기존 확장)
  components/
    OntologyWizard.tsx          — 3단계 위자드 Stepper
    WizardStepInput.tsx         — Step1: PDF/텍스트 입력 + 기존 스키마 목록
    WizardStepReview.tsx        — Step2: LLM 생성 결과 검토 (Cytoscape 미리보기)
    WizardStepBinding.tsx       — Step3: 데이터 소스 바인딩 + MV 설정
    SchemaBasedGenerator.tsx    — 스키마 → 온톨로지 자동 변환
    InstanceDataPanel.tsx       — 인스턴스 데이터 조회 패널
    EntityQueryPanel.tsx        — 엔티티 쿼리 패널
    FeedbackDialog.tsx          — 스키마 수정 요청
  hooks/
    useOntologyWizard.ts        — 위자드 스텝 로직
    useSchemaGenerator.ts       — LLM 기반 스키마 생성
```

#### 6-3. 백엔드 의존성

| 엔드포인트 | 서비스 | 상태 | 비고 |
|-----------|--------|------|------|
| `POST /api/ontology/generate` | Synapse | **신규** | LLM 기반 스키마 생성 |
| `GET /api/ontology/schemas` | Synapse | 기존 (확장) | 스키마 목록 |
| `POST /api/ontology/schemas/:id/bind` | Synapse | **신규** | 데이터 바인딩 |
| `POST /api/ontology/schemas/:id/mv` | Weaver | **신규** | MV 생성 |

#### 6-4. 예상 LOC: ~3,200

---

### 7. NL2SQL 고도화 (스키마 캔버스)

#### 7-1. KAIR 소스 분석

```
components/text2sql/
  Text2SqlTab.vue             (3,879 LOC) — 메인 탭: 채팅 + 스키마 뷰 + 결과
  SchemaCanvas.vue            (3,781 LOC) — VueFlow 기반 ER 다이어그램 캔버스
  TableDetailPanel.vue        (1,127 LOC) — 테이블 상세: 컬럼, 샘플, AI 설명
  EditRelationshipDialog.vue  (1,086 LOC) — FK 관계 편집 다이얼로그
  DirectSqlInput.vue          (944 LOC)   — 직접 SQL 입력 (Monaco 에디터)
  HistoryPanel.vue            (799 LOC)   — 쿼리 히스토리 패널
  MermaidERView.vue           (679 LOC)   — Mermaid ER 다이어그램
  ColumnDetailPanel.vue       (688 LOC)   — 컬럼 상세
  CardinalityModal.vue        (586 LOC)   — 카디날리티 설정
  ReactStepTimeline.vue       (470 LOC)   — ReAct 단계 타임라인
  ReactSummaryPanel.vue       (403 LOC)   — ReAct 요약 패널
  ReactInput.vue              (375 LOC)   — ReAct 입력
  RelationshipManager.vue     (366 LOC)   — 관계 관리
  ERDiagram.vue               (363 LOC)   — ER 다이어그램
  DatabaseTree.vue            (348 LOC)   — DB 트리 뷰
  TableCard.vue               (273 LOC)   — 테이블 카드 (VueFlow 노드)
  ResultTable.vue             (178 LOC)   — 결과 테이블
  TypeWriter.vue              (77 LOC)    — 타이핑 효과
  SchemaView.vue              (78 LOC)    — 스키마 뷰 래퍼
```

**주요 기능:**
- VueFlow 기반 인터랙티브 ER 다이어그램 (테이블 드래그, 관계 편집)
- DB 트리 뷰 (데이터소스 > 스키마 > 테이블 > 컬럼)
- FK 관계 관리: 카디날리티 설정, 관계 추가/편집/삭제
- ReAct 에이전트 단계별 타임라인
- Monaco 기반 직접 SQL 입력
- 쿼리 히스토리 관리

**Axiom 기존 상태:**
- `features/nl2sql/` — 기본 API, 타입, 히스토리 훅 존재
- `features/datasource/` — ERD 렌더링 (Mermaid 기반)
- `pages/nl2sql/Nl2SqlPage.tsx` — 채팅 UI 존재
- **부족한 것:** 인터랙티브 스키마 캔버스(ReactFlow 기반), DB 트리 뷰, 관계 편집, ReAct 타임라인 시각화

#### 7-2. Axiom 이식 설계

**기존 feature slice 확장:**
```
features/nl2sql/ (기존 확장)
  components/
    SchemaCanvas.tsx            — ReactFlow 기반 ER 다이어그램
    SchemaCanvasToolbar.tsx     — 캔버스 도구 모음
    TableNode.tsx               — ReactFlow 커스텀 노드: 테이블
    DatabaseTreePanel.tsx       — DB 트리 뷰 (Accordion)
    TableDetailSheet.tsx        — 테이블 상세 Sheet (컬럼, 샘플, 통계)
    RelationshipEdge.tsx        — ReactFlow 커스텀 엣지: FK 관계
    EditRelationshipDialog.tsx  — FK 관계 편집
    CardinalityDialog.tsx       — 카디날리티 설정
    DirectSqlEditor.tsx         — Monaco SQL 에디터
    ReActTimeline.tsx           — ReAct 단계 타임라인
    ReActSummaryPanel.tsx       — ReAct 요약 패널
  hooks/
    useSchemaCanvas.ts          — 캔버스 상태: 노드/엣지/선택/줌
    useTableRelations.ts        — FK 관계 CRUD
    useDatabaseTree.ts          — DB 트리 데이터 로드
```

#### 7-3. 백엔드 의존성

| 엔드포인트 | 서비스 | 상태 | 비고 |
|-----------|--------|------|------|
| `GET /api/schemas/:ds/tables` | Weaver | 기존 | 테이블 목록 |
| `GET /api/schemas/:ds/tables/:t/columns` | Weaver | 기존 | 컬럼 목록 |
| `GET /api/schemas/:ds/tables/:t/sample` | Weaver | 기존 (확장) | 샘플 데이터 |
| `GET /api/schemas/:ds/relationships` | Weaver | **신규** | FK 관계 목록 |
| `POST /api/schemas/:ds/relationships` | Weaver | **신규** | FK 관계 추가 |
| `PUT /api/schemas/:ds/relationships/:id` | Weaver | **신규** | FK 관계 수정 |
| `DELETE /api/schemas/:ds/relationships/:id` | Weaver | **신규** | FK 관계 삭제 |
| `POST /api/nl2sql/react` | Oracle | 기존 | ReAct 에이전트 (스트리밍) |

#### 7-4. 라우트 등록

기존 `/analysis/nl2sql` 유지. 스키마 캔버스는 페이지 내 탭 또는 패널로 통합.

#### 7-5. 예상 LOC: ~6,000

---

## Phase 3: 시맨틱 레이어

---

### 8. 데이터 리니지

#### 8-1. KAIR 소스 분석

```
components/lineage/
  LineageTab.vue          (690 LOC) — 메인: 통계 바 + 그래프 + 검색
  LineageGraph.vue        (830 LOC) — Cytoscape 리니지 그래프 (SOURCE→ETL→TARGET)
  LineageDetailPanel.vue  (582 LOC) — 노드 상세 패널
```

**주요 기능:**
- ETL 데이터 흐름 시각화 (SOURCE → ETL → TARGET)
- Neo4j + OLAP ETL 설정에서 리니지 데이터 로드
- 노드 유형별 색상 구분 (소스=파랑, ETL=보라, 타겟=초록)
- 노드 클릭 시 상세 속성 패널

**Axiom 기존 상태:** 리니지 관련 구현 없음. Weaver 서비스에 리니지 도메인이 필요.

#### 8-2. Axiom 이식 설계

**신규 feature slice:**
```
features/lineage/
  api/
    weaverLineageApi.ts        — Weaver 리니지 API
  types/
    lineage.ts                 — LineageNode, LineageEdge, LineageStats
  hooks/
    useLineageData.ts          — TanStack Query: 리니지 데이터 로드
  store/
    useLineageStore.ts         — 선택 노드, 필터 등
  components/
    LineageGraph.tsx            — Cytoscape 리니지 그래프
    LineageStatsBar.tsx         — 통계 바 (소스/ETL/타겟 카운트)
    LineageDetailPanel.tsx      — 노드 상세 패널
    LineageSearchBar.tsx        — 노드 검색
```

#### 8-3. 백엔드 의존성

| 엔드포인트 | 서비스 | 상태 | 비고 |
|-----------|--------|------|------|
| `GET /api/lineage/overview` | Weaver | **신규** | 리니지 전체 그래프 |
| `GET /api/lineage/nodes/:id` | Weaver | **신규** | 노드 상세 |
| `GET /api/lineage/impact/:id` | Weaver | **신규** | 영향도 분석 |

#### 8-4. 라우트 등록

```typescript
DATA: {
  ...existing,
  LINEAGE: '/data/lineage',
}

// Sidebar 추가
{ to: ROUTES.DATA.LINEAGE, icon: GitBranch, labelKey: 'sidebar.lineage' }
```

#### 8-5. 예상 LOC: ~2,000

---

### 9. 비즈니스 글로서리

#### 9-1. KAIR 소스 분석

```
components/glossary/
  GlossaryTab.vue            (1,052 LOC) — 메인: 용어집 사이드바 + 용어 테이블
  BusinessDayCalendar.vue    (1,137 LOC) — 영업일 캘린더
  TermModal.vue              (670 LOC)   — 용어 생성/편집 모달
  GlossaryModal.vue          (393 LOC)   — 용어집 생성/편집 모달
```

**주요 기능:**
- 용어집 관리: 생성/편집/삭제
- 용어 관리: 이름, 설명, 상태(Draft/Approved/Deprecated), 관련 테이블/컬럼 매핑
- 용어 검색/필터 (상태별)
- 영업일 캘린더 관리

**Axiom 기존 상태:** Weaver에 `MetadataCatalog` 모델이 있으나, 글로서리 전용 UI 없음.

#### 9-2. Axiom 이식 설계

**신규 feature slice:**
```
features/glossary/
  api/
    weaverGlossaryApi.ts       — Weaver 글로서리 API
  types/
    glossary.ts                — Glossary, Term, TermStatus
  hooks/
    useGlossaries.ts           — TanStack Query: 용어집 CRUD
    useTerms.ts                — TanStack Query: 용어 CRUD
  store/
    useGlossaryStore.ts        — 선택 용어집, 필터 등
  components/
    GlossaryPage.tsx           — 레이아웃: 사이드바 + 메인
    GlossarySidebar.tsx        — 용어집 목록
    TermTable.tsx              — 용어 DataTable
    TermCreateDialog.tsx       — 용어 생성/편집 Dialog
    GlossaryCreateDialog.tsx   — 용어집 생성/편집 Dialog
```

#### 9-3. 백엔드 의존성

| 엔드포인트 | 서비스 | 상태 | 비고 |
|-----------|--------|------|------|
| `GET /api/glossary` | Weaver | **신규** | 용어집 목록 |
| `POST /api/glossary` | Weaver | **신규** | 용어집 생성 |
| `GET /api/glossary/:id/terms` | Weaver | **신규** | 용어 목록 |
| `POST /api/glossary/:id/terms` | Weaver | **신규** | 용어 생성 |
| `PUT /api/glossary/:id/terms/:tid` | Weaver | **신규** | 용어 수정 |
| `DELETE /api/glossary/:id/terms/:tid` | Weaver | **신규** | 용어 삭제 |

#### 9-4. 라우트 등록

```typescript
DATA: {
  ...existing,
  GLOSSARY: '/data/glossary',
}

// Sidebar 추가
{ to: ROUTES.DATA.GLOSSARY, icon: BookOpen, labelKey: 'sidebar.glossary' }
```

#### 9-5. 예상 LOC: ~2,400

---

### 10. 오브젝트 탐색기

#### 10-1. KAIR 소스 분석

```
components/object-explorer/
  ObjectExplorerTab.vue      (829 LOC) — 메인: 그래프 + 좌측 검색/상세 + 우측 차트
  ObjectExplorerGraph.vue    (677 LOC) — NVL(Neo4j Visualization Library) 그래프
  ObjectSearchPanel.vue      (524 LOC) — 검색 패널 (OT 필터 + 키워드)
  ObjectDetailPanel.vue      (420 LOC) — 노드 상세 패널 (속성 테이블)
  ObjectChartPanel.vue       (320 LOC) — OT별 차트 (Recharts)
  ChildSelectDialog.vue      (484 LOC) — 5+ child 노드 선택 다이얼로그
```

**주요 기능:**
- ObjectType 기반 그래프 탐색 (더블클릭 드릴다운)
- 스키마 정의 기반 관계 자동 추적
- 5개 이상 child 노드일 때 선택 다이얼로그
- OT별 차트 설정에 따른 데이터 시각화
- 3패널 레이아웃: 검색/상세(좌) + 그래프(중앙) + 차트(우)

**Axiom 기존 상태:** 온톨로지 그래프 뷰어는 있으나, ObjectType 기반 인스턴스 탐색기는 없음.

#### 10-2. Axiom 이식 설계

**신규 feature slice:**
```
features/object-explorer/
  api/
    synapseExplorerApi.ts       — Synapse ObjectType 인스턴스 조회 API
  types/
    objectExplorer.ts           — ObjectNode, ObjectRelation, GraphData
  hooks/
    useObjectExplorer.ts        — 그래프 데이터 로드 + 드릴다운
    useObjectSearch.ts          — OT 기반 검색
  store/
    useObjectExplorerStore.ts   — 선택 노드, 그래프 상태 등
  components/
    ObjectExplorerLayout.tsx    — 3패널 레이아웃 (리사이즈)
    ObjectGraph.tsx             — Cytoscape 인스턴스 그래프
    ObjectSearchPanel.tsx       — 좌측: 검색 탭
    ObjectDetailPanel.tsx       — 좌측: 상세 탭
    ObjectChartPanel.tsx        — 우측: OT별 차트
    ChildSelectDialog.tsx       — 다중 child 선택 Dialog
```

#### 10-3. 백엔드 의존성

| 엔드포인트 | 서비스 | 상태 | 비고 |
|-----------|--------|------|------|
| `GET /api/object-types` | Synapse | Phase 1에서 구현 | OT 목록 |
| `GET /api/object-types/:id/instances` | Synapse | **신규** | 인스턴스 목록 |
| `GET /api/object-types/:id/instances/:iid` | Synapse | **신규** | 인스턴스 상세 |
| `GET /api/object-types/:id/instances/:iid/relations` | Synapse | **신규** | 관계 탐색 |
| `GET /api/object-types/:id/instances/:iid/chart-data` | Synapse | **신규** | 차트 데이터 |

#### 10-4. 라우트 등록

```typescript
DATA: {
  ...existing,
  OBJECT_EXPLORER: '/data/object-explorer',
}

// Sidebar 추가
{ to: ROUTES.DATA.OBJECT_EXPLORER, icon: Boxes, labelKey: 'sidebar.objectExplorer' }
```

#### 10-5. 예상 LOC: ~3,000

---

## 구현 순서 (의존성 기반)

```
Phase 1 (엔터프라이즈 기반) — 4~6주
├── Step 1: 보안/감사 관리 (#1)               — Core 백엔드 → 프론트엔드
├── Step 2: What-if 5단계 위자드 (#3)          — Vision 백엔드 확장 → 프론트엔드
│   (의존: Vision whatif_dag_engine 기존 구현)
└── Step 3: 도메인 레이어 (#2)                 — Synapse 백엔드 → 프론트엔드
    (의존: #6 온톨로지 위자드의 기반)

Phase 2 (데이터 관리) — 5~7주
├── Step 4: NL2SQL 스키마 캔버스 (#7)          — Weaver 관계 API → 프론트엔드
│   (의존: Weaver 메타데이터 기존 구현)
├── Step 5: 데이터 수집/파이프라인 (#4)         — Weaver 파이프라인 → 프론트엔드
├── Step 6: 데이터 품질/관측성 (#5)             — Core 품질 API → 프론트엔드
│   (의존: #4 데이터 수집의 테스트 대상)
└── Step 7: 온톨로지 위자드 (#6)               — Synapse 생성 API → 프론트엔드
    (의존: #2 도메인 레이어의 OT 구조)

Phase 3 (시맨틱 레이어) — 3~4주
├── Step 8: 비즈니스 글로서리 (#9)             — Weaver 글로서리 API → 프론트엔드
├── Step 9: 데이터 리니지 (#8)                 — Weaver 리니지 API → 프론트엔드
│   (의존: #4 데이터소스 메타데이터)
└── Step 10: 오브젝트 탐색기 (#10)             — Synapse 인스턴스 API → 프론트엔드
    (의존: #2 도메인 레이어 OT 정의)
```

---

## routes.ts 최종 변경 사항

```typescript
export const ROUTES = {
  // ... 기존 유지 ...
  ANALYSIS: {
    OLAP: '/analysis/olap',
    NL2SQL: '/analysis/nl2sql',
    INSIGHT: '/analysis/insight',
    WHATIF: '/analysis/whatif',           // 신규
  },
  DATA: {
    ONTOLOGY: '/data/ontology',
    DATASOURCES: '/data/datasources',
    UPLOAD: '/data/upload',              // 신규
    LINEAGE: '/data/lineage',            // 신규
    GLOSSARY: '/data/glossary',          // 신규
    OBJECT_EXPLORER: '/data/object-explorer',  // 신규
    QUALITY: '/data/quality',            // 신규
  },
  SETTINGS_SECURITY: '/settings/security',  // 신규
} as const;
```

## Sidebar.tsx 변경 사항

```typescript
const navItems = [
  { to: ROUTES.DASHBOARD, icon: LayoutDashboard, labelKey: 'sidebar.dashboard' },
  { to: ROUTES.ANALYSIS.NL2SQL, icon: MessageSquareText, labelKey: 'sidebar.nl2sql' },
  { to: ROUTES.ANALYSIS.OLAP, icon: BarChart3, labelKey: 'sidebar.olapPivot' },
  { to: ROUTES.ANALYSIS.INSIGHT, icon: Lightbulb, labelKey: 'sidebar.insight' },
  { to: ROUTES.ANALYSIS.WHATIF, icon: FlaskConical, labelKey: 'sidebar.whatif' },     // 신규
  { to: ROUTES.DATA.ONTOLOGY, icon: Network, labelKey: 'sidebar.ontology' },
  { to: ROUTES.DATA.DATASOURCES, icon: Database, labelKey: 'sidebar.data' },
  { to: ROUTES.DATA.LINEAGE, icon: GitBranch, labelKey: 'sidebar.lineage' },          // 신규
  { to: ROUTES.DATA.GLOSSARY, icon: BookOpen, labelKey: 'sidebar.glossary' },          // 신규
  { to: ROUTES.DATA.OBJECT_EXPLORER, icon: Boxes, labelKey: 'sidebar.objectExplorer' }, // 신규
  { to: ROUTES.DATA.QUALITY, icon: ShieldCheck, labelKey: 'sidebar.dataQuality' },     // 신규
  { to: ROUTES.PROCESS_DESIGNER.LIST, icon: Workflow, labelKey: 'sidebar.processDesigner' },
  { to: ROUTES.WATCH, icon: Eye, labelKey: 'sidebar.watch' },
];
```

---

## 리스크 평가

| 리스크 | 영향 | 완화 전략 |
|--------|------|-----------|
| KAIR MultiLayerOntologyViewer 14K LOC 이식 복잡성 | 높음 | 모듈 분해 후 핵심만 우선 이식, 기존 OntologyPage 재활용 |
| Vision What-if 백엔드 API 부족 | 중간 | 기존 DAG 엔진 위에 시나리오/인과발견 API 점진 추가 |
| ReactFlow 학습 곡선 (SchemaCanvas, WatchAgent) | 중간 | 기존 datasource ERD 패턴 참고, ReactFlow 공식 예제 활용 |
| 보안 API가 Core 서비스에 광범위 추가 | 중간 | 기존 JWT/역할 시스템 확장, RLS 패턴 유지 |
| 데이터소스 100+ 카탈로그 유지보수 | 낮음 | 정적 설정 파일로 관리, 필요시 점진 추가 |
| 글로서리/리니지 Weaver 스키마 확장 | 낮음 | weaver 스키마에 glossary, lineage 테이블 추가 |

---

## 문서 갱신 필요 사항

- i18n: `sidebar.*` 키 7개 추가 (whatif, lineage, glossary, objectExplorer, dataQuality, upload, security)
- CLAUDE.md: 서비스별 역할 테이블에 신규 API 엔드포인트 반영
- 라우트 구조 문서 갱신 (routes.ts SSOT 기준)
