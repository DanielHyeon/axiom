"""AXIOM_XXXX 에러 코드 체계.

프론트엔드, 백엔드, 운영 팀이 동일한 에러 분류를 사용하여
로그 검색, 알림 규칙, 사용자 메시지 매핑이 일관되게 동작한다.

에러 코드 범위:
- 1xxx: 인증/인가 (토큰 만료, 권한 부족 등)
- 2xxx: 입력 검증 (필수 필드 누락, 형식 오류 등)
- 3xxx: 비즈니스 로직 (리소스 미발견, 상태 전이 오류 등)
- 4xxx: 외부 서비스 (DB 연결 실패, LLM 오류 등)
- 5xxx: 시스템 (내부 오류, 레이트 리밋 등)
- 6xxx: 시맨틱 레이어 (예약 — 계약 위반, 스냅샷 불일치, 온톨로지 충돌)
- 7xxx: 데이터 품질 (예약 — 품질 게이트 차단, 신선도 SLA 위반, 드리프트)
- 8xxx: NL2SQL/Oracle (예약 — AST 검증 실패, 팬아웃 위험, 의도 분류 실패)

사용 예시:
    raise AxiomError(
        code=AxiomErrorCode.BIZ_RESOURCE_NOT_FOUND,
        detail="테넌트 T-001을 찾을 수 없습니다",
        status_code=404,
    )
"""

from __future__ import annotations

import contextlib
from enum import Enum
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


class AxiomErrorCode(str, Enum):
    """전 서비스 공용 에러 코드.

    각 범위(1xxx~5xxx)는 도메인별로 구분되어 있어
    에러 코드만 보고 어떤 종류의 문제인지 즉시 파악할 수 있다.
    """

    # --- 1xxx: 인증/인가 ---
    AUTH_TOKEN_EXPIRED = "AXIOM_1001"       # 토큰 유효기간 만료
    AUTH_TOKEN_INVALID = "AXIOM_1002"       # 토큰 디코딩 실패 또는 변조
    AUTH_PERMISSION_DENIED = "AXIOM_1003"   # 역할(role)에 해당 권한 없음
    AUTH_TENANT_MISMATCH = "AXIOM_1004"     # 요청 테넌트 =/= 토큰 테넌트

    # --- 2xxx: 입력 검증 ---
    VALIDATION_REQUIRED_FIELD = "AXIOM_2001"       # 필수 필드 누락
    VALIDATION_INVALID_FORMAT = "AXIOM_2002"       # 형식 오류 (이메일, UUID 등)
    VALIDATION_CONSTRAINT_VIOLATION = "AXIOM_2003" # 제약 조건 위반 (길이, 범위 등)

    # --- 3xxx: 비즈니스 로직 ---
    BIZ_RESOURCE_NOT_FOUND = "AXIOM_3001"        # 요청한 리소스 없음
    BIZ_RESOURCE_CONFLICT = "AXIOM_3002"         # 중복 생성 등 충돌
    BIZ_STATE_TRANSITION_DENIED = "AXIOM_3003"   # 허용되지 않는 상태 전이
    BIZ_QUOTA_EXCEEDED = "AXIOM_3004"            # 할당량 초과

    # --- 4xxx: 외부 서비스 ---
    EXT_SERVICE_UNAVAILABLE = "AXIOM_4001"   # 외부 서비스 접속 불가
    EXT_SERVICE_TIMEOUT = "AXIOM_4002"       # 외부 서비스 응답 시간 초과
    EXT_LLM_ERROR = "AXIOM_4003"             # LLM API 호출 실패
    EXT_DB_ERROR = "AXIOM_4004"              # 데이터베이스 쿼리/연결 오류

    # --- 5xxx: 시스템 ---
    SYS_INTERNAL_ERROR = "AXIOM_5001"    # 예상치 못한 내부 오류
    SYS_RATE_LIMITED = "AXIOM_5002"      # 요청 속도 제한 초과
    SYS_MAINTENANCE = "AXIOM_5003"       # 시스템 점검 중


class AxiomError(HTTPException):
    """표준 Axiom 에러 응답.

    FastAPI의 HTTPException을 확장하여 에러 코드(AxiomErrorCode)를 포함한다.
    axiom_error_handler와 함께 사용하면 일관된 JSON 응답을 생성한다.

    Args:
        code: AXIOM_XXXX 에러 코드 (AxiomErrorCode enum 값)
        detail: 사람이 읽을 수 있는 에러 메시지
        status_code: HTTP 상태 코드 (기본 400)
        extra: 응답에 포함할 추가 데이터 (디버깅 힌트 등)
    """

    def __init__(
        self,
        code: AxiomErrorCode,
        detail: str,
        status_code: int = 400,
        extra: dict[str, Any] | None = None,
    ):
        self.error_code = code
        self.extra = extra or {}
        super().__init__(status_code=status_code, detail=detail)


async def axiom_error_handler(request: Request, exc: AxiomError) -> JSONResponse:
    """AxiomError를 표준 JSON 응답으로 변환하는 핸들러.

    FastAPI app에 등록하여 사용한다:
        app.add_exception_handler(AxiomError, axiom_error_handler)

    응답 형식:
    {
        "success": false,
        "error": {
            "code": "AXIOM_3001",
            "message": "테넌트 T-001을 찾을 수 없습니다"
        },
        "request_id": "abc123..."
    }
    """
    # request.state.request_id 또는 ContextVar에서 request_id를 가져온다
    # (raw ASGI 미들웨어는 ContextVar만 설정하고, BaseHTTPMiddleware는 state도 설정할 수 있다)
    request_id = getattr(request.state, "request_id", None)
    if not request_id:
        with contextlib.suppress(ImportError):
            from shared.middleware.request_id import get_request_id
            request_id = get_request_id() or None

    body: dict[str, Any] = {
        "success": False,
        "error": {
            "code": exc.error_code.value,
            "message": exc.detail,
        },
        "request_id": request_id,
    }

    # 추가 데이터가 있으면 error 객체에 병합 (hint, retryable 등)
    if exc.extra:
        body["error"].update(exc.extra)

    return JSONResponse(status_code=exc.status_code, content=body)
