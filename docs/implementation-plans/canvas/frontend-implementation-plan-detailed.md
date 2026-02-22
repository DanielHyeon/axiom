# Canvas 프론트엔드 상세 구현 계획 및 통과 조건

## 1. 문서 목적·범위

- **목적**: `docs/frontend-design-gap-analysis.md`에서 도출한 갭을 해소하기 위한 단계별 구현 계획을 수립하고, **Phase·작업 단위별 통과 조건**을 명시한다.
- **범위**: Canvas(`apps/canvas`) 프론트엔드 전반 — 라우팅·레이아웃·인프라·P0/P1/P2 Feature·품질·테스트.
- **참조 문서**:
  - `docs/frontend-design-gap-analysis.md` (갭 목록)
  - `apps/canvas/docs/04_frontend/` (routing, directory-structure, feature-priority-matrix, implementation-guide, case-dashboard, document-management 등)
  - `docs/implementation-plans/program/01_sprint-backlog-master.md` (프로그램 스프린트 연동)

---

## 2. Phase 개요

| Phase | 목표 | 산출물 핵심 | 통과 조건 요약 |
|-------|------|--------------|----------------|
| **Phase 0** | 인프라·구조 정리 | 라우트 설계 정렬, 디렉토리·레이아웃·공통 인프라 | §3 통과 조건 |
| **Phase 1** | P0 기능 완성 | 케이스 라우트·대시보드·문서+HITL | §4 통과 조건 |
| **Phase 2** | P1 기능 완성 | NL2SQL/OLAP/Watch 실연동, 복원력 UI | §5 통과 조건 |
| **Phase 3** | P2 기능 완성 | 데이터소스·프로세스 디자이너·설정·What-if·온톨로지 | §6 통과 조건 |
| **Phase 4** | 품질·테스트 | E2E·접근성·성능·문서 동기화 | §7 통과 조건 |

---

## 3. Phase 0: 인프라·구조 정리

### 3.1 작업 상세

#### 3.1.1 라우트 구조 설계 정렬

| 번호 | 작업 | 상세 |
|------|------|------|
| 0-R1 | Auth 경로 통일 | `/login` → `/auth/login`으로 이동. 기존 `/login`은 301 리다이렉트 또는 제거. `/auth/callback` 라우트 추가 (OAuth 콜백용, 초기에는 빈 페이지 가능). |
| 0-R2 | 대시보드·루트 | `/` → `/dashboard` 리다이렉트. `/dashboard`에 CaseDashboardPage 배치. |
| 0-R3 | 케이스 중첩 라우트 | `/cases`, `/cases/:caseId`, `/cases/:caseId/documents`, `/cases/:caseId/documents/:docId`, `/cases/:caseId/documents/:docId/review`, `/cases/:caseId/scenarios` 추가. 기존 `/documents`는 `/cases` 없이 접근 시 리다이렉트 또는 경고 처리 정책 결정. |
| 0-R4 | 분석·데이터 경로 | `/analytics/pivot` → `/analysis/olap`, `/nl2sql` → `/analysis/nl2sql`. `/ontology` → `/data/ontology`. `/data/datasources` 신규. |
| 0-R5 | 프로세스·설정 | `/process` → `/process-designer`, `/process-designer/:boardId` 추가. `/settings` 및 SettingsPage 라우트 추가. |
| 0-R6 | 404·에러 페이지 | `NotFoundPage`, `ErrorPage` 컴포넌트 생성. `path="*"`에 NotFoundPage, `errorElement`에 ErrorPage 배치. |
| 0-R7 | 라우트 상수·타입 안전 파라미터 | `lib/routes/routes.ts`에 ROUTES 상수 정의. `lib/routes/params.ts`에 useCaseParams, useDocumentParams, useBoardParams (Zod UUID 검증) 구현. 모든 네비게이션·링크는 ROUTES 사용. |
| 0-R8 | 코드 분할 | 모든 페이지를 `React.lazy()`로 로드. Suspense fallback으로 LoadingSkeleton 사용. (선택) createBrowserRouter 도입. |

#### 3.1.2 디렉토리·공유 구조

| 번호 | 작업 | 상세 |
|------|------|------|
| 0-D1 | 공유 UI 위치 통일 | Shadcn/ui: 설계상 `shared/ui`로 통일할지, 현행 `components/ui` 유지할지 결정. 유지 시 `directory-structure.md`를 현행에 맞게 수정. 통일 시 `components/ui` → `shared/ui` 이전 및 import 일괄 수정. |
| 0-D2 | 공유 컴포넌트 일원화 | `shared/components/`와 `components/shared/` 중 한 곳으로 통일. DataTable, EmptyState 등 이동 후 import 수정. |
| 0-D3 | app 진입점 (선택) | `src/app/` 생성 후 App.tsx, router.tsx, providers.tsx, queryClient.ts 이전. 미적용 시 설계 문서만 현행 구조로 수정. |
| 0-D4 | Feature 모듈 구조 | document-management, process-designer에 대해 `features/document-management/`, `features/process-designer/` 생성. 기존 pages 내 컴포넌트를 feature로 이전하거나, pages는 라우트 페이지만 두고 비즈니스 로직·컴포넌트는 feature로 위임. |

#### 3.1.3 레이아웃·공통 UI

| 번호 | 작업 | 상세 |
|------|------|------|
| 0-L1 | RootLayout | 최상위 레이아웃 컴포넌트 도입. errorElement, Outlet 감싸기. MainLayout을 DashboardLayout과 동일 개념으로 정리. |
| 0-L2 | Sidebar 모듈화 | Sidebar, SidebarNav, SidebarItem을 `layouts/Sidebar/`로 분리. nav 항목은 ROUTES 기반으로 생성. |
| 0-L3 | Header·UserMenu | Header에 NotificationBell, UserMenu(프로필·로그아웃) 통합. MainLayout/DashboardLayout에 Header 배치. |
| 0-L4 | Design Tokens·다크 모드 | CSS 변수(색상, 타이포, 간격) 정의. themeStore 또는 Context로 라이트/다크 전환. 전역 적용 후 주요 페이지 시각 검수. |

#### 3.1.4 인프라

| 번호 | 작업 | 상세 |
|------|------|------|
| 0-I1 | queryClient 전역 옵션 | retry(4xx 미재시도), staleTime, mutation onError에서 AppError.userMessage 토스트 등 구현 가이드 반영. |
| 0-I2 | wsManager·streamManager | WebSocket은 `lib/api/wsManager.ts` 싱글톤으로 표준화. SSE/NDJSON 스트림은 `lib/api/streamManager.ts` (createTextStream, createNdjsonStream) 제공. |
| 0-I3 | 페이지 단위 ErrorBoundary | 각 주요 라우트(또는 레이아웃 구간)를 ErrorBoundary로 감싸고 FallbackComponent로 ErrorFallback 사용. onReset에서 쿼리 무효화 등. |
| 0-I4 | i18n (Phase 0 또는 4) | react-i18next, ko.json/en.json 도입. 사용자 대면 문자열을 t()로 치환. (범위가 크면 Phase 4로 이동 가능) |

### 3.2 Phase 0 통과 조건

- **0-G1 라우트**: 아래 경로가 모두 동작하고, 미인증 시 `/auth/login`으로 리다이렉트된다.  
  `/`, `/auth/login`, `/auth/callback`, `/dashboard`, `/cases`, `/cases/:caseId`, `/cases/:caseId/documents`, `/cases/:caseId/documents/:docId`, `/cases/:caseId/documents/:docId/review`, `/cases/:caseId/scenarios`, `/analysis/olap`, `/analysis/nl2sql`, `/data/ontology`, `/data/datasources`, `/process-designer`, `/process-designer/:boardId`, `/watch`, `/settings`, `*`(404).
- **0-G2 상수·파라미터**: ROUTES 상수가 모든 위 경로를 포함하며, useCaseParams/useDocumentParams/useBoardParams 사용 시 잘못된 UUID가 들어오면 404 또는 에러 화면으로 처리된다.
- **0-G3 404·에러**: 알 수 없는 path 접근 시 NotFoundPage가 렌더되고, ErrorBoundary 발생 시 ErrorPage(또는 ErrorFallback)가 렌더된다.
- **0-G4 레이아웃**: Sidebar·Header·UserMenu·NotificationBell이 보호된 라우트에서 일관되게 노출된다.
- **0-G5 코드 분할**: 최소 5개 이상 페이지가 lazy 로드되며, 해당 라우트 진입 시 별도 청크가 로드된다 (네트워크 탭 또는 번들 분석으로 확인).
- **0-G6 문서**: `apps/canvas/docs/04_frontend/routing.md`, `directory-structure.md`가 현재 라우트·디렉토리와 불일치 없이 반영된다.

---

## 4. Phase 1: P0 기능 (케이스·문서+HITL)

### 4.1 작업 상세

#### 4.1.1 케이스 대시보드

| 번호 | 작업 | 상세 |
|------|------|------|
| 1-C1 | CaseListPage | `/cases` 전용 페이지. CaseTable(DataTable), 정렬·페이지네이션·URL 동기화. |
| 1-C2 | CaseDetailPage | `/cases/:caseId` 전용 페이지. 케이스 기본 정보, 하위 탭/링크(문서, 시나리오). |
| 1-C3 | StatsCard x4 | 전체/진행중/검토중/이번주 마감 통계. useCaseStats 또는 Core API 연동. |
| 1-C4 | CaseFilters | 상태·유형·날짜 범위·검색. URL query와 동기화. |
| 1-C5 | CaseTimeline | 최근 활동 목록. useCaseTimeline 또는 이벤트 API. |
| 1-C6 | CaseDistributionChart | 유형별 분포 PieChart. |
| 1-C7 | DashboardComposer·역할별 패널 | useDashboardConfig(역할→표시 패널 매핑). RoleGreeting, QuickActionsPanel. MyWorkitemsPanel(attorney, staff), ApprovalQueuePanel(manager), AnalyticsQuickPanel(analyst), DataPipelinePanel(engineer), SystemHealthMiniCard(admin, engineer) 중 최소 2종 구현. |
| 1-C8 | 대시보드 = 케이스 요약 | CaseDashboardPage는 StatsCard + CaseTable(요약) + CaseTimeline + 역할별 패널 조합. |

#### 4.1.2 문서 관리 + HITL

| 번호 | 작업 | 상세 |
|------|------|------|
| 1-D1 | 케이스 컨텍스트 문서 라우트 | DocumentListPage를 `/cases/:caseId/documents`에서 사용. DocumentEditorPage는 `/cases/:caseId/documents/:docId`, DocumentReviewPage는 `/cases/:caseId/documents/:docId/review`. |
| 1-D2 | DocumentReviewPage | 리뷰 전용 페이지. Diff 뷰(AI 원본 vs 현재), 인라인 코멘트, 승인/반려/수정요청 버튼. |
| 1-D3 | ReviewPanel·InlineComment | 코멘트 쓰레드, 인라인 앵커(선택). |
| 1-D4 | DocumentDiffViewer | react-diff-viewer-continued 등으로 side-by-side 또는 unified diff. |
| 1-D5 | ApprovalWorkflow | 승인/반려/수정요청 시 API 호출, 낙관적 업데이트, 실패 시 롤백. |
| 1-D6 | 기존 /documents 호환 | 케이스 없이 접근 시 caseId 선택 유도 또는 리다이렉트 `/cases` 정책 명시. |

### 4.2 Phase 1 통과 조건

- **1-G1 케이스 라우트**: `/cases`에서 목록, `/cases/:caseId`에서 상세, `/cases/:caseId/documents`에서 해당 케이스 문서 목록이 표시된다. 목록→상세→문서 목록→문서 편집으로 네비게이션 가능하다.
- **1-G2 대시보드**: `/dashboard`에 StatsCard 4개, CaseTable(또는 요약 테이블), CaseTimeline, 역할별 패널 중 최소 2종이 표시된다. 역할(admin 등)에 따라 표시되는 패널이 다르다(또는 mock 역할로 2종 이상 전환 확인).
- **1-G3 문서 HITL**: 한 케이스의 문서에 대해 "리뷰" 진입 시 Diff 뷰·코멘트·승인/반려/수정요청 중 최소 승인·반려가 동작하고, 상태 전이가 API 또는 mock으로 반영된다.
- **1-G4 API 계약**: 케이스·문서 관련 Core API 호출이 설계(02_api)와 일치하고, 응답 필드 누락/오표시가 0건이다(문서화된 필드 기준).
- **1-G5 E2E**: 로그인 → 대시보드 → 케이스 목록 → 케이스 상세 → 문서 목록 → 문서 편집(또는 리뷰) 시나리오가 Playwright E2E 1개 이상 통과한다.

---

## 5. Phase 2: P1 기능 (NL2SQL·OLAP·Watch·복원력)

### 5.1 작업 상세

#### 5.1.1 NL2SQL

| 번호 | 작업 | 상세 |
|------|------|------|
| 2-N1 | Oracle API·SSE 연동 | mock 제거, Oracle `/text2sql/ask` 또는 `/text2sql/react` (NDJSON) 연동. streamManager 사용. |
| 2-N2 | QueryHistory | 시트/패널로 최근 질의 목록 표시. Oracle history API 연동(있을 경우). |
| 2-N3 | ChatInterface 완성 | 메시지 목록, 스트리밍 표시, SQL 미리보기, 결과 테이블·차트. |

#### 5.1.2 OLAP 피벗

| 번호 | 작업 | 상세 |
|------|------|------|
| 2-O1 | Vision API 연동 | useOlapMock 제거, Vision 큐브/쿼리 API 연동. |
| 2-O2 | DrilldownBreadcrumb | 드릴다운 경로 표시, URL search params 동기화. |
| 2-O3 | ChartSwitcher | Table/Bar/Line/Pie 전환, 데이터 유지. |

#### 5.1.3 Watch 알림

| 번호 | 작업 | 상세 |
|------|------|------|
| 2-W1 | Core WebSocket 연동 | watch 알림 구독. wsManager 사용, 이벤트 타입은 domain contract registry 준수. |
| 2-W2 | AlertRuleEditor | 알림 규칙 CRUD 시트/폼. Core API 연동. |
| 2-W3 | EventTimeline | 이벤트 타임라인 컴포넌트. |
| 2-W4 | 심각도별 토스트 | CRITICAL/HIGH → toast.error/warning(수동 닫힘), MEDIUM 이하 정책 적용. |

#### 5.1.4 복원력 UI

| 번호 | 작업 | 상세 |
|------|------|------|
| 2-R1 | 서비스 상태 배너 | Core/Vision/Oracle 등 헬스 또는 Circuit Breaker 상태에 따른 상단 배너. |
| 2-R2 | Graceful Degradation | API 실패 시 해당 영역만 에러 메시지·재시도 버튼, 전체 화면 붕괴 방지. |

### 5.2 Phase 2 통과 조건

- **2-G1 NL2SQL**: 자연어 질문 입력 → Oracle API 호출 → SQL 미리보기·결과 테이블(또는 차트)이 표시된다. Mock 없이 실 API 또는 통합 테스트용 스텁으로 검증된다.
- **2-G2 OLAP**: 큐브 선택 → 차원/측정값 DnD → 쿼리 실행 → 피벗 테이블·드릴다운·차트 전환이 동작한다. Vision API 연동 시 응답 구조가 문서와 일치한다.
- **2-G3 Watch**: WebSocket 연결 시 알림 이벤트 수신 시 목록/벨 카운트가 갱신된다. AlertRuleEditor로 규칙 1건 생성·수정·삭제가 동작한다.
- **2-G4 복원력**: 백엔드 1개 서비스를 중지했을 때 해당 기능 영역에만 배너 또는 에러 메시지가 표시되고, 다른 영역은 정상 동작한다.
- **2-G5 E2E**: NL2SQL 1건 질의→결과 확인, OLAP 1건 큐브 선택→피벗 확인, Watch 알림 1건 확인 시나리오 중 최소 2개 통과한다.

---

## 6. Phase 3: P2 기능 (데이터소스·프로세스·설정·What-if·온톨로지)

### 6.1 작업 상세

#### 6.1.1 데이터소스 관리

| 번호 | 작업 | 상세 |
|------|------|------|
| 3-DS1 | DatasourcePage·라우트 | `/data/datasources` 페이지. Weaver API 연동. |
| 3-DS2 | DatasourceList·ConnectionForm | 목록, 추가/편집 폼, 연결 테스트 버튼. |
| 3-DS3 | SchemaExplorer·SyncProgress | 메타데이터 트리, 동기화 진행률(SSE 가능 시). |

#### 6.1.2 프로세스 디자이너

| 번호 | 작업 | 상세 |
|------|------|------|
| 3-PD1 | ProcessDesignerListPage | `/process-designer`에서 보드 목록, 생성/삭제. |
| 3-PD2 | ProcessDesignerPage(:boardId) | `/process-designer/:boardId`에서 단일 보드 편집. |
| 3-PD3 | react-konva 캔버스 | ProcessCanvas, CanvasItem, ConnectionLine. 노드 8종 이상, 연결선 4종. |
| 3-PD4 | ProcessPropertyPanel·Minimap | 속성 편집 패널, 미니맵. |
| 3-PD5 | Yjs 협업(선택) | useYjsCollaboration, CollaboratorCursors. |
| 3-PD6 | ConformanceOverlay·VariantList(선택) | Synapse 프로세스 마이닝 결과 오버레이, 변형 목록. |

#### 6.1.3 설정

| 번호 | 작업 | 상세 |
|------|------|------|
| 3-S1 | SettingsPage | `/settings` 기본 페이지. 하위 탭/라우트: /settings/system, /settings/logs, /settings/users, /settings/config 중 최소 2개. |
| 3-S2 | 시스템·사용자·설정 UI | 읽기 전용 또는 편집 가능 폼. Core/백엔드 API 연동 범위는 별도 정의. |

#### 6.1.4 What-if·온톨로지

| 번호 | 작업 | 상세 |
|------|------|------|
| 3-WI1 | ScenarioComparison·Vision API | 시나리오 비교 테이블, Vision What-if API 연동. |
| 3-ON1 | PathHighlighter·프로세스 연동 | 온톨로지 경로 하이라이트, 프로세스 디자이너와 URL 파라미터 연동. |

### 6.2 Phase 3 통과 조건

- **3-G1 데이터소스**: `/data/datasources`에서 데이터소스 목록이 표시되고, 1건 추가·연결 테스트·스키마 탐색(또는 동기화) 중 최소 2가지가 동작한다.
- **3-G2 프로세스 디자이너**: `/process-designer`에서 보드 목록, 보드 생성 후 `/process-designer/:boardId` 진입 시 캔버스에 노드 추가·연결·속성 편집이 가능하다. Synapse API와 연동 시 보드 저장/로드가 동작한다.
- **3-G3 설정**: `/settings` 접근 시 설정 페이지가 렌더되고, 하위 메뉴 2개 이상이 존재한다.
- **3-G4 What-if**: 케이스 컨텍스트(`/cases/:caseId/scenarios`)에서 시나리오 파라미터 조정·분석 실행·결과 요약(또는 토네이도·비교)이 Vision API와 연동된다.
- **3-G5 온톨로지**: 노드 선택·경로 하이라이트 또는 프로세스 디자이너로 이동 중 1가지가 동작한다.

---

## 7. Phase 4: 품질·테스트·문서

### 7.1 작업 상세

| 번호 | 작업 | 상세 |
|------|------|------|
| 4-T1 | 단위·통합 테스트 | Vitest + React Testing Library. 유틸·Zod 스키마·authStore·주요 훅·컴포넌트(필터, 테이블 등) 커버리지 목표 설정(예: 핵심 경로 60% 이상). |
| 4-T2 | E2E 시나리오 정리 | Playwright. 로그인→대시보드→케이스→문서→NL2SQL→OLAP→Watch 중 핵심 5개 이상 시나리오 통과. |
| 4-T3 | 접근성 | 키보드 탐색, 포커스 링, ARIA, 대비율. axe-core 또는 Lighthouse로 Critical/Serious 0건. |
| 4-T4 | 성능 | LCP < 2.5s, CLS < 0.1 목표. 초기 번들 gzip < 200KB 목표(또는 상한 명시). |
| 4-D1 | 문서 동기화 | directory-structure, routing, feature-priority-matrix가 최종 구현과 일치. frontend-design-gap-analysis.md는 "갭 해소 완료" 또는 이행 상태로 갱신. |

### 7.2 Phase 4 통과 조건

- **4-G1 단위/통합**: 위 4-T1 범위에 대해 테스트 스위트가 존재하고, CI에서 0 fail로 통과한다.
- **4-G2 E2E**: 4-T2에 정의한 핵심 시나리오 5개 이상이 Playwright로 통과한다.
- **4-G3 접근성**: axe-core(또는 동등 도구)로 전체 앱 스캔 시 Critical·Serious 이슈 0건이다.
- **4-G4 성능**: Lighthouse(또는 동등) 측정 시 LCP·CLS가 목표 이내이거나, 초기 번들이 목표 이내이다. 목표 미달 시 예외 사유를 문서에 기록한다.
- **4-G5 문서**: 04_frontend 내 routing, directory-structure, feature-priority-matrix가 코드와 불일치 없이 반영되고, 갭 분석 문서가 이행 상태를 반영한다.

---

## 8. 전체 프로그램 통과 조건 (Gate)

다음이 모두 충족되어야 **Canvas 프론트엔드 구현 계획 완료**로 인정한다.

| Gate | 조건 | 검증 방법 |
|------|------|-----------|
| **G-CANVAS-1** | Phase 0 통과 조건(0-G1~0-G6) 충족 | 체크리스트 + 라우트·레이아웃 수동/자동 확인 |
| **G-CANVAS-2** | Phase 1 통과 조건(1-G1~1-G5) 충족 | 체크리스트 + E2E 1개 이상 + API 계약 검증 |
| **G-CANVAS-3** | Phase 2 통과 조건(2-G1~2-G5) 충족 | 체크리스트 + E2E 2개 이상 + 실연동 확인 |
| **G-CANVAS-4** | Phase 3 통과 조건(3-G1~3-G5) 충족 | 체크리스트 + 데이터소스·프로세스·설정·What-if·온톨로지 동작 확인 |
| **G-CANVAS-5** | Phase 4 통과 조건(4-G1~4-G5) 충족 | 테스트·접근성·성능·문서 체크리스트 |
| **G-CANVAS-6** | API 계약 대비 화면 데이터 누락/오표시 0건 | 02_api 문서 대비 수동/자동 검증 |
| **G-CANVAS-7** | Critical 접근성 이슈 0건 | axe-core(또는 동등) 결과 첨부 |
| **G-CANVAS-8** | 주요 사용자 여정 E2E 5개 이상 통과 | Playwright 결과 첨부 |

---

## 9. 부록: 작업 체크리스트 요약

### Phase 0

- [ ] 0-R1 ~ 0-R8 (라우트)
- [ ] 0-D1 ~ 0-D4 (디렉토리)
- [ ] 0-L1 ~ 0-L4 (레이아웃)
- [ ] 0-I1 ~ 0-I4 (인프라)
- [ ] 0-G1 ~ 0-G6 (통과 조건 검증)

### Phase 1

- [ ] 1-C1 ~ 1-C8 (케이스 대시보드)
- [ ] 1-D1 ~ 1-D6 (문서+HITL)
- [ ] 1-G1 ~ 1-G5 (통과 조건 검증)

### Phase 2

- [ ] 2-N1 ~ 2-N3 (NL2SQL)
- [ ] 2-O1 ~ 2-O3 (OLAP)
- [ ] 2-W1 ~ 2-W4 (Watch)
- [ ] 2-R1 ~ 2-R2 (복원력)
- [ ] 2-G1 ~ 2-G5 (통과 조건 검증)

### Phase 3

- [ ] 3-DS1 ~ 3-DS3 (데이터소스)
- [ ] 3-PD1 ~ 3-PD6 (프로세스 디자이너)
- [ ] 3-S1 ~ 3-S2 (설정)
- [ ] 3-WI1, 3-ON1 (What-if·온톨로지)
- [ ] 3-G1 ~ 3-G5 (통과 조건 검증)

### Phase 4

- [ ] 4-T1 ~ 4-T4, 4-D1 (품질·문서)
- [ ] 4-G1 ~ 4-G5 (통과 조건 검증)

### Gate

- [ ] G-CANVAS-1 ~ G-CANVAS-8 (전체 통과 조건 검증)

---

## 10. 변경 이력

| 날짜 | 버전 | 작성자 | 내용 |
|------|------|--------|------|
| 2026-02-22 | 1.0 | Axiom Team | 초기 작성 — Phase 0~4 상세 작업 및 통과 조건, Gate 정의 |
