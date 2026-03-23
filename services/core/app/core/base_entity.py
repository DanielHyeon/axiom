"""
멀티테넌트 프로세스 그래프 — 공통 엔티티 Mixin.

Phase 0 (플랫폼 하드닝): 모든 신규 테이블이 상속하는 공통 컬럼 세트.
- SoftDeleteMixin: is_deleted, version, created_at, updated_at
- TenantScopedMixin: + tenant_id
- WorkspaceScopedMixin: + workspace_id

기존 모델은 Column() 스타일을 사용하므로, 호환성을 위해 동일 스타일을 유지한다.
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Column, DateTime, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func


class SoftDeleteMixin:
    """soft delete + optimistic lock + 타임스탬프 공통 컬럼."""

    is_deleted = Column(
        Boolean, nullable=False, default=False,
        server_default=text("false"),
    )
    # CAS 패턴용 (UPDATE ... WHERE version = :expected)
    version = Column(
        BigInteger, nullable=False, default=1,
        server_default=text("1"),
    )
    created_at = Column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(), onupdate=func.now(),
    )


class TenantScopedMixin(SoftDeleteMixin):
    """tenant_id를 포함하는 모든 엔티티의 공통 컬럼.

    tenant_id는 기존 tenants.id 타입(VARCHAR)과 일치시킨다.
    """
    tenant_id = Column(String, nullable=False, index=True)


class WorkspaceScopedMixin(TenantScopedMixin):
    """workspace_id를 추가로 포함하는 엔티티의 공통 컬럼."""
    workspace_id = Column(UUID(as_uuid=True), nullable=False, index=True)


class AuditColumnsMixin:
    """생성자/수정자 컬럼. 필요한 테이블에만 추가."""
    created_by = Column(String, nullable=True)
    updated_by = Column(String, nullable=True)
