from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.middleware import get_current_tenant_id
from app.services.watch_service import WatchService

router = APIRouter(prefix="/watches", tags=["watches"])


class SubscriptionCreateRequest(BaseModel):
    user_id: str
    event_type: str
    channels: list[str] = Field(default_factory=lambda: ["in_app"])
    case_id: str | None = None
    active: bool = True


class SubscriptionUpdateRequest(BaseModel):
    channels: list[str] | None = None
    active: bool | None = None


class RuleCreateRequest(BaseModel):
    name: str
    event_type: str
    definition: dict = Field(default_factory=dict)
    active: bool = True


@router.post("/subscriptions")
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
            active=req.active,
            tenant_id=get_current_tenant_id(),
        )
        await db.commit()
        return {"subscription_id": item.id, "event_type": item.event_type, "active": item.active}
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
                    "channels": item.channels,
                    "active": item.active,
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
        )
        await db.commit()
        return {"subscription_id": item.id, "active": item.active, "channels": item.channels}
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=404, detail=str(e))
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
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/alerts")
async def list_alerts(
    status: str | None = None,
    severity: str | None = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_session),
):
    try:
        return await WatchService.list_alerts(
            db=db,
            tenant_id=get_current_tenant_id(),
            status=status,
            severity=severity,
            limit=limit,
        )
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
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.put("/alerts/read-all")
async def read_all_alerts(db: AsyncSession = Depends(get_session)):
    try:
        result = await WatchService.read_all_alerts(db=db, tenant_id=get_current_tenant_id())
        await db.commit()
        return result
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal Server Error")


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
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/rules")
async def list_rules(request: Request, db: AsyncSession = Depends(get_session)):
    _ = request
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
