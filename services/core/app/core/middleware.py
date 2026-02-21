from contextvars import ContextVar
import logging
import time
import uuid


logger = logging.getLogger("axiom.core")

_tenant_id: ContextVar[str] = ContextVar("tenant_id", default="")
_request_id: ContextVar[str] = ContextVar("request_id", default="")


def get_current_tenant_id() -> str:
    return _tenant_id.get()


def get_current_request_id() -> str:
    return _request_id.get()


class TenantMiddleware:
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
        token = _tenant_id.set(tenant_id)
        try:
            await self.app(scope, receive, send)
        finally:
            _tenant_id.reset(token)


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
