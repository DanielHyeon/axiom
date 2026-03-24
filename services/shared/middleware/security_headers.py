"""보안 헤더 미들웨어 — 모든 HTTP 응답에 표준 보안 헤더를 추가한다.

추가되는 헤더:
- X-Content-Type-Options: nosniff  → 브라우저가 MIME 타입을 추측하지 못하게 한다
- X-Frame-Options: DENY            → 클릭재킹(iframe 삽입) 공격을 방지한다
- Referrer-Policy                  → 외부로 보내는 Referer 정보를 최소화한다
- Permissions-Policy               → 브라우저 기능(카메라, 마이크 등) 사용을 제한한다
- Content-Security-Policy-Report-Only → 위반 시 차단하지 않고 보고만 한다 (Phase 1)
- Strict-Transport-Security        → HTTPS 전용 접속을 강제한다 (프록시 뒤에서만)
- Cache-Control                    → API 응답 캐시를 방지한다
- X-Request-Id                     → 요청 추적용 고유 ID를 전달한다

Sprint 1 구현 완료.
"""
from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """모든 응답에 보안 헤더를 붙여주는 미들웨어.

    사용법:
        app.add_middleware(SecurityHeadersMiddleware, allowed_connect_src="'self' http://localhost:9001")

    Feature Flag:
        FF_CSP_ENFORCE=true → Content-Security-Policy (차단 모드)로 전환
        FF_CSP_ENFORCE=false (기본값) → Content-Security-Policy-Report-Only 유지

    Args:
        app: FastAPI(또는 Starlette) 앱 인스턴스
        allowed_connect_src: CSP connect-src 값 — 서비스마다 허용할 URL이 다르므로 주입 가능
    """

    def __init__(self, app, allowed_connect_src: str = "'self'") -> None:  # noqa: D107
        super().__init__(app)
        # CSP 정책을 미리 만들어 둔다 (요청마다 문자열 조합하지 않기 위해)
        self._csp = (
            f"default-src 'self'; "
            f"script-src 'self'; "
            f"style-src 'self' 'unsafe-inline'; "
            f"img-src 'self' data:; "
            f"font-src 'self'; "
            f"object-src 'none'; "
            f"base-uri 'self'; "
            f"connect-src {allowed_connect_src}; "
            f"frame-ancestors 'none'"
        )

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """요청을 처리한 뒤 응답에 보안 헤더를 추가한다."""
        # 요청 ID가 없으면 새로 생성한다 (다른 미들웨어가 먼저 넣었을 수도 있음)
        request_id = request.headers.get("X-Request-Id") or f"req-{uuid.uuid4().hex}"

        response: Response = await call_next(request)

        # ── 1) MIME 스니핑 방지 ──
        response.headers["X-Content-Type-Options"] = "nosniff"

        # ── 2) 클릭재킹 방지 (iframe 삽입 차단) ──
        response.headers["X-Frame-Options"] = "DENY"

        # ── 3) 외부로 보내는 Referer 정보 최소화 ──
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # ── 4) 브라우저 기능(카메라, 마이크 등) 사용 제한 ──
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )

        # ── 5) CSP — Feature Flag(FF_CSP_ENFORCE)로 enforcing/report-only 전환 ──
        from shared.utils.feature_flags import is_enabled  # 지연 임포트 (순환 방지)
        if is_enabled("CSP_ENFORCE"):
            # 차단 모드: 위반 시 리소스 로드를 차단한다
            response.headers["Content-Security-Policy"] = self._csp
        else:
            # 보고 모드: 위반 시 차단하지 않고 보고만 한다 (Phase 1 기본값)
            response.headers["Content-Security-Policy-Report-Only"] = self._csp

        # ── 6) HSTS — 리버스 프록시가 HTTPS를 알려줄 때만 설정 ──
        forwarded_proto = request.headers.get("X-Forwarded-Proto", "")
        if forwarded_proto == "https":
            # max-age 1년(31536000초), 서브도메인 포함
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        # ── 7) API 응답 캐시 방지 (헬스체크/메트릭은 제외) ──
        path = request.url.path
        if not path.startswith(("/health", "/metrics")):
            response.headers["Cache-Control"] = "no-store"

        # ── 8) 요청 추적용 ID 전달 ──
        response.headers["X-Request-Id"] = request_id

        return response
