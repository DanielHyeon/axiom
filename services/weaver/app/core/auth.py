from __future__ import annotations

from typing import List

import jwt
from fastapi import HTTPException
from pydantic import BaseModel

from app.core.config import settings

class CurrentUser(BaseModel):
    user_id: str
    tenant_id: str
    role: str
    permissions: list[str] = []

class AuthService:
    _ROLE_PERMISSIONS: dict[str, list[str]] = {
        "admin": [
            "datasource:read",
            "datasource:write",
            "query:read",
            "query:execute",
            "metadata:read",
            "metadata:write",
            "metadata:admin",
        ],
        "staff": [
            "datasource:read",
            "datasource:write",
            "query:read",
            "query:execute",
            "metadata:read",
            "metadata:write",
        ],
        "analyst": [
            "datasource:read",
            "query:read",
            "query:execute",
            "metadata:read",
        ],
        "viewer": [
            "datasource:read",
            "query:read",
            "query:execute",
            "metadata:read",
        ],
    }

    @staticmethod
    def _extract_bearer_token(authorization: str | None) -> str:
        if not authorization:
            raise HTTPException(status_code=401, detail="Missing Authorization header")
        prefix = "bearer "
        if not authorization.lower().startswith(prefix):
            raise HTTPException(status_code=401, detail="Invalid authorization scheme")
        token = authorization[len(prefix) :].strip()
        if not token:
            raise HTTPException(status_code=401, detail="Missing bearer token")
        return token

    def verify_token(self, authorization: str | None) -> CurrentUser:
        token = self._extract_bearer_token(authorization)
        options = {"verify_aud": bool(settings.jwt_audience)}
        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
                audience=settings.jwt_audience or None,
                issuer=settings.jwt_issuer or None,
                options=options,
            )
        except jwt.PyJWTError as exc:
            raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc

        user_id = str(payload.get("sub") or "")
        tenant_id = str(payload.get("tenant_id") or "")
        role = str(payload.get("role") or "")
        if not user_id or not tenant_id or not role:
            raise HTTPException(status_code=401, detail="Invalid token payload")

        claim_permissions = payload.get("permissions")
        permissions: list[str]
        if isinstance(claim_permissions, list):
            permissions = [str(p) for p in claim_permissions]
        else:
            permissions = list(self._ROLE_PERMISSIONS.get(role, []))
        return CurrentUser(
            user_id=user_id,
            tenant_id=tenant_id,
            role=role,
            permissions=permissions,
        )
        
    def requires_role(self, user: CurrentUser, allowed_roles: List[str]):
        if user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail=f"Role {user.role} not permitted.")

    def requires_permission(self, user: CurrentUser, permission: str):
        if user.role == "admin":
            return
        if permission not in user.permissions:
            raise HTTPException(status_code=403, detail=f"Permission {permission} not permitted.")

    def requires_any_permission(self, user: CurrentUser, permissions: List[str]):
        if user.role == "admin":
            return
        if not any(p in user.permissions for p in permissions):
            joined = ",".join(permissions)
            raise HTTPException(status_code=403, detail=f"Permissions [{joined}] not permitted.")

auth_service = AuthService()
