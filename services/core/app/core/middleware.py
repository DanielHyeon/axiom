from contextvars import ContextVar
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import uuid
import time
import logging

logger = logging.getLogger("axiom.core")

_tenant_id: ContextVar[str] = ContextVar("tenant_id", default="")
_request_id: ContextVar[str] = ContextVar("request_id", default="")

def get_current_tenant_id() -> str:
    return _tenant_id.get()

def get_current_request_id() -> str:
    return _request_id.get()

class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        tenant_id = (
            request.headers.get("X-Tenant-Id") or
            request.headers.get("X-Forwarded-Host", "").split(".")[0] or
            "default"
        )
        token = _tenant_id.set(tenant_id)
        
        try:
            response = await call_next(request)
            return response
        finally:
            _tenant_id.reset(token)

class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get(
            "X-Request-Id", str(uuid.uuid4())
        )
        token = _request_id.set(request_id)
        start = time.time()
        
        try:
            response = await call_next(request)
            duration = time.time() - start
            response.headers["X-Request-Id"] = request_id
            response.headers["X-Response-Time"] = f"{duration:.3f}s"
            
            logger.info(
                f"{request.method} {request.url.path} "
                f"status={response.status_code} "
                f"duration={duration:.3f}s "
                f"tenant={get_current_tenant_id()}"
            )
            return response
        finally:
            _request_id.reset(token)
