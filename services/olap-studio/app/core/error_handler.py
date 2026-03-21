"""전역 예외 핸들러 — 일관된 에러 응답 보장.

FastAPI의 기본 예외 핸들러를 오버라이드하여
Axiom 표준 에러 포맷으로 변환한다.
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging_config import get_logger

logger = get_logger(__name__)


def register_error_handlers(app: FastAPI) -> None:
    """FastAPI 앱에 전역 예외 핸들러를 등록한다."""

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException,
    ) -> JSONResponse:
        """HTTP 예외 → Axiom 표준 에러 포맷.

        4xx는 클라이언트 에러로 debug 수준, 5xx는 error 수준으로 기록한다.
        """
        if exc.status_code < 500:
            logger.debug(
                "http_client_error",
                status=exc.status_code,
                detail=str(exc.detail),
                path=request.url.path,
            )
        else:
            logger.error(
                "http_server_error",
                status=exc.status_code,
                detail=str(exc.detail),
                path=request.url.path,
            )

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {
                    "code": _status_to_code(exc.status_code),
                    "message": str(exc.detail),
                },
            },
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError,
    ) -> JSONResponse:
        """Pydantic 검증 오류 → 422 표준 에러.

        각 필드별 에러 메시지를 details.errors 배열로 포함한다.
        """
        errors = exc.errors()
        logger.debug(
            "validation_error",
            path=request.url.path,
            error_count=len(errors),
        )

        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "요청 데이터 검증 실패",
                    "details": {
                        "errors": [
                            {
                                "field": ".".join(
                                    str(loc) for loc in e.get("loc", [])
                                ),
                                "message": e.get("msg", ""),
                                "type": e.get("type", ""),
                            }
                            for e in errors
                        ],
                    },
                },
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception,
    ) -> JSONResponse:
        """처리되지 않은 예외 → 500 일반 에러.

        내부 에러 정보를 클라이언트에 노출하지 않고 로그에만 기록한다.
        """
        logger.error(
            "unhandled_exception",
            path=request.url.path,
            error=str(exc),
            exc_info=True,
        )

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "서버 내부 오류가 발생했습니다",
                },
            },
        )


def _status_to_code(status: int) -> str:
    """HTTP 상태 코드를 에러 코드 문자열로 변환한다."""
    codes = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMITED",
        500: "INTERNAL_ERROR",
        502: "BAD_GATEWAY",
        503: "SERVICE_UNAVAILABLE",
    }
    return codes.get(status, f"HTTP_{status}")
