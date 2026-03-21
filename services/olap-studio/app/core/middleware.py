"""ASGI 미들웨어 — JWT 검증 + 테넌트/프로젝트 컨텍스트 추출."""
from jose import JWTError, jwt
from starlette.responses import JSONResponse

from app.core.config import settings


def decode_jwt_token(token: str) -> dict | None:
    """JWT를 디코딩한다. 실패 시 None."""
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None


class TenantMiddleware:
    """ASGI 미들웨어 — JWT 검증 + tenant/project 컨텍스트 추출.

    Gateway가 주입한 X-Tenant-Id, X-Project-Id 헤더도 지원한다.
    plain ASGI 스타일로 구현하여 request body deadlock을 방지한다.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        # 헬스체크는 인증 없이 통과
        if path.startswith("/health"):
            await self.app(scope, receive, send)
            return

        headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in scope.get("headers", [])
        }

        # Gateway 모드: X-Tenant-Id 헤더가 있으면 Gateway가 이미 인증을 완료한 것으로 간주
        gateway_tenant = headers.get("x-tenant-id")
        if gateway_tenant:
            scope.setdefault("state", {})
            scope["state"]["tenant_id"] = gateway_tenant
            scope["state"]["project_id"] = headers.get("x-project-id", "")
            scope["state"]["user_id"] = headers.get("x-user-id", "")
            scope["state"]["user_name"] = headers.get("x-user-name", "")
            scope["state"]["roles"] = [r.strip() for r in headers.get("x-roles", "").split(",") if r.strip()]
            scope["state"]["trace_id"] = headers.get("x-trace-id", "")
            await self.app(scope, receive, send)
            return

        # 직접 접근 모드: JWT 토큰 검증
        auth_header = headers.get("authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            response = JSONResponse({"detail": "Authorization 헤더 누락"}, status_code=401)
            await response(scope, receive, send)
            return

        token = auth_header.split(" ", 1)[1]
        payload = decode_jwt_token(token)
        if not payload or "tenant_id" not in payload:
            response = JSONResponse({"detail": "유효하지 않은 토큰"}, status_code=401)
            await response(scope, receive, send)
            return

        scope.setdefault("state", {})
        scope["state"]["tenant_id"] = payload.get("tenant_id", "")
        scope["state"]["project_id"] = payload.get("project_id", "")
        scope["state"]["user_id"] = payload.get("sub", "")
        scope["state"]["user_name"] = payload.get("name", "")
        scope["state"]["user_role"] = payload.get("role", "")
        scope["state"]["roles"] = [payload.get("role", "")] if payload.get("role") else []
        await self.app(scope, receive, send)
