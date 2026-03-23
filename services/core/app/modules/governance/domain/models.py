"""
거버넌스 도메인 — SQLAlchemy ORM 모델.

Phase 1: OrgUnit, Workspace, Membership.
기존 tenants/users 테이블은 base_models.py에서 관리하며 여기서 변경하지 않는다.
"""
from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, ForeignKey,
    Index, String, text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.core.database import Base


class OrgUnit(Base):
    """조직 계층 (HQ → DIVISION → DEPARTMENT)."""
    __tablename__ = "org_units"
    __table_args__ = (
        Index("idx_org_units_tenant_parent", "tenant_id", "parent_org_unit_id"),
        Index("idx_org_units_tenant_path", "tenant_id", "path"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    parent_org_unit_id = Column(UUID(as_uuid=True), ForeignKey("org_units.id"), nullable=True)
    code = Column(String(100), nullable=False)
    name = Column(String(255), nullable=False)
    org_type = Column(String(50), nullable=False)
    owner_user_id = Column(String, nullable=True)
    path = Column(String(1000), nullable=False)
    is_deleted = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class Workspace(Base):
    """워크스페이스 — 프로세스/분석/트윈/샌드박스."""
    __tablename__ = "workspaces"
    __table_args__ = (
        Index("idx_workspaces_tenant_org", "tenant_id", "org_unit_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    org_unit_id = Column(UUID(as_uuid=True), ForeignKey("org_units.id"), nullable=False)
    code = Column(String(100), nullable=False)
    name = Column(String(255), nullable=False)
    workspace_type = Column(String(50), nullable=False)
    visibility_policy = Column(String(50), nullable=False, default="PRIVATE", server_default=text("'PRIVATE'"))
    is_deleted = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class Membership(Base):
    """사용자-역할 바인딩 (scope_type으로 범위 결정)."""
    __tablename__ = "memberships"
    __table_args__ = (
        CheckConstraint(
            "(scope_type = 'TENANT'    AND org_unit_id IS NULL AND workspace_id IS NULL) OR "
            "(scope_type = 'ORG_UNIT'  AND org_unit_id IS NOT NULL AND workspace_id IS NULL) OR "
            "(scope_type = 'WORKSPACE' AND workspace_id IS NOT NULL AND org_unit_id IS NULL)",
            name="chk_membership_scope",
        ),
        Index("idx_memberships_tenant_user", "tenant_id", "user_id"),
        Index("idx_memberships_tenant_workspace", "tenant_id", "workspace_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    org_unit_id = Column(UUID(as_uuid=True), ForeignKey("org_units.id"), nullable=True)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=True)
    role_code = Column(String(100), nullable=False)
    scope_type = Column(String(20), nullable=False)
    status = Column(String(30), nullable=False, default="ACTIVE", server_default=text("'ACTIVE'"))
    effective_from = Column(DateTime(timezone=True), nullable=True)
    effective_to = Column(DateTime(timezone=True), nullable=True)
    is_deleted = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
