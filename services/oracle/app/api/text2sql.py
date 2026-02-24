from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
import structlog

from app.pipelines.nl2sql_pipeline import nl2sql_pipeline
from app.core.auth import auth_service, CurrentUser, security_scheme
from app.core.query_history import query_history_repo
from app.infrastructure.acl.synapse_acl import oracle_synapse_acl
from app.core.rate_limit import rate_limiter

logger = structlog.get_logger()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> CurrentUser:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing",
        )
    return auth_service.verify_token(credentials.credentials)


async def rate_limit_ask(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    rate_limiter.check(f"text2sql:ask:{user.user_id}", limit=30, window_seconds=60)
    return user


async def rate_limit_react(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    rate_limiter.check(f"text2sql:react:{user.user_id}", limit=10, window_seconds=60)
    return user


async def rate_limit_direct_sql(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    rate_limiter.check(f"text2sql:direct_sql:{user.user_id}", limit=60, window_seconds=60)
    return user


router = APIRouter(prefix="/text2sql", tags=["Text2SQL"])

class AskOptions(BaseModel):
    use_cache: bool = True
    include_viz: bool = True
    row_limit: int = Field(default=1000, le=10000)
    dialect: str = "postgres"

class AskRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=2000)
    datasource_id: str
    case_id: str | None = None  # O3: ontology context
    options: AskOptions = Field(default_factory=AskOptions)

class ReactOptions(BaseModel):
    max_iterations: int = Field(default=5, le=10)
    stream: bool = True
    row_limit: int = Field(default=1000, le=10000)

class ReactRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=2000)
    datasource_id: str
    case_id: str | None = None  # O3: ontology context
    options: ReactOptions = Field(default_factory=ReactOptions)

class DirectSqlRequest(BaseModel):
    sql: str
    datasource_id: str

def _validate_datasource_id(datasource_id: str) -> None:
    for ds in oracle_synapse_acl.list_datasources():
        if ds.id == datasource_id:
            return
    raise HTTPException(status_code=404, detail="DATASOURCE_NOT_FOUND")

@router.post("/ask")
async def ask_question(request_payload: AskRequest, user: CurrentUser = Depends(rate_limit_ask)):
    auth_service.requires_role(user, ["admin", "manager", "attorney", "analyst", "engineer"])
    _validate_datasource_id(request_payload.datasource_id)
    result = await nl2sql_pipeline.execute(
        request_payload.question,
        request_payload.datasource_id,
        request_payload.options.model_dump(),
        user,
        case_id=request_payload.case_id,
    )
    if result.get("success"):
        data = result.get("data", {})
        record = {
            "tenant_id": user.tenant_id,
            "user_id": user.user_id,
            "question": request_payload.question,
            "sql": data.get("sql", ""),
            "status": "success",
            "result": data.get("result", {}),
            "row_count": data.get("result", {}).get("row_count"),
            "datasource_id": request_payload.datasource_id,
            "metadata": data.get("metadata", {}),
        }
        try:
            query_id = await query_history_repo.save_query_history(record)
            result.setdefault("data", {}).setdefault("metadata", {})["query_id"] = query_id
        except Exception as exc:
            logger.exception("history_save_failed", error=str(exc))
            result.setdefault("data", {}).setdefault("metadata", {})["query_id"] = None
    return result

from fastapi.responses import StreamingResponse
from app.pipelines.react_agent import react_agent, ReactSession

@router.post("/react")
async def react_stream(request_payload: ReactRequest, user: CurrentUser = Depends(rate_limit_react)):
    auth_service.requires_role(user, ["admin", "manager", "attorney", "analyst", "engineer"])
    _validate_datasource_id(request_payload.datasource_id)
    session = ReactSession(
        question=request_payload.question,
        datasource_id=request_payload.datasource_id,
        case_id=request_payload.case_id,
        options=request_payload.options.model_dump(),
        max_iterations=request_payload.options.max_iterations,
    )
    # Return NDJSON stream directly from generator
    return StreamingResponse(
        react_agent.stream_react_loop(session, user),
        media_type="application/x-ndjson"
    )

@router.post("/direct-sql")
async def direct_sql(payload: DirectSqlRequest, user: CurrentUser = Depends(rate_limit_direct_sql)):
    # Mocking admin only execution
    auth_service.requires_role(user, ["admin"])
    _validate_datasource_id(payload.datasource_id)
    from app.core.sql_exec import sql_executor
    res = await sql_executor.execute_sql(payload.sql, payload.datasource_id, user)
    response = {
        "success": True,
        "data": {
            "result": res.model_dump(),
            "metadata": {
                "execution_time_ms": res.execution_time_ms,
                "guard_status": "PASS",
                "execution_backend": res.backend,
            },
        }
    }
    try:
        query_id = await query_history_repo.save_query_history(
            {
                "tenant_id": user.tenant_id,
                "user_id": user.user_id,
                "question": "DIRECT_SQL",
                "sql": payload.sql,
                "status": "success",
                "result": res.model_dump(),
                "row_count": res.row_count,
                "datasource_id": payload.datasource_id,
                "metadata": response["data"]["metadata"],
            }
        )
        response["data"]["metadata"]["query_id"] = query_id
    except Exception as exc:
        logger.exception("history_save_failed", error=str(exc))
        response["data"]["metadata"]["query_id"] = None
    return response


@router.get("/history")
async def list_history(
    datasource_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    status: str | None = Query(default=None, pattern="^(success|error)$"),
    user: CurrentUser = Depends(get_current_user),
):
    auth_service.requires_role(user, ["admin", "manager", "attorney", "analyst", "engineer"])
    page_result = await query_history_repo.list_history(
        tenant_id=user.tenant_id,
        datasource_id=datasource_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    total_pages = (page_result.total_count + page_size - 1) // page_size
    return {
        "success": True,
        "data": {
            "history": page_result.items,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_count": page_result.total_count,
                "total_pages": total_pages,
            },
        },
    }


@router.get("/history/{query_id}")
async def get_history_detail(query_id: str, user: CurrentUser = Depends(get_current_user)):
    auth_service.requires_role(user, ["admin", "manager", "attorney", "analyst", "engineer"])
    detail = await query_history_repo.get_history_detail(user.tenant_id, query_id)
    if not detail:
        raise HTTPException(status_code=404, detail="query history not found")
    return {"success": True, "data": detail}
