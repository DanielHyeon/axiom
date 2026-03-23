"""
Axiom Twin 서비스 — FastAPI 앱.

Phase 4: Digital Twin Runtime (포트 8006 → 9006).
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import init_database
from app.api.routes import router as twin_router
from app.simulation.api.scenario_routes import router as simulation_router

app = FastAPI(title="Axiom Twin", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(twin_router)
app.include_router(simulation_router)


@app.on_event("startup")
async def startup():
    await init_database()


@app.get("/health/live")
async def health_live():
    return {"status": "alive", "service": "twin"}
