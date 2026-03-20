# Axiom Core - PostgreSQL 스키마

> **최종 수정일**: 2026-03-21
> **상태**: Active — 실제 SQLAlchemy 모델 기준 검증 완료
> **구현 근거**: `app/models/base_models.py` (모든 ORM 모델), `app/core/database.py` (스키마: `core`)

## 이 문서가 답하는 질문

- 핵심 테이블과 관계는 무엇인가?
- 각 필드의 의미적 정의(semantic meaning)는 무엇인가?
- 테넌트 격리는 어떻게 적용되는가?

<!-- affects: backend, security -->
<!-- requires-update: 07_security/data-isolation.md -->

---

## 0. 스키마 구성

모든 Core 테이블은 PostgreSQL 스키마 `core` 에 생성된다. `app/core/database.py`에서 `MetaData(schema="core")`로 설정. `DATABASE_SCHEMA` 환경변수로 오버라이드 가능.

> **주의**: 실제 구현에서는 PostgreSQL ENUM 타입을 사용하지 않는다. 모든 상태/역할은 `VARCHAR(String)` 컬럼에 문자열로 저장하며, 검증은 Application Layer에서 수행한다. PK는 UUID가 아닌 `String` 타입이다 (Python `uuid.uuid4()` 문자열화).

---

## 1. 테이블 구성 (실제 구현 — 14개 테이블)

### 1.1 테넌트, 사용자

```sql
-- 테넌트 (core.tenants)
CREATE TABLE core.tenants (
    id VARCHAR PRIMARY KEY,              -- uuid4 문자열
    name VARCHAR NOT NULL,
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 사용자 (core.users)
CREATE TABLE core.users (
    id VARCHAR PRIMARY KEY,
    email VARCHAR NOT NULL UNIQUE,
    password_hash VARCHAR NOT NULL,
    tenant_id VARCHAR NOT NULL,          -- FK 없음 (Application 레벨 검증)
    role VARCHAR NOT NULL DEFAULT 'viewer',  -- admin, manager, attorney, analyst, engineer, staff, viewer
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ
);
CREATE INDEX idx_users_email ON core.users (email);
CREATE INDEX idx_users_tenant ON core.users (tenant_id);
```

> **문서 이전 버전과 차이점**: `tenants` 테이블에 `slug`, `owner_id`, `mcp_config`, `settings` 컬럼은 **미구현**이다. `users` 테이블에 `username`, `skills`, `is_agent`, `preferences` 컬럼은 **미구현**이다.

### 1.2 케이스

```sql
-- 케이스 (core.core_case)
CREATE TABLE core.core_case (
    id VARCHAR PRIMARY KEY,
    tenant_id VARCHAR NOT NULL,
    title VARCHAR NOT NULL,              -- (문서 이전 버전의 'name' → 실제 'title')
    status VARCHAR NOT NULL DEFAULT 'PENDING',  -- PENDING, IN_PROGRESS, COMPLETED, REJECTED
    priority VARCHAR NOT NULL DEFAULT 'MEDIUM',
    due_date TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ
);
CREATE INDEX idx_core_case_tenant_status ON core.core_case (tenant_id, status);

-- 케이스 활동 (core.core_case_activity)
CREATE TABLE core.core_case_activity (
    id VARCHAR PRIMARY KEY,
    case_id VARCHAR NOT NULL,
    tenant_id VARCHAR NOT NULL,
    activity_type VARCHAR NOT NULL DEFAULT 'event',
    text VARCHAR NOT NULL,
    meta JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_core_case_activity_case_created ON core.core_case_activity (case_id, created_at);
```

> **문서 이전 버전과 차이점**: 테이블명이 `cases`가 아닌 `core_case`이다. `description`, `case_type`, `settings`, `created_by`, `closed_at` 컬럼은 **미구현**이다. 상태 ENUM이 `OPEN/IN_PROGRESS/CLOSED/ARCHIVED`가 아닌 `PENDING/IN_PROGRESS/COMPLETED/REJECTED`이다.

### 1.3 BPM 프로세스

```sql
-- 프로세스 정의 (core.bpm_process_definition)
CREATE TABLE core.bpm_process_definition (
    id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    description VARCHAR,
    version INTEGER NOT NULL DEFAULT 1,
    type VARCHAR NOT NULL DEFAULT 'base',
    source VARCHAR NOT NULL,             -- natural_language, bpmn_upload 등
    definition JSONB NOT NULL DEFAULT '{}',
    bpmn_xml VARCHAR,                    -- BPMN 2.0 XML (선택)
    confidence FLOAT,                    -- LLM 생성 시 신뢰도
    needs_review BOOLEAN NOT NULL DEFAULT true,
    tenant_id VARCHAR NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ
);
UNIQUE (tenant_id, name, version);
CREATE INDEX idx_bpm_process_definition_tenant_created ON core.bpm_process_definition (tenant_id, created_at);

-- 워크아이템 (core.bpm_work_item)
CREATE TABLE core.bpm_work_item (
    id VARCHAR PRIMARY KEY,
    proc_inst_id VARCHAR,                -- 프로세스 인스턴스 ID (nullable)
    activity_name VARCHAR,
    activity_type VARCHAR DEFAULT 'humanTask',
    assignee_id VARCHAR,
    agent_mode VARCHAR DEFAULT 'MANUAL', -- MANUAL, SUPERVISED, AUTONOMOUS, SELF_VERIFY
    status VARCHAR DEFAULT 'TODO',       -- TODO, IN_PROGRESS, SUBMITTED, DONE, REWORK, CANCELLED
    result_data JSONB,
    tenant_id VARCHAR NOT NULL,
    version INTEGER DEFAULT 1,           -- 낙관적 잠금
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ
);
CREATE INDEX idx_bpm_work_item_tenant_proc_status ON core.bpm_work_item (tenant_id, proc_inst_id, status);
CREATE INDEX idx_bpm_work_item_tenant_assignee_status ON core.bpm_work_item (tenant_id, assignee_id, status);

-- 프로세스 역할 바인딩 (core.bpm_process_role_binding)
CREATE TABLE core.bpm_process_role_binding (
    id VARCHAR PRIMARY KEY,
    proc_inst_id VARCHAR NOT NULL,
    role_name VARCHAR NOT NULL,
    user_id VARCHAR,
    tenant_id VARCHAR NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);
UNIQUE (proc_inst_id, role_name, tenant_id);
```

> **문서 이전 버전과 차이점**: `bpm_proc_inst` 테이블은 **미구현** (인스턴스 상태는 WorkItem 기반으로 관리). `proc_def_version` 테이블도 **미구현**. `bpm_work_item`에서 `activity_id`, `input_data`, `draft_data`, `confidence`, `completed_at` 컬럼은 **미구현**. `agent_mode`에 `SELF_VERIFY`가 추가됨.

### 1.4 Watch Agent

```sql
-- Watch 구독 (core.watch_subscriptions)
CREATE TABLE core.watch_subscriptions (
    id VARCHAR PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    event_type VARCHAR NOT NULL,
    case_id VARCHAR,                     -- null이면 전체
    rule JSONB NOT NULL DEFAULT '{}',
    channels JSONB NOT NULL DEFAULT '[]',
    severity_override VARCHAR,
    active BOOLEAN NOT NULL DEFAULT true,
    tenant_id VARCHAR NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ
);
UNIQUE (user_id, event_type, case_id, tenant_id, active);
CREATE INDEX idx_watch_subscriptions_tenant_user_active ON core.watch_subscriptions (tenant_id, user_id, active);

-- Watch 룰 (core.watch_rules) — 문서 이전 버전에 없던 신규 테이블
CREATE TABLE core.watch_rules (
    id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    event_type VARCHAR NOT NULL,
    definition JSONB NOT NULL DEFAULT '{}',
    active BOOLEAN NOT NULL DEFAULT true,
    tenant_id VARCHAR NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ
);
UNIQUE (tenant_id, name, event_type);
CREATE INDEX idx_watch_rules_tenant_event_active ON core.watch_rules (tenant_id, event_type, active);

-- Watch 알림 (core.watch_alerts)
CREATE TABLE core.watch_alerts (
    id VARCHAR PRIMARY KEY,
    subscription_id VARCHAR REFERENCES core.watch_subscriptions(id) ON DELETE SET NULL,
    event_type VARCHAR NOT NULL,
    case_id VARCHAR,
    case_name VARCHAR,
    severity VARCHAR NOT NULL DEFAULT 'MEDIUM',
    message VARCHAR NOT NULL,
    status VARCHAR NOT NULL DEFAULT 'unread',  -- unread, acknowledged, dismissed
    action_url VARCHAR,
    metadata JSONB NOT NULL DEFAULT '{}',      -- 컬럼명은 'metadata', ORM 속성명은 'meta'
    tenant_id VARCHAR NOT NULL,
    triggered_at TIMESTAMPTZ DEFAULT now(),
    acknowledged_at TIMESTAMPTZ,
    dismissed_at TIMESTAMPTZ                   -- (문서 이전 버전의 resolved_at → dismissed_at)
);
CREATE INDEX idx_watch_alerts_tenant_status_triggered ON core.watch_alerts (tenant_id, status, triggered_at);
CREATE INDEX idx_watch_alerts_tenant_unread_triggered ON core.watch_alerts (tenant_id, triggered_at) WHERE status = 'unread';
```

> **문서 이전 버전과 차이점**: `watch_rules` 테이블이 신규 추가됨. `watch_alert_deliveries`, `watch_alert_actions` 테이블은 **미구현**. `watch_alerts.resolved_at` → `dismissed_at`로 변경, `false_positive` 컬럼 **미구현**. `case_name`, `action_url` 컬럼 추가됨.

### 1.5 Event Outbox + Dead Letter Queue

```sql
-- Event Outbox (core.event_outbox)
CREATE TABLE core.event_outbox (
    id VARCHAR PRIMARY KEY,
    event_type VARCHAR NOT NULL,
    aggregate_type VARCHAR NOT NULL,
    aggregate_id VARCHAR NOT NULL,
    payload JSONB NOT NULL,
    status VARCHAR DEFAULT 'PENDING',     -- PENDING, PUBLISHED, FAILED, DEAD_LETTER
    tenant_id VARCHAR NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    published_at TIMESTAMPTZ,
    retry_count INTEGER DEFAULT 0 NOT NULL,
    last_error VARCHAR                    -- (문서 이전 버전의 error_message → last_error)
);
CREATE INDEX idx_event_outbox_pending ON core.event_outbox (created_at) WHERE status = 'PENDING';
CREATE INDEX idx_event_outbox_failed ON core.event_outbox (created_at) WHERE status = 'FAILED';
CREATE INDEX idx_event_outbox_tenant_created ON core.event_outbox (tenant_id, created_at);

-- Dead Letter Queue (core.event_dead_letter) — 문서 이전 버전에 없던 신규 테이블
CREATE TABLE core.event_dead_letter (
    id VARCHAR PRIMARY KEY,
    original_event_id VARCHAR NOT NULL,
    event_type VARCHAR NOT NULL,
    aggregate_type VARCHAR,
    aggregate_id VARCHAR,
    payload JSONB NOT NULL,
    failure_reason VARCHAR,
    retry_count INTEGER DEFAULT 0 NOT NULL,
    first_failed_at TIMESTAMPTZ DEFAULT now(),
    last_failed_at TIMESTAMPTZ DEFAULT now(),
    resolved_at TIMESTAMPTZ,             -- RETRIED, DISCARDED, MANUAL_FIX
    resolution VARCHAR,
    tenant_id VARCHAR NOT NULL
);
CREATE INDEX idx_event_dead_letter_tenant_resolved ON core.event_dead_letter (tenant_id, resolved_at);
CREATE INDEX idx_event_dead_letter_event_type ON core.event_dead_letter (event_type, last_failed_at);
```

> **문서 이전 버전과 차이점**: `event_outbox`에 `max_retries` 컬럼 **미구현** (하드코딩 `MAX_RETRY=3`). `DEAD_LETTER` 상태 추가. `event_dead_letter` 테이블이 신규 추가됨.

### 1.6 Saga 실행 이력 + 문서 리뷰 (신규 테이블)

```sql
-- Saga 실행 이력 (core.saga_execution_log)
CREATE TABLE core.saga_execution_log (
    id VARCHAR PRIMARY KEY,
    saga_name VARCHAR NOT NULL,
    tenant_id VARCHAR NOT NULL,
    status VARCHAR NOT NULL DEFAULT 'RUNNING',
    context_snapshot JSONB NOT NULL DEFAULT '{}',
    steps_log JSONB NOT NULL DEFAULT '[]',
    started_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ,
    error VARCHAR
);
CREATE INDEX idx_saga_execution_log_tenant_status ON core.saga_execution_log (tenant_id, status);
CREATE INDEX idx_saga_execution_log_saga_name ON core.saga_execution_log (saga_name, started_at);

-- 문서 리뷰 결과 (core.core_document_review)
CREATE TABLE core.core_document_review (
    id VARCHAR PRIMARY KEY,
    case_id VARCHAR NOT NULL,
    document_id VARCHAR NOT NULL,
    tenant_id VARCHAR NOT NULL,
    status VARCHAR NOT NULL,             -- approved, rejected, changes_requested
    comment VARCHAR,
    reviewed_by VARCHAR,
    created_at TIMESTAMPTZ DEFAULT now()
);
UNIQUE (case_id, document_id);
```

---

## 2. 타입 사용 방식

> **참고**: 실제 구현에서는 PostgreSQL ENUM 타입을 사용하지 않는다. 모든 상태 값은 `VARCHAR(String)` 컬럼에 문자열로 저장한다.

### 2.1 상태 값 목록 (Application 레벨 검증)

| 컬럼                     | 허용 값                                                      | 구현 위치                                                         |
|--------------------------|--------------------------------------------------------------|-------------------------------------------------------------------|
| `core_case.status`       | PENDING, IN_PROGRESS, COMPLETED, REJECTED                    | `modules/case/api/routes.py`                                      |
| `bpm_work_item.status`   | TODO, IN_PROGRESS, SUBMITTED, DONE, REWORK, CANCELLED        | `modules/process/domain/aggregates/work_item.py` (WorkItemStatus) |
| `bpm_work_item.agent_mode` | MANUAL, SUPERVISED, AUTONOMOUS, SELF_VERIFY               | `modules/process/domain/aggregates/work_item.py` (AgentMode)      |
| `event_outbox.status`    | PENDING, PUBLISHED, FAILED, DEAD_LETTER                      | `workers/sync.py`                                                 |
| `watch_alerts.status`    | unread, acknowledged, dismissed                              | `modules/watch/application/watch_service.py`                      |
| `users.role`             | admin, manager, attorney, analyst, engineer, staff, viewer   | `core/security.py` (ROLE_PERMISSIONS)                             |

---

## 3. 테넌트 격리

```text
[사실] 모든 주요 테이블에 tenant_id 컬럼이 있다.
[사실] 현재 RLS(Row Level Security) 정책은 DB 레벨에서 미적용이다.
[사실] 테넌트 격리는 Application 레벨에서 수행한다:
       1. JWT에서 tenant_id 추출 (core/security.py)
       2. ContextVar에 설정 (core/middleware.py - TenantMiddleware)
       3. 쿼리 WHERE 절에서 tenant_id 필터링 (각 서비스 레이어)
[계획] PostgreSQL RLS 정책 적용은 향후 추가 예정.
```

---

## 4. 인덱스 (실제 구현)

| 테이블 | 인덱스 | 유형 |
|--------|--------|------|
| `event_outbox` | `(created_at) WHERE status = 'PENDING'` | 부분 인덱스 |
| `event_outbox` | `(created_at) WHERE status = 'FAILED'` | 부분 인덱스 |
| `event_outbox` | `(tenant_id, created_at)` | 복합 |
| `bpm_work_item` | `(tenant_id, proc_inst_id, status)` | 복합 |
| `bpm_work_item` | `(tenant_id, assignee_id, status)` | 복합 |
| `watch_alerts` | `(tenant_id, status, triggered_at)` | 복합 |
| `watch_alerts` | `(tenant_id, triggered_at) WHERE status = 'unread'` | 부분 인덱스 |
| `core_case` | `(tenant_id, status)` | 복합 |
| `core_case_activity` | `(case_id, created_at)` | 복합 |
| `event_dead_letter` | `(tenant_id, resolved_at)` | 복합 |
| `event_dead_letter` | `(event_type, last_failed_at)` | 복합 |
| `saga_execution_log` | `(tenant_id, status)` | 복합 |

---

## 근거

- 실제 구현: `app/models/base_models.py` (2026-03-21 검증)
- `app/core/database.py` (스키마 관리, auto-create)
- [06_data/database-operations.md](./database-operations.md) (백업/복구, 관리자 대시보드 연동)
