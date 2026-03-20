"""
Vision 서비스 공용 유틸리티.

여러 서비스 모듈에서 반복되던 헬퍼 함수를 한곳으로 모아
중복을 제거하고 일관성을 확보한다.
"""
from __future__ import annotations

from datetime import datetime, timezone


def utc_now_iso() -> str:
    """현재 UTC 시각을 ISO 형식 문자열로 반환한다."""
    return datetime.now(timezone.utc).isoformat()
