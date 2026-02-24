import asyncio
import json
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, get_session
from app.core.middleware import get_current_tenant_id
from app.models.base_models import WatchAlert
from app.modules.watch.application.watch_service import WatchDomainError, WatchService

router = APIRouter(prefix="/watches", tags=["watches"])

_stream_counts: dict[str, int] = defaultdict(int)
_stream_lock = asyncio.Lock()
_MAX_STREAMS_PER_TENANT = 100
_HEARTBEAT_INTERVAL_SECONDS = 30


class SubscriptionCreateRequest(BaseModel):
    user_id: str
    event_type: str
    case_id: str | None = None
    rule: dict = Field(default_factory=lambda: {"type": "deadline", "days_before": 7})
    channels: list[str] = Field(default_factory=lambda: ["in_app"])
    severity_override: str | None = None
    active: bool = True


class SubscriptionUpdateRequest(BaseModel):
    channels: list[str] | None = None
    active: bool | None = None
    rule: dict | None = None
    severity_override: str | None = None


class RuleCreateRequest(BaseModel):
    name: str
    event_type: str
    definition: dict = Field(default_factory=dict)
    active: bool = True


class RuleUpdateRequest(BaseModel):
    name: str | None = None
    event_type: str | None = None
    definition: dict | None = None
    active: bool | None = None


_scheduler_state = {"running": False, "updated_at": None}


def _as_http_error(e: WatchDomainError) -> HTTPException:
    return HTTPException(status_code=e.status_code, detail={"code": e.code, "message": e.message})


@router.post("/subscriptions", status_code=status.HTTP_201_CREATED)
async def create_subscription(
    req: SubscriptionCreateRequest,
    db: AsyncSession = Depends(get_session),
):
    try:
        item = await WatchService.create_subscription(
            db=db,
            user_id=req.user_id,
            event_type=req.event_type,
            channels=req.channels,
            case_id=req.case_id,
            rule=req.rule,
            severity_override=req.severity_override,
            active=req.active,
            tenant_id=get_current_tenant_id(),
        )
        await db.commit()
        return {
            "subscription_id": item.id,
            "event_type": item.event_type,
            "case_id": item.case_id,
            "channels": item.channels,
            "active": item.active,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }
    except WatchDomainError as e:
        await db.rollback()
        raise _as_http_error(e)
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/subscriptions")
async def list_subscriptions(
    user_id: str,
    db: AsyncSession = Depends(get_session),
):
    try:
        items = await WatchService.list_subscriptions(
            db=db,
            user_id=user_id,
            tenant_id=get_current_tenant_id(),
        )
        return {
            "data": [
                {
                    "subscription_id": item.id,
                    "event_type": item.event_type,
                    "case_id": item.case_id,
                    "rule": item.rule,
                    "channels": item.channels,
                    "severity_override": item.severity_override,
                    "active": item.active,
                    "created_at": item.created_at.isoformat() if item.created_at else None,
                }
                for item in items
            ]
        }
    except Exception:
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.put("/subscriptions/{subscription_id}")
async def update_subscription(
    subscription_id: str,
    req: SubscriptionUpdateRequest,
    db: AsyncSession = Depends(get_session),
):
    try:
        item = await WatchService.update_subscription(
            db=db,
            subscription_id=subscription_id,
            tenant_id=get_current_tenant_id(),
            channels=req.channels,
            active=req.active,
            rule=req.rule,
            severity_override=req.severity_override,
        )
        await db.commit()
        return {"subscription_id": item.id, "active": item.active, "channels": item.channels}
    except WatchDomainError as e:
        await db.rollback()
        raise _as_http_error(e)
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.delete("/subscriptions/{subscription_id}")
async def delete_subscription(
    subscription_id: str,
    db: AsyncSession = Depends(get_session),
):
    try:
        await WatchService.delete_subscription(
            db=db,
            subscription_id=subscription_id,
            tenant_id=get_current_tenant_id(),
        )
        await db.commit()
        return {"deleted": True}
    except WatchDomainError as e:
        await db.rollback()
        raise _as_http_error(e)
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/alerts")
async def list_alerts(
    status: str | None = None,
    severity: str | None = None,
    case_id: str | None = None,
    from_ts: datetime | None = Query(default=None, alias="from"),
    to_ts: datetime | None = Query(default=None, alias="to"),
    cursor: str | None = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_session),
):
    try:
        return await WatchService.list_alerts(
            db=db,
            tenant_id=get_current_tenant_id(),
            status=status,
            severity=severity,
            case_id=case_id,
            from_ts=from_ts,
            to_ts=to_ts,
            cursor=cursor,
            limit=limit,
        )
    except WatchDomainError as e:
        raise _as_http_error(e)
    except Exception:
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.put("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    db: AsyncSession = Depends(get_session),
):
    try:
        result = await WatchService.acknowledge_alert(
            db=db,
            alert_id=alert_id,
            tenant_id=get_current_tenant_id(),
        )
        await db.commit()
        return result
    except WatchDomainError as e:
        await db.rollback()
        raise _as_http_error(e)
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.put("/alerts/{alert_id}/dismiss")
async def dismiss_alert(
    alert_id: str,
    db: AsyncSession = Depends(get_session),
):
    try:
        result = await WatchService.dismiss_alert(
            db=db,
            alert_id=alert_id,
            tenant_id=get_current_tenant_id(),
        )
        await db.commit()
        return result
    except WatchDomainError as e:
        await db.rollback()
        raise _as_http_error(e)
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.put("/alerts/read-all")
async def read_all_alerts(user_id: str | None = None, db: AsyncSession = Depends(get_session)):
    try:
        result = await WatchService.read_all_alerts(
            db=db, tenant_id=get_current_tenant_id(), user_id=user_id
        )
        await db.commit()
        return result
    except WatchDomainError as e:
        await db.rollback()
        raise _as_http_error(e)
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/stream")
async def watch_stream(
    request: Request,
    token: str | None = None,
):
    if not token or not token.strip():
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHORIZED", "message": "token query param is required for SSE"},
        )
    tenant_id = get_current_tenant_id()
    async with _stream_lock:
        if _stream_counts[tenant_id] >= _MAX_STREAMS_PER_TENANT:
            raise HTTPException(
                status_code=429,
                detail={"code": "TOO_MANY_STREAM_CONNECTIONS", "message": "too many SSE connections"},
            )
        _stream_counts[tenant_id] += 1

    async def event_generator():
        last_status_by_id: dict[str, str] = {}
        try:
            while True:
                if await request.is_disconnected():
                    break
                async with AsyncSessionLocal() as session:
                    snapshot = await WatchService.list_alerts(
                        db=session,
                        tenant_id=tenant_id,
                        limit=20,
                    )
                    for alert in snapshot["data"]:
                        current_status = alert["status"]
                        prev_status = last_status_by_id.get(alert["alert_id"])
                        if prev_status is None and current_status == "unread":
                            payload = json.dumps(alert, ensure_ascii=False)
                            yield f"event: alert\ndata: {payload}\n\n"
                        elif prev_status and prev_status != current_status:
                            payload = json.dumps(
                                {"alert_id": alert["alert_id"], "status": current_status},
                                ensure_ascii=False,
                            )
                            yield f"event: alert_update\ndata: {payload}\n\n"
                        last_status_by_id[alert["alert_id"]] = current_status

                async with AsyncSessionLocal() as session:
                    stale = await session.execute(
                        select(WatchAlert.id).where(WatchAlert.tenant_id == tenant_id).limit(200)
                    )
                    valid_ids = {row[0] for row in stale.all()}
                    for key in list(last_status_by_id.keys()):
                        if key not in valid_ids:
                            del last_status_by_id[key]

                heartbeat = json.dumps({"timestamp": datetime.now(timezone.utc).isoformat()})
                yield f"event: heartbeat\ndata: {heartbeat}\n\n"
                await asyncio.sleep(_HEARTBEAT_INTERVAL_SECONDS)
        finally:
            async with _stream_lock:
                _stream_counts[tenant_id] = max(0, _stream_counts[tenant_id] - 1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/rules")
async def create_rule(req: RuleCreateRequest, db: AsyncSession = Depends(get_session)):
    try:
        item = await WatchService.create_rule(
            db=db,
            name=req.name,
            event_type=req.event_type,
            definition=req.definition,
            active=req.active,
            tenant_id=get_current_tenant_id(),
        )
        await db.commit()
        return {"rule_id": item.id, "event_type": item.event_type, "active": item.active}
    except WatchDomainError as e:
        await db.rollback()
        raise _as_http_error(e)
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/rules")
async def list_rules(db: AsyncSession = Depends(get_session)):
    try:
        items = await WatchService.list_rules(db=db, tenant_id=get_current_tenant_id())
        return {
            "data": [
                {"rule_id": item.id, "name": item.name, "event_type": item.event_type, "active": item.active}
                for item in items
            ]
        }
    except Exception:
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/rules/{rule_id}")
async def get_rule(rule_id: str, db: AsyncSession = Depends(get_session)):
    try:
        item = await WatchService.get_rule(db=db, tenant_id=get_current_tenant_id(), rule_id=rule_id)
        return {
            "rule_id": item.id,
            "name": item.name,
            "event_type": item.event_type,
            "definition": item.definition,
            "active": item.active,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        }
    except WatchDomainError as e:
        raise _as_http_error(e)
    except Exception:
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.put("/rules/{rule_id}")
async def update_rule(rule_id: str, req: RuleUpdateRequest, db: AsyncSession = Depends(get_session)):
    try:
        item = await WatchService.update_rule(
            db=db,
            tenant_id=get_current_tenant_id(),
            rule_id=rule_id,
            name=req.name,
            event_type=req.event_type,
            definition=req.definition,
            active=req.active,
        )
        await db.commit()
        return {
            "rule_id": item.id,
            "name": item.name,
            "event_type": item.event_type,
            "definition": item.definition,
            "active": item.active,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        }
    except WatchDomainError as e:
        await db.rollback()
        raise _as_http_error(e)
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str, db: AsyncSession = Depends(get_session)):
    try:
        await WatchService.delete_rule(db=db, tenant_id=get_current_tenant_id(), rule_id=rule_id)
        await db.commit()
        return {"deleted": True}
    except WatchDomainError as e:
        await db.rollback()
        raise _as_http_error(e)
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/scheduler/start")
async def start_scheduler():
    _scheduler_state["running"] = True
    _scheduler_state["updated_at"] = datetime.now(timezone.utc).isoformat()
    return {"running": True, "updated_at": _scheduler_state["updated_at"]}


@router.post("/scheduler/stop")
async def stop_scheduler():
    _scheduler_state["running"] = False
    _scheduler_state["updated_at"] = datetime.now(timezone.utc).isoformat()
    return {"running": False, "updated_at": _scheduler_state["updated_at"]}


@router.get("/scheduler/status")
async def scheduler_status():
    return {
        "running": bool(_scheduler_state["running"]),
        "updated_at": _scheduler_state["updated_at"],
    }
