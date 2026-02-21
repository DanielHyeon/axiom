from jose import JWTError, jwt
from starlette.responses import JSONResponse

from app.core.config import settings


def decode_jwt_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None


class TenantMiddleware:
    """
    ASGI middleware for JWT validation + tenant extraction.
    Uses plain ASGI style (not BaseHTTPMiddleware) to avoid request-body deadlocks.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path.startswith("/health"):
            await self.app(scope, receive, send)
            return

        headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in scope.get("headers", [])
        }
        auth_header = headers.get("authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            response = JSONResponse({"detail": "Missing Authorization header"}, status_code=401)
            await response(scope, receive, send)
            return

        token = auth_header.split(" ", 1)[1]
        payload = decode_jwt_token(token)
        if not payload or "tenant_id" not in payload:
            if token == settings.SERVICE_TOKEN_ORACLE:
                scope.setdefault("state", {})
                scope["state"]["tenant_id"] = "system"
                scope["state"]["user_role"] = "system"
                await self.app(scope, receive, send)
                return
            response = JSONResponse({"detail": "Invalid Token or missing tenant"}, status_code=401)
            await response(scope, receive, send)
            return

        scope.setdefault("state", {})
        scope["state"]["tenant_id"] = payload.get("tenant_id")
        scope["state"]["user_id"] = payload.get("sub")
        scope["state"]["user_role"] = payload.get("role")
        await self.app(scope, receive, send)
