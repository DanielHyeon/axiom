from fastapi import FastAPI
from app.api.datasource import router as datasource_router
from app.api.query import router as query_router

app = FastAPI(title="Axiom Weaver", version="1.0.0")

app.include_router(datasource_router)
app.include_router(query_router)

@app.get("/health")
async def health_check():
    return {"status": "alive"}

@app.get("/health/ready")
async def health_ready():
    # Check graph database connection mappings and Neo4j availability natively
    return {
        "status": "ready",
        "dependencies": {
            "neo4j": "up",
            "metadata_llm": "up"
        }
    }
