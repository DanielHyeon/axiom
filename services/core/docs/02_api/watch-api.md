# Axiom Core - Watch Agent API

> 구현 상태 태그: `Implemented`
> 기준일: 2026-02-21

## 이 문서가 답하는 질문

- Watch Agent 구독/알림 API는 어떻게 사용하는가?
- CEP 룰을 어떻게 정의하고 관리하는가?
- 알림을 실시간으로 어떻게 수신하는가?

<!-- affects: frontend -->
<!-- requires-update: 01_architecture/event-driven.md -->

---

## 1. 엔드포인트 목록

| Method | Path | 설명 | 타임아웃 | 상태 | 근거(구현/티켓) |
|--------|------|------|---------|------|------------------|
| POST | `/api/v1/watches/subscriptions` | 이벤트 구독 생성 | 10s | Implemented | `services/core/app/api/watch/routes.py` |
| GET | `/api/v1/watches/subscriptions` | 내 구독 목록 조회 | 10s | Implemented | `services/core/app/api/watch/routes.py` |
| PUT | `/api/v1/watches/subscriptions/{id}` | 구독 수정 | 10s | Implemented | `services/core/app/api/watch/routes.py` |
| DELETE | `/api/v1/watches/subscriptions/{id}` | 구독 삭제 | 10s | Implemented | `services/core/app/api/watch/routes.py` |
| GET | `/api/v1/watches/alerts` | 알림 목록 조회 | 10s | Implemented | `services/core/app/api/watch/routes.py` |
| PUT | `/api/v1/watches/alerts/{id}/acknowledge` | 알림 확인 | 10s | Implemented | `services/core/app/api/watch/routes.py` |
| PUT | `/api/v1/watches/alerts/{id}/dismiss` | 알림 해제 | 10s | Implemented | `services/core/app/api/watch/routes.py` |
| PUT | `/api/v1/watches/alerts/read-all` | 전체 알림 읽음 처리 | 10s | Implemented | `services/core/app/api/watch/routes.py` |
| GET | `/api/v1/watches/stream` | 실시간 알림 스트림 (SSE) | - | Implemented | `services/core/app/api/watch/routes.py` |
| POST | `/api/v1/watches/rules` | CEP 룰 생성 (관리자) | 10s | Implemented | `services/core/app/api/watch/routes.py` |
| GET | `/api/v1/watches/rules` | CEP 룰 목록 (관리자) | 10s | Implemented | `services/core/app/api/watch/routes.py` |

---

## 2. 주요 엔드포인트 상세

### 2.1 POST /api/v1/watches/subscriptions

이벤트 구독을 생성한다.

#### 요청

```json
{
  "event_type": "DEADLINE_APPROACHING (required)",
  "case_id": "uuid (optional) - 특정 사건만 모니터링. null이면 전체",
  "rule": {
    "type": "deadline | threshold | pattern",
    "days_before": 7,
    "field": null,
    "operator": null,
    "threshold": null,
    "window_hours": null,
    "min_count": null
  },
  "channels": ["in_app", "email"],
  "severity_override": "HIGH (optional)",
  "active": true
}
```

#### 응답 (201 Created)

```json
{
  "subscription_id": "uuid",
  "event_type": "DEADLINE_APPROACHING",
  "case_id": null,
  "channels": ["in_app", "email"],
  "active": true,
  "created_at": "2026-02-19T10:00:00Z"
}
```

#### 이벤트 유형별 룰 예시

```json
// 기한 알림 (7일 전)
{
  "event_type": "DEADLINE_APPROACHING",
  "rule": { "type": "deadline", "days_before": 7 }
}

// 현금 부족 알림 (운영 필요액의 10% 미만)
{
  "event_type": "CASH_LOW",
  "rule": { "type": "threshold", "field": "cash_ratio", "operator": "<", "threshold": 0.10 }
}

// 대량 데이터 등록 (1시간 내 5건 이상)
{
  "event_type": "DATA_REGISTERED",
  "rule": { "type": "pattern", "window_hours": 1, "min_count": 5 }
}
```

---

### 2.2 GET /api/v1/watches/alerts

알림 목록을 조회한다.

#### 쿼리 파라미터

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| `status` | string | N | `unread`, `acknowledged`, `dismissed` |
| `severity` | string | N | `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` |
| `case_id` | uuid | N | 특정 사건의 알림만 |
| `from` | datetime | N | 시작일 |
| `to` | datetime | N | 종료일 |
| `cursor` | uuid | N | 페이지네이션 커서 |
| `limit` | int | N | 기본 20, 최대 100 |

#### 응답

```json
{
  "data": [
    {
      "alert_id": "uuid",
      "event_type": "DEADLINE_APPROACHING",
      "severity": "HIGH",
      "message": "이해관계자 리뷰 기한이 3일 남았습니다.",
      "case_id": "uuid",
      "case_name": "주식회사 XYZ 운영 최적화",
      "status": "unread",
      "triggered_at": "2026-02-19T10:00:00Z",
      "action_url": "/cases/uuid/meetings",
      "metadata": {
        "deadline": "2026-02-22",
        "remaining_days": 3
      }
    }
  ],
  "cursor": { "next": "uuid", "has_more": true },
  "summary": {
    "total_unread": 5,
    "critical_count": 1,
    "high_count": 2
  }
}
```

---

### 2.3 GET /api/v1/watches/stream (SSE)

실시간 알림을 SSE 스트림으로 수신한다.

#### 연결

```
GET /api/v1/watches/stream?token=<jwt_token>
Accept: text/event-stream
```

#### 이벤트 형식

```
event: alert
data: {"alert_id":"uuid","event_type":"DEADLINE_APPROACHING","severity":"HIGH","message":"..."}

event: heartbeat
data: {"timestamp":"2026-02-19T10:00:00Z"}

event: alert_update
data: {"alert_id":"uuid","status":"acknowledged"}
```

#### 연결 관리

```
[사실] SSE 연결은 tenant_id 기반으로 격리된다.
[사실] heartbeat는 30초 간격으로 전송되어 연결 유지를 확인한다.
[사실] 클라이언트 연결이 끊어지면 자동으로 리소스를 정리한다.
[결정] 최대 동시 SSE 연결은 테넌트당 100개로 제한한다.
```

### 2.4 PUT /api/v1/watches/alerts/read-all

현재 사용자의 모든 unread 알림을 acknowledged 상태로 변경한다. Notification Center(헤더 알림 벨)의 "전체 읽음" 버튼에서 호출한다.

#### 요청

```
PUT /api/v1/watches/alerts/read-all
Authorization: Bearer <jwt_token>
```

#### 응답 (200 OK)

```json
{
  "acknowledged_count": 12,
  "message": "12 alerts marked as read"
}
```

> 내부적으로 `UPDATE watch_alerts SET status = 'acknowledged', acknowledged_at = now() WHERE subscription_id IN (SELECT id FROM watch_subscriptions WHERE user_id = :current_user_id) AND status = 'unread'`를 실행한다.

---

### 2.5 역할별 기본 구독 시드

사용자 생성 시(`POST /api/v1/users`) 역할에 따라 기본 구독이 자동 생성된다. 상세 매핑은 `apps/canvas/docs/04_frontend/watch-alerts.md` §8.2를 참조한다.

```
[결정] 사용자 생성 시 역할별 기본 구독을 자동 시드한다.
[결정] 기본 구독은 사용자가 자유롭게 수정/삭제할 수 있다.
[결정] viewer 역할은 기본 구독이 없다 (읽기 전용).
```

---

## 3. 에러 코드

| HTTP | 코드 | 설명 |
|------|------|------|
| 400 | INVALID_RULE | CEP 룰 형식이 잘못됨 |
| 401 | UNAUTHORIZED | SSE 연결 시 `token` 쿼리 파라미터 누락 |
| 404 | SUBSCRIPTION_NOT_FOUND | 구독을 찾을 수 없음 |
| 404 | ALERT_NOT_FOUND | 알림을 찾을 수 없음 |
| 409 | DUPLICATE_SUBSCRIPTION | 동일한 구독이 이미 존재 |
| 429 | TOO_MANY_SUBSCRIPTIONS | 구독 수 제한 초과 (사용자당 50개) |

---

## 관련 문서

| 문서 | 관계 |
|------|------|
| `apps/canvas/docs/04_frontend/watch-alerts.md` | 프론트엔드 Watch 대시보드 UI, Notification Center, 역할별 알림 관련성 |
| `01_architecture/event-driven.md` | CEP 엔진 설계, AlertDispatcher, 에스컬레이션 정책 |

---

## 근거

- K-AIR 역설계 보고서 섹션 4.7.5 (Watch Agent), 섹션 15.2 (events API)
- robo-data-text2sql-main/app/routers/events.py
- 01_architecture/event-driven.md (CEP 엔진 설계)
