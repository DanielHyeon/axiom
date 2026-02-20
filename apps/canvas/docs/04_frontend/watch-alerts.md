# Watch 알림 대시보드 UI

<!-- affects: frontend, api -->
<!-- requires-update: 02_api/api-client.md (WebSocket) -->

## 이 문서가 답하는 질문

- Watch 알림 대시보드의 화면 구성은 어떻게 되는가?
- 실시간 알림 수신과 표시는 어떻게 동작하는가?
- 알림 규칙 설정은 어떤 인터페이스인가?
- **헤더 알림 벨(Notification Center)의 UI와 동작은 어떻게 되는가?**
- **역할별로 어떤 알림을 기본 구독하는가?**
- **알림의 생명주기(보존, 에스컬레이션, 아카이브)는 어떻게 되는가?**
- **SSE와 WebSocket의 역할 분담은 어떻게 되는가?**
- K-AIR Socket.io 이벤트에서 무엇이 달라지는가?

---

## 1. 화면 와이어프레임

```
┌──────────────────────────────────────────────────────────────────────┐
│ 🔔 Watch 알림 대시보드                          [규칙 설정] [전체 읽음]│
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─ 통계 ──────────────────────────────────────────────────────┐    │
│  │  전체: 47   읽지 않음: 12   긴급: 3   오늘: 8              │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─ 필터 ──────────────────────────────────────────────────────┐    │
│  │  [전체 ▼] [긴급 ▼] [유형 ▼] [날짜 범위]          🔍 검색  │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─ 알림 피드 ─────────────────────┐  ┌─ 이벤트 타임라인 ──────┐  │
│  │                                  │  │                         │  │
│  │  ┌─ 🔴 긴급 ──────────────────┐ │  │  ●─ 14:30 문서 승인    │  │
│  │  │  기한 초과: (주)한진 이해관  │ │  │  │  (주)한진 이해관계   │  │
│  │  │  계자 목록 제출 마감 (D+2)  │ │  │  │  자 목록 v3          │  │
│  │  │  케이스: 2024-PRJ-100123   │ │  │  │                      │  │
│  │  │  2분 전 │ [케이스 보기]     │ │  │  ●─ 13:15 케이스 생성  │  │
│  │  └─────────────────────────────┘ │  │  │  삼성바이오 분석      │  │
│  │                                  │  │  │                      │  │
│  │  ┌─ 🟡 경고 ──────────────────┐ │  │  ●─ 11:00 리뷰 완료   │  │
│  │  │  문서 리뷰 지연: 두산인프라  │ │  │  │  두산인프라 실행     │  │
│  │  │  실행 계획안 리뷰 (D+1)     │ │  │  │  계획안              │  │
│  │  │  15분 전 │ [문서 보기]      │ │  │  │                      │  │
│  │  └─────────────────────────────┘ │  │  ●─ 09:30 알림 규칙    │  │
│  │                                  │  │  │  트리거: 기한 초과   │  │
│  │  ┌─ 🔵 정보 ──────────────────┐ │  │  │                      │  │
│  │  │  새 케이스 등록: 삼성바이오  │ │  │  ●─ 08:00 시스템 시작  │  │
│  │  │  분석 프로세스 개시          │ │  │     일일 배치 완료     │  │
│  │  │  1시간 전 │ [케이스 보기]   │ │  │                         │  │
│  │  └─────────────────────────────┘ │  └─────────────────────────┘  │
│  │                                  │                                │
│  │  ┌─ 🔵 정보 ──────────────────┐ │                                │
│  │  │  데이터 동기화 완료          │ │                                │
│  │  │  운영 PostgreSQL - 45 테이블│ │                                │
│  │  │  3시간 전 │ [상세 보기]     │ │                                │
│  │  └─────────────────────────────┘ │                                │
│  │                                  │                                │
│  │  [더 보기...]                    │                                │
│  └──────────────────────────────────┘                                │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 2. 알림 유형과 우선순위

| 우선순위 | 색상 | 아이콘 | 예시 |
|----------|------|--------|------|
| **긴급** (critical) | 빨강 | 🔴 | 기한 초과, 시스템 장애 |
| **경고** (warning) | 노랑 | 🟡 | 기한 임박 (D-1), 리뷰 지연 |
| **정보** (info) | 파랑 | 🔵 | 새 케이스, 동기화 완료, 문서 승인 |

### 알림 이벤트 -> 우선순위 매핑

| WebSocket 이벤트 | 우선순위 | 알림 메시지 |
|-----------------|----------|-------------|
| `alert:deadline_exceeded` | critical | "기한 초과: {케이스명} {문서명} (D+{일수})" |
| `alert:system_error` | critical | "시스템 오류: {서비스명}" |
| `alert:deadline_approaching` | warning | "기한 임박: {케이스명} (D-{일수})" |
| `alert:review_delayed` | warning | "리뷰 지연: {문서명} (D+{일수})" |
| `case:created` | info | "새 케이스 등록: {케이스명}" |
| `document:status_changed` | info | "문서 상태 변경: {문서명} -> {상태}" |
| `sync:complete` | info | "데이터 동기화 완료: {데이터소스명}" |

---

## 3. 알림 규칙 설정

```
┌──────────────────────────────────────────────────────────────────┐
│ ⚙ 알림 규칙 설정                                                 │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─ 규칙 1: 기한 알림 ──────────────────────── [활성 ●] ──────┐│
│  │  조건: 문서 제출 기한 {D-3, D-1, D+0, D+1} 시점             ││
│  │  대상: 내가 담당하는 케이스                                   ││
│  │  채널: 대시보드 + 이메일                                      ││
│  └──────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ┌─ 규칙 2: 케이스 상태 변경 ──────────────── [활성 ●] ──────┐│
│  │  조건: 케이스 상태가 변경될 때                                ││
│  │  대상: 모든 케이스                                            ││
│  │  채널: 대시보드                                               ││
│  └──────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ┌─ 규칙 3: 이상 탐지 ──────────────────────── [비활성 ○] ───┐│
│  │  조건: 부채비율 급등 (전월 대비 50% 이상)                     ││
│  │  대상: 모니터링 대상 기업                                     ││
│  │  채널: 대시보드 + 이메일 + 슬랙                               ││
│  └──────────────────────────────────────────────────────────────┘│
│                                                                  │
│  [+ 새 규칙 추가]                                                │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 4. 컴포넌트 분해

```
WatchDashboardPage
├── AlertStats
│   └── shared/ui/Card (x4: 전체, 읽지않음, 긴급, 오늘)
├── PriorityFilter
│   ├── shared/ui/Select (우선순위)
│   ├── shared/ui/Select (유형)
│   └── shared/SearchInput
├── AlertFeed
│   ├── AlertCard (x N)
│   │   ├── PriorityIcon (🔴/🟡/🔵)
│   │   ├── AlertContent (메시지, 케이스, 시간)
│   │   ├── ActionButton (케이스/문서 보기)
│   │   └── ReadToggle (읽음/안읽음)
│   └── LoadMoreButton
├── EventTimeline
│   └── TimelineItem (x N)
└── AlertRuleEditor (Sheet/Dialog)
    ├── RuleCondition (조건 빌더)
    ├── RuleTarget (대상 선택)
    └── RuleChannel (채널 선택)
```

---

## 5. 타입 정의

```typescript
// features/watch-alerts/types/alert.ts

/** 알림 우선순위 */
type AlertSeverity = 'critical' | 'warning' | 'info';

/** 알림 상태 */
type AlertStatus = 'unread' | 'acknowledged' | 'dismissed';

/** 알림 이벤트 유형 */
type AlertEventType =
  | 'DEADLINE_APPROACHING'
  | 'APPROVAL_DEADLINE_MISSED'
  | 'REVIEW_SCHEDULED'
  | 'PAYMENT_DUE'
  | 'CASH_LOW'
  | 'DATA_REGISTERED'
  | 'ISSUE_RATIO_HIGH'
  | 'ANOMALY_INDICATOR'
  | 'CASE_CREATED'
  | 'CASE_STATUS_CHANGED'
  | 'DOCUMENT_STATUS_CHANGED'
  | 'WORKITEM_CREATED'
  | 'SYNC_COMPLETE'
  | 'SYSTEM_ERROR';

/** 알림 객체 — Core API GET /alerts 응답 항목 */
interface Alert {
  id: string;                     // UUID
  event_type: AlertEventType;
  severity: AlertSeverity;
  status: AlertStatus;
  message: string;                // 사용자 표시 메시지
  action_url: string;             // 클릭 시 이동 경로 (예: /cases/{caseId})
  case_id?: string;               // 관련 케이스 ID (nullable)
  document_id?: string;           // 관련 문서 ID (nullable)
  triggered_at: string;           // ISO 8601
  acknowledged_at?: string;       // ISO 8601 (nullable)
  escalation_level: number;       // 0 = 원본, 1 = 1차 에스컬레이션, 2 = 2차
  metadata: Record<string, unknown>;  // 이벤트별 추가 데이터
}

/** 알림 목록 응답 */
interface AlertListResponse {
  data: Alert[];
  summary: {
    total: number;
    total_unread: number;
    critical_count: number;
    today_count: number;
  };
  pagination: {
    page: number;
    page_size: number;
    total_pages: number;
  };
}
```

---

## 6. WebSocket 연동

```typescript
// hooks/useAlerts.ts

function useAlerts() {
  const queryClient = useQueryClient();

  // 기존 알림 목록 (REST)
  const alertsQuery = useQuery({
    queryKey: ['alerts', 'feed'],
    queryFn: () => coreApi.getAlerts(),
    staleTime: 0, // WebSocket이 주도하므로 항상 stale
  });

  // 실시간 알림 수신 (WebSocket)
  useEffect(() => {
    const unsub = wsManager.on('alert:new', (alert: Alert) => {
      // 캐시에 직접 추가 (서버 재조회 불필요)
      queryClient.setQueryData(['alerts', 'feed'], (old: Alert[]) => {
        return [alert, ...(old || [])].slice(0, 100); // 최대 100건
      });

      // 토스트 알림 (긴급/경고만)
      if (alert.severity !== 'info') {
        toast[alert.severity === 'critical' ? 'error' : 'warning'](
          alert.message
        );
      }

      // 알림 벨 카운터 업데이트
      useUiStore.getState().incrementUnreadAlerts();
    });

    return unsub;
  }, [queryClient]);

  return alertsQuery;
}
```

---

## 7. K-AIR 전환 노트

| K-AIR (Socket.io) | Canvas | 전환 노트 |
|--------------------|--------|-----------|
| Socket.io 이벤트 수신 | WebSocket 네이티브 | 프로토콜 단순화 |
| mitt() 이벤트 버스로 전파 | TanStack Query cache 직접 업데이트 | 추적 가능한 상태 변경 |
| 알림 UI: 토스트만 | 전용 대시보드 + 토스트 | 알림 관리 강화 |
| 알림 규칙: 없음 | 사용자 정의 규칙 | 신규 기능 |

---

## 8. Notification Center (헤더 알림 벨)

> Watch 대시보드(`/watch`)와 별개로, 앱 전역 헤더의 알림 벨 아이콘을 클릭하면 최근 알림 드롭다운이 표시된다. 이 Notification Center는 모든 페이지에서 접근 가능하다.

### 11.1 와이어프레임

```
Header:  [Logo] [Breadcrumb]                         [🔔 3] [User ▼]
                                                        │
                                                        ▼ (클릭 시 Popover)
              ┌──────────────────────────────────────────┐
              │  알림                          전체 읽음  │
              ├──────────────────────────────────────────┤
              │  🔴 기한 초과: (주)한진 이해관계자        │
              │     목록 제출 마감 (D+2)                  │
              │     2분 전                                │
              │  ──────────────────────────────────────  │
              │  🟡 승인 대기: 두산인프라 실행계획안       │
              │     리뷰 지연 (D+1)                       │
              │     15분 전                               │
              │  ──────────────────────────────────────  │
              │  🔵 새 케이스: 삼성바이오 분석             │
              │     프로세스 개시                          │
              │     1시간 전                              │
              │  ──────────────────────────────────────  │
              │  🔵 데이터 동기화 완료                     │
              │     PostgreSQL - 45 테이블                 │
              │     3시간 전                              │
              ├──────────────────────────────────────────┤
              │            모든 알림 보기 →               │
              └──────────────────────────────────────────┘
```

### 10.2 동작 규칙

| 동작 | 규칙 |
|------|------|
| 벨 아이콘 클릭 | Popover 토글 (Shadcn `Popover`) |
| 벨 배지 숫자 | unread 건수 (최대 99+ 표시, 0이면 배지 숨김) |
| 드롭다운 최대 표시 | 최근 5건 (스크롤 없음 — 간결한 미리보기) |
| 알림 항목 클릭 | `action_url`로 이동 + 자동 읽음 처리 (`PUT /alerts/{id}/acknowledge`) |
| "전체 읽음" 클릭 | `PUT /api/v1/watches/alerts/read-all` → 벨 배지 0으로 초기화 |
| "모든 알림 보기" 클릭 | `/watch` (Watch 대시보드)로 이동 |
| 새 알림 수신 시 (WebSocket) | 벨 배지 숫자 +1, 드롭다운 열려있으면 항목 prepend |
| Popover 외부 클릭 | Popover 닫기 |

### 8.3 컴포넌트 구조

```
layouts/Header/NotificationBell.tsx
├── BellIcon + Badge (unreadAlertCount from uiStore)
├── Popover (Shadcn)
│   ├── PopoverTrigger (Bell + Badge)
│   └── PopoverContent (w-96)
│       ├── NotificationHeader
│       │   ├── "알림" (제목)
│       │   └── Button "전체 읽음" (variant=ghost)
│       ├── NotificationList (최근 5건)
│       │   └── NotificationItem (x5)
│       │       ├── SeverityDot (🔴/🟡/🔵 → bg-destructive/bg-warning/bg-info)
│       │       ├── AlertMessage (text-sm, line-clamp-2)
│       │       ├── RelativeTime (text-xs, text-muted-foreground)
│       │       └── 클릭 → navigate(action_url) + markAsRead
│       └── NotificationFooter
│           └── Link "모든 알림 보기 →" → /watch
└── useNotificationBell() hook
```

### 8.4 `useNotificationBell` 훅 설계

```typescript
// features/watch-alerts/hooks/useNotificationBell.ts

function useNotificationBell() {
  const queryClient = useQueryClient();

  // 최근 알림 5건 (REST)
  const recentAlerts = useQuery({
    queryKey: ['alerts', 'recent'],
    queryFn: () => coreApi.getAlerts({ limit: 5, status: 'unread' }),
    staleTime: 60_000,  // 1분 — WebSocket이 보충
  });

  // 읽지 않은 건수 (별도 쿼리 — 빠른 카운트)
  const unreadCount = useQuery({
    queryKey: ['alerts', 'unread-count'],
    queryFn: () => coreApi.getAlerts({ limit: 0 }).then(r => r.summary.total_unread),
    staleTime: 60_000,
  });

  // WebSocket 실시간 수신 (앱 전역 — DashboardLayout에서 마운트)
  // alert:new 이벤트 → recentAlerts 캐시 prepend + unreadCount +1
  // 이 WebSocket 구독은 §6의 useAlerts와 공유된다.

  // 전체 읽음 처리
  const markAllRead = useMutation({
    mutationFn: () => coreApi.markAllAlertsRead(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
      useUiStore.getState().setUnreadAlertCount(0);
    },
  });

  return { recentAlerts, unreadCount, markAllRead };
}
```

> **Watch 대시보드(§1-4)와 Notification Center(§8)의 관계**: Watch 대시보드는 전체 알림을 관리하는 전용 페이지(`/watch`)이고, Notification Center는 헤더의 벨 아이콘을 통한 빠른 미리보기다. 둘 다 동일한 `['alerts']` TanStack Query 캐시를 공유한다.

---

## 9. 역할별 알림 관련성 & 기본 구독

### 11.1 이벤트 유형 → 역할 관련성 매핑

| 이벤트 유형 | 설명 | admin | manager | attorney | analyst | engineer | staff | viewer |
|------------|------|:-----:|:-------:|:--------:|:-------:|:--------:|:-----:|:------:|
| DEADLINE_APPROACHING | 기한 도래 | O | O | O | - | - | O | - |
| APPROVAL_DEADLINE_MISSED | 승인 기한 도과 | O | O | O | - | - | O | - |
| REVIEW_SCHEDULED | 리뷰 예정 | - | O | O | - | - | - | - |
| PAYMENT_DUE | 지급 기일 | O | O | O | O | - | O | - |
| CASH_LOW | 가용 현금 부족 | O | O | - | O | - | - | - |
| DATA_REGISTERED | 신규 데이터 등록 | - | - | - | O | O | - | - |
| ISSUE_RATIO_HIGH | 이슈 비율 과다 | O | O | - | O | - | - | - |
| ANOMALY_INDICATOR | 이상 징후 감지 | O | O | - | O | - | - | - |
| CASE_CREATED | 케이스 생성 | O | O | - | - | - | - | - |
| CASE_STATUS_CHANGED | 케이스 상태 변경 | - | O | O | - | - | O | - |
| DOCUMENT_STATUS_CHANGED | 문서 상태 변경 | - | O | O | - | - | O | - |
| WORKITEM_CREATED | 워크아이템 생성 | - | - | O | - | - | O | - |
| SYNC_COMPLETE | 데이터 동기화 완료 | O | - | - | - | O | - | - |
| SYSTEM_ERROR | 시스템 오류 | O | - | - | - | O | - | - |

> **설계 원칙**: viewer는 읽기 전용이므로 알림 구독 자체를 하지 않는다. engineer는 데이터/시스템 관련 알림만 수신한다. admin은 시스템 전반을 관리하므로 대부분의 알림을 수신하되, 개별 케이스 워크플로(WORKITEM_CREATED 등)는 제외한다.

### 10.2 역할별 기본 구독 (Default Subscriptions)

사용자 생성 시 역할에 따라 자동으로 구독이 생성된다. 사용자는 §3의 알림 규칙 설정 UI에서 자유롭게 수정/추가/삭제할 수 있다.

```python
# services/core - app/services/watch_service.py

DEFAULT_SUBSCRIPTIONS: dict[str, list[dict]] = {
    "admin": [
        {"event_type": "DEADLINE_APPROACHING", "channels": ["in_app"]},
        {"event_type": "APPROVAL_DEADLINE_MISSED", "channels": ["in_app", "email"]},
        {"event_type": "SYSTEM_ERROR", "channels": ["in_app", "email", "slack"]},
        {"event_type": "CASH_LOW", "channels": ["in_app", "email"]},
        {"event_type": "ANOMALY_INDICATOR", "channels": ["in_app"]},
        {"event_type": "CASE_CREATED", "channels": ["in_app"]},
    ],
    "manager": [
        {"event_type": "DEADLINE_APPROACHING", "channels": ["in_app", "email"]},
        {"event_type": "APPROVAL_DEADLINE_MISSED", "channels": ["in_app", "email"]},
        {"event_type": "REVIEW_SCHEDULED", "channels": ["in_app"]},
        {"event_type": "CASE_STATUS_CHANGED", "channels": ["in_app"]},
        {"event_type": "DOCUMENT_STATUS_CHANGED", "channels": ["in_app"]},
        {"event_type": "CASH_LOW", "channels": ["in_app"]},
    ],
    "attorney": [
        {"event_type": "DEADLINE_APPROACHING", "channels": ["in_app", "email"]},
        {"event_type": "REVIEW_SCHEDULED", "channels": ["in_app", "email"]},
        {"event_type": "WORKITEM_CREATED", "channels": ["in_app"]},
        {"event_type": "DOCUMENT_STATUS_CHANGED", "channels": ["in_app"]},
    ],
    "analyst": [
        {"event_type": "DATA_REGISTERED", "channels": ["in_app"]},
        {"event_type": "CASH_LOW", "channels": ["in_app"]},
        {"event_type": "ANOMALY_INDICATOR", "channels": ["in_app", "email"]},
        {"event_type": "PAYMENT_DUE", "channels": ["in_app"]},
    ],
    "engineer": [
        {"event_type": "DATA_REGISTERED", "channels": ["in_app"]},
        {"event_type": "SYNC_COMPLETE", "channels": ["in_app"]},
        {"event_type": "SYSTEM_ERROR", "channels": ["in_app", "email"]},
    ],
    "staff": [
        {"event_type": "WORKITEM_CREATED", "channels": ["in_app"]},
        {"event_type": "DEADLINE_APPROACHING", "channels": ["in_app"]},
        {"event_type": "CASE_STATUS_CHANGED", "channels": ["in_app"]},
    ],
    "viewer": [],  # 읽기 전용 — 기본 구독 없음
}
```

> **이 기본값은 "합리적인 첫 경험"을 제공하기 위한 시드 데이터다.** 사용자가 알림 규칙 설정(§3)에서 자유롭게 수정할 수 있다. CRITICAL 이벤트(SYSTEM_ERROR, APPROVAL_DEADLINE_MISSED)에는 email/slack 채널이 기본 포함되어 즉각 인지를 보장한다.

---

## 10. 알림 생명주기 & 에스컬레이션

### 11.1 알림 상태 전이

```
알림 생성 (triggered_at, status: unread)
    │
    ├── 사용자 확인 (벨 드롭다운 클릭 또는 Watch 대시보드에서 확인)
    │   → status: acknowledged (acknowledged_at 기록)
    │       └── 30일 후 자동 삭제
    │
    ├── 사용자 해제 (Watch 대시보드에서 dismiss)
    │   → status: dismissed
    │       └── 7일 후 자동 삭제
    │
    └── 미확인 상태 유지 (status: unread)
            ├── CRITICAL: 1시간 미확인 → 에스컬레이션 (§10.2)
            ├── HIGH: 24시간 미확인 → 리마인더 재발송
            └── 90일 후 자동 아카이브
```

### 10.2 에스컬레이션 경로

CRITICAL 알림이 일정 시간 미확인 시, 상위 역할에게 자동 에스컬레이션된다.

```
CRITICAL 알림 1시간 미확인
    │
    ├── 담당자(원래 수신자) → 해당 케이스의 manager에게 에스컬레이션
    │   채널: 이메일 + 인앱 알림
    │   메시지: "[에스컬레이션] {원본 알림 메시지} — {담당자}가 1시간 미확인"
    │
    └── manager도 2시간 미확인 → admin에게 에스컬레이션
        채널: 이메일 + Slack
        메시지: "[긴급 에스컬레이션] {원본 알림 메시지} — 3시간 미확인"
```

> **에스컬레이션은 Watch CEP Worker의 주기적 스캔(5분 간격)으로 구현한다.** `event-driven.md` §4.4의 중복 제거 정책에 따라 에스컬레이션 알림도 idempotency_key로 중복 방지된다.

### 10.3 보존 정책

| 알림 상태 | 보존 기간 | 정리 방식 | 근거 |
|----------|----------|----------|------|
| unread | 90일 | 아카이브 (`watch_alerts` → `watch_alerts_archive` 파티션) | 장기 미확인은 더 이상 행동 가능하지 않음 |
| acknowledged | 30일 | DELETE | 확인된 알림은 기록 목적으로 30일 보존 |
| dismissed | 7일 | DELETE | 사용자가 의도적으로 해제한 알림 |

> `database-operations.md`의 기존 `cleanup_old_data()` 크론잡(매일 03:00 UTC)에 `watch_alerts` 정리 로직을 추가한다. Alembic 마이그레이션으로 `watch_alerts_archive` 파티션 테이블을 생성한다.

### 10.4 토스트 알림 심각도 규칙

WebSocket으로 수신된 알림의 심각도에 따라 토스트 표시 여부와 방식이 달라진다.

| 심각도 | 토스트 | 닫힘 방식 | 벨 카운터 | 근거 |
|--------|--------|----------|----------|------|
| CRITICAL | `toast.error()` | 수동 닫힘 | +1 | 즉각 인지 필요, 자동 사라짐 위험 |
| HIGH | `toast.warning()` | 수동 닫힘 | +1 | 주의 필요, 놓치면 안 됨 |
| MEDIUM | `toast.warning()` | 5초 자동 닫힘 | +1 | 참고 수준, 장시간 방해 불필요 |
| LOW / INFO | 토스트 없음 | - | +1 | 벨 카운터만 증가 — 노이즈 최소화 |

> 이 규칙은 `ux-interaction-patterns.md` §2의 피드백 체계와 일치한다.

---

## 11. 실시간 채널 아키텍처

### 11.1 SSE와 WebSocket의 역할 분담

```
[Core API]                                    [Canvas Frontend]
                                                    │
  ┌─ SSE ─────────────────────────┐                │
  │ GET /api/v1/watches/stream    │                │
  │ • Watch 대시보드 전용          │ ──── SSE ────→ │ WatchDashboardPage
  │ • 전체 알림 스트림 수신        │                │ (페이지 진입 시 연결)
  │ • heartbeat 30초 간격         │                │
  └───────────────────────────────┘                │
                                                    │
  ┌─ WebSocket ───────────────────┐                │
  │ Redis axiom:notifications:    │                │
  │ {tenant_id}                   │                │
  │ • 앱 전역 이벤트 버스          │ ── WebSocket ─→ │ DashboardLayout
  │ • alert:new 이벤트             │                │ (항상 연결)
  │ • case:updated, workitem:     │                │ → NotificationBell
  │   updated 등 다른 이벤트 포함  │                │ → Toast
  └───────────────────────────────┘                │
```

| 채널 | 용도 | 연결 시점 | 해제 시점 |
|------|------|----------|----------|
| **SSE** | Watch 대시보드 전체 알림 스트림 | `/watch` 페이지 진입 | `/watch` 페이지 이탈 |
| **WebSocket** | 앱 전역 실시간 이벤트 (`alert:new`, `case:updated`, `workitem:updated` 등) | `DashboardLayout` 마운트 (로그인 후 항상) | 로그아웃 또는 탭 종료 |

> **왜 둘 다 유지하는가?** SSE는 Watch 대시보드에서 알림 히스토리를 포함한 전체 스트림을 수신하기에 적합하다 (단방향, 자동 재연결). WebSocket은 앱 전역의 양방향 이벤트 버스로, 알림 외에도 `case:updated`, `workitem:updated` 등 다양한 이벤트를 처리한다. Watch 대시보드가 아닌 다른 페이지에서는 WebSocket의 `alert:new` 이벤트만으로 NotificationBell과 Toast를 구동한다.

---

## 결정 사항 (Decisions)

- WebSocket 알림은 TanStack Query 캐시에 직접 주입 (서버 재조회 안함)
  - 근거: 실시간성이 중요, 매번 서버 조회는 불필요 지연
  - 보완: 5분마다 전체 목록 동기화로 누락 방지
- **Notification Center는 Shadcn Popover로 구현하며, 최근 5건만 표시한다** (전체 목록은 Watch 대시보드)
- **역할별 기본 구독은 사용자 생성 시 자동 시드하며, 사용자가 자유롭게 수정할 수 있다**
- **CRITICAL 알림은 1시간 미확인 시 상위 역할에게 에스컬레이션한다**
- **SSE는 Watch 대시보드 전용, WebSocket은 앱 전역 이벤트 버스로 역할을 분담한다**

---

## 관련 문서

| 문서 | 관계 |
|------|------|
| `04_frontend/case-dashboard.md` | 역할별 대시보드 합성 — QuickActions의 "Watch 알림" 카운트 연동 |
| `services/core/docs/07_security/auth-model.md` | RBAC 7역할 정의 — 역할별 알림 관련성의 근거 |
| `services/core/docs/01_architecture/event-driven.md` | Event Outbox → CEP Worker → AlertDispatcher 아키텍처 |
| `services/core/docs/02_api/watch-api.md` | Watch 구독/알림 REST API + SSE 스트림 엔드포인트 |
| `04_frontend/ux-interaction-patterns.md` | 토스트 피드백 규칙 — 심각도별 토스트 동작 |
| `06_data/state-schema.md` | uiStore.unreadAlertCount 상태 정의 |

---

## 변경 이력

| 날짜 | 버전 | 작성자 | 내용 |
|------|------|--------|------|
| 2026-02-20 | 2.0 | Axiom Team | Notification Center UI(§8), 역할별 알림 관련성(§9), 생명주기 & 에스컬레이션(§10), 실시간 채널 아키텍처(§11), 타입 정의(§5) 추가. 관련 문서 테이블 추가 |
| 2026-02-19 | 1.0 | Axiom Team | 초기 작성 |
