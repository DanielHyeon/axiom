"""SQLAlchemy 공통 Mixin — 전 서비스에서 재사용.

SoftDeleteMixin: 물리 삭제 대신 논리 삭제 (deleted_at 타임스탬프)
TimestampMixin: created_at + updated_at 자동 관리

사용 방법:
    class SemanticEntity(Base, SoftDeleteMixin, TimestampMixin):
        __tablename__ = "semantic_entities"
        id = Column(UUID, primary_key=True)
        name = Column(String, nullable=False)

    # 논리 삭제 (DB에서 안 지우고 삭제 시각만 기록)
    entity.soft_delete()

    # 복원 (삭제 취소)
    entity.restore()

    # 살아있는 레코드만 조회할 때:
    session.query(SemanticEntity).filter(SemanticEntity.deleted_at.is_(None))
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime


class TimestampMixin:
    """생성/수정 시각 자동 관리.

    created_at: 레코드가 처음 만들어진 시각 (UTC)
    updated_at: 레코드가 마지막으로 수정된 시각 (UTC)
    """

    # 레코드가 처음 만들어진 시각 — INSERT 때 자동 설정
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # 레코드가 마지막으로 수정된 시각 — UPDATE 때 자동 설정
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=True,
    )


class SoftDeleteMixin:
    """논리 삭제 — deleted_at이 NULL이면 살아있는 레코드.

    핵심 거버넌스 자산(SemanticEntity, OntologyConcept 등)에만 선택 적용.
    조회 시 WHERE deleted_at IS NULL 필터 필수.

    왜 물리 삭제 대신 논리 삭제?
    - 삭제 후에도 이력 추적 가능 (감사 로그)
    - 실수로 삭제한 경우 복원 가능
    - 참조하는 다른 테이블의 FK 깨짐 방지
    """

    # 삭제된 시각 — NULL이면 살아있는 레코드, 값이 있으면 삭제된 레코드
    deleted_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    def soft_delete(self) -> None:
        """레코드를 논리 삭제한다 — 실제로 DB에서 지우지 않고 삭제 시각만 기록."""
        self.deleted_at = datetime.now(timezone.utc)

    def restore(self) -> None:
        """논리 삭제된 레코드를 복원한다 — deleted_at을 None으로 되돌림."""
        self.deleted_at = None

    @property
    def is_deleted(self) -> bool:
        """이 레코드가 논리 삭제되었는지 확인한다."""
        return self.deleted_at is not None
