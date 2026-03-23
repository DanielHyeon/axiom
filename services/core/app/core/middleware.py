from contextvars import ContextVar
import logging
import time
import uuid

from app.core.tenant_context import _workspace_id_header

logger = logging.getLogger("axiom.core")

_tenant_id: ContextVar[str] = ContextVar("tenant_id", default="")
_request_id: ContextVar[str] = ContextVar("request_id", default="")


def get_current_tenant_id() -> str:
    return _tenant_id.get()


def get_current_request_id() -> str:
    return _request_id.get()


def get_current_workspace_id() -> str:
    """미들웨어가 추출한 X-Axiom-Workspace-Id 헤더 원본값."""
    return _workspace_id_header.get()


class TenantMiddleware:
    """X-Tenant-Id + X-Axiom-Workspace-Id 헤더 추출 미들웨어.

    workspace_id는 여기서 추출만 하고, 실제 membership 검증은
    서비스 레이어(Phase 1 GovernanceService)에서 수행한다.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in scope.get("headers", [])
        }
        tenant_id = (
            headers.get("x-tenant-id")
            or (headers.get("x-forwarded-host", "").split(".")[0] if headers.get("x-forwarded-host") else "")
            or "default"
        )
        # Phase 0: workspace 헤더 추출 (검증은 Phase 1에서)
        # UUID는 최대 36자 — 메모리 남용 방지를 위해 64자로 제한
        workspace_id_raw = headers.get("x-axiom-workspace-id", "")[:64]

        tenant_token = _tenant_id.set(tenant_id)
        ws_token = _workspace_id_header.set(workspace_id_raw)
        try:
            await self.app(scope, receive, send)
        finally:
            _tenant_id.reset(tenant_token)
            _workspace_id_header.reset(ws_token)


class RequestIdMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in scope.get("headers", [])
        }
        request_id = headers.get("x-request-id", str(uuid.uuid4()))
        token = _request_id.set(request_id)
        start = time.time()
        status_code = 500

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 500)
                raw_headers = list(message.get("headers", []))
                raw_headers.append((b"x-request-id", request_id.encode()))
                duration = f"{(time.time() - start):.3f}s"
                raw_headers.append((b"x-response-time", duration.encode()))
                message["headers"] = raw_headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration = time.time() - start
            logger.info(
                f"{scope.get('method')} {scope.get('path')} "
                f"status={status_code} duration={duration:.3f}s tenant={get_current_tenant_id()}"
            )
            _request_id.reset(token)
