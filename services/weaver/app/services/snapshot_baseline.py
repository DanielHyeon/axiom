"""G33a: Physical Snapshot Baseline — 구조 해시 스냅샷 + 변경 감지.

메타데이터 추출 완료 시 테이블별 structure_hash를 스냅샷으로 저장하고,
이전 스냅샷과 비교하여 추가/삭제/구조변경을 감지한다.

설계 원칙:
- LKG(Last Known Good) 스냅샷을 기준으로 변경 사실만 기록 (severity 판정은 Phase 4 SSDD)
- Phase 4 SSDD(G33b)의 DriftDetector가 이 스냅샷을 LKG로 사용
- extract_metadata_stream의 complete 시점에 자동 호출
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.services.adapters.normalization import (
    StandardColumnMetadata,
    StandardMetadata,
    StandardSchemaMetadata,
    StandardTableMetadata,
)

logger = logging.getLogger("axiom.weaver.snapshot")


# ── 변경 유형 ── #

class ChangeType(str, Enum):
    """스키마 변경 유형 — 사실만 기록, severity는 Phase 4 SSDD에서 판정"""
    TABLE_ADDED = "table_added"
    TABLE_REMOVED = "table_removed"
    TABLE_STRUCTURE_CHANGED = "table_structure_changed"  # 컬럼 추가/삭제/타입변경
    COLUMN_ADDED = "column_added"
    COLUMN_REMOVED = "column_removed"
    COLUMN_TYPE_CHANGED = "column_type_changed"
    COLUMN_NULLABLE_CHANGED = "column_nullable_changed"


# ── 모델 ── #

class TableHash(BaseModel):
    """테이블별 구조 해시"""
    table_name: str
    schema_name: str
    structure_hash: str  # SHA256(정렬된 컬럼명:타입:nullable:pk)
    column_count: int
    columns_snapshot: list[dict] = Field(default_factory=list)  # 컬럼 상세 (diff용)


class SchemaSnapshot(BaseModel):
    """특정 시점의 전체 메타데이터 스냅샷"""
    snapshot_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    datasource_name: str
    tenant_id: str = ""
    table_hashes: list[TableHash] = Field(default_factory=list)
    total_tables: int = 0
    total_columns: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SimpleChange(BaseModel):
    """변경 사실 기록 — severity 없이 사실만"""
    change_type: ChangeType
    schema_name: str = ""
    table_name: str = ""
    column_name: str | None = None
    old_value: str | None = None  # 변경 전 (타입, 해시 등)
    new_value: str | None = None  # 변경 후
    description: str = ""


class ChangeReport(BaseModel):
    """스냅샷 비교 결과"""
    datasource_name: str
    previous_snapshot_id: str | None = None
    current_snapshot_id: str
    changes: list[SimpleChange] = Field(default_factory=list)
    has_changes: bool = False
    compared_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── 서비스 ── #

class SchemaSnapshotService:
    """메타데이터 추출 완료 시 구조 해시 스냅샷 저장 + 변경 감지.

    in-memory 저장소로 시작 — Phase 2에서 PostgreSQL weaver.schema_snapshots로 전환.
    """

    def __init__(self) -> None:
        # (tenant_id:datasource_name) → 스냅샷 이력 (최신순) — N-1: 테넌트 격리
        self._snapshots: dict[str, list[SchemaSnapshot]] = {}
        # M-1: 최대 datasource 키 수 제한
        self._max_datasources = 500

    def _key(self, tenant_id: str, datasource_name: str) -> str:
        """테넌트 격리 키 생성 (N-1 반영)"""
        return f"{tenant_id}:{datasource_name}"

    async def save_snapshot(
        self,
        datasource_name: str,
        metadata: StandardMetadata,
        tenant_id: str = "",
    ) -> str:
        """현재 메타데이터의 테이블별 structure_hash 저장 → snapshot_id 반환"""
        table_hashes: list[TableHash] = []
        total_columns = 0

        for schema in metadata.schemas:
            for table in schema.tables:
                h = self._compute_table_hash(table, schema.schema_name)
                table_hashes.append(h)
                total_columns += h.column_count

        snapshot = SchemaSnapshot(
            datasource_name=datasource_name,
            tenant_id=tenant_id,
            table_hashes=table_hashes,
            total_tables=len(table_hashes),
            total_columns=total_columns,
        )

        key = self._key(tenant_id, datasource_name)
        # 이력에 추가 (최신이 앞)
        history = self._snapshots.setdefault(key, [])
        history.insert(0, snapshot)

        # 최대 50개 스냅샷 유지
        if len(history) > 50:
            self._snapshots[key] = history[:50]

        # M-1: 전체 datasource 키 수 제한
        if len(self._snapshots) > self._max_datasources:
            oldest_key = min(
                self._snapshots,
                key=lambda k: self._snapshots[k][0].created_at
                if self._snapshots[k]
                else datetime.min.replace(tzinfo=timezone.utc),
            )
            del self._snapshots[oldest_key]
            logger.warning("스냅샷 저장소 용량 초과 — 가장 오래된 키 제거: %s", oldest_key)

        logger.info(
            "스냅샷 저장: %s (id=%s, tables=%d, columns=%d)",
            datasource_name, snapshot.snapshot_id[:8],
            snapshot.total_tables, snapshot.total_columns,
        )
        return snapshot.snapshot_id

    async def get_last_snapshot(
        self, datasource_name: str, tenant_id: str = "",
    ) -> SchemaSnapshot | None:
        """마지막 LKG 스냅샷 조회"""
        key = self._key(tenant_id, datasource_name)
        history = self._snapshots.get(key, [])
        return history[0] if history else None

    async def get_snapshot_history(
        self,
        datasource_name: str,
        tenant_id: str = "",
        limit: int = 10,
    ) -> list[SchemaSnapshot]:
        """스냅샷 이력 조회 (최신순)"""
        key = self._key(tenant_id, datasource_name)
        history = self._snapshots.get(key, [])
        return history[:limit]

    async def detect_changes(
        self,
        datasource_name: str,
        new_metadata: StandardMetadata,
        tenant_id: str = "",
    ) -> ChangeReport:
        """이전 스냅샷 대비 변경 감지 — 추가/삭제/구조변경 목록.

        Phase 4 SSDD(G33b)의 DriftDetector 입력 데이터로 재활용됨.
        """
        previous = await self.get_last_snapshot(datasource_name, tenant_id)

        # 새 스냅샷 생성 (아직 저장하지 않음 — 호출자가 save_snapshot 결정)
        new_hashes: dict[str, TableHash] = {}
        for schema in new_metadata.schemas:
            for table in schema.tables:
                h = self._compute_table_hash(table, schema.schema_name)
                key = f"{schema.schema_name}.{table.name}"
                new_hashes[key] = h

        current_snapshot_id = uuid.uuid4().hex
        changes: list[SimpleChange] = []

        if previous is None:
            # 첫 스냅샷 — 모든 테이블이 "추가"
            for key, h in new_hashes.items():
                changes.append(SimpleChange(
                    change_type=ChangeType.TABLE_ADDED,
                    schema_name=h.schema_name,
                    table_name=h.table_name,
                    description=f"신규 테이블 발견: {key} (컬럼 {h.column_count}개)",
                ))
            return ChangeReport(
                datasource_name=datasource_name,
                current_snapshot_id=current_snapshot_id,
                changes=changes,
                has_changes=bool(changes),
            )

        # 이전 스냅샷과 비교
        old_hashes: dict[str, TableHash] = {
            f"{h.schema_name}.{h.table_name}": h for h in previous.table_hashes
        }

        # 1. 삭제된 테이블
        for key, old_h in old_hashes.items():
            if key not in new_hashes:
                changes.append(SimpleChange(
                    change_type=ChangeType.TABLE_REMOVED,
                    schema_name=old_h.schema_name,
                    table_name=old_h.table_name,
                    description=f"테이블 삭제됨: {key}",
                ))

        # 2. 추가된 테이블 + 구조 변경
        for key, new_h in new_hashes.items():
            old_h = old_hashes.get(key)
            if old_h is None:
                changes.append(SimpleChange(
                    change_type=ChangeType.TABLE_ADDED,
                    schema_name=new_h.schema_name,
                    table_name=new_h.table_name,
                    description=f"신규 테이블: {key} (컬럼 {new_h.column_count}개)",
                ))
            elif old_h.structure_hash != new_h.structure_hash:
                # 구조 변경 — 컬럼 수준 diff
                changes.append(SimpleChange(
                    change_type=ChangeType.TABLE_STRUCTURE_CHANGED,
                    schema_name=new_h.schema_name,
                    table_name=new_h.table_name,
                    old_value=old_h.structure_hash[:16],
                    new_value=new_h.structure_hash[:16],
                    description=f"구조 변경: {key}",
                ))
                # 컬럼 수준 세부 diff
                col_changes = self._diff_columns(old_h, new_h)
                changes.extend(col_changes)

        return ChangeReport(
            datasource_name=datasource_name,
            previous_snapshot_id=previous.snapshot_id,
            current_snapshot_id=current_snapshot_id,
            changes=changes,
            has_changes=bool(changes),
        )

    # ── 내부 메서드 ── #

    def _compute_table_hash(
        self,
        table: StandardTableMetadata,
        schema_name: str,
    ) -> TableHash:
        """테이블 구조 해시 계산 — IdentityResolver와 동일 알고리즘"""
        columns_snapshot = []
        normalized = []
        for c in table.columns:
            col_str = (
                f"{c.name}:{c.data_type}"
                f":{'N' if c.nullable else 'NN'}"
                f":{'PK' if c.is_primary_key else ''}"
            )
            normalized.append(col_str)
            columns_snapshot.append({
                "name": c.name,
                "type": c.data_type,
                "original_type": c.original_type,
                "nullable": c.nullable,
                "is_primary_key": c.is_primary_key,
            })
        normalized.sort()
        structure_hash = hashlib.sha256("|".join(normalized).encode()).hexdigest()

        return TableHash(
            table_name=table.name,
            schema_name=schema_name,
            structure_hash=structure_hash,
            column_count=len(table.columns),
            columns_snapshot=columns_snapshot,
        )

    def _diff_columns(self, old_h: TableHash, new_h: TableHash) -> list[SimpleChange]:
        """컬럼 수준 세부 변경 감지"""
        changes: list[SimpleChange] = []
        old_cols = {c["name"]: c for c in old_h.columns_snapshot}
        new_cols = {c["name"]: c for c in new_h.columns_snapshot}

        # 삭제된 컬럼
        for name in old_cols:
            if name not in new_cols:
                changes.append(SimpleChange(
                    change_type=ChangeType.COLUMN_REMOVED,
                    schema_name=old_h.schema_name,
                    table_name=old_h.table_name,
                    column_name=name,
                    description=f"컬럼 삭제: {name}",
                ))

        # 추가/변경된 컬럼
        for name, new_c in new_cols.items():
            old_c = old_cols.get(name)
            if old_c is None:
                changes.append(SimpleChange(
                    change_type=ChangeType.COLUMN_ADDED,
                    schema_name=new_h.schema_name,
                    table_name=new_h.table_name,
                    column_name=name,
                    new_value=new_c.get("type", ""),
                    description=f"컬럼 추가: {name} ({new_c.get('type', '')})",
                ))
            else:
                # 타입 변경
                if old_c.get("type") != new_c.get("type"):
                    changes.append(SimpleChange(
                        change_type=ChangeType.COLUMN_TYPE_CHANGED,
                        schema_name=new_h.schema_name,
                        table_name=new_h.table_name,
                        column_name=name,
                        old_value=old_c.get("type", ""),
                        new_value=new_c.get("type", ""),
                        description=f"타입 변경: {name} ({old_c.get('type')} → {new_c.get('type')})",
                    ))
                # nullable 변경
                if old_c.get("nullable") != new_c.get("nullable"):
                    changes.append(SimpleChange(
                        change_type=ChangeType.COLUMN_NULLABLE_CHANGED,
                        schema_name=new_h.schema_name,
                        table_name=new_h.table_name,
                        column_name=name,
                        old_value=str(old_c.get("nullable")),
                        new_value=str(new_c.get("nullable")),
                        description=f"nullable 변경: {name} ({old_c.get('nullable')} → {new_c.get('nullable')})",
                    ))

        return changes


# 모듈 수준 싱글톤
snapshot_service = SchemaSnapshotService()
