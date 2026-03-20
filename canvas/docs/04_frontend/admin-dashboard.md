# 관리자 대시보드 화면 구성

<!-- affects: frontend, api, operations -->
<!-- requires-update: 04_frontend/routing.md, 07_security/auth-flow.md -->

> **최종 수정일**: 2026-02-20
> **상태**: Draft
> **접근 권한**: `admin` 역할 전용

---

## 이 문서가 답하는 질문

- 관리자 대시보드의 전체 화면 구성은 어떻게 되는가?
- 각 관리 화면의 와이어프레임과 기능 범위는?
- AI 로그 분석 챗봇의 UI 인터페이스는 어떻게 구성되는가?
- 시스템 모니터링 정보를 Canvas 내에서 어떻게 확인하는가?
- 기존 `/settings` 페이지와 관리자 대시보드의 관계는?

---

## 1. 관리자 화면 전체 구조

### 1.1 라우트 구조

```
/settings                              (DashboardLayout)
├── index                              → SettingsOverviewPage (기본 탭)
├── /system                            → SystemMonitorPage
│   ├── ?tab=health                    → 서비스 상태 탭
│   ├── ?tab=metrics                   → 메트릭 요약 탭
│   └── ?tab=alerts                    → 활성 알림 탭
├── /logs                              → LogExplorerPage
│   ├── ?tab=explorer                  → 로그 탐색 탭
│   └── ?tab=ai-analysis               → AI 분석 챗봇 탭
├── /users                             → UserManagementPage
└── /config                            → SystemConfigPage
```

### 1.2 사이드바 네비게이션 (관리자 확장)

```
┌───────────────────────────────────┐
│  Axiom Canvas                      │
│                                    │
│  ┌──────────────────────────────┐ │
│  │ 📊 대시보드                  │ │  → /dashboard
│  ├──────────────────────────────┤ │
│  │ 📁 케이스                    │ │  → /cases
│  ├──────────────────────────────┤ │
│  │ 📈 분석                      │ │
│  │   ├ OLAP 피벗                │ │  → /analysis/olap
│  │   └ 자연어 쿼리              │ │  → /analysis/nl2sql
│  ├──────────────────────────────┤ │
│  │ 🔗 데이터                    │ │
│  │   ├ 온톨로지                 │ │  → /data/ontology
│  │   └ 데이터소스               │ │  → /data/datasources
│  ├──────────────────────────────┤ │
│  │ 🔄 프로세스                   │ │  → /process-designer
│  ├──────────────────────────────┤ │
│  │ 🔔 Watch                     │ │  → /watch
│  ├──────────────────────────────┤ │
│  │                              │ │
│  │ ─── 관리 (Admin Only) ───── │ │
│  │                              │ │
│  │ ⚙ 설정                      │ │  → /settings
│  │   ├ 시스템 모니터링          │ │  → /settings/system
│  │   ├ 로그 & AI 분석           │ │  → /settings/logs
│  │   ├ 사용자 관리              │ │  → /settings/users
│  │   └ 시스템 설정              │ │  → /settings/config
│  │                              │ │
│  └──────────────────────────────┘ │
│                                    │
│  ┌──────────────────────────────┐ │
│  │ 사용자 메뉴                  │ │
│  │ 프로필 | 로그아웃            │ │
│  └──────────────────────────────┘ │
└───────────────────────────────────┘
```

> **Note**: "관리 (Admin Only)" 섹션은 `admin` 역할인 경우에만 표시된다. 기존 사이드바 구조를 유지하면서 하단에 관리 메뉴를 추가한다.

### 1.3 라우트 등록

```typescript
// app/router.tsx (추가 부분)

const SystemMonitorPage = lazy(() => import('@/pages/settings/SystemMonitorPage'));
const LogExplorerPage = lazy(() => import('@/pages/settings/LogExplorerPage'));
const UserManagementPage = lazy(() => import('@/pages/settings/UserManagementPage'));
const SystemConfigPage = lazy(() => import('@/pages/settings/SystemConfigPage'));

// Settings 하위 라우트 (Admin only)
{
  path: 'settings',
  element: (
    <RoleGuard roles={['admin']}>
      <Outlet />
    </RoleGuard>
  ),
  children: [
    { index: true, element: <SuspenseWrapper><SettingsPage /></SuspenseWrapper> },
    { path: 'system', element: <SuspenseWrapper><SystemMonitorPage /></SuspenseWrapper> },
    { path: 'logs', element: <SuspenseWrapper><LogExplorerPage /></SuspenseWrapper> },
    { path: 'users', element: <SuspenseWrapper><UserManagementPage /></SuspenseWrapper> },
    { path: 'config', element: <SuspenseWrapper><SystemConfigPage /></SuspenseWrapper> },
  ],
}
```

---

## 2. 설정 개요 (Settings Overview)

### 2.1 화면: `/settings`

```
┌──────────────────────────────────────────────────────────────────────┐
│ ⚙ 설정                                                              │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─ 시스템 상태 요약 ──────────────────────────────────────────┐    │
│  │                                                              │    │
│  │  서비스: 5/5 정상   알림: 2건 (경고 2)   에러율: 0.3%       │    │
│  │  업타임: 15일 2시간  마지막 배포: 2시간 전                   │    │
│  │                                                              │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─ 빠른 바로가기 ─────────────────────────────────────────────┐    │
│  │                                                              │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │    │
│  │  │ 🖥 시스템     │  │ 📋 로그 &    │  │ 👥 사용자    │      │    │
│  │  │ 모니터링     │  │ AI 분석      │  │ 관리         │      │    │
│  │  │              │  │              │  │              │      │    │
│  │  │ 서비스 상태  │  │ 로그 검색    │  │ 계정 관리    │      │    │
│  │  │ 메트릭 요약  │  │ AI 문제분석  │  │ 역할 배정    │      │    │
│  │  │ 활성 알림    │  │ 분석 이력    │  │ 초대         │      │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘      │    │
│  │                                                              │    │
│  │  ┌──────────────┐                                           │    │
│  │  │ 🔧 시스템    │                                           │    │
│  │  │ 설정         │                                           │    │
│  │  │              │                                           │    │
│  │  │ 환경변수     │                                           │    │
│  │  │ 로그 레벨    │                                           │    │
│  │  │ AI 설정      │                                           │    │
│  │  └──────────────┘                                           │    │
│  │                                                              │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─ 최근 활동 ─────────────────────────────────────────────────┐    │
│  │                                                              │    │
│  │  14:30  로그 레벨 변경 (Oracle: INFO → DEBUG) by admin      │    │
│  │  13:15  사용자 추가 (analyst@corp.com) by admin             │    │
│  │  11:00  시스템 배포 (v1.2.3) 완료                           │    │
│  │  09:00  일일 배치 완료 (45 테이블 동기화)                   │    │
│  │                                                              │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 2.2 컴포넌트 구조

```
features/admin/
├── components/
│   ├── AdminOverview/
│   │   ├── SystemStatusSummary.tsx    # 시스템 상태 요약 카드
│   │   ├── QuickAccessCards.tsx       # 빠른 바로가기 카드 그리드
│   │   └── RecentActivityFeed.tsx     # 최근 관리 활동 피드
│   ├── SystemMonitor/                 # → 3절
│   ├── LogExplorer/                   # → 4절
│   ├── UserManagement/                # → 5절
│   └── SystemConfig/                  # → 6절
├── hooks/
│   ├── useSystemHealth.ts             # 서비스 헬스 체크 polling
│   ├── useActiveAlerts.ts             # 활성 알림 조회
│   ├── useAdminAuditLog.ts            # 관리 활동 이력
│   └── useLogAnalysis.ts              # AI 로그 분석 mutation
├── api/
│   ├── adminApi.ts                    # 관리자 API 클라이언트
│   └── adminApi.types.ts              # 타입 정의
├── stores/
│   └── adminFilterStore.ts            # 필터 상태 관리
└── index.ts
```

---

## 3. 시스템 모니터링 (`/settings/system`)

### 3.1 서비스 상태 탭 (`?tab=health`)

```
┌──────────────────────────────────────────────────────────────────────┐
│ 🖥 시스템 모니터링                [상태] [메트릭] [알림]             │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─ 서비스 상태 ───────────────────────────────────────────────┐    │
│  │                                                              │    │
│  │  ┌─ Core API ────────────────────────────────────────┐      │    │
│  │  │ ● 정상 (2/2 Pod)   p95: 320ms   에러율: 0.05%    │      │    │
│  │  │ 업타임: 15일   메모리: 2.1/4GB   CPU: 35%        │      │    │
│  │  │ DB Pool: 15/100   Redis: 연결됨                    │      │    │
│  │  └───────────────────────────────────────────────────┘      │    │
│  │                                                              │    │
│  │  ┌─ Oracle ──────────────────────────────────────────┐      │    │
│  │  │ ● 정상 (2/2 Pod)   p95: 4.2s    에러율: 1.2%     │      │    │
│  │  │ 업타임: 15일   메모리: 1.5/2GB   CPU: 42%        │      │    │
│  │  │ 캐시 히트율: 68%   LLM 토큰: 45K/일              │      │    │
│  │  └───────────────────────────────────────────────────┘      │    │
│  │                                                              │    │
│  │  ┌─ Vision ──────────────────────────────────────────┐      │    │
│  │  │ ● 정상 (2/2 Pod)   p95: 1.1s    에러율: 0.2%     │      │    │
│  │  │ 업타임: 15일   메모리: 2.8/4GB   CPU: 28%        │      │    │
│  │  │ MV 갱신: 정상 (마지막: 30분 전)                    │      │    │
│  │  └───────────────────────────────────────────────────┘      │    │
│  │                                                              │    │
│  │  ┌─ Synapse ─────────────────────────────────────────┐      │    │
│  │  │ ⚠ 경고 (2/2 Pod)   p95: 45s     에러율: 2.8%     │      │    │
│  │  │ 업타임: 15일   메모리: 3.2/4GB   CPU: 55%        │      │    │
│  │  │ HITL 대기: 23건   Neo4j Pool: 72%                 │      │    │
│  │  └───────────────────────────────────────────────────┘      │    │
│  │                                                              │    │
│  │  ┌─ Weaver ──────────────────────────────────────────┐      │    │
│  │  │ ● 정상 (1/1 Pod)   p95: 2.8s    에러율: 0.3%     │      │    │
│  │  │ 업타임: 15일   메모리: 1.2/2GB   CPU: 20%        │      │    │
│  │  │ 동기화: 진행 없음                                  │      │    │
│  │  └───────────────────────────────────────────────────┘      │    │
│  │                                                              │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─ 인프라 상태 ───────────────────────────────────────────────┐    │
│  │                                                              │    │
│  │  PostgreSQL  ● 정상   CPU: 25%  메모리: 12/16GB  디스크: 45%│    │
│  │  Redis       ● 정상   메모리: 2.1/4GB  명령: 1.2K/s        │    │
│  │  Neo4j       ● 정상   Heap: 3.2/4GB  쿼리: 8/s             │    │
│  │                                                              │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  자동 새로고침: 30초                                [↻ 새로고침]    │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 3.2 메트릭 요약 탭 (`?tab=metrics`)

```
┌──────────────────────────────────────────────────────────────────────┐
│ 🖥 시스템 모니터링                [상태] [메트릭] [알림]             │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  기간: [1시간 ▼] [6시간] [24시간] [7일]                             │
│                                                                      │
│  ┌─ 요청량 추이 ─────────────────────────────────────────────┐      │
│  │                                                            │      │
│  │  req/s                                                     │      │
│  │  80 ┤                                                      │      │
│  │  60 ┤            ╱╲                                        │      │
│  │  40 ┤      ╱────╱  ╲────╱╲                                │      │
│  │  20 ┤╱────╱                ╲────                           │      │
│  │   0 ┤─────┼─────┼─────┼─────┼─────                        │      │
│  │     09:00  10:00  11:00  12:00  13:00                      │      │
│  │                                                            │      │
│  │  ── Core  ── Oracle  ── Vision  ── Synapse  ── Weaver     │      │
│  │                                                            │      │
│  └────────────────────────────────────────────────────────────┘      │
│                                                                      │
│  ┌─ 응답 지연 (p95) ─────────────┐  ┌─ 에러율 (%) ──────────┐      │
│  │                                │  │                        │      │
│  │  Core    ██░ 320ms             │  │  Core    ░ 0.05%       │      │
│  │  Oracle  ████████░ 4.2s       │  │  Oracle  █ 1.2%        │      │
│  │  Vision  ███░ 1.1s            │  │  Vision  ░ 0.2%        │      │
│  │  Synapse █████████████ 45s    │  │  Synapse █░ 2.8%       │      │
│  │  Weaver  █████░ 2.8s         │  │  Weaver  ░ 0.3%        │      │
│  │                                │  │                        │      │
│  └────────────────────────────────┘  └────────────────────────┘      │
│                                                                      │
│  ┌─ LLM 사용량 ──────────────────────────────────────────────┐      │
│  │                                                            │      │
│  │  오늘 토큰: 45,200 / 1,000,000   비용: $2.15              │      │
│  │                                                            │      │
│  │  모델별:  gpt-4o: 32K 토큰 ($1.60)                        │      │
│  │          gpt-4o-mini: 13.2K 토큰 ($0.55)                  │      │
│  │                                                            │      │
│  │  Fallback 발생: 3회 (Rate Limit 2, Timeout 1)             │      │
│  │                                                            │      │
│  └────────────────────────────────────────────────────────────┘      │
│                                                                      │
│  [📊 Grafana 상세 보기 →]                                           │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 3.3 활성 알림 탭 (`?tab=alerts`)

```
┌──────────────────────────────────────────────────────────────────────┐
│ 🖥 시스템 모니터링                [상태] [메트릭] [알림]             │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  활성 알림: 2건   [전체 ▼] [Critical ▼] [Warning ▼]                 │
│                                                                      │
│  ┌─ ⚠ Warning ───────────────────────────────────────────────┐      │
│  │  HITLBacklog: HITL 대기 23건                               │      │
│  │  시작: 2시간 전                                            │      │
│  │  대상: Synapse                                             │      │
│  │  대응: 검토자 배정 필요                                    │      │
│  │  [상세 보기] [Grafana →] [AI 분석]                         │      │
│  └────────────────────────────────────────────────────────────┘      │
│                                                                      │
│  ┌─ ⚠ Warning ───────────────────────────────────────────────┐      │
│  │  LowCacheHitRate: Oracle 캐시 히트율 32%                   │      │
│  │  시작: 4시간 전                                            │      │
│  │  대상: Oracle                                              │      │
│  │  대응: Enum 부트스트랩 재실행 확인                         │      │
│  │  [상세 보기] [Grafana →] [AI 분석]                         │      │
│  └────────────────────────────────────────────────────────────┘      │
│                                                                      │
│  ┌─ 최근 해제된 알림 (24시간) ────────────────────────────────┐     │
│  │                                                              │     │
│  │  ✓ HighLatency (Oracle, 해제: 6시간 전, 지속: 25분)         │     │
│  │  ✓ RedisHighMemory (해제: 12시간 전, 지속: 40분)            │     │
│  │                                                              │     │
│  └──────────────────────────────────────────────────────────────┘     │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 3.4 API 연동

```typescript
// features/admin/api/adminApi.ts (시스템 모니터링 관련)

// 서비스 헬스 체크 (Polling 30초)
GET /api/v1/admin/health
→ { services: [{ name, status, pods, uptime, p95, errorRate, memory, cpu }] }

// 인프라 상태
GET /api/v1/admin/health/infra
→ { postgres: {...}, redis: {...}, neo4j: {...} }

// 메트릭 요약 (Prometheus Proxy)
GET /api/v1/admin/metrics/summary?range=1h
→ { requestRate, latencyP95, errorRate, llmUsage, ... }

// 활성 알림 (AlertManager Proxy)
GET /api/v1/admin/alerts?state=active
→ { alerts: [{ name, severity, service, startedAt, annotations }] }
```

---

## 4. 로그 탐색 & AI 분석 (`/settings/logs`)

### 4.1 로그 탐색 탭 (`?tab=explorer`)

```
┌──────────────────────────────────────────────────────────────────────┐
│ 📋 로그 & AI 분석                      [탐색] [AI 분석]             │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─ 필터 ──────────────────────────────────────────────────────┐    │
│  │ 서비스: [전체 ▼]  레벨: [전체 ▼]  기간: [1시간 ▼]          │    │
│  │ 검색어: [___________________________________]  [검색]        │    │
│  │                                                              │    │
│  │ 고급: [tenant_id ▼] [request_id] [event 패턴]               │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─ 로그 볼륨 (시간 × 레벨) ──────────────────────────────────┐    │
│  │  ░░░░░░░░░░░░░░░░██░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │    │
│  │  09:00        10:00        11:00        12:00        13:00  │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  결과: 2,847건 (7일 이내)                              [CSV 내보내기]│
│                                                                      │
│  ┌─ 로그 목록 ─────────────────────────────────────────────────┐    │
│  │                                                              │    │
│  │  ▸ 14:32:15 ERR oracle  llm_call_failed                    │    │
│  │    error="RateLimitError" model="gpt-4o" tenant="abc..."    │    │
│  │                                                              │    │
│  │  ▸ 14:32:14 INF core    api_request_completed              │    │
│  │    path="/api/v1/cases" status=200 duration=45ms            │    │
│  │                                                              │    │
│  │  ▾ 14:32:13 WRN oracle  db_query_timeout                   │    │
│  │  ┌─ 상세 ──────────────────────────────────────────┐       │    │
│  │  │ {                                                │       │    │
│  │  │   "timestamp": "2026-02-20T14:32:13.000Z",      │       │    │
│  │  │   "level": "warning",                            │       │    │
│  │  │   "event": "db_query_timeout",                   │       │    │
│  │  │   "service": "oracle",                           │       │    │
│  │  │   "tenant_id": "550e8400-...",                   │       │    │
│  │  │   "request_id": "6ba7b810-...",                  │       │    │
│  │  │   "duration_ms": 5200,                           │       │    │
│  │  │   "query_type": "nl2sql_execute"                 │       │    │
│  │  │ }                                                │       │    │
│  │  │                                                  │       │    │
│  │  │ [request_id로 추적] [Jaeger 트레이스 →]          │       │    │
│  │  └──────────────────────────────────────────────────┘       │    │
│  │                                                              │    │
│  │  ▸ 14:32:12 INF core    event_published                    │    │
│  │    type="case.updated" aggregate_id="uuid"                  │    │
│  │                                                              │    │
│  │                               [이전] 1 2 3 ... 57 [다음]   │    │
│  │                                                              │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 4.2 AI 분석 챗봇 탭 (`?tab=ai-analysis`)

```
┌──────────────────────────────────────────────────────────────────────┐
│ 📋 로그 & AI 분석                      [탐색] [AI 분석]             │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─ 프리셋 질문 ───────────────────────────────────────────────┐    │
│  │ [에러 요약] [슬로우 쿼리] [LLM 분석] [보안 점검]            │    │
│  │ [DB 상태] [Worker 상태] [캐시 분석] [전체 현황]              │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─ 대화 영역 ─────────────────────────────────────────────────┐    │
│  │                                                              │    │
│  │  ┌─ 🧑‍💼 관리자 ─────────────────────────────────────────┐ │    │
│  │  │ 지난 1시간 Oracle 에러 원인 분석해줘                    │ │    │
│  │  └─────────────────────────────────────────────────────────┘ │    │
│  │                                                              │    │
│  │  ┌─ 🤖 AI 분석 ────────────────────────────────────────┐   │    │
│  │  │                                                      │   │    │
│  │  │  📊 분석 요약                                        │   │    │
│  │  │  지난 1시간 Oracle에서 128건 에러 발생.               │   │    │
│  │  │  주요 원인: OpenAI Rate Limit 초과 (80%)             │   │    │
│  │  │                                                      │   │    │
│  │  │  🎯 에러 패턴                                        │   │    │
│  │  │  ┌────────────────────────────────────────┐          │   │    │
│  │  │  │ llm_call_failed (RateLimit)  102건 80% │          │   │    │
│  │  │  │ db_query_timeout              19건 15% │          │   │    │
│  │  │  │ cache_write_failed             7건  5% │          │   │    │
│  │  │  └────────────────────────────────────────┘          │   │    │
│  │  │                                                      │   │    │
│  │  │  🔎 추정 근본 원인                                   │   │    │
│  │  │  14:00~14:30 NL2SQL 동시 요청 급증 (평소 3배)        │   │    │
│  │  │  → OpenAI Tier 2 Rate Limit (500 RPM) 초과           │   │    │
│  │  │                                                      │   │    │
│  │  │  💡 권장 대응                                         │   │    │
│  │  │  1. ORACLE_LLM_FALLBACK_THRESHOLD=3 → 2             │   │    │
│  │  │  2. ORACLE_MAX_LLM_CONCURRENT=10 → 5                │   │    │
│  │  │  3. 캐시 히트율 32% → Enum 부트스트랩 재실행         │   │    │
│  │  │                                                      │   │    │
│  │  │  ⚠️ 관련 활성 알림                                    │   │    │
│  │  │  • LLMErrorRate: Oracle 에러율 12.5%                 │   │    │
│  │  │  • LowCacheHitRate: Oracle 캐시 히트율 32%           │   │    │
│  │  │                                                      │   │    │
│  │  │  실행 쿼리: {service="oracle"} |= "error" | json     │   │    │
│  │  │  분석 대상: 128건 로그                                │   │    │
│  │  │                                                      │   │    │
│  │  │  [로그 탐색에서 보기] [Grafana →]                     │   │    │
│  │  └──────────────────────────────────────────────────────┘   │    │
│  │                                                              │    │
│  │  ┌─ 🧑‍💼 관리자 ─────────────────────────────────────────┐ │    │
│  │  │ Fallback 임계값 변경하면 되는거지?                      │ │    │
│  │  └─────────────────────────────────────────────────────────┘ │    │
│  │                                                              │    │
│  │  ┌─ 🤖 AI 분석 ────────────────────────────────────────┐   │    │
│  │  │  네, ORACLE_LLM_FALLBACK_THRESHOLD를 3에서 2로       │   │    │
│  │  │  변경하면 Rate Limit 에러 2회 발생 시 바로            │   │    │
│  │  │  gpt-4o-mini로 전환됩니다.                           │   │    │
│  │  │                                                      │   │    │
│  │  │  시스템 설정에서 변경하시겠습니까?                    │   │    │
│  │  │  [설정 변경 페이지로 이동]                            │   │    │
│  │  └──────────────────────────────────────────────────────┘   │    │
│  │                                                              │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─ 질문 입력 ─────────────────────────────────────────────────┐    │
│  │ [_______________________________________________] [분석 ▶]  │    │
│  │                                                              │    │
│  │ 범위: [전체 서비스 ▼]  기간: [1시간 ▼]                      │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─ 분석 이력 ─────────────────────────────────────────────────┐    │
│  │ 14:35 Oracle 에러 분석 (128건) │ 13:00 전체 상태 점검       │    │
│  │ 11:20 Worker 적체 분석 (45건)  │ 09:30 일일 보안 점검       │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 4.3 AI 분석 컴포넌트 구조

```typescript
// features/admin/components/LogExplorer/

LogExplorerPage.tsx                  // 탭 컨테이너
├── LogSearchPanel.tsx               // 필터 + 검색
│   ├── ServiceFilter.tsx            // 서비스 멀티셀렉트
│   ├── LevelFilter.tsx              // 로그 레벨 필터
│   ├── TimeRangeSelector.tsx        // 기간 선택
│   └── AdvancedFilters.tsx          // tenant_id, request_id 등
├── LogVolumeChart.tsx               // 시간별 로그 볼륨 바 차트
├── LogList.tsx                      // 로그 목록 (가상화 스크롤)
│   ├── LogEntry.tsx                 // 개별 로그 행
│   └── LogDetailPanel.tsx           // 확장 상세 (JSON 뷰어)
├── AiAnalysisChat.tsx               // AI 챗봇 대화 인터페이스
│   ├── PresetQuestions.tsx          // 프리셋 질문 버튼
│   ├── ChatMessage.tsx              // 대화 메시지 (사용자/AI)
│   ├── AnalysisResult.tsx           // AI 분석 결과 포맷팅
│   │   ├── ErrorPatternTable.tsx    // 에러 패턴 테이블
│   │   ├── RootCauseCard.tsx        // 근본 원인 카드
│   │   └── RecommendationList.tsx   // 권장 대응 목록
│   ├── ChatInput.tsx                // 질문 입력 + 범위 설정
│   └── AnalysisHistory.tsx          // 분석 이력 목록
└── LogExportButton.tsx              // CSV 내보내기
```

### 4.4 AI 분석 Hook

```typescript
// features/admin/hooks/useLogAnalysis.ts

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { adminApi } from '../api/adminApi';

interface LogAnalysisRequest {
  question: string;
  timeRange: '1h' | '6h' | '24h' | '7d';
  service?: string;
  level?: string;
}

interface LogAnalysisResponse {
  summary: string;
  rootCause: string;
  recommendation: string;
  logQuery: string;
  logCount: number;
  errorPatterns: Array<{
    pattern: string;
    count: number;
    percentage: number;
    firstSeen: string;
    lastSeen: string;
  }>;
  relatedAlerts: string[];
}

export function useLogAnalysis() {
  return useMutation({
    mutationFn: (request: LogAnalysisRequest) =>
      adminApi.post<LogAnalysisResponse>('/admin/log-analysis', request),
    onError: (error) => {
      // Rate Limit 초과 시 사용자에게 안내
      if (error.response?.status === 429) {
        toast.warning('분석 요청 제한에 도달했습니다. 1분 후 다시 시도해주세요.');
      }
    },
  });
}
```

### 4.5 API 연동

```typescript
// 로그 조회 (Loki/CloudWatch Proxy)
POST /api/v1/admin/logs/query
Body: { query: string, start: ISO, end: ISO, limit: number }
→ { logs: [{ timestamp, level, event, service, ... }], total: number }

// AI 로그 분석
POST /api/v1/admin/log-analysis
Body: { question: string, timeRange: "1h", service?: string, level?: string }
→ { summary, rootCause, recommendation, logQuery, logCount, errorPatterns, relatedAlerts }

// 분석 이력 조회
GET /api/v1/admin/log-analysis/history?limit=20
→ { analyses: [{ id, question, createdAt, logCount }] }
```

---

## 5. 사용자 관리 (`/settings/users`)

### 5.1 화면

```
┌──────────────────────────────────────────────────────────────────────┐
│ 👥 사용자 관리                                      [+ 사용자 초대]  │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─ 사용자 통계 ───────────────────────────────────────────────┐    │
│  │ 전체: 24명  활성: 22명  비활성: 2명                          │    │
│  │ admin: 2  manager: 3  attorney: 5  analyst: 8  기타: 6       │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  검색: [_________________________]   역할: [전체 ▼]  상태: [전체 ▼] │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────┐      │
│  │ 이름          │ 이메일              │ 역할     │ 마지막 │ │      │
│  │               │                     │          │ 로그인 │ │      │
│  ├───────────────┼─────────────────────┼──────────┼────────┤ │      │
│  │ 김관리자      │ admin@corp.com      │ admin    │ 방금   │ │      │
│  │ 이분석가      │ analyst@corp.com    │ analyst  │ 1시간  │ │      │
│  │ 박변호사      │ attorney@corp.com   │ attorney │ 3시간  │ │      │
│  │ 최엔지니어    │ engineer@corp.com   │ engineer │ 1일    │ │      │
│  │ 정매니저      │ manager@corp.com    │ manager  │ 2일    │ │      │
│  │ ...           │                     │          │        │ │      │
│  └────────────────────────────────────────────────────────────┘      │
│                                                                      │
│  ┌─ 사용자 상세 (클릭 시) ─────────────────────────────────────┐    │
│  │                                                              │    │
│  │  👤 김관리자                                                 │    │
│  │  이메일: admin@corp.com                                      │    │
│  │  역할: admin                              [역할 변경 ▼]      │    │
│  │  상태: 활성                               [비활성화]          │    │
│  │  가입일: 2026-01-15                                          │    │
│  │  마지막 로그인: 2026-02-20 14:30                             │    │
│  │                                                              │    │
│  │  최근 활동:                                                  │    │
│  │  • 14:30 로그인                                              │    │
│  │  • 14:25 시스템 설정 변경                                    │    │
│  │  • 13:00 사용자 추가                                         │    │
│  │                                                              │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 5.2 사용자 초대 모달

```
┌─ 사용자 초대 ──────────────────────────────────────────┐
│                                                          │
│  이메일: [________________________________]              │
│                                                          │
│  역할:  ○ admin (시스템 관리자)                          │
│         ○ manager (프로세스 분석가)                       │
│         ○ attorney (도메인 전문가)                        │
│         ○ analyst (재무 분석가)                           │
│         ○ engineer (데이터 엔지니어)                      │
│         ○ staff (담당 직원)                               │
│         ○ viewer (뷰어)                                   │
│                                                          │
│  메시지: [________________________________]              │
│          [________________________________]              │
│                                                          │
│                          [취소] [초대 발송]              │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### 5.3 API 연동

```typescript
// 사용자 목록
GET /api/v1/admin/users?role=&status=&search=
→ { users: [{ id, name, email, role, status, lastLoginAt }], total }

// 사용자 초대
POST /api/v1/admin/users/invite
Body: { email, role, message? }

// 역할 변경
PATCH /api/v1/admin/users/:userId/role
Body: { role }

// 사용자 비활성화
PATCH /api/v1/admin/users/:userId/status
Body: { status: "active" | "inactive" }
```

---

## 6. 시스템 설정 (`/settings/config`)

### 6.1 화면

```
┌──────────────────────────────────────────────────────────────────────┐
│ 🔧 시스템 설정                                                       │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─ 로그 설정 ─────────────────────────────────────────────────┐    │
│  │                                                              │    │
│  │  로그 레벨 (서비스별 동적 변경)                              │    │
│  │                                                              │    │
│  │  Core API      [INFO    ▼]  ⟳ 기본값 복원                   │    │
│  │  Core Workers  [WARNING ▼]  ⟳ 기본값 복원                   │    │
│  │  Oracle        [DEBUG   ▼]  ⟳ 기본값 복원  ⚠ 디버그 모드    │    │
│  │  Vision        [INFO    ▼]  ⟳ 기본값 복원                   │    │
│  │  Synapse       [INFO    ▼]  ⟳ 기본값 복원                   │    │
│  │  Weaver        [INFO    ▼]  ⟳ 기본값 복원                   │    │
│  │                                                              │    │
│  │  ℹ 로그 레벨 변경은 즉시 적용됩니다.                        │    │
│  │  Pod 재시작 시 환경변수 기본값으로 복원됩니다.               │    │
│  │                                                              │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─ AI 설정 ───────────────────────────────────────────────────┐    │
│  │                                                              │    │
│  │  NL2SQL 모델        [gpt-4o       ▼]                         │    │
│  │  Fallback 모델      [gpt-4o-mini  ▼]                         │    │
│  │  Fallback 임계값    [2            ▼] 회 연속 실패 시 전환    │    │
│  │  일일 토큰 한도     [1,000,000    ] tokens                   │    │
│  │  동시 LLM 요청      [5            ] 건                       │    │
│  │                                                              │    │
│  │                                          [변경사항 저장]     │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─ 알림 설정 ─────────────────────────────────────────────────┐    │
│  │                                                              │    │
│  │  Slack 채널 (Critical)  [#axiom-critical     ]               │    │
│  │  Slack 채널 (Warning)   [#axiom-alerts       ]               │    │
│  │  이메일 수신자          [admin@corp.com      ] [+ 추가]      │    │
│  │                                                              │    │
│  │  ☑ Critical 알림 → Slack + 이메일                            │    │
│  │  ☑ Warning 알림 → Slack                                      │    │
│  │  ☐ Info 알림 → Slack (기본 비활성)                           │    │
│  │                                                              │    │
│  │                                          [변경사항 저장]     │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─ 데이터 보관 ───────────────────────────────────────────────┐    │
│  │                                                              │    │
│  │  로그 보관 기간          7일 (변경 불가 - 정책)              │    │
│  │  감사 로그 보관          1년 (변경 불가 - 컴플라이언스)      │    │
│  │  Sentry 이벤트 보관      90일                                │    │
│  │  Prometheus 메트릭 보관  30일 (Thanos: 1년)                  │    │
│  │                                                              │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─ 변경 이력 ─────────────────────────────────────────────────┐    │
│  │                                                              │    │
│  │  14:30  LOG_LEVEL (Oracle): INFO → DEBUG  by 김관리자        │    │
│  │  13:15  FALLBACK_THRESHOLD: 3 → 2         by 김관리자        │    │
│  │  09:00  Slack 채널 변경                   by 이관리자        │    │
│  │                                                              │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 6.2 API 연동

```typescript
// 로그 레벨 변경
PUT /api/v1/admin/log/level
Body: { level: "DEBUG", service: "oracle" }

// 로그 레벨 조회
GET /api/v1/admin/log/level
→ { levels: { core: "INFO", oracle: "DEBUG", ... } }

// AI 설정 조회/변경
GET  /api/v1/admin/config/llm
PUT  /api/v1/admin/config/llm
Body: { model, fallbackModel, fallbackThreshold, dailyTokenLimit, maxConcurrent }

// 알림 설정 조회/변경
GET  /api/v1/admin/config/alerts
PUT  /api/v1/admin/config/alerts
Body: { slackChannels, emailRecipients, enabledSeverities }

// 설정 변경 이력
GET /api/v1/admin/config/audit-log?limit=20
→ { entries: [{ timestamp, key, oldValue, newValue, changedBy }] }
```

---

## 7. 디자인 시스템 가이드

### 7.1 관리자 전용 컬러 팔레트

```
상태 표시:
  ● 정상 (green-500)    #22c55e
  ⚠ 경고 (amber-500)    #f59e0b
  ✕ 위험 (red-500)      #ef4444
  ○ 비활성 (gray-400)   #9ca3af

로그 레벨 배지:
  CRITICAL  bg-red-100 text-red-800      border-red-200
  ERROR     bg-red-50 text-red-700       border-red-100
  WARNING   bg-amber-50 text-amber-700   border-amber-100
  INFO      bg-blue-50 text-blue-700     border-blue-100
  DEBUG     bg-gray-50 text-gray-600     border-gray-100

AI 분석 메시지:
  사용자 메시지    bg-primary-50     border-primary-200
  AI 응답         bg-gray-50        border-gray-200
  에러 패턴 강조   bg-red-50         border-red-200
  권장 대응 강조   bg-green-50       border-green-200
```

### 7.2 공통 컴포넌트

```typescript
// shared/components/admin/ (관리자 전용 공통 컴포넌트)

StatusBadge        // 상태 배지 (정상/경고/위험)
MetricCard         // 메트릭 수치 카드
ServiceHealthCard  // 서비스 상태 카드
LogLevelBadge      // 로그 레벨 배지
TimeRangeSelector  // 시간 범위 선택기
JsonViewer         // JSON 뷰어 (로그 상세)
AuditLogEntry      // 감사 로그 항목
AlertCard          // 알림 카드
```

---

## 8. 데이터 흐름

### 8.1 시스템 모니터링 데이터 흐름

```
Canvas Admin UI
    │
    ├── /admin/health → Core API → 각 서비스 /health 호출 (집계)
    │                              → Redis PING
    │                              → PostgreSQL pg_stat_activity
    │                              → Neo4j CALL dbms.info()
    │
    ├── /admin/metrics/summary → Core API → Prometheus HTTP API
    │                                        (PromQL 실행 → 결과 집계)
    │
    └── /admin/alerts → Core API → AlertManager API
                                    (/api/v2/alerts)
```

### 8.2 AI 로그 분석 데이터 흐름

```
Canvas Admin UI
    │
    │  POST /admin/log-analysis
    │  { question: "Oracle 에러 분석" }
    │
    ▼
Core API (LogAnalyzer)
    │
    ├── 1. LLM (gpt-4o-mini) → LogQL 생성
    │
    ├── 2. Loki/CloudWatch → 로그 조회 (최대 500건)
    │
    ├── 3. LLM (gpt-4o) → 로그 분석 + 근본 원인 추정
    │
    ├── 4. AlertManager → 관련 알림 조회
    │
    └── 5. Response → Canvas UI에 표시
```

---

## 결정 사항 (Decisions)

- 관리자 화면을 `/settings` 하위 라우트로 배치
  - 근거: K-AIR의 `/admin/*` → Canvas `/settings`로 통합, 기존 라우트 구조 유지
  - 재평가: 관리 기능이 크게 확장되면 별도 `/admin` 라우트 분리 검토

- 시스템 모니터링은 Canvas 내 요약 + Grafana 상세 링크
  - 근거: Grafana의 풍부한 대시보드를 Canvas에서 재구현하는 것은 비효율적
  - Canvas에서는 핵심 KPI 요약만 제공하고, 상세 분석은 Grafana로 연결

- AI 챗봇은 대화형 인터페이스 (비실시간)
  - 근거: SSE 스트리밍 대신 완성된 분석 결과를 한 번에 반환
  - 이유: 로그 수집 + 분석에 5-15초 소요, 중간 스트리밍의 UX 이점 낮음

- 로그 탐색은 자체 UI 구현 (Grafana Explore 임베딩 아님)
  - 근거: Grafana 임베딩은 인증 복잡도 증가, Canvas 디자인 시스템과 불일치
  - Canvas 내에서 기본 로그 검색 제공, 고급 분석은 Grafana 링크

## 금지됨 (Forbidden)

- 관리자 화면에서 서비스 직접 제어 (재시작, 스케일링 등)
  - 이유: 실수로 인한 서비스 중단 방지, kubectl/Grafana에서 수행
- AI 분석 결과를 자동 적용 (설정 자동 변경)
  - 이유: 관리자가 반드시 검토 후 수동 적용
- 비관리자의 시스템 모니터링/로그 접근

## 필수 (Required)

- 모든 관리자 작업은 audit log 기록
- AI 분석 요청/응답 전체 기록 (감사 목적)
- 시스템 모니터링 데이터 30초 폴링 (WebSocket 불필요 - 데이터 빈도 낮음)
- 로그 상세에서 request_id 클릭 시 전체 서비스 추적 뷰 제공

---

## 관련 문서

| 문서 | 관계 |
|------|------|
| `services/core/docs/08_operations/logging-system.md` | 로깅 체계, AI 분석 API, 보관 정책 |
| `services/core/docs/08_operations/performance-monitoring.md` | Prometheus 메트릭, Grafana 대시보드, 알림 규칙 |
| `canvas/docs/07_security/auth-flow.md` | RBAC 역할 정의, admin 권한 |
| `canvas/docs/04_frontend/routing.md` | 라우트 구조, /settings 경로 |
| `canvas/docs/04_frontend/design-system.md` | 디자인 토큰, 컴포넌트 라이브러리 |
| `canvas/docs/04_frontend/watch-alerts.md` | Watch 알림 UI (참조 패턴) |
| `services/core/docs/06_data/database-operations.md` | DB 모니터링, 슬로우 쿼리, 관리자 API |

---

## 변경 이력

| 날짜 | 버전 | 작성자 | 내용 |
|------|------|--------|------|
| 2026-02-20 | 1.0 | Axiom Team | 초기 작성 (관리자 대시보드, 로그 탐색, AI 분석 챗봇 UI) |
