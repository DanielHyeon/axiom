-- ============================================================
-- Phase 1: Governance 기반 — DB 마이그레이션
-- 멀티테넌트 프로세스 그래프 구현 계획서 §1.2 기준
-- ============================================================

-- 1. 기존 tenants 테이블 보강
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS code VARCHAR(100);
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS industry_type VARCHAR(100);
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS default_timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Seoul';
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS data_residency VARCHAR(64);
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE';
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();

-- 2. org_units: 조직 계층 (HQ → DIVISION → DEPARTMENT)
CREATE TABLE IF NOT EXISTS org_units (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL REFERENCES tenants(id),
    parent_org_unit_id UUID REFERENCES org_units(id),
    code VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    org_type VARCHAR(50) NOT NULL,
    owner_user_id VARCHAR,
    path VARCHAR(1000) NOT NULL,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_org_units_tenant_code_active
    ON org_units(tenant_id, code) WHERE is_deleted = false;
CREATE INDEX IF NOT EXISTS idx_org_units_tenant_parent ON org_units(tenant_id, parent_org_unit_id);
CREATE INDEX IF NOT EXISTS idx_org_units_tenant_path ON org_units(tenant_id, path);

-- 3. workspaces: 작업 공간
CREATE TABLE IF NOT EXISTS workspaces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL REFERENCES tenants(id),
    org_unit_id UUID NOT NULL REFERENCES org_units(id),
    code VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    workspace_type VARCHAR(50) NOT NULL,
    visibility_policy VARCHAR(50) NOT NULL DEFAULT 'PRIVATE',
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_workspaces_tenant_code_active
    ON workspaces(tenant_id, code) WHERE is_deleted = false;
CREATE INDEX IF NOT EXISTS idx_workspaces_tenant_org ON workspaces(tenant_id, org_unit_id);

-- 4. memberships: 사용자 역할 바인딩
CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE IF NOT EXISTS memberships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL REFERENCES tenants(id),
    user_id VARCHAR NOT NULL REFERENCES users(id),
    org_unit_id UUID REFERENCES org_units(id),
    workspace_id UUID REFERENCES workspaces(id),
    role_code VARCHAR(100) NOT NULL,
    scope_type VARCHAR(20) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',
    effective_from TIMESTAMPTZ,
    effective_to TIMESTAMPTZ,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_membership_scope CHECK (
        (scope_type = 'TENANT'    AND org_unit_id IS NULL AND workspace_id IS NULL) OR
        (scope_type = 'ORG_UNIT'  AND org_unit_id IS NOT NULL AND workspace_id IS NULL) OR
        (scope_type = 'WORKSPACE' AND workspace_id IS NOT NULL AND org_unit_id IS NULL)
    )
);
CREATE INDEX IF NOT EXISTS idx_memberships_tenant_user ON memberships(tenant_id, user_id);
CREATE INDEX IF NOT EXISTS idx_memberships_tenant_workspace ON memberships(tenant_id, workspace_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_membership_active_scope_role
    ON memberships(
        tenant_id, user_id,
        COALESCE(workspace_id, '00000000-0000-0000-0000-000000000000'::uuid),
        COALESCE(org_unit_id, '00000000-0000-0000-0000-000000000000'::uuid),
        role_code
    ) WHERE is_deleted = false AND status = 'ACTIVE';

-- 5. audit_logs (Phase 0에서 정의, Phase 1에서 생성)
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR NOT NULL,
    actor_user_id VARCHAR NOT NULL,
    actor_roles TEXT[] NOT NULL,
    action VARCHAR(100) NOT NULL,
    target_type VARCHAR(50) NOT NULL,
    target_id UUID NOT NULL,
    workspace_id UUID,
    detail_json JSONB,
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant_target
    ON audit_logs(tenant_id, target_type, target_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant_actor
    ON audit_logs(tenant_id, actor_user_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant_action
    ON audit_logs(tenant_id, action, occurred_at DESC);
