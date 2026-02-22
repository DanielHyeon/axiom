from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import init_database, AsyncSessionLocal
from app.core.security import hash_password
from app.models.base_models import User, Tenant
from sqlalchemy import select
from app.core.middleware import TenantMiddleware, RequestIdMiddleware
from app.api import health
from app.api.auth.routes import router as auth_router
from app.api.agent.routes import router as agent_router
from app.api.events.routes import router as events_router
from app.api.gateway.routes import router as gateway_router
from app.api.process.routes import router as process_router
from app.api.watch.routes import router as watch_router
from app.api.users.routes import router as users_router
from app.core.security import get_current_user
from fastapi import Depends

app = FastAPI(title="Axiom Core", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://app.axiom.ai",
        "https://*.axiom.ai",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-Tenant-Id", "X-Request-Id"],
    expose_headers=["X-Request-Id", "X-Response-Time"],
)

app.add_middleware(RequestIdMiddleware)
app.add_middleware(TenantMiddleware)

app.include_router(health.router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1", dependencies=[Depends(get_current_user)])
app.include_router(process_router, prefix="/api/v1", dependencies=[Depends(get_current_user)])
app.include_router(watch_router, prefix="/api/v1", dependencies=[Depends(get_current_user)])
app.include_router(agent_router, prefix="/api/v1", dependencies=[Depends(get_current_user)])
app.include_router(gateway_router, prefix="/api/v1", dependencies=[Depends(get_current_user)])
app.include_router(events_router, prefix="/api/v1", dependencies=[Depends(get_current_user)])


@app.on_event("startup")
async def startup_event():
    await init_database()
    from app.core.config import settings
    if getattr(settings, "SEED_DEV_USER", False):
        async with AsyncSessionLocal() as session:
            from sqlalchemy import select, func
            r = await session.execute(select(func.count()).select_from(User))
            if (r.scalar() or 0) == 0:
                t = Tenant(id="default", name="Default", active=True)
                session.add(t)
                u = User(
                    id="seed-admin",
                    email=settings.SEED_DEV_EMAIL,
                    password_hash=hash_password(settings.SEED_DEV_PASSWORD),
                    tenant_id="default",
                    role="admin",
                    active=True,
                )
                session.add(u)
                await session.commit()
