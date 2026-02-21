from typing import List
from pydantic import BaseModel
import uuid
from fastapi import HTTPException

class CurrentUser(BaseModel):
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    role: str

class AuthService:
    def verify_token(self, token: str) -> CurrentUser:
        """Mock abstraction mimicking JWT verification."""
        if not token:
            raise HTTPException(status_code=401, detail="Token missing")
            
        role = "admin"
        if "viewer" in token.lower():
            role = "viewer"
        elif "staff" in token.lower():
            role = "staff"
            
        return CurrentUser(
            user_id=uuid.uuid4(),
            tenant_id=uuid.UUID('12345678-1234-5678-1234-567812345678'),
            role=role
        )
        
    def requires_role(self, user: CurrentUser, allowed_roles: List[str]):
        if user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail=f"Role {user.role} not permitted.")

auth_service = AuthService()
