"""전 서비스 공통 Request-Id 미들웨어.

요청에 X-Request-Id 헤더가 있으면 그대로 사용하고,
없으면 새로 생성(uuid4)하여 응답 헤더에 포함한다.
이 ID를 이용해 로그에서 전 서비스 요청 추적이 가능하다.

구현 방식:
- raw ASGI 프로토콜을 직접 사용한다.
  (BaseHTTPMiddleware는 request body 읽기 시 데드락이 발생할 수 있어 사용하지 않는다.)
- ContextVar에 request_id를 저장하여 어디서든 get_request_id()로 접근 가능하다.
- 응답 헤더에 X-Request-Id와 X-Response-Time을 자동 추가한다.
"""

from __future__ import annotations

import time
import uuid
from contextvars import ContextVar

# --- ContextVar: 어디서든 현재 요청 ID를 읽을 수 있다 ---
_request_id_var: ContextVar[str] = ContextVar("axiom_shared_request_id", default="")


def get_request_id() -> str:
    """현재 요청의 Request-Id를 반환한다.

    미들웨어가 설정한 ContextVar 값을 읽는다.
    미들웨어 밖에서 호출하면 빈 문자열을 반환한다.
    """
    return _request_id_var.get()


class RequestIdMiddleware:
    """ASGI 미들웨어 — 요청마다 고유 ID를 부여하고 응답에 포함한다.

    동작 순서:
    1. 요청 헤더에서 X-Request-Id를 찾는다 (서비스 간 호출 시 전파용)
    2. 없으면 uuid4로 새로 생성한다
    3. ContextVar에 저장하여 로깅 등에서 사용할 수 있게 한다
    4. 응답 헤더에 X-Request-Id, X-Response-Time을 추가한다
    5. 요청 완료 후 ContextVar를 원래 값으로 복원한다
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        # HTTP 요청이 아니면 (websocket, lifespan 등) 그냥 통과
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        # --- 1) 요청 헤더에서 X-Request-Id 추출 ---
        headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in scope.get("headers", [])
        }
        request_id = headers.get("x-request-id") or uuid.uuid4().hex

        # --- 2) ContextVar + scope["state"]에 저장 ---
        # scope["state"]에도 넣어야 request.state.request_id로 접근 가능
        token = _request_id_var.set(request_id)
        scope.setdefault("state", {})
        scope["state"]["request_id"] = request_id
        start = time.monotonic()

        # --- 3) 응답 헤더에 X-Request-Id, X-Response-Time 추가 ---
        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                raw_headers = list(message.get("headers", []))
                raw_headers.append(
                    (b"x-request-id", request_id.encode("latin-1"))
                )
                elapsed = time.monotonic() - start
                raw_headers.append(
                    (b"x-response-time", f"{elapsed:.3f}s".encode("latin-1"))
                )
                message = {**message, "headers": raw_headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_headers)
        finally:
            # --- 4) ContextVar 복원 (다음 요청에 이전 값이 남지 않도록) ---
            _request_id_var.reset(token)
