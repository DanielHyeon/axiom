# 이벤트 룰 CRUD API

> 구현 상태 태그: `Implemented (Core Watch Proxy)`
> 기준일: 2026-02-21

## 이 문서가 답하는 질문

- 이벤트 감시 룰을 어떻게 등록/수정/삭제하는가?
- 스케줄러를 어떻게 제어하는가?
- 알림 스트림을 어떻게 구독하는가?
- Core Watch 이관 후 이 API는 어떻게 변경되는가?

<!-- affects: 01_architecture, 08_operations -->
<!-- requires-update: 01_architecture/cep-engine.md -->

---

## 1. 이관 공지

> **중요**: Oracle 이벤트 API는 Core Watch API를 프록시한다.
> Oracle은 `/text2sql/events/*` 경로를 유지하고, 내부적으로 Core `/api/v1/watches/*`를 호출한다.
> 상세: [01_architecture/cep-engine.md](../01_architecture/cep-engine.md)

---

## 2. 엔드포인트 요약

| Method | Path | 설명 | 이관 후 | 상태 | 근거(구현/티켓) |
|--------|------|------|--------|------|------------------|
| POST | `/text2sql/events/rules` | 이벤트 룰 생성 | Core Watch | Implemented | `services/oracle/app/api/events.py` |
| GET | `/text2sql/events/rules` | 이벤트 룰 목록 | Core Watch | Implemented | `services/oracle/app/api/events.py` |
| GET | `/text2sql/events/rules/{id}` | 이벤트 룰 상세 | Core Watch | Implemented | `services/oracle/app/api/events.py` |
| PUT | `/text2sql/events/rules/{id}` | 이벤트 룰 수정 | Core Watch | Implemented | `services/oracle/app/api/events.py` |
| DELETE | `/text2sql/events/rules/{id}` | 이벤트 룰 삭제 | Core Watch | Implemented | `services/oracle/app/api/events.py` |
| POST | `/text2sql/events/scheduler/start` | 스케줄러 시작 | Core Watch | Implemented | `services/oracle/app/api/events.py` |
| POST | `/text2sql/events/scheduler/stop` | 스케줄러 중지 | Core Watch | Implemented | `services/oracle/app/api/events.py` |
| GET | `/text2sql/events/scheduler/status` | 스케줄러 상태 | Core Watch | Implemented | `services/oracle/app/api/events.py` |
| GET | `/text2sql/events/stream/alarms` | SSE 알림 스트림 | Core Watch | Implemented | `services/oracle/app/api/events.py` |
| POST | `/text2sql/watch-agent/chat` | 감시 에이전트 대화 | Core Watch | Implemented | `services/oracle/app/api/events.py` |

---

## 3. POST /text2sql/events/rules

### 3.1 요청

```json
{
    "name": "프로세스 마일스톤 기한 임박 알림",
    "description": "마일스톤 기한 3일 전에 대상 프로세스를 알림",
    "datasource_id": "ds_business_main",
    "sql": "SELECT process_id, milestone_deadline, org_name FROM process_milestones WHERE milestone_deadline BETWEEN NOW() AND NOW() + INTERVAL '3 days' AND status = 'ACTIVE'",
    "schedule": {
        "type": "interval",
        "value": "1h"
    },
    "condition": {
        "type": "row_count",
        "operator": "gt",
        "threshold": 0
    },
    "actions": [
        {
            "type": "notification",
            "channel": "sse",
            "template": "프로세스 {process_id}: {org_name}의 마일스톤 기한 {milestone_deadline} 임박"
        }
    ],
    "enabled": true
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `name` | string | Yes | 룰 이름 |
| `description` | string | No | 설명 |
| `datasource_id` | string | Yes | 대상 데이터소스 |
| `sql` | string | Yes | 감시 SQL (SELECT만 허용, SQL Guard 적용) |
| `schedule.type` | string | Yes | 스케줄 유형 (interval/cron) |
| `schedule.value` | string | Yes | 간격 ("1h", "30m") 또는 cron 표현식 |
| `condition.type` | string | Yes | 조건 유형 (row_count/value_change/threshold) |
| `condition.operator` | string | Yes | 비교 연산자 (gt/lt/eq/gte/lte/ne) |
| `condition.threshold` | number | Yes | 임계값 |
| `actions` | array | Yes | 조건 충족 시 실행할 액션 목록 |
| `actions[].type` | string | Yes | 액션 유형 (notification/webhook/email) |
| `actions[].channel` | string | Yes | 채널 (sse/webhook/email) |
| `actions[].template` | string | Yes | 메시지 템플릿 ({column_name}으로 값 치환) |
| `enabled` | boolean | No | 활성화 여부 (기본: true) |

### 3.2 응답 (201 Created)

```json
{
    "success": true,
    "data": {
        "rule_id": "rule_20240115_001",
        "name": "프로세스 마일스톤 기한 임박 알림",
        "status": "active",
        "next_run": "2024-01-15T10:00:00Z"
    }
}
```

---

## 4. GET /text2sql/events/stream/alarms

### 4.1 설명

SSE(Server-Sent Events) 스트림으로 실시간 알림을 수신한다.
Oracle은 이 요청을 Core `/api/v1/watches/stream`으로 프록시하며, `token` 쿼리 파라미터를 함께 전달한다.

### 4.2 응답 (text/event-stream)

```
event: alarm
data: {"rule_id": "rule_20240115_001", "rule_name": "프로세스 마일스톤 기한 임박 알림", "triggered_at": "2024-01-15T10:00:05Z", "matched_rows": 3, "data": [{"process_id": "PROC-2024-100", "org_name": "디지털사업부", "milestone_deadline": "2024-01-18"}], "message": "프로세스 PROC-2024-100: 디지털사업부의 마일스톤 기한 2024-01-18 임박"}

event: heartbeat
data: {"timestamp": "2024-01-15T10:01:00Z"}

event: alarm
data: {"rule_id": "rule_20240115_002", ...}
```

---

## 5. POST /text2sql/watch-agent/chat

### 5.1 설명

감시 에이전트와 자연어로 대화하여 이벤트 룰을 관리한다.

### 5.2 요청

```json
{
    "message": "매출이 전월 대비 10% 이상 감소한 부서를 매시간 알려줘",
    "datasource_id": "ds_business_main",
    "session_id": "watch_session_001"
}
```

### 5.3 응답 (200 OK)

```json
{
    "success": true,
    "data": {
        "response": "다음과 같은 감시 룰을 등록하겠습니다:\n\n- 이름: 매출 감소 부서 감시\n- 실행 간격: 1시간\n- 조건: 전월 대비 매출 10% 이상 감소 부서 존재\n\n등록하시겠습니까?",
        "proposed_rule": {
            "name": "매출 감소 부서 감시",
            "sql": "SELECT ...",
            "schedule": {"type": "interval", "value": "1h"},
            "condition": {"type": "threshold", "field": "change_rate", "operator": "lte", "threshold": -0.1}
        },
        "action_required": "confirm",
        "session_id": "watch_session_001"
    }
}
```

---

## 관련 문서

- [01_architecture/cep-engine.md](../01_architecture/cep-engine.md): CEP 엔진 아키텍처
- [07_security/sql-safety.md](../07_security/sql-safety.md): 이벤트 SQL도 Guard 적용
