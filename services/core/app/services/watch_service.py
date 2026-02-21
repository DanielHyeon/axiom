from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base_models import WatchAlert, WatchRule, WatchSubscription


class WatchService:
    @staticmethod
    async def create_subscription(
        db: AsyncSession,
        user_id: str,
        event_type: str,
        channels: list[str],
        tenant_id: str,
        case_id: str | None = None,
        active: bool = True,
    ) -> WatchSubscription:
        subscription = WatchSubscription(
            user_id=user_id,
            event_type=event_type,
            channels=channels,
            case_id=case_id,
            active=active,
            tenant_id=tenant_id,
        )
        db.add(subscription)
        await db.flush()
        return subscription

    @staticmethod
    async def list_subscriptions(db: AsyncSession, user_id: str, tenant_id: str) -> list[WatchSubscription]:
        result = await db.execute(
            select(WatchSubscription).where(
                WatchSubscription.user_id == user_id,
                WatchSubscription.tenant_id == tenant_id,
            )
        )
        return result.scalars().all()

    @staticmethod
    async def update_subscription(
        db: AsyncSession,
        subscription_id: str,
        tenant_id: str,
        channels: list[str] | None,
        active: bool | None,
    ) -> WatchSubscription:
        result = await db.execute(
            select(WatchSubscription).where(
                WatchSubscription.id == subscription_id,
                WatchSubscription.tenant_id == tenant_id,
            )
        )
        subscription = result.scalar_one_or_none()
        if not subscription:
            raise ValueError("SUBSCRIPTION_NOT_FOUND")
        if channels is not None:
            subscription.channels = channels
        if active is not None:
            subscription.active = active
        await db.flush()
        return subscription

    @staticmethod
    async def delete_subscription(db: AsyncSession, subscription_id: str, tenant_id: str) -> None:
        result = await db.execute(
            select(WatchSubscription).where(
                WatchSubscription.id == subscription_id,
                WatchSubscription.tenant_id == tenant_id,
            )
        )
        subscription = result.scalar_one_or_none()
        if not subscription:
            raise ValueError("SUBSCRIPTION_NOT_FOUND")
        await db.delete(subscription)

    @staticmethod
    async def list_alerts(
        db: AsyncSession,
        tenant_id: str,
        status: str | None = None,
        severity: str | None = None,
        limit: int = 20,
    ) -> dict:
        stmt = select(WatchAlert).where(WatchAlert.tenant_id == tenant_id)
        if status:
            stmt = stmt.where(WatchAlert.status == status)
        if severity:
            stmt = stmt.where(WatchAlert.severity == severity)
        stmt = stmt.order_by(WatchAlert.triggered_at.desc()).limit(min(max(limit, 1), 100))
        result = await db.execute(stmt)
        alerts = result.scalars().all()

        summary_result = await db.execute(
            select(func.sum(case((WatchAlert.status == "unread", 1), else_=0))).where(
                WatchAlert.tenant_id == tenant_id
            )
        )
        unread_count = summary_result.scalar_one_or_none() or 0

        return {
            "data": [
                {
                    "alert_id": a.id,
                    "event_type": a.event_type,
                    "severity": a.severity,
                    "message": a.message,
                    "status": a.status,
                    "metadata": a.meta or {},
                    "triggered_at": a.triggered_at.isoformat() if a.triggered_at else None,
                }
                for a in alerts
            ],
            "summary": {"total_unread": unread_count},
        }

    @staticmethod
    async def acknowledge_alert(db: AsyncSession, alert_id: str, tenant_id: str) -> dict:
        result = await db.execute(
            select(WatchAlert).where(WatchAlert.id == alert_id, WatchAlert.tenant_id == tenant_id)
        )
        alert = result.scalar_one_or_none()
        if not alert:
            raise ValueError("ALERT_NOT_FOUND")
        alert.status = "acknowledged"
        await db.flush()
        return {"alert_id": alert.id, "status": alert.status}

    @staticmethod
    async def read_all_alerts(db: AsyncSession, tenant_id: str) -> dict:
        result = await db.execute(
            select(WatchAlert).where(
                WatchAlert.tenant_id == tenant_id,
                WatchAlert.status == "unread",
            )
        )
        alerts = result.scalars().all()
        for alert in alerts:
            alert.status = "acknowledged"
        await db.flush()
        return {"acknowledged_count": len(alerts), "message": f"{len(alerts)} alerts marked as read"}

    @staticmethod
    async def create_rule(
        db: AsyncSession,
        name: str,
        event_type: str,
        definition: dict,
        tenant_id: str,
        active: bool = True,
    ) -> WatchRule:
        rule = WatchRule(
            name=name,
            event_type=event_type,
            definition=definition,
            tenant_id=tenant_id,
            active=active,
        )
        db.add(rule)
        await db.flush()
        return rule

    @staticmethod
    async def list_rules(db: AsyncSession, tenant_id: str) -> list[WatchRule]:
        result = await db.execute(select(WatchRule).where(WatchRule.tenant_id == tenant_id))
        return result.scalars().all()
