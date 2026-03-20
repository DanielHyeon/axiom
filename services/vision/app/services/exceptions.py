"""
Vision 서비스 공용 예외 클래스.

여러 서비스 모듈에서 중복 정의되던 예외를 한곳에 모아
import 경로를 통일하고 유지보수성을 높인다.
"""
from __future__ import annotations


class VisionRuntimeError(Exception):
    """Vision 서비스 비즈니스 로직 에러 (error code + message)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class PivotQueryTimeoutError(Exception):
    """피벗 쿼리 30초 타임아웃 (504 QUERY_TIMEOUT)."""
