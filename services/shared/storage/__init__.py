"""스냅샷 Object Storage 폴백 모듈.

DB 장애 시 마지막 활성 스냅샷을 S3/EFS/로컬 파일에서 서빙한다.
전체 구현은 별도 설계 문서 기반으로 진행 (L effort).
"""
from .snapshot_fallback import (  # noqa: F401
    SnapshotFallbackStore,
    LocalFileFallback,
)

__all__ = ["SnapshotFallbackStore", "LocalFileFallback"]
