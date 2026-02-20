# Axiom Core - PostgreSQL 스키마

> **최종 수정일**: 2026-02-20
> **상태**: Active

## 이 문서가 답하는 질문

- 핵심 테이블과 관계는 무엇인가?
- 각 필드의 의미적 정의(semantic meaning)는 무엇인가?
- RLS 정책은 어떻게 적용되는가?
- K-AIR init.sql에서 무엇을 이식하는가?

<!-- affects: backend, security -->
<!-- requires-update: 07_security/data-isolation.md -->

---

## 1. 테이블 구성

### 1.1 테넌트, 사용자, 케이스

```sql
-- 테넌트 (분석 조직, 컨설팅 조직)
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,   -- URL 경로에 사용 (예: "kim-law")
    owner_id UUID,                        -- 소유자 사용자 ID
    mcp_config JSONB DEFAULT '{}',        -- 테넌트별 MCP 서버 설정
    settings JSONB DEFAULT '{}',          -- 테넌트 설정 (LLM 프로바이더 등)
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 사용자
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    role VARCHAR(50) NOT NULL DEFAULT 'viewer',  -- admin, manager, attorney, analyst, engineer, staff, viewer
    skills JSONB DEFAULT '[]',            -- 사용자 보유 역량 태그
    is_agent BOOLEAN DEFAULT false,       -- AI 에이전트 계정 여부
    is_active BOOLEAN DEFAULT true,
    -- [P2 예정] preferences JSONB DEFAULT '{}',  -- 대시보드 패널 설정, locale, page_size 등
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 케이스 (프로젝트/사건 - 전체 시스템의 루트 엔티티)
-- 모든 모듈(Vision, Synapse, Oracle, Weaver)이 case_id로 데이터를 스코핑한다.
CREATE TABLE cases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    name VARCHAR(255) NOT NULL,           -- 프로젝트명 (예: "2026년 1분기 ERP 분석")
    description TEXT,                     -- 프로젝트 설명
    case_type VARCHAR(50) NOT NULL DEFAULT 'GENERAL',
        -- RESTRUCTURING: 기업회생, GROWTH: 성장전략, AUDIT: 감사, GENERAL: 범용
    status case_status NOT NULL DEFAULT 'OPEN',
    settings JSONB DEFAULT '{}',          -- 케이스별 설정 (분석 파라미터 등)
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    closed_at TIMESTAMPTZ                 -- 종결 시각 (status=CLOSED 전이 시)
);

-- Indexes
CREATE INDEX idx_cases_tenant ON cases (tenant_id);
CREATE INDEX idx_cases_tenant_status ON cases (tenant_id, status);
CREATE INDEX idx_cases_created_by ON cases (created_by);
```

> **용어 주의**: 다른 모듈(Vision, Synapse)에서 `org_id`로 참조하는 경우가 있으나, 이는 `tenant_id`와 동일한 개념이다. JWT 페이로드에서는 `tenant_id`가 정규 필드명이며, Core가 발급하는 JWT의 SSOT이다. 향후 모든 모듈은 `tenant_id`로 통일한다.

### 1.2 BPM 프로세스

```sql
-- 프로세스 정의
CREATE TABLE proc_def (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT DEFAULT '',
    bpmn TEXT,                            -- BPMN 2.0 XML (프론트엔드 렌더링)
    definition JSONB NOT NULL,            -- ProcessDefinition JSON (AI 접근)
    type VARCHAR(50) DEFAULT 'base',      -- mega, major, base, sub
    parent_id UUID REFERENCES proc_def(id), -- 계층 구조
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    created_by UUID REFERENCES users(id),
    version INT DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 프로세스 정의 버전
CREATE TABLE proc_def_version (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proc_def_id UUID NOT NULL REFERENCES proc_def(id),
    version INT NOT NULL,
    snapshot JSONB NOT NULL,              -- 해당 버전의 전체 스냅샷
    diff JSONB,                           -- 이전 버전과의 차이
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(proc_def_id, version)
);

-- 프로세스 인스턴스
CREATE TABLE bpm_proc_inst (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proc_def_id UUID NOT NULL REFERENCES proc_def(id),
    case_id UUID REFERENCES cases(id),    -- 연관 사건 (nullable)
    status process_status NOT NULL DEFAULT 'RUNNING',
    initiator_id UUID REFERENCES users(id),
    input_data JSONB DEFAULT '{}',
    result_data JSONB DEFAULT '{}',
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    started_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ,
    version INT DEFAULT 1                 -- 낙관적 잠금
);

-- 워크아이템
CREATE TABLE bpm_work_item (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proc_inst_id UUID NOT NULL REFERENCES bpm_proc_inst(id),
    activity_id VARCHAR(100) NOT NULL,    -- ProcessActivity.id
    activity_name VARCHAR(255) NOT NULL,
    activity_type VARCHAR(50) NOT NULL,   -- humanTask, serviceTask, scriptTask
    assignee_id UUID REFERENCES users(id),
    agent_mode agent_mode DEFAULT 'MANUAL',
    status todo_status NOT NULL DEFAULT 'TODO',
    input_data JSONB DEFAULT '{}',
    result_data JSONB DEFAULT '{}',
    draft_data JSONB,                     -- SUPERVISED 모드: 에이전트 초안
    confidence FLOAT,                     -- 에이전트 실행 신뢰도
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    created_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ,
    version INT DEFAULT 1
);
```

### 1.3 Watch Agent

```sql
-- Watch 구독
CREATE TABLE watch_subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    case_id UUID REFERENCES cases(id),    -- null이면 전체 프로젝트
    event_type VARCHAR(100) NOT NULL,
    rule JSONB NOT NULL DEFAULT '{}',     -- CEP 룰 정의
    channels JSONB DEFAULT '["in_app"]',  -- 알림 채널
    severity_override VARCHAR(20),        -- 기본 심각도 오버라이드
    active BOOLEAN DEFAULT true,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Watch 알림
CREATE TABLE watch_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscription_id UUID REFERENCES watch_subscriptions(id),
    case_id UUID REFERENCES cases(id),
    event_type VARCHAR(100) NOT NULL,
    severity VARCHAR(20) NOT NULL,        -- LOW, MEDIUM, HIGH, CRITICAL
    message TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    status VARCHAR(20) DEFAULT 'unread',  -- unread, acknowledged, dismissed
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    triggered_at TIMESTAMPTZ DEFAULT now(),
    acknowledged_at TIMESTAMPTZ
);

-- 알림 발송 이력
CREATE TABLE watch_alert_deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_id UUID NOT NULL REFERENCES watch_alerts(id),
    channel VARCHAR(20) NOT NULL,         -- in_app, email, sms, slack
    status VARCHAR(20) NOT NULL,          -- SENT, FAILED
    sent_at TIMESTAMPTZ DEFAULT now(),
    error_message TEXT
);
```

### 1.4 Event Outbox

```sql
CREATE TABLE event_outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(100) NOT NULL,
    aggregate_type VARCHAR(100) NOT NULL,
    aggregate_id UUID NOT NULL,
    payload JSONB NOT NULL,
    tenant_id UUID NOT NULL,
    status VARCHAR(20) DEFAULT 'PENDING',
    created_at TIMESTAMPTZ DEFAULT now(),
    published_at TIMESTAMPTZ,
    retry_count INT DEFAULT 0,
    max_retries INT DEFAULT 3,
    error_message TEXT
);
```

---

## 2. ENUM 타입

```sql
CREATE TYPE case_status AS ENUM (
    'OPEN', 'IN_PROGRESS', 'CLOSED', 'ARCHIVED'
);

CREATE TYPE process_status AS ENUM (
    'RUNNING', 'COMPLETED', 'TERMINATED', 'SUSPENDED'
);

CREATE TYPE todo_status AS ENUM (
    'TODO', 'IN_PROGRESS', 'SUBMITTED', 'DONE', 'REWORK', 'CANCELLED'
);

CREATE TYPE agent_mode AS ENUM (
    'AUTONOMOUS', 'SUPERVISED', 'MANUAL'
);
```

---

## 3. RLS 정책

```sql
-- 모든 주요 테이블에 tenant_id 기반 RLS (data-isolation.md 참조)
ALTER TABLE cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE proc_def ENABLE ROW LEVEL SECURITY;
ALTER TABLE bpm_proc_inst ENABLE ROW LEVEL SECURITY;
ALTER TABLE bpm_work_item ENABLE ROW LEVEL SECURITY;
ALTER TABLE watch_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE watch_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE watch_alert_deliveries ENABLE ROW LEVEL SECURITY;
ALTER TABLE event_outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

-- 공통 정책: 현재 테넌트의 데이터만 조회/수정 가능
-- GUC 변수: app.current_tenant_id (JWT에서 추출, ContextVar 경유 설정)
CREATE POLICY tenant_isolation ON cases
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);
-- (다른 테이블도 동일 패턴 적용 — 상세는 07_security/data-isolation.md 참조)
```

---

## 4. 인덱스

```sql
-- 성능 핵심 인덱스
CREATE INDEX idx_workitem_status ON bpm_work_item (proc_inst_id, status);
CREATE INDEX idx_outbox_pending ON event_outbox (status, created_at) WHERE status = 'PENDING';
CREATE INDEX idx_alerts_unread ON watch_alerts (tenant_id, status) WHERE status = 'unread';
CREATE INDEX idx_proc_inst_case ON bpm_proc_inst (case_id, status);

-- pgvector 인덱스 (벡터 검색)
CREATE EXTENSION IF NOT EXISTS vector;
-- (문서 임베딩 테이블에 적용)
```

---

## 근거

- K-AIR process-gpt-main/init.sql (95KB)
- K-AIR 역설계 보고서 섹션 6 (데이터 아키텍처)
- [06_data/database-operations.md](./database-operations.md) (백업/복구, VACUUM, 슬로우 쿼리, 커넥션 풀, 관리자 대시보드 연동)
- [06_data/data-lifecycle.md](./data-lifecycle.md) (엔티티 라이프사이클, 보존 정책, Alembic 마이그레이션)
