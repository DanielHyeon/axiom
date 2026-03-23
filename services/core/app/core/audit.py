"""
멀티테넌트 프로세스 그래프 — 감사 로그.

Phase 0 (플랫폼 하드닝): 민감 변경 액션을 별도 audit_logs 테이블에 기록한다.
created_by/updated_by 컬럼과는 별개로, "누가 어떤 권한으로 무엇을 바꿨는가"를 추적.
"""
from __future__ import annotations

import functools
import logging
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4

from sqlalchemy import Column, DateTime, Index, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PG_UUID, JSONB
from sqlalchemy.sql import func

from app.core.database import Base
from app.core.tenant_context import TenantContext, get_tenant_context

logger = logging.getLogger("axiom.audit")


class AuditLog(Base):
    """감사 로그 — 민감 변경 액션 추적 테이블."""
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("idx_audit_logs_tenant_target", "tenant_id", "target_type", "target_id", "occurred_at"),
        Index("idx_audit_logs_tenant_actor", "tenant_id", "actor_user_id", "occurred_at"),
        Index("idx_audit_logs_tenant_action", "tenant_id", "action", "occurred_at"),
    )

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(String, nullable=False)
    actor_user_id = Column(String, nullable=False)
    # TEXT[] 배열 — 행위 시점의 역할 목록
    actor_roles = Column(ARRAY(String), nullable=False)
    action = Column(String(100), nullable=False)
    target_type = Column(String(50), nullable=False)
    target_id = Column(PG_UUID(as_uuid=True), nullable=False)
    workspace_id = Column(PG_UUID(as_uuid=True), nullable=True)
    # before/after diff만 저장, payload 전체 금지, 민감정보 마스킹
    detail_json = Column(JSONB, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    occurred_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


# ── 감사 대상 액션 목록 ────────────────────────────────────
AUDIT_ACTIONS: frozenset[str] = frozenset({
    "governance:workspace:create",
    "governance:workspace:update",
    "governance:workspace:delete",
    "governance:membership:grant",
    "governance:membership:revoke",
    "governance:workspace-switch",
    "process:definition:create",
    "process:definition:update",
    "process:definition:delete",
    "process:version:publish",
    "process:version:deprecate",
    "process:relation:create",
    "process:relation:delete",
    "twin:event:write",
    "twin:snapshot:capture",
    "scenario:run:start",
    "graph:projection:rebuild",
})


async def write_audit_log(
    session,
    *,
    tenant_id: str,
    actor_user_id: str,
    actor_roles: list[str],
    action: str,
    target_type: str,
    target_id,
    workspace_id=None,
    detail_json: dict[str, Any] | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    """감사 로그 1건을 DB에 기록한다."""
    log_entry = AuditLog(
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        actor_roles=actor_roles,
        action=action,
        target_type=target_type,
        target_id=target_id,
        workspace_id=workspace_id,
        detail_json=detail_json,
        ip_address=ip_address,
        user_agent=user_agent,
        occurred_at=datetime.now(timezone.utc),
    )
    session.add(log_entry)
    # flush만 수행 — 트랜잭션 커밋은 호출자 책임
    await session.flush()


def audit_logged(action: str, target_type: str) -> Callable:
    """민감 액션 자동 감사 로깅 데코레이터.

    대상 함수는 첫 번째 인수로 session, 키워드 인수로 target_id를 받아야 한다.
    TenantContext에서 tenant_id, user_id, roles를 자동 추출한다.

    사용 예:
        @audit_logged("process:definition:create", "PROCESS_DEFINITION")
        async def create_definition(session, *, target_id, ...):
            ...
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            result = await fn(*args, **kwargs)

            # 감사 로그 기록 시도 — 실패해도 본 기능은 중단하지 않음
            try:
                ctx = get_tenant_context()
                session = args[0] if args else kwargs.get("session")
                target_id = kwargs.get("target_id")
                if ctx and session and target_id:
                    await write_audit_log(
                        session,
                        tenant_id=ctx.tenant_id,
                        actor_user_id=ctx.user_id,
                        actor_roles=list(ctx.role_codes),
                        action=action,
                        target_type=target_type,
                        target_id=target_id,
                        workspace_id=ctx.workspace_id,
                    )
            except Exception:
                logger.error(
                    "감사 로그 기록 실패: action=%s target_type=%s",
                    action, target_type, exc_info=True,
                )

            return result
        return wrapper
    return decorator
