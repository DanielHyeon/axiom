# 케이스 대시보드 UI 설계

<!-- affects: frontend, api -->
<!-- requires-update: 02_api/api-contracts.md (Core API) -->

## 이 문서가 답하는 질문

- 케이스 대시보드의 화면 구성은 어떻게 되는가?
- 어떤 데이터를 어디에 표시하는가?
- 사용자 인터랙션 흐름은 어떻게 되는가?
- **역할별로 대시보드 구성은 어떻게 달라지는가?**
- **각 역할의 QuickActions와 전용 패널은 무엇인가?**
- K-AIR Dashboard.vue에서 무엇이 달라지는가?

---

## 1. 화면 와이어프레임

```
┌──────────────────────────────────────────────────────────────────────┐
│  Header: Axiom Canvas         🔔 3   👤 김분석가                     │
├──────────┬───────────────────────────────────────────────────────────┤
│          │                                                           │
│ Sidebar  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐       │
│          │  │ 전체     │ │ 진행중   │ │ 검토중   │ │ 이번주   │       │
│ ● 대시보드│  │ 케이스   │ │ 케이스   │ │ 문서     │ │ 마감     │       │
│ ○ 케이스 │  │   142    │ │    38    │ │    15    │ │     7    │       │
│ ○ 분석   │  │ ▲ 12%   │ │ ━ 0%    │ │ ▼ 5%    │ │ ▲ 2건   │       │
│ ○ 데이터 │  └─────────┘ └─────────┘ └─────────┘ └─────────┘       │
│ ○ Watch  │                                                           │
│ ○ 설정   │  ┌─────────────────────────────────────────────────────┐ │
│          │  │ 케이스 목록                            🔍 검색       │ │
│          │  │                                                      │ │
│          │  │ 필터: [전체 상태 ▼] [전체 유형 ▼] [날짜 범위]       │ │
│          │  │                                                      │ │
│          │  │ ┌────┬──────────┬──────┬────────┬──────┬────────┐  │ │
│          │  │ │ #  │ 케이스명  │ 유형  │ 상태    │ 진행률│ 마감일  │  │ │
│          │  │ ├────┼──────────┼──────┼────────┼──────┼────────┤  │ │
│          │  │ │ 01 │ 물류최적화│ 분석  │ ● 진행중│ ██░ 72%│ 03-15 │  │ │
│          │  │ │ 02 │ 생산라인A│ 개선  │ ◐ 검토중│ █░░ 45%│ 03-20 │  │ │
│          │  │ │ 03 │ 공급망진단│ 분석  │ ● 진행중│ ███ 88%│ 02-28 │  │ │
│          │  │ │ .. │ ...      │ ...  │ ...    │ ...  │ ...   │  │ │
│          │  │ └────┴──────────┴──────┴────────┴──────┴────────┘  │ │
│          │  │                                                      │ │
│          │  │ ◀ 1 2 3 ... 8 ▶                    20건/페이지 ▼    │ │
│          │  └─────────────────────────────────────────────────────┘ │
│          │                                                           │
│          │  ┌───────────────────────┐ ┌───────────────────────────┐ │
│          │  │ 최근 활동 타임라인     │ │ 유형별 분포 (파이 차트)   │ │
│          │  │                        │ │                            │ │
│          │  │ 14:30 문서 승인        │ │     ╭───╮                 │ │
│          │  │ 13:15 케이스 생성      │ │   ╭─┤분석├─╮             │ │
│          │  │ 11:00 리뷰 완료        │ │   │ ╰───╯ │              │ │
│          │  │ ...                    │ │   │  62%   │ 개선 38%    │ │
│          │  └───────────────────────┘ │   ╰───────╯              │ │
│          │                             └───────────────────────────┘ │
│          │                                                           │
└──────────┴───────────────────────────────────────────────────────────┘
```

---

## 2. 컴포넌트 분해

### 2.1 컴포넌트 트리

```
CaseDashboardPage
└── DashboardComposer                  # 역할별 패널 합성 (§4 참조)
    ├── RoleGreeting                   # "안녕하세요, {이름}님. 대기 업무 N건"
    ├── QuickActionsPanel              # 역할별 바로가기 카드 (§4.3)
    ├── StatsCard (x4)                 # 통계 카드 (역할별 표시 여부 결정)
    │   ├── shared/ui/Card
    │   └── 트렌드 아이콘 (▲/▼/━)
    ├── [역할별 전용 패널]              # §4.4 참조
    │   ├── MyWorkitemsPanel           # attorney, staff
    │   ├── ApprovalQueuePanel         # manager
    │   ├── AnalyticsQuickPanel        # analyst
    │   ├── DataPipelinePanel          # engineer
    │   └── SystemHealthMiniCard       # admin, engineer
    ├── CaseFilters                    # 필터 바
    │   ├── shared/ui/Select (상태)
    │   ├── shared/ui/Select (유형)
    │   ├── shared/DateRangePicker
    │   └── shared/SearchInput
    ├── CaseTable                      # 케이스 목록 테이블 (engineer 제외)
    │   ├── shared/DataTable
    │   │   ├── ColumnHeader (정렬)
    │   │   └── Pagination
    │   ├── StatusBadge                # 상태 배지
    │   └── ProgressBar                # 진행률 바
    ├── CaseTimeline                   # 최근 활동 (admin, manager, attorney)
    │   └── TimelineItem (x N)
    └── CaseDistributionChart          # 유형별 분포 (admin, manager, analyst)
        └── shared/Chart/PieChart
```

### 2.2 데이터 흐름

```
[역할 결정]
    │
    ▼
useDashboardConfig(role) ──→ DashboardComposer (패널 목록 결정)

[Core API]
    │
    ▼
useCases(filters)      ──→ CaseTable
useCaseStats()         ──→ StatsCard (x4)
                       ──→ CaseDistributionChart
useCaseTimeline()      ──→ CaseTimeline
useMyWorkitems()       ──→ MyWorkitemsPanel      (attorney, staff)
useApprovalQueue()     ──→ ApprovalQueuePanel     (manager)

[Module APIs]
    │
    ▼
useSystemHealth()      ──→ SystemHealthMiniCard   (admin, engineer)
useDatasourceStatus()  ──→ DataPipelinePanel      (engineer)
useRecentQueries()     ──→ AnalyticsQuickPanel    (analyst)

[WebSocket]
    │
    ▼
case:updated   ──→ invalidateQueries(['cases'])      ──→ 자동 리렌더
alert:new      ──→ invalidateQueries(['alerts'])      ──→ QuickActions 카운트 갱신
workitem:updated ──→ invalidateQueries(['workitems']) ──→ 패널 갱신
```

---

## 3. 상태 관리

### 3.1 필터 상태 (URL 동기화)

```typescript
// URL: /dashboard?status=in_progress&type=optimization&page=1

interface CaseFilters {
  status?: CaseStatus;       // URL search param
  type?: 'analysis' | 'optimization';
  dateFrom?: string;
  dateTo?: string;
  search?: string;
  page: number;              // 기본 1
  pageSize: number;          // 기본 20
  sort: string;              // 기본 'createdAt'
  order: 'asc' | 'desc';    // 기본 'desc'
}
```

### 3.2 K-AIR 전환 노트

| K-AIR (Dashboard.vue) | Canvas (CaseDashboardPage) |
|------------------------|----------------------------|
| Vuetify `<v-data-table>` | TanStack Table + Shadcn/ui |
| ApexCharts 파이 차트 | Recharts PieChart |
| Pinia appStore.cases | TanStack Query `useCases()` |
| 필터: 컴포넌트 로컬 state | URL search params |
| 실시간: Socket.io event | WebSocket -> query invalidation |

---

## 4. 역할별 대시보드 합성 (Role-Aware Dashboard Composition)

> **설계 원칙**: 역할별 별도 대시보드 페이지를 만들지 않는다. 단일 `CaseDashboardPage`에서 `DashboardComposer`가 역할에 따라 패널을 조건부 렌더링한다.

### 4.1 DashboardComposer 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│  authStore.user.role                                             │
│       │                                                          │
│       ▼                                                          │
│  useDashboardConfig(role)  ──→  DashboardConfig                 │
│       │                         { panels[], greeting, statsVar } │
│       ▼                                                          │
│  DashboardComposer                                               │
│       │                                                          │
│       ├── panels.includes('system-health') ? <SystemHealthMini/> │
│       ├── panels.includes('case-stats')    ? <StatsCardsRow/>    │
│       ├── panels.includes('quick-actions') ? <QuickActionsPanel/>│
│       ├── panels.includes('my-workitems')  ? <MyWorkitemsPanel/> │
│       ├── panels.includes('approval-queue')? <ApprovalQueue/>    │
│       ├── ...                                                    │
│       └── 순수 프론트엔드 로직 (백엔드 API 불필요)               │
└─────────────────────────────────────────────────────────────────┘
```

#### Per-Panel Suspense 경계

각 패널은 독립적인 `Suspense` 경계로 감싸야 한다. 한 패널의 데이터 로딩이 다른 패널을 블록하지 않도록 한다.

```typescript
// DashboardComposer.tsx
function DashboardComposer() {
  const { panels } = useDashboardConfig();

  return (
    <div className="grid gap-4">
      {panels.includes('system-health') && (
        <Suspense fallback={<SystemHealthSkeleton />}>
          <ErrorBoundary fallback={<PanelError title="시스템 상태" />}>
            <SystemHealthMiniCard />
          </ErrorBoundary>
        </Suspense>
      )}
      {panels.includes('case-stats') && (
        <Suspense fallback={<StatsCardsSkeleton />}>
          <ErrorBoundary fallback={<PanelError title="케이스 통계" />}>
            <StatsCardsRow />
          </ErrorBoundary>
        </Suspense>
      )}
      {/* 나머지 패널도 동일 패턴 */}
    </div>
  );
}
```

> **패턴 근거**: SystemHealthMiniCard는 `/admin/health` API, ApprovalQueuePanel은 `/workitems?status=SUBMITTED` API를 각각 호출한다. 하나의 API가 느리거나 실패해도 다른 패널은 즉시 표시되어야 한다. ErrorBoundary도 패널 단위로 분리하여 한 패널 오류가 전체 대시보드를 망가뜨리지 않도록 한다.

### 4.2 역할 → 패널 매핑

| 패널 | admin | manager | attorney | analyst | engineer | staff | viewer |
|------|:-----:|:-------:|:--------:|:-------:|:--------:|:-----:|:------:|
| RoleGreeting | O | O | O | O | O | O | O |
| SystemHealthMiniCard | O | - | - | - | O | - | - |
| CaseStats (4카드) | O | O | O | - | - | O | O |
| QuickActionsPanel | O | O | O | O | O | O | - |
| MyWorkitemsPanel | - | - | O | - | - | O | - |
| ApprovalQueuePanel | - | O | - | - | - | - | - |
| AnalyticsQuickPanel | - | - | - | O | - | - | - |
| DataPipelinePanel | - | - | - | - | O | - | - |
| CaseTable | O | O | O | O | - | O | O |
| CaseTimeline | O | O | O | - | - | - | - |
| CaseDistributionChart | O | O | - | O | - | - | - |

> **근거**: engineer는 케이스보다 데이터 파이프라인이 주 관심사이므로 CaseTable 대신 DataPipelinePanel을 표시한다. analyst는 케이스 통계보다 분석 도구 바로가기가 더 유용하므로 CaseStats 대신 AnalyticsQuickPanel을 표시한다.

### 4.3 QuickActions 역할별 내용

```
┌────────────────────────────────────────────────────────────────┐
│  admin 로그인 시:                                               │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐           │
│  │ 🖥️ 시스템 상태│ │ 👥 사용자 관리│ │ 📋 로그 탐색  │           │
│  │ → /settings   │ │ → /settings  │ │ → /settings  │           │
│  │   /system     │ │   /users     │ │   /logs      │           │
│  └──────────────┘ └──────────────┘ └──────────────┘           │
│                                                                │
│  manager 로그인 시:                                             │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐           │
│  │ ⏳ 승인 대기  │ │ 🔔 Watch 알림│ │ 📊 팀 업무    │           │
│  │    5건       │ │    12건      │ │   현황        │           │
│  └──────────────┘ └──────────────┘ └──────────────┘           │
│                                                                │
│  attorney 로그인 시:                                            │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐           │
│  │ 📝 내 리뷰   │ │ 🔍 HITL 검토 │ │ 📄 최근 문서  │           │
│  │    3건       │ │   대기 목록   │ │              │           │
│  └──────────────┘ └──────────────┘ └──────────────┘           │
│                                                                │
│  analyst 로그인 시:                                             │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐           │
│  │ 💬 NL2SQL    │ │ 📊 OLAP 피벗 │ │ 🔄 최근      │           │
│  │   쿼리       │ │   분석       │ │   시나리오    │           │
│  │ → /analysis  │ │ → /analysis  │ │ → /cases/    │           │
│  │   /nl2sql    │ │   /olap      │ │   scenarios  │           │
│  └──────────────┘ └──────────────┘ └──────────────┘           │
│                                                                │
│  engineer 로그인 시:                                            │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐           │
│  │ 🔌 데이터소스 │ │ 🔄 동기화    │ │ 🧬 온톨로지  │           │
│  │   상태       │ │   현황       │ │   브라우저    │           │
│  │ → /data/     │ │              │ │ → /data/     │           │
│  │  datasources │ │              │ │  ontology    │           │
│  └──────────────┘ └──────────────┘ └──────────────┘           │
│                                                                │
│  staff 로그인 시:                                               │
│  ┌──────────────┐ ┌──────────────┐                             │
│  │ ✅ 내 할당    │ │ 📅 이번 주   │                             │
│  │   작업 8건   │ │   마감 2건   │                             │
│  └──────────────┘ └──────────────┘                             │
│                                                                │
│  viewer: QuickActions 없음 (읽기 전용)                         │
└────────────────────────────────────────────────────────────────┘
```

> **"Watch 알림 N건" 카운트는 헤더의 NotificationBell과 동일한 데이터를 공유한다.** QuickActions의 Watch 알림 카드는 `uiStore.unreadAlertCount`를 읽어 표시하며, 클릭 시 `/watch`(Watch 대시보드)로 이동한다. NotificationBell 드롭다운 UI 설계는 `watch-alerts.md` §7을 참조한다.

### 4.4 역할별 전용 패널 와이어프레임

#### MyWorkitemsPanel (attorney, staff)

```
┌─────────────────────────────────────────────────────────┐
│  내 할당 업무                                    전체 보기 → │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │ ● TODO    물류최적화 - 재무제표 검토   마감: 03-15 │   │
│  │ ● TODO    생산라인A - 원가 분석       마감: 03-18 │   │
│  │ ◐ 진행중  공급망진단 - HITL 리뷰 대기  마감: 02-28 │   │
│  └──────────────────────────────────────────────────┘   │
│  총 8건 (TODO 5 · 진행중 3)                              │
└─────────────────────────────────────────────────────────┘
```

#### ApprovalQueuePanel (manager)

```
┌─────────────────────────────────────────────────────────┐
│  승인 대기 문서                                  전체 보기 → │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │ 📄 물류최적화 - 프로젝트 차터  김변호사  2시간 전  │   │
│  │ 📄 생산라인A - 원가 보고서    이분석가  1일 전    │   │
│  │ 📄 공급망진단 - 현황 분석     박직원    3일 전 ⚠  │   │
│  └──────────────────────────────────────────────────┘   │
│  총 5건 · 3일 초과 1건 ⚠                                │
└─────────────────────────────────────────────────────────┘
```

#### AnalyticsQuickPanel (analyst)

```
┌─────────────────────────────────────────────────────────┐
│  최근 분석 활동                                           │
│                                                          │
│  최근 쿼리:                                              │
│  ┌──────────────────────────────────────────────────┐   │
│  │ "2025년 분기별 매출 추이는?"           2시간 전    │   │
│  │ "부서별 원가 비율 상위 10개"           어제        │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  최근 시나리오:                                           │
│  ┌──────────────────────────────────────────────────┐   │
│  │ 물류최적화 - 낙관적 시나리오  배분율 85.2%  완료   │   │
│  │ 물류최적화 - 비관적 시나리오  배분율 62.1%  완료   │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

#### DataPipelinePanel (engineer)

```
┌─────────────────────────────────────────────────────────┐
│  데이터소스 현황                              전체 관리 → │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │ ● 정상   PostgreSQL (ERP)     동기화: 10분 전     │   │
│  │ ● 정상   MySQL (CRM)          동기화: 15분 전     │   │
│  │ ⚠ 경고   Oracle (Legacy)      동기화: 2시간 전    │   │
│  │ ✕ 오류   MSSQL (Warehouse)    연결 실패           │   │
│  └──────────────────────────────────────────────────┘   │
│  총 4개 · 정상 2 · 경고 1 · 오류 1                       │
└─────────────────────────────────────────────────────────┘
```

#### SystemHealthMiniCard (admin, engineer)

```
┌──────────────────────────────────────────────────────────┐
│  시스템 상태 요약                        상세 보기 →       │
│                                                           │
│  ● Core   p95: 85ms   │  ● Oracle  p95: 320ms           │
│  ● Vision p95: 150ms  │  ⚠ Synapse p95: 890ms           │
│  ● Weaver p95: 200ms  │     활성 알림: 2건               │
└──────────────────────────────────────────────────────────┘
```

### 4.5 `useDashboardConfig` 훅 설계

```typescript
// features/case-dashboard/hooks/useDashboardConfig.ts

type DashboardPanel =
  | 'system-health'
  | 'case-stats'
  | 'quick-actions'
  | 'my-workitems'
  | 'approval-queue'
  | 'analytics-quick'
  | 'data-pipeline'
  | 'case-table'
  | 'timeline'
  | 'distribution-chart';

interface DashboardConfig {
  panels: DashboardPanel[];
  statsVariant: 'full' | 'compact' | 'none';
}

const ROLE_PANEL_MAP: Record<UserRole, DashboardPanel[]> = {
  admin: [
    'system-health', 'case-stats', 'quick-actions',
    'case-table', 'timeline', 'distribution-chart',
  ],
  manager: [
    'case-stats', 'quick-actions', 'approval-queue',
    'case-table', 'timeline', 'distribution-chart',
  ],
  attorney: [
    'case-stats', 'quick-actions', 'my-workitems',
    'case-table', 'timeline',
  ],
  analyst: [
    'quick-actions', 'analytics-quick',
    'case-table', 'distribution-chart',
  ],
  engineer: [
    'system-health', 'quick-actions', 'data-pipeline',
  ],
  staff: [
    'case-stats', 'quick-actions', 'my-workitems',
    'case-table',
  ],
  viewer: [
    'case-stats', 'case-table',
  ],
};

function useDashboardConfig(): DashboardConfig {
  const role = useAuthStore((s) => s.user?.role ?? 'viewer');

  return useMemo(() => ({
    panels: ROLE_PANEL_MAP[role],
    statsVariant: ['admin', 'manager', 'attorney', 'staff', 'viewer']
      .includes(role) ? 'full' : 'none',
  }), [role]);
}
```

> **설계 결정**: 패널 구성은 순수 프론트엔드 로직이다. JWT `role`에서 파생되며 백엔드 API 호출이 불필요하다. 향후 사용자 커스터마이징이 필요하면 P2에서 `users.preferences` JSONB 컬럼을 활용한다.

### 4.6 새 패널 데이터 소스

| 패널 | API 엔드포인트 | TanStack Query 키 | 원천 테이블 |
|------|-------------|-------------------|-----------|
| MyWorkitemsPanel | `GET /api/v1/workitems/my` | `['workitems', 'my']` | `bpm_work_item` (assignee_id = 현재 사용자) |
| ApprovalQueuePanel | `GET /api/v1/workitems?status=SUBMITTED` | `['workitems', 'pending-review']` | `bpm_work_item` (status = SUBMITTED) |
| DataPipelinePanel | `GET /api/v1/datasources/status` | `['datasources', 'status']` | Weaver API |
| SystemHealthMiniCard | `GET /api/v1/admin/health` | `['admin', 'health']` | admin-dashboard 기존 훅 재사용 |
| AnalyticsQuickPanel | `GET /api/v1/queries/recent` | `['queries', 'recent']` | Oracle query_history |

### 4.7 새 컴포넌트 디렉토리 구조

```
features/case-dashboard/
  components/
    DashboardComposer.tsx              # 역할별 패널 합성기
    RoleGreeting.tsx                    # 역할 맞춤 인사 + 요약
    QuickActionsPanel.tsx              # 역할별 바로가기 카드
    panels/
      MyWorkitemsPanel.tsx             # attorney, staff
      ApprovalQueuePanel.tsx           # manager
      AnalyticsQuickPanel.tsx          # analyst
      DataPipelinePanel.tsx            # engineer
      SystemHealthMiniCard.tsx         # admin, engineer
    StatsCard.tsx                       # (기존)
    CaseTable.tsx                      # (기존)
    CaseTimeline.tsx                   # (기존)
    CaseFilters.tsx                    # (기존)
  hooks/
    useDashboardConfig.ts              # 역할 → 패널 매핑
    useMyWorkitems.ts                  # 내 할당 워크아이템
    useApprovalQueue.ts                # 승인 대기 목록
    useCases.ts                        # (기존)
    useCaseStats.ts                    # (기존)
    useCaseTimeline.ts                 # (기존)
```

### 4.8 P2 — 사용자 환경설정 영속화

P2 단계에서 `users` 테이블에 `preferences JSONB DEFAULT '{}'` 컬럼을 추가하여 대시보드 커스터마이징을 지원한다:

```typescript
// P2 예정
interface UserPreferences {
  dashboard: {
    collapsed_panels: DashboardPanel[];  // 접힌 패널 목록
    stats_density: 'full' | 'compact';   // 통계 카드 밀도
  };
  locale: 'ko' | 'en';
  page_size: number;
}
```

- **API**: 기존 `PATCH /api/v1/users/me`에 preferences 필드 추가
- **DB**: `ALTER TABLE users ADD COLUMN preferences JSONB DEFAULT '{}'` (Alembic 마이그레이션)
- **설계 근거**: `tenants.settings` JSONB 패턴과 동일. 별도 테이블 불필요 (사용자별 1:1 데이터)

### 4.9 명시적 제외 사항

다음은 의도적으로 구현하지 않는다:

| 제외 항목 | 근거 |
|----------|------|
| 역할별 별도 대시보드 페이지 | 7개 페이지 유지보수 부담. DashboardComposer로 충분 |
| 드래그앤드롭 위젯 빌더 | Axiom은 대시보드 제품이 아님 (스코프 크리프) |
| `dashboard_widgets` 등 전용 DB 테이블 | JSONB preferences로 충분 |
| 대시보드 전용 WebSocket 채널 | 기존 이벤트(`case:updated`, `alert:new`)로 충분 |
| 관리자용 대시보드 레이아웃 편집 UI | 역할→패널 매핑은 코드로 관리 |

---

## 결정 사항 (Decisions)

- 필터 상태를 URL에 저장 (북마크/공유 가능)
- 통계 카드는 별도 API 호출 (목록 API에 포함하지 않음)
- **역할별 대시보드 합성은 단일 페이지 + `DashboardComposer` 패턴으로 구현한다** (별도 페이지 금지)
- **패널 구성은 JWT `role` 기반 순수 프론트엔드 로직이다** (P1에서 DB 변경 없음)
- **P2에서 `users.preferences` JSONB 컬럼을 추가하여 사용자 커스터마이징을 지원한다**

---

## 관련 문서

| 문서 | 관계 |
|------|------|
| `services/core/docs/07_security/auth-model.md` | RBAC 7역할 정의, 권한 매트릭스 (SSOT) |
| `canvas/docs/04_frontend/admin-dashboard.md` | admin 전용 시스템 관리 대시보드 (별도 `/settings` 경로) |
| `canvas/docs/07_security/auth-flow.md` | `useRole()`, `RoleGuard`, 사이드바 역할 필터링 |
| `canvas/docs/06_data/state-schema.md` | User.role 타입 정의, authStore 상태 구조 |
| `services/core/docs/06_data/database-schema.md` | `bpm_work_item`, `users` 테이블 (패널 데이터 원천) |
| `canvas/docs/04_frontend/watch-alerts.md` | Watch 알림 대시보드 UI, Notification Center(§7), 역할별 알림 관련성(§8) |

---

## 변경 이력

| 날짜 | 버전 | 작성자 | 내용 |
|------|------|--------|------|
| 2026-02-20 | 2.1 | Axiom Team | §4.1 Per-Panel Suspense 경계 가이드 추가 |
| 2026-02-20 | 2.0 | Axiom Team | 역할별 대시보드 합성 설계 추가 (§4), 컴포넌트 트리/데이터 흐름 업데이트, 관련 문서 추가 |
| 2026-02-19 | 1.0 | Axiom Team | 초기 작성 |
