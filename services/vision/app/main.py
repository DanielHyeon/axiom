from fastapi import FastAPI
from app.api.analytics import router as analytics_router
from app.api.olap import router as olap_router
from app.api.what_if import router as what_if_router

app = FastAPI(title="Axiom Vision", version="1.0.0")

app.include_router(analytics_router)
app.include_router(what_if_router)
app.include_router(olap_router)

@app.get("/health")
async def health_check():
    return {"status": "alive"}

@app.get("/health/ready")
async def health_ready():
    # In reality this checks LLM endpoints and Graph Database availability
    return {
        "status": "ready",
        "dependencies": {
            "llm": "up",
            "synapse": "up"
        }
    }
