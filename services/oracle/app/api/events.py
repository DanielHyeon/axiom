from __future__ import annotations

import json
import re
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.api.text2sql import get_current_user
from app.core.auth import CurrentUser, auth_service
from app.core.config import settings

router = APIRouter(prefix="/text2sql/events", tags=["Events"])
watch_agent_router = APIRouter(prefix="/text2sql", tags=["Events"])


def _core_headers(user: CurrentUser) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.SERVICE_TOKEN_ORACLE}",
        "X-Tenant-Id": str(user.tenant_id),
        "Content-Type": "application/json",
    }


async def _core_request(
    method: str,
    path: str,
    user: CurrentUser,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"{settings.CORE_API_URL}/api/v1{path}"
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            res = await client.request(method, url, headers=_core_headers(user), params=params, json=json_body)
            res.raise_for_status()
            if res.content:
                return res.json()
            return {}
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text
            raise HTTPException(status_code=exc.response.status_code, detail=detail)
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="core watch unavailable")


def _build_definition(payload: dict[str, Any], include_when_empty: bool) -> dict[str, Any] | None:
    condition = (payload or {}).get("condition") or {}
    schedule = (payload or {}).get("schedule")
    actions = (payload or {}).get("actions")
    sql = (payload or {}).get("sql")
    datasource_id = (payload or {}).get("datasource_id")

    condition_type = str(condition.get("type") or "threshold")
    if condition_type == "row_count":
        condition_type = "threshold"
    if condition_type not in {"deadline", "threshold", "pattern"}:
        condition_type = "threshold"

    definition: dict[str, Any] = {"type": condition_type}
    if condition_type == "threshold":
        definition["field"] = condition.get("field") or "row_count"
        definition["operator"] = condition.get("operator") or "gt"
        definition["threshold"] = condition.get("threshold", 0)
    elif condition_type == "deadline":
        definition["days_before"] = condition.get("days_before", 7)
    elif condition_type == "pattern":
        definition["window_hours"] = condition.get("window_hours", 24)
        definition["min_count"] = condition.get("min_count", 1)

    if sql is not None:
        definition["sql"] = sql
    if schedule is not None:
        definition["schedule"] = schedule
    if actions is not None:
        definition["actions"] = actions
    if datasource_id is not None:
        definition["datasource_id"] = datasource_id

    has_payload_keys = any(
        key in (payload or {})
        for key in ("condition", "schedule", "actions", "sql", "datasource_id")
    )
    if include_when_empty or has_payload_keys:
        return definition
    return None


def _propose_watch_rule(message: str, datasource_id: str) -> dict[str, Any]:
    text = (message or "").strip()
    lowered = text.lower()
    schedule = {"type": "interval", "value": "1h"}
    if "30분" in text or "30 min" in lowered:
        schedule["value"] = "30m"
    elif "15분" in text or "15 min" in lowered:
        schedule["value"] = "15m"
    elif "매일" in text or "daily" in lowered:
        schedule = {"type": "cron", "value": "0 9 * * *"}

    threshold_pct = None
    matched = re.search(r"(\d+)\s*%", text)
    if matched:
        threshold_pct = int(matched.group(1)) / 100.0
    condition = {"type": "row_count", "operator": "gt", "threshold": 0}
    if threshold_pct is not None:
        condition = {
            "type": "threshold",
            "field": "change_rate",
            "operator": "lte",
            "threshold": -threshold_pct,
        }

    rule_name = "자동 감시 룰"
    if "매출" in text:
        rule_name = "매출 변동 감시"
    elif "기한" in text or "마일스톤" in text:
        rule_name = "기한 임박 감시"

    sql = "SELECT * FROM monitored_events WHERE 1=1"
    if "매출" in text:
        sql = "SELECT org_name, change_rate FROM sales_change_monitor WHERE change_rate <= :threshold"
    elif "기한" in text or "마일스톤" in text:
        sql = "SELECT process_id, milestone_deadline FROM process_milestones WHERE milestone_deadline <= NOW() + INTERVAL '3 days'"

    return {
        "name": rule_name,
        "datasource_id": datasource_id,
        "sql": sql,
        "schedule": schedule,
        "condition": condition,
    }


@router.post("/rules")
async def create_rule(payload: dict[str, Any], user: CurrentUser = Depends(get_current_user)):
    auth_service.requires_role(user, ["admin", "manager", "attorney", "analyst", "engineer"])
    definition = _build_definition(payload or {}, include_when_empty=True) or {"type": "threshold", "field": "row_count", "operator": "gt", "threshold": 0}
    req = {
        "name": str((payload or {}).get("name") or "event-rule"),
        "event_type": str((payload or {}).get("event_type") or "THRESHOLD_ALERT"),
        "definition": definition,
        "active": bool((payload or {}).get("enabled", True)),
    }
    result = await _core_request("POST", "/watches/rules", user, json_body=req)
    return {
        "success": True,
        "data": {
            "rule_id": result.get("rule_id"),
            "name": req["name"],
            "status": "active" if req["active"] else "inactive",
            "next_run": None,
        },
    }


@router.get("/rules")
async def list_rules(user: CurrentUser = Depends(get_current_user)):
    auth_service.requires_role(user, ["admin", "manager", "attorney", "analyst", "engineer"])
    result = await _core_request("GET", "/watches/rules", user)
    rows = result.get("data", [])
    return {"success": True, "data": {"rules": rows, "total": len(rows)}}


@router.get("/rules/{rule_id}")
async def get_rule(rule_id: str, user: CurrentUser = Depends(get_current_user)):
    auth_service.requires_role(user, ["admin", "manager", "attorney", "analyst", "engineer"])
    result = await _core_request("GET", f"/watches/rules/{rule_id}", user)
    return {"success": True, "data": result}


@router.put("/rules/{rule_id}")
async def update_rule(rule_id: str, payload: dict[str, Any], user: CurrentUser = Depends(get_current_user)):
    auth_service.requires_role(user, ["admin", "manager", "attorney", "analyst", "engineer"])
    definition = _build_definition(payload or {}, include_when_empty=False)
    req = {
        "name": (payload or {}).get("name"),
        "event_type": (payload or {}).get("event_type"),
        "definition": definition,
        "active": (payload or {}).get("enabled"),
    }
    result = await _core_request("PUT", f"/watches/rules/{rule_id}", user, json_body=req)
    return {"success": True, "data": result}


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str, user: CurrentUser = Depends(get_current_user)):
    auth_service.requires_role(user, ["admin", "manager", "attorney", "analyst", "engineer"])
    result = await _core_request("DELETE", f"/watches/rules/{rule_id}", user)
    return {"success": True, "data": result}


@router.post("/scheduler/start")
async def scheduler_start(user: CurrentUser = Depends(get_current_user)):
    auth_service.requires_role(user, ["admin"])
    result = await _core_request("POST", "/watches/scheduler/start", user)
    return {"success": True, "data": result}


@router.post("/scheduler/stop")
async def scheduler_stop(user: CurrentUser = Depends(get_current_user)):
    auth_service.requires_role(user, ["admin"])
    result = await _core_request("POST", "/watches/scheduler/stop", user)
    return {"success": True, "data": result}


@router.get("/scheduler/status")
async def scheduler_status(user: CurrentUser = Depends(get_current_user)):
    auth_service.requires_role(user, ["admin", "manager", "attorney", "analyst", "engineer"])
    result = await _core_request("GET", "/watches/scheduler/status", user)
    return {"success": True, "data": result}


@router.get("/stream/alarms")
async def stream_alarms(
    request: Request,
    token: str | None = None,
    user: CurrentUser = Depends(get_current_user),
):
    auth_service.requires_role(user, ["admin", "manager", "attorney", "analyst", "engineer"])

    async def event_stream():
        url = f"{settings.CORE_API_URL}/api/v1/watches/stream"
        forwarded_token = token or settings.SERVICE_TOKEN_ORACLE
        async with httpx.AsyncClient(timeout=None) as client:
            try:
                async with client.stream("GET", url, headers=_core_headers(user), params={"token": forwarded_token}) as res:
                    res.raise_for_status()
                    async for line in res.aiter_lines():
                        if await request.is_disconnected():
                            break
                        if line is None:
                            continue
                        yield f"{line}\n"
            except Exception:
                yield f"event: error\ndata: {json.dumps({'message': 'core watch stream unavailable'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@watch_agent_router.post("/watch-agent/chat")
async def watch_agent_chat(payload: dict[str, Any], user: CurrentUser = Depends(get_current_user)):
    auth_service.requires_role(user, ["admin", "manager", "attorney", "analyst", "engineer"])
    message = str((payload or {}).get("message") or "")
    datasource_id = str((payload or {}).get("datasource_id") or "")
    session_id = str((payload or {}).get("session_id") or "")
    core_payload = {
        "message": f"[watch-agent]\n{message}\n[datasource_id]={datasource_id}",
        "context": {"mode": "watch-agent"},
        "stream": False,
        "agent_config": {"intent": "watch-rule-management"},
    }
    result = await _core_request("POST", "/agents/chat", user, json_body=core_payload)
    response_text = result.get("response") or "요청을 처리했습니다."
    proposed_rule = _propose_watch_rule(message=message, datasource_id=datasource_id)
    return {
        "success": True,
        "data": {
            "response": response_text,
            "proposed_rule": proposed_rule,
            "action_required": "confirm",
            "session_id": session_id,
        },
    }
