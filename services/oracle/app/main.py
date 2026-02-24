from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api.text2sql import router as text2sql_router
from app.api.health import router as health_router
from app.api.feedback import router as feedback_router
from app.api.meta import router as meta_router
from app.api.events import router as events_router, watch_agent_router
from app.core.rate_limit import RateLimitExceeded
import structlog

logger = structlog.get_logger()

app = FastAPI(title="Axiom Oracle", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"success": False, "error": exc.detail},
        headers={"Retry-After": str(exc.retry_after_seconds)},
    )


app.include_router(text2sql_router)
app.include_router(health_router)
app.include_router(feedback_router)
app.include_router(meta_router)
app.include_router(events_router)
app.include_router(watch_agent_router)

@app.get("/health/live")
async def health_live():
    return {"status": "alive"}
