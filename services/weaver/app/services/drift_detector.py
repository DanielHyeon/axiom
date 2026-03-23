"""G33b: Schema-Semantic Drift Detector (SSDD) — L1-L2 정합성 수호자.

3단계 비교 엔진:
  Stage 1: L1 스냅샷 해시 비교 (구조 변경 감지)
  Stage 2: L2 시맨틱 바인딩 검사 (변경된 자산이 계약에서 참조되는지)
  Stage 3: Breaking Change 판별 + Impact Score 계산

Sprint 3의 SchemaSnapshotService(G33a)를 LKG 입력으로 사용한다.
서킷 브레이커: CRITICAL 드리프트 시 QueryPolicyEngine에 테이블 차단 신호.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.services.snapshot_baseline import (
    ChangeReport,
    ChangeType,
    SchemaSnapshotService,
    SimpleChange,
    snapshot_service,
)
from app.services.adapters.normalization import StandardMetadata
from app.services.semantic_binding_checker import binding_checker, ImpactResult

logger = logging.getLogger("axiom.weaver.drift_detector")


# ── 모델 ── #

class DriftType(str, Enum):
    """시맨틱 드리프트 유형"""
    COLUMN_RENAMED = "column_renamed"
    COLUMN_TYPE_CHANGED = "column_type_changed"
    COLUMN_DROPPED = "column_dropped"
    COLUMN_ADDED = "column_added"
    TABLE_RENAMED = "table_renamed"
    TABLE_DROPPED = "table_dropped"
    FK_DROPPED = "fk_dropped"
    FK_ADDED = "fk_added"
    TABLE_ADDED = "table_added"
    NULLABLE_CHANGED = "nullable_changed"


class DriftSeverity(str, Enum):
    """드리프트 심각도"""
    CRITICAL = "critical"     # 파괴적 변경 — 서킷 브레이커 발동 가능
    WARNING = "warning"       # 수동 검토 권장
    INFO = "info"             # 비파괴적 변경


class ResolutionStatus(str, Enum):
    """드리프트 처리 상태"""
    DETECTED = "detected"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    IGNORED = "ignored"


class SchemaDrift(BaseModel):
    """개별 드리프트 항목"""
    drift_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    tenant_id: str = ""
    datasource_name: str
    schema_name: str = ""
    table_name: str = ""
    column_name: str | None = None
    drift_type: DriftType
    severity: DriftSeverity
    diff_json: dict = Field(default_factory=dict)  # {"old": ..., "new": ...}
    impact_score: int = 0                           # L2 참조 수
    affected_contracts: list[str] = Field(default_factory=list)
    resolution_status: ResolutionStatus = ResolutionStatus.DETECTED
    resolution_comment: str = ""
    resolved_by: str | None = None
    resolved_at: datetime | None = None
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DriftReport(BaseModel):
    """드리프트 탐지 보고서"""
    datasource_name: str
    tenant_id: str = ""
    drifts: list[SchemaDrift] = Field(default_factory=list)
    critical_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    circuit_breaker_triggered: bool = False
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── 심각도 분류 규칙 ── #

# ChangeType → (DriftType, DriftSeverity)
_SEVERITY_MAP: dict[ChangeType, tuple[DriftType, DriftSeverity]] = {
    ChangeType.TABLE_REMOVED: (DriftType.TABLE_DROPPED, DriftSeverity.CRITICAL),
    ChangeType.COLUMN_REMOVED: (DriftType.COLUMN_DROPPED, DriftSeverity.CRITICAL),
    ChangeType.COLUMN_TYPE_CHANGED: (DriftType.COLUMN_TYPE_CHANGED, DriftSeverity.WARNING),
    ChangeType.TABLE_ADDED: (DriftType.TABLE_ADDED, DriftSeverity.INFO),
    ChangeType.COLUMN_ADDED: (DriftType.COLUMN_ADDED, DriftSeverity.INFO),
    ChangeType.TABLE_STRUCTURE_CHANGED: (DriftType.COLUMN_TYPE_CHANGED, DriftSeverity.WARNING),
    ChangeType.COLUMN_NULLABLE_CHANGED: (DriftType.NULLABLE_CHANGED, DriftSeverity.WARNING),
}


# ── 서비스 ── #

class DriftDetector:
    """3단계 비교 엔진: 스냅샷 해시 → 바인딩 검사 → Breaking Change 판별.

    사용법:
        detector = DriftDetector()
        report = await detector.detect("ds1", new_metadata, tenant_id="t1")
    """

    def __init__(self) -> None:
        self._snapshot_service = snapshot_service
        # 드리프트 이력 (in-memory MVP — Phase 5에서 PostgreSQL)
        self._drifts: dict[str, list[SchemaDrift]] = {}  # tenant_id:ds → 드리프트 목록

    async def detect(
        self,
        datasource_name: str,
        new_metadata: StandardMetadata,
        tenant_id: str = "",
    ) -> DriftReport:
        """3단계 드리프트 탐지.

        Stage 1: SchemaSnapshotService.detect_changes() — L1 해시 비교
        Stage 2: 변경된 자산이 L2 시맨틱 계약에서 참조되는지 확인 (MVP: 전체 변경 보고)
        Stage 3: Breaking Change 분류 + 심각도 판정
        """
        # Stage 1: 스냅샷 비교
        change_report = await self._snapshot_service.detect_changes(
            datasource_name, new_metadata, tenant_id,
        )

        if not change_report.has_changes:
            return DriftReport(datasource_name=datasource_name, tenant_id=tenant_id)

        # Stage 2 + 3: 변경 → L2 바인딩 영향도 → 심각도 분류
        drifts: list[SchemaDrift] = []
        for change in change_report.changes:
            drift_type, base_severity = _SEVERITY_MAP.get(
                change.change_type,
                (DriftType.COLUMN_ADDED, DriftSeverity.INFO),
            )

            # G33b 고도화: L2 시맨틱 바인딩 영향도 실연동
            impact = await binding_checker.check_impact(
                datasource_name=datasource_name,
                schema_name=change.schema_name,
                table_name=change.table_name,
                column_name=change.column_name,
                tenant_id=tenant_id,
            )

            # 영향도에 따라 심각도 상향 조정
            severity = base_severity
            if impact.is_breaking and base_severity != DriftSeverity.INFO:
                severity = DriftSeverity.CRITICAL  # L2 참조 있으면 CRITICAL로 상향
            elif impact.has_impact and severity == DriftSeverity.INFO:
                severity = DriftSeverity.WARNING   # 영향 있으면 최소 WARNING

            drift = SchemaDrift(
                tenant_id=tenant_id,
                datasource_name=datasource_name,
                schema_name=change.schema_name,
                table_name=change.table_name,
                column_name=change.column_name,
                drift_type=drift_type,
                severity=severity,
                diff_json={
                    "old": change.old_value,
                    "new": change.new_value,
                    "description": change.description,
                },
                impact_score=impact.impact_score,
                affected_contracts=impact.affected_entities,
            )
            drifts.append(drift)

        # 이력 저장
        key = f"{tenant_id}:{datasource_name}"
        self._drifts.setdefault(key, []).extend(drifts)
        # 최대 1000건 유지
        if len(self._drifts[key]) > 1000:
            self._drifts[key] = self._drifts[key][-500:]

        # 서킷 브레이커 판단
        critical_count = sum(1 for d in drifts if d.severity == DriftSeverity.CRITICAL)
        warning_count = sum(1 for d in drifts if d.severity == DriftSeverity.WARNING)
        info_count = sum(1 for d in drifts if d.severity == DriftSeverity.INFO)
        circuit_breaker = critical_count > 0

        if circuit_breaker:
            # 서킷 브레이커: CRITICAL 드리프트가 있는 테이블을 QueryPolicyEngine에 차단 등록
            from app.services.query_engine import query_engine
            for d in drifts:
                if d.severity == DriftSeverity.CRITICAL:
                    fqn = f"{d.schema_name}.{d.table_name}".lower()
                    query_engine.block_table(fqn)
                    logger.warning("서킷 브레이커 발동: %s (%s)", fqn, d.drift_type.value)

        # M2: CRITICAL 드리프트 시 LKG 스냅샷 유지 (깨진 스키마로 덮어쓰지 않음)
        if not circuit_breaker:
            await self._snapshot_service.save_snapshot(datasource_name, new_metadata, tenant_id)

        report = DriftReport(
            datasource_name=datasource_name,
            tenant_id=tenant_id,
            drifts=drifts,
            critical_count=critical_count,
            warning_count=warning_count,
            info_count=info_count,
            circuit_breaker_triggered=circuit_breaker,
        )

        logger.info(
            "드리프트 탐지 완료: ds=%s, critical=%d, warning=%d, info=%d, circuit_breaker=%s",
            datasource_name, critical_count, warning_count, info_count, circuit_breaker,
        )
        return report

    def get_drifts(
        self,
        datasource_name: str,
        tenant_id: str = "",
        severity: DriftSeverity | None = None,
        status: ResolutionStatus | None = None,
        limit: int = 50,
    ) -> list[SchemaDrift]:
        """드리프트 이력 조회"""
        key = f"{tenant_id}:{datasource_name}"
        drifts = self._drifts.get(key, [])
        if severity:
            drifts = [d for d in drifts if d.severity == severity]
        if status:
            drifts = [d for d in drifts if d.resolution_status == status]
        return sorted(drifts, key=lambda d: d.detected_at, reverse=True)[:limit]

    def resolve_drift(
        self,
        drift_id: str,
        tenant_id: str,
        resolved_by: str,
        resolution_status: ResolutionStatus = ResolutionStatus.RESOLVED,
        comment: str = "",
    ) -> SchemaDrift | None:
        """드리프트 해결 처리"""
        for key, drifts in self._drifts.items():
            if not key.startswith(f"{tenant_id}:"):
                continue
            for drift in drifts:
                if drift.drift_id == drift_id:
                    drift.resolution_status = resolution_status
                    drift.resolution_comment = comment
                    drift.resolved_by = resolved_by
                    drift.resolved_at = datetime.now(timezone.utc)

                    # C1: 해결 시 서킷 브레이커 해제 — 같은 테이블에 미해결 CRITICAL 없을 때만
                    if (
                        resolution_status == ResolutionStatus.RESOLVED
                        and drift.severity == DriftSeverity.CRITICAL
                    ):
                        fqn = f"{drift.schema_name}.{drift.table_name}".lower()
                        remaining_critical = [
                            d for d in drifts
                            if d.drift_id != drift_id
                            and d.severity == DriftSeverity.CRITICAL
                            and d.resolution_status == ResolutionStatus.DETECTED
                            and f"{d.schema_name}.{d.table_name}".lower() == fqn
                        ]
                        if not remaining_critical:
                            from app.services.query_engine import query_engine
                            query_engine.unblock_table(fqn)
                            logger.info("서킷 브레이커 해제: %s (resolved by %s)", fqn, resolved_by)

                    return drift
        return None


# 모듈 수준 싱글톤
drift_detector = DriftDetector()
