from datetime import datetime, timezone

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base_models import WatchAlert, WatchRule, WatchSubscription


class WatchDomainError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class WatchService:
    VALID_RULE_TYPES = {"deadline", "threshold", "pattern"}

    @staticmethod
    def _validate_rule(rule: dict) -> None:
        rule_type = (rule or {}).get("type")
        if rule_type not in WatchService.VALID_RULE_TYPES:
            raise WatchDomainError(400, "INVALID_RULE", "rule.type must be deadline|threshold|pattern")
        if rule_type == "deadline" and not (rule or {}).get("days_before"):
            raise WatchDomainError(400, "INVALID_RULE", "deadline rule requires days_before")
        if rule_type == "threshold":
            if not all((rule or {}).get(key) is not None for key in ("field", "operator", "threshold")):
                raise WatchDomainError(400, "INVALID_RULE", "threshold rule requires field/operator/threshold")
        if rule_type == "pattern":
            if not all((rule or {}).get(key) is not None for key in ("window_hours", "min_count")):
                raise WatchDomainError(400, "INVALID_RULE", "pattern rule requires window_hours/min_count")

    @staticmethod
    async def create_subscription(
        db: AsyncSession,
        user_id: str,
        event_type: str,
        channels: list[str],
        tenant_id: str,
        case_id: str | None = None,
        active: bool = True,
        rule: dict | None = None,
        severity_override: str | None = None,
    ) -> WatchSubscription:
        WatchService._validate_rule(rule or {"type": "deadline", "days_before": 7})
        count_result = await db.execute(
            select(func.count()).select_from(WatchSubscription).where(
                WatchSubscription.user_id == user_id,
                WatchSubscription.tenant_id == tenant_id,
            )
        )
        if (count_result.scalar_one() or 0) >= 50:
            raise WatchDomainError(429, "TOO_MANY_SUBSCRIPTIONS", "subscription limit exceeded (50)")

        duplicate_result = await db.execute(
            select(WatchSubscription).where(
                WatchSubscription.user_id == user_id,
                WatchSubscription.tenant_id == tenant_id,
                WatchSubscription.event_type == event_type,
                WatchSubscription.case_id == case_id,
                WatchSubscription.active.is_(True),
            )
        )
        if duplicate_result.scalar_one_or_none():
            raise WatchDomainError(409, "DUPLICATE_SUBSCRIPTION", "duplicate subscription exists")

        subscription = WatchSubscription(
            user_id=user_id,
            event_type=event_type,
            channels=channels,
            case_id=case_id,
            rule=rule or {"type": "deadline", "days_before": 7},
            severity_override=severity_override,
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
        rule: dict | None,
        severity_override: str | None,
    ) -> WatchSubscription:
        result = await db.execute(
            select(WatchSubscription).where(
                WatchSubscription.id == subscription_id,
                WatchSubscription.tenant_id == tenant_id,
            )
        )
        subscription = result.scalar_one_or_none()
        if not subscription:
            raise WatchDomainError(404, "SUBSCRIPTION_NOT_FOUND", "subscription not found")
        if channels is not None:
            subscription.channels = channels
        if active is not None:
            subscription.active = active
        if rule is not None:
            WatchService._validate_rule(rule)
            subscription.rule = rule
        if severity_override is not None:
            subscription.severity_override = severity_override
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
            raise WatchDomainError(404, "SUBSCRIPTION_NOT_FOUND", "subscription not found")
        await db.delete(subscription)

    @staticmethod
    async def list_alerts(
        db: AsyncSession,
        tenant_id: str,
        status: str | None = None,
        severity: str | None = None,
        case_id: str | None = None,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
        cursor: str | None = None,
        limit: int = 20,
    ) -> dict:
        safe_limit = min(max(limit, 1), 100)
        stmt = select(WatchAlert).where(WatchAlert.tenant_id == tenant_id)
        if status:
            stmt = stmt.where(WatchAlert.status == status)
        if severity:
            stmt = stmt.where(WatchAlert.severity == severity)
        if case_id:
            stmt = stmt.where(WatchAlert.case_id == case_id)
        if from_ts:
            stmt = stmt.where(WatchAlert.triggered_at >= from_ts)
        if to_ts:
            stmt = stmt.where(WatchAlert.triggered_at <= to_ts)
        if cursor:
            cursor_obj = await db.execute(
                select(WatchAlert).where(WatchAlert.id == cursor, WatchAlert.tenant_id == tenant_id)
            )
            cursor_alert = cursor_obj.scalar_one_or_none()
            if cursor_alert and cursor_alert.triggered_at:
                stmt = stmt.where(WatchAlert.triggered_at < cursor_alert.triggered_at)

        stmt = stmt.order_by(WatchAlert.triggered_at.desc(), WatchAlert.id.desc()).limit(safe_limit + 1)
        result = await db.execute(stmt)
        alerts = result.scalars().all()
        has_more = len(alerts) > safe_limit
        page = alerts[:safe_limit]
        next_cursor = page[-1].id if has_more and page else None

        summary_result = await db.execute(
            select(
                func.sum(case((WatchAlert.status == "unread", 1), else_=0)),
                func.sum(case((WatchAlert.severity == "CRITICAL", 1), else_=0)),
                func.sum(case((WatchAlert.severity == "HIGH", 1), else_=0)),
            ).where(WatchAlert.tenant_id == tenant_id)
        )
        unread_count, critical_count, high_count = summary_result.one()

        return {
            "data": [
                {
                    "alert_id": a.id,
                    "event_type": a.event_type,
                    "severity": a.severity,
                    "message": a.message,
                    "case_id": a.case_id,
                    "case_name": a.case_name,
                    "status": a.status,
                    "triggered_at": a.triggered_at.isoformat() if a.triggered_at else None,
                    "action_url": a.action_url,
                    "metadata": a.meta or {},
                }
                for a in page
            ],
            "cursor": {"next": next_cursor, "has_more": has_more},
            "summary": {
                "total_unread": unread_count or 0,
                "critical_count": critical_count or 0,
                "high_count": high_count or 0,
            },
        }

    @staticmethod
    async def acknowledge_alert(db: AsyncSession, alert_id: str, tenant_id: str) -> dict:
        result = await db.execute(
            select(WatchAlert).where(WatchAlert.id == alert_id, WatchAlert.tenant_id == tenant_id)
        )
        alert = result.scalar_one_or_none()
        if not alert:
            raise WatchDomainError(404, "ALERT_NOT_FOUND", "alert not found")
        alert.status = "acknowledged"
        alert.acknowledged_at = datetime.now(timezone.utc)
        await db.flush()
        return {"alert_id": alert.id, "status": alert.status}

    @staticmethod
    async def dismiss_alert(db: AsyncSession, alert_id: str, tenant_id: str) -> dict:
        result = await db.execute(
            select(WatchAlert).where(WatchAlert.id == alert_id, WatchAlert.tenant_id == tenant_id)
        )
        alert = result.scalar_one_or_none()
        if not alert:
            raise WatchDomainError(404, "ALERT_NOT_FOUND", "alert not found")
        alert.status = "dismissed"
        alert.dismissed_at = datetime.now(timezone.utc)
        await db.flush()
        return {"alert_id": alert.id, "status": alert.status}

    @staticmethod
    async def read_all_alerts(db: AsyncSession, tenant_id: str, user_id: str | None = None) -> dict:
        stmt = select(WatchAlert).where(
            WatchAlert.tenant_id == tenant_id,
            WatchAlert.status == "unread",
        )
        if user_id:
            subquery = (
                select(WatchSubscription.id)
                .where(
                    WatchSubscription.user_id == user_id,
                    WatchSubscription.tenant_id == tenant_id,
                )
                .subquery()
            )
            stmt = stmt.where(WatchAlert.subscription_id.in_(select(subquery.c.id)))

        result = await db.execute(stmt)
        alerts = result.scalars().all()
        now = datetime.now(timezone.utc)
        for alert in alerts:
            alert.status = "acknowledged"
            alert.acknowledged_at = now
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
        WatchService._validate_rule(definition)
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

    @staticmethod
    async def get_rule(db: AsyncSession, tenant_id: str, rule_id: str) -> WatchRule:
        result = await db.execute(
            select(WatchRule).where(
                WatchRule.id == rule_id,
                WatchRule.tenant_id == tenant_id,
            )
        )
        rule = result.scalar_one_or_none()
        if not rule:
            raise WatchDomainError(404, "RULE_NOT_FOUND", "rule not found")
        return rule

    @staticmethod
    async def update_rule(
        db: AsyncSession,
        tenant_id: str,
        rule_id: str,
        name: str | None,
        event_type: str | None,
        definition: dict | None,
        active: bool | None,
    ) -> WatchRule:
        rule = await WatchService.get_rule(db=db, tenant_id=tenant_id, rule_id=rule_id)
        if definition is not None:
            WatchService._validate_rule(definition)
            rule.definition = definition
        if name is not None:
            rule.name = name
        if event_type is not None:
            rule.event_type = event_type
        if active is not None:
            rule.active = active
        await db.flush()
        return rule

    @staticmethod
    async def delete_rule(db: AsyncSession, tenant_id: str, rule_id: str) -> None:
        rule = await WatchService.get_rule(db=db, tenant_id=tenant_id, rule_id=rule_id)
        await db.delete(rule)

    @staticmethod
    async def create_alert(
        db: AsyncSession,
        tenant_id: str,
        subscription_id: str | None,
        event_type: str,
        severity: str,
        message: str,
        case_id: str | None = None,
        case_name: str | None = None,
        action_url: str | None = None,
        meta: dict | None = None,
    ) -> WatchAlert:
        """CEP Worker용 알림 생성. severity는 LOW|MEDIUM|HIGH|CRITICAL."""
        alert = WatchAlert(
            subscription_id=subscription_id,
            event_type=event_type,
            case_id=case_id,
            case_name=case_name,
            severity=severity.upper() if severity else "MEDIUM",
            message=message,
            status="unread",
            action_url=action_url,
            meta=meta or {},
            tenant_id=tenant_id,
        )
        db.add(alert)
        await db.flush()
        return alert

    @staticmethod
    async def list_subscriptions_for_event(
        db: AsyncSession,
        tenant_id: str,
        event_type: str,
        case_id: str | None,
    ) -> list[WatchSubscription]:
        """event_type·tenant_id·case_id(선택)에 맞는 활성 구독 목록."""
        stmt = select(WatchSubscription).where(
            WatchSubscription.tenant_id == tenant_id,
            WatchSubscription.event_type == event_type,
            WatchSubscription.active.is_(True),
        )
        if case_id is not None:
            stmt = stmt.where(
                (WatchSubscription.case_id.is_(None)) | (WatchSubscription.case_id == case_id)
            )
        result = await db.execute(stmt)
        return list(result.scalars().all())
