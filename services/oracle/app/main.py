from fastapi import FastAPI
from app.api.text2sql import router as text2sql_router
from app.api.health import router as health_router
from app.api.feedback import router as feedback_router
import structlog

logger = structlog.get_logger()

app = FastAPI(title="Axiom Oracle", version="2.0.0")
app.include_router(text2sql_router)
app.include_router(health_router)
app.include_router(feedback_router)

@app.get("/health/live")
async def health_live():
    return {"status": "alive"}
