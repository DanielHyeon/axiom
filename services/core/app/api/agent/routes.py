import asyncio
import json
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.middleware import get_current_tenant_id
from app.services.agent_service import AgentDomainError, agent_service

router = APIRouter(tags=["agent"])


class FeedbackRequest(BaseModel):
    workitem_id: str
    feedback_type: str = "suggestion"
    content: str
    corrected_output: dict[str, Any] = Field(default_factory=dict)
    priority: str = "medium"


class ChatRequest(BaseModel):
    message: str
    context: dict[str, Any] = Field(default_factory=dict)
    stream: bool = False
    agent_config: dict[str, Any] = Field(default_factory=dict)


def _raise(e: AgentDomainError) -> None:
    raise HTTPException(status_code=e.status_code, detail={"code": e.code, "message": e.message})


@router.post("/agents/feedback", status_code=202)
async def submit_feedback(req: FeedbackRequest):
    try:
        return agent_service.submit_feedback(get_current_tenant_id(), req.model_dump())
    except AgentDomainError as e:
        _raise(e)


@router.get("/agents/feedback/{workitem_id}")
async def get_feedback(workitem_id: str):
    try:
        return agent_service.get_feedback(get_current_tenant_id(), workitem_id)
    except AgentDomainError as e:
        _raise(e)


@router.post("/mcp/config")
async def configure_mcp(payload: dict[str, Any]):
    try:
        return agent_service.configure_mcp(get_current_tenant_id(), payload or {})
    except AgentDomainError as e:
        _raise(e)


@router.get("/mcp/tools")
async def list_mcp_tools():
    try:
        return agent_service.list_mcp_tools(get_current_tenant_id())
    except AgentDomainError as e:
        _raise(e)


@router.post("/mcp/execute-tool")
async def execute_mcp_tool(payload: dict[str, Any]):
    try:
        return agent_service.execute_tool(get_current_tenant_id(), payload or {})
    except AgentDomainError as e:
        _raise(e)


@router.post("/completion/complete")
async def completion_complete(payload: dict[str, Any]):
    try:
        return agent_service.complete(get_current_tenant_id(), payload or {}, vision=False)
    except AgentDomainError as e:
        _raise(e)


@router.post("/completion/vision-complete")
async def completion_vision_complete(payload: dict[str, Any]):
    try:
        return agent_service.complete(get_current_tenant_id(), payload or {}, vision=True)
    except AgentDomainError as e:
        _raise(e)


@router.post("/agents/chat")
async def agent_chat(req: ChatRequest):
    try:
        payload = req.model_dump()
        if not req.stream:
            return agent_service.chat(get_current_tenant_id(), payload)

        async def stream():
            for item in agent_service.chat_stream(get_current_tenant_id(), payload):
                yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0)

        return StreamingResponse(stream(), media_type="text/event-stream")
    except AgentDomainError as e:
        _raise(e)


@router.get("/agents/knowledge")
async def list_knowledge(limit: int = 20, offset: int = 0):
    try:
        return agent_service.list_knowledge(get_current_tenant_id(), limit=limit, offset=offset)
    except AgentDomainError as e:
        _raise(e)


@router.delete("/agents/knowledge/{knowledge_id}")
async def delete_knowledge(knowledge_id: str):
    try:
        return agent_service.delete_knowledge(get_current_tenant_id(), knowledge_id)
    except AgentDomainError as e:
        _raise(e)
