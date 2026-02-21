from pydantic import BaseModel
from typing import List
from uuid import UUID, NAMESPACE_DNS, uuid5

class CurrentUser(BaseModel):
    user_id: UUID
    tenant_id: UUID
    role: str
    permissions: List[str] = []

from fastapi import HTTPException

class AuthService:
    def verify_token(self, token: str) -> CurrentUser:
        """
        Mock abstraction replacing actual JWT asymmetric decoding logic for now. 
        It reads simple string payloads mimicking roles.
        """
        if not token:
            raise HTTPException(status_code=401, detail="Token missing")
            
        role = "admin"
        if "viewer" in token.lower():
            role = "viewer"
        elif "staff" in token.lower():
            role = "staff"
            
        # uuid4() can block in entropy-starved environments; use deterministic uuid5 for stable tests.
        user_id = uuid5(NAMESPACE_DNS, f"user:{token}")
        return CurrentUser(
            user_id=user_id,
            tenant_id=UUID("12345678-1234-5678-1234-567812345678"),
            role=role,
        )
        
    def requires_role(self, user: CurrentUser, allowed_roles: List[str]):
        if user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail=f"Role {user.role} not permitted to access this resource.")

auth_service = AuthService()
