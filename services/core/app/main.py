from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.middleware import TenantMiddleware, RequestIdMiddleware
from app.api import health
from app.api.agent.routes import router as agent_router
from app.api.gateway.routes import router as gateway_router
from app.api.process.routes import router as process_router
from app.api.watch.routes import router as watch_router

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
app.include_router(process_router, prefix="/api/v1")
app.include_router(watch_router, prefix="/api/v1")
app.include_router(agent_router, prefix="/api/v1")
app.include_router(gateway_router, prefix="/api/v1")
