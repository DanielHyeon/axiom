"""구조화 액세스 로그 미들웨어 — 모든 HTTP 요청/응답을 JSON으로 기록한다.

사용법:
    app = FastAPI()
    app.add_middleware(lambda app: AccessLogMiddleware(app, service_name="weaver"))

기록하는 필드:
    request_id, tenant_id, user_id, method, path, status_code,
    duration_ms, client_ip, service_name

설계 결정:
    - raw ASGI 방식 (BaseHTTPMiddleware는 body 읽기 시 데드락 위험이 있어 사용하지 않는다)
    - /health, /metrics 경로는 로그를 남기지 않는다 (로그 폭탄 방지)
    - Authorization, Cookie 헤더는 마스킹하여 민감 정보를 보호한다
    - try/finally로 감싸서 예외가 발생해도 반드시 로그를 남긴다
    - 상태 코드별 로그 레벨: 5xx=ERROR, 4xx=WARNING, 나머지=INFO
"""

from __future__ import annotations

import json
import logging
import time
from typing import Set

from .request_id import get_request_id

# --- 이 미들웨어 전용 로거 ---
logger = logging.getLogger("axiom.access")

# --- 로그를 남기지 않을 경로 (헬스체크, 메트릭 등) ---
_SKIP_PATHS: Set[str] = {"/health", "/healthz", "/metrics", "/readiness", "/liveness"}

# --- 마스킹할 헤더 이름 (소문자) ---
_MASKED_HEADERS: Set[str] = {"authorization", "cookie", "set-cookie", "x-api-key"}


def _mask_headers(raw_headers: list[tuple[bytes, bytes]]) -> dict[str, str]:
    """요청 헤더를 딕셔너리로 변환하면서 민감 헤더는 '***'로 가린다.

    예: {"authorization": "***", "content-type": "application/json"}
    """
    result: dict[str, str] = {}
    for key_bytes, value_bytes in raw_headers:
        key = key_bytes.decode("latin-1").lower()
        if key in _MASKED_HEADERS:
            result[key] = "***"
        else:
            result[key] = value_bytes.decode("latin-1", errors="replace")
    return result


def _extract_client_ip(scope: dict) -> str:
    """클라이언트 IP를 추출한다.

    X-Forwarded-For 헤더가 있으면 첫 번째 IP를 사용하고,
    없으면 ASGI scope["client"]에서 가져온다.
    """
    # 헤더에서 X-Forwarded-For 확인
    for key, value in scope.get("headers", []):
        if key.decode("latin-1").lower() == "x-forwarded-for":
            # 쉼표로 구분된 IP 목록 중 첫 번째가 진짜 클라이언트
            return value.decode("latin-1").split(",")[0].strip()

    # 프록시가 없으면 직접 연결 IP 사용
    client = scope.get("client")
    if client:
        return client[0]
    return "unknown"


class AccessLogMiddleware:
    """ASGI 미들웨어 — 모든 HTTP 요청을 JSON 구조화 로그로 남긴다.

    동작 순서:
    1. 요청 시작 시간을 기록한다
    2. 경로가 /health, /metrics이면 로그 없이 통과시킨다
    3. 응답 상태 코드를 가로채서 저장한다
    4. 요청 완료(또는 예외) 후 JSON 로그를 남긴다
    5. 상태 코드에 따라 로그 레벨을 다르게 설정한다
    """

    def __init__(self, app, service_name: str = "unknown"):
        # ASGI 앱 체인의 다음 앱
        self.app = app
        # 어떤 서비스인지 로그에 기록 (예: "weaver", "oracle")
        self.service_name = service_name

    async def __call__(self, scope, receive, send):
        # HTTP가 아닌 요청 (websocket, lifespan 등)은 그냥 통과
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        # --- 경로 추출 ---
        path: str = scope.get("path", "")

        # /health, /metrics 같은 경로는 로그를 남기지 않는다 (노이즈 방지)
        if path in _SKIP_PATHS:
            await self.app(scope, receive, send)
            return

        # --- 요청 정보 미리 뽑아두기 ---
        method: str = scope.get("method", "?")
        raw_headers = scope.get("headers", [])
        client_ip = _extract_client_ip(scope)

        # 헤더를 딕셔너리로 변환 (소문자 키)
        headers_dict: dict[str, str] = {}
        for key_bytes, value_bytes in raw_headers:
            headers_dict[key_bytes.decode("latin-1").lower()] = value_bytes.decode(
                "latin-1", errors="replace"
            )

        tenant_id = headers_dict.get("x-tenant-id", "-")
        # user_id는 인증 미들웨어가 scope["state"]에 넣어주는 값을 쓴다
        state = scope.get("state", {})
        user_id = state.get("user_id", "-")

        # --- 응답 상태 코드를 가로채기 위한 변수 ---
        status_code = 500  # 기본값: 예외 발생 시 500으로 기록
        start = time.monotonic()

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                # 응답 시작 메시지에서 상태 코드를 뽑아둔다
                status_code = message.get("status", 500)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            # 예외가 발생하면 status_code는 기본값 500이 된다
            raise
        finally:
            # --- 반드시 로그를 남긴다 (예외가 발생해도) ---
            duration_ms = round((time.monotonic() - start) * 1000, 2)

            # scope["state"]에서 user_id 재확인 (인증 미들웨어가 나중에 설정할 수 있음)
            state = scope.get("state", {})
            user_id_final = state.get("user_id", user_id)
            request_id = get_request_id() or state.get("request_id", "-")

            # 쿼리스트링 포함 경로
            query_string = scope.get("query_string", b"").decode("latin-1")
            full_path = f"{path}?{query_string}" if query_string else path

            # --- JSON 구조화 로그 ---
            log_data = {
                "event": "http_request",
                "request_id": request_id,
                "tenant_id": tenant_id,
                "user_id": user_id_final,
                "method": method,
                "path": full_path,
                "status_code": status_code,
                "duration_ms": duration_ms,
                "client_ip": client_ip,
                "service": self.service_name,
                "headers": _mask_headers(raw_headers),
            }

            log_message = json.dumps(log_data, ensure_ascii=False)

            # --- 상태 코드에 따라 로그 레벨 결정 ---
            if status_code >= 500:
                logger.error(log_message)
            elif status_code >= 400:
                logger.warning(log_message)
            else:
                logger.info(log_message)
