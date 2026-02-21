import logging
from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from jose import jwt, JWTError
from app.core.config import settings
import structlog

logger = structlog.get_logger()

# Shared logic from K-AIR / Core: Token Verification
def decode_jwt_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None

class TenantMiddleware(BaseHTTPMiddleware):
    """
    Validates JWT and extracts tenant_id, enforcing strictly that requests are not cross-tenant.
    """
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            # Allow health checks
            if request.url.path.startswith("/health"):
                return await call_next(request)
            return JSONResponse({"detail": "Missing Authorization header"}, status_code=401)
        
        token = auth_header.split(" ")[1]
        payload = decode_jwt_token(token)
        
        if not payload or "tenant_id" not in payload:
            # Let Service tokens through if valid
            if token == settings.SERVICE_TOKEN_ORACLE:
                 request.state.tenant_id = "system"
                 request.state.user_role = "system"
                 return await call_next(request)
            return JSONResponse({"detail": "Invalid Token or missing tenant"}, status_code=401)
            
        request.state.tenant_id = payload.get("tenant_id")
        request.state.user_id = payload.get("sub")
        request.state.user_role = payload.get("role")
        
        return await call_next(request)
