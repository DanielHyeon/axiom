import uuid

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from app.api.datasource import router as datasource_router
from app.api.metadata_catalog import router as metadata_catalog_router
from app.api.query import router as query_router
from app.core.config import settings
from app.core.error_codes import public_error_message
from app.core.logging import configure_secret_redaction
from app.services.metrics import metrics_service
from app.services.mindsdb_client import mindsdb_client
from app.services.neo4j_metadata_store import neo4j_metadata_store
from app.services.postgres_metadata_store import postgres_metadata_store

configure_secret_redaction()

app = FastAPI(title="Axiom Weaver", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.weaver_cors_allowed_origins,
    allow_credentials=True,
    allow_methods=settings.weaver_cors_allowed_methods,
    allow_headers=settings.weaver_cors_allowed_headers,
)

app.include_router(datasource_router)
app.include_router(query_router)
app.include_router(metadata_catalog_router)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-Id") or f"req-{uuid.uuid4().hex}"
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    return response


@app.get("/health")
async def health_check():
    return {"status": "alive"}


@app.get("/health/live")
async def health_live():
    return {"status": "alive"}


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    return metrics_service.render_prometheus()


@app.get("/health/ready")
async def health_ready():
    dependencies: dict[str, str] = {
        "mindsdb": "disabled",
        "postgres": "disabled",
        "neo4j": "disabled",
    }
    details: dict[str, str] = {}

    if settings.external_mode:
        try:
            await mindsdb_client.health_check()
            dependencies["mindsdb"] = "up"
        except Exception as exc:
            dependencies["mindsdb"] = "down"
            details["mindsdb"] = public_error_message(exc)

    if settings.metadata_pg_mode:
        try:
            await postgres_metadata_store.health_check()
            dependencies["postgres"] = "up"
        except Exception as exc:
            dependencies["postgres"] = "down"
            details["postgres"] = public_error_message(exc)

    if settings.metadata_external_mode:
        try:
            await neo4j_metadata_store.health_check()
            dependencies["neo4j"] = "up"
        except Exception as exc:
            dependencies["neo4j"] = "down"
            details["neo4j"] = public_error_message(exc)

    is_ready = all(state != "down" for state in dependencies.values())
    body = {
        "status": "ready" if is_ready else "degraded",
        "dependencies": dependencies,
        "details": details,
    }
    if is_ready:
        return body
    return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=body)
