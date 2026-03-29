import asyncio
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import init_database, AsyncSessionLocal
from app.core.security import hash_password
from app.models.base_models import User, Tenant
from sqlalchemy import select
from app.core.middleware import TenantMiddleware, RequestIdMiddleware
from app.core.rate_limiter import RateLimitMiddleware
from app.api import health
from app.api.auth.routes import router as auth_router
from app.modules.agent.api.routes import router as agent_router
from app.api.events.routes import router as events_router
from app.api.gateway.routes import router as gateway_router
from app.modules.process.api.routes import router as process_router
from app.modules.watch.api.routes import router as watch_router
from app.api.users.routes import router as users_router
from app.modules.case.api.routes import router as cases_router
from app.api.admin.event_routes import router as admin_events_router
from app.modules.watch.cep_api import router as cep_router
from app.modules.watch.watch_agent_api import router as watch_agent_router
from app.modules.governance.api.routes import router as governance_router
from app.modules.process_model.api.definition_routes import router as pm_definition_router
from app.modules.process_model.api.relation_routes import router as pm_relation_router
from app.modules.process_model.api.transition_routes import router as pm_transition_router
from app.core.security import get_current_user
from fastapi import Depends
from app.api.security_policies import router as security_policies_router
from app.api.audit import router as audit_router
from app.api.alert_dag import router as alert_dag_router
from app.api.event_detection import router as event_detection_router
from app.api.admin_audit import router as admin_audit_router

# 프로덕션 환경에서는 API 문서(Swagger, ReDoc)를 비활성화한다
_is_prod = os.getenv("ENVIRONMENT", "dev") == "production"

app = FastAPI(
    title="Axiom Core",
    version="1.0.0",
    docs_url=None if _is_prod else "/docs",
    redoc_url=None if _is_prod else "/redoc",
    openapi_url=None if _is_prod else "/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://app.axiom.ai",
        "https://*.axiom.ai",
        "http://localhost:3000",
        "http://localhost:5173",  # Docker canvas-ui
        "http://localhost:5174",  # Docker canvas-ui (포트 충돌 회피)
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-Tenant-Id", "X-Request-Id", "X-Axiom-Workspace-Id"],
    expose_headers=["X-Request-Id", "X-Response-Time"],
)

# 미들웨어 등록 순서 (Starlette: 마지막 추가 = 가장 바깥쪽 실행)
# 실행 순서: RequestId → AccessLog → Prometheus → SecurityHeaders → RateLimit → Tenant → handler
app.add_middleware(TenantMiddleware)
app.add_middleware(RateLimitMiddleware)

from shared.middleware.security_headers import SecurityHeadersMiddleware  # noqa: E402
app.add_middleware(
    SecurityHeadersMiddleware,
    allowed_connect_src="'self' http://localhost:9001 http://localhost:9002 http://localhost:9003 http://localhost:9004 http://localhost:9005 http://localhost:9100",
)

from shared.middleware.prometheus import setup_prometheus  # noqa: E402
_metrics_collector = setup_prometheus(app, service_name="core")

from shared.middleware.access_log import AccessLogMiddleware  # noqa: E402
app.add_middleware(AccessLogMiddleware, service_name="core")

# RequestId를 가장 마지막에 추가 → 가장 바깥쪽에서 실행 → 모든 내부 미들웨어가 request_id 사용 가능
app.add_middleware(RequestIdMiddleware)

app.include_router(health.router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1", dependencies=[Depends(get_current_user)])
app.include_router(cases_router, prefix="/api/v1", dependencies=[Depends(get_current_user)])
app.include_router(process_router, prefix="/api/v1", dependencies=[Depends(get_current_user)])
app.include_router(watch_router, prefix="/api/v1", dependencies=[Depends(get_current_user)])
app.include_router(agent_router, prefix="/api/v1", dependencies=[Depends(get_current_user)])
app.include_router(gateway_router, prefix="/api/v1", dependencies=[Depends(get_current_user)])
app.include_router(events_router, prefix="/api/v1", dependencies=[Depends(get_current_user)])
app.include_router(admin_events_router, prefix="/api/v1", dependencies=[Depends(get_current_user)])
app.include_router(cep_router, prefix="/api/v1", dependencies=[Depends(get_current_user)])
app.include_router(watch_agent_router, prefix="/api/v1", dependencies=[Depends(get_current_user)])
app.include_router(governance_router, prefix="/api/v1", dependencies=[Depends(get_current_user)])
app.include_router(pm_definition_router, prefix="/api/v1", dependencies=[Depends(get_current_user)])
app.include_router(pm_relation_router, prefix="/api/v1", dependencies=[Depends(get_current_user)])
app.include_router(pm_transition_router, prefix="/api/v1", dependencies=[Depends(get_current_user)])
# Phase 4 Sprint 12: 보안 정책 + 감사 로그
app.include_router(security_policies_router, dependencies=[Depends(get_current_user)])
app.include_router(audit_router, dependencies=[Depends(get_current_user)])
# Phase 5 Sprint 15: DAG 알림 + 이벤트 탐지
app.include_router(alert_dag_router, dependencies=[Depends(get_current_user)])
app.include_router(event_detection_router, dependencies=[Depends(get_current_user)])
# Sprint 3: 관리자용 감사 로그 + AI 사용량 API
app.include_router(admin_audit_router, dependencies=[Depends(get_current_user)])


@app.on_event("startup")
async def startup_event():
    await init_database()
    from app.core.config import settings
    if getattr(settings, "SEED_DEV_USER", False):
        async with AsyncSessionLocal() as session:
            from sqlalchemy import select, func
            from app.models.base_models import Case
            _SEED_TENANT_ID = "00000000-0000-0000-0000-000000000001"
            _SEED_USER_ID = "00000000-0000-0000-0000-000000000002"
            r = await session.execute(select(func.count()).select_from(User))
            if (r.scalar() or 0) == 0:
                t = Tenant(id=_SEED_TENANT_ID, name="Default", active=True)
                session.add(t)
                u = User(
                    id=_SEED_USER_ID,
                    email=settings.SEED_DEV_EMAIL,
                    password_hash=hash_password(settings.SEED_DEV_PASSWORD),
                    tenant_id=_SEED_TENANT_ID,
                    role="admin",
                    active=True,
                )
                session.add(u)
                await session.commit()
            # Seed demo case for ontology viewer
            _DEMO_CASE_ID = "00000000-0000-4000-a000-000000000100"
            rc = await session.execute(select(func.count()).select_from(Case).where(Case.id == _DEMO_CASE_ID))
            if (rc.scalar() or 0) == 0:
                session.add(Case(
                    id=_DEMO_CASE_ID,
                    tenant_id=_SEED_TENANT_ID,
                    title="[Demo] 제조업 프로세스 분석",
                    status="IN_PROGRESS",
                    priority="HIGH",
                    assignee="admin@local.axiom",
                ))
                await session.commit()

    # Start Outbox Relay Worker (Transactional Outbox pattern)
    from app.workers.sync import SyncWorker
    relay = SyncWorker(poll_interval_seconds=5, max_batch=100)
    asyncio.create_task(relay.run())
