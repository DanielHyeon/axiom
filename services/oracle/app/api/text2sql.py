from fastapi import APIRouter, Depends, Request, HTTPException, Header
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional

from app.pipelines.nl2sql_pipeline import nl2sql_pipeline
from app.core.auth import auth_service, CurrentUser

async def get_current_user(authorization: str = Header("mock_token", alias="Authorization")) -> CurrentUser:
    return auth_service.verify_token(authorization)

router = APIRouter(prefix="/text2sql", tags=["Text2SQL"])

class AskOptions(BaseModel):
    use_cache: bool = True
    include_viz: bool = True
    row_limit: int = Field(default=1000, le=10000)
    dialect: str = "postgres"

class AskRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=2000)
    datasource_id: str
    options: AskOptions = Field(default_factory=AskOptions)

class ReactOptions(BaseModel):
    max_iterations: int = Field(default=5, le=10)
    stream: bool = True

class ReactRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=2000)
    datasource_id: str
    options: ReactOptions = Field(default_factory=ReactOptions)

class DirectSqlRequest(BaseModel):
    sql: str
    datasource_id: str

@router.post("/ask")
async def ask_question(request_payload: AskRequest, user: CurrentUser = Depends(get_current_user)):
    auth_service.requires_role(user, ["admin", "manager", "attorney", "analyst", "engineer"])
    result = await nl2sql_pipeline.execute(
        request_payload.question, 
        request_payload.datasource_id, 
        request_payload.options.model_dump(),
        user
    )
    return result

from fastapi.responses import StreamingResponse
from app.pipelines.react_agent import react_agent, ReactSession

@router.post("/react")
async def react_stream(request_payload: ReactRequest, user: CurrentUser = Depends(get_current_user)):
    auth_service.requires_role(user, ["admin", "manager", "attorney", "analyst", "engineer"])
    session = ReactSession(
        question=request_payload.question,
        datasource_id=request_payload.datasource_id,
        options=request_payload.options.model_dump(),
        max_iterations=request_payload.options.max_iterations
    )
    # Return NDJSON stream directly from generator
    return StreamingResponse(
        react_agent.stream_react_loop(session, user),
        media_type="application/x-ndjson"
    )

@router.post("/direct-sql")
async def direct_sql(payload: DirectSqlRequest, user: CurrentUser = Depends(get_current_user)):
    # Mocking admin only execution
    auth_service.requires_role(user, ["admin"])
    from app.core.sql_exec import sql_executor
    res = await sql_executor.execute_sql(payload.sql, payload.datasource_id, user)
    return {
        "success": True,
        "data": {
            "result": res.model_dump(),
            "metadata": {"execution_time_ms": res.execution_time_ms, "guard_status": "PASS"}
        }
    }
