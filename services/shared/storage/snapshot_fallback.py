"""스냅샷 Object Storage 폴백 인터페이스.

DB 장애 시 마지막 활성 스냅샷을 S3/EFS에서 서빙한다.
전체 구현은 별도 설계 문서 기반으로 진행 (L effort).

아키텍처:
    ┌──────────┐    정상 시    ┌────────────┐
    │  Oracle  │ ──────────→ │  Synapse DB │
    └──────────┘             └────────────┘
         │                         ✗ DB 장애
         │   폴백 경로     ┌────────────────┐
         └──────────────→ │  Fallback Store │
                          │ (S3/EFS/Local)  │
                          └────────────────┘

사용 예시:
    fallback = LocalFileFallback(base_dir="/tmp/snapshot-fallback")
    await fallback.save_snapshot("snap-20260324-abc12345", artifacts)
    data = await fallback.load_snapshot("snap-20260324-abc12345")
"""
from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()


class SnapshotFallbackStore(ABC):
    """스냅샷 폴백 저장소 인터페이스 — 모든 구현체가 따라야 하는 계약.

    save_snapshot: 스냅샷을 폴백 저장소에 저장
    load_snapshot: 특정 버전의 스냅샷을 폴백 저장소에서 로드
    get_latest_active: 가장 최근 활성 스냅샷을 반환 (DB 장애 시 사용)
    """

    @abstractmethod
    async def save_snapshot(self, snapshot_version: str, artifacts: dict) -> None:
        """스냅샷 아티팩트를 폴백 저장소에 저장한다.

        Args:
            snapshot_version: 스냅샷 버전 (예: "snap-20260324-abc12345")
            artifacts: 아티팩트 딕셔너리 {artifact_type: artifact_json}
        """
        ...

    @abstractmethod
    async def load_snapshot(self, snapshot_version: str) -> dict | None:
        """특정 버전의 스냅샷을 폴백 저장소에서 로드한다.

        Args:
            snapshot_version: 스냅샷 버전

        Returns:
            아티팩트 딕셔너리 또는 None (존재하지 않으면)
        """
        ...

    @abstractmethod
    async def get_latest_active(self) -> dict | None:
        """가장 최근 활성 스냅샷을 반환한다.

        DB가 완전히 불통일 때 사용하는 최후의 수단.

        Returns:
            {"snapshot_version": "...", "artifacts": {...}} 또는 None
        """
        ...


class LocalFileFallback(SnapshotFallbackStore):
    """로컬 파일 기반 폴백 — 단일 인스턴스 개발/테스트용.

    프로덕션에서는 S3Fallback 또는 EFSFallback을 사용해야 한다.
    이 구현체는 로컬 디스크에 JSON 파일로 스냅샷을 저장한다.

    디렉토리 구조:
        base_dir/
            snap-20260324-abc12345.json
            snap-20260325-def67890.json
            _latest_active.json  ← 가장 최근 활성 버전 포인터
    """

    def __init__(self, base_dir: str = "/tmp/axiom-snapshot-fallback"):
        self._base_dir = Path(base_dir)

    def _ensure_dir(self) -> None:
        """저장 디렉토리가 없으면 생성한다."""
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def _snapshot_path(self, version: str) -> Path:
        """스냅샷 파일 경로를 반환한다."""
        # 파일명에 위험한 문자가 들어가지 않도록 방어
        safe_name = version.replace("/", "_").replace("..", "_")
        return self._base_dir / f"{safe_name}.json"

    def _latest_pointer_path(self) -> Path:
        """최신 활성 버전 포인터 파일 경로."""
        return self._base_dir / "_latest_active.json"

    async def save_snapshot(self, snapshot_version: str, artifacts: dict) -> None:
        """스냅샷을 로컬 JSON 파일로 저장한다."""
        self._ensure_dir()
        payload: dict[str, Any] = {
            "snapshot_version": snapshot_version,
            "artifacts": artifacts,
        }
        path = self._snapshot_path(snapshot_version)
        path.write_text(
            json.dumps(payload, default=str, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        # 최신 활성 포인터 갱신
        self._latest_pointer_path().write_text(
            json.dumps({"snapshot_version": snapshot_version}, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info(
            "snapshot_fallback_saved",
            snapshot_version=snapshot_version,
            path=str(path),
        )

    async def load_snapshot(self, snapshot_version: str) -> dict | None:
        """로컬 파일에서 스냅샷을 로드한다."""
        path = self._snapshot_path(snapshot_version)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("snapshot_fallback_load_error", error=str(exc), path=str(path))
            return None

    async def get_latest_active(self) -> dict | None:
        """최신 활성 포인터를 읽고, 해당 스냅샷을 반환한다."""
        pointer_path = self._latest_pointer_path()
        if not pointer_path.exists():
            return None
        try:
            pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
            version = pointer.get("snapshot_version")
            if not version:
                return None
            return await self.load_snapshot(version)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("snapshot_fallback_pointer_error", error=str(exc))
            return None


# ── 추후 구현 예정 (별도 설계 문서 기반) ──
# class S3Fallback(SnapshotFallbackStore):
#     """AWS S3 기반 폴백 — 프로덕션 멀티 인스턴스 환경용"""
#     ...

# class EFSFallback(SnapshotFallbackStore):
#     """AWS EFS 기반 폴백 — 프로덕션 공유 파일시스템용"""
#     ...
