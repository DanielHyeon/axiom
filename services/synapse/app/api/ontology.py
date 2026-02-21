from fastapi import APIRouter

router = APIRouter(prefix="/api/v3/synapse/ontology", tags=["Ontology"])

@router.get("/")
async def get_ontology():
    return {"message": "Ontology API Stub"}

@router.post("/extract-ontology")
async def extract_ontology():
    """Async task dispatch for document ontology extraction"""
    return {"task_id": "mock_task_uuid", "status": "processing"}
