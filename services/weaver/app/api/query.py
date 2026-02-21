from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from typing import Dict, Any
from app.core.auth import auth_service, CurrentUser

router = APIRouter(prefix="/query", tags=["Query Engine"])

class QueryExecution(BaseModel):
    datasource_id: str
    target_node: str
    execution_parameters: Dict[str, Any]

async def get_current_user(authorization: str = Header("mock_token", alias="Authorization")) -> CurrentUser:
    return auth_service.verify_token(authorization)

@router.post("")
async def execute_graph_query(payload: QueryExecution, user: CurrentUser = Depends(get_current_user)):
    auth_service.requires_role(user, ["admin", "analyst", "viewer"])
    
    # Block list validation against unsafe target architectures natively mapped
    blocklist = ["localhost", "127.0.0.1", "10.0.", "192.168."]
    if any(b in payload.target_node for b in blocklist):
        raise HTTPException(status_code=400, detail="Target Node violates connection blocklist policies")
        
    return {"status": "executed", "records_returned": 5}
