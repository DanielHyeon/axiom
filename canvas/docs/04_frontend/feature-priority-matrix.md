# Feature 구현 우선순위 매트릭스

<!-- affects: frontend -->
<!-- requires-update: 04_frontend/directory-structure.md, 01_architecture/component-architecture.md -->

## 이 문서가 답하는 질문

- 9개 Feature 모듈의 구현 순서는 어떻게 되는가?
- 각 Feature의 우선순위 근거는 무엇인가?
- Feature 간 의존성 관계는 어떻게 되는가?
- 스프린트별 구현 목표와 체크리스트는 무엇인가?

---

## 1. MVP 기능 우선순위 매트릭스 (Feature Priority Matrix)

### 1.1 우선순위 정의

| 등급 | 의미 | 기준 |
|------|------|------|
| **P0 (MVP)** | 제품 출시에 반드시 필요 | 이것 없이는 사용자가 핵심 업무를 수행할 수 없음 |
| **P1 (Phase 1)** | MVP 직후 확장 | 핵심 가치를 강화하는 분석/알림 기능 |
| **P2 (Phase 2)** | 차별화 기능 | 경쟁 우위를 만드는 고급 기능 |

### 1.2 전체 매트릭스

| 기능 | 사용자 가치 | 비즈니스 가치 | 구현 난이도 | 의존성 | 우선순위 | 근거 |
|------|-----------|-------------|------------|--------|---------|------|
| **인증/인가** | 높음 | 높음 | 중간 | 없음 (기반 인프라) | **P0** | 모든 기능의 전제 조건. 인증 없이는 어떤 페이지도 접근 불가. RBAC이 없으면 데이터 보안 불가. |
| **케이스 대시보드** | 높음 | 높음 | 낮음 | 인증, Core API | **P0** | 사용자가 로그인 후 가장 먼저 보는 화면. 전체 업무 현황을 한눈에 파악하는 진입점. 이 화면이 없으면 사용자가 "무엇을 해야 하는지" 알 수 없음. |
| **문서 관리 + HITL** | 높음 | 높음 | 중간 | 인증, Core API, 케이스 | **P0** | Canvas의 핵심 차별점인 AI+인간 협업(HITL) 워크플로우. 문서 생성 -> 리뷰 -> 승인이 비즈니스 프로세스의 핵심 산출물. K-AIR 대비 가장 큰 개선 포인트. |
| **NL2SQL 대화형 쿼리** | 높음 | 높음 | 중간 | 인증, Oracle API, 데이터소스(최소 1개) | **P1** | 비기술 사용자가 SQL 없이 데이터를 탐색하는 핵심 기능. 다만 MVP에서는 케이스 관리가 더 시급하고, 데이터소스 연결이 선행되어야 동작 가능. |
| **OLAP 피벗 분석** | 중간 | 높음 | 중간 | 인증, Vision API, 데이터소스 | **P1** | 구조화된 데이터 분석의 핵심. NL2SQL과 함께 "분석" 카테고리의 양대 축. DnD 피벗 빌더는 구현 공수가 있으나 @dnd-kit으로 관리 가능. |
| **Watch 알림** | 중간 | 중간 | 낮음 | 인증, Core API (WebSocket) | **P1** | 사용자에게 중요한 이벤트를 능동적으로 알려주는 기능. MVP 없이도 사용은 가능하나, 기한 관리/리뷰 독촉 등 업무 효율에 직결. WebSocket 인프라는 P0에서 이미 구축됨. |
| **복원력 UI** | 중간 | 높음 | 낮음 | 공유 인프라 | **P1** | 서비스 상태 배너, Graceful Degradation UI, Circuit Breaker 상태 반영. Core [resilience-patterns.md](../../../../services/core/docs/01_architecture/resilience-patterns.md) §7 참조 |
| **데이터소스 관리** | 중간 | 높음 | 중간 | 인증, Weaver API | **P2** | NL2SQL/OLAP의 전제 조건이나, 초기에는 기본 데이터소스를 미리 설정하여 P1 기능을 먼저 사용 가능하게 함. 본격적인 다중 데이터소스 관리는 P2. |
| **프로세스 디자이너** | 높음 | 높음 | **높음** | 인증, Synapse API, Yjs, react-konva | **P2** | Canvas의 가장 강력한 기능이지만 구현 난이도가 압도적으로 높음. react-konva 캔버스 + Yjs 실시간 협업 + 프로세스 마이닝 오버레이를 모두 포함. 코어 기능(캔버스+노드)과 확장 기능(협업+마이닝)을 분리하여 2개 스프린트에 걸쳐 구현. |
| **What-if 시나리오** | 중간 | 중간 | 중간 | 인증, Vision API, 케이스 | **P2** | K-AIR에서 미구현이었던 신규 기능. 비즈니스 의사결정 시뮬레이션에 유용하나, 핵심 업무 흐름(케이스+문서+분석) 이후에 추가해도 사용자 가치 손실이 적음. |
| **온톨로지 브라우저** | 낮음 | 중간 | 중간 | 인증, Synapse API, react-force-graph-2d | **P2** | 조직 지식 체계 시각화. 데이터 엔지니어/관리자에게 유용하나 일반 분석가에게는 부차적. 프로세스 디자이너와 연동(상호 네비게이션)되므로 같은 Phase에 배치. |

### 1.3 사용자 가치/비즈니스 가치 기준 설명

**사용자 가치 평가 기준**:
- 높음: 해당 기능 없이는 주요 업무 수행 불가
- 중간: 업무 효율을 크게 높이지만 대안 경로 존재
- 낮음: 특정 역할에만 유용하거나 부가적 가치

**비즈니스 가치 평가 기준**:
- 높음: K-AIR 대비 차별점, 경쟁 우위, 핵심 가치 제안
- 중간: 사용자 만족도/리텐션에 기여
- 낮음: Nice-to-have

**구현 난이도 평가 기준**:
- 낮음: 표준 CRUD + 기존 Shadcn/ui 컴포넌트로 충분 (1~2주)
- 중간: 외부 라이브러리 통합 또는 복잡한 상태 관리 (2~3주)
- 높음: 캔버스/실시간/복합 인터랙션 (3주 이상)

---

## 2. 구현 순서와 의존성 그래프 (Implementation Order & Dependencies)

### 2.1 의존성 그래프

```
                        ┌────────────────────┐
                        │  공유 인프라 (P0)    │
                        │                     │
                        │  - 디자인 시스템     │
                        │  - API 클라이언트    │
                        │  - 상태 관리 기반    │
                        │  - 레이아웃/라우팅   │
                        │  - 인증/인가         │
                        │  - WebSocket 매니저  │
                        └─────────┬───────────┘
                                  │
                    ┌─────────────┼─────────────────┐
                    │             │                  │
                    ▼             ▼                  ▼
            ┌──────────┐  ┌───────────┐    ┌─────────────┐
            │ 케이스     │  │ 케이스    │    │ (WebSocket  │
            │ 대시보드   │  │ 목록/상세 │    │  기반 인프라)│
            │ (P0)      │  │ (P0)     │    │             │
            └──────┬───┘  └────┬──────┘    └──────┬──────┘
                   │           │                   │
                   │     ┌─────┴──────┐            │
                   │     │            │            │
                   │     ▼            │            ▼
                   │  ┌─────────┐    │    ┌──────────────┐
                   │  │ 문서 관리│    │    │ Watch 알림    │
                   │  │ + HITL  │    │    │ (P1)         │
                   │  │ (P0)    │    │    └──────────────┘
                   │  └─────────┘    │
                   │                  │
         ┌─────────┴────────┐        │
         │                  │        │
         ▼                  ▼        ▼
  ┌────────────┐    ┌────────────┐ ┌────────────────┐
  │ NL2SQL     │    │ OLAP 피벗  │ │ 데이터소스 관리 │
  │ (P1)       │    │ (P1)       │ │ (P2)           │
  │            │    │            │ │                 │
  │ Oracle API │    │ Vision API │ │ Weaver API      │
  └────────────┘    └─────┬──────┘ └────────────────┘
                          │
                          ▼
                   ┌─────────────┐
                   │ What-if     │
                   │ 시나리오    │
                   │ (P2)       │
                   │ Vision API  │
                   └─────────────┘

  ┌─────────────────────────────────────────────────┐
  │                프로세스 디자이너 (P2)              │
  │                                                   │
  │  ┌──────────────┐    ┌─────────────────────────┐ │
  │  │ 코어 (Sprint 6)│───▶│ 협업 + 마이닝 (Sprint 7)│ │
  │  │ 캔버스+노드    │    │ Yjs + 오버레이          │ │
  │  │ react-konva   │    │ Synapse API             │ │
  │  └──────────────┘    └─────────┬───────────────┘ │
  │                                 │                  │
  └─────────────────────────────────┼──────────────────┘
                                    │
                                    ▼
                            ┌──────────────┐
                            │ 온톨로지      │
                            │ 브라우저 (P2) │
                            │ (프로세스     │
                            │  디자이너 연동)│
                            │ Synapse API   │
                            └──────────────┘
```

### 2.2 의존성 규칙

| 의존성 유형 | 설명 | 예시 |
|------------|------|------|
| **하드 의존성** | 선행 Feature 없이 구현/동작 불가 | 문서 관리 -> 케이스 (케이스 컨텍스트 필수) |
| **소프트 의존성** | 없어도 동작하나 기능이 제한됨 | NL2SQL -> 데이터소스 (기본 데이터소스로 우회 가능) |
| **인프라 의존성** | 공유 인프라가 선행 | 모든 Feature -> 인증/인가, API 클라이언트 |

**왜 이 순서인가?**:

1. **인증/인가가 최우선인 이유**: 보안 없이 배포할 수 없다. RBAC이 모든 UI 렌더링에 영향을 미치므로 가장 먼저 구현한다.
2. **케이스 대시보드가 P0인 이유**: "로그인 후 무엇을 보여줄 것인가?"에 대한 답이다. 사용자의 첫 경험을 결정한다.
3. **문서 관리+HITL이 P0인 이유**: Canvas의 핵심 가치 제안(AI+인간 협업)이 여기서 구현된다. MVP에서 이 기능이 빠지면 "K-AIR와 뭐가 다른가?"에 답할 수 없다.
4. **프로세스 디자이너가 P2인 이유**: 가장 강력한 기능이지만 구현 난이도가 높고, react-konva + Yjs + 프로세스 마이닝 3가지를 결합해야 한다. 핵심 업무 흐름(케이스+문서+분석)이 안정된 후에 투자하는 것이 리스크 관리 측면에서 합리적이다.

---

## 3. 각 Feature의 구현 체크리스트 (Implementation Checklist per Feature)

### 3.1 공유 인프라 (Shared Infrastructure)

- [ ] 디자인 시스템 (Shadcn/ui 컴포넌트 설치 및 커스터마이징)
- [ ] Design Tokens (CSS 변수, 다크 모드)
- [ ] 레이아웃 (RootLayout, DashboardLayout, AuthLayout, Sidebar)
- [ ] React Router v6 라우트 정의 + AuthGuard + RoleGuard
- [ ] API 클라이언트 (createApiClient, 인터셉터, 토큰 갱신)
- [ ] Zustand 전역 스토어 (authStore, uiStore, themeStore)
- [ ] TanStack Query 설정 (QueryClient, 기본 옵션)
- [ ] WebSocket 매니저 (wsManager)
- [ ] i18n 설정 (ko/en)
- [ ] 공용 컴포넌트 (DataTable, StatusBadge, EmptyState, LoadingSkeleton)
- [ ] 에러 바운더리 (ErrorPage, NotFoundPage)
- [ ] Toast 시스템 (sonner 또는 자체 구현)
- [ ] 반응형 디자인 (모바일/태블릿/데스크톱/와이드)
- [ ] 다크 모드 전체 적용
- [ ] 접근성 기본 검증 (키보드 탐색, ARIA 속성)
- [ ] 단위 테스트 환경 (Vitest + Testing Library)
- [ ] E2E 테스트 환경 (Playwright)

### 3.2 인증/인가 (Auth)

- [ ] 디렉토리 구조 생성 (`features/auth/`)
- [ ] TypeScript 타입 정의 (User, LoginCredentials, AccessTokenPayload, UserRole)
- [ ] API 클라이언트 함수 (login, logout, refreshToken, getMe)
- [ ] Zustand authStore (user, tokens, login, logout, refreshAccessToken)
- [ ] LoginPage 컴포넌트 구현
- [ ] CallbackPage (OAuth 콜백, 필요 시)
- [ ] AuthGuard 컴포넌트
- [ ] RoleGuard 컴포넌트
- [ ] usePermission, useRole 훅
- [ ] 사이드바 메뉴 권한 필터링
- [ ] 토큰 자동 갱신 (인터셉터)
- [ ] 로그아웃 시 상태 전체 클리어
- [ ] 반응형 디자인
- [ ] 다크 모드 대응
- [ ] 접근성 검증 (로그인 폼 키보드 탐색)
- [ ] 단위 테스트 (authStore, token 갱신 로직)
- [ ] 통합 테스트 (로그인 -> 대시보드 이동)
- [ ] E2E 시나리오 (로그인 -> 세션 만료 -> 자동 갱신)

### 3.3 케이스 대시보드 (Case Dashboard)

- [ ] 디렉토리 구조 생성 (`features/case-dashboard/`)
- [ ] TypeScript 타입 정의 (Case, CaseStatus, CaseFilters, CaseStats)
- [ ] API 클라이언트 함수 (getCases, getCaseStats, getCaseTimeline)
- [ ] TanStack Query hooks (useCases, useCaseStats, useCaseTimeline)
- [ ] CaseDashboardPage 컴포넌트
- [ ] StatsCard (x4)
- [ ] CaseFilters (검색 + 필터 + URL 동기화)
- [ ] CaseTable (DataTable + 정렬 + 페이지네이션)
- [ ] CaseTimeline
- [ ] CaseDistributionChart (Recharts PieChart)
- [ ] WebSocket 연동 (case:updated -> 쿼리 무효화)
- [ ] **역할별 대시보드 합성** (`case-dashboard.md` §4 참조):
  - [ ] `useDashboardConfig` 훅 (역할 → 패널 매핑, 순수 프론트엔드 로직)
  - [ ] `DashboardComposer` 컴포넌트 (역할별 조건부 패널 렌더링)
  - [ ] `RoleGreeting` 컴포넌트 (역할별 인사 + 업무 요약)
  - [ ] `QuickActionsPanel` 컴포넌트 (역할별 바로가기 카드)
  - [ ] `MyWorkitemsPanel` (attorney, staff — `useMyWorkitems` 훅)
  - [ ] `ApprovalQueuePanel` (manager — `useApprovalQueue` 훅)
  - [ ] `SystemHealthMiniCard` (admin, engineer — 기존 `useSystemHealth` 재사용)
  - [ ] `DataPipelinePanel` (engineer — `useDatasourceStatus` 훅)
  - [ ] `AnalyticsQuickPanel` (analyst — `useRecentQueries` 훅)
- [ ] 빈 상태 (Empty State) 디자인
- [ ] 반응형 디자인
- [ ] 다크 모드 대응
- [ ] 접근성 검증
- [ ] 단위 테스트
- [ ] 통합 테스트
- [ ] E2E 시나리오 (필터 -> 정렬 -> 페이지 이동 -> 상세 진입 -> 복귀)
- [ ] E2E 시나리오 (역할별 로그인 -> 패널 표시 확인 -> QuickAction 네비게이션)

### 3.4 문서 관리 + HITL (Document Management)

- [ ] 디렉토리 구조 생성 (`features/document-management/`)
- [ ] TypeScript 타입 정의 (Document, DocumentStatus, ReviewComment, DiffResult)
- [ ] API 클라이언트 함수 (getDocuments, getDocument, updateDocument, approve, reject, requestChanges, addComment)
- [ ] TanStack Query hooks (useDocuments, useDocument, useDocumentComments)
- [ ] useMutation hooks (useApproveDocument, useRejectDocument, useAddComment)
- [ ] DocumentListPage 컴포넌트
- [ ] DocumentEditorPage (Monaco Editor 통합)
- [ ] ReviewPanel (인라인 코멘트, 쓰레드)
- [ ] DocumentDiffViewer (react-diff-viewer-continued)
- [ ] ApprovalWorkflow (승인/반려/수정요청 버튼 + AlertDialog)
- [ ] AiGeneratedBadge (AI 생성 문서 표시)
- [ ] 낙관적 업데이트 (승인/반려 시 즉시 UI 반영)
- [ ] HITL 워크플로우 상태 전이 (draft -> in_review -> approved/rejected)
- [ ] 빈 상태 (Empty State) 디자인
- [ ] 반응형 디자인
- [ ] 다크 모드 대응
- [ ] 접근성 검증
- [ ] 단위 테스트
- [ ] 통합 테스트
- [ ] E2E 시나리오 (AI 생성 -> 리뷰 -> 코멘트 -> 승인)

### 3.5 NL2SQL 대화형 쿼리

- [ ] 디렉토리 구조 생성 (`features/nl2sql/`)
- [ ] TypeScript 타입 정의 (Nl2SqlState, ChatMessage, ChartType)
- [ ] SSE 연결 함수 (Oracle API nl2sql/ask)
- [ ] useNl2sql 훅 (SSE 스트리밍 상태 관리)
- [ ] Nl2SqlPage 컴포넌트
- [ ] ChatInterface (대화 영역)
- [ ] MessageBubble (사용자/AI 메시지)
- [ ] ThinkingIndicator (스트리밍 표시)
- [ ] SqlPreview (구문 강조 + 복사/수정 버튼)
- [ ] ResultTable (TanStack Table)
- [ ] ChartRecommender (자동 차트 추천)
- [ ] ChatInput (데이터소스 선택 + 입력 + 전송)
- [ ] QueryHistory (Sheet 패널)
- [ ] 대화 컨텍스트 관리 (이전 SQL 전달)
- [ ] 빈 상태 (예시 질문 표시)
- [ ] 반응형 디자인
- [ ] 다크 모드 대응
- [ ] 접근성 검증
- [ ] 단위 테스트
- [ ] 통합 테스트
- [ ] E2E 시나리오 (질문 -> SQL 생성 -> 결과 -> 차트 전환 -> 후속 질문)

### 3.6 OLAP 피벗 분석

- [ ] 디렉토리 구조 생성 (`features/olap-pivot/`)
- [ ] TypeScript 타입 정의 (PivotConfig, Dimension, Measure, OlapFilter, DrilldownStep)
- [ ] API 클라이언트 함수 (getCubes, queryCube)
- [ ] TanStack Query hooks (useCubes, useOlapQuery)
- [ ] Zustand pivotConfigStore
- [ ] OlapPivotPage 컴포넌트
- [ ] CubeSelector
- [ ] DimensionPalette + DraggableDimension/Measure (@dnd-kit)
- [ ] PivotBuilder + DroppableZone (행/열/측정값/필터)
- [ ] PivotTable + PivotGrid (드릴다운 지원)
- [ ] DrilldownBreadcrumb
- [ ] ChartSwitcher (Bar/Line/Pie 전환)
- [ ] ExportButton (CSV)
- [ ] DnD 접근성 (키보드 DnD)
- [ ] 드릴다운 경로 URL search params 동기화
- [ ] 빈 상태 (Empty State) 디자인
- [ ] 반응형 디자인
- [ ] 다크 모드 대응
- [ ] 접근성 검증
- [ ] 단위 테스트
- [ ] 통합 테스트
- [ ] E2E 시나리오 (큐브 선택 -> DnD -> 쿼리 실행 -> 드릴다운 -> 차트 전환)

### 3.7 Watch 알림

- [ ] 디렉토리 구조 생성 (`features/watch-alerts/`)
- [ ] TypeScript 타입 정의 (Alert, AlertSeverity, AlertRule, RuleCondition)
- [ ] API 클라이언트 함수 (getAlerts, markAsRead, getRules, createRule, updateRule)
- [ ] TanStack Query hooks (useAlerts, useAlertRules)
- [ ] WebSocket 연동 (alert:new -> 캐시 직접 추가 + 토스트)
- [ ] WatchDashboardPage 컴포넌트
- [ ] AlertStats (통계 카드)
- [ ] PriorityFilter
- [ ] AlertFeed + AlertCard
- [ ] EventTimeline
- [ ] AlertRuleEditor (Sheet)
- [ ] 알림 벨 카운터 (uiStore.unreadAlertCount)
- [ ] **Notification Center** (`watch-alerts.md` §7 참조):
  - [ ] `NotificationBell` 컴포넌트 (Shadcn Popover + 최근 5건 드롭다운)
  - [ ] `useNotificationBell` 훅 (최근 알림 + unread 카운트 + WebSocket)
  - [ ] 알림 항목 클릭 → `action_url` 이동 + 읽음 처리 (`PUT /alerts/{id}/acknowledge`)
  - [ ] "전체 읽음" 버튼 → `PUT /api/v1/watches/alerts/read-all`
  - [ ] "모든 알림 보기" → `/watch` 네비게이션
- [ ] **역할별 기본 구독** (`watch-alerts.md` §8 참조):
  - [ ] 사용자 생성 시 역할별 기본 구독 자동 시드 (백엔드 연동)
  - [ ] 알림 규칙 설정에서 기본 구독 수정/삭제 가능
- [ ] **심각도별 토스트 규칙** (`ux-interaction-patterns.md` §2.3 참조):
  - [ ] CRITICAL/HIGH → toast.error/warning (수동 닫힘)
  - [ ] MEDIUM → toast.warning (5초 자동)
  - [ ] LOW/INFO → 토스트 없음 (벨 카운터만)
- [ ] 빈 상태 (Empty State) 디자인
- [ ] 반응형 디자인
- [ ] 다크 모드 대응
- [ ] 접근성 검증
- [ ] 단위 테스트
- [ ] 통합 테스트
- [ ] E2E 시나리오 (알림 수신 -> 읽음 처리 -> 규칙 생성)
- [ ] E2E 시나리오 (벨 클릭 -> 드롭다운 확인 -> 항목 클릭 -> 상세 이동 -> 읽음 확인)

### 3.8 데이터소스 관리

- [ ] 디렉토리 구조 생성 (`features/datasource-manager/`)
- [ ] TypeScript 타입 정의 (Datasource, DatasourceType, SyncProgress, SchemaMetadata)
- [ ] API 클라이언트 함수 (getDatasources, createDatasource, testConnection, syncMetadata)
- [ ] TanStack Query hooks (useDatasources, useDatasource)
- [ ] SSE 연결 함수 (메타데이터 동기화 진행률)
- [ ] DatasourcePage 컴포넌트
- [ ] DatasourceList + DatasourceCard
- [ ] ConnectionForm (Dialog)
- [ ] TestConnectionButton
- [ ] SchemaExplorer (트리 뷰)
- [ ] SyncProgress (프로그레스 바)
- [ ] 빈 상태 (Empty State) 디자인
- [ ] 반응형 디자인
- [ ] 다크 모드 대응
- [ ] 접근성 검증
- [ ] 단위 테스트
- [ ] 통합 테스트
- [ ] E2E 시나리오 (데이터소스 추가 -> 연결 테스트 -> 동기화 -> 스키마 탐색)

### 3.9 프로세스 디자이너

- [ ] 디렉토리 구조 생성 (`features/process-designer/`)
- [ ] TypeScript 타입 정의 (CanvasItem, CanvasItemType, Connection, ConnectionType, BoardState)
- [ ] API 클라이언트 함수 (getBoards, getBoard, createBoard)
- [ ] TanStack Query hooks (useBoards, useBoard, useProcessMining)
- [ ] Zustand processDesignerStore
- [ ] Yjs 연동 (useYjsCollaboration 훅)
- [ ] ProcessDesignerListPage
- [ ] ProcessDesignerPage (메인 캔버스)
- [ ] ProcessToolbox (노드 팔레트)
- [ ] ProcessCanvas (react-konva Stage + Layer)
- [ ] CanvasItem (노드 렌더링, 8+3종)
- [ ] ConnectionLine (연결선 4종)
- [ ] ProcessPropertyPanel (속성 편집: 기본, 시간축, 측정값, 로그 바인딩)
- [ ] ProcessMinimap
- [ ] 키보드 단축키 (useCanvasKeyboard)
- [ ] Undo/Redo (Yjs UndoManager)
- [ ] CollaboratorCursors (Yjs Awareness)
- [ ] ConformanceOverlay (프로세스 마이닝 결과)
- [ ] ProcessVariantPanel (변형 목록)
- [ ] AI 역공학 (이벤트 로그 -> 프로세스 모델 자동 생성)
- [ ] 뷰포트 컬링 (노드 100개 이상)
- [ ] 빈 상태 (Empty State) 디자인
- [ ] 반응형 디자인 (최소 1024px, 캔버스 기능은 데스크톱 전용)
- [ ] 다크 모드 대응
- [ ] 접근성 검증 (키보드 단축키 충돌 검사)
- [ ] 단위 테스트 (스토어, 타입 변환)
- [ ] 통합 테스트 (Yjs 동기화, 캔버스 인터랙션)
- [ ] E2E 시나리오 (보드 생성 -> 노드 추가 -> 연결 -> 마이닝 오버레이)

### 3.10 What-if 시나리오 빌더

- [ ] 디렉토리 구조 생성 (`features/what-if-builder/`)
- [ ] TypeScript 타입 정의 (Scenario, Parameter, SensitivityData, SimulationResult)
- [ ] API 클라이언트 함수 (getScenarios, getParameters, analyzeScenario, saveScenario)
- [ ] TanStack Query hooks (useScenarios, useScenarioParameters)
- [ ] WhatIfPage 컴포넌트
- [ ] ScenarioPanel + ParameterSlider (디바운스 300ms)
- [ ] ResultSummary (결과 카드)
- [ ] TornadoChart (Recharts 가로 BarChart 커스텀)
- [ ] ScenarioComparison (DataTable)
- [ ] 빈 상태 (Empty State) 디자인
- [ ] 반응형 디자인
- [ ] 다크 모드 대응
- [ ] 접근성 검증 (슬라이더 키보드 조작)
- [ ] 단위 테스트
- [ ] 통합 테스트
- [ ] E2E 시나리오 (슬라이더 조정 -> 분석 실행 -> 시나리오 저장 -> 비교)

### 3.11 온톨로지 브라우저

- [ ] 디렉토리 구조 생성 (`features/ontology-browser/`)
- [ ] TypeScript 타입 정의 (OntologyNode, OntologyEdge, OntologyLayer, PathResult)
- [ ] API 클라이언트 함수 (getOntologyGraph, getOntologyNode, findPaths)
- [ ] TanStack Query hooks (useOntologyGraph, useOntologyNode, useOntologyPaths)
- [ ] OntologyPage 컴포넌트
- [ ] SearchPanel (디바운스 검색 + 자동완성)
- [ ] LayerFilter (4계층 체크박스)
- [ ] DepthSelector
- [ ] GraphViewer (react-force-graph-2d)
- [ ] NodeDetail (속성, 연결, 프로세스 디자이너 연동)
- [ ] PathHighlighter (경로 탐색)
- [ ] 프로세스 디자이너 상호 네비게이션 (URL 파라미터)
- [ ] 빈 상태 (Empty State) 디자인
- [ ] 반응형 디자인
- [ ] 다크 모드 대응
- [ ] 접근성 검증
- [ ] 단위 테스트
- [ ] 통합 테스트
- [ ] E2E 시나리오 (검색 -> 필터 -> 노드 클릭 -> 경로 탐색 -> 프로세스 디자이너 이동)

---

## 4. 스프린트 목표 예시 (Sprint Goal Examples)

각 스프린트는 2주 단위를 가정한다. 실제 팀 규모와 속도에 따라 조정한다.

### Sprint 1: 인프라 + 인증 + 레이아웃

**목표**: "사용자가 로그인하여 빈 대시보드를 볼 수 있다."

| 항목 | 상세 | 완료 기준 |
|------|------|----------|
| 프로젝트 초기 설정 | Vite + React 18 + TypeScript, 디렉토리 구조 | 빌드 성공 |
| 디자인 시스템 | Shadcn/ui 설치, Design Tokens, Pretendard 폰트, 다크 모드 토글 | 라이트/다크 전환 동작 |
| 레이아웃 | DashboardLayout (사이드바 + 헤더 + 콘텐츠), AuthLayout | 반응형 확인 |
| 라우팅 | React Router v6 전체 라우트 정의, lazy loading | 404 페이지 동작 |
| 인증 | LoginPage, authStore, JWT 인터셉터, AuthGuard, RoleGuard | 로그인 -> 대시보드 이동 |
| API 클라이언트 | createApiClient, 토큰 갱신 인터셉터 | 401 자동 갱신 |
| WebSocket | wsManager 기본 연결/해제 | 연결 로그 확인 |
| 공용 컴포넌트 | LoadingSkeleton, EmptyState, Toast 시스템 | 스토리북 또는 수동 확인 |

**왜 Sprint 1에 인프라를 몰아넣는가?**: 모든 Feature가 공유 인프라에 의존한다. 이것이 불안정하면 이후 모든 스프린트에서 반복적인 기반 작업이 발생하여 속도가 나지 않는다.

---

### Sprint 2: 케이스 대시보드

**목표**: "각 역할의 사용자가 로그인 후 자신의 업무에 맞는 대시보드를 보고, 원하는 케이스를 찾아 상세 페이지로 진입할 수 있다."

| 항목 | 상세 | 완료 기준 |
|------|------|----------|
| 케이스 API 연동 | useCases, useCaseStats, useCaseTimeline | API 호출 성공 |
| 통계 카드 | StatsCard x4 (전체, 진행중, 검토중, 이번주 마감) | 실시간 데이터 표시 |
| 케이스 테이블 | DataTable + 필터 + 정렬 + 페이지네이션 | URL 동기화 |
| 케이스 상세 | CaseDetailPage (기본 정보 표시) | 목록 -> 상세 네비게이션 |
| 차트 | PieChart (유형별 분포) | 다크 모드 대응 |
| 타임라인 | CaseTimeline (최근 활동) | WebSocket 연동 |
| **역할별 합성** | DashboardComposer, useDashboardConfig, QuickActionsPanel | 7개 역할별 패널 확인 |
| **역할별 전용 패널** | MyWorkitems, ApprovalQueue, DataPipeline, Analytics, SystemHealth | 역할 로그인 시 해당 패널만 표시 |
| 빈 상태 | 케이스 없음 상태 | CTA 버튼 동작 |

---

### Sprint 3: 문서 관리 + HITL

**목표**: "담당자가 AI로 문서 초안을 생성하고, 검토자가 인라인 코멘트를 달아 리뷰하며, 승인자가 최종 승인할 수 있다."

| 항목 | 상세 | 완료 기준 |
|------|------|----------|
| 문서 목록 | DocumentListPage (AI/수동 구분 표시) | 목록 표시 + 필터 |
| 문서 편집기 | Monaco Editor 통합 (Markdown 지원) | 편집 + 저장 동작 |
| HITL 리뷰 | ReviewPanel, InlineComment, CommentThread | 코멘트 추가/해결 |
| Diff 뷰어 | AI 원본 vs 현재 버전 비교 | Side-by-side 표시 |
| 승인 워크플로우 | 승인/반려/수정요청 버튼 + AlertDialog | 상태 전이 동작 |
| 낙관적 업데이트 | 승인 시 즉시 UI 반영, 실패 시 롤백 | 네트워크 지연에도 즉시 반영 |

**왜 HITL이 MVP인가?**: AI 생성 + 인간 검토는 Canvas의 핵심 가치 제안이다. 단순 CRUD 문서 관리는 차별점이 없다. HITL 워크플로우(AI 초안 -> Diff -> 인라인 코멘트 -> 승인)가 있어야 "K-AIR와 다르다"는 것을 증명할 수 있다.

---

### Sprint 4: NL2SQL + OLAP

**목표**: "분석가가 자연어로 데이터를 질문하고, 피벗 테이블로 다차원 분석을 수행할 수 있다."

| 항목 | 상세 | 완료 기준 |
|------|------|----------|
| NL2SQL 채팅 | ChatInterface, SSE 스트리밍, SQL 미리보기 | 질문 -> SQL -> 결과 흐름 |
| 차트 추천 | ChartRecommender (Bar/Line/Pie 자동 선택) | 추천 차트 렌더링 |
| 대화 컨텍스트 | 후속 질문 시 이전 SQL 컨텍스트 전달 | 대화형 정제 동작 |
| OLAP 피벗 | PivotBuilder + DnD 팔레트 (@dnd-kit) | DnD 동작 + 접근성 |
| 드릴다운 | PivotGrid 셀 클릭 -> 하위 차원 탐색 | Breadcrumb + URL 동기화 |
| 차트 전환 | ChartSwitcher (Table/Bar/Line/Pie) | 전환 시 데이터 유지 |

---

### Sprint 5: Watch + 데이터소스

**목표**: "관리자가 데이터소스를 연결하고, 각 역할의 사용자가 자신에게 관련된 실시간 알림을 수신하여 기한 관리를 할 수 있다."

| 항목 | 상세 | 완료 기준 |
|------|------|----------|
| Watch 대시보드 | AlertFeed, EventTimeline, AlertStats | 알림 목록 표시 |
| 실시간 알림 | WebSocket -> TanStack Query 캐시 직접 주입 + 심각도별 토스트 | CRITICAL/HIGH는 수동 닫힘, LOW/INFO는 벨만 |
| 알림 규칙 | AlertRuleEditor (Sheet), 조건/대상/채널 설정 | 규칙 CRUD |
| **Notification Center** | NotificationBell Popover, 최근 5건 드롭다운, 전체 읽음 | 벨 클릭 → 드롭다운 → 항목 클릭 → 이동 |
| **역할별 기본 구독** | 사용자 생성 시 역할별 자동 시드, 규칙 설정에서 수정 가능 | 7개 역할별 기본 구독 생성 확인 |
| 데이터소스 목록 | DatasourceCard, 상태 표시 (연결/동기화중/오류) | 목록 표시 |
| 연결 폼 | ConnectionForm + TestConnectionButton | 연결 테스트 성공 |
| 메타데이터 동기화 | SSE 프로그레스 바 | 진행률 표시 + 완료 토스트 |
| 스키마 탐색기 | MetadataTree (Lazy 로딩) | 테이블/컬럼 트리 표시 |

---

### Sprint 6: 프로세스 디자이너 (코어)

**목표**: "사용자가 캔버스에서 비즈니스 프로세스 노드를 생성하고, 연결하고, 속성을 편집할 수 있다."

| 항목 | 상세 | 완료 기준 |
|------|------|----------|
| 보드 관리 | ProcessDesignerListPage, 보드 생성/삭제 | 목록 + CRUD |
| 캔버스 렌더링 | react-konva Stage + Layer, CanvasItem (11종 노드) | 노드 표시 |
| 노드 추가 | ProcessToolbox + 키보드 단축키 (B/E/N/R/S/T/M/D) | 툴박스/단축키로 노드 생성 |
| 노드 이동/선택 | 드래그 이동, 단일/다중 선택, 키보드 이동 | 선택 + 이동 동작 |
| 연결선 | ConnectionLine (4종), C키로 연결 모드 | 연결 생성/삭제 |
| 속성 패널 | ProcessPropertyPanel (기본, 시간축, 측정값, 로그 바인딩) | 속성 편집 + 저장 |
| 미니맵 | ProcessMinimap | 현재 뷰포트 표시 |
| 줌/패닝 | Ctrl+스크롤, Space+드래그 | 줌 범위 25%~400% |
| Undo/Redo | Yjs UndoManager | Ctrl+Z/Ctrl+Shift+Z |

**왜 코어와 협업을 분리하는가?**: 캔버스 인터랙션만으로도 1개 스프린트 분량이다. 여기에 Yjs 실시간 협업과 프로세스 마이닝 오버레이까지 넣으면 스프린트가 실패할 위험이 높다. 코어를 안정화한 후 확장하는 것이 리스크가 낮다.

---

### Sprint 7: 프로세스 디자이너 (협업 + 마이닝)

**목표**: "여러 사용자가 동시에 프로세스 모델을 편집하고, 프로세스 마이닝 결과를 캔버스 위에 오버레이할 수 있다."

| 항목 | 상세 | 완료 기준 |
|------|------|----------|
| Yjs 협업 | useYjsCollaboration, Y.Map 동기화, 오프라인 지원 | 2인 이상 동시 편집 |
| 커서 공유 | CollaboratorCursors (Awareness 프로토콜) | 다른 사용자 커서 표시 |
| 소프트 잠금 | 편집 중인 노드 시각적 표시 | 동시 편집 힌트 |
| 프로세스 마이닝 | useProcessMining (적합도/병목/이탈) | 결과 데이터 조회 |
| 오버레이 | ConformanceOverlay (빈도, 시간, 병목, 이탈 경로) | 단계별 오버레이 전환 |
| 변형 패널 | ProcessVariantPanel (변형 목록 + 적합도 점수) | 변형 선택 -> 하이라이트 |
| AI 역공학 | 이벤트 로그 -> 프로세스 모델 자동 생성 (HITL) | 자동 생성 + 수동 보완 |
| 성능 최적화 | 뷰포트 컬링, LOD (노드 100개 이상) | 200노드에서 30fps 이상 |

---

### Sprint 8: What-if + 온톨로지

**목표**: "분석가가 시나리오를 시뮬레이션하고, 데이터 엔지니어가 온톨로지 그래프를 탐색할 수 있다."

| 항목 | 상세 | 완료 기준 |
|------|------|----------|
| What-if 슬라이더 | ParameterSlider (디바운스), ResetButton | 슬라이더 조작 |
| 분석 실행 | POST /scenarios/analyze, ResultSummary | 결과 표시 |
| 토네이도 차트 | Recharts 가로 BarChart 커스텀 | 민감도 시각화 |
| 시나리오 비교 | ScenarioComparison 테이블 | 복수 시나리오 열 비교 |
| 온톨로지 그래프 | react-force-graph-2d, 노드/엣지 시각 인코딩 | 그래프 렌더링 |
| 계층 필터 | LayerFilter (KPI/Measure/Process/Resource) | 필터 -> 그래프 재계산 |
| 노드 상세 | NodeDetail + 연결 목록 | 클릭 -> 상세 표시 |
| 경로 탐색 | PathHighlighter (최단 경로 하이라이트) | 2개 노드 선택 -> 경로 |
| 프로세스 디자이너 연동 | 상호 네비게이션 (URL 파라미터) | 양방향 이동 |

---

### Sprint 9-10: 통합 테스트 + 성능 최적화

**목표**: "전체 Feature가 통합 환경에서 안정적으로 동작하고, 성능 기준을 충족한다."

| 항목 | 상세 | 완료 기준 |
|------|------|----------|
| E2E 테스트 전체 | 로그인 -> 대시보드 -> 케이스 -> 문서 -> 분석 -> 프로세스 | 주요 시나리오 통과 |
| 크로스 브라우저 | Chrome, Firefox, Safari, Edge | 주요 기능 동작 |
| 성능 프로파일링 | Lighthouse, Web Vitals (LCP, FID, CLS) | LCP < 2.5s, CLS < 0.1 |
| 번들 최적화 | 코드 분할 확인, 불필요 의존성 제거 | 초기 번들 < 200KB (gzipped) |
| 접근성 감사 | axe-core 전체 스캔 | Critical/Serious 0건 |
| 다크 모드 전체 검수 | 모든 페이지 다크 모드 시각 확인 | 하드코딩 색상 0건 |
| 반응형 전체 검수 | 모바일/태블릿/데스크톱 전 화면 | 레이아웃 깨짐 0건 |
| 실시간 기능 통합 | WebSocket + Yjs 동시 동작 확인 | 연결 안정성 |
| 에러 시나리오 | 네트워크 끊김, API 오류, 권한 없음 | 에러 바운더리 동작 |
| 문서화 최종 점검 | 코드 <-> 문서 정합성 확인 | 불일치 0건 |

**왜 2개 스프린트인가?**: 9개 Feature의 통합 테스트, 성능 최적화, 접근성 감사를 1개 스프린트에 넣으면 품질이 희생된다. 충분한 검증 시간을 확보하는 것이 출시 후 긴급 대응 비용보다 저렴하다.

---

## 결정 사항 (Decisions)

- **P0 = 인증 + 케이스 대시보드 + 문서 관리(HITL)**
  - 근거: "로그인 -> 현황 파악 -> AI+인간 협업 문서 작업"이 Canvas의 최소 가치 루프(value loop)이다. 이 루프가 동작하면 나머지는 확장이다.

- **프로세스 디자이너는 P2이지만 2개 스프린트 할당**
  - 근거: 구현 난이도가 높아 1개 스프린트에 넣으면 실패 확률이 높음. 코어(캔버스+노드)와 확장(협업+마이닝)으로 분리.
  - 재평가: 비즈니스 요구에 따라 P1으로 당길 수 있으나, 분석 기능(NL2SQL+OLAP)보다 우선시하기는 어려움.

- **데이터소스 관리가 P2인 이유**
  - 근거: 초기 MVP/P1 단계에서는 관리자가 직접 기본 데이터소스를 설정(seed data)하여 NL2SQL/OLAP이 동작하게 할 수 있음. 사용자 셀프서비스 데이터소스 관리는 P2에서 충분.

- **통합 테스트에 2개 스프린트 할당**
  - 근거: 9개 Feature의 품질 검증을 서두르면 출시 후 긴급 대응 비용이 더 큼.

---

## 금지됨 (Forbidden)

- 공유 인프라(인증, API 클라이언트, 디자인 시스템) 완성 전에 Feature 구현 착수
- 우선순위 근거 없이 Feature 순서 변경 (변경 시 이 문서에 근거 기록 필수)
- 체크리스트의 "접근성 검증" 항목을 "시간 부족"으로 생략
- 스프린트 범위에 포함되지 않은 Feature의 부분 구현 (스코프 크리프 방지)
- 테스트 코드 없이 Feature 완료 선언

---

## 필수 (Required)

- 모든 Feature는 체크리스트 항목을 100% 완료해야 "완료" 상태
- 각 스프린트 시작 시 이 문서의 체크리스트를 기반으로 Sprint Backlog 생성
- 우선순위 변경 시 이 문서를 먼저 업데이트하고, 변경 근거를 명시
- Feature 구현 시 반드시 빈 상태(Empty State), 다크 모드, 접근성 포함
- 스프린트 리뷰에서 이 문서의 진행률을 확인하여 전체 프로젝트 상태 추적

---

## 변경 이력

| 날짜 | 버전 | 작성자 | 내용 |
|------|------|--------|------|
| 2026-02-20 | 1.2 | Axiom Team | Sprint 5 Watch 알림 체크리스트 보강 (NotificationBell, 역할별 기본 구독, 심각도별 토스트, E2E 시나리오 추가) |
| 2026-02-20 | 1.1 | Axiom Team | Sprint 2 역할별 대시보드 합성 체크리스트 추가 (DashboardComposer, 역할별 패널, E2E 시나리오) |
| 2026-02-20 | 1.0 | Axiom Team | 초기 작성 |
