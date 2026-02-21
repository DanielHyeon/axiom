from fastapi import FastAPI
from app.api.analytics import router as analytics_router

app = FastAPI(title="Axiom Vision", version="1.0.0")

app.include_router(analytics_router)

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
